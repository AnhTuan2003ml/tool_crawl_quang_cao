import requests
import json
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, parse_qs

# ====== LƯU Ý ======
# Lấy access_token từ cookies.json thông qua profile_id
# Sử dụng get_payload.get_access_token_by_profile_id(profile_id) để lấy access_token


def get_access_token_by_profile_id(profile_id):
    """
    Lấy access_token từ cookies.json dựa trên profile_id
    
    Args:
        profile_id (str): Profile ID (ví dụ: "031ca13d-e8fa-400c-a603-df57a2806788")
    
    Returns:
        str: Access token hoặc None nếu không tìm thấy
    """
    from get_payload import get_access_token_by_profile_id as get_token
    return get_token(profile_id)


def parse_datetime_string(dt_string):
    """
    Parse datetime string từ Facebook API (format: "2025-12-14T17:58:05+0000")
    
    Args:
        dt_string (str): Datetime string từ Facebook API
        
    Returns:
        datetime: Datetime object hoặc None nếu parse lỗi
    """
    try:
        # Format: "2025-12-14T17:58:05+0000"
        # Chuyển thành: "2025-12-14T17:58:05+00:00" để parse được
        if dt_string.endswith("+0000"):
            dt_string = dt_string.replace("+0000", "+00:00")
        elif dt_string.endswith("-0000"):
            dt_string = dt_string.replace("-0000", "-00:00")
        
        return datetime.fromisoformat(dt_string)
    except Exception as e:
        print(f"⚠️ Lỗi khi parse datetime '{dt_string}': {e}")
        return None


def convert_to_vietnam_datetime(dt_string):
    """
    Chuyển đổi datetime string từ Facebook API sang ngày tháng năm theo múi giờ Việt Nam (UTC+7)
    
    Args:
        dt_string (str): Datetime string từ Facebook API (format: "2025-12-14T17:58:05+0000")
        
    Returns:
        str: Ngày tháng năm theo format "YYYY-MM-DD HH:MM:SS" (múi giờ Việt Nam) hoặc None nếu lỗi
    """
    try:
        # Parse datetime từ API (UTC)
        dt_utc = parse_datetime_string(dt_string)
        if not dt_utc:
            return None
        
        # Chuyển sang múi giờ Việt Nam (UTC+7)
        vietnam_tz = timezone(timedelta(hours=7))
        dt_vietnam = dt_utc.astimezone(vietnam_tz)
        
        # Format thành ngày tháng năm
        return dt_vietnam.strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        print(f"⚠️ Lỗi khi chuyển đổi datetime '{dt_string}' sang giờ Việt Nam: {e}")
        return None


def parse_vietnam_datetime(date_str, is_end_of_day=False):
    """
    Parse ngày tháng năm theo múi giờ Việt Nam (UTC+7) và chuyển sang UTC
    
    Hỗ trợ các format:
    - "2025-12-14" hoặc "2025/12/14"
    - "14-12-2025" hoặc "14/12/2025"
    - "2025-12-14 00:00:00" hoặc "2025-12-14 23:59:59"
    
    Args:
        date_str (str): Chuỗi ngày tháng năm
        is_end_of_day (bool): Nếu True, đặt thời gian là 23:59:59, nếu False là 00:00:00
        
    Returns:
        tuple: (datetime_utc, datetime_string_for_api) hoặc (None, None) nếu lỗi
    """
    try:
        # Múi giờ Việt Nam (UTC+7)
        vietnam_tz = timezone(timedelta(hours=7))
        
        # Loại bỏ khoảng trắng thừa
        date_str = date_str.strip()
        
        # Xử lý các format khác nhau
        dt = None
        
        # Format: "2025-12-14" hoặc "2025/12/14"
        if "-" in date_str or "/" in date_str:
            # Thay thế "/" bằng "-"
            date_str = date_str.replace("/", "-")
            
            # Tách phần ngày và giờ (nếu có)
            parts = date_str.split()
            date_part = parts[0]
            time_part = parts[1] if len(parts) > 1 else None
            
            # Parse date part
            date_parts = date_part.split("-")
            
            if len(date_parts) == 3:
                # Kiểm tra format: YYYY-MM-DD hoặc DD-MM-YYYY
                if len(date_parts[0]) == 4:  # YYYY-MM-DD
                    year, month, day = date_parts
                else:  # DD-MM-YYYY
                    day, month, year = date_parts
                
                year = int(year)
                month = int(month)
                day = int(day)
                
                # Parse time part (nếu có)
                if time_part:
                    time_parts = time_part.split(":")
                    hour = int(time_parts[0])
                    minute = int(time_parts[1]) if len(time_parts) > 1 else 0
                    second = int(time_parts[2]) if len(time_parts) > 2 else 0
                else:
                    # Nếu không có time, đặt theo is_end_of_day
                    if is_end_of_day:
                        hour, minute, second = 23, 59, 59
                    else:
                        hour, minute, second = 0, 0, 0
                
                # Tạo datetime với múi giờ Việt Nam
                dt = datetime(year, month, day, hour, minute, second, tzinfo=vietnam_tz)
        
        # Nếu không parse được, thử parse trực tiếp
        if dt is None:
            # Thử parse với các format khác
            formats = [
                "%Y-%m-%d",
                "%d-%m-%Y",
                "%Y/%m/%d",
                "%d/%m/%Y",
                "%Y-%m-%d %H:%M:%S",
                "%d-%m-%Y %H:%M:%S",
            ]
            
            for fmt in formats:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    # Thêm múi giờ Việt Nam
                    dt = dt.replace(tzinfo=vietnam_tz)
                    # Nếu không có giờ, đặt theo is_end_of_day
                    if "%H" not in fmt:
                        if is_end_of_day:
                            dt = dt.replace(hour=23, minute=59, second=59)
                        else:
                            dt = dt.replace(hour=0, minute=0, second=0)
                    break
                except ValueError:
                    continue
        
        if dt is None:
            raise ValueError(f"Không thể parse date string: {date_str}")
        
        # Chuyển sang UTC
        dt_utc = dt.astimezone(timezone.utc)
        
        # Format cho API: Unix timestamp hoặc ISO format
        # Sử dụng Unix timestamp (dễ dàng hơn)
        unix_timestamp = str(int(dt_utc.timestamp()))
        
        return dt_utc, unix_timestamp
        
    except Exception as e:
        print(f"⚠️ Lỗi khi parse Vietnam datetime '{date_str}': {e}")
        return None, None


def get_posts_from_page(page_id, profile_id, start_date=None, end_date=None, limit=None):
    """
    Lấy danh sách posts từ page/group qua Graph API với điều kiện lọc theo thời gian
    
    Args:
        page_id (str): Page ID hoặc Group ID
        profile_id (str): Profile ID để lấy access_token
        start_date (str, required): Ngày bắt đầu theo múi giờ Việt Nam (format: "2025-12-14" hoặc "14/12/2025")
        end_date (str, required): Ngày kết thúc theo múi giờ Việt Nam (format: "2025-12-14" hoặc "14/12/2025")
        limit (int, optional): Giới hạn số lượng posts (None = không giới hạn)
        
    Returns:
        list: Danh sách posts phù hợp điều kiện thời gian [{"id": "...", "updated_time": "..."}, ...]
    """
    # Validate thời gian
    if not start_date or not end_date:
        print(f"❌ Lỗi: Cần cung cấp cả start_date và end_date")
        return []
    
    # Lấy access_token
    access_token = get_access_token_by_profile_id(profile_id)
    if not access_token:
        print(f"❌ Không thể lấy access_token từ profile_id: {profile_id}")
        return []
    
    # Parse ngày tháng năm theo múi giờ Việt Nam và chuyển sang UTC
    start_dt, start_timestamp = parse_vietnam_datetime(start_date, is_end_of_day=False)
    end_dt, end_timestamp = parse_vietnam_datetime(end_date, is_end_of_day=True)
    
    if not start_dt or not end_dt:
        print(f"❌ Lỗi: Không thể parse ngày tháng")
        return []
    
    # Validate: start_date phải <= end_date
    if start_dt > end_dt:
        print(f"❌ Lỗi: start_date ({start_date}) phải <= end_date ({end_date})")
        return []
    
    # Base URL cho Graph API
    base_url = f"https://graph.facebook.com/v24.0/{page_id}"
    
    # Parameters cho request (sử dụng Unix timestamp)
    # Sử dụng feed.limit(1000) để lấy nhiều posts mỗi trang (tối đa 1000)
    params = {
        "access_token": access_token,
        "fields": "feed.limit(1000){id,created_time}",
        "format": "json",
        "method": "get",
        "pretty": "0",
        "suppress_http_code": "1",
        "since": start_timestamp,  # Unix timestamp (UTC)
        "until": end_timestamp,     # Unix timestamp (UTC)
        "debug": "all",
        "origin_graph_explorer": "1",
        "transport": "cors"
    }
    
    all_posts = []
    next_url = None
    page_count = 0
    
    print(f"\n🚀 Bắt đầu lấy posts từ page_id: {page_id}")
    print(f"   📅 Ngày bắt đầu (VN): {start_date} → UTC: {start_dt.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"   📅 Ngày kết thúc (VN): {end_date} → UTC: {end_dt.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    
    while True:
        # Gửi request
        if next_url:
            # Sử dụng URL pagination từ response trước
            url = next_url
            response = requests.get(url)
        else:
            # Request đầu tiên
            url = base_url
            response = requests.get(url, params=params)
        
        page_count += 1
        print(f"\n📄 Trang {page_count}: {url[:100]}...")
        
        if response.status_code != 200:
            print(f"❌ Lỗi: Status code {response.status_code}")
            print(f"Response: {response.text[:500]}")
            break
        
        try:
            data = response.json()
            
            # Kiểm tra lỗi từ API
            if "error" in data:
                print(f"❌ Lỗi từ API: {data['error']}")
                break
            
            # Lấy feed data
            feed_data = data.get("feed", {})
            posts = feed_data.get("data", [])
            
            if not posts:
                print(f"   ℹ️ Không có posts nào trong trang này")
                break
            
            print(f"   📋 Tìm thấy {len(posts)} posts trong trang này")
            
            # Lọc posts theo điều kiện thời gian
            matched_count = 0
            for post in posts:
                post_id = post.get("id")
                created_time_str = post.get("created_time")
                
                if not post_id or not created_time_str:
                    continue
                
                # Parse created_time
                created_dt = parse_datetime_string(created_time_str)
                if not created_dt:
                    continue
                
                # Kiểm tra điều kiện thời gian: start_time <= created_time <= end_time
                # Đảm bảo created_time nằm trong khoảng [start_dt, end_dt]
                if start_dt <= created_dt <= end_dt:
                    # Chuyển đổi sang ngày tháng năm theo múi giờ Việt Nam
                    created_time_vn = convert_to_vietnam_datetime(created_time_str)
                    
                    all_posts.append({
                        "id": post_id,
                        "created_time": created_time_vn if created_time_vn else created_time_str
                    })
                    matched_count += 1
            
            print(f"   ✅ Có {matched_count} posts phù hợp điều kiện trong trang này")
            
            # Kiểm tra limit
            if limit and len(all_posts) >= limit:
                print(f"   ⏹️ Đã đạt giới hạn {limit} posts")
                all_posts = all_posts[:limit]
                break
            
            # Kiểm tra pagination
            paging = feed_data.get("paging", {})
            if "next" in paging:
                next_url = paging["next"]
            else:
                print(f"   ℹ️ Không còn trang tiếp theo")
                break
                
        except json.JSONDecodeError as e:
            print(f"❌ Lỗi: Response không phải JSON hợp lệ")
            print(f"Response text (500 ký tự đầu): {response.text[:500]}")
            break
        except Exception as e:
            print(f"❌ Lỗi khi xử lý response: {e}")
            import traceback
            traceback.print_exc()
            break
    
    print(f"\n✅ Hoàn thành! Tổng cộng lấy được {len(all_posts)} posts phù hợp điều kiện")
    return all_posts


def get_post_ids_from_page(page_id, profile_id, start_date=None, end_date=None, limit=None):
    """
    Lấy danh sách post IDs từ page/group (chỉ trả về IDs, không có thông tin thời gian)
    
    Args:
        page_id (str): Page ID hoặc Group ID
        profile_id (str): Profile ID để lấy access_token
        start_date (str, required): Ngày bắt đầu theo múi giờ Việt Nam (format: "2025-12-14" hoặc "14/12/2025")
        end_date (str, required): Ngày kết thúc theo múi giờ Việt Nam (format: "2025-12-14" hoặc "14/12/2025")
        limit (int, optional): Giới hạn số lượng posts
        
    Returns:
        list: Danh sách post IDs (strings)
    """
    posts = get_posts_from_page(page_id, profile_id, start_date, end_date, limit)
    return [post["id"] for post in posts]


if __name__ == "__main__":
    import os
    
    # Ví dụ sử dụng
    profile_id = "031ca13d-e8fa-400c-a603-df57a2806788"
    page_id = "987870664956102"
    
    # Lấy posts với điều kiện thời gian (theo múi giờ Việt Nam)
    start_date = "2025-12-8"  # Ngày bắt đầu (sẽ tự động đặt 00:00:00 VN = 17:00:00 UTC ngày hôm trước)
    end_date = "2025-12-14"    # Ngày kết thúc (sẽ tự động đặt 23:59:59 VN = 16:59:59 UTC ngày hôm sau)
    
    posts = get_posts_from_page(page_id, profile_id, start_date, end_date, limit=None)
    
    # In kết quả
    print(f"\n📊 Kết quả:")
    print(f"   Tổng số posts: {len(posts)}")
    if posts:
        print(f"   Ví dụ 5 posts đầu tiên:")
        for post in posts[:5]:
            print(f"      - {post['id']} (created: {post['created_time']})")
    
    # Lưu ra file JSON
    output_dir = "backend/data"
    os.makedirs(output_dir, exist_ok=True)
    
    # Tạo tên file dựa trên page_id và ngày
    filename = f"{page_id}_posts_{start_date.replace('/', '-')}_to_{end_date.replace('/', '-')}.json"
    filepath = os.path.join(output_dir, filename)
    
    # Tạo dữ liệu để lưu
    output_data = {
        "page_id": page_id,
        "profile_id": profile_id,
        "start_date": start_date,
        "end_date": end_date,
        "total_posts": len(posts),
        "posts": posts
    }
    
    # Lưu file JSON
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 Đã lưu kết quả vào: {filepath}")
    print(f"   Tổng số posts: {len(posts)}")
    
    # Lấy chỉ post IDs
    post_ids = get_post_ids_from_page(page_id, profile_id, start_date, end_date)
    print(f"\n📋 Post IDs: {len(post_ids)}")
    if post_ids:
        print(f"   Ví dụ: {post_ids[:5]}")

