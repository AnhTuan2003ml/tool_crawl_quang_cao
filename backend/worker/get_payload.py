import requests
import re
import json
import time
import sys
import os
from urllib.parse import parse_qs, unquote_plus
from pathlib import Path
from playwright.sync_api import sync_playwright

# ====== FIX IMPORT PATH KHI CHẠY TRỰC TIẾP ======
# Nếu chạy trực tiếp từ thư mục worker, thêm parent directory vào sys.path
if __name__ == "__main__" or not any("core" in str(p) for p in sys.path):
    current_file = Path(__file__).resolve()
    # Tìm backend directory (parent của worker)
    backend_dir = current_file.parent.parent
    if backend_dir.exists() and backend_dir.name == "backend":
        backend_path = str(backend_dir)
        if backend_path not in sys.path:
            sys.path.insert(0, backend_path)

# ====== ĐƯỜNG DẪN THEO PROJECT ROOT ======
try:
    from core.paths import get_config_dir, get_settings_path
    SETTINGS_JSON_FILE = get_settings_path()  # backend/config/settings.json
    PAYLOAD_TXT_FILE = get_config_dir() / "payload.txt"
except ImportError:
    # Fallback nếu không import được core.paths
    if getattr(sys, 'frozen', False):
        # Đang chạy từ file .exe -> Lấy thư mục chứa file exe
        config_dir = Path(sys.executable).parent / "config"
        SETTINGS_JSON_FILE = config_dir / "settings.json"
        PAYLOAD_TXT_FILE = config_dir / "payload.txt"
    else:
        # Đang chạy code python -> Lấy thư mục backend/config
        current_file = Path(__file__).resolve()
        backend_dir = current_file.parent.parent
        config_dir = backend_dir / "config"
        SETTINGS_JSON_FILE = config_dir / "settings.json"
        PAYLOAD_TXT_FILE = config_dir / "payload.txt"


def _normalize_cookie(cookie: str | None) -> str | None:
    if cookie is None:
        return None
    cookie = str(cookie).strip()
    if not cookie:
        return None
    # Loại bỏ ký tự xuống dòng và khoảng trắng thừa
    return " ".join(cookie.split())


def _read_settings_profile_config(profile_id: str) -> dict | None:
    """
    Đọc PROFILE_IDS[profile_id] từ backend/config/settings.json.
    Trả về dict config hoặc None nếu không có.
    """
    try:
        if not SETTINGS_JSON_FILE.exists():
            return None
        with SETTINGS_JSON_FILE.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        profiles = raw.get("PROFILE_IDS")
        if not isinstance(profiles, dict):
            return None
        cfg = profiles.get(profile_id)
        return cfg if isinstance(cfg, dict) else None
    except Exception:
        return None


def get_cookies_by_profile_id(profile_id):
    """
    Lấy cookies theo profile_id.

    Ưu tiên đọc từ backend/config/settings.json:
      PROFILE_IDS[profile_id].cookie
    
    Args:
        profile_id (str): Profile ID (ví dụ: "031ca13d-e8fa-400c-a603-df57a2806788")
    
    Returns:
        str: Cookie string hoặc None nếu không tìm thấy
    """
    # 1) ƯU TIÊN: settings.json
    cfg = _read_settings_profile_config(profile_id)
    if cfg is not None:
        cookie = _normalize_cookie(cfg.get("cookie"))
        if cookie:
            return cookie

    print(f"❌ Không tìm thấy cookie trong {SETTINGS_JSON_FILE} cho profile_id='{profile_id}'")
    return None


def get_access_token_by_profile_id(profile_id):
    """
    Lấy access_token theo profile_id.

    Ưu tiên đọc từ backend/config/settings.json:
      PROFILE_IDS[profile_id].access_token
    
    Args:
        profile_id (str): Profile ID (ví dụ: "031ca13d-e8fa-400c-a603-df57a2806788")
    
    Returns:
        str: Access token hoặc None nếu không tìm thấy
    """
    # 1) ƯU TIÊN: settings.json
    cfg = _read_settings_profile_config(profile_id)
    if cfg is not None:
        access_token = str(cfg.get("access_token") or "").strip()
        if access_token:
            return access_token

    print(f"❌ Không tìm thấy access_token trong {SETTINGS_JSON_FILE} cho profile_id='{profile_id}'")
    return None


def get_base_headers(cookie):
    """
    Tạo headers với cookie được truyền vào
    
    Args:
        cookie (str): Cookie string
    
    Returns:
        dict: Headers dictionary
    """
    return {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "accept-encoding": "gzip, deflate",
        "accept-language": "en,vi;q=0.9,en-US;q=0.8",
        "cookie": cookie,
        "referer": "https://www.facebook.com/",
        "sec-ch-ua": '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "same-origin",
        "upgrade-insecure-requests": "1",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
    }


def get_c_user(cookie):
    """
    Lấy c_user từ cookie
    
    Args:
        cookie (str): Cookie string
    
    Returns:
        str: Giá trị c_user hoặc None nếu không tìm thấy
    """
    try:
        match = re.search(r'c_user=(\d+)', cookie)
        if match:
            return match.group(1)
        return None
    except Exception as e:
        print(f"⚠️ Lỗi khi lấy c_user: {e}")
        return None


def get_jazoest(fb_dtsg):
    """
    Tính jazoest từ fb_dtsg
    
    Args:
        fb_dtsg (str): Giá trị fb_dtsg
    
    Returns:
        str: Giá trị jazoest
    """
    if not fb_dtsg:
        return None
    jazoest = str(sum(ord(c) for c in fb_dtsg))
    return jazoest


def get_lsd(html):
    """
    Lấy lsd từ HTML
    
    Args:
        html (str): HTML content
    
    Returns:
        str: Giá trị lsd hoặc None nếu không tìm thấy
    """
    try:
        match = re.search(r'"LSD",\[\],{"token":"(.*?)"}', html)
        if match:
            return match.group(1)
        return None
    except Exception as e:
        print(f"⚠️ Lỗi khi lấy lsd: {e}")
        return None


def get_spin_r(html):
    """
    Lấy __spin_r từ HTML
    
    Args:
        html (str): HTML content
    
    Returns:
        str: Giá trị __spin_r hoặc None nếu không tìm thấy
    """
    try:
        match = re.search(r'"__spin_r":(\d+)', html)
        if match:
            return match.group(1)
        return None
    except Exception as e:
        print(f"⚠️ Lỗi khi lấy __spin_r: {e}")
        return None


def get_spin_t(html):
    """
    Lấy __spin_t từ HTML
    
    Args:
        html (str): HTML content
    
    Returns:
        str: Giá trị __spin_t hoặc None nếu không tìm thấy
    """
    try:
        match = re.search(r'"__spin_t":(\d+)', html)
        if match:
            return match.group(1)
        return None
    except Exception as e:
        print(f"⚠️ Lỗi khi lấy __spin_t: {e}")
        return None


def get_fb_dtsg(cookie, profile_id: str | None = None, return_page_source: bool = False):
    """
    Lấy fb_dtsg từ Facebook.com sử dụng Playwright

    Args:
        cookie (str): Cookie string để sử dụng

    Returns:
        str: Giá trị fb_dtsg hoặc None nếu không tìm thấy
    """
    url = "https://www.facebook.com"

    print(f"\n🚀 Bắt đầu headless capture từ: {url} (DÙNG Playwright)")

    # First: if profile_id provided, try reading fb_dtsg from settings.json
    try:
        if profile_id:
            cfg = _read_settings_profile_config(profile_id)
            if isinstance(cfg, dict):
                fb_from_cfg = cfg.get("fb_dtsg") or cfg.get("fb_dtsg_token") or cfg.get("fb_dtsg_value")
                if fb_from_cfg:
                    fb_from_cfg = str(fb_from_cfg).strip()
                    if fb_from_cfg:
                        print(f"ℹ️ Lấy fb_dtsg từ {SETTINGS_JSON_FILE} cho profile_id={profile_id}")
                        if return_page_source:
                            return fb_from_cfg, ""
                        return fb_from_cfg
    except Exception:
        pass

    # Require Playwright; fail loudly if unavailable
    try:
        pass  # Playwright already imported at module level
    except Exception as e:
        print(f"❌ Playwright not available: {e}")
        return None

    fb_dtsg = None
    page_source = ""

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1200, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
        )

        # Add cookies
        cookies = []
        for c in cookie.split(";"):
            if "=" in c:
                k, v = c.strip().split("=", 1)
                cookies.append({
                    "name": k,
                    "value": v,
                    "domain": ".facebook.com",
                    "path": "/"
                })
        context.add_cookies(cookies)

        page = context.new_page()

        # Listen for network requests to capture GraphQL POST data
        def on_request(request):
            nonlocal fb_dtsg
            if (
                request.method == "POST"
                and "/api/graphql" in request.url
                and request.post_data
            ):
                post_data = request.post_data
                # Try to find fb_dtsg in post data
                m = re.search(r'fb_dtsg["\\\']?\\s*[:=]\\s*["\\\']([^"\\\']+)', post_data)
                if not m:
                    m = re.search(r'fb_dtsg=([^&"\\\']+)', post_data)
                if m:
                    fb_dtsg = m.group(1)
                    print(f"✅ Bắt được fb_dtsg từ graphql postData: {fb_dtsg[:50]}...")

        page.on("request", on_request)

        try:
            page.goto(url, timeout=60000)
            time.sleep(3)  # Wait for page to load and requests to be made

            # If not found in network requests, search in page source
            if not fb_dtsg:
                page_source = page.content()
                patterns = [
                    r'"name":"fb_dtsg","value":"([^"]+)"',
                    r'"token":"([^"]+)","type":"fb_dtsg"',
                    r'"fb_dtsg"\\s*:\\s*"([^"]+)"',
                    r'name="fb_dtsg"\\s+value="([^"]+)"',
                    r'DTSGInitData.*?"token":"([^"]+)"'
                ]
                for i, pattern in enumerate(patterns, 1):
                    match = re.search(pattern, page_source)
                    if match:
                        fb_dtsg = match.group(1)
                        print(f"✅ Tìm thấy fb_dtsg trong page_source với pattern {i}: {fb_dtsg[:50]}...")
                        break

            if return_page_source and not page_source:
                page_source = page.content()

        except Exception as e:
            print(f"❌ Lỗi khi navigate hoặc capture: {e}")
        finally:
            browser.close()

    if return_page_source:
        return fb_dtsg, page_source
    return fb_dtsg

from urllib.parse import parse_qs, unquote_plus
import time

def capture_graphql_post_payloads(cookie_str, timeout=8):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()

        # Inject cookie
        cookies = []
        for c in cookie_str.split(";"):
            if "=" in c:
                k, v = c.strip().split("=", 1)
                cookies.append({
                    "name": k,
                    "value": v,
                    "domain": ".facebook.com",
                    "path": "/"
                })
        context.add_cookies(cookies)

        page = context.new_page()
        payload_found = {}

        def on_request(request):
            if (
                request.method == "POST"
                and "/api/graphql" in request.url
                and request.post_data
            ):
                parsed = parse_qs(request.post_data)
                flat = {
                    k: unquote_plus(v[0]) if v else ""
                    for k, v in parsed.items()
                }
                payload_found.update(flat)

        page.on("request", on_request)
        page.goto("https://www.facebook.com", timeout=60000)
        time.sleep(timeout)

        browser.close()
        return payload_found or None




def get_all_payload_values(cookie, profile_id: str | None = None):
    """
    Lấy tất cả các giá trị payload từ Facebook.com
    
    Args:
        cookie (str): Cookie string để sử dụng
    
    Returns:
        dict: Dictionary chứa c_user, av, __user, fb_dtsg, jazoest, lsd, spin_r, spin_t hoặc None nếu lỗi
    """
    # CHỈ DÙNG HEADLESS SELENIUM: không còn fallback bằng requests.get
    try:
        # Lấy c_user từ cookie (từ cookie string)
        c_user = get_c_user(cookie)
        if c_user:
            print(f"✅ Tìm thấy c_user: {c_user}")
        else:
            print(f"⚠️ Không tìm thấy c_user trong cookie")

        # Try to get fb_dtsg from settings.json first (if profile_id provided)
        fb_from_cfg = None
        if profile_id:
            try:
                cfg = _read_settings_profile_config(profile_id)
                if isinstance(cfg, dict):
                    fb_from_cfg = cfg.get("fb_dtsg") or cfg.get("fb_dtsg_token") or cfg.get("fb_dtsg_value")
                    if fb_from_cfg:
                        fb_from_cfg = str(fb_from_cfg).strip()
            except Exception:
                fb_from_cfg = None

        fb_dtsg = None
        html_content = ""
        payload = {}

        # If fb_dtsg not present in settings, capture graphql POST payload to extract it and other values.
        if not fb_from_cfg:
            parsed_post = capture_graphql_post_payload(cookie, timeout=5)
            if not parsed_post:
                print("❌ Không tìm thấy POST /api/graphql hoặc không parse được payload")
                return None
            payload = parsed_post  # dict of string->string
            fb_dtsg = payload.get("fb_dtsg") or payload.get("fb_dtsg_token") or None
            if fb_dtsg:
                print(f"✅ fb_dtsg từ payload: {fb_dtsg[:30]}...")
                # Persist fb_dtsg into settings.json for this profile_id if provided
                if profile_id:
                    try:
                        if SETTINGS_JSON_FILE.exists():
                            with SETTINGS_JSON_FILE.open("r", encoding="utf-8") as sf:
                                sdata = json.load(sf)
                        else:
                            sdata = {}
                        profiles = sdata.get("PROFILE_IDS") or {}
                        if not isinstance(profiles, dict):
                            profiles = {}
                        profile_cfg = profiles.get(profile_id) or {}
                        if not isinstance(profile_cfg, dict):
                            profile_cfg = {}
                        profile_cfg["fb_dtsg"] = fb_dtsg
                        profiles[profile_id] = profile_cfg
                        sdata["PROFILE_IDS"] = profiles
                        with SETTINGS_JSON_FILE.open("w", encoding="utf-8") as sf:
                            json.dump(sdata, sf, ensure_ascii=False, indent=2)
                        print(f"✅ Đã ghi fb_dtsg vào {SETTINGS_JSON_FILE} cho profile_id={profile_id}")
                    except Exception as e:
                        print(f"⚠️ Không thể ghi fb_dtsg vào settings.json: {e}")
        else:
            fb_dtsg = fb_from_cfg
            payload = {}
            print(f"ℹ️ Sử dụng fb_dtsg từ {SETTINGS_JSON_FILE} cho profile_id={profile_id} — không khởi động headless capture")

        # prefer payload __user/av when present, otherwise use c_user
        av = payload.get("av") or payload.get("__user") or payload.get("__aaid") or c_user
        __user = payload.get("__user") or av or c_user
        c_user_final = c_user or __user or av

        # jazoest may be present in payload, otherwise compute from fb_dtsg
        jazoest = payload.get("jazoest") or (get_jazoest(fb_dtsg) if fb_dtsg else None)

        # lsd / spin values may be present in payload or in page source
        lsd = payload.get("lsd") or payload.get("x-fb-lsd") or None
        spin_r = payload.get("__spin_r") or None
        spin_t = payload.get("__spin_t") or None

        print(f"✅ Bắt được graphql payload keys: {list(payload.keys())}")
        if fb_dtsg:
            print(f"✅ fb_dtsg: {fb_dtsg[:30]}...")

        result = {
            "c_user": c_user_final,
            "av": av,
            "__user": __user,
            "fb_dtsg": fb_dtsg,
            "jazoest": jazoest,
            "lsd": lsd,
            "spin_r": spin_r,
            "spin_t": spin_t
        }
        return result
    except Exception as e:
        print(f"❌ Lỗi khi lấy payload values (headless): {e}")
        import traceback
        traceback.print_exc()
        return None


def capture_graphql_post_payload(cookie, timeout: int = 8):
    """
    Dùng headless Playwright để bắt POST requests tới /api/graphql/
    Trả về dictionary từ postData (form-urlencoded) của request đầu tìm được.

    Args:
        cookie (str): Cookie string để inject
        timeout (int): Số giây chờ sau khi load trang để thu requests

    Returns:
        dict | None: parsed payload (string->string) hoặc None nếu không tìm thấy
    """
    try:
        from urllib.parse import parse_qs, unquote_plus
    except Exception as e:
        print(f"❌ Playwright hoặc urllib không có: {e}")
        return None

    payload_found = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1200, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
        )

        # Add cookies
        cookies = []
        for c in cookie.split(";"):
            if "=" in c:
                k, v = c.strip().split("=", 1)
                cookies.append({
                    "name": k,
                    "value": v,
                    "domain": ".facebook.com",
                    "path": "/"
                })
        context.add_cookies(cookies)

        page = context.new_page()

        def on_request(request):
            if (
                request.method == "POST"
                and "/api/graphql" in request.url
                and request.post_data
                and not payload_found  # Only capture the first one
            ):
                post_data = request.post_data
                try:
                    # postData is form-urlencoded string; parse it
                    parsed = parse_qs(post_data, keep_blank_values=True)
                    # flatten values: take first value and url-decode
                    flat = {k: unquote_plus(v[0]) if isinstance(v, list) and v else (v if isinstance(v, str) else "") for k, v in parsed.items()}
                    payload_found.update(flat)
                    print(f"✅ Bắt được graphql POST tại {request.url}, keys: {list(flat.keys())}")
                except Exception as e:
                    print(f"⚠️ Lỗi khi parse postData: {e}")
                    # try manual parse fallback
                    try:
                        parts = post_data.split("&")
                        flat = {}
                        for p in parts:
                            if "=" in p:
                                k, v = p.split("=", 1)
                                flat[k] = unquote_plus(v)
                        if flat:
                            payload_found.update(flat)
                            print(f"✅ Bắt được graphql POST (manual parse), keys: {list(flat.keys())}")
                    except Exception:
                        pass

        page.on("request", on_request)

        try:
            page.goto("https://www.facebook.com", timeout=60000)
            time.sleep(timeout)  # Wait for requests to be made
        except Exception as e:
            print(f"❌ Lỗi khi navigate: {e}")
        finally:
            browser.close()

    if payload_found:
        return payload_found
    else:
        print("⚠️ Không tìm thấy POST tới /api/graphql/")
        return None


def create_payload_dict(payload_values):
    """
    Tạo payload dictionary từ payload.txt và payload_values
    
    Args:
        payload_values (dict): Dictionary chứa các giá trị động (fb_dtsg, jazoest, lsd, etc.)
    
    Returns:
        dict: Payload dictionary hoàn chỉnh
    """
    try:
        # Đọc file payload.txt
        with PAYLOAD_TXT_FILE.open("r", encoding="utf-8") as f:
            content = f.read().strip()
        
        # Parse từng dòng key: value
        payload_dict = {}
        for line in content.split('\n'):
            line = line.strip()
            if not line or not ':' in line:
                continue
            
            # Tách key và value
            parts = line.split(':', 1)
            if len(parts) == 2:
                key = parts[0].strip().replace('"', '').replace("'", '')
                value = parts[1].strip().replace('"', '').replace("'", '').rstrip(',').strip()
                if key and value:
                    payload_dict[key] = value
        
        # Cập nhật các giá trị động từ payload_values
        if payload_values.get('c_user'):
            payload_dict['av'] = payload_values['c_user']
            payload_dict['__user'] = payload_values['c_user']
        
        if payload_values.get('fb_dtsg'):
            payload_dict['fb_dtsg'] = payload_values['fb_dtsg']
        
        if payload_values.get('jazoest'):
            payload_dict['jazoest'] = payload_values['jazoest']
        
        if payload_values.get('lsd'):
            payload_dict['lsd'] = payload_values['lsd']
        
        if payload_values.get('spin_r'):
            payload_dict['__spin_r'] = payload_values['spin_r']
        
        if payload_values.get('spin_t'):
            payload_dict['__spin_t'] = payload_values['spin_t']
        
        print(f"✅ Đã tạo payload dictionary với {len(payload_dict)} keys")
        return payload_dict
        
    except FileNotFoundError:
        print(f"❌ Không tìm thấy file {PAYLOAD_TXT_FILE}!")
        return None
    except Exception as e:
        print(f"❌ Lỗi khi tạo payload dict: {e}")
        return None


def get_payload_by_profile_id(profile_id):
    """
    Lấy payload dictionary dựa trên profile_id
    
    Args:
        profile_id (str): Profile ID (ví dụ: "031ca13d-e8fa-400c-a603-df57a2806788")
    
    Returns:
        dict: Payload dictionary hoàn chỉnh hoặc None nếu lỗi
    """
    # Lấy cookies từ profile_id
    cookie = get_cookies_by_profile_id(profile_id)
    if not cookie:
        return None
    
    # Lấy payload values từ Facebook (truyền profile_id để ưu tiên fb_dtsg từ settings.json)
    payload_values = get_all_payload_values(cookie, profile_id=profile_id)
    if not payload_values:
        return None
    
    # Tạo payload dict từ payload.txt và payload_values
    payload_dict = create_payload_dict(payload_values)
    return payload_dict


def update_payload_file(payload_values):
    """
    Cập nhật file payload.txt với các giá trị mới
    
    Args:
        payload_values (dict): Dictionary chứa các giá trị cần cập nhật
            - c_user: Giá trị c_user (sẽ thay cho av và __user)
            - fb_dtsg: Giá trị fb_dtsg
            - jazoest: Giá trị jazoest
            - lsd: Giá trị lsd
            - spin_r: Giá trị __spin_r
            - spin_t: Giá trị __spin_t
    
    Returns:
        bool: True nếu thành công, False nếu lỗi
    """
    PAYLOAD_FILE = get_config_dir() / "payload.txt"
    
    try:
        # Đọc file payload hiện tại
        if not PAYLOAD_FILE.exists():
            print(f"⚠️ File {PAYLOAD_FILE} không tồn tại")
            return False
            
        with PAYLOAD_FILE.open("r", encoding="utf-8") as f:
            lines = f.readlines()
        
        # Cập nhật các giá trị
        updated_lines = []
        for line in lines:
            original_line = line
            
            # Cập nhật av và __user nếu có c_user
            if payload_values.get('c_user'):
                if line.strip().startswith('"av":'):
                    line = f'"av": "{payload_values["c_user"]}",\n'
                elif line.strip().startswith('"__user":'):
                    line = f'"__user": "{payload_values["c_user"]}",\n'
            
            # Cập nhật fb_dtsg
            if payload_values.get('fb_dtsg') and line.strip().startswith('"fb_dtsg":'):
                line = f'"fb_dtsg": "{payload_values["fb_dtsg"]}",\n'
            
            # Cập nhật jazoest
            if payload_values.get('jazoest') and line.strip().startswith('"jazoest":'):
                line = f'"jazoest": "{payload_values["jazoest"]}",\n'
            
            # Cập nhật lsd
            if payload_values.get('lsd') and line.strip().startswith('"lsd":'):
                line = f'"lsd": "{payload_values["lsd"]}",\n'
            
            # Cập nhật __spin_r
            if payload_values.get('spin_r') and line.strip().startswith('"__spin_r":'):
                line = f'"__spin_r": "{payload_values["spin_r"]}",\n'
            
            # Cập nhật __spin_t
            if payload_values.get('spin_t') and line.strip().startswith('"__spin_t":'):
                line = f'"__spin_t": "{payload_values["spin_t"]}",\n'
            
            updated_lines.append(line)
        
        # Ghi lại file
        with PAYLOAD_FILE.open("w", encoding="utf-8") as f:
            f.writelines(updated_lines)
        
        print(f"✅ Đã cập nhật file {PAYLOAD_FILE}")
        return True
        
    except Exception as e:
        print(f"❌ Lỗi khi cập nhật file payload: {e}")
        import traceback
        traceback.print_exc()
        return False


def ensure_payload_from_bad_response(profile_id: str | None, cookie: str | None, response_text: str | None = None, timeout: int = 8):
    """
    Khi gặp response không phải JSON (ví dụ trả về 'for (;;);{...error...}'), cố gắng:
      - Lấy fb_dtsg, lsd từ `response_text` nếu có
      - Nếu không, khởi động headless capture (`capture_graphql_post_payload`) để bắt postData
      - Ghi các giá trị tìm được vào `settings.json` trong PROFILE_IDS[profile_id]
    Trả về dict với các giá trị tìm được hoặc None nếu thất bại.
    """
    try:
        fb_dtsg = None
        lsd = None

        text = response_text or ""
        # Remove facebook XSSI prefix if present
        if isinstance(text, str) and text.startswith("for (;;);"):
            text = text[len("for (;;);"):]

        # Try parse JSON body if possible and extract known fields
        try:
            parsed_json = json.loads(text) if text else {}
            if isinstance(parsed_json, dict):
                # some responses may include tokens under nested structures
                # quick search for common keys
                for k in ("fb_dtsg", "fb_dtsg_token", "fb_dtsg_value"):
                    v = parsed_json.get(k)
                    if v:
                        fb_dtsg = str(v)
                        break
                # lsd may appear as x-fb-lsd or lsd
                for k in ("lsd", "x-fb-lsd"):
                    v = parsed_json.get(k)
                    if v:
                        lsd = str(v)
                        break
        except Exception:
            parsed_json = {}

        # Fallback: regex search in raw text
        if not fb_dtsg and isinstance(text, str):
            fb_patterns = [
                r'"name":"fb_dtsg","value":"([^"]+)"',
                r'"token":"([^"]+)","type":"fb_dtsg"',
                r'"fb_dtsg"\s*:\s*"([^"]+)"',
                r'name="fb_dtsg"\s+value="([^"]+)"',
                r'DTSGInitData.*?"token":"([^"]+)"'
            ]
            for p in fb_patterns:
                m = re.search(p, text)
                if m:
                    fb_dtsg = m.group(1)
                    break

        if not lsd and isinstance(text, str):
            lsd_patterns = [
                r'"LSD",\[\],{"token":"(.*?)"}',
                r'"x-fb-lsd"\s*:\s*"([^"]+)"',
                r'"lsd"\s*:\s*"([^"]+)"'
            ]
            for p in lsd_patterns:
                m = re.search(p, text)
                if m:
                    lsd = m.group(1)
                    break

        # If still not found, attempt headless capture to parse graphql postData
        if not fb_dtsg or not lsd:
            try:
                parsed = capture_graphql_post_payload(cookie, timeout=timeout)
                if isinstance(parsed, dict):
                    if not fb_dtsg:
                        fb_dtsg = parsed.get("fb_dtsg") or parsed.get("fb_dtsg_token") or parsed.get("fb_dtsg_value")
                    if not lsd:
                        lsd = parsed.get("lsd") or parsed.get("x-fb-lsd")
            except Exception as e:
                print(f"⚠️ Headless capture failed: {e}")

        # Persist into settings.json if profile_id provided and we found anything
        if profile_id and (fb_dtsg or lsd):
            try:
                if SETTINGS_JSON_FILE.exists():
                    with SETTINGS_JSON_FILE.open("r", encoding="utf-8") as sf:
                        sdata = json.load(sf)
                else:
                    sdata = {}
                profiles = sdata.get("PROFILE_IDS") or {}
                if not isinstance(profiles, dict):
                    profiles = {}
                profile_cfg = profiles.get(profile_id) or {}
                if not isinstance(profile_cfg, dict):
                    profile_cfg = {}
                if fb_dtsg:
                    profile_cfg["fb_dtsg"] = fb_dtsg
                if lsd:
                    profile_cfg["lsd"] = lsd
                profiles[profile_id] = profile_cfg
                sdata["PROFILE_IDS"] = profiles
                with SETTINGS_JSON_FILE.open("w", encoding="utf-8") as sf:
                    json.dump(sdata, sf, ensure_ascii=False, indent=2)
                print(f"✅ Đã ghi payload values vào {SETTINGS_JSON_FILE} cho profile_id={profile_id}")
            except Exception as e:
                print(f"⚠️ Không thể ghi vào settings.json: {e}")

        result = {"fb_dtsg": fb_dtsg, "lsd": lsd}
        return result
    except Exception as e:
        print(f"❌ ensure_payload_from_bad_response failed: {e}")
        return None
if __name__ == "__main__":
    # Ví dụ sử dụng với profile_id
    profile_id = "b77da63d-af55-43c2-ab7f-364250b20e30"
    payload_dict = get_payload_by_profile_id(profile_id)
    
    if payload_dict:
        print(f"\n📋 Payload dictionary đã tạo thành công!")
        print(f"   Số lượng keys: {len(payload_dict)}")
        print(f"   Sample keys: {list(payload_dict.keys())[:5]}")
    else:
        print(f"\n❌ Không thể tạo payload dictionary")

