import requests
import re
import json
import time
from urllib.parse import parse_qs, unquote_plus
from pathlib import Path

# ====== ĐƯỜNG DẪN THEO PROJECT ROOT ======
BASE_DIR = Path(__file__).resolve().parents[2]  # Thư mục gốc project
SETTINGS_JSON_FILE = BASE_DIR / "backend" / "config" / "settings.json"
PAYLOAD_TXT_FILE = BASE_DIR / "backend" / "config" / "payload.txt"


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
        with open(SETTINGS_JSON_FILE, "r", encoding="utf-8") as f:
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
    Lấy fb_dtsg từ Facebook.com
    
    Args:
        cookie (str): Cookie string để sử dụng
    
    Returns:
        str: Giá trị fb_dtsg hoặc None nếu không tìm thấy
    """
    url = "https://www.facebook.com"

    print(f"\n🚀 Bắt đầu headless capture từ: {url} (CHỈ DÙNG Selenium/WebDriver)")

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

    # Require Selenium + webdriver-manager; fail loudly if unavailable
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from selenium.common.exceptions import WebDriverException
        from webdriver_manager.chrome import ChromeDriverManager
    except Exception as e:
        print(f"❌ Selenium or webdriver_manager not available: {e}")
        return None

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1200,800")
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
    except WebDriverException as e:
        print(f"❌ Không thể khởi tạo Chrome WebDriver: {e}")
        return None
    except Exception as e:
        print(f"❌ Lỗi khi cài/chạy ChromeDriver: {e}")
        return None

    try:
        try:
            driver.execute_cdp_cmd("Network.enable", {})
            driver.execute_cdp_cmd("Network.setExtraHTTPHeaders", {"headers": {"cookie": cookie}})
        except Exception:
            pass

        driver.get(url)
        time.sleep(3)

        fb_dtsg = None
        try:
            logs = driver.get_log("performance")
        except Exception:
            logs = []

        for entry in logs:
            try:
                msg = json.loads(entry.get("message", "{}")).get("message", {})
                method = msg.get("method", "")
                params = msg.get("params", {}) or {}
                if method in ("Network.requestWillBeSent", "Network.responseReceived"):
                    req = params.get("request") or params.get("response") or {}
                    url_req = req.get("url") or ""
                    if "api/graphql" in url_req:
                        postData = req.get("postData") or params.get("request", {}).get("postData", "") or ""
                        if postData:
                            m = re.search(r'fb_dtsg["\\\']?\\s*[:=]\\s*["\\\']([^"\\\']+)', postData)
                            if not m:
                                m = re.search(r'fb_dtsg=([^&"\\\']+)', postData)
                            if m:
                                fb_dtsg = m.group(1)
                                print(f"✅ Bắt được fb_dtsg từ graphql postData: {fb_dtsg[:50]}...")
                                break
            except Exception:
                continue

        if not fb_dtsg:
            # last resort: search in rendered page source (still within headless mode)
            html_content = driver.page_source or ""
            patterns = [
                r'"name":"fb_dtsg","value":"([^"]+)"',
                r'"token":"([^"]+)","type":"fb_dtsg"',
                r'"fb_dtsg"\\s*:\\s*"([^"]+)"',
                r'name="fb_dtsg"\\s+value="([^"]+)"',
                r'DTSGInitData.*?"token":"([^"]+)"'
            ]
            for i, pattern in enumerate(patterns, 1):
                match = re.search(pattern, html_content)
                if match:
                    fb_dtsg = match.group(1)
                    print(f"✅ Tìm thấy fb_dtsg trong page_source với pattern {i}: {fb_dtsg[:50]}...")
                    break

        if return_page_source:
            try:
                page_source = driver.page_source or ""
            except Exception:
                page_source = ""
            return fb_dtsg, page_source
        return fb_dtsg
    finally:
        try:
            driver.quit()
        except Exception:
            pass


def capture_graphql_post_payloads(cookie, timeout: int = 6, first_only: bool = True):
    """
    Dùng headless Chrome (CDP performance logs) để bắt các request POST tới /api/graphql/
    Trả về danh sách dict chứa: url, request_id, post_data (raw string), parsed (dict)
    Chỉ trả các request có response status == 200.
    """
    url = "https://www.facebook.com"

    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from selenium.common.exceptions import WebDriverException
        from webdriver_manager.chrome import ChromeDriverManager
    except Exception as e:
        print(f"❌ Selenium/webdriver_manager unavailable: {e}")
        return []

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1200,800")
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
    except Exception as e:
        print(f"❌ Cannot start ChromeDriver: {e}")
        return []

    try:
        try:
            driver.execute_cdp_cmd("Network.enable", {})
            driver.execute_cdp_cmd("Network.setExtraHTTPHeaders", {"headers": {"cookie": cookie}})
        except Exception:
            pass

        driver.get(url)
        # allow network activity
        time.sleep(max(2, timeout))

        try:
            logs = driver.get_log("performance")
        except Exception:
            logs = []

        requests_map = {}
        responses_map = {}

        for entry in logs:
            try:
                msg = json.loads(entry.get("message", "{}")).get("message", {})
                method = msg.get("method", "")
                params = msg.get("params", {}) or {}
                request_id = params.get("requestId")

                if method == "Network.requestWillBeSent":
                    req = params.get("request", {}) or {}
                    url_req = req.get("url", "")
                    meth = req.get("method", "").upper()
                    if "/api/graphql" in url_req and meth == "POST":
                        requests_map[request_id] = {
                            "url": url_req,
                            "postData": req.get("postData", ""),
                            "headers": req.get("headers", {})
                        }

                elif method == "Network.responseReceived":
                    resp = params.get("response", {}) or {}
                    status = resp.get("status")
                    responses_map[request_id] = status
            except Exception:
                continue

        results = []
        for req_id, req_info in requests_map.items():
            status = responses_map.get(req_id)
            if status != 200:
                continue
            raw_post = req_info.get("postData", "") or ""
            # postData may be urlencoded form; parse it
            parsed_qs = parse_qs(raw_post, keep_blank_values=True)
            # flatten values to single string
            parsed = {k: (v[0] if isinstance(v, list) and len(v) > 0 else "") for k, v in parsed_qs.items()}
            # also decode pluses for safety
            parsed = {k: unquote_plus(v) if isinstance(v, str) else v for k, v in parsed.items()}

            results.append({
                "request_id": req_id,
                "url": req_info.get("url"),
                "raw_post_data": raw_post,
                "parsed": parsed,
                "status": status,
                "headers": req_info.get("headers", {})
            })

            if first_only and results:
                break

        if not results:
            print("⚠️ Không bắt được POST /api/graphql/ với status 200 trong khoảng thời gian này.")
        else:
            print(f"✅ Bắt được {len(results)} POST /api/graphql/ (status=200).")

        return results
    finally:
        try:
            driver.quit()
        except Exception:
            pass


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
                            with open(SETTINGS_JSON_FILE, "r", encoding="utf-8") as sf:
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
                        with open(SETTINGS_JSON_FILE, "w", encoding="utf-8") as sf:
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
    Dùng headless Selenium + performance logs để bắt POST requests tới /api/graphql/
    Trả về dictionary từ postData (form-urlencoded) của request đầu tìm được.

    Args:
        cookie (str): Cookie string để inject
        timeout (int): Số giây chờ sau khi load trang để thu logs

    Returns:
        dict | None: parsed payload (string->string) hoặc None nếu không tìm thấy
    """
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from selenium.common.exceptions import WebDriverException
        from webdriver_manager.chrome import ChromeDriverManager
        from urllib.parse import parse_qs, unquote_plus
    except Exception as e:
        print(f"❌ Selenium/webdriver_manager hoặc urllib không có: {e}")
        return None

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1200,800")
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
    except WebDriverException as e:
        print(f"❌ Không thể khởi tạo Chrome WebDriver: {e}")
        return None
    except Exception as e:
        print(f"❌ Lỗi khi cài/chạy ChromeDriver: {e}")
        return None

    try:
        try:
            driver.execute_cdp_cmd("Network.enable", {})
            driver.execute_cdp_cmd("Network.setExtraHTTPHeaders", {"headers": {"cookie": cookie}})
        except Exception:
            pass

        driver.get("https://www.facebook.com")
        time.sleep(timeout)

        try:
            logs = driver.get_log("performance")
        except Exception:
            logs = []

        for entry in logs:
            try:
                msg = json.loads(entry.get("message", "{}")).get("message", {})
                method = msg.get("method", "")
                params = msg.get("params", {}) or {}
                # requestWillBeSent contains request with postData
                if method == "Network.requestWillBeSent":
                    req = params.get("request", {}) or {}
                    url_req = req.get("url", "") or ""
                    postData = req.get("postData", "") or ""
                    if "/api/graphql" in url_req and postData:
                        # postData is form-urlencoded string; parse it
                        try:
                            parsed = parse_qs(postData, keep_blank_values=True)
                            # flatten values: take first value and url-decode
                            flat = {k: unquote_plus(v[0]) if isinstance(v, list) and v else (v if isinstance(v, str) else "") for k, v in parsed.items()}
                            print(f"✅ Bắt được graphql POST tại {url_req}, keys: {list(flat.keys())}")
                            return flat
                        except Exception as e:
                            print(f"⚠️ Lỗi khi parse postData: {e}")
                            # try manual parse fallback
                            try:
                                parts = postData.split("&")
                                flat = {}
                                for p in parts:
                                    if "=" in p:
                                        k, v = p.split("=", 1)
                                        flat[k] = unquote_plus(v)
                                if flat:
                                    print(f"✅ Bắt được graphql POST (manual parse), keys: {list(flat.keys())}")
                                    return flat
                            except Exception:
                                pass
                # also consider Network.responseReceived -> might include requestId, skip for now
            except Exception:
                continue

        print("⚠️ Không tìm thấy POST tới /api/graphql/ trong performance logs")
        return None
    finally:
        try:
            driver.quit()
        except Exception:
            pass


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
        with open(PAYLOAD_TXT_FILE, "r", encoding="utf-8") as f:
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
    PAYLOAD_FILE = "backend/config/payload.txt"
    
    try:
        # Đọc file payload hiện tại
        with open(PAYLOAD_FILE, "r", encoding="utf-8") as f:
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
        with open(PAYLOAD_FILE, "w", encoding="utf-8") as f:
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
                    with open(SETTINGS_JSON_FILE, "r", encoding="utf-8") as sf:
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
                with open(SETTINGS_JSON_FILE, "w", encoding="utf-8") as sf:
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
    profile_id = "031ca13d-e8fa-400c-a603-df57a2806788"
    payload_dict = get_payload_by_profile_id(profile_id)
    
    if payload_dict:
        print(f"\n📋 Payload dictionary đã tạo thành công!")
        print(f"   Số lượng keys: {len(payload_dict)}")
        print(f"   Sample keys: {list(payload_dict.keys())[:5]}")
    else:
        print(f"\n❌ Không thể tạo payload dictionary")

