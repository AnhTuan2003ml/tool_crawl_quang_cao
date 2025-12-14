import requests
import re
import json

# ====== ĐƯỜNG DẪN ======
COOKIES_JSON_FILE = "backend/config/cookies.json"
PAYLOAD_TXT_FILE = "backend/config/payload.txt"


def get_cookies_by_profile_id(profile_id):
    """
    Lấy cookies từ cookies.json dựa trên profile_id
    
    Args:
        profile_id (str): Profile ID (ví dụ: "031ca13d-e8fa-400c-a603-df57a2806788")
    
    Returns:
        str: Cookie string hoặc None nếu không tìm thấy
    """
    try:
        with open(COOKIES_JSON_FILE, "r", encoding="utf-8") as f:
            cookies_data = json.load(f)
        
        if profile_id in cookies_data:
            cookie = cookies_data[profile_id].strip()
            # Loại bỏ ký tự xuống dòng và khoảng trắng thừa
            cookie = " ".join(cookie.split())
            print(f"✅ Đã lấy cookie từ profile_id: {profile_id}")
            return cookie
        else:
            print(f"❌ Không tìm thấy profile_id '{profile_id}' trong {COOKIES_JSON_FILE}")
            print(f"   Các profile_id có sẵn: {list(cookies_data.keys())}")
            return None
    except FileNotFoundError:
        print(f"❌ Không tìm thấy file {COOKIES_JSON_FILE}!")
        return None
    except Exception as e:
        print(f"❌ Lỗi khi đọc {COOKIES_JSON_FILE}: {e}")
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
        "accept-encoding": "gzip, deflate, br",
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


def get_fb_dtsg(cookie):
    """
    Lấy fb_dtsg từ Facebook.com
    
    Args:
        cookie (str): Cookie string để sử dụng
    
    Returns:
        str: Giá trị fb_dtsg hoặc None nếu không tìm thấy
    """
    url = "https://www.facebook.com"
    
    print(f"\n🚀 Đang GET request từ: {url}")
    
    try:
        # Tạo headers với cookie
        headers = get_base_headers(cookie)
        
        # GET request với cookies và headers
        response = requests.get(url, headers=headers)
        
        print(f"📊 Status Code: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ Lỗi: Status code {response.status_code}")
            print(f"Response text: {response.text[:500]}")
            return None
        
        html_content = response.text
        print(f"📄 Đã lấy HTML content ({len(html_content)} ký tự)")
        
        # Danh sách các pattern để tìm fb_dtsg
        patterns = [
            r'"name":"fb_dtsg","value":"([^"]+)"',      # Pattern gốc
            r'"token":"([^"]+)","type":"fb_dtsg"',       # Token với type fb_dtsg
            r'"fb_dtsg"\s*:\s*"([^"]+)"',               # "fb_dtsg": "value"
            r'name="fb_dtsg"\s+value="([^"]+)"',        # name="fb_dtsg" value="value"
            r'DTSGInitData.*?"token":"([^"]+)"'          # DTSGInitData với token
        ]
        
        # Thử từng pattern
        for i, pattern in enumerate(patterns, 1):
            match = re.search(pattern, html_content)
            if match:
                fb_dtsg = match.group(1)
                print(f"✅ Tìm thấy fb_dtsg với pattern {i}: {fb_dtsg[:50]}...")
                return fb_dtsg
        
        # Không tìm thấy với bất kỳ pattern nào
        print(f"⚠️ Không tìm thấy fb_dtsg với {len(patterns)} patterns")
        return None
            
    except Exception as e:
        print(f"❌ Lỗi khi lấy fb_dtsg: {e}")
        import traceback
        traceback.print_exc()
        return None


def get_all_payload_values(cookie):
    """
    Lấy tất cả các giá trị payload từ Facebook.com
    
    Args:
        cookie (str): Cookie string để sử dụng
    
    Returns:
        dict: Dictionary chứa c_user, av, __user, fb_dtsg, jazoest, lsd, spin_r, spin_t hoặc None nếu lỗi
    """
    url = "https://www.facebook.com"
    
    print(f"\n🚀 Đang GET request từ: {url}")
    
    try:
        # Lấy c_user từ cookie
        c_user = get_c_user(cookie)
        if c_user:
            print(f"✅ Tìm thấy c_user: {c_user}")
        else:
            print(f"⚠️ Không tìm thấy c_user trong cookie")
        
        # Tạo headers với cookie
        headers = get_base_headers(cookie)
        
        # GET request với cookies và headers
        response = requests.get(url, headers=headers)
        
        print(f"📊 Status Code: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ Lỗi: Status code {response.status_code}")
            print(f"Response text: {response.text[:500]}")
            return None
        
        html_content = response.text
        print(f"📄 Đã lấy HTML content ({len(html_content)} ký tự)")
        
        # Lấy fb_dtsg
        patterns = [
            r'"name":"fb_dtsg","value":"([^"]+)"',      # Pattern gốc
            r'"token":"([^"]+)","type":"fb_dtsg"',       # Token với type fb_dtsg
            r'"fb_dtsg"\s*:\s*"([^"]+)"',               # "fb_dtsg": "value"
            r'name="fb_dtsg"\s+value="([^"]+)"',        # name="fb_dtsg" value="value"
            r'DTSGInitData.*?"token":"([^"]+)"'          # DTSGInitData với token
        ]
        
        fb_dtsg = None
        for i, pattern in enumerate(patterns, 1):
            match = re.search(pattern, html_content)
            if match:
                fb_dtsg = match.group(1)
                print(f"✅ Tìm thấy fb_dtsg với pattern {i}: {fb_dtsg[:50]}...")
                break
        
        if not fb_dtsg:
            print(f"⚠️ Không tìm thấy fb_dtsg với {len(patterns)} patterns")
            return None
        
        # Tính jazoest từ fb_dtsg
        jazoest = get_jazoest(fb_dtsg)
        print(f"✅ Tính được jazoest: {jazoest}")
        
        # Lấy lsd
        lsd = get_lsd(html_content)
        if lsd:
            print(f"✅ Tìm thấy lsd: {lsd[:30]}...")
        else:
            print(f"⚠️ Không tìm thấy lsd")
        
        # Lấy spin_r
        spin_r = get_spin_r(html_content)
        if spin_r:
            print(f"✅ Tìm thấy __spin_r: {spin_r}")
        else:
            print(f"⚠️ Không tìm thấy __spin_r")
        
        # Lấy spin_t
        spin_t = get_spin_t(html_content)
        if spin_t:
            print(f"✅ Tìm thấy __spin_t: {spin_t}")
        else:
            print(f"⚠️ Không tìm thấy __spin_t")
        
        result = {
            "c_user": c_user,
            "av": c_user,  # av giống với c_user
            "__user": c_user,  # __user giống với c_user
            "fb_dtsg": fb_dtsg,
            "jazoest": jazoest,
            "lsd": lsd,
            "spin_r": spin_r,
            "spin_t": spin_t
        }
        
        return result
            
    except Exception as e:
        print(f"❌ Lỗi khi lấy payload values: {e}")
        import traceback
        traceback.print_exc()
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
    
    # Lấy payload values từ Facebook
    payload_values = get_all_payload_values(cookie)
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

