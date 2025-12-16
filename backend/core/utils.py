

import re

def extract_uid_from_url(url):
    """
    Chuyển đổi link profile thành UID hoặc Username
    Ví dụ: 
    - https://www.facebook.com/profile.php?id=10001234 -> 10001234
    - https://www.facebook.com/zuck?comment_id=... -> zuck
    """
    if not url: return None
    
    # Trường hợp 1: profile.php?id=12345
    match_id = re.search(r'profile\.php\?id=(\d+)', url)
    if match_id:
        return match_id.group(1)
        
    # Trường hợp 2: facebook.com/username
    # Loại bỏ các tham số rác sau dấu ? hoặc &
    clean_url = url.split('?')[0].split('&')[0]
    parts = clean_url.rstrip('/').split('/')
    
    # Lấy phần cuối cùng (username)
    if parts:
        user_part = parts[-1]
        if user_part not in ['facebook.com', 'www.facebook.com', '']:
            return user_part
            
    return None

def clean_profile_list(raw):
    """Chuẩn hóa danh sách profile từ string hoặc list."""
    if not raw:
        return []

    items = raw if isinstance(raw, list) else str(raw).split(",")
    return [str(p).strip() for p in items if str(p).strip()]