from multiprocessing import Process
import time
from typing import Optional, Any, Dict
from pathlib import Path
import json
import os
import tempfile
import threading
import re
from urllib.parse import quote_plus
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.concurrency import run_in_threadpool

from core.settings import SETTINGS_PATH
from core.nst import connect_profile, stop_profile, stop_all_browsers
from core.browser import FBController
from core import control as control_state
from core.control import smart_sleep
from core.scraper import SimpleBot
from core.settings import get_settings
from worker.get_all_info import get_all_info_from_post_ids_dir, get_info_for_profile_ids
from core.paths import get_data_dir, get_settings_path, get_config_dir
app = FastAPI(title="NST Tool API", version="1.0.0")
class InfoRunRequest(BaseModel):
    mode: str = "all"  # "all" hoặc "selected"
    profiles: list[str] | None = None


# Cho phép frontend (file tĩnh) gọi API qua localhost
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Bot processes (mỗi profile 1 process độc lập RUN/REST)
_bot_lock = threading.Lock()
_bot_processes: Dict[str, Process] = {}
_settings_lock = threading.Lock()
_join_groups_lock = threading.Lock()
_join_groups_processes: Dict[str, Process] = {}
_feed_lock = threading.Lock()
_feed_processes: Dict[str, Process] = {}


def _hard_stop_everything(reason: str = "") -> dict:
    """
    STOP kiểu "fresh start":
    - Signal STOP ngay (set_global_emergency_stop=True) để các loop thoát nếu còn sống
    - Đóng toàn bộ NST browser
    - Terminate runner/join/feed processes (đóng hẳn, không giữ sleep)
    - Reset runtime_control.json về mặc định (SẴN SÀNG)
    """
    global _bot_processes

    print("=" * 60)
    print(f"🛑 [HARD_STOP] {reason}".strip())
    print("=" * 60)

    # 1) Signal STOP
    try:
        control_state.set_global_emergency_stop(True)
    except Exception:
        pass

    # 2) Close all NST browsers
    nst_ok = False
    nst_err = None
    try:
        nst_ok = bool(stop_all_browsers())
    except Exception as e:
        nst_err = str(e)
        print(f"⚠️ stop_all_browsers lỗi: {e}")

    # 3) Kill bot processes
    bot_killed: list[str] = []
    try:
        with _bot_lock:
            for pid, proc in list(_bot_processes.items()):
                try:
                    if proc and proc.is_alive():
                        proc.terminate()
                        proc.join(timeout=3)
                        bot_killed.append(pid)
                except Exception:
                    pass
                _bot_processes.pop(pid, None)
    except Exception:
        pass

    # 4) Kill join groups processes
    join_killed: list[str] = []
    try:
        with _join_groups_lock:
            _prune_join_group_processes()
            for pid, proc in list(_join_groups_processes.items()):
                try:
                    if proc and proc.is_alive():
                        proc.terminate()
                        proc.join(timeout=3)
                        join_killed.append(pid)
                except Exception:
                    pass
                _join_groups_processes.pop(pid, None)
    except Exception:
        pass

    # 5) Kill feed processes
    feed_killed: list[str] = []
    try:
        with _feed_lock:
            _prune_feed_processes()
            for pid, proc in list(_feed_processes.items()):
                try:
                    if proc and proc.is_alive():
                        proc.terminate()
                        proc.join(timeout=3)
                        feed_killed.append(pid)
                except Exception:
                    pass
                _feed_processes.pop(pid, None)
    except Exception:
        pass

    # 6) Stop group scan queue
    try:
        global _group_scan_stop_requested, _group_scan_queue
        with _group_scan_lock:
            _group_scan_stop_requested = True
            _group_scan_queue.clear()
        print("🛑 Đã dừng group scan queue")
    except Exception:
        pass

    # 7) Stop multi-thread runner
    multi_thread_stopped = False
    try:
        from worker.multi_thread import stop_multi_thread
        result = stop_multi_thread()
        if result and result.get("status") == "ok":
            multi_thread_stopped = True
            print("🛑 Đã dừng multi-thread runner")
        else:
            print(f"⚠️ Multi-thread runner dừng không thành công: {result}")
    except Exception as e:
        print(f"⚠️ Lỗi khi dừng multi-thread runner: {e}")
        import traceback
        traceback.print_exc()

    # 8) Reset runtime state về mặc định (để lần sau bấm chạy là "mới hoàn toàn")
    try:
        control_state.reset_all_state()
    except Exception:
        # fallback: ít nhất clear emergency stop để UI không bị kẹt
        try:
            control_state.reset_emergency_stop(clear_stopped_profiles=True)
        except Exception:
            pass

    return {
        "status": "ok",
        "nst_stop_all_ok": nst_ok,
        "nst_error": nst_err,
        "bot_killed": bot_killed,
        "join_killed": join_killed,
        "feed_killed": feed_killed,
        "multi_thread_stopped": multi_thread_stopped,
    }


def _prune_bot_processes() -> None:
    dead = []
    for pid, proc in list(_bot_processes.items()):
        try:
            if not proc.is_alive():
                dead.append(pid)
        except Exception:
            dead.append(pid)
    for pid in dead:
        _bot_processes.pop(pid, None)


def _run_bot_profile_loop(
    profile_id: str,
    run_minutes: float,  # Hỗ trợ số thập phân
    rest_minutes: float,  # Hỗ trợ số thập phân
    text: str,
    mode: str,
    all_profile_ids: Optional[list[str]] = None,  # Danh sách tất cả profile đang chạy
) -> None:
    """
    Worker độc lập cho 1 profile:
    - chạy RUN_MINUTES (active time, pause freeze)
    - ngủ REST_MINUTES (pause freeze)
    - lặp lại cho tới khi STOP (global hoặc stop theo profile)
    """
    pid = str(profile_id or "").strip()
    if not pid:
        return

    cfg = get_settings()
    target_url = cfg.target_url
    m = str(mode or "feed").strip().lower()
    # Hỗ trợ feed+search và feed_search cho quét bài viết
    if m not in ("feed", "search", "feed+search", "feed_search"):
        m = "feed"
    t = str(text or "").strip()
    # Chỉ tạo search URL nếu là search thuần (không phải feed+search, vì feed+search sẽ tự chuyển sau)
    if m == "search" and t:
        q = quote_plus(t)
        target_url = f"https://www.facebook.com/search/top/?q={q}"

    # Hỗ trợ số thập phân (0.5 phút = 30 giây)
    run_m = float(run_minutes or 0)
    rest_m = float(rest_minutes or 0)
    if run_m <= 0:
        run_m = float(getattr(cfg, "run_minutes", 30) or 30)
    if rest_m <= 0:
        rest_m = float(getattr(cfg, "rest_minutes", 120) or 120)

    duration_seconds = max(1, int(run_m * 60))
    rest_seconds = max(1, int(rest_m * 60))

    # 🔍 DEBUG: Log thời gian đã parse
    print(f"⏱️ [{pid}] Worker nhận: run_minutes={run_minutes} -> run_m={run_m} phút -> duration_seconds={duration_seconds}s")
    print(f"⏱️ [{pid}] Worker nhận: rest_minutes={rest_minutes} -> rest_m={rest_m} phút -> rest_seconds={rest_seconds}s")

    try:
        while True:
            # STOP/PAUSE trước khi bắt đầu phiên
            stop, paused, reason = control_state.check_flags(pid)
            if stop:
                print(f"🛑 [{pid}] STOP trước khi start loop ({reason})")
                try:
                    control_state.set_profile_state(pid, "STOPPED")
                except Exception:
                    pass
                return
            if paused:
                print(f"⏸️ [{pid}] PAUSED trước khi start loop ({reason})")
                control_state.wait_if_paused(pid, sleep_seconds=0.5)

            fb: Optional[FBController] = None
            try:
                control_state.set_profile_state(pid, "RUNNING")
            except Exception:
                pass

            try:
                ws = connect_profile(pid)
                fb = FBController(ws)
                fb.profile_id = pid
                # tuyệt đối độc lập: chỉ xử lý trong profile này
                try:
                    fb.all_profile_ids = [pid]
                except Exception:
                    pass
                # filter text nếu có
                try:
                    if t:
                        parts = []
                        for chunk in t.replace("\n", ",").split(","):
                            s = " ".join(str(chunk).strip().split())
                            if s:
                                parts.append(s)
                        seen = set()
                        user_keywords = []
                        for x in parts:
                            k = x.lower()
                            if k in seen:
                                continue
                            seen.add(k)
                            user_keywords.append(x)
                        fb.user_keywords = user_keywords
                except Exception:
                    pass
                fb.connect()
                
                # Hỗ trợ mode feed+search cho quét bài viết
                if (m == "feed+search" or m == "feed_search") and t:
                    from core.scraper import FeedSearchCombinedScanBot
                    bot = FeedSearchCombinedScanBot(fb, t)
                    # Bắt đầu với Feed URL
                    feed_url = "https://www.facebook.com/"
                    bot.run(feed_url, duration=duration_seconds)
                else:
                    bot = SimpleBot(fb)
                    bot.run(target_url, duration=duration_seconds)
                    
            except RuntimeError as e:
                # STOP/BROWSER_CLOSED/ACCOUNT_BANNED => thoát phiên
                if (
                    "EMERGENCY_STOP" in str(e)
                    or "BROWSER_CLOSED" in str(e)
                    or "ACCOUNT_BANNED" in str(e)
                ):
                    print(f"🛑 [{pid}] Dừng bot ({e})")
                    return
                raise
            except Exception as e:
                error_str = str(e)
                print(f"❌ Lỗi ở profile {pid}: {error_str}")
                
                # Nếu là lỗi nghiêm trọng (profile không tồn tại, NST không chạy), dừng ngay
                is_critical_error = (
                    "không tồn tại" in error_str.lower() or
                    "profile" in error_str.lower() and "not found" in error_str.lower() or
                    "không thể kết nối đến nst" in error_str.lower() or
                    "nst server" in error_str.lower()
                )
                
                try:
                    control_state.set_profile_state(pid, "ERROR")
                except Exception:
                    pass
                
                # Nếu là lỗi nghiêm trọng, dừng loop ngay
                if is_critical_error:
                    print(f"🛑 [{pid}] Dừng loop do lỗi nghiêm trọng: {error_str}")
                    return
            finally:
                # 🆕 LẤY COOKIE TỪ BROWSER ĐANG MỞ VÀ LƯU VÀO settings.json
                # Lấy cookie TRƯỚC KHI đóng browser để đảm bảo browser còn mở
                try:
                    if fb and getattr(fb, "page", None):
                        try:
                            # Kiểm tra page và context còn hoạt động
                            if hasattr(fb.page, "context") and fb.page.context:
                                print(f"🍪 [{pid}] Đang lấy cookie từ browser đang mở...")
                                cookie_string = fb.save_cookies()
                                if cookie_string:
                                    print(f"✅ [{pid}] Đã lưu cookie vào settings.json")
                                else:
                                    print(f"⚠️ [{pid}] Không lấy được cookie (có thể chưa đăng nhập hoặc cookie rỗng)")
                        except Exception as cookie_err:
                            # Nếu page/context đã đóng thì bỏ qua, không ảnh hưởng luồng chính
                            error_msg = str(cookie_err).lower()
                            if any(kw in error_msg for kw in ["closed", "disconnected", "target page", "context"]):
                                print(f"⚠️ [{pid}] Browser đã đóng, không thể lấy cookie")
                            else:
                                print(f"⚠️ [{pid}] Lỗi khi lấy cookie: {cookie_err}")
                except Exception as e:
                    # Bỏ qua lỗi, không ảnh hưởng luồng chính
                    print(f"⚠️ [{pid}] Không thể lấy cookie: {e}")
                
                # đóng playwright + NST profile best-effort
                try:
                    if fb and getattr(fb, "page", None):
                        try:
                            fb.page.close()
                        except Exception:
                            pass
                except Exception:
                    pass
                try:
                    if fb and getattr(fb, "browser", None) and getattr(fb.browser, "contexts", None):
                        for ctx in list(fb.browser.contexts):
                            try:
                                ctx.close()
                            except Exception:
                                pass
                except Exception:
                    pass
                try:
                    if fb and getattr(fb, "browser", None):
                        try:
                            fb.browser.close()
                        except Exception:
                            pass
                except Exception:
                    pass
                try:
                    if fb and getattr(fb, "play", None):
                        try:
                            fb.play.stop()
                        except Exception:
                            pass
                except Exception:
                    pass
                try:
                    stop_profile(pid)
                except Exception:
                    pass

            # Check stop sau khi kết thúc phiên
            stop, paused, reason = control_state.check_flags(pid)
            if stop:
                print(f"🛑 [{pid}] STOP sau phiên ({reason}) -> thoát loop")
                try:
                    control_state.set_profile_state(pid, "STOPPED")
                except Exception:
                    pass
                return

            # 🆕 TẬN DỤNG THỜI GIAN NGHỈ ĐỂ LẤY THÔNG TIN
            # Browser đã tắt, payload/cookies lấy từ file → không cần browser
            # Chỉ profile đầu tiên trong danh sách mới gọi để tránh duplicate
            if rest_m > 0 and all_profile_ids and len(all_profile_ids) > 0:
                # Chỉ profile đầu tiên mới gọi lấy thông tin cho tất cả profile
                is_first_profile = (pid == all_profile_ids[0])
                if is_first_profile:
                    try:
                        print(f"📊 [{pid}] Tận dụng thời gian nghỉ để lấy thông tin cho {len(all_profile_ids)} profile(s)...")
                        from worker.get_all_info import get_info_for_profile_ids
                        import threading
                        
                        def collect_info():
                            try:
                                summary = get_info_for_profile_ids(all_profile_ids)
                                print(f"✅ [{pid}] Đã lấy thông tin cho {len(all_profile_ids)} profile(s): {summary}")
                            except Exception as e:
                                print(f"⚠️ [{pid}] Lỗi khi lấy thông tin: {e}")
                        
                        # Chạy trong thread để không block rest period
                        info_thread = threading.Thread(target=collect_info, daemon=True)
                        info_thread.start()
                        # Không join() để không block, cho phép rest period chạy song song
                    except Exception as e:
                        print(f"⚠️ [{pid}] Không thể khởi động lấy thông tin: {e}")

            # REST (độc lập theo profile) - pause freeze
            try:
                smart_sleep(rest_seconds, pid)
            except RuntimeError as e:
                if "EMERGENCY_STOP" in str(e):
                    print(f"🛑 [{pid}] STOP trong REST -> thoát")
                    try:
                        control_state.set_profile_state(pid, "STOPPED")
                    except Exception:
                        pass
                    return
                raise
    except RuntimeError as e:
        if "EMERGENCY_STOP" in str(e):
            print(f"🛑 [{pid}] EMERGENCY_STOP trong loop -> thoát")
            try:
                control_state.set_profile_state(pid, "STOPPED")
            except Exception:
                pass
            return
        raise


def _run_join_groups_worker(profile_id: str, groups: list[str]) -> None:
    """Worker chạy join groups cho 1 profile (để chạy song song nhiều profile)."""
    try:
        from core.join_groups import run_batch_join_from_list
        run_batch_join_from_list(profile_id, groups)
    except Exception as exc:
        print(f"❌ Join groups worker lỗi ({profile_id}): {exc}")


def _run_feed_worker(
    profile_id: str,
    mode: str,
    text: str,
    run_minutes: float,  # Hỗ trợ số thập phân
    rest_minutes: float,  # Hỗ trợ số thập phân
    all_profile_ids: Optional[list[str]] = None,
) -> None:
    """
    Worker chạy nuôi acc (feed/search & like) cho 1 profile theo vòng lặp:
    chạy run_minutes -> tắt -> nghỉ rest_minutes -> lặp lại.
    Nếu rest_minutes <= 0 thì chỉ chạy 1 lần.
    """
    try:
        from core.search_worker import feed_and_like, search_and_like, feed_and_search_combined
        m = str(mode or "feed").strip().lower()
        # Hỗ trợ số thập phân (0.5 phút = 30 giây)
        run_m = float(run_minutes or 0)
        rest_m = float(rest_minutes or 0)
        if run_m <= 0:
            run_m = 30.0

        # 🔍 DEBUG: Log thời gian đã parse
        print(f"⏱️ [FEED] {profile_id} Worker nhận: run_minutes={run_minutes} (raw) -> run_m={run_m} phút = {run_m * 60} giây")
        print(f"⏱️ [FEED] {profile_id} Worker nhận: rest_minutes={rest_minutes} (raw) -> rest_m={rest_m} phút = {rest_m * 60} giây")
        print(f"⏱️ [FEED] {profile_id} Mode: {m}, Text: '{text}'")

        try:
            while True:
                # STOP/PAUSE checkpoint
                stop, paused, reason = control_state.check_flags(profile_id)
                if stop:
                    print(f"🛑 [FEED] {profile_id} EMERGENCY_STOP ({reason}) -> dừng worker")
                    break
                if paused:
                    print(f"⏸️ [FEED] {profile_id} PAUSED ({reason}) -> sleep")
                    control_state.wait_if_paused(profile_id, sleep_seconds=0.5)

                try:
                    if m == "search":
                        search_and_like(profile_id, text or "", duration_minutes=run_m, all_profile_ids=all_profile_ids)
                    elif m == "feed+search" or m == "feed_search":
                        # Mode kết hợp: Feed nửa thời gian, rồi chuyển sang Search
                        feed_and_search_combined(profile_id, text or "", duration_minutes=run_m, all_profile_ids=all_profile_ids)
                    else:
                        feed_and_like(profile_id, text or "", duration_minutes=run_m, all_profile_ids=all_profile_ids)
                except RuntimeError as e:
                    if "EMERGENCY_STOP" in str(e):
                        print(f"🛑 [FEED] {profile_id} EMERGENCY_STOP trong bot ({reason}) -> dừng")
                        return
                    raise

                if rest_m <= 0:
                    break

                # nghỉ rồi chạy lại (pause freeze)
                try:
                    smart_sleep(rest_m * 60, profile_id)
                except RuntimeError as e:
                    if "EMERGENCY_STOP" in str(e):
                        print(f"🛑 [FEED] {profile_id} EMERGENCY_STOP trong REST -> dừng")
                        return
                    raise
        except RuntimeError as e:
            if "EMERGENCY_STOP" in str(e):
                print(f"🛑 [FEED] {profile_id} EMERGENCY_STOP trong loop -> dừng")
                return
            raise
    except Exception as exc:
        print(f"❌ Feed worker lỗi ({profile_id}): {exc}")


def _close_fb_controller_best_effort(fb: Optional[FBController], profile_id: str) -> None:
    """
    Đóng sạch tab/context playwright + yêu cầu NST stop (giống logic trong cookie fetch).
    """
    try:
        if fb and getattr(fb, "page", None):
            try:
                fb.page.close()
            except Exception:
                pass
    except Exception:
        pass
    try:
        if fb and getattr(fb, "browser", None) and getattr(fb.browser, "contexts", None):
            for ctx in list(fb.browser.contexts):
                try:
                    ctx.close()
                except Exception:
                    pass
    except Exception:
        pass
    try:
        if fb and getattr(fb, "browser", None):
            try:
                fb.browser.close()
            except Exception:
                pass
    except Exception:
        pass
    try:
        if fb and getattr(fb, "play", None):
            try:
                fb.play.stop()
            except Exception:
                pass
    except Exception:
        pass

    # Best-effort: yêu cầu NST stop/close browser instance của profile
    try:
        stop_profile(profile_id)
    except Exception:
        pass


def _force_close_nst_tabs_for_profile(profile_id: str) -> dict:
    """
    Force đóng tab NST theo đúng kiểu cookie:
    connect -> attach CDP -> close page/context/browser/play -> stop_profile
    """
    pid = _norm_profile_id(profile_id)
    if not pid:
        return {"profile_id": profile_id, "ok": False, "reason": "empty_profile_id"}

    fb: Optional[FBController] = None
    connected = False
    try:
        ws = connect_profile(pid)
        fb = FBController(ws)
        fb.profile_id = pid
        fb.connect()
        connected = True
        return {"profile_id": pid, "ok": True, "connected": True}
    except Exception as exc:
        # Nếu connect fail vẫn cố stop_profile ở finally
        return {"profile_id": pid, "ok": False, "connected": connected, "reason": str(exc)}
    finally:
        _close_fb_controller_best_effort(fb, pid)


def _norm_profile_id(value: str) -> str:
    """Chuẩn hoá profile_id: bỏ toàn bộ whitespace (tránh lỗi dính space khi copy/paste)."""
    return re.sub(r"\s+", "", str(value or "")).strip()


class RunRequest(BaseModel):
    run_minutes: Optional[float] = None  # Hỗ trợ số thập phân (0.5 phút = 30 giây)
    rest_minutes: Optional[float] = None  # Hỗ trợ số thập phân
    profile_ids: Optional[list[str]] = None
    # text filter cho scan bài viết (dùng trong core/browser.py)
    text: Optional[str] = None
    # mode cho scan bài viết: "feed" | "search"
    mode: Optional[str] = None


class RunMultiThreadRequest(BaseModel):
    """Request cho multi-thread runner (feed+search + group scan song song)"""
    run_minutes: Optional[float] = None
    rest_minutes: Optional[float] = None
    profile_ids: Optional[list[str]] = None
    text: Optional[str] = None
    mode: Optional[str] = None
    # Group scan params
    post_count: Optional[int] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


## NOTE: AppRunner mode đã được thay bằng bot per-profile độc lập (xem _run_bot_profile_loop)


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}


@app.post("/run")
def run_bot(payload: Optional[RunRequest] = Body(None)) -> dict:
    """
    Start bot per-profile độc lập (mỗi profile 1 process loop RUN/REST).
    """
    # start per-profile bot processes (độc lập)

    run_minutes = payload.run_minutes if payload else None
    rest_minutes = payload.rest_minutes if payload else None
    profile_ids = payload.profile_ids if payload else None
    text = payload.text if payload else None
    mode = payload.mode if payload else None

    # Validate profile_ids (bắt buộc chọn profile như UI)
    if not profile_ids:
        raise HTTPException(status_code=400, detail="profile_ids rỗng")
    pids = [_norm_profile_id(x) for x in (profile_ids or [])]
    pids = [p for p in pids if p]
    if not pids:
        raise HTTPException(status_code=400, detail="profile_ids không hợp lệ")

    # Nếu user bấm CHẠY mà trước đó đã STOP/PAUSE, auto reset để job chạy được.
    # - Tắt GLOBAL_PAUSE
    # - Nếu đang GLOBAL_EMERGENCY_STOP thì reset
    # - resume_profiles cho đúng các profile được yêu cầu chạy.
    try:
        # Luôn clear global_pause khi bấm bất kỳ nút start nào (scan/feed/search)
        control_state.set_global_pause(False)

        stop, _paused, reason = control_state.check_flags(None)
        if stop:
            print(f"🟡 [/run] GLOBAL_EMERGENCY_STOP đang bật ({reason}) -> auto reset để chạy")
            control_state.reset_emergency_stop(clear_stopped_profiles=False)
        # Nếu profile đang bị stop riêng lẻ thì clear để chạy được
        control_state.resume_profiles(pids)
    except Exception as _e:
        pass

    # Dọn state cũ trong runtime_control: chỉ giữ profile_states của đúng pids đang chạy
    try:
        def _keep_only_selected(st: dict) -> None:
            ps = st.get("profile_states")
            if not isinstance(ps, dict):
                ps = {}
            keep = {pid: ps.get(pid) or "RUNNING" for pid in pids}
            st["profile_states"] = keep
            # remove paused/stopped ngoài danh sách được chạy (tránh hiện profile lạ)
            st["paused_profiles"] = [x for x in (st.get("paused_profiles") or []) if str(x) in set(pids)]
            st["stopped_profiles"] = [x for x in (st.get("stopped_profiles") or []) if str(x) in set(pids)]
        control_state._update(_keep_only_selected)  # type: ignore[attr-defined]
    except Exception:
        pass

    # ✅ Cho phép chạy ngay cả khi thiếu cookie/access_token (không bắt buộc)
    _validate_profiles_requirements(pids, require_cookie=False, require_access_token=False)

    m = str(mode or "feed").strip().lower()
    # Hỗ trợ feed+search và feed_search
    if m not in ("feed", "search", "feed+search", "feed_search"):
        m = "feed"
    # Search và Feed+Search bắt buộc có text để search
    if m in ("search", "feed+search", "feed_search") and not str(text or "").strip():
        raise HTTPException(status_code=400, detail="Search và Feed+Search cần text")

    started: list[str] = []
    skipped: list[dict] = []
    # Hỗ trợ số thập phân (0.5 phút = 30 giây)
    run_m = float(run_minutes or 0) if payload else 0.0
    rest_m = float(rest_minutes or 0) if payload else 0.0
    txt = str(text or "")
    md = str(m or "feed")

    # 🔍 DEBUG: Log thời gian nhận từ frontend
    print(f"📥 [API /run] Nhận từ frontend: run_minutes={run_minutes} (raw), run_m={run_m} (parsed), rest_minutes={rest_minutes} (raw), rest_m={rest_m} (parsed)")
    print(f"📥 [API /run] Thời gian chạy: {run_m} phút = {run_m * 60} giây, Thời gian nghỉ: {rest_m} phút = {rest_m * 60} giây")
    print(f"📥 [API /run] Mode: {md}, Text: {txt}, Profiles: {pids}")

    with _bot_lock:
        _prune_bot_processes()
        for pid in pids:
            existing = _bot_processes.get(pid)
            if existing and existing.is_alive():
                skipped.append({"profile_id": pid, "reason": "already_running"})
                continue
            proc = Process(
                target=_run_bot_profile_loop,
                args=(pid, run_m, rest_m, txt, md, pids),  # Truyền danh sách tất cả profile_ids
                daemon=True,
            )
            proc.start()
            _bot_processes[pid] = proc
            started.append(pid)

    return {"status": "ok", "started": started, "skipped": skipped, "running": list(_bot_processes.keys())}


@app.post("/stop")
def stop_bot() -> dict:
    """
    STOP (fresh start):
    - Đóng hẳn mọi thứ (NST + kill runner/jobs)
    - Reset runtime_control.json về mặc định
    - Lần sau bấm chạy sẽ tính lại RUN/REST từ đầu (PAUSE mới là cái giữ timer)
    """
    return _hard_stop_everything(reason="/stop")


@app.get("/status")
def status() -> dict:
    with _bot_lock:
        _prune_bot_processes()
        running = [pid for pid, proc in _bot_processes.items() if proc and proc.is_alive()]
    return {"running": len(running) > 0, "bot_profile_ids": running}


@app.get("/settings")
def get_settings_json() -> dict:
    """
    Trả nội dung file backend/config/settings.json để frontend hiển thị.
    """
    path: Path = SETTINGS_PATH
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Không tìm thấy settings.json: {path}")

    try:
        with path.open(encoding="utf-8") as f:
            raw = json.load(f)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"settings.json không hợp lệ: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Không đọc được settings.json: {exc}") from exc

    return raw


def _read_settings_raw() -> Dict[str, Any]:
    path: Path = SETTINGS_PATH
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Không tìm thấy settings.json: {path}")
    try:
        with path.open(encoding="utf-8") as f:
            raw = json.load(f)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"settings.json không hợp lệ: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Không đọc được settings.json: {exc}") from exc

    if not isinstance(raw, dict):
        raise HTTPException(status_code=400, detail="settings.json phải là object")
    return raw


def _validate_profiles_requirements(
    profile_ids: list[str],
    *,
    require_cookie: bool = False,
    require_access_token: bool = False,
) -> None:
    """
    Nếu có profile thiếu cookie/access_token (theo require_*), sẽ raise 400 và KHÔNG cho start job.
    Mặc định không bắt buộc (require_cookie=False, require_access_token=False) để cho phép các trường trống.
    """
    raw = _read_settings_raw()
    profiles = raw.get("PROFILE_IDS") or {}
    if not isinstance(profiles, dict):
        profiles = {}

    missing_list: list[dict] = []
    for pid in profile_ids:
        cfg = profiles.get(pid)
        missing: list[str] = []
        if not isinstance(cfg, dict):
            # profile chưa tồn tại trong settings.json
            if require_cookie:
                missing.append("cookie")
            if require_access_token:
                missing.append("access_token")
        else:
            if require_cookie and not str(cfg.get("cookie") or "").strip():
                missing.append("cookie")
            if require_access_token and not str(cfg.get("access_token") or cfg.get("accessToken") or "").strip():
                missing.append("access_token")

        if missing:
            missing_list.append({"profile_id": pid, "missing": missing})

    if missing_list:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Thiếu cấu hình profile (cookie/access_token). Hãy cập nhật trước khi chạy.",
                "missing": missing_list,
            },
        )


def _atomic_write_json(path: Path, data: Dict[str, Any]) -> None:
    """
    Ghi JSON an toàn: write temp file cùng thư mục rồi replace.
    """
    directory = str(path.parent)
    os.makedirs(directory, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(prefix="settings_", suffix=".json", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp_path, str(path))
    except Exception:
        try:
            os.remove(tmp_path)
        except Exception:
            pass
        raise


def _merge_group_ids(existing: Any, new_items: list[str]) -> list[str]:
    """Merge + de-dupe group ids, giữ thứ tự (existing trước)."""
    base: list[str] = []
    if isinstance(existing, list):
        base = [str(x).strip() for x in existing if str(x).strip()]
    elif isinstance(existing, str):
        base = [s.strip() for s in existing.split(",") if s.strip()]

    seen: set[str] = set()
    merged: list[str] = []
    for gid in base + new_items:
        gid2 = str(gid or "").strip()
        if not gid2 or gid2 in seen:
            continue
        seen.add(gid2)
        merged.append(gid2)
    return merged


def _write_settings_raw(raw: Dict[str, Any]) -> None:
    try:
        _atomic_write_json(SETTINGS_PATH, raw)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Không ghi được settings.json: {exc}") from exc


class ApiKeyPayload(BaseModel):
    api_key: str


class ProfileCreatePayload(BaseModel):
    profile_id: str


class ProfileUpdatePayload(BaseModel):
    cookie: Optional[str] = None
    access_token: Optional[str] = None
    fb_dtsg: Optional[str] = None
    lsd: Optional[str] = None
    spin_r: Optional[str] = None
    spin_t: Optional[str] = None


class ProfileGroupsPayload(BaseModel):
    # Có thể truyền 1 group hoặc nhiều group (append).
    group_id: Optional[str] = None
    group_ids: Optional[list[str]] = None


class ProfileGroupsReplacePayload(BaseModel):
    # Replace hoàn toàn groups của profile. Cho phép rỗng để xoá hết.
    groups: Optional[list[str]] = None


class JoinGroupsRequest(BaseModel):
    profile_ids: list[str]


class JoinGroupsStopRequest(BaseModel):
    # nếu không truyền -> stop tất cả
    profile_ids: Optional[list[str]] = None


class FeedStartRequest(BaseModel):
    profile_ids: list[str]
    mode: str = "feed"  # "feed" | "search"
    text: str = ""      # input text (địa điểm, hoặc query search)
    # backward-compat: giữ field cũ nếu frontend cũ còn gọi
    filter_text: str = ""
    run_minutes: float = 30.0  # Hỗ trợ số thập phân (0.5 phút = 30 giây)
    rest_minutes: float = 0.0  # Hỗ trợ số thập phân


class FeedStopRequest(BaseModel):
    profile_ids: Optional[list[str]] = None


class AccountStatusPayload(BaseModel):
    profile_id: str
    status: str
    banned: bool
    reason: Optional[str] = None
    message: str
    url: Optional[str] = None
    keyword: Optional[str] = None
    title: Optional[str] = None
    checked_at: Optional[str] = None


@app.put("/settings/api-key")
def update_api_key(payload: ApiKeyPayload) -> dict:
    with _settings_lock:
        raw = _read_settings_raw()
        raw["API_KEY"] = str(payload.api_key or "").strip()
        _write_settings_raw(raw)
        return {"status": "ok"}


@app.post("/account/status")
def report_account_status(payload: AccountStatusPayload) -> dict:
    """
    Nhận báo cáo trạng thái account từ worker.
    ✅ Chức năng dự phòng: KHÔNG dừng bot, chỉ lưu/log để frontend cảnh báo.
    """
    pid = _norm_profile_id(payload.profile_id)
    if not pid:
        raise HTTPException(status_code=400, detail="profile_id rỗng")

    status_file = get_data_dir() / "account_status.json"
    status_file.parent.mkdir(parents=True, exist_ok=True)

    data: Dict[str, Any] = {}
    if status_file.exists():
        try:
            with status_file.open("r", encoding="utf-8") as f:
                data = json.load(f) or {}
        except Exception:
            data = {}

    data[pid] = {
        "profile_id": pid,
        "status": payload.status,
        "banned": bool(payload.banned),
        "reason": payload.reason,
        "message": payload.message,
        "url": payload.url,
        "keyword": payload.keyword,
        "title": payload.title,
        "checked_at": payload.checked_at or datetime.utcnow().isoformat(),
    }

    try:
        with status_file.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Không ghi được account_status.json: {e}")

    print(f"🔔 [ACCOUNT_STATUS] {pid}: {payload.message}")
    return {"status": "ok", "profile_id": pid}


@app.get("/account/status")
def get_account_status() -> dict:
    """
    Lấy snapshot trạng thái account (do worker đã ghi ra file).
    Frontend chỉ dùng để hiển thị cảnh báo, không điều khiển luồng.
    """
    status_file = get_data_dir() / "account_status.json"
    if not status_file.exists():
        return {"accounts": {}}

    try:
        with status_file.open("r", encoding="utf-8") as f:
            data = json.load(f) or {}
        return {"accounts": data}
    except Exception as e:
        print(f"⚠️ Không đọc được account_status.json: {e}")
        return {"accounts": {}}


@app.post("/settings/profiles")
def add_profile(payload: ProfileCreatePayload) -> dict:
    pid = _norm_profile_id(payload.profile_id)
    if not pid:
        raise HTTPException(status_code=400, detail="profile_id rỗng")

    with _settings_lock:
        raw = _read_settings_raw()
        profiles = raw.get("PROFILE_IDS")
        if profiles is None or isinstance(profiles, list) or isinstance(profiles, str):
            # Nếu đang format cũ, convert sang dict
            profiles = {}
        if not isinstance(profiles, dict):
            raise HTTPException(status_code=400, detail="PROFILE_IDS phải là object")

        # Tạo profile mới: luôn có cookie/access_token/fb_dtsg/lsd/spin_r/spin_t/groups (groups trống)
        cur = profiles.get(pid)
        if cur is None or not isinstance(cur, dict):
            cur = {}
            profiles[pid] = cur
        cur.setdefault("cookie", "")
        cur.setdefault("access_token", "")
        cur.setdefault("fb_dtsg", "")
        cur.setdefault("lsd", "")
        cur.setdefault("spin_r", "")
        cur.setdefault("spin_t", "")
        cur.setdefault("groups", [])
        raw["PROFILE_IDS"] = profiles
        _write_settings_raw(raw)
        return {"status": "ok"}


@app.put("/settings/profiles/{profile_id}")
def update_profile(profile_id: str, payload: ProfileUpdatePayload) -> dict:
    pid = _norm_profile_id(profile_id)
    if not pid:
        raise HTTPException(status_code=400, detail="profile_id rỗng")

    with _settings_lock:
        raw = _read_settings_raw()
        profiles = raw.get("PROFILE_IDS") or {}
        if isinstance(profiles, list) or isinstance(profiles, str):
            profiles = {}
        if not isinstance(profiles, dict):
            raise HTTPException(status_code=400, detail="PROFILE_IDS phải là object")

        cur = profiles.get(pid)
        if cur is None:
            profiles[pid] = {}
            cur = profiles[pid]
        if not isinstance(cur, dict):
            cur = {}
            profiles[pid] = cur

        if payload.cookie is not None:
            cur["cookie"] = str(payload.cookie)
        if payload.access_token is not None:
            cur["access_token"] = str(payload.access_token)
        if payload.fb_dtsg is not None:
            cur["fb_dtsg"] = str(payload.fb_dtsg)
        if payload.lsd is not None:
            cur["lsd"] = str(payload.lsd)
        if payload.spin_r is not None:
            cur["spin_r"] = str(payload.spin_r)
        if payload.spin_t is not None:
            cur["spin_t"] = str(payload.spin_t)

        raw["PROFILE_IDS"] = profiles
        _write_settings_raw(raw)
        return {"status": "ok"}


@app.post("/settings/profiles/{profile_id}/groups")
def add_or_sync_profile_groups(profile_id: str, payload: ProfileGroupsPayload) -> dict:
    """
    Cập nhật groups cho 1 profile:
    - hoặc truyền group_id / group_ids để append vào PROFILE_IDS[pid].groups
    """
    pid = _norm_profile_id(profile_id)
    if not pid:
        raise HTTPException(status_code=400, detail="profile_id rỗng")

    new_groups: list[str] = []
    if payload.group_ids:
        new_groups.extend([str(x or "").strip() for x in payload.group_ids])
    if payload.group_id:
        new_groups.append(str(payload.group_id or "").strip())
    new_groups = [g for g in new_groups if g]

    if not new_groups:
        raise HTTPException(status_code=400, detail="Thiếu group_id/group_ids")

    with _settings_lock:
        raw = _read_settings_raw()
        profiles = raw.get("PROFILE_IDS") or {}
        if isinstance(profiles, list) or isinstance(profiles, str):
            profiles = {}
        if not isinstance(profiles, dict):
            raise HTTPException(status_code=400, detail="PROFILE_IDS phải là object")

        cur = profiles.get(pid)
        if cur is None or not isinstance(cur, dict):
            cur = {}
            profiles[pid] = cur

        merged = _merge_group_ids(cur.get("groups"), new_groups)

        cur["groups"] = merged
        raw["PROFILE_IDS"] = profiles
        _write_settings_raw(raw)

        return {"status": "ok", "profile_id": pid, "groups": merged}


def _extract_page_id_from_group_url(url: str) -> Optional[str]:
    """
    Extract page_id từ Facebook group URL.
    Hỗ trợ các format:
    - https://www.facebook.com/groups/486503093715305
    - https://www.facebook.com/groups/486503093715305/
    - https://www.facebook.com/groups/tuyendungkisuIT
    - 486503093715305 (chỉ số)
    """
    if not url or not isinstance(url, str):
        return None
    
    url = url.strip()
    if not url:
        return None
    
    # Nếu chỉ là số thì trả về luôn
    if url.isdigit():
        return url
    
    # Tìm pattern /groups/{id} trong URL
    import re
    patterns = [
        r"/groups/(\d+)",  # /groups/486503093715305
        r"groups/(\d+)",   # groups/486503093715305 (không có / đầu)
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url, re.IGNORECASE)
        if match:
            page_id = match.group(1)
            if page_id and page_id.isdigit():
                return page_id
    
    # Nếu không tìm thấy số, có thể là group name (như tuyendungkisuIT)
    # Trong trường hợp này, cần dùng get_id_from_url để lấy page_id
    # Nhưng để đơn giản, trả về None và sẽ bỏ qua
    return None


@app.put("/settings/profiles/{profile_id}/groups")
def replace_profile_groups(profile_id: str, payload: ProfileGroupsReplacePayload) -> dict:
    """
    Ghi đè toàn bộ groups của 1 profile (đúng yêu cầu: trong textarea có gì thì đè lên cái cũ).
    Tự động tách page_id từ URL và lưu vào groups.json.
    """
    pid = _norm_profile_id(profile_id)
    if not pid:
        raise HTTPException(status_code=400, detail="profile_id rỗng")

    raw_groups = payload.groups if payload and payload.groups is not None else []
    if not isinstance(raw_groups, list):
        raise HTTPException(status_code=400, detail="groups phải là list")

    cleaned: list[str] = []
    seen: set[str] = set()
    for item in raw_groups:
        s = str(item or "").strip()
        if not s:
            continue
        # de-dupe để tránh spam
        if s in seen:
            continue
        seen.add(s)
        cleaned.append(s)

    # Lưu vào settings.json (giữ nguyên logic cũ)
    with _settings_lock:
        raw = _read_settings_raw()
        profiles = raw.get("PROFILE_IDS") or {}
        if isinstance(profiles, list) or isinstance(profiles, str):
            profiles = {}
        if not isinstance(profiles, dict):
            raise HTTPException(status_code=400, detail="PROFILE_IDS phải là object")

        cur = profiles.get(pid)
        if cur is None or not isinstance(cur, dict):
            cur = {}
            profiles[pid] = cur

        cur["groups"] = cleaned
        raw["PROFILE_IDS"] = profiles
        _write_settings_raw(raw)
    
    # Tự động tách page_id từ URL và lưu vào groups.json
    try:
        from core.join_groups import save_group_page_id
        
        saved_count = 0
        for group_url in cleaned:
            page_id = _extract_page_id_from_group_url(group_url)
            if page_id:
                # Normalize URL để đảm bảo format đúng
                normalized_url = group_url
                if not normalized_url.startswith("http"):
                    if "/groups/" in normalized_url:
                        normalized_url = f"https://www.facebook.com{normalized_url}" if normalized_url.startswith("/") else f"https://www.facebook.com/{normalized_url}"
                    else:
                        normalized_url = f"https://www.facebook.com/groups/{normalized_url}"
                
                # Lưu vào groups.json
                if save_group_page_id(pid, page_id, normalized_url):
                    saved_count += 1
                    print(f"✅ Đã lưu group vào groups.json: profile_id={pid}, page_id={page_id}, url={normalized_url}")
                else:
                    print(f"⚠️ Không lưu được group: profile_id={pid}, page_id={page_id}, url={normalized_url}")
            else:
                print(f"⚠️ Không tách được page_id từ URL: {group_url}")
        
        if saved_count > 0:
            print(f"✅ Đã lưu {saved_count}/{len(cleaned)} group(s) vào groups.json cho profile {pid}")
    except Exception as e:
        print(f"⚠️ Lỗi khi lưu groups vào groups.json: {e}")
        import traceback
        traceback.print_exc()
        # Không raise error để không ảnh hưởng đến việc lưu vào settings.json
    
        return {"status": "ok", "profile_id": pid, "groups": cleaned}


def _prune_join_group_processes() -> None:
    """Dọn các process đã chạy xong khỏi map."""
    dead = []
    for pid, proc in list(_join_groups_processes.items()):
        try:
            if not proc.is_alive():
                dead.append(pid)
        except Exception:
            dead.append(pid)
    for pid in dead:
        _join_groups_processes.pop(pid, None)


def _prune_feed_processes() -> None:
    dead = []
    for pid, proc in list(_feed_processes.items()):
        try:
            if not proc.is_alive():
                dead.append(pid)
        except Exception:
            dead.append(pid)
    for pid in dead:
        _feed_processes.pop(pid, None)


@app.post("/groups/join")
def auto_join_groups(payload: JoinGroupsRequest) -> dict:
    """
    Chạy auto join group cho các profile đã chọn (mỗi profile 1 process → chạy song song).
    Groups lấy từ settings.json: PROFILE_IDS[pid].groups
    """
    # Nếu user bấm JOIN mà trước đó đã STOP/PAUSE, auto reset để job chạy được.
    try:
        # Clear global_pause khi bấm JOIN
        control_state.set_global_pause(False)

        stop, _paused, reason = control_state.check_flags(None)
        if stop:
            print(f"🟡 [/groups/join] GLOBAL_EMERGENCY_STOP đang bật ({reason}) -> auto reset để join")
            control_state.reset_emergency_stop(clear_stopped_profiles=False)
    except Exception:
        pass

    if not payload.profile_ids:
        raise HTTPException(status_code=400, detail="profile_ids rỗng")

    pids = [_norm_profile_id(x) for x in payload.profile_ids]
    pids = [p for p in pids if p]
    if not pids:
        raise HTTPException(status_code=400, detail="profile_ids không hợp lệ")

    # Clear STOPPED cho đúng các profile được yêu cầu join
    try:
        control_state.resume_profiles(pids)
    except Exception:
        pass

    # ✅ Join group không bắt buộc cookie/access_token (cho phép trống)
    _validate_profiles_requirements(pids, require_cookie=False, require_access_token=False)

    started: list[str] = []
    skipped: list[dict] = []

    with _join_groups_lock:
        _prune_join_group_processes()

        raw = _read_settings_raw()
        profiles = raw.get("PROFILE_IDS") or {}
        if not isinstance(profiles, dict):
            profiles = {}

        for pid in pids:
            # skip nếu đang chạy
            existing = _join_groups_processes.get(pid)
            if existing and existing.is_alive():
                skipped.append({"profile_id": pid, "reason": "already_running"})
                continue

            cfg = profiles.get(pid)
            if not isinstance(cfg, dict):
                skipped.append({"profile_id": pid, "reason": "profile_not_found"})
                continue

            groups = cfg.get("groups")
            if not isinstance(groups, list):
                groups = []
            groups = [str(g or "").strip() for g in groups if str(g or "").strip()]

            if len(groups) == 0:
                skipped.append({"profile_id": pid, "reason": "no_groups"})
                continue

            proc = Process(
                target=_run_join_groups_worker,
                args=(pid, groups),
                daemon=True,
            )
            proc.start()
            _join_groups_processes[pid] = proc
            started.append(pid)

    return {
        "status": "ok",
        "started": started,
        "skipped": skipped,
        "running": list(_join_groups_processes.keys()),
    }


@app.post("/groups/join/stop")
def stop_auto_join_groups(payload: Optional[JoinGroupsStopRequest] = Body(None)) -> dict:
    """
    Dừng auto join group:
    - Không truyền payload -> dừng tất cả
    - Có profile_ids -> dừng theo danh sách
    """
    target: Optional[list[str]] = None
    if payload and payload.profile_ids is not None:
        target = [_norm_profile_id(x) for x in (payload.profile_ids or [])]
        target = [p for p in target if p]

    stopped: list[str] = []
    not_running: list[str] = []

    with _join_groups_lock:
        _prune_join_group_processes()
        keys = list(_join_groups_processes.keys())
        to_stop = keys if target is None else [p for p in target if p in _join_groups_processes]

        # terminate processes
        for pid in to_stop:
            proc = _join_groups_processes.get(pid)
            if not proc:
                continue
            try:
                if proc.is_alive():
                    proc.terminate()
                    proc.join(timeout=5)
            except Exception:
                pass
            _join_groups_processes.pop(pid, None)
            stopped.append(pid)

        if target is not None:
            for pid in target:
                if pid not in stopped:
                    not_running.append(pid)

    # Best-effort: yêu cầu NST stop/close browser instance của profile (giống luồng lấy cookie)
    for pid in stopped:
        try:
            stop_profile(pid)
        except Exception:
            pass

    return {"status": "ok", "stopped": stopped, "not_running": not_running}


@app.get("/groups/join/status")
def join_groups_status() -> dict:
    """Trạng thái join-groups đang chạy."""
    with _join_groups_lock:
        _prune_join_group_processes()
        running = []
        for pid, proc in _join_groups_processes.items():
            try:
                if proc.is_alive():
                    running.append(pid)
            except Exception:
                pass
    return {"running": running}


@app.get("/feed/status")
def feed_status() -> dict:
    """Trạng thái nuôi acc (feed) đang chạy."""
    with _feed_lock:
        _prune_feed_processes()
        running: list[str] = []
        for pid, proc in _feed_processes.items():
            try:
                if proc.is_alive():
                    running.append(pid)
            except Exception:
                pass
    return {"running": running}


@app.post("/feed/start")
def feed_start(payload: FeedStartRequest) -> dict:
    """Chạy nuôi acc (feed & like) cho các profile đã chọn (mỗi profile 1 process)."""
    if not payload.profile_ids:
        raise HTTPException(status_code=400, detail="profile_ids rỗng")

    pids = [_norm_profile_id(x) for x in payload.profile_ids]
    pids = [p for p in pids if p]
    if not pids:
        raise HTTPException(status_code=400, detail="profile_ids không hợp lệ")

    # Nếu user bấm NUÔI ACC mà trước đó đã STOP/PAUSE, auto reset STOP/PAUSE để job chạy được.
    try:
        # Clear global_pause khi bấm NUÔI ACC
        control_state.set_global_pause(False)

        stop, _paused, reason = control_state.check_flags(None)
        if stop:
            print(f"🟡 [/feed/start] GLOBAL_EMERGENCY_STOP đang bật ({reason}) -> auto reset để chạy")
            control_state.reset_emergency_stop(clear_stopped_profiles=False)
        control_state.resume_profiles(pids)
    except Exception:
        pass

    # ✅ Cho phép chạy ngay cả khi thiếu cookie/access_token (không bắt buộc)
    _validate_profiles_requirements(pids, require_cookie=False, require_access_token=False)

    # Hỗ trợ số thập phân (0.5 phút = 30 giây)
    run_minutes = float(payload.run_minutes or 0)
    if run_minutes <= 0:
        raise HTTPException(status_code=400, detail="run_minutes phải > 0")
    rest_minutes = float(payload.rest_minutes or 0)
    if rest_minutes < 0:
        raise HTTPException(status_code=400, detail="rest_minutes phải >= 0")

    # 🔍 DEBUG: Log thời gian nhận từ frontend
    print(f"📥 [API /feed/start] Nhận từ frontend: run_minutes={payload.run_minutes} (raw), run_minutes={run_minutes} (parsed), rest_minutes={payload.rest_minutes} (raw), rest_minutes={rest_minutes} (parsed)")
    print(f"📥 [API /feed/start] Thời gian chạy: {run_minutes} phút = {run_minutes * 60} giây, Thời gian nghỉ: {rest_minutes} phút = {rest_minutes * 60} giây")

    started: list[str] = []
    skipped: list[dict] = []
    mode = str(payload.mode or "feed").strip().lower()
    text = str(payload.text or "").strip()
    # backward-compat
    if not text and getattr(payload, "filter_text", None):
        text = str(payload.filter_text or "").strip()
    # Cho phép text rỗng nếu mode=feed (sẽ chỉ filter theo keyword mặc định)
    # Search và Feed+Search bắt buộc có text
    if not text and mode in ("search", "feed+search", "feed_search"):
        raise HTTPException(status_code=400, detail="text rỗng (search và feed+search cần text)")

    with _feed_lock:
        _prune_feed_processes()
        for pid in pids:
            existing = _feed_processes.get(pid)
            if existing and existing.is_alive():
                skipped.append({"profile_id": pid, "reason": "already_running"})
                continue

            proc = Process(
                target=_run_feed_worker,
                args=(pid, mode, text, run_minutes, rest_minutes, pids),
                daemon=True,
            )
            proc.start()
            _feed_processes[pid] = proc
            started.append(pid)

    return {"status": "ok", "started": started, "skipped": skipped, "running": list(_feed_processes.keys())}


@app.post("/feed/stop")
def feed_stop(payload: Optional[FeedStopRequest] = Body(None)) -> dict:
    """Dừng nuôi acc (feed) theo list profile_ids hoặc dừng tất cả nếu không truyền."""
    target: Optional[list[str]] = None
    if payload and payload.profile_ids is not None:
        target = [_norm_profile_id(x) for x in (payload.profile_ids or [])]
        target = [p for p in target if p]

    stopped: list[str] = []
    with _feed_lock:
        _prune_feed_processes()
        keys = list(_feed_processes.keys())
        to_stop = keys if target is None else [p for p in target if p in _feed_processes]
        for pid in to_stop:
            proc = _feed_processes.get(pid)
            try:
                if proc and proc.is_alive():
                    proc.terminate()
                    proc.join(timeout=5)
            except Exception:
                pass
            _feed_processes.pop(pid, None)
            stopped.append(pid)

    for pid in stopped:
        try:
            stop_profile(pid)
        except Exception:
            pass

    return {"status": "ok", "stopped": stopped}


@app.get("/jobs/status")
def jobs_status() -> dict:
    """Trạng thái chung (để UI hiển thị/diagnose)."""
    with _bot_lock:
        _prune_bot_processes()
        bot_running_pids = []
        for pid, proc in _bot_processes.items():
            try:
                if proc.is_alive():
                    bot_running_pids.append(pid)
            except Exception:
                pass
    is_bot_running = len(bot_running_pids) > 0
    with _join_groups_lock:
        _prune_join_group_processes()
        join_running = []
        for pid, proc in _join_groups_processes.items():
            try:
                if proc.is_alive():
                    join_running.append(pid)
            except Exception:
                pass
    with _feed_lock:
        _prune_feed_processes()
        feed_running = []
        for pid, proc in _feed_processes.items():
            try:
                if proc.is_alive():
                    feed_running.append(pid)
            except Exception:
                pass
    return {
        "bot_running": is_bot_running,
        "bot_pid": None,
        "bot_profile_ids": bot_running_pids,
        "join_groups_running": join_running,
        "feed_running": feed_running,
    }


# ==============================================================================
# FRONTEND STATE (lưu trạng thái UI để khôi phục khi reload)
# ==============================================================================

class FrontendStateRequest(BaseModel):
    selected_profiles: Optional[Dict[str, bool]] = None
    feed_mode: Optional[str] = None
    feed_text: Optional[str] = None
    feed_run_minutes: Optional[float] = None  # Hỗ trợ số thập phân
    feed_rest_minutes: Optional[float] = None  # Hỗ trợ số thập phân
    scan_mode: Optional[str] = None
    scan_text: Optional[str] = None
    scan_run_minutes: Optional[float] = None  # Hỗ trợ số thập phân
    scan_rest_minutes: Optional[float] = None  # Hỗ trợ số thập phân
    group_scan_post_count: Optional[int] = None
    group_scan_start_date: Optional[str] = None
    group_scan_end_date: Optional[str] = None


def _get_frontend_state_path() -> Path:
    """Đường dẫn file lưu frontend state."""
    return get_data_dir() / "frontend_state.json"


@app.get("/frontend/state")
def get_frontend_state() -> dict:
    """Đọc trạng thái frontend đã lưu."""
    path = _get_frontend_state_path()
    if not path.exists():
        return {
            "selected_profiles": {},
            "feed_mode": "feed",
            "feed_text": "",
            "feed_run_minutes": 30,
            "feed_rest_minutes": 120,
            "scan_mode": "feed",
            "scan_text": "",
            "scan_run_minutes": 30,
            "scan_rest_minutes": 120,
            "group_scan_post_count": 0,
            "group_scan_start_date": "",
            "group_scan_end_date": "",
            "last_updated": None,
        }
    
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Không đọc được frontend state: {exc}") from exc


@app.post("/frontend/state")
def save_frontend_state(payload: FrontendStateRequest) -> dict:
    """Lưu trạng thái frontend."""
    path = _get_frontend_state_path()
    
    # Đọc state hiện tại (nếu có)
    current_state = {}
    if path.exists():
        try:
            with path.open(encoding="utf-8") as f:
                current_state = json.load(f)
        except Exception:
            pass
    
    # Cập nhật state mới
    if payload.selected_profiles is not None:
        current_state["selected_profiles"] = payload.selected_profiles
    if payload.feed_mode is not None:
        current_state["feed_mode"] = payload.feed_mode
    if payload.feed_text is not None:
        current_state["feed_text"] = payload.feed_text
    if payload.feed_run_minutes is not None:
        current_state["feed_run_minutes"] = payload.feed_run_minutes
    if payload.feed_rest_minutes is not None:
        current_state["feed_rest_minutes"] = payload.feed_rest_minutes
    if payload.scan_mode is not None:
        current_state["scan_mode"] = payload.scan_mode
    if payload.scan_text is not None:
        current_state["scan_text"] = payload.scan_text
    if payload.scan_run_minutes is not None:
        current_state["scan_run_minutes"] = payload.scan_run_minutes
    if payload.scan_rest_minutes is not None:
        current_state["scan_rest_minutes"] = payload.scan_rest_minutes
    if payload.group_scan_post_count is not None:
        current_state["group_scan_post_count"] = payload.group_scan_post_count
    if payload.group_scan_start_date is not None:
        current_state["group_scan_start_date"] = payload.group_scan_start_date
    if payload.group_scan_end_date is not None:
        current_state["group_scan_end_date"] = payload.group_scan_end_date
    
    current_state["last_updated"] = datetime.now().isoformat()
    
    # Ghi file
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(current_state, f, ensure_ascii=False, indent=2)
        return {"status": "ok", "message": "Đã lưu frontend state"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Không ghi được frontend state: {exc}") from exc


@app.post("/jobs/stop-all")
def stop_all_jobs() -> dict:
    """
    Dừng tất cả tác vụ nền (dùng chung cho auto join group + sau này nuôi acc).
    """
    # Legacy endpoint: vẫn map về hard stop (fresh start) cho đúng spec mới
    return _hard_stop_everything(reason="/jobs/stop-all")


# ==============================================================================
# INFO COLLECTOR (get_all_info_from_post_ids_dir)
# ==============================================================================

def _check_data_exists(mode: str, profiles: Optional[list[str]] = None) -> bool:
    """
    Helper function: Kiểm tra xem có dữ liệu bài viết không trước khi lấy cookie.
    Trả về True nếu có dữ liệu, False nếu không có.
    """
    from pathlib import Path
    post_ids_dir = get_data_dir() / "post_ids"
    
    if not post_ids_dir.exists():
        return False
    
    if mode == "selected":
        if not profiles:
            return False
        # Kiểm tra xem có file nào cho các profile đã chọn không
        for pid in profiles:
            file_path = post_ids_dir / f"{pid}.json"
            if file_path.exists():
                try:
                    with file_path.open("r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, list) and len(data) > 0:
                            return True
                except Exception:
                    pass
        return False
    else:
        # Mode "all": kiểm tra xem có file nào có dữ liệu không
        json_files = list(post_ids_dir.glob("*.json"))
        for file_path in json_files:
            try:
                with file_path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list) and len(data) > 0:
                        return True
            except Exception:
                pass
        return False


@app.post("/info/run")
async def run_info_collector(payload: InfoRunRequest = Body(...)) -> dict:
    """
    Trigger lấy thông tin reactions/comments:
      - mode="all": chạy toàn bộ post_ids dir (giống CLI hiện tại)
      - mode="selected": chỉ chạy các profile_id truyền trong payload.profiles
    
    TRƯỚC KHI lấy cookie, sẽ kiểm tra xem có dữ liệu bài viết không.
    Nếu có dữ liệu thì mới lấy cookie, sau đó mới lấy thông tin.
    """
    mode = (payload.mode or "all").lower()
    
    # Khi bấm Lấy thông tin, auto clear global_pause + emergency_stop
    try:
        control_state.set_global_pause(False)
        stop, _paused, reason = control_state.check_flags(None)
        if stop:
            print(f"🟡 [/info/run] GLOBAL_EMERGENCY_STOP đang bật ({reason}) -> auto reset để chạy")
            control_state.reset_emergency_stop(clear_stopped_profiles=False)
    except Exception:
        pass
    
    # 🆕 BƯỚC 1: KIỂM TRA DỮ LIỆU TRƯỚC
    try:
        has_data = _check_data_exists(mode, payload.profiles if mode == "selected" else None)
        if not has_data:
            print(f"⚠️ [/info/run] Không có dữ liệu bài viết để xử lý")
            raise HTTPException(status_code=400, detail="Không có dữ liệu bài viết để xử lý")
        print(f"✅ [/info/run] Đã kiểm tra: có dữ liệu bài viết, tiếp tục lấy cookie...")
    except HTTPException:
        raise
    except Exception as e:
        print(f"⚠️ [/info/run] Lỗi khi kiểm tra dữ liệu: {e}")
        raise HTTPException(status_code=400, detail="Không có dữ liệu bài viết để xử lý")
    
    # 🆕 BƯỚC 2: LẤY COOKIE CHO TẤT CẢ PROFILE (TUẦN TỰ) - CHỈ KHI CÓ DỮ LIỆU
    profiles_to_fetch_cookies = []
    try:
        if mode == "selected":
            profiles_to_fetch_cookies = payload.profiles or []
            if not profiles_to_fetch_cookies:
                raise HTTPException(status_code=400, detail="profiles is required when mode=selected")
        else:
            # Mode "all": lấy tất cả profile từ settings.json
            raw = _read_settings_raw()
            all_profiles = raw.get("PROFILE_IDS") or {}
            if isinstance(all_profiles, dict):
                profiles_to_fetch_cookies = list(all_profiles.keys())
            else:
                profiles_to_fetch_cookies = []
        
        # Lấy cookie tuần tự cho từng profile (tránh race condition)
        # Dùng run_in_threadpool vì _fetch_cookie_for_profile dùng Playwright Sync API
        if profiles_to_fetch_cookies:
            print(f"🍪 [/info/run] Bắt đầu lấy cookie cho {len(profiles_to_fetch_cookies)} profile(s)...")
            cookie_results = []
            for pid in profiles_to_fetch_cookies:
                # Chạy trong thread pool để tránh lỗi "Playwright Sync API inside asyncio loop"
                result = await run_in_threadpool(_fetch_cookie_for_profile, pid)
                cookie_results.append(result)
                if result["status"] == "ok":
                    print(f"✅ [{pid}] Đã lấy cookie thành công")
                else:
                    print(f"⚠️ [{pid}] Lỗi lấy cookie: {result.get('message', 'Unknown error')}")
            
            # Thống kê kết quả
            success_count = sum(1 for r in cookie_results if r["status"] == "ok")
            error_count = len(cookie_results) - success_count
            print(f"🍪 [/info/run] Hoàn thành lấy cookie: {success_count} thành công, {error_count} lỗi")
    except Exception as e:
        # Nếu lỗi khi lấy cookie, log nhưng vẫn tiếp tục lấy thông tin
        print(f"⚠️ [/info/run] Lỗi khi lấy cookie: {e}, nhưng vẫn tiếp tục lấy thông tin...")
    
    # 🆕 BƯỚC 3: SAU KHI LẤY ĐỦ COOKIE, MỚI BẮT ĐẦU LẤY THÔNG TIN
    try:
        if mode == "selected":
            profiles = payload.profiles or []
            if not profiles:
                raise HTTPException(status_code=400, detail="profiles is required when mode=selected")
            summary = await run_in_threadpool(get_info_for_profile_ids, profiles)
        else:
            summary = await run_in_threadpool(get_all_info_from_post_ids_dir)
        return {"status": "ok", "mode": mode, "summary": summary}
    except ValueError as e:
        # Nếu không có dữ liệu bài viết thì trả về message rõ ràng
        error_msg = str(e)
        if "không có dữ liệu bài viết" in error_msg.lower():
            raise HTTPException(status_code=400, detail="Không có dữ liệu bài viết để xử lý")
        raise HTTPException(status_code=400, detail=error_msg)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/info/scan-stats")
def get_scan_stats() -> dict:
    """
    Lấy số bài đã quét được cho từng profile_id từ các file JSON trong data/post_ids/
    """
    from pathlib import Path
    import json
    import os
    
    POST_IDS_DIR = get_data_dir() / "post_ids"
    
    stats = {}
    
    if not POST_IDS_DIR.exists():
        return {"stats": stats}
    
    json_files = list(POST_IDS_DIR.glob("*.json"))
    for file_path in json_files:
        profile_id = file_path.stem  # Lấy tên file không có extension
        try:
            with file_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    count = len(data)
                else:
                    count = 0
                stats[profile_id] = count
        except Exception:
            stats[profile_id] = 0
    
    return {"stats": stats}


@app.get("/info/progress")
def get_info_progress() -> dict:
    """
    Lấy tiến trình khi đang lấy thông tin (số bài đã xử lý / tổng số bài)
    """
    try:
        from worker.get_all_info import INFO_PROGRESS
    except ImportError:
        try:
            from backend.worker.get_all_info import INFO_PROGRESS
        except ImportError:
            # Fallback nếu không import được
            INFO_PROGRESS = {
                "is_running": False,
                "current": 0,
                "total": 0,
                "current_file": "",
            }
    
    return {
        "is_running": INFO_PROGRESS.get("is_running", False),
        "current": INFO_PROGRESS.get("current", 0),
        "total": INFO_PROGRESS.get("total", 0),
        "current_file": INFO_PROGRESS.get("current_file", ""),
    }


# ==============================================================================
# CONTROL API (STOP / PAUSE / RESUME) - theo spec Boss
# ==============================================================================

class ProfileControlPayload(BaseModel):
    profile_id: str


class ProfilesControlPayload(BaseModel):
    profile_ids: list[str]


class ResetStopPayload(BaseModel):
    clear_stopped_profiles: bool = False


@app.get("/control/state")
def control_get_state() -> dict:
    return control_state.get_state()


@app.post("/control/stop-all")
def control_stop_all() -> dict:
    """
    STOP ALL = dừng khẩn cấp.
    - set GLOBAL_EMERGENCY_STOP=true (ưu tiên cao nhất)
    - best-effort: đóng toàn bộ NST browser
    - KHÔNG hỏi confirm, KHÔNG delay
    """
    return _hard_stop_everything(reason="/control/stop-all")


@app.post("/control/pause-all")
def control_pause_all() -> dict:
    print("[UI] PAUSE ALL triggered")
    st = control_state.set_global_pause(True)
    return {"status": "ok", "state": st}


@app.post("/control/resume-all")
def control_resume_all() -> dict:
    print("[UI] RESUME ALL triggered")
    st = control_state.set_global_pause(False)
    return {"status": "ok", "state": st}


@app.post("/control/pause-profile")
def control_pause_profile(payload: ProfileControlPayload) -> dict:
    pid = _norm_profile_id(payload.profile_id)
    print(f"[UI] PAUSE profile_id={pid}")
    st = control_state.pause_profile(pid)
    return {"status": "ok", "state": st, "profile_id": pid}


@app.post("/control/resume-profile")
def control_resume_profile(payload: ProfileControlPayload) -> dict:
    pid = _norm_profile_id(payload.profile_id)
    print(f"[UI] RESUME profile_id={pid}")
    st = control_state.resume_profile(pid)
    return {"status": "ok", "state": st, "profile_id": pid}


@app.post("/control/stop-profiles")
def control_stop_profiles(payload: ProfilesControlPayload) -> dict:
    """
    STOP theo danh sách profile (dùng cho UI: tick profile -> bấm dừng).
    - Set stopped_profiles cho từng pid
    - Best-effort: đóng NST browser cho đúng các pid đó
    """
    global _bot_processes
    pids = [_norm_profile_id(x) for x in (payload.profile_ids or [])]
    pids = [p for p in pids if p]
    print(f"[UI] STOP profiles={pids}")

    st = control_state.stop_profiles(pids)

    # Terminate bot process đúng profile (độc lập), không ảnh hưởng profile khác
    try:
        with _bot_lock:
            _prune_bot_processes()
            for pid in pids:
                proc = _bot_processes.get(pid)
                try:
                    if proc and proc.is_alive():
                        proc.terminate()
                        proc.join(timeout=3)
                except Exception:
                    pass
                _bot_processes.pop(pid, None)
    except Exception:
        pass

    nst_ok: list[str] = []
    nst_fail: list[dict] = []
    for pid in pids:
        try:
            ok = bool(stop_profile(pid))
            if ok:
                nst_ok.append(pid)
            else:
                nst_fail.append({"profile_id": pid, "reason": "stop_profile_returned_false"})
        except Exception as e:
            nst_fail.append({"profile_id": pid, "reason": str(e)})

    return {"status": "ok", "state": st, "stopped_profiles": pids, "nst_ok": nst_ok, "nst_fail": nst_fail}


@app.post("/control/pause-profiles")
def control_pause_profiles(payload: ProfilesControlPayload) -> dict:
    pids = [_norm_profile_id(x) for x in (payload.profile_ids or [])]
    pids = [p for p in pids if p]
    print(f"[UI] PAUSE profiles={pids}")
    st = control_state.pause_profiles(pids)
    return {"status": "ok", "state": st, "paused_profiles": pids}


@app.post("/control/resume-profiles")
def control_resume_profiles(payload: ProfilesControlPayload) -> dict:
    pids = [_norm_profile_id(x) for x in (payload.profile_ids or [])]
    pids = [p for p in pids if p]
    print(f"[UI] RESUME profiles={pids}")
    st = control_state.resume_profiles(pids)
    return {"status": "ok", "state": st, "resumed_profiles": pids}


@app.post("/control/reset-stop")
def control_reset_stop(payload: Optional[ResetStopPayload] = Body(None)) -> dict:
    """
    Reset emergency stop để hệ thống chạy lại được.
    - clear_stopped_profiles=true: xoá luôn stopped_profiles (để profile không bị giữ STOPPED)
    """
    clear_stopped = bool(payload.clear_stopped_profiles) if payload else False
    print(f"[UI] RESET STOP (clear_stopped_profiles={clear_stopped})")
    st = control_state.reset_emergency_stop(clear_stopped_profiles=clear_stopped)
    return {"status": "ok", "state": st}

@app.delete("/settings/profiles/{profile_id}")
def delete_profile(profile_id: str) -> dict:
    pid = _norm_profile_id(profile_id)
    if not pid:
        raise HTTPException(status_code=400, detail="profile_id rỗng")

    with _settings_lock:
        raw = _read_settings_raw()
        profiles = raw.get("PROFILE_IDS") or {}
        if isinstance(profiles, list) or isinstance(profiles, str):
            profiles = {}
        if not isinstance(profiles, dict):
            raise HTTPException(status_code=400, detail="PROFILE_IDS phải là object")

        if pid in profiles:
            del profiles[pid]
        raw["PROFILE_IDS"] = profiles
        _write_settings_raw(raw)
        return {"status": "ok"}


def _fetch_cookie_for_profile(profile_id: str) -> dict:
    """
    Helper function: Lấy cookie cho 1 profile (mở NST, lấy cookie, lưu, đóng).
    Trả về dict với status và message.
    """
    pid = _norm_profile_id(profile_id)
    if not pid:
        return {"status": "error", "profile_id": profile_id, "message": "profile_id rỗng"}

    fb = None
    try:
        print(f"🍪 [{pid}] Đang mở NST để lấy cookie...")
        ws = connect_profile(pid)
        fb = FBController(ws)
        fb.profile_id = pid
        fb.connect()
        
        # đảm bảo context đã có session/cookie
        try:
            fb.goto("https://www.facebook.com/")
            fb.page.wait_for_timeout(1200)
        except Exception:
            pass

        cookie_string = fb.save_cookies()
        if not cookie_string:
            return {"status": "error", "profile_id": pid, "message": "Không lấy được cookie (có thể chưa đăng nhập)"}
        
        print(f"✅ [{pid}] Đã lấy và lưu cookie thành công")
        return {"status": "ok", "profile_id": pid, "message": "Đã lấy và lưu cookie thành công"}
    except Exception as exc:
        error_msg = str(exc)
        print(f"❌ [{pid}] Lỗi khi lấy cookie: {error_msg}")
        return {"status": "error", "profile_id": pid, "message": f"Lỗi: {error_msg}"}
    finally:
        # Đóng sạch tab/context playwright
        if fb:
            try:
                if fb.page:
                    try:
                        fb.page.close()
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                if fb.browser and getattr(fb.browser, "contexts", None):
                    for ctx in list(fb.browser.contexts):
                        try:
                            ctx.close()
                        except Exception:
                            pass
            except Exception:
                pass
            try:
                if fb.browser:
                    fb.browser.close()
            except Exception:
                pass
            try:
                if fb.play:
                    fb.play.stop()
            except Exception:
                pass

        # Best-effort: yêu cầu NST stop/close browser instance của profile
        try:
            stop_profile(pid)
        except Exception:
            pass


@app.post("/settings/profiles/{profile_id}/cookie/fetch")
def fetch_and_save_cookie(profile_id: str) -> dict:
    """
    Kết nối NST profile -> lấy cookie từ browser context -> lưu vào settings.json.
    """
    result = _fetch_cookie_for_profile(profile_id)
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return {"status": "ok", "profile_id": result["profile_id"], "cookie": "đã lưu vào settings.json"}


def _get_latest_results_file_logic(filename_param: Optional[str] = None) -> dict:
    """
    Logic chung để lấy file results (dùng cho cả GET và POST).
    """
    from pathlib import Path
    import re

    RESULTS_DIR = get_data_dir() / "results"

    # Nếu có filename, load file đó
    if filename_param:
        file_path = RESULTS_DIR / filename_param
        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"File {filename_param} không tồn tại")

        # Parse timestamp từ filename
        pattern = re.compile(r'all_results_(\d{8})_(\d{6})\.json$')
        match = pattern.match(filename_param)
        if not match:
            raise HTTPException(status_code=400, detail=f"Tên file {filename_param} không hợp lệ")

        date_str, time_str = match.groups()
        try:
            from datetime import datetime
            dt = datetime.strptime(f"{date_str} {time_str}", "%Y%m%d %H%M%S")
            timestamp = dt.timestamp()
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Không thể parse timestamp từ {filename_param}")

        try:
            with file_path.open("r", encoding="utf-8") as f:
                content = f.read().strip()

            # Thử parse JSON
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                # Thử tìm object JSON chính
                last_brace = content.rfind('}')
                if last_brace > 0:
                    try:
                        data = json.loads(content[:last_brace + 1])
                    except json.JSONDecodeError as exc:
                        raise HTTPException(status_code=400, detail=f"File {filename_param} không phải JSON hợp lệ: {exc}") from exc
                else:
                    raise HTTPException(status_code=400, detail=f"File {filename_param} không phải JSON hợp lệ")
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Không đọc được file {filename_param}: {exc}")

        return {
            "filename": filename_param,
            "timestamp": int(timestamp),
            "data": data
        }

    # Nếu không có filename, tìm file gần nhất như cũ
    if not RESULTS_DIR.exists():
        raise HTTPException(status_code=404, detail=f"Thư mục results không tồn tại: {RESULTS_DIR}")

    # Pattern để parse timestamp từ tên file: all_results_YYYYMMDD_HHMMSS.json
    pattern = re.compile(r'all_results_(\d{8})_(\d{6})\.json$')

    # Tìm tất cả file JSON và parse timestamp
    json_files = []
    all_files = list(RESULTS_DIR.glob("*.json"))

    for file_path in all_files:
        match = pattern.match(file_path.name)
        if match:
            date_str, time_str = match.groups()
            # Parse thành datetime để so sánh chính xác
            try:
                from datetime import datetime
                # Parse YYYYMMDD HHMMSS
                dt = datetime.strptime(f"{date_str} {time_str}", "%Y%m%d %H%M%S")
                timestamp = dt.timestamp()  # Unix timestamp
                json_files.append((file_path, timestamp, file_path.name))
            except ValueError:
                continue

    if not json_files:
        file_names = [f.name for f in all_files]
        raise HTTPException(status_code=404, detail=f"Không tìm thấy file JSON nào match pattern. Files found: {file_names}")

    # Sắp xếp theo timestamp giảm dần (mới nhất trước)
    json_files.sort(key=lambda x: x[1], reverse=True)

    # Lấy file gần nhất
    latest_file, timestamp, filename = json_files[0]

    try:
        with latest_file.open("r", encoding="utf-8") as f:
            content = f.read().strip()

        # Thử parse JSON bình thường trước
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            # Nếu thất bại, thử tìm object JSON chính (bỏ dữ liệu thừa ở cuối)
            # Tìm vị trí cuối cùng của closing brace
            last_brace = content.rfind('}')
            if last_brace > 0:
                # Thử parse từ đầu đến closing brace
                try:
                    data = json.loads(content[:last_brace + 1])
                except json.JSONDecodeError as exc:
                    raise HTTPException(status_code=400, detail=f"File {filename} không phải JSON hợp lệ: {exc}") from exc
            else:
                raise HTTPException(status_code=400, detail=f"File {filename} không phải JSON hợp lệ")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Không đọc được file {filename}: {exc}") from exc

    return {
        "filename": filename,
        "timestamp": int(timestamp),
        "data": data
    }


@app.get("/data/latest-results")
def get_latest_results_file_get(filename: Optional[str] = Query(None)) -> dict:
    """
    GET endpoint: Tìm và trả về nội dung file JSON theo filename hoặc gần nhất.
    """
    return _get_latest_results_file_logic(filename)


@app.get("/data/post-ids")
def get_post_ids_list() -> dict:
    """
    Lấy danh sách tất cả file post_ids và nội dung của chúng.
    """
    from pathlib import Path
    import json

    POST_IDS_DIR = get_data_dir() / "post_ids"

    if not POST_IDS_DIR.exists():
        return {"files": [], "total": 0}

    files_data = []
    json_files = list(POST_IDS_DIR.glob("*.json"))

    for file_path in json_files:
        try:
            with file_path.open("r", encoding="utf-8") as f:
                content = f.read().strip()

            # Parse JSON
            data = json.loads(content)

            # Xử lý cả trường hợp array hoặc object
            if isinstance(data, list):
                posts = data
            elif isinstance(data, dict):
                posts = [data]
            else:
                continue

            # Lấy thông tin từ posts
            for post in posts:
                if isinstance(post, dict) and "id" in post:
                    files_data.append({
                        "filename": file_path.name,
                        "post_id": post.get("id"),
                        "flag": post.get("flag", ""),
                        "text": post.get("text", ""),
                        "owning_profile": post.get("owning_profile", {})
                    })

        except Exception as e:
            # Nếu không đọc được file, bỏ qua
            continue

    return {
        "files": files_data,
        "total": len(files_data)
    }


@app.post("/cleanup/old-files")
def cleanup_old_files(max_days: int = 3) -> dict:
    """
    Dọn dẹp các file all_results cũ quá max_days ngày.
    """
    from pathlib import Path
    import re
    from datetime import datetime, timedelta

    RESULTS_DIR = get_data_dir() / "results"

    if not RESULTS_DIR.exists():
        return {"deleted_count": 0, "message": "Thư mục results không tồn tại"}

    # Pattern để parse timestamp từ tên file: all_results_YYYYMMDD_HHMMSS.json
    pattern = re.compile(r'all_results_(\d{8})_(\d{6})\.json$')

    current_time = datetime.now()
    max_age = timedelta(days=max_days)
    deleted_count = 0
    deleted_files = []

    # Duyệt qua tất cả file trong thư mục
    for file_path in RESULTS_DIR.glob("*.json"):
        if not file_path.is_file():
            continue

        match = pattern.match(file_path.name)
        if not match:
            continue

        date_str, time_str = match.groups()
        try:
            # Parse thành datetime
            file_datetime = datetime.strptime(f"{date_str} {time_str}", "%Y%m%d %H%M%S")

            # Kiểm tra tuổi file
            if current_time - file_datetime > max_age:
                try:
                    file_path.unlink()  # Xóa file
                    deleted_count += 1
                    deleted_files.append(file_path.name)
                    print(f"Đã xóa file cũ: {file_path.name}")
                except Exception as e:
                    print(f"Lỗi khi xóa file {file_path.name}: {e}")

        except ValueError:
            # Nếu không parse được timestamp, bỏ qua
            continue

    return {
        "deleted_count": deleted_count,
        "deleted_files": deleted_files,
        "message": f"Đã xóa {deleted_count} file cũ quá {max_days} ngày"
    }


@app.post("/data/latest-results")
def get_latest_results_file_post(request: Optional[dict] = Body(None)) -> dict:
    """
    POST endpoint: Tìm và trả về nội dung file JSON theo filename hoặc gần nhất (tương thích ngược).
    """
    filename_param = None
    if request and isinstance(request, dict):
        filename_param = request.get("filename")
    return _get_latest_results_file_logic(filename_param)


@app.post("/data/by-date-range")
def get_results_by_date_range(request: dict) -> dict:
    """
    Tìm và trả về file JSON có timestamp nằm trong khoảng thời gian được chỉ định
    """
    from pathlib import Path
    import re

    RESULTS_DIR = get_data_dir() / "results"

    from_timestamp = request.get("from_timestamp")
    to_timestamp = request.get("to_timestamp")

    if not from_timestamp or not to_timestamp:
        raise HTTPException(status_code=400, detail="Thiếu from_timestamp hoặc to_timestamp")

    try:
        from_timestamp = int(from_timestamp)
        to_timestamp = int(to_timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Timestamp phải là số nguyên")

    if not RESULTS_DIR.exists():
        raise HTTPException(status_code=404, detail=f"Thư mục results không tồn tại: {RESULTS_DIR}")

    # Pattern để parse timestamp từ tên file
    pattern = re.compile(r'all_results_(\d{8})_(\d{6})\.json$')

    # Tìm tất cả file JSON và parse timestamp
    matching_files = []
    all_files = list(RESULTS_DIR.glob("*.json"))

    for file_path in all_files:
        match = pattern.match(file_path.name)
        if match:
            date_str, time_str = match.groups()
            try:
                from datetime import datetime
                dt = datetime.strptime(f"{date_str} {time_str}", "%Y%m%d %H%M%S")
                timestamp = dt.timestamp()

                # Kiểm tra xem timestamp có nằm trong khoảng không
                if from_timestamp <= timestamp <= to_timestamp:
                    matching_files.append((file_path, timestamp, file_path.name))
            except ValueError:
                continue

    if not matching_files:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy file JSON nào trong khoảng thời gian từ {from_timestamp} đến {to_timestamp}")

    # Sắp xếp theo timestamp giảm dần (mới nhất trước)
    matching_files.sort(key=lambda x: x[1], reverse=True)

    # Lấy file gần nhất trong khoảng
    latest_file, timestamp, filename = matching_files[0]

    try:
        with latest_file.open("r", encoding="utf-8") as f:
            content = f.read().strip()

        # Thử parse JSON
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            # Thử tìm object JSON chính
            last_brace = content.rfind('}')
            if last_brace > 0:
                try:
                    data = json.loads(content[:last_brace + 1])
                except json.JSONDecodeError as exc:
                    raise HTTPException(status_code=400, detail=f"File {filename} không phải JSON hợp lệ: {exc}") from exc
            else:
                raise HTTPException(status_code=400, detail=f"File {filename} không phải JSON hợp lệ")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Không đọc được file {filename}: {exc}")

    return {
        "filename": filename,
        "timestamp": int(timestamp),
        "data": data
    }

@app.post("/data/files-in-range")
def get_files_in_date_range(request: dict) -> dict:
    """
    Trả về danh sách các file JSON có timestamp trong khoảng thời gian được chỉ định
    """
    from pathlib import Path
    import re

    RESULTS_DIR = get_data_dir() / "results"

    from_timestamp = request.get("from_timestamp")
    to_timestamp = request.get("to_timestamp")

    if not from_timestamp or not to_timestamp:
        raise HTTPException(status_code=400, detail="Thiếu from_timestamp hoặc to_timestamp")

    try:
        from_timestamp = int(from_timestamp)
        to_timestamp = int(to_timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Timestamp phải là số nguyên")

    if not RESULTS_DIR.exists():
        raise HTTPException(status_code=404, detail=f"Thư mục results không tồn tại: {RESULTS_DIR}")

    # Pattern để parse timestamp từ tên file
    pattern = re.compile(r'all_results_(\d{8})_(\d{6})\.json$')

    # Tìm tất cả file JSON và parse timestamp
    matching_files = []
    all_files = list(RESULTS_DIR.glob("*.json"))

    for file_path in all_files:
        match = pattern.match(file_path.name)
        if match:
            date_str, time_str = match.groups()
            try:
                from datetime import datetime
                dt = datetime.strptime(f"{date_str} {time_str}", "%Y%m%d %H%M%S")
                timestamp = dt.timestamp()

                # Kiểm tra xem timestamp có nằm trong khoảng không
                if from_timestamp <= timestamp <= to_timestamp:
                    matching_files.append({
                        "filename": file_path.name,
                        "timestamp": int(timestamp),
                        "filepath": str(file_path),
                        "date_formatted": dt.strftime("%d/%m/%Y %H:%M:%S")
                    })
            except ValueError:
                continue

    # Sắp xếp theo timestamp giảm dần (mới nhất trước)
    matching_files.sort(key=lambda x: x["timestamp"], reverse=True)

    return {
        "files": matching_files,
        "total_files": len(matching_files),
        "range": {
            "from_timestamp": from_timestamp,
            "to_timestamp": to_timestamp
        }
    }

class ScanGroupsRequest(BaseModel):
    profile_ids: list[str]
    post_count: int
    start_date: str  # Format: YYYY-MM-DD
    end_date: str    # Format: YYYY-MM-DD

# Queue để xử lý quét group lần lượt
_group_scan_queue = []
_group_scan_lock = threading.Lock()
_group_scan_processing = False
_group_scan_stop_requested = False  # Flag để dừng group scan

def _process_group_scan_queue():
    """Xử lý queue quét group lần lượt"""
    global _group_scan_processing, _group_scan_stop_requested
    
    with _group_scan_lock:
        if _group_scan_processing or len(_group_scan_queue) == 0 or _group_scan_stop_requested:
            return
        _group_scan_processing = True
        _group_scan_stop_requested = False  # Reset flag khi bắt đầu
    
    try:
        while True:
            # Check stop flag trước khi xử lý task tiếp theo
            with _group_scan_lock:
                if _group_scan_stop_requested:
                    print("🛑 Đã nhận yêu cầu dừng group scan")
                    break
                if len(_group_scan_queue) == 0:
                    break
                task = _group_scan_queue.pop(0)
            
            # Xử lý task
            profile_id = task["profile_id"]
            post_count = task["post_count"]
            start_date = task["start_date"]
            end_date = task["end_date"]
            
            print(f"\n{'='*60}")
            print(f"🚀 Bắt đầu quét group cho profile: {profile_id}")
            print(f"   Số bài viết: {post_count}")
            print(f"   Từ ngày: {start_date} đến {end_date}")
            print(f"{'='*60}\n")
            
            try:
                # Đọc groups.json
                groups_file = get_config_dir() / "groups.json"
                if not groups_file.exists():
                    print(f"❌ File groups.json không tồn tại: {groups_file}")
                    continue
                
                with groups_file.open("r", encoding="utf-8") as f:
                    groups_data = json.load(f)
                
                # Lấy danh sách groups cho profile này
                profile_groups = groups_data.get(profile_id, [])
                if not profile_groups:
                    print(f"⚠️ Không có group nào cho profile {profile_id}")
                    continue
                
                print(f"📋 Tìm thấy {len(profile_groups)} group(s) cho profile {profile_id}")
                
                # Import function
                from worker.get_post_from_page import get_posts_from_page
                
                # Quét từng group
                total_posts_scanned = 0
                for group_info in profile_groups:
                    # Check stop flag trước mỗi group
                    with _group_scan_lock:
                        if _group_scan_stop_requested:
                            print("🛑 Đã nhận yêu cầu dừng, dừng quét group")
                            break
                    
                    page_id = group_info.get("page_id")
                    url_page = group_info.get("url_page", "")
                    
                    if not page_id:
                        print(f"⚠️ Bỏ qua group không có page_id: {group_info}")
                        continue
                    
                    print(f"\n📌 Xử lý group: {page_id}")
                    if url_page:
                        print(f"   URL: {url_page}")
                    
                    # Check stop flag trước khi gọi get_posts_from_page
                    with _group_scan_lock:
                        if _group_scan_stop_requested:
                            print("🛑 Đã nhận yêu cầu dừng, bỏ qua group còn lại")
                            break
                    
                    try:
                        # Gọi get_posts_from_page với limit = post_count
                        # Hàm này sẽ tự động:
                        # 1. Lấy posts từ Graph API
                        # 2. Gọi get_id_from_url cho mỗi post để lấy chi tiết
                        # 3. Lưu vào data/post_ids/{profile_id}.json
                        posts = get_posts_from_page(
                            page_id=page_id,
                            profile_id=profile_id,
                            start_date=start_date,
                            end_date=end_date,
                            limit=post_count
                        )
                        
                        # Check stop flag sau khi quét xong group
                        with _group_scan_lock:
                            if _group_scan_stop_requested:
                                print("🛑 Đã nhận yêu cầu dừng sau khi quét xong group")
                                break
                        
                        if posts:
                            total_posts_scanned += len(posts)
                            print(f"   ✅ Đã quét {len(posts)} posts từ group {page_id}")
                        else:
                            print(f"   ⚠️ Không lấy được posts nào từ group {page_id}")
                        
                    except Exception as e:
                        print(f"   ❌ Lỗi khi quét group {page_id}: {e}")
                        import traceback
                        traceback.print_exc()
                        continue
                
                # Check stop flag sau khi quét xong profile
                with _group_scan_lock:
                    if _group_scan_stop_requested:
                        print("🛑 Đã nhận yêu cầu dừng sau khi quét xong profile")
                        break
                
                print(f"\n✅ Hoàn thành quét {len(profile_groups)} group(s), tổng cộng {total_posts_scanned} posts")
                
                print(f"\n✅ Hoàn thành quét group cho profile: {profile_id}\n")
                
            except Exception as e:
                print(f"❌ Lỗi khi xử lý profile {profile_id}: {e}")
                import traceback
                traceback.print_exc()
    
    finally:
        with _group_scan_lock:
            _group_scan_processing = False
            # Chỉ reset stop flag nếu không phải do stop request
            # Nếu do stop request thì giữ nguyên flag để đảm bảo không restart
        
        # KHÔNG tự động tiếp tục xử lý queue khi hoàn thành
        # Chỉ tiếp tục nếu được gọi lại từ API
        with _group_scan_lock:
            if _group_scan_stop_requested:
                print("🛑 Group scan đã dừng theo yêu cầu.")
            else:
                print("✅ Group scan đã hoàn thành và tự động dừng. Gọi lại API để tiếp tục.")

@app.post("/scan-groups")
def scan_groups(request: ScanGroupsRequest) -> dict:
    """
    Quét bài viết từ các group đã cấu hình trong groups.json
    
    - Đọc groups.json để lấy danh sách groups cho mỗi profile
    - Với mỗi group, quét số lượng bài viết trong khoảng thời gian
    - Lưu kết quả vào data/post_ids/{profile_id}.json
    - Xử lý lần lượt nếu có nhiều profile
    """
    profile_ids = request.profile_ids
    post_count = request.post_count
    start_date = request.start_date
    end_date = request.end_date
    
    if not profile_ids:
        raise HTTPException(status_code=400, detail="Chưa chọn profile nào")
    
    if post_count <= 0:
        raise HTTPException(status_code=400, detail="Số bài viết phải lớn hơn 0")
    
    if not start_date or not end_date:
        raise HTTPException(status_code=400, detail="Chưa nhập đủ ngày bắt đầu và ngày kết thúc")
    
    # Validate date format (YYYY-MM-DD)
    try:
        from datetime import datetime
        datetime.strptime(start_date, "%Y-%m-%d")
        datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Định dạng ngày không hợp lệ. Phải là YYYY-MM-DD")
    
    # Thêm các task vào queue
    with _group_scan_lock:
        # Reset stop flag khi bắt đầu quét mới
        _group_scan_stop_requested = False
        for profile_id in profile_ids:
            task = {
                "profile_id": profile_id,
                "post_count": post_count,
                "start_date": start_date,
                "end_date": end_date
            }
            _group_scan_queue.append(task)
    
    # Bắt đầu xử lý queue (nếu chưa đang xử lý)
    threading.Thread(target=_process_group_scan_queue, daemon=True).start()
    
    return {
        "status": "ok",
        "message": f"Đã thêm {len(profile_ids)} profile vào hàng chờ quét group",
        "queue_length": len(_group_scan_queue),
        "profiles": profile_ids
    }

@app.get("/scan-groups/status")
def get_scan_groups_status() -> dict:
    """Lấy trạng thái queue quét group"""
    with _group_scan_lock:
        return {
            "processing": _group_scan_processing,
            "queue_length": len(_group_scan_queue),
            "queue": _group_scan_queue.copy(),
            "stop_requested": _group_scan_stop_requested
        }


@app.post("/scan-groups/stop")
def stop_scan_groups() -> dict:
    """
    Dừng quét group ngay lập tức:
    - Set flag stop để dừng xử lý queue
    - Clear queue nếu cần
    """
    global _group_scan_stop_requested, _group_scan_queue
    
    with _group_scan_lock:
        _group_scan_stop_requested = True
        queue_length = len(_group_scan_queue)
        # Clear queue để không xử lý các task còn lại
        _group_scan_queue.clear()
    
    print(f"🛑 Đã yêu cầu dừng group scan. Queue đã được clear ({queue_length} task(s))")
    
    return {
        "status": "ok",
        "message": "Đã yêu cầu dừng group scan",
        "queue_cleared": queue_length
    }


@app.post("/run-multi-thread")
def run_multi_thread(payload: Optional[RunMultiThreadRequest] = Body(None)) -> dict:
    """
    Chạy song song quét feed+search và quét group bằng multi_thread runner
    """
    try:
        from worker.multi_thread import start_multi_thread
        
        run_minutes = payload.run_minutes if payload else None
        rest_minutes = payload.rest_minutes if payload else None
        profile_ids = payload.profile_ids if payload else None
        text = payload.text if payload else None
        mode = payload.mode if payload else None
        post_count = payload.post_count if payload else None
        start_date = payload.start_date if payload else None
        end_date = payload.end_date if payload else None
        
        # Validate profile_ids
        if not profile_ids:
            raise HTTPException(status_code=400, detail="profile_ids rỗng")
        pids = [_norm_profile_id(x) for x in (profile_ids or [])]
        pids = [p for p in pids if p]
        if not pids:
            raise HTTPException(status_code=400, detail="profile_ids không hợp lệ")
        
        # Validate mode và text
        m = str(mode or "feed+search").strip().lower()
        if m not in ("feed", "search", "feed+search", "feed_search"):
            m = "feed+search"
        if m in ("search", "feed+search", "feed_search") and not str(text or "").strip():
            raise HTTPException(status_code=400, detail="Search và Feed+Search cần text")
        
        # Validate group scan params (nếu có)
        if start_date and end_date:
            try:
                from datetime import datetime
                datetime.strptime(start_date, "%Y-%m-%d")
                datetime.strptime(end_date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(status_code=400, detail="Định dạng ngày không hợp lệ. Phải là YYYY-MM-DD")
        
        # Reset control state
        try:
            control_state.set_global_pause(False)
            stop, _paused, reason = control_state.check_flags(None)
            if stop:
                print(f"🟡 [/run-multi-thread] GLOBAL_EMERGENCY_STOP đang bật ({reason}) -> auto reset để chạy")
                control_state.reset_emergency_stop(clear_stopped_profiles=False)
            control_state.resume_profiles(pids)
        except Exception as _e:
            pass
        
        # Gọi multi-thread runner
        result = start_multi_thread(
            profile_ids=pids,
            run_minutes=float(run_minutes or 30.0),
            rest_minutes=float(rest_minutes or 120.0),
            text=str(text or ""),
            mode=m,
            post_count=int(post_count or 10) if post_count else 10,
            start_date=str(start_date or ""),
            end_date=str(end_date or "")
        )
        
        return result
        
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"Không thể import multi_thread module: {e}")
    except Exception as e:
        import traceback
        print(f"❌ Lỗi trong /run-multi-thread: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Lỗi khi chạy multi-thread: {str(e)}")


@app.get("/run-multi-thread/status")
def get_multi_thread_status() -> dict:
    """Lấy trạng thái multi-thread runner"""
    try:
        from worker.multi_thread import get_multi_thread_status
        return get_multi_thread_status()
    except ImportError:
        return {"status": "error", "message": "Multi-thread module không khả dụng"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/run-multi-thread/stop")
def stop_multi_thread() -> dict:
    """Dừng multi-thread runner"""
    try:
        from worker.multi_thread import stop_multi_thread
        return stop_multi_thread()
    except ImportError:
        raise HTTPException(status_code=500, detail="Multi-thread module không khả dụng")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi dừng multi-thread: {str(e)}")

