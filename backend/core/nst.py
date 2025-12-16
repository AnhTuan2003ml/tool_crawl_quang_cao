import requests
import json
import urllib.parse  # Cần cái này để mã hóa User-Agent có dấu cách

from core.settings import get_settings

settings = get_settings()
API_KEY = settings.api_key
HEADLESS = settings.headless

def connect_profile(profile_id: str):
    # Cấu hình chuẩn theo JS mẫu: Dùng fingerprint để fake User-Agent
    # KHÔNG dùng 'args' để tránh bị hiện UI
    config = {
        "headless": HEADLESS,
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

    url = f"http://127.0.0.1:8848/api/v2/connect/{profile_id}?x-api-key={API_KEY}&config={encoded_config}"

    print(f"🚀 Mở profile {profile_id} (headless={HEADLESS})")

    # Thử kết nối
    try:
        resp = requests.get(url, timeout=20)
        data = resp.json()

        if data.get("err"):
            raise Exception(f"❌ NST Error: {data.get('err')}")

        ws = data["data"]["webSocketDebuggerUrl"]
        print(f"🔌 WebSocket: {ws}")
        return ws
        
    except Exception as e:
        print(f"❌ Lỗi kết nối: {e}")
        raise e