import requests
import json
import re
import codecs
from urllib.parse import urlencode, urlparse, parse_qs

# ====== LƯU Ý ======
# Cookies và payload được lấy từ cookies.json và payload.txt thông qua profile_id
# cookies.json có cấu trúc: {"profile_id": {"cookie": "...", "access_token": "..."}}
# Sử dụng get_payload.get_payload_by_profile_id(profile_id) để lấy payload
# Sử dụng get_payload.get_cookies_by_profile_id(profile_id) để lấy cookie


# ================================
#   HÀM GỌI API VỚI URL VIDEO
# ================================
def get_post_id(video_url, profile_id, payload_dict=None, cookies=None):
    """
    Gọi API với URL video để lấy post_id
    
    Args:
        video_url (str): URL của video Facebook (ví dụ: "https://www.facebook.com/reel/1525194028720314/")
        profile_id (str): Profile ID để lấy cookies và payload
        payload_dict (dict, optional): Payload dictionary (nếu đã có sẵn)
        cookies (str, optional): Cookie string (nếu đã có sẵn)
        
    Returns:
        tuple: (post_id, owning_profile_dict) hoặc (None, None) nếu không tìm thấy
        owning_profile_dict: {"__typename": "...", "name": "...", "id": "..."} hoặc None
    """
    from get_payload import get_payload_by_profile_id, get_cookies_by_profile_id
    
    # Lấy payload và cookies nếu chưa có
    if payload_dict is None:
        payload_dict = get_payload_by_profile_id(profile_id)
        if not payload_dict:
            return None, None
    
    if cookies is None:
        cookies = get_cookies_by_profile_id(profile_id)
        if not cookies:
            return None, None
    
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
    
    # Gửi request
    response = requests.post(url, data=payload, headers=headers)
    
    if response.status_code != 200:
        return None, None
    
    # Parse và lấy post_id
    try:
        response_json = response.json()
        
        # Lấy post_id từ response
        post_id = response_json.get("data", {}).get("xma_preview_data", {}).get("post_id")
        
        # Tìm owning_profile trong toàn bộ response (có thể ở nhiều vị trí)
        owning_profile = None
        
        # Thử tìm trong xma_preview_data trước
        xma_data = response_json.get("data", {}).get("xma_preview_data", {})
        if xma_data:
            owning_profile = xma_data.get("owning_profile")
        
        # Nếu không tìm thấy, tìm trong data trực tiếp
        if not owning_profile:
            data = response_json.get("data", {})
            if isinstance(data, dict):
                owning_profile = data.get("owning_profile")
        
        # Nếu vẫn không tìm thấy, tìm đệ quy trong toàn bộ response
        if not owning_profile:
            def find_owning_profile(obj):
                """Tìm owning_profile đệ quy trong object"""
                if isinstance(obj, dict):
                    if "owning_profile" in obj:
                        return obj["owning_profile"]
                    for value in obj.values():
                        result = find_owning_profile(value)
                        if result:
                            return result
                elif isinstance(obj, list):
                    for item in obj:
                        result = find_owning_profile(item)
                        if result:
                            return result
                return None
            
            owning_profile = find_owning_profile(response_json)
        
        if post_id:
            # Nếu không tìm thấy owning_profile trong API response, thử tìm trong HTML
            if not owning_profile:
                _, owning_profile = get_post_id_from_html(video_url, profile_id, cookies)
            
            # Decode Unicode escape sequences trong owning_profile name nếu có
            if owning_profile and "name" in owning_profile:
                name = owning_profile['name']
                if isinstance(name, str) and '\\u' in name:
                    try:
                        name = json.loads(f'"{name}"')
                        owning_profile['name'] = name
                    except:
                        try:
                            name = codecs.decode(name, 'unicode_escape')
                            owning_profile['name'] = name
                        except:
                            pass
            
            return post_id, owning_profile
        else:
            # Fallback: Tìm post_id trong HTML source (cũng lấy owning_profile)
            post_id, owning_profile = get_post_id_from_html(video_url, profile_id, cookies)
            
            # Decode Unicode escape sequences trong owning_profile name nếu có
            if owning_profile and "name" in owning_profile:
                name = owning_profile['name']
                if isinstance(name, str) and '\\u' in name:
                    try:
                        name = json.loads(f'"{name}"')
                        owning_profile['name'] = name
                    except:
                        try:
                            name = codecs.decode(name, 'unicode_escape')
                            owning_profile['name'] = name
                        except:
                            pass
            
            return post_id, owning_profile
            
    except json.JSONDecodeError:
        # Fallback: Tìm post_id trong HTML source
        post_id, owning_profile = get_post_id_from_html(video_url, profile_id, cookies)
        
        # Decode Unicode escape sequences trong owning_profile name nếu có
        if owning_profile and "name" in owning_profile:
            name = owning_profile['name']
            if isinstance(name, str) and '\\u' in name:
                try:
                    name = json.loads(f'"{name}"')
                    owning_profile['name'] = name
                except:
                    try:
                        name = codecs.decode(name, 'unicode_escape')
                        owning_profile['name'] = name
                    except:
                        pass
        
        return post_id, owning_profile
    except Exception:
        return None, None


def get_post_id_from_html(url, profile_id, cookies=None):
    """
    Fallback: Lấy post_id và owning_profile từ HTML source của trang (view-source)
    
    Args:
        url (str): URL của Facebook post
        profile_id (str): Profile ID để lấy cookies
        cookies (str, optional): Cookie string (nếu đã có sẵn)
        
    Returns:
        tuple: (post_id, owning_profile_dict) hoặc (None, None) nếu không tìm thấy
        owning_profile_dict: {"__typename": "...", "name": "...", "id": "..."} hoặc None
    """
    from get_payload import get_cookies_by_profile_id
    
    # Lấy cookies nếu chưa có
    if cookies is None:
        cookies = get_cookies_by_profile_id(profile_id)
        if not cookies:
            return None, None
    
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
            return None, None
        
        html_content = response.text
        
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
        
        post_id = None
        if found_ids:
            # Lấy post_id đầu tiên (thường là post_id chính)
            post_id = found_ids[0]
        
        # Tìm owning_profile trong HTML
        owning_profile = None
        
        # Pattern 1: Tìm trong JSON structure với các field có thể ở bất kỳ thứ tự nào
        # "owning_profile":{"__typename":"User","name":"Nhà Bao Drama","id":"100092638646924"}
        owning_profile_patterns = [
            # Pattern với thứ tự: __typename, name, id
            r'"owning_profile"\s*:\s*\{[^}]*"__typename"\s*:\s*"([^"]+)"[^}]*"name"\s*:\s*"([^"]+)"[^}]*"id"\s*:\s*"([^"]+)"',
            # Pattern với thứ tự: name, __typename, id
            r'"owning_profile"\s*:\s*\{[^}]*"name"\s*:\s*"([^"]+)"[^}]*"__typename"\s*:\s*"([^"]+)"[^}]*"id"\s*:\s*"([^"]+)"',
            # Pattern với thứ tự: id, __typename, name
            r'"owning_profile"\s*:\s*\{[^}]*"id"\s*:\s*"([^"]+)"[^}]*"__typename"\s*:\s*"([^"]+)"[^}]*"name"\s*:\s*"([^"]+)"',
        ]
        
        for pattern in owning_profile_patterns:
            match = re.search(pattern, html_content, re.DOTALL)
            if match:
                # Xác định thứ tự các group dựa trên pattern
                if '"__typename"' in pattern and pattern.index('"__typename"') < pattern.index('"name"'):
                    owning_profile = {
                        "__typename": match.group(1),
                        "name": match.group(2),
                        "id": match.group(3)
                    }
                elif '"name"' in pattern and pattern.index('"name"') < pattern.index('"__typename"'):
                    owning_profile = {
                        "name": match.group(1),
                        "__typename": match.group(2),
                        "id": match.group(3)
                    }
                else:
                    owning_profile = {
                        "id": match.group(1),
                        "__typename": match.group(2),
                        "name": match.group(3)
                    }
                break
        
        # Pattern 2: Tìm riêng lẻ các field (nếu pattern 1 không match)
        if not owning_profile:
            # Tìm block owning_profile trước
            owning_profile_block = re.search(r'"owning_profile"\s*:\s*\{([^}]+)\}', html_content, re.DOTALL)
            if owning_profile_block:
                block_content = owning_profile_block.group(1)
                owning_profile = {}
                
                # Tìm __typename
                typename_match = re.search(r'"__typename"\s*:\s*"([^"]+)"', block_content)
                if typename_match:
                    owning_profile["__typename"] = typename_match.group(1)
                
                # Tìm name
                name_match = re.search(r'"name"\s*:\s*"([^"]+)"', block_content)
                if name_match:
                    owning_profile["name"] = name_match.group(1)
                
                # Tìm id
                id_match = re.search(r'"id"\s*:\s*"([^"]+)"', block_content)
                if id_match:
                    owning_profile["id"] = id_match.group(1)
        
        # Decode Unicode escape sequences trong owning_profile name nếu có
        if owning_profile and "name" in owning_profile:
            name = owning_profile['name']
            if isinstance(name, str) and '\\u' in name:
                try:
                    name = json.loads(f'"{name}"')
                    owning_profile['name'] = name
                except:
                    try:
                        name = codecs.decode(name, 'unicode_escape')
                        owning_profile['name'] = name
                    except:
                        pass
        
        return post_id, owning_profile
            
    except Exception:
        return None, None


def get_page_id_from_html(url, profile_id, cookies=None):
    """
    Lấy page_id từ HTML source của trang (view-source)
    
    Args:
        url (str): URL của Facebook page/group
        profile_id (str): Profile ID để lấy cookies
        cookies (str, optional): Cookie string (nếu đã có sẵn)
        
    Returns:
        str: page_id đầu tiên tìm thấy hoặc None
    """
    from get_payload import get_cookies_by_profile_id
    
    # Lấy cookies nếu chưa có
    if cookies is None:
        cookies = get_cookies_by_profile_id(profile_id)
        if not cookies:
            return None
    
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
            return None
        
        html_content = response.text
        
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
        
        # Tìm trong JSON structure như ví dụ: {"987870664956102":{"page_id":"987870664956102","page_id_type":"group"
        # Pattern 1: Lấy từ key của JSON object
        json_key_pattern = r'{"(\d+)":\s*{"page_id"\s*:\s*"(\d+)"'
        json_matches = re.findall(json_key_pattern, html_content)
        if json_matches:
            for match in json_matches:
                found_ids.append(match[0])  # Key từ JSON
                found_ids.append(match[1])  # Value từ page_id field
        
        # Pattern 2: Tìm trực tiếp trong JSON với page_id_type
        json_with_type_pattern = r'"page_id"\s*:\s*"(\d+)"\s*,\s*"page_id_type"\s*:\s*"[^"]*"'
        json_type_matches = re.findall(json_with_type_pattern, html_content)
        if json_type_matches:
            found_ids.extend(json_type_matches)
        
        # Pattern 3: Tìm trong structure phức tạp hơn (có thể có nhiều fields giữa)
        complex_json_pattern = r'{"(\d+)":\s*{[^}]*"page_id"\s*:\s*"(\d+)"'
        complex_matches = re.findall(complex_json_pattern, html_content)
        if complex_matches:
            for match in complex_matches:
                found_ids.append(match[0])  # Key
                found_ids.append(match[1])  # page_id value
        
        if found_ids:
            # Lấy page_id đầu tiên (thường là page_id chính)
            page_id = found_ids[0]
            return page_id
        else:
            return None
            
    except Exception:
        return None


def get_id_from_url(url, profile_id):
    """
    Hàm tổng hợp tự động phát hiện loại URL và lấy page_id hoặc post_id tương ứng
    
    Logic:
    - Nếu URL chứa "group" → là group (chỉ lấy page_id)
    - Còn lại tất cả → là post (lấy post_id và owning_profile)
    
    Args:
        url (str): URL của Facebook (có thể là group hoặc post)
        profile_id (str): Profile ID để lấy cookies và payload
        
    Returns:
        dict: {
            "page_id": str hoặc None,
            "post_id": str hoặc None,
            "owning_profile": dict hoặc None,
            "url_type": str ("group" hoặc "post")
        }
    """
    from get_payload import get_payload_by_profile_id, get_cookies_by_profile_id
    
    # Load cookies và payload một lần duy nhất
    cookies = get_cookies_by_profile_id(profile_id)
    payload_dict = get_payload_by_profile_id(profile_id)
    
    if not cookies or not payload_dict:
        return {
            "page_id": None,
            "post_id": None,
            "owning_profile": None,
            "url_type": "post"
        }
    
    url_lower = url.lower()
    result = {
        "page_id": None,
        "post_id": None,
        "owning_profile": None,
        "url_type": "post"  # Mặc định là post
    }
    
    # Phát hiện loại URL: nếu có "group" trong URL → là group
    if "group" in url_lower:
        result["url_type"] = "group"
        page_id = get_page_id_from_html(url, profile_id, cookies)
        result["page_id"] = page_id
        if page_id:
            print(f"page_id: {page_id}")
        return result
    else:
        # Tất cả các URL khác đều là post
        result["url_type"] = "post"
        
        # Lấy post_id và owning_profile (truyền cookies và payload đã load)
        post_id_result = get_post_id(url, profile_id, payload_dict, cookies)
        if isinstance(post_id_result, tuple):
            post_id, owning_profile = post_id_result
        else:
            post_id = post_id_result
            owning_profile = None
        
        result["post_id"] = post_id
        result["owning_profile"] = owning_profile       
        return result


if __name__ == "__main__":
    # Ví dụ sử dụng hàm get_id_from_url (tổng hợp)
    profile_id = "031ca13d-e8fa-400c-a603-df57a2806788"
    # Test với video/post URL
    url = "https://www.facebook.com/share/p/1D11GiNtVy/"
    result = get_id_from_url(url, profile_id)
    print(result)