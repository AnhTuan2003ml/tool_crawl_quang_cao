import json
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from core.paths import get_data_dir

CONTROL_STATE_PATH = get_data_dir() / "runtime_control.json"

_lock = threading.Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    tmp.replace(path)


def _default_state() -> Dict[str, Any]:
    return {
        "global_emergency_stop": False,
        "global_pause": False,
        "paused_profiles": [],
        "stopped_profiles": [],  # STOP theo profile (dừng ngay profile đó)
        "profile_states": {},  # {profile_id: RUNNING|PAUSED|STOPPED|ERROR}
        "updated_at": _now_iso(),
    }


def load_state() -> Dict[str, Any]:
    """
    Đọc state từ file runtime_control.json.
    Best-effort: nếu file lỗi/không tồn tại -> trả default.
    """
    try:
        if not CONTROL_STATE_PATH.exists():
            return _default_state()
        with CONTROL_STATE_PATH.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        if not isinstance(raw, dict):
            return _default_state()
        # Merge default keys để tránh thiếu field
        base = _default_state()
        base.update(raw)
        # normalize
        if not isinstance(base.get("paused_profiles"), list):
            base["paused_profiles"] = []
        if not isinstance(base.get("stopped_profiles"), list):
            base["stopped_profiles"] = []
        if not isinstance(base.get("profile_states"), dict):
            base["profile_states"] = {}
        base["updated_at"] = _now_iso()
        return base
    except Exception:
        return _default_state()


def save_state(state: Dict[str, Any]) -> None:
    state = dict(state or {})
    state.setdefault("paused_profiles", [])
    state.setdefault("stopped_profiles", [])
    state.setdefault("profile_states", {})
    state["updated_at"] = _now_iso()
    _atomic_write_json(CONTROL_STATE_PATH, state)


def get_state() -> Dict[str, Any]:
    with _lock:
        return load_state()


def _update(mutator) -> Dict[str, Any]:
    with _lock:
        st = load_state()
        mutator(st)
        save_state(st)
        return st


def reset_all_state() -> Dict[str, Any]:
    """
    Reset toàn bộ runtime state về mặc định (SẴN SÀNG).
    Dùng cho STOP kiểu "fresh start".
    """
    def _m(st: Dict[str, Any]) -> None:
        st.clear()
        st.update(_default_state())
    return _update(_m)


def set_global_emergency_stop(value: bool) -> Dict[str, Any]:
    def _m(st: Dict[str, Any]) -> None:
        st["global_emergency_stop"] = bool(value)
        if value:
            # Khi STOP ALL: clear pause + đưa tất cả profile_states về STOPPED để tránh "RUNNING" rác
            st["global_pause"] = False
            st["paused_profiles"] = []
            ps = st.get("profile_states")
            if not isinstance(ps, dict):
                ps = {}
            for k in list(ps.keys()):
                ps[k] = "STOPPED"
            st["profile_states"] = ps

    return _update(_m)


def set_global_pause(value: bool) -> Dict[str, Any]:
    def _m(st: Dict[str, Any]) -> None:
        st["global_pause"] = bool(value)

    return _update(_m)


def reset_emergency_stop(*, clear_stopped_profiles: bool = False) -> Dict[str, Any]:
    """
    Reset GLOBAL_EMERGENCY_STOP về false để hệ thống chạy lại được.
    Optionally clear stopped_profiles (để profile không bị giữ STOPPED).
    """
    def _m(st: Dict[str, Any]) -> None:
        st["global_emergency_stop"] = False
        if clear_stopped_profiles:
            st["stopped_profiles"] = []
            # không force đổi profile_states nếu caller muốn giữ audit;
            # nhưng nếu đang STOPPED mà clear_stopped_profiles thì set RUNNING để dễ hiểu.
            ps = st.get("profile_states")
            if isinstance(ps, dict):
                for k in list(ps.keys()):
                    if str(ps.get(k) or "").upper() == "STOPPED":
                        ps[k] = "RUNNING"

    return _update(_m)


def pause_profile(profile_id: str) -> Dict[str, Any]:
    pid = str(profile_id or "").strip()
    if not pid:
        return get_state()

    def _m(st: Dict[str, Any]) -> None:
        paused = set([str(x).strip() for x in (st.get("paused_profiles") or []) if str(x).strip()])
        paused.add(pid)
        st["paused_profiles"] = sorted(paused)
        # pause không tự clear STOP; nếu đang STOP thì vẫn STOP
        # state chỉ là "định danh", process thật sự sẽ tự update theo loop
        st.setdefault("profile_states", {})
        st["profile_states"][pid] = "PAUSED"

    return _update(_m)


def resume_profile(profile_id: str) -> Dict[str, Any]:
    pid = str(profile_id or "").strip()
    if not pid:
        return get_state()

    def _m(st: Dict[str, Any]) -> None:
        paused = [str(x).strip() for x in (st.get("paused_profiles") or []) if str(x).strip()]
        paused = [x for x in paused if x != pid]
        st["paused_profiles"] = paused
        # resume sẽ clear STOP theo profile (để chạy lại được)
        stopped = [str(x).strip() for x in (st.get("stopped_profiles") or []) if str(x).strip()]
        stopped = [x for x in stopped if x != pid]
        st["stopped_profiles"] = stopped
        st.setdefault("profile_states", {})
        st["profile_states"][pid] = "RUNNING"

    return _update(_m)


def stop_profiles(profile_ids: list[str]) -> Dict[str, Any]:
    """
    STOP theo profile: add vào stopped_profiles + set state STOPPED.
    """
    ids = []
    for x in (profile_ids or []):
        s = str(x or "").strip()
        if s:
            ids.append(s)

    if not ids:
        return get_state()

    def _m(st: Dict[str, Any]) -> None:
        stopped = set([str(x).strip() for x in (st.get("stopped_profiles") or []) if str(x).strip()])
        for pid in ids:
            stopped.add(pid)
        st["stopped_profiles"] = sorted(stopped)
        # remove khỏi paused để tránh state mâu thuẫn
        paused = [str(x).strip() for x in (st.get("paused_profiles") or []) if str(x).strip()]
        paused = [p for p in paused if p not in stopped]
        st["paused_profiles"] = paused
        st.setdefault("profile_states", {})
        for pid in ids:
            st["profile_states"][pid] = "STOPPED"

    return _update(_m)


def pause_profiles(profile_ids: list[str]) -> Dict[str, Any]:
    ids = []
    for x in (profile_ids or []):
        s = str(x or "").strip()
        if s:
            ids.append(s)
    if not ids:
        return get_state()

    def _m(st: Dict[str, Any]) -> None:
        paused = set([str(x).strip() for x in (st.get("paused_profiles") or []) if str(x).strip()])
        for pid in ids:
            paused.add(pid)
        st["paused_profiles"] = sorted(paused)
        st.setdefault("profile_states", {})
        for pid in ids:
            # nếu profile đang STOPPED thì giữ STOPPED
            cur = str(st["profile_states"].get(pid) or "").upper()
            if cur != "STOPPED":
                st["profile_states"][pid] = "PAUSED"

    return _update(_m)


def resume_profiles(profile_ids: list[str]) -> Dict[str, Any]:
    ids = []
    for x in (profile_ids or []):
        s = str(x or "").strip()
        if s:
            ids.append(s)
    if not ids:
        return get_state()

    def _m(st: Dict[str, Any]) -> None:
        paused = [str(x).strip() for x in (st.get("paused_profiles") or []) if str(x).strip()]
        paused = [p for p in paused if p not in set(ids)]
        st["paused_profiles"] = paused
        # resume cũng clear STOP theo profile (để profile chạy lại được)
        stopped = [str(x).strip() for x in (st.get("stopped_profiles") or []) if str(x).strip()]
        stopped = [p for p in stopped if p not in set(ids)]
        st["stopped_profiles"] = stopped
        st.setdefault("profile_states", {})
        for pid in ids:
            st["profile_states"][pid] = "RUNNING"

    return _update(_m)


def set_profile_state(profile_id: str, state: str) -> Dict[str, Any]:
    pid = str(profile_id or "").strip()
    if not pid:
        return get_state()
    s = str(state or "").strip().upper()
    if s not in {"RUNNING", "PAUSED", "STOPPED", "ERROR"}:
        s = "ERROR"

    def _m(st: Dict[str, Any]) -> None:
        st.setdefault("profile_states", {})
        st["profile_states"][pid] = s

    return _update(_m)


def check_flags(profile_id: Optional[str] = None) -> Tuple[bool, bool, str]:
    """
    Return: (emergency_stop, paused, pause_reason)
    Priority:
      1) emergency_stop
      2) global_pause
      3) paused_profiles[pid]
    """
    st = get_state()
    if bool(st.get("global_emergency_stop")):
        return True, False, "GLOBAL_EMERGENCY_STOP"

    pid = str(profile_id or "").strip()

    # STOP theo profile (ưu tiên hơn pause)
    stopped_set = set([str(x).strip() for x in (st.get("stopped_profiles") or []) if str(x).strip()])
    if pid and pid in stopped_set:
        return True, False, "STOPPED_PROFILE"

    if bool(st.get("global_pause")):
        return False, True, "GLOBAL_PAUSE"

    paused_set = set([str(x).strip() for x in (st.get("paused_profiles") or []) if str(x).strip()])
    if pid and pid in paused_set:
        return False, True, "PAUSED_PROFILE"

    return False, False, ""


def wait_if_paused(profile_id: Optional[str], sleep_seconds: float = 0.5) -> None:
    """
    Nếu PAUSE -> sleep + check flag liên tục.
    Nếu emergency_stop -> raise RuntimeError để caller thoát ngay.
    """
    pid = str(profile_id or "").strip()
    while True:
        stop, paused, _reason = check_flags(pid)
        if stop:
            raise RuntimeError("EMERGENCY_STOP")
        if not paused:
            return
        time.sleep(max(0.2, float(sleep_seconds)))


def smart_sleep(seconds: float, profile_id: Optional[str] = None) -> None:
    """
    Sleep thông minh với khả năng STOP/PAUSE:
    - Sleep theo chunk 0.5s
    - Check STOP/PAUSE mỗi chunk
    - Nếu STOP: raise RuntimeError("EMERGENCY_STOP") ngay lập tức
    - Nếu PAUSE: block trong wait_if_paused và KHÔNG giảm remaining time
    - Nếu NORMAL: sleep chunk và giảm remaining time
    
    Args:
        seconds: Tổng số giây cần sleep
        profile_id: Profile ID để check STOP/PAUSE (optional)
    
    Raises:
        RuntimeError: Nếu bị STOP (message = "EMERGENCY_STOP")
    """
    remaining = float(seconds)
    chunk = 0.5
    pid = str(profile_id or "").strip() if profile_id else None
    
    while remaining > 0:
        stop, paused, _reason = check_flags(pid)
        
        if stop:
            raise RuntimeError("EMERGENCY_STOP")
        
        if paused:
            # PAUSE: block trong wait_if_paused, KHÔNG giảm remaining time
            wait_if_paused(pid, sleep_seconds=chunk)
            continue
        
        # NORMAL: sleep chunk và giảm remaining time
        sleep_time = min(chunk, remaining)
        time.sleep(sleep_time)
        remaining -= sleep_time


