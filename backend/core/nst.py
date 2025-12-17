import requests
import json
import urllib.parse  # Cần cái này để mã hóa User-Agent có dấu cách
from typing import Optional, Any

from core.settings import reload_settings

def _get_runtime_settings():
    """
    NST API key/headless có thể đổi trong lúc backend đang chạy.
    Vì get_settings() có cache, dùng reload_settings() để lấy giá trị mới nhất.
    """
    try:
        return reload_settings()
    except Exception:
        # fallback: vẫn cố đọc cache nếu reload lỗi
        from core.settings import get_settings
        return get_settings()
NST_BASE_URL = "http://127.0.0.1:8848/api/v2"


def _nst_request(method: str, path: str, timeout: int = 15) -> Optional[Any]:
    """
    Gọi NST local API. Trả về JSON nếu parse được, None nếu lỗi.
    """
    url = f"{NST_BASE_URL}{path}"
    try:
        resp = requests.request(method, url, timeout=timeout)
        try:
            return resp.json()
        except Exception:
            return {"status_code": resp.status_code, "text": resp.text}
    except Exception:
        return None


def stop_profile(profile_id: str) -> bool:
    """
    Best-effort: yêu cầu NST stop/close browser instance của profile.
    Vì NST có nhiều bản/endpoint khác nhau, thử nhiều đường dẫn phổ biến.
    """
    pid = str(profile_id or "").strip()
    if not pid:
        return False

    cfg = _get_runtime_settings()
    api_key = str(getattr(cfg, "api_key", "") or "").strip()
    candidates = [
        ("POST", f"/browsers/stop/{pid}?x-api-key={api_key}"),
        ("GET", f"/browsers/stop/{pid}?x-api-key={api_key}"),
        ("POST", f"/browsers/close/{pid}?x-api-key={api_key}"),
        ("GET", f"/browsers/close/{pid}?x-api-key={api_key}"),
        ("POST", f"/browser/stop/{pid}?x-api-key={api_key}"),
        ("GET", f"/browser/stop/{pid}?x-api-key={api_key}"),
        ("POST", f"/browser/close/{pid}?x-api-key={api_key}"),
        ("GET", f"/browser/close/{pid}?x-api-key={api_key}"),
        ("POST", f"/stop/{pid}?x-api-key={api_key}"),
        ("GET", f"/stop/{pid}?x-api-key={api_key}"),
        ("POST", f"/close/{pid}?x-api-key={api_key}"),
        ("GET", f"/close/{pid}?x-api-key={api_key}"),
        ("POST", f"/disconnect/{pid}?x-api-key={api_key}"),
        ("GET", f"/disconnect/{pid}?x-api-key={api_key}"),
    ]

    for method, path in candidates:
        data = _nst_request(method, path)
        if not data:
            continue
        # heuristic success: err==False or code==0 or status ok
        if data.get("err") is False:
            return True
        if str(data.get("status")).lower() in {"ok", "success", "stopped", "closed"}:
            return True
        if data.get("code") in (0, 200):
            return True
    return False

def connect_profile(profile_id: str):
    cfg = _get_runtime_settings()
    api_key = str(getattr(cfg, "api_key", "") or "").strip()
    headless = bool(getattr(cfg, "headless", False))
    # Cấu hình chuẩn theo JS mẫu: Dùng fingerprint để fake User-Agent
    # KHÔNG dùng 'args' để tránh bị hiện UI
    config = {
        "headless": headless,
        "autoClose": True,
        "fingerprint": {
            # User-Agent xịn để qua mặt Facebook
            "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "hardwareConcurrency": 8,
            "deviceMemory": 8
        }
    }

    # Mã hóa config thành chuỗi an toàn cho URL (vì User-Agent có dấu cách)
    encoded_config = urllib.parse.quote(json.dumps(config))

    url = f"http://127.0.0.1:8848/api/v2/connect/{profile_id}?x-api-key={api_key}&config={encoded_config}"

    print(f"🚀 Mở profile {profile_id} (headless={headless})")

    # Thử kết nối
    try:
        resp = requests.get(url, timeout=20)
        data = resp.json()

        if data.get("err"):
            # Trả lỗi rõ hơn để debug (profile không tồn tại / api key sai / NST chưa sẵn sàng)
            # NST thường trả key: {err: true, msg: "...", code: ...}
            msg = data.get("msg") or data.get("message") or data.get("error") or data.get("err")
            raise Exception(f"❌ NST Error: {msg} | raw={data}")

        ws = data["data"]["webSocketDebuggerUrl"]
        print(f"🔌 WebSocket: {ws}")
        return ws
        
    except Exception as e:
        print(f"❌ Lỗi kết nối: {e}")
        raise e