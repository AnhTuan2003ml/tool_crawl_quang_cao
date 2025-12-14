import requests
import json
import re
from urllib.parse import urlencode, urlparse, parse_qs

# ====== LƯU Ý ======
# Cookies và payload được lấy từ cookies.json và payload.txt thông qua profile_id
# cookies.json có cấu trúc: {"profile_id": {"cookie": "...", "access_token": "..."}}
# Sử dụng get_payload.get_payload_by_profile_id(profile_id) để lấy payload
# Sử dụng get_payload.get_cookies_by_profile_id(profile_id) để lấy cookie


# ================================
#   HÀM GỌI API VỚI URL VIDEO
# ================================
def get_post_id(video_url, profile_id):
    """
    Gọi API với URL video để lấy post_id
    
    Args:
        video_url (str): URL của video Facebook (ví dụ: "https://www.facebook.com/reel/1525194028720314/")
        profile_id (str): Profile ID để lấy cookies và payload
        
    Returns:
        str: post_id hoặc None nếu không tìm thấy
    """
    from get_payload import get_payload_by_profile_id, get_cookies_by_profile_id
    
    # Lấy payload và cookies từ profile_id
    payload_dict = get_payload_by_profile_id(profile_id)
    if not payload_dict:
        print(f"❌ Không thể lấy payload từ profile_id: {profile_id}")
        return None
    
    cookies = get_cookies_by_profile_id(profile_id)
    if not cookies:
        print(f"❌ Không thể lấy cookies từ profile_id: {profile_id}")
        return None
    
    url = "https://www.facebook.com/api/graphql/"
    
    variables = {
        "url": video_url
    }
    
    # Sử dụng payload và thêm variables, doc_id
    payload_dict = payload_dict.copy()
    payload_dict["variables"] = json.dumps(variables, ensure_ascii=False)
    payload_dict["doc_id"] = "9840669832713841"
    
    # Chuyển dictionary thành form-urlencoded string
    payload = urlencode(payload_dict)
    
    # Tạo headers với cookies
    headers = {
        "accept": "*/*",
        "accept-encoding": "gzip, deflate, br",
        "accept-language": "en,vi;q=0.9,en-US;q=0.8",
        "content-type": "application/x-www-form-urlencoded",
        "cookie": cookies,
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
        "x-fb-lsd": payload_dict.get("lsd", "")
    }
    
    print(f"\n🚀 Gọi API với URL video: {video_url}")
    print(f"📋 Variables: {json.dumps(variables, ensure_ascii=False)}")

    # Gửi request
    response = requests.post(url, data=payload, headers=headers)
    
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
            return get_post_id_from_html(video_url, profile_id)
            
    except json.JSONDecodeError as e:
        print(f"❌ Lỗi: Response không phải JSON hợp lệ")
        print(f"Response text (500 ký tự đầu): {response.text[:500]}")
        print(f"Chi tiết lỗi: {e}")
        return None
    except Exception as e:
        print(f"❌ Lỗi khi parse response: {e}")
        return None


def get_post_id_from_html(url, profile_id):
    """
    Fallback: Lấy post_id từ HTML source của trang (view-source)
    
    Args:
        url (str): URL của Facebook post
        profile_id (str): Profile ID để lấy cookies
        
    Returns:
        str: post_id đầu tiên tìm thấy hoặc None
    """
    from get_payload import get_cookies_by_profile_id
    
    # Lấy cookies từ profile_id
    cookies = get_cookies_by_profile_id(profile_id)
    if not cookies:
        print(f"❌ Không thể lấy cookies từ profile_id: {profile_id}")
        return None
    
    print(f"\n🔄 Fallback: Đang lấy HTML source (view-source) từ: {url}")
    
    try:
        # Headers cho GET request (khác với POST)
        get_headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "accept-encoding": "gzip, deflate, br",
            "accept-language": "en,vi;q=0.9,en-US;q=0.8",
            "cookie": cookies,
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
        response = requests.get(url, headers=get_headers)
        
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


def get_page_id_from_html(url, profile_id):
    """
    Lấy page_id từ HTML source của trang (view-source)
    
    Args:
        url (str): URL của Facebook page/group
        profile_id (str): Profile ID để lấy cookies
        
    Returns:
        str: page_id đầu tiên tìm thấy hoặc None
    """
    from get_payload import get_cookies_by_profile_id
    
    # Lấy cookies từ profile_id
    cookies = get_cookies_by_profile_id(profile_id)
    if not cookies:
        print(f"❌ Không thể lấy cookies từ profile_id: {profile_id}")
        return None
    
    print(f"\n🔄 Đang lấy HTML source (view-source) từ: {url}")
    
    try:
        # Headers cho GET request
        get_headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "accept-encoding": "gzip, deflate, br",
            "accept-language": "en,vi;q=0.9,en-US;q=0.8",
            "cookie": cookies,
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
        response = requests.get(url, headers=get_headers)
        
        if response.status_code != 200:
            print(f"❌ Lỗi: Status code {response.status_code}")
            return None
        
        html_content = response.text
        print(f"📄 Đã lấy HTML source ({len(html_content)} ký tự)")
        
        # Tìm page_id bằng các pattern phổ biến
        page_id_patterns = [
            r'"page_id"\s*:\s*"(\d+)"',  # "page_id": "987870664956102"
            r'page_id["\']\s*:\s*["\'](\d+)',  # page_id: "987870664956102"
            r'/groups/(\d+)',  # /groups/987870664956102
            r'/pages/(\d+)',  # /pages/987870664956102
            r'page_id=(\d+)',  # page_id=987870664956102
            r'data-page-id="(\d+)"',  # data-page-id="987870664956102"
            r'"pageID"\s*:\s*"(\d+)"',  # "pageID": "987870664956102"
        ]
        
        found_ids = []
        for pattern in page_id_patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            if matches:
                found_ids.extend(matches)
                print(f"   🔍 Tìm thấy {len(matches)} page_id(s) với pattern: {pattern[:50]}...")
        
        # Tìm trong JSON structure như ví dụ: {"987870664956102":{"page_id":"987870664956102","page_id_type":"group"
        # Pattern 1: Lấy từ key của JSON object
        json_key_pattern = r'{"(\d+)":\s*{"page_id"\s*:\s*"(\d+)"'
        json_matches = re.findall(json_key_pattern, html_content)
        if json_matches:
            for match in json_matches:
                # Lấy cả key (thường là page_id) và value
                found_ids.append(match[0])  # Key từ JSON
                found_ids.append(match[1])  # Value từ page_id field
            print(f"   🔍 Tìm thấy {len(json_matches)} page_id(s) trong JSON structure (key pattern)")
        
        # Pattern 2: Tìm trực tiếp trong JSON với page_id_type
        json_with_type_pattern = r'"page_id"\s*:\s*"(\d+)"\s*,\s*"page_id_type"\s*:\s*"[^"]*"'
        json_type_matches = re.findall(json_with_type_pattern, html_content)
        if json_type_matches:
            found_ids.extend(json_type_matches)
            print(f"   🔍 Tìm thấy {len(json_type_matches)} page_id(s) với page_id_type")
        
        # Pattern 3: Tìm trong structure phức tạp hơn (có thể có nhiều fields giữa)
        complex_json_pattern = r'{"(\d+)":\s*{[^}]*"page_id"\s*:\s*"(\d+)"'
        complex_matches = re.findall(complex_json_pattern, html_content)
        if complex_matches:
            for match in complex_matches:
                found_ids.append(match[0])  # Key
                found_ids.append(match[1])  # page_id value
            print(f"   🔍 Tìm thấy {len(complex_matches)} page_id(s) trong complex JSON structure")
        
        if found_ids:
            # Lấy page_id đầu tiên (thường là page_id chính)
            page_id = found_ids[0]
            print(f"✅ Tìm thấy page_id từ HTML: {page_id}")
            print(f"   📋 Tổng số page_id tìm thấy: {len(set(found_ids))} (unique)")
            if len(set(found_ids)) > 1:
                print(f"   📋 Các page_id tìm thấy: {list(set(found_ids))[:5]}")
            return page_id
        else:
            print(f"⚠️ Không tìm thấy page_id trong HTML source")
            # Lưu HTML để debug
            with open("html_source_page_id_debug.html", "w", encoding="utf-8") as f:
                f.write(html_content)
            print(f"   💾 Đã lưu HTML source vào html_source_page_id_debug.html để debug")
            return None
            
    except Exception as e:
        print(f"❌ Lỗi khi lấy HTML source: {e}")
        import traceback
        traceback.print_exc()
        return None


def get_id_from_url(url, profile_id):
    """
    Hàm tổng hợp tự động phát hiện loại URL và lấy page_id hoặc post_id tương ứng
    
    Logic:
    - Nếu URL chứa /groups/ hoặc /pages/ → chỉ lấy page_id
    - Nếu URL là post/video/reel → lấy cả post_id và page_id
    
    Args:
        url (str): URL của Facebook (có thể là group, page, post, video, reel, ...)
        profile_id (str): Profile ID để lấy cookies và payload
        
    Returns:
        dict: {
            "page_id": str hoặc None,
            "post_id": str hoặc None,
            "url_type": str ("group", "page", "post", "video", "reel", "unknown")
        }
    """
    url_lower = url.lower()
    result = {
        "page_id": None,
        "post_id": None,
        "url_type": "unknown"
    }
    
    # Phát hiện loại URL
    if "/groups/" in url_lower:
        result["url_type"] = "group"
        page_id = get_page_id_from_html(url, profile_id)
        result["page_id"] = page_id
        if page_id:
            print(f"page_id: {page_id}")
        return result
        
    elif "/pages/" in url_lower:
        result["url_type"] = "page"
        page_id = get_page_id_from_html(url, profile_id)
        result["page_id"] = page_id
        if page_id:
            print(f"page_id: {page_id}")
        return result
        
    elif any(keyword in url_lower for keyword in ["/reel/", "/video/", "/watch/", "/share/v/", "/photo/", "/posts/", "/permalink/"]):
        result["url_type"] = "post"
        # Lấy post_id
        post_id = get_post_id(url, profile_id)
        result["post_id"] = post_id
        
        # Lấy cả page_id từ HTML source của post
        page_id = get_page_id_from_html(url, profile_id)
        result["page_id"] = page_id
        
        # In kết quả
        if post_id:
            print(f"post_id: {post_id}")
        if page_id:
            print(f"page_id: {page_id}")
        return result
        
    else:
        # URL không rõ ràng, thử cả hai
        result["url_type"] = "unknown"
        
        # Thử lấy page_id trước
        page_id = get_page_id_from_html(url, profile_id)
        result["page_id"] = page_id
        
        # Thử lấy post_id
        post_id = get_post_id(url, profile_id)
        result["post_id"] = post_id
        
        # In kết quả
        if page_id:
            print(f"page_id: {page_id}")
        if post_id:
            print(f"post_id: {post_id}")
        
        return result


if __name__ == "__main__":
    # Ví dụ sử dụng hàm get_id_from_url (tổng hợp)
    profile_id = "031ca13d-e8fa-400c-a603-df57a2806788"
    
    # Test với group URL
    group_url = "https://www.facebook.com/groups/987870664956102/"
    result = get_id_from_url(group_url, profile_id)
    print(f"\n📊 Kết quả:")
    print(f"   URL Type: {result['url_type']}")
    print(f"   Page ID: {result['page_id']}")
    print(f"   Post ID: {result['post_id']}")
    
    # Test với video/post URL
    video_url = "https://www.facebook.com/share/v/17qwV639vQ/?mibextid=wwXIfr"
    result = get_id_from_url(video_url, profile_id)
    print(f"\n📊 Kết quả:")
    print(f"   URL Type: {result['url_type']}")
    print(f"   Page ID: {result['page_id']}")
    print(f"   Post ID: {result['post_id']}")