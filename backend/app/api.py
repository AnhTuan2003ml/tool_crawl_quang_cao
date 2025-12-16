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

        profiles.setdefault(pid, {})
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
