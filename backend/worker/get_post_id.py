import requests
import json
import re
from urllib.parse import urlencode, urlparse, parse_qs

# ====== ĐỌC COOKIE TỪ FILE ======
COOKIE_FILE = "backend/config/cookies.txt"
try:
    with open(COOKIE_FILE, "r", encoding="utf-8") as f:
        COOKIE = f.read().strip()
    # Loại bỏ ký tự xuống dòng và khoảng trắng thừa
    COOKIE = " ".join(COOKIE.split())
    print(f"✅ Đã đọc cookie từ {COOKIE_FILE}")
except FileNotFoundError:
    print(f"❌ Không tìm thấy file {COOKIE_FILE}!")
    print(f"Vui lòng tạo file {COOKIE_FILE} và thêm cookie vào đó.")
    exit(1)
except Exception as e:
    print(f"❌ Lỗi khi đọc {COOKIE_FILE}: {e}")
    exit(1)

# ====== HEADERS TỪ REQUEST ======
HEADERS = {
    "accept": "*/*",
    "accept-encoding": "gzip, deflate, br",  # Loại bỏ zstd vì requests không hỗ trợ tự động
    "accept-language": "en,vi;q=0.9,en-US;q=0.8",
    "content-type": "application/x-www-form-urlencoded",
    "cookie": COOKIE,
    "origin": "https://www.facebook.com",
    "priority": "u=1, i",
    "referer": "https://www.facebook.com/photo/?fbid=965661036626847&set=a.777896542069965",
    "sec-ch-ua": '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
    "x-asbd-id": "359341",
    "x-fb-friendly-name": "CometUFIReactionsCountTooltipContentQuery",
    "x-fb-lsd": "OdWgrzyRzfrz5zMIFQOfKy"
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)

# ====== ĐỌC PAYLOAD TỪ FILE ======
PAYLOAD_FILE = "backend/config/payload.txt"
def load_payload_from_file():
    """
    Đọc payload từ file payload.txt và trả về dictionary
    
    Returns:
        dict: Payload dictionary từ file
    """
    try:
        with open(PAYLOAD_FILE, "r", encoding="utf-8") as f:
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
                # Loại bỏ tất cả dấu ngoặc kép, dấu nháy đơn và dấu phẩy
                key = parts[0].strip().replace('"', '').replace("'", '')
                value = parts[1].strip().replace('"', '').replace("'", '').rstrip(',').strip()
                if key and value:  # Chỉ thêm nếu cả key và value đều không rỗng
                    payload_dict[key] = value
        
        print(f"✅ Đã đọc payload từ {PAYLOAD_FILE}")
        return payload_dict
    except FileNotFoundError:
        print(f"❌ Không tìm thấy file {PAYLOAD_FILE}!")
        print(f"Vui lòng tạo file {PAYLOAD_FILE} và thêm payload vào đó.")
        exit(1)
    except Exception as e:
        print(f"❌ Lỗi khi đọc {PAYLOAD_FILE}: {e}")
        exit(1)

# Load payload một lần khi import module
BASE_PAYLOAD = load_payload_from_file()


# ================================
#   HÀM GỌI API VỚI URL VIDEO
# ================================
def get_post_id(video_url):
    """
    Gọi API với URL video để lấy post_id
    
    Args:
        video_url (str): URL của video Facebook (ví dụ: "https://www.facebook.com/reel/1525194028720314/")
        
    Returns:
        str: post_id hoặc None nếu không tìm thấy
    """
    url = "https://www.facebook.com/api/graphql/"
    
    variables = {
        "url": video_url
    }
    
    # Đọc payload từ file và thêm variables, doc_id
    payload_dict = BASE_PAYLOAD.copy()
    payload_dict["variables"] = json.dumps(variables, ensure_ascii=False)
    payload_dict["doc_id"] = "9840669832713841"
    
    # Chuyển dictionary thành form-urlencoded string
    payload = urlencode(payload_dict)
    
    print(f"\n🚀 Gọi API với URL video: {video_url}")
    print(f"📋 Variables: {json.dumps(variables, ensure_ascii=False)}")

    # Gửi request
    response = SESSION.post(url, data=payload)
    
    print(f"📊 Status Code: {response.status_code}")
    
    if response.status_code != 200:
        print(f"❌ Lỗi: Status code {response.status_code}")
        print(f"Response text: {response.text[:500]}")
        return None
    
    # Parse và lấy post_id
    try:
        response_json = response.json()
        
        # Lấy post_id từ response
        post_id = response_json.get("data", {}).get("xma_preview_data", {}).get("post_id")
        
        if post_id:
            print(f"✅ Post ID: {post_id}")
            return post_id
        else:
            print(f"⚠️ Không tìm thấy post_id trong response, thử fallback sang view-source...")
            # Fallback: Tìm post_id trong HTML source
            return get_post_id_from_html(video_url)
            
    except json.JSONDecodeError as e:
        print(f"❌ Lỗi: Response không phải JSON hợp lệ")
        print(f"Response text (500 ký tự đầu): {response.text[:500]}")
        print(f"Chi tiết lỗi: {e}")
        return None
    except Exception as e:
        print(f"❌ Lỗi khi parse response: {e}")
        return None


def get_post_id_from_html(url):
    """
    Fallback: Lấy post_id từ HTML source của trang (view-source)
    
    Args:
        url (str): URL của Facebook post
        
    Returns:
        str: post_id đầu tiên tìm thấy hoặc None
    """
    print(f"\n🔄 Fallback: Đang lấy HTML source (view-source) từ: {url}")
    
    try:
        # Headers cho GET request (khác với POST)
        get_headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "accept-encoding": "gzip, deflate, br",
            "accept-language": "en,vi;q=0.9,en-US;q=0.8",
            "cookie": COOKIE,
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
        
        # Lấy HTML source với cookies
        response = SESSION.get(url, headers=get_headers)
        
        if response.status_code != 200:
            print(f"❌ Lỗi: Status code {response.status_code}")
            return None
        
        html_content = response.text
        print(f"📄 Đã lấy HTML source ({len(html_content)} ký tự)")
        
        # Tìm post_id bằng các pattern phổ biến
        post_id_patterns = [
            r'"post_id"\s*:\s*"(\d+)"',  # "post_id": "123456789"
            r'"fbid"\s*:\s*"(\d+)"',     # "fbid": "123456789"
            r'"pfbid"\s*:\s*"(\d+)"',    # "pfbid": "123456789"
            r'fbid=(\d+)',                # fbid=123456789
            r'post_id=(\d+)',             # post_id=123456789
            r'/posts/(\d+)',              # /posts/123456789
            r'/photo/\?fbid=(\d+)',       # /photo/?fbid=123456789
            r'"legacy_fbid"\s*:\s*"(\d+)"',  # "legacy_fbid": "123456789"
            r'data-post-id="(\d+)"',      # data-post-id="123456789"
            r'post_id["\']\s*:\s*["\']?(\d+)',  # post_id: "123456789"
        ]
        
        found_ids = []
        for pattern in post_id_patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            if matches:
                found_ids.extend(matches)
                print(f"   🔍 Tìm thấy {len(matches)} post_id(s) với pattern: {pattern[:30]}...")
        
        if found_ids:
            # Lấy post_id đầu tiên (thường là post_id chính)
            post_id = found_ids[0]
            print(f"✅ Tìm thấy post_id từ HTML: {post_id}")
            print(f"   📋 Tổng số post_id tìm thấy: {len(set(found_ids))} (unique)")
            return post_id
        else:
            print(f"⚠️ Không tìm thấy post_id trong HTML source")
            # Lưu HTML để debug
            with open("html_source_debug.html", "w", encoding="utf-8") as f:
                f.write(html_content)
            print(f"   💾 Đã lưu HTML source vào html_source_debug.html để debug")
            return None
            
    except Exception as e:
        print(f"❌ Lỗi khi lấy HTML source: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    # Ví dụ sử dụng hàm get_post_id
    video_url = "https://www.facebook.com/share/p/1BvHoT8PUU/"
    post_id = get_post_id(video_url)
    if post_id:
        print(f"\n✅ Post ID đã lấy được: {post_id}")

