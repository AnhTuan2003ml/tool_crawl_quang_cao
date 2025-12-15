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
def get_post_id(video_url, profile_id, cookies=None):
    """
    Lấy post_id và owning_profile từ HTML source (view-source)
    Sử dụng cookies để mở như trình duyệt bình thường
    
    Args:
        video_url (str): URL của video Facebook (ví dụ: "https://www.facebook.com/reel/1525194028720314/")
        profile_id (str): Profile ID để lấy cookies
        cookies (str, optional): Cookie string (nếu đã có sẵn)
        
    Returns:
        tuple: (post_id, owning_profile_dict) hoặc (None, None) nếu không tìm thấy
        owning_profile_dict: {"__typename": "...", "name": "...", "id": "..."} hoặc None
    """
    # Sử dụng HTML source để lấy thông tin (với cookies)
    post_id, owning_profile, post_text = get_post_id_from_html(video_url, profile_id, cookies)
    
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
    
    return post_id, owning_profile, post_text


def get_post_id_from_html(url, profile_id, cookies=None):
    """
    Lấy post_id và owning_profile từ HTML source của trang (view-source)
    Sử dụng cookies để mở như trình duyệt bình thường
    
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
            print(f"❌ Không thể lấy cookies từ profile_id: {profile_id}")
            return None, None
    
    try:
        # Tạo session để quản lý cookies tốt hơn (như trình duyệt)
        session = requests.Session()
        
        # Parse cookies string thành dict và thêm vào session
        # Cookies string format: "name1=value1; name2=value2; ..."
        if cookies:
            cookies_dict = {}
            for cookie_pair in cookies.split(';'):
                cookie_pair = cookie_pair.strip()
                if '=' in cookie_pair:
                    key, value = cookie_pair.split('=', 1)
                    cookies_dict[key.strip()] = value.strip()
            session.cookies.update(cookies_dict)
        
        # Headers cho GET request (giống trình duyệt)
        get_headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "accept-encoding": "gzip, deflate",
            "accept-language": "en,vi;q=0.9,en-US;q=0.8",
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
        
        # Lấy HTML source trực tiếp (view-source) với cookies
        print(f"🌐 Lấy HTML source (view-source) trực tiếp từ: {url}")
        response = session.get(url, headers=get_headers)
        
        print(f"📊 Status Code: {response.status_code}")
        print(f"📄 Response Length: {len(response.text)} characters")
        
        if response.status_code != 200:
            print(f"❌ Status code không phải 200: {response.status_code}")
            return None, None
        
        html_content = response.text
        print(f"✅ Đã lấy HTML content ({len(html_content)} ký tự)")
        
        # Debug: Tìm các pattern có thể có trong HTML
        # Facebook có thể escape hoặc encode khác
        print(f"\n🔍 Đang tìm kiếm patterns...")
        
        # Thử tìm post_id với nhiều pattern khác nhau
        post_id = None
        
        # Pattern 1: "post_id":"123456789" (chuẩn)
        match = re.search(r'"post_id"\s*:\s*"(\d+)"', html_content)
        if match:
            post_id = match.group(1)
            print(f"✅ Tìm thấy post_id (pattern 1): {post_id}")
        else:
            # Pattern 2: "post_id":123456789 (không có quotes)
            match = re.search(r'"post_id"\s*:\s*(\d+)', html_content)
            if match:
                post_id = match.group(1)
                print(f"✅ Tìm thấy post_id (pattern 2): {post_id}")
            else:
                # Pattern 3: post_id":"123456789" (có thể escape)
                match = re.search(r'post_id["\']?\s*:\s*["\']?(\d+)', html_content)
                if match:
                    post_id = match.group(1)
                    print(f"✅ Tìm thấy post_id (pattern 3): {post_id}")
                else:
                    # Pattern 4: Tìm trong JSON structure
                    # Có thể là JSON được embed trong HTML
                    json_matches = re.findall(r'["\']post_id["\']\s*:\s*["\']?(\d+)', html_content, re.IGNORECASE)
                    if json_matches:
                        post_id = json_matches[0]
                        print(f"✅ Tìm thấy post_id (pattern 4 - JSON): {post_id}")
                    else:
                        print(f"⚠️ Không tìm thấy post_id với bất kỳ pattern nào")
                        # Debug: Tìm một số pattern khác để xem HTML có gì
                        if '"post_id"' in html_content:
                            print(f"   🔍 Tìm thấy chuỗi 'post_id' trong HTML nhưng không match pattern")
                            # Tìm context xung quanh
                            idx = html_content.find('"post_id"')
                            if idx != -1:
                                context = html_content[max(0, idx-50):min(len(html_content), idx+100)]
                                print(f"   📋 Context: {context[:150]}...")
                        else:
                            print(f"   🔍 Không tìm thấy chuỗi 'post_id' trong HTML")
        
        # ===== TÌM OWNING_PROFILE ĐẦU TIÊN TRONG HTML =====
        # Pattern: "owning_profile":{"__typename":"User","name":"...","id":"..."}
        # Có thể có các field khác như "short_name" giữa các field
        owning_profile = None
        
        # Tìm owning_profile với nhiều pattern khác nhau
        
        # Pattern 1: "owning_profile":{ (chuẩn)
        pattern = r'"owning_profile"\s*:\s*\{'
        match = re.search(pattern, html_content)
        
        if match:
            print(f"✅ Tìm thấy 'owning_profile':{{ tại vị trí {match.start()}")
            start_pos = match.end()
            
            # Tìm closing brace tương ứng (balanced braces)
            brace_count = 1
            end_pos = start_pos
            while end_pos < len(html_content) and brace_count > 0:
                if html_content[end_pos] == '{':
                    brace_count += 1
                elif html_content[end_pos] == '}':
                    brace_count -= 1
                end_pos += 1
            
            if brace_count == 0:
                # Lấy nội dung bên trong braces
                block_content = html_content[start_pos:end_pos-1]
                print(f"   📋 Block content length: {len(block_content)} characters")
                
                # Tìm các field trong block này
                owning_profile_data = {}
                
                # Tìm __typename
                typename_match = re.search(r'"__typename"\s*:\s*"([^"]+)"', block_content)
                if typename_match:
                    owning_profile_data["__typename"] = typename_match.group(1)
                    print(f"   ✅ Tìm thấy __typename: {typename_match.group(1)}")
                
                # Tìm name
                name_match = re.search(r'"name"\s*:\s*"([^"]+)"', block_content)
                if name_match:
                    owning_profile_data["name"] = name_match.group(1)
                    print(f"   ✅ Tìm thấy name: {name_match.group(1)[:50]}...")
                
                # Tìm id
                id_match = re.search(r'"id"\s*:\s*"([^"]+)"', block_content)
                if id_match:
                    owning_profile_data["id"] = id_match.group(1)
                    print(f"   ✅ Tìm thấy id: {id_match.group(1)}")
                
                # Chỉ lấy nếu có đủ ít nhất 2 trong 3 fields (__typename, name, id)
                if len(owning_profile_data) >= 2:
                    owning_profile = owning_profile_data
                    print(f"✅ Đã extract owning_profile thành công")
                else:
                    print(f"⚠️ Không đủ fields trong owning_profile (chỉ có {len(owning_profile_data)} fields)")
            else:
                print(f"⚠️ Không tìm thấy closing brace tương ứng (brace_count: {brace_count})")
        else:
            print(f"⚠️ Không tìm thấy pattern 'owning_profile':{{")
            # Debug: Kiểm tra xem có chuỗi owning_profile không
            if '"owning_profile"' in html_content or "'owning_profile'" in html_content:
                print(f"   🔍 Tìm thấy chuỗi 'owning_profile' trong HTML nhưng không match pattern")
                # Tìm context xung quanh
                idx = html_content.find('owning_profile')
                if idx != -1:
                    context = html_content[max(0, idx-50):min(len(html_content), idx+200)]
                    print(f"   📋 Context: {context[:200]}...")
            else:
                print(f"   🔍 Không tìm thấy chuỗi 'owning_profile' trong HTML")
                # Có thể HTML được minify, thử tìm trong JSON blocks
                # Facebook thường embed JSON trong script tags
                script_tags = re.findall(r'<script[^>]*>(.*?)</script>', html_content, re.DOTALL)
                print(f"   🔍 Tìm thấy {len(script_tags)} script tags, đang tìm trong đó...")
                for i, script_content in enumerate(script_tags[:5]):  # Chỉ check 5 script đầu tiên
                    if 'owning_profile' in script_content:
                        print(f"   ✅ Tìm thấy 'owning_profile' trong script tag #{i+1}")
                        # Tìm trong script này
                        match = re.search(r'"owning_profile"\s*:\s*\{', script_content)
                        if match:
                            print(f"      ✅ Match pattern trong script tag!")
                            # Extract từ script content
                            start_pos = match.end()
                            brace_count = 1
                            end_pos = start_pos
                            while end_pos < len(script_content) and brace_count > 0:
                                if script_content[end_pos] == '{':
                                    brace_count += 1
                                elif script_content[end_pos] == '}':
                                    brace_count -= 1
                                end_pos += 1
                            
                            if brace_count == 0:
                                block_content = script_content[start_pos:end_pos-1]
                                owning_profile_data = {}
                                
                                typename_match = re.search(r'"__typename"\s*:\s*"([^"]+)"', block_content)
                                if typename_match:
                                    owning_profile_data["__typename"] = typename_match.group(1)
                                
                                name_match = re.search(r'"name"\s*:\s*"([^"]+)"', block_content)
                                if name_match:
                                    owning_profile_data["name"] = name_match.group(1)
                                
                                id_match = re.search(r'"id"\s*:\s*"([^"]+)"', block_content)
                                if id_match:
                                    owning_profile_data["id"] = id_match.group(1)
                                
                                if len(owning_profile_data) >= 2:
                                    owning_profile = owning_profile_data
                                    print(f"      ✅ Đã extract owning_profile từ script tag!")
                                    break
        
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

        # ===== LẤY NỘI DUNG BÀI POST =====
        post_text = None

        # Ưu tiên lấy nội dung trong block story_message (nội dung bài post)
        content_html = None

        story_match = re.search(
            r'data-ad-rendering-role="story_message"[^>]*>(.*?)</div></div></div>',
            html_content,
            re.DOTALL,
        )
        if story_match:
            content_html = story_match.group(1)
            print("✅ Tìm thấy block story_message để trích nội dung bài post")
        else:
            # Fallback: dùng một phần đầu HTML
            content_html = html_content[:500_000]
            print("⚠️ Không tìm thấy block story_message, dùng fallback (500KB đầu HTML)")

        # Thay <img ... alt="..."> bằng chính alt (để giữ emoji/text)
        def _img_alt_to_text(m):
            alt_text = m.group(1) or ""
            return f" {alt_text} "

        content_html = re.sub(
            r'<img[^>]*alt="([^"]*)"[^>]*>',
            _img_alt_to_text,
            content_html,
            flags=re.IGNORECASE,
        )

        # Bỏ toàn bộ tag HTML còn lại
        text_raw = re.sub(r"<[^>]*>", " ", content_html)
        # Chuẩn hóa khoảng trắng
        text_clean = re.sub(r"\s+", " ", text_raw).strip()

        if text_clean:
            post_text = text_clean
            preview = post_text[:400] + "..." if len(post_text) > 400 else post_text
            print(f"✅ Post text (preview): {preview}")
        else:
            print("⚠️ Không trích được nội dung bài post từ HTML")

        return post_id, owning_profile, post_text
            
    except Exception as e:
        print(f"❌ Lỗi khi lấy HTML source: {e}")
        import traceback
        traceback.print_exc()
        return None, None


def get_page_id_from_html(url, profile_id, cookies=None):
    """
    Lấy page_id từ HTML source của trang (view-source)
    Sử dụng cookies để mở như trình duyệt bình thường
    
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
            print(f"❌ Không thể lấy cookies từ profile_id: {profile_id}")
            return None
    
    try:
        # Tạo session để quản lý cookies tốt hơn (như trình duyệt)
        session = requests.Session()
        
        # Parse cookies string thành dict và thêm vào session
        if cookies:
            cookies_dict = {}
            for cookie_pair in cookies.split(';'):
                cookie_pair = cookie_pair.strip()
                if '=' in cookie_pair:
                    key, value = cookie_pair.split('=', 1)
                    cookies_dict[key.strip()] = value.strip()
            session.cookies.update(cookies_dict)
        
        # Headers cho GET request (giống trình duyệt)
        get_headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "accept-encoding": "gzip, deflate, br",
            "accept-language": "en,vi;q=0.9,en-US;q=0.8",
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
        
        # Lấy HTML source trực tiếp (view-source) với cookies
        print(f"🌐 Lấy HTML source (view-source) trực tiếp từ: {url}")
        response = session.get(url, headers=get_headers)
        
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
    Sử dụng HTML source (view-source) với cookies để mở như trình duyệt bình thường
    
    Logic:
    - Nếu URL chứa "group" → là group (chỉ lấy page_id)
    - Còn lại tất cả → là post (lấy post_id và owning_profile)
    
    Args:
        url (str): URL của Facebook (có thể là group hoặc post)
        profile_id (str): Profile ID để lấy cookies
        
    Returns:
        dict: {
            "page_id": str hoặc None,
            "post_id": str hoặc None,
            "owning_profile": dict hoặc None,
            "url_type": str ("group" hoặc "post")
        }
    """
    from get_payload import get_cookies_by_profile_id
    
    # Load cookies một lần duy nhất
    cookies = get_cookies_by_profile_id(profile_id)
    
    if not cookies:
        print(f"❌ Không thể lấy cookies từ profile_id: {profile_id}")
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
        
        # Lấy post_id, owning_profile và post_text từ HTML source (với cookies)
        post_id, owning_profile, post_text = get_post_id(url, profile_id, cookies)
        
        result["post_id"] = post_id
        result["owning_profile"] = owning_profile
        result["post_text"] = post_text
        
        # In kết quả cuối cùng
        if post_id:
            print(f"post_id: {post_id}")
        
        if owning_profile:
            owning_profile_typename = owning_profile.get("__typename")
            owning_profile_name = owning_profile.get("name")
            owning_profile_id = owning_profile.get("id")
            
            if owning_profile_typename:
                print(f"owning_profile.__typename: {owning_profile_typename}")
            if owning_profile_name:
                print(f"owning_profile.name: {owning_profile_name}")
            if owning_profile_id:
                print(f"owning_profile.id: {owning_profile_id}")

        if post_text:
            preview = post_text[:200] + "..." if len(post_text) > 200 else post_text
            print(f"post_text: {preview}")
        
        return result


if __name__ == "__main__":
    # Ví dụ sử dụng hàm get_id_from_url (tổng hợp)
    profile_id = "621e1f5d-0c42-481e-9ddd-7abaafce68ed"
    
    # Test với group URL
    # group_url = "https://www.facebook.com/groups/987870664956102/"
    # result = get_id_from_url(group_url, profile_id)
    
    # Test với video/post URL
    url = "https://www.facebook.com/122152251362694490"
    result = get_id_from_url(url, profile_id)
    print(result)