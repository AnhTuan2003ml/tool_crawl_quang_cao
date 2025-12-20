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

from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.settings import SETTINGS_PATH
from core.nst import connect_profile, stop_profile, stop_all_browsers
from core.browser import FBController
from core import control as control_state
from core.scraper import SimpleBot
from core.settings import get_settings

app = FastAPI(title="NST Tool API", version="1.0.0")

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

    # 6) Reset runtime state về mặc định (để lần sau bấm chạy là "mới hoàn toàn")
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
    run_minutes: int,
    rest_minutes: int,
    text: str,
    mode: str,
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
    if m not in ("feed", "search"):
        m = "feed"
    t = str(text or "").strip()
    if m == "search" and t:
        q = quote_plus(t)
        target_url = f"https://www.facebook.com/search/posts/?q={q}"

    run_m = int(run_minutes or 0)
    rest_m = int(rest_minutes or 0)
    if run_m <= 0:
        run_m = int(getattr(cfg, "run_minutes", 30) or 30)
    if rest_m <= 0:
        rest_m = int(getattr(cfg, "rest_minutes", 120) or 120)

    duration_seconds = max(1, run_m * 60)
    rest_seconds = max(1, rest_m * 60)

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
            bot = SimpleBot(fb)
            bot.run(target_url, duration=duration_seconds)
        except RuntimeError as e:
            # STOP/BROWSER_CLOSED => thoát phiên
            if "EMERGENCY_STOP" in str(e) or "BROWSER_CLOSED" in str(e):
                print(f"🛑 [{pid}] Dừng bot ({e})")
            else:
                raise
        except Exception as e:
            print(f"❌ Lỗi ở profile {pid}: {e}")
            try:
                control_state.set_profile_state(pid, "ERROR")
            except Exception:
                pass
        finally:
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

        # REST (độc lập theo profile) - pause freeze
        slept = 0
        while slept < rest_seconds:
            stop, paused, reason = control_state.check_flags(pid)
            if stop:
                print(f"🛑 [{pid}] STOP trong REST ({reason}) -> thoát")
                try:
                    control_state.set_profile_state(pid, "STOPPED")
                except Exception:
                    pass
                return
            if paused:
                control_state.wait_if_paused(pid, sleep_seconds=0.5)
                continue
            time.sleep(1)
            slept += 1


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
    run_minutes: int,
    rest_minutes: int,
    all_profile_ids: Optional[list[str]] = None,
) -> None:
    """
    Worker chạy nuôi acc (feed/search & like) cho 1 profile theo vòng lặp:
    chạy run_minutes -> tắt -> nghỉ rest_minutes -> lặp lại.
    Nếu rest_minutes <= 0 thì chỉ chạy 1 lần.
    """
    try:
        from core.search_worker import feed_and_like, search_and_like
        m = str(mode or "feed").strip().lower()
        run_m = int(run_minutes or 0)
        rest_m = int(rest_minutes or 0)
        if run_m <= 0:
            run_m = 30

        while True:
            # STOP/PAUSE checkpoint
            stop, paused, reason = control_state.check_flags(profile_id)
            if stop:
                print(f"🛑 [FEED] {profile_id} EMERGENCY_STOP ({reason}) -> dừng worker")
                break
            if paused:
                print(f"⏸️ [FEED] {profile_id} PAUSED ({reason}) -> sleep")
                control_state.wait_if_paused(profile_id, sleep_seconds=0.5)

            if m == "search":
                search_and_like(profile_id, text or "", duration_minutes=run_m, all_profile_ids=all_profile_ids)
            else:
                feed_and_like(profile_id, text or "", duration_minutes=run_m, all_profile_ids=all_profile_ids)

            if rest_m <= 0:
                break

            # nghỉ rồi chạy lại (process có thể bị terminate bởi stop-all)
            import time as _t
            # sleep theo chunk để vẫn dừng được ngay
            slept = 0
            while slept < rest_m * 60:
                stop, paused, reason = control_state.check_flags(profile_id)
                if stop:
                    print(f"🛑 [FEED] {profile_id} EMERGENCY_STOP trong sleep ({reason}) -> dừng")
                    return
                if paused:
                    _t.sleep(1)
                    continue
                _t.sleep(1)
                slept += 1
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
    run_minutes: Optional[int] = None
    rest_minutes: Optional[int] = None
    profile_ids: Optional[list[str]] = None
    # text filter cho scan bài viết (dùng trong core/browser.py)
    text: Optional[str] = None
    # mode cho scan bài viết: "feed" | "search"
    mode: Optional[str] = None


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

    # Nếu user bấm CHẠY mà trước đó đã STOP, auto reset STOP để job chạy được.
    # Chỉ resume/clear STOPPED cho đúng các profile được yêu cầu chạy.
    try:
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

    # ✅ Chặn chạy nếu bất kỳ profile nào thiếu cookie/access_token
    _validate_profiles_requirements(pids, require_cookie=True, require_access_token=True)

    m = str(mode or "feed").strip().lower()
    if m not in ("feed", "search"):
        m = "feed"
    # Search bắt buộc có text để search
    if m == "search" and not str(text or "").strip():
        raise HTTPException(status_code=400, detail="Search cần text")

    started: list[str] = []
    skipped: list[dict] = []
    run_m = int(run_minutes or 0) if payload else 0
    rest_m = int(rest_minutes or 0) if payload else 0
    txt = str(text or "")
    md = str(m or "feed")

    with _bot_lock:
        _prune_bot_processes()
        for pid in pids:
            existing = _bot_processes.get(pid)
            if existing and existing.is_alive():
                skipped.append({"profile_id": pid, "reason": "already_running"})
                continue
            proc = Process(
                target=_run_bot_profile_loop,
                args=(pid, run_m, rest_m, txt, md),
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
    require_cookie: bool = True,
    require_access_token: bool = True,
) -> None:
    """
    Nếu có profile thiếu cookie/access_token (theo require_*), sẽ raise 400 và KHÔNG cho start job.
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
    run_minutes: int = 30
    rest_minutes: int = 0


class FeedStopRequest(BaseModel):
    profile_ids: Optional[list[str]] = None


@app.put("/settings/api-key")
def update_api_key(payload: ApiKeyPayload) -> dict:
    with _settings_lock:
        raw = _read_settings_raw()
        raw["API_KEY"] = str(payload.api_key or "").strip()
        _write_settings_raw(raw)
        return {"status": "ok"}


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

        # Tạo profile mới: luôn có cookie/access_token/groups (groups trống)
        cur = profiles.get(pid)
        if cur is None or not isinstance(cur, dict):
            cur = {}
            profiles[pid] = cur
        cur.setdefault("cookie", "")
        cur.setdefault("access_token", "")
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


@app.put("/settings/profiles/{profile_id}/groups")
def replace_profile_groups(profile_id: str, payload: ProfileGroupsReplacePayload) -> dict:
    """
    Ghi đè toàn bộ groups của 1 profile (đúng yêu cầu: trong textarea có gì thì đè lên cái cũ).
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
    # Nếu user bấm join mà trước đó đã STOP, auto reset STOP để job chạy được.
    try:
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

    # ✅ Join group chỉ cần cookie (không bắt access_token)
    _validate_profiles_requirements(pids, require_cookie=True, require_access_token=False)

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

    # Nếu user bấm NUÔI ACC mà trước đó đã STOP, auto reset STOP để job chạy được.
    try:
        stop, _paused, reason = control_state.check_flags(None)
        if stop:
            print(f"🟡 [/feed/start] GLOBAL_EMERGENCY_STOP đang bật ({reason}) -> auto reset để chạy")
            control_state.reset_emergency_stop(clear_stopped_profiles=False)
        control_state.resume_profiles(pids)
    except Exception:
        pass

    # ✅ Chặn chạy nếu bất kỳ profile nào thiếu cookie/access_token
    _validate_profiles_requirements(pids, require_cookie=True, require_access_token=True)

    run_minutes = int(payload.run_minutes or 0)
    if run_minutes <= 0:
        raise HTTPException(status_code=400, detail="run_minutes phải > 0")
    rest_minutes = int(payload.rest_minutes or 0)
    if rest_minutes < 0:
        raise HTTPException(status_code=400, detail="rest_minutes phải >= 0")

    started: list[str] = []
    skipped: list[dict] = []
    mode = str(payload.mode or "feed").strip().lower()
    text = str(payload.text or "").strip()
    # backward-compat
    if not text and getattr(payload, "filter_text", None):
        text = str(payload.filter_text or "").strip()
    # Cho phép text rỗng nếu mode=feed (sẽ chỉ filter theo keyword mặc định)
    if not text and mode == "search":
        raise HTTPException(status_code=400, detail="text rỗng (search cần text)")

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


@app.post("/jobs/stop-all")
def stop_all_jobs() -> dict:
    """
    Dừng tất cả tác vụ nền (dùng chung cho auto join group + sau này nuôi acc).
    """
    # Legacy endpoint: vẫn map về hard stop (fresh start) cho đúng spec mới
    return _hard_stop_everything(reason="/jobs/stop-all")


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


@app.post("/settings/profiles/{profile_id}/cookie/fetch")
def fetch_and_save_cookie(profile_id: str) -> dict:
    """
    Kết nối NST profile -> lấy cookie từ browser context -> lưu vào settings.json.
    """
    pid = _norm_profile_id(profile_id)
    if not pid:
        raise HTTPException(status_code=400, detail="profile_id rỗng")

    try:
        ws = connect_profile(pid)
    except Exception as exc:
        # NST chưa chạy / API key sai / profile_id sai
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    fb = FBController(ws)
    fb.profile_id = pid
    fb.connect()
    try:
        # đảm bảo context đã có session/cookie
        try:
            fb.goto("https://www.facebook.com/")
            fb.page.wait_for_timeout(1200)
        except Exception:
            pass

        cookie_string = fb.save_cookies()
        if not cookie_string:
            raise HTTPException(status_code=400, detail="Không lấy được cookie (có thể chưa đăng nhập)")
        return {"status": "ok", "profile_id": pid, "cookie": cookie_string}
    finally:
        # Đóng sạch tab/context playwright
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
