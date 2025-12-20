from multiprocessing import Process
from typing import Optional, Any, Dict
from pathlib import Path
import json
import os
import tempfile
import threading
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.runner import AppRunner
from core.settings import SETTINGS_PATH
from core.nst import connect_profile, stop_profile, stop_all_browsers
from core.browser import FBController
from core import control as control_state

app = FastAPI(title="NST Tool API", version="1.0.0")

# Cho phép frontend (file tĩnh) gọi API qua localhost
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Biến toàn cục giữ tiến trình đang chạy AppRunner
runner_process: Optional[Process] = None
_settings_lock = threading.Lock()
_join_groups_lock = threading.Lock()
_join_groups_processes: Dict[str, Process] = {}
_feed_lock = threading.Lock()
_feed_processes: Dict[str, Process] = {}


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


def _start_runner(
    run_minutes: Optional[int] = None,
    rest_minutes: Optional[int] = None,
    profile_ids: Optional[list[str]] = None,
    text: Optional[str] = None,
    mode: Optional[str] = None,
) -> None:
    """Hàm wrapper để chạy vòng lặp AppRunner trong tiến trình riêng."""
    AppRunner(run_minutes=run_minutes, rest_minutes=rest_minutes, profile_ids=profile_ids, text=text, mode=mode).run()


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}


@app.post("/run")
def run_bot(payload: Optional[RunRequest] = Body(None)) -> dict:
    """
    Khởi động AppRunner nếu chưa chạy.
    Chạy trong process riêng để không khóa FastAPI.
    """
    global runner_process

    if runner_process and runner_process.is_alive():
        return {"status": "running", "pid": runner_process.pid}

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

    # ✅ Chặn chạy nếu bất kỳ profile nào thiếu cookie/access_token
    _validate_profiles_requirements(pids, require_cookie=True, require_access_token=True)

    m = str(mode or "feed").strip().lower()
    if m not in ("feed", "search"):
        m = "feed"
    # Search bắt buộc có text để search
    if m == "search" and not str(text or "").strip():
        raise HTTPException(status_code=400, detail="Search cần text")

    # Không dùng daemon vì AppRunner tự sinh thêm Process con
    runner_process = Process(
        target=_start_runner,
        args=(run_minutes, rest_minutes, pids, text, m),
        daemon=False,
    )
    runner_process.start()

    if not runner_process.is_alive():
        raise HTTPException(status_code=500, detail="Không khởi động được bot")

    return {"status": "started", "pid": runner_process.pid}


@app.post("/stop")
def stop_bot() -> dict:
    """
    STOP (khẩn cấp):
    - Set GLOBAL_EMERGENCY_STOP = true
    - Best-effort: đóng toàn bộ NST browser (để các loop Playwright tự thoát)
    - Không terminate/kill process (cooperative stop theo spec)
    """
    print("=" * 60)
    print("🛑 [STOP] /stop triggered")
    print("=" * 60)

    control_state.set_global_emergency_stop(True)

    nst_stopped = False
    nst_error = None
    try:
        nst_stopped = bool(stop_all_browsers())
    except Exception as e:
        nst_error = str(e)
        print(f"⚠️ stop_all_browsers lỗi: {e}")

    return {"status": "ok", "global_emergency_stop": True, "nst_stopped": nst_stopped, "nst_error": nst_error}


@app.get("/status")
def status() -> dict:
    is_running = bool(runner_process and runner_process.is_alive())
    return {"running": is_running, "pid": runner_process.pid if is_running else None}


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
    if not payload.profile_ids:
        raise HTTPException(status_code=400, detail="profile_ids rỗng")

    pids = [_norm_profile_id(x) for x in payload.profile_ids]
    pids = [p for p in pids if p]
    if not pids:
        raise HTTPException(status_code=400, detail="profile_ids không hợp lệ")

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
    is_bot_running = bool(runner_process and runner_process.is_alive())
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
        "bot_pid": runner_process.pid if is_bot_running else None,
        "join_groups_running": join_running,
        "feed_running": feed_running,
    }


@app.post("/jobs/stop-all")
def stop_all_jobs() -> dict:
    """
    Dừng tất cả tác vụ nền (dùng chung cho auto join group + sau này nuôi acc).
    """
    global runner_process

    # STOP ALL theo spec: set flag trước, ưu tiên cao nhất
    print("[UI] STOP ALL triggered (/jobs/stop-all)")
    control_state.set_global_emergency_stop(True)

    stopped = {
        "bot": False,  # best-effort: chỉ báo đã SIGNAL stop
        "join_groups": [],
        "feed": [],
    }

    # 1) bot runner: KHÔNG terminate/kill (cooperative stop)
    try:
        if runner_process and runner_process.is_alive():
            stopped["bot"] = True
    except Exception:
        pass

    # 2) stop join groups processes
    join_to_stop: list[str] = []
    with _join_groups_lock:
        _prune_join_group_processes()
        join_to_stop = list(_join_groups_processes.keys())
        # KHÔNG terminate: chỉ ghi nhận để UI biết đang có
        stopped["join_groups"] = join_to_stop

    # 2b) stop feed processes
    feed_to_stop: list[str] = []
    with _feed_lock:
        _prune_feed_processes()
        feed_to_stop = list(_feed_processes.keys())
        # KHÔNG terminate: feed worker đã check flag và sẽ tự thoát
        stopped["feed"] = feed_to_stop

    # 3) Đóng NST browser (best-effort)
    nst_stop_all_ok = False
    nst_err = None
    try:
        nst_stop_all_ok = bool(stop_all_browsers())
    except Exception as e:
        nst_err = str(e)
        nst_stop_all_ok = False

    return {
        "status": "ok",
        "stopped": stopped,
        "nst_stop_attempted": [],
        "nst_stop_ok": [],
        "nst_stop_all_ok": nst_stop_all_ok,
        "nst_error": nst_err,
        # giữ field này để frontend cũ không bị crash
        "nst_force_close_results": [],
    }


# ==============================================================================
# CONTROL API (STOP / PAUSE / RESUME) - theo spec Boss
# ==============================================================================

class ProfileControlPayload(BaseModel):
    profile_id: str


class ProfilesControlPayload(BaseModel):
    profile_ids: list[str]


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
    print("[UI] STOP ALL triggered")
    control_state.set_global_emergency_stop(True)

    # best-effort: đóng NST ngay để các loop Playwright tự fail và thoát
    nst_all_ok = False
    nst_err = None
    try:
        nst_all_ok = bool(stop_all_browsers())
    except Exception as e:
        nst_err = str(e)
        print(f"⚠️ stop_all_browsers lỗi: {e}")

    return {"status": "ok", "global_emergency_stop": True, "nst_stop_all_ok": nst_all_ok, "nst_error": nst_err}


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
    pids = [_norm_profile_id(x) for x in (payload.profile_ids or [])]
    pids = [p for p in pids if p]
    print(f"[UI] STOP profiles={pids}")

    st = control_state.stop_profiles(pids)

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
