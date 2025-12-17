from multiprocessing import Process
from typing import Optional, Any, Dict
from pathlib import Path
import json
import os
import tempfile
import threading
import re

from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.runner import AppRunner
from core.settings import SETTINGS_PATH
from core.nst import connect_profile, stop_profile
from core.browser import FBController

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


def _run_join_groups_worker(profile_id: str, groups: list[str]) -> None:
    """Worker chạy join groups cho 1 profile (để chạy song song nhiều profile)."""
    try:
        from core.join_groups import run_batch_join_from_list
        run_batch_join_from_list(profile_id, groups)
    except Exception as exc:
        print(f"❌ Join groups worker lỗi ({profile_id}): {exc}")


def _norm_profile_id(value: str) -> str:
    """Chuẩn hoá profile_id: bỏ toàn bộ whitespace (tránh lỗi dính space khi copy/paste)."""
    return re.sub(r"\s+", "", str(value or "")).strip()


class RunRequest(BaseModel):
    run_minutes: Optional[int] = None
    rest_minutes: Optional[int] = None


def _start_runner(run_minutes: Optional[int] = None, rest_minutes: Optional[int] = None) -> None:
    """Hàm wrapper để chạy vòng lặp AppRunner trong tiến trình riêng."""
    AppRunner(run_minutes=run_minutes, rest_minutes=rest_minutes).run()


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

    # Không dùng daemon vì AppRunner tự sinh thêm Process con
    runner_process = Process(
        target=_start_runner,
        args=(run_minutes, rest_minutes),
        daemon=False,
    )
    runner_process.start()

    if not runner_process.is_alive():
        raise HTTPException(status_code=500, detail="Không khởi động được bot")

    return {"status": "started", "pid": runner_process.pid}


@app.post("/stop")
def stop_bot() -> dict:
    """Dừng tiến trình AppRunner nếu đang chạy."""
    global runner_process

    if not runner_process or not runner_process.is_alive():
        return {"status": "not_running"}

    runner_process.terminate()
    runner_process.join(timeout=5)

    was_alive = runner_process.is_alive()
    runner_process = None

    if was_alive:
        raise HTTPException(status_code=500, detail="Không dừng được bot")

    return {"status": "stopped"}


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
