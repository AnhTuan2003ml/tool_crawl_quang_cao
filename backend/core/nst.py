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
NST_BASE_URLS = [
    "http://127.0.0.1:8848/api/v2",
    "http://127.0.0.1:8848/api/v1",
    "http://127.0.0.1:8848/api",
]


def _nst_request(method: str, path: str, timeout: int = 15, headers: Optional[dict] = None, data: Optional[Any] = None) -> Optional[Any]:
    """
    Gọi NST local API. Trả về JSON nếu parse được, None nếu lỗi.
    """
    for base in NST_BASE_URLS:
        url = f"{base}{path}"
        try:
            print(f"      🔗 Thử: {method} {url}")
            if data is not None:
                print(f"         → Body: {data}")
            resp = requests.request(method, url, timeout=timeout, headers=headers, json=data if data is not None else None)
            print(f"         → Status: {resp.status_code}")
            try:
                json_data = resp.json()
                print(f"         → Response: {json_data}")
                return json_data
            except Exception as json_err:
                text_data = {"status_code": resp.status_code, "text": resp.text[:200]}
                print(f"         → Response (không phải JSON): {text_data}")
                return text_data
        except Exception as req_err:
            print(f"         ❌ Lỗi request: {req_err}")
            continue
    print(f"      ⚠️ Không endpoint nào thành công cho {method} {path}")
    return None


def stop_profile(profile_id: str) -> bool:
    """
    Dừng browser instance của profile bằng DELETE /api/v2/browsers/{profile_id}
    """
    pid = str(profile_id or "").strip()
    if not pid:
        print(f"   ⚠️ [stop_profile] profile_id rỗng")
        return False

    print(f"   🔍 [stop_profile] Đang dừng profile: {pid}")
    
    cfg = _get_runtime_settings()
    api_key = str(getattr(cfg, "api_key", "") or "").strip()
    hdr = {
        "x-api-key": api_key,
        "Content-Type": "application/json"
    } if api_key else {"Content-Type": "application/json"}
    
    # Dùng DELETE /browsers/{profile_id} (base URL đã có /api/v2)
    path = f"/browsers/{pid}"
    
    print(f"   📋 API Key: {'Có' if api_key else 'Không có'}")
    print(f"   📋 Endpoint: DELETE {path}")
    
    data = _nst_request("DELETE", path, headers=hdr)
    if not data:
        print(f"   ❌ [stop_profile] Không có response từ NST")
        return False
    
    # Kiểm tra kết quả
    if isinstance(data, dict):
        # Idempotent: nếu browser instance không tồn tại thì coi như đã dừng rồi
        msg_lower = str(data.get("msg") or data.get("message") or "").lower()
        if data.get("code") == 400 and "browser instance not found" in msg_lower:
            print(f"   ✅ [stop_profile] Browser đã đóng sẵn / không tồn tại (code=400). Coi như thành công.")
            return True

        if data.get("err") is False:
            print(f"   ✅ [stop_profile] THÀNH CÔNG! err=False")
            return True
        status_lower = str(data.get("status", "")).lower()
        if status_lower in {"ok", "success", "stopped", "closed"}:
            print(f"   ✅ [stop_profile] THÀNH CÔNG! status={status_lower}")
            return True
        if data.get("code") in (0, 200):
            print(f"   ✅ [stop_profile] THÀNH CÔNG! code={data.get('code')}")
            return True
        print(f"   ⚠️ [stop_profile] Không match điều kiện thành công (err={data.get('err')}, status={data.get('status')}, code={data.get('code')})")
    else:
        print(f"   ⚠️ [stop_profile] Response không phải dict: {type(data)}")
    
    return False


def stop_all_browsers() -> bool:
    """
    Đóng toàn bộ browser NST bằng DELETE /api/v2/browsers với body là array các profile_id.
    """
    print("   🔍 [stop_all_browsers] Bắt đầu đóng toàn bộ NST browser...")
    
    cfg = _get_runtime_settings()
    api_key = str(getattr(cfg, "api_key", "") or "").strip()
    hdr = {
        "x-api-key": api_key,
        "Content-Type": "application/json"
    } if api_key else {"Content-Type": "application/json"}
    
    print(f"   📋 API Key: {'Có' if api_key else 'Không có'}")
    
    # Lấy danh sách profile_id từ settings
    try:
        from core.settings import get_settings
        settings = get_settings()
        profile_ids = []
        
        # Lấy từ PROFILE_IDS (có thể là dict hoặc list)
        profile_data = getattr(settings, "profile_ids", None)
        if isinstance(profile_data, dict):
            profile_ids = list(profile_data.keys())
        elif isinstance(profile_data, list):
            profile_ids = profile_data
        elif isinstance(profile_data, str):
            profile_ids = [p.strip() for p in profile_data.split(",") if p.strip()]
        
        profile_ids = [str(pid).strip() for pid in profile_ids if str(pid).strip()]
        
        if not profile_ids:
            print(f"   ⚠️ [stop_all_browsers] Không tìm thấy profile_id nào trong settings")
            # Vẫn thử gọi với array rỗng
            profile_ids = []
    except Exception as e:
        print(f"   ⚠️ [stop_all_browsers] Lỗi khi lấy profile_ids: {e}")
        profile_ids = []
    
    print(f"   📋 Số profile sẽ đóng: {len(profile_ids)}")
    if profile_ids:
        print(f"   📋 Profile IDs: {profile_ids}")
    
    # Dùng DELETE /browsers với body là JSON array các profile_id (base URL đã có /api/v2)
    path = "/browsers"
    payload = profile_ids  # requests sẽ tự động convert list thành JSON array
    
    print(f"   📋 Endpoint: DELETE {path}")
    print(f"   📋 Body: {payload}")
    
    data = _nst_request("DELETE", path, headers=hdr, data=payload)
    if not data:
        print(f"   ❌ [stop_all_browsers] Không có response từ NST")
        return False
    
    # Kiểm tra kết quả
    if isinstance(data, dict):
        # Idempotent: nếu không có browser instance nào thì coi như đã đóng hết
        msg_lower = str(data.get("msg") or data.get("message") or "").lower()
        if data.get("code") == 400 and "browser instance not found" in msg_lower:
            print(f"   ✅ [stop_all_browsers] Browser đã đóng sẵn / không tồn tại (code=400). Coi như thành công.")
            return True

        if data.get("err") is False:
            print(f"   ✅ [stop_all_browsers] THÀNH CÔNG! err=False")
            return True
        status_lower = str(data.get("status", "")).lower()
        if status_lower in {"ok", "success", "stopped", "closed"}:
            print(f"   ✅ [stop_all_browsers] THÀNH CÔNG! status={status_lower}")
            return True
        if data.get("code") in (0, 200):
            print(f"   ✅ [stop_all_browsers] THÀNH CÔNG! code={data.get('code')}")
            return True
        print(f"   ⚠️ [stop_all_browsers] Không match điều kiện thành công (err={data.get('err')}, status={data.get('status')}, code={data.get('code')})")
    else:
        print(f"   ⚠️ [stop_all_browsers] Response không phải dict: {type(data)}")
    
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

    # Connect vẫn ưu tiên v2 vì đang dùng ổn định
    url = f"http://127.0.0.1:8848/api/v2/connect/{profile_id}?x-api-key={api_key}&config={encoded_config}"

    print(f"🚀 Mở profile {profile_id} (headless={headless})")

    # Thử kết nối
    try:
        resp = requests.get(url, timeout=20)
        data = resp.json()

        if data.get("err"):
            # Trả lỗi rõ hơn để debug (profile không tồn tại / api key sai / NST chưa sẵn sàng)
            # NST thường trả key: {err: true, msg: "...", code: ...}
            msg = data.get("msg") or data.get("message") or data.get("error") or str(data.get("err"))
            code = data.get("code", "unknown")
            
            # Xử lý đặc biệt cho lỗi 400 (profile không tồn tại)
            if code == 400:
                error_msg = f"❌ NST Error: Profile '{profile_id}' không tồn tại trong NST. Vui lòng kiểm tra lại profile_id hoặc tạo profile mới trong NST. | code={code}, msg={msg}"
            else:
                error_msg = f"❌ NST Error: {msg} | code={code}, raw={data}"
            
            raise Exception(error_msg)

        ws = data["data"]["webSocketDebuggerUrl"]
        print(f"🔌 WebSocket: {ws}")
        return ws
        
    except requests.exceptions.RequestException as e:
        error_msg = f"❌ Lỗi kết nối NST: Không thể kết nối đến NST server (http://127.0.0.1:8848). Vui lòng kiểm tra NST đã chạy chưa. | {str(e)}"
        print(error_msg)
        raise Exception(error_msg)
    except KeyError as e:
        error_msg = f"❌ Lỗi response từ NST: Response không có đầy đủ dữ liệu. | {str(e)}"
        print(error_msg)
        raise Exception(error_msg)
    except Exception as e:
        # Nếu đã là Exception với message rõ ràng thì giữ nguyên
        if "❌ NST Error:" in str(e):
            print(f"❌ Lỗi kết nối: {e}")
            raise e
        # Nếu là exception khác thì wrap lại
        error_msg = f"❌ Lỗi kết nối profile '{profile_id}': {str(e)}"
        print(error_msg)
        raise Exception(error_msg) from e