import json
import os
from pathlib import Path
from datetime import datetime
from single_get_reactions import get_all_users_by_fid
from single_get_comment import get_all_comments_by_post_id
from core import control as control_state


def _import_get_payload_funcs():
    """
    Try multiple import paths for get_payload functions so the worker scripts
    can be run from different working directories.
    Returns tuple: (get_payload_by_profile_id, get_cookies_by_profile_id, get_access_token_by_profile_id)
    """
    try:
        from get_payload import get_payload_by_profile_id, get_cookies_by_profile_id, get_access_token_by_profile_id  # type: ignore
        return get_payload_by_profile_id, get_cookies_by_profile_id, get_access_token_by_profile_id
    except Exception:
        try:
            from backend.worker.get_payload import get_payload_by_profile_id, get_cookies_by_profile_id, get_access_token_by_profile_id  # type: ignore
            return get_payload_by_profile_id, get_cookies_by_profile_id, get_access_token_by_profile_id
        except Exception:
            from worker.get_payload import get_payload_by_profile_id, get_cookies_by_profile_id, get_access_token_by_profile_id  # type: ignore
            return get_payload_by_profile_id, get_cookies_by_profile_id, get_access_token_by_profile_id


# Get payload functions (imported via helper)
get_payload_by_profile_id, get_cookies_by_profile_id, get_access_token_by_profile_id = _import_get_payload_funcs()

# ====== ĐƯỜNG DẪN THEO PROJECT ROOT ======
# Sử dụng paths utility để xác định đúng đường dẫn khi chạy từ .exe
try:
    from core.paths import get_data_dir
    DATA_DIR = get_data_dir()
except ImportError:
    # Fallback nếu không import được (khi chạy standalone)
    if hasattr(__import__('sys'), 'frozen') and getattr(__import__('sys'), 'frozen', False):
        import sys
        DATA_DIR = Path(sys.executable).parent / "data"
    else:
        BASE_DIR = Path(__file__).resolve().parents[2]  # Thư mục gốc project
        DATA_DIR = BASE_DIR / "backend" / "data"

POST_IDS_DIR = DATA_DIR / "post_ids"
OUTPUT_DIR = DATA_DIR / "results"
# File all_results kèm timestamp cho mỗi lần chạy (chỉ một file duy nhất)
RUN_TS = datetime.now().strftime("%Y%m%d_%H%M%S")
ALL_RESULTS_FILE = OUTPUT_DIR / f"all_results_{RUN_TS}.json"
# Bộ nhớ đệm kết quả để ghi dạng summary giống all_results_summary_selected
ALL_RESULTS_DATA = {
    "total_files": 0,
    "results_by_file": {},
    "total_posts_processed": 0,
    "total_reactions": 0,
    "total_comments": 0,
}

def cleanup_old_result_files(max_days: int = 3) -> int:
    """
    Xóa các file all_results cũ quá max_days ngày.
    Trả về số file đã xóa.
    """
    import re
    from datetime import datetime, timedelta

    if not OUTPUT_DIR.exists():
        return 0

    # Pattern để parse timestamp từ tên file: all_results_YYYYMMDD_HHMMSS.json
    pattern = re.compile(r'all_results_(\d{8})_(\d{6})\.json$')

    current_time = datetime.now()
    max_age = timedelta(days=max_days)
    deleted_count = 0

    # Duyệt qua tất cả file trong thư mục
    for file_path in OUTPUT_DIR.glob("*.json"):
        if not file_path.is_file():
            continue

        match = pattern.match(file_path.name)
        if not match:
            continue

        date_str, time_str = match.groups()
        try:
            # Parse thành datetime
            file_datetime = datetime.strptime(f"{date_str} {time_str}", "%Y%m%d %H%M%S")

            # Kiểm tra tuổi file
            if current_time - file_datetime > max_age:
                try:
                    file_path.unlink()  # Xóa file
                    deleted_count += 1
                    print(f"Đã xóa file cũ: {file_path.name}")
                except Exception as e:
                    print(f"Lỗi khi xóa file {file_path.name}: {e}")

        except ValueError:
            # Nếu không parse được timestamp, bỏ qua
            continue

    return deleted_count


# Biến global để lưu tiến trình khi đang lấy thông tin
INFO_PROGRESS = {
    "is_running": False,
    "current": 0,
    "total": 0,
    "current_file": "",
}

# Tạo thư mục output nếu chưa có
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ====== PROFILE ID ======
# Profile ID mặc định, có thể thay đổi
DEFAULT_PROFILE_ID = "031ca13d-e8fa-400c-a603-df57a2806788"


def filter_by_owner_id(items, owner_id):
    """
    Lọc bỏ các items có id trùng với owner_id
    
    Args:
        items (list): Danh sách items (reactions hoặc comments)
        owner_id (str): ID của owner cần loại bỏ
        
    Returns:
        list: Danh sách items đã được lọc
    """
    if not owner_id or not items:
        return items
    
    filtered = []
    removed_count = 0
    
    for item in items:
        # Reactions: {"id": user_id, "name": user_name}
        # Comments: {"id": user_id, "name": user_name, "text": ...} hoặc {"id": comment_id, "author": {"id": user_id, ...}}
        item_id = None
        
        # Thử lấy id từ các vị trí có thể
        if "id" in item:
            # Với comments, có thể là comment_id hoặc user_id
            # Nếu có "author", thì id là comment_id, cần lấy từ author
            if "author" in item and isinstance(item["author"], dict):
                item_id = item["author"].get("id")
            else:
                # Nếu không có author, thì id chính là user_id
                item_id = item.get("id")
        
        # Nếu vẫn chưa có, thử các field khác
        if not item_id:
            item_id = item.get("user_id")
        
        # Chỉ thêm vào nếu id khác với owner_id
        if item_id != owner_id:
            filtered.append(item)
        else:
            removed_count += 1
    
    if removed_count > 0:
        print(f"   🚫 Đã lọc bỏ {removed_count} items từ owner (ID: {owner_id})")
    
    return filtered


def process_post_id(post_data, file_name, profile_id, payload_dict, cookies):
    """
    Xử lý một post: lấy reactions và comments
    
    Args:
        post_data (dict hoặc str): 
            - Nếu là dict: {"id": "...", "flag": "...", "text": "...", "owning_profile": {...}}
            - Nếu là str: post_id (format cũ, để tương thích)
        file_name (str): Tên file JSON chứa post này
        profile_id (str): Profile ID
        payload_dict (dict): Payload dictionary đã được load sẵn
        cookies (str): Cookie string đã được load sẵn
        
    Returns:
        dict: Kết quả với reactions và comments
    """
    # Xử lý cả format cũ (string) và format mới (object)
    if isinstance(post_data, str):
        # Format cũ: chỉ là string post_id
        post_id = post_data
        flag = None
        text = None
        owning_profile = None
        owning_profile_id = None
    else:
        # Format mới: object với id, flag, text, owning_profile
        post_id = post_data.get("id")
        flag = post_data.get("flag")
        text = post_data.get("text")
        owning_profile = post_data.get("owning_profile")
        owning_profile_id = owning_profile.get("id") if owning_profile else None
    
    if not post_id:
        print(f"⚠️ Không tìm thấy post_id trong post_data")
        return None
    
    print("\n" + "="*70)
    print(f"📌 Xử lý Post ID: {post_id}")
    if flag:
        print(f"🏷️  Flag: {flag}")
    if owning_profile:
        print(f"👤 Owner: {owning_profile.get('name', 'N/A')} (ID: {owning_profile_id})")
    print(f"📁 Từ file: {file_name}")
    print(f"👤 Profile ID: {profile_id}")
    print("="*70)
    
    result = {
        "post_id": post_id,
        "flag": flag,
        "text": text,
        "owning_profile": owning_profile,
        "source_file": file_name,
        "profile_id": profile_id,
        "reactions": [],
        "comments": [],
        "reactions_count": 0,
        "comments_count": 0,
        "reactions_count_before_filter": 0,
        "comments_count_before_filter": 0,
        "status": "success"
    }
    
    try:
        # 1. Lấy reactions
        print(f"\n🔵 Bắt đầu lấy REACTIONS cho post_id: {post_id}")
        reactions = get_all_users_by_fid(post_id, payload_dict, profile_id, cookies)
        result["reactions_count_before_filter"] = len(reactions)
        
        # Lọc bỏ reactions từ owner
        if owning_profile_id:
            reactions = filter_by_owner_id(reactions, owning_profile_id)
            filtered_count = result["reactions_count_before_filter"] - len(reactions)
            if filtered_count > 0:
                print(f"🚫 Đã lọc bỏ {filtered_count} reactions từ owner (ID: {owning_profile_id})")
        
        result["reactions"] = reactions
        result["reactions_count"] = len(reactions)
        print(f"✅ Đã lấy được {result['reactions_count']} reactions (sau khi lọc)")
        
        # 2. Lấy comments
        print(f"\n🟢 Bắt đầu lấy COMMENTS cho post_id: {post_id}")
        comments = get_all_comments_by_post_id(post_id, payload_dict, profile_id, cookies)
        result["comments_count_before_filter"] = len(comments)
        
        # Lọc bỏ comments từ owner
        if owning_profile_id:
            comments = filter_by_owner_id(comments, owning_profile_id)
            filtered_count = result["comments_count_before_filter"] - len(comments)
            if filtered_count > 0:
                print(f"🚫 Đã lọc bỏ {filtered_count} comments từ owner (ID: {owning_profile_id})")
        
        result["comments"] = comments
        result["comments_count"] = len(comments)
        print(f"✅ Đã lấy được {result['comments_count']} comments (sau khi lọc)")
        
    except RuntimeError as e:
        # Re-raise RuntimeError (EMERGENCY_STOP) để caller có thể dừng hoàn toàn
        if "EMERGENCY_STOP" in str(e):
            raise
        # Nếu không phải EMERGENCY_STOP thì xử lý như lỗi thông thường
        print(f"❌ Lỗi khi xử lý post_id {post_id}: {e}")
        import traceback
        traceback.print_exc()
        result["status"] = "error"
        result["error"] = str(e)
    except Exception as e:
        print(f"❌ Lỗi khi xử lý post_id {post_id}: {e}")
        import traceback
        traceback.print_exc()
        result["status"] = "error"
        result["error"] = str(e)
    
    return result


def append_to_all_results(file_name: str, result: dict):
    """
    Append FULL result vào cấu trúc summary (results_by_file) và ghi ra all_results_<timestamp>.json NGAY LẬP TỨC.
    """
    try:
        # Bổ sung list cho file nếu chưa có
        results_by_file = ALL_RESULTS_DATA.get("results_by_file", {})
        file_list = results_by_file.get(file_name)
        if file_list is None:
            file_list = []
            results_by_file[file_name] = file_list
        file_list.append(result)
        ALL_RESULTS_DATA["results_by_file"] = results_by_file

        # Cập nhật counters
        ALL_RESULTS_DATA["total_posts_processed"] = sum(len(v) for v in results_by_file.values())
        ALL_RESULTS_DATA["total_reactions"] += int(result.get("reactions_count", 0) or 0)
        ALL_RESULTS_DATA["total_comments"] += int(result.get("comments_count", 0) or 0)
        ALL_RESULTS_DATA["total_files"] = len(results_by_file.keys())

        # Cleanup file cũ quá 3 ngày trước khi ghi file mới
        cleanup_old_result_files(3)

        # Ghi file NGAY LẬP TỨC và flush để đảm bảo dữ liệu được ghi ngay
        with open(ALL_RESULTS_FILE, "w", encoding="utf-8") as f:
            json.dump(ALL_RESULTS_DATA, f, ensure_ascii=False, indent=2)
            f.flush()  # Đảm bảo dữ liệu được ghi ngay vào disk
            os.fsync(f.fileno())  # Force write to disk (nếu hệ thống hỗ trợ)
        
        post_id = result.get("post_id", "N/A")
        print(f"💾 Đã lưu post_id {post_id} vào {ALL_RESULTS_FILE}")
    except Exception as e:
        print(f"⚠️ Lỗi khi lưu vào {ALL_RESULTS_FILE}: {e}")
        import traceback
        traceback.print_exc()


def _check_stop_pause(profile_id: str | None = None):
    """Tôn trọng nút dừng / pause (global hoặc theo profile)."""
    stop, paused, reason = control_state.check_flags(profile_id)
    if stop:
        raise RuntimeError(f"EMERGENCY_STOP ({reason})")
    if paused:
        print(f"⏸️ Đang tạm dừng ({reason}), chờ tiếp tục ...")
        control_state.wait_if_paused(profile_id, sleep_seconds=0.5)


def extract_profile_id_from_filename(file_name):
    """
    Tách profile_id từ tên file (ví dụ: 031ca13d-e8fa-400c-a603-df57a2806788.json -> 031ca13d-e8fa-400c-a603-df57a2806788)
    
    Args:
        file_name (str): Tên file (có thể có hoặc không có đường dẫn)
        
    Returns:
        str: Profile ID hoặc None nếu không tách được
    """
    # Lấy tên file không có extension
    base_name = os.path.splitext(os.path.basename(file_name))[0]
    
    # Kiểm tra xem có phải là UUID format không (có dấu gạch ngang)
    if '-' in base_name and len(base_name) == 36:  # UUID format: 8-4-4-4-12
        return base_name
    
    return None


def process_post_ids_file(file_path):
    """
    Xử lý một file JSON chứa danh sách post_ids
    
    Args:
        file_path (str): Đường dẫn đến file JSON
        
    Returns:
        list: Danh sách kết quả của tất cả post_ids trong file
    """
    file_name = os.path.basename(file_path)
    
    # Tự động tách profile_id từ tên file
    profile_id = extract_profile_id_from_filename(file_name)
    
    if not profile_id:
        print(f"⚠️ Không thể tách profile_id từ tên file: {file_name}")
        print(f"   Sử dụng profile_id mặc định: {DEFAULT_PROFILE_ID}")
        profile_id = DEFAULT_PROFILE_ID
    else:
        print(f"✅ Đã tách profile_id từ tên file: {profile_id}")
    
    print("\n" + "="*70)
    print(f"📂 Đang xử lý file: {file_name}")
    print(f"👤 Profile ID: {profile_id}")
    print("="*70)
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            post_ids = json.load(f)
        
        if not isinstance(post_ids, list):
            print(f"⚠️ File {file_name} không chứa mảng post_ids")
            return []
        
        # Kiểm tra nếu file trống hoặc không có dữ liệu
        if len(post_ids) == 0:
            print(f"⚠️ File {file_name} không có dữ liệu bài viết (file trống)")
            raise ValueError(f"File {file_name} không có dữ liệu bài viết")
        
        print(f"📋 Tìm thấy {len(post_ids)} post(s) trong file")
        
        # Load payload và cookies một lần cho tất cả posts
        print(f"\n🔄 Đang lấy payload và cookies từ profile_id: {profile_id}")
        # Khi bắt đầu xử lý, đảm bảo profile không bị STOP trong runtime_control
        control_state.resume_profile(profile_id)

        payload_dict = get_payload_by_profile_id(profile_id)
        if not payload_dict:
            print(f"❌ Không thể lấy payload từ profile_id: {profile_id}")
            return []
        
        cookies = get_cookies_by_profile_id(profile_id)
        if not cookies:
            print(f"❌ Không thể lấy cookies từ profile_id: {profile_id}")
            return []
        
        print(f"✅ Đã load payload và cookies thành công (sẽ dùng chung cho tất cả {len(post_ids)} posts)")
        
        results = []
        idx = 0
        while idx < len(post_ids):
            try:
                _check_stop_pause(profile_id)
            except RuntimeError as stp:
                print(f"🛑 Dừng xử lý file {file_name} do stop/pause: {stp}")
                break

            post_data = post_ids[idx]
            # Xử lý cả format cũ (string) và format mới (object)
            if isinstance(post_data, str):
                post_id = post_data
            else:
                post_id = post_data.get("id")
            
            if not post_id:
                print(f"⚠️ [{idx+1}/{len(post_ids)}] Bỏ qua item không có post_id: {post_data}")
                idx += 1
                continue
            
            print(f"\n{'='*70}")
            print(f"📌 [{idx+1}/{len(post_ids)}] Xử lý Post ID: {post_id}")
            print(f"{'='*70}")
            
            try:
                result = process_post_id(post_data, file_name, profile_id, payload_dict, cookies)
            except RuntimeError as stp:
                # Nếu là EMERGENCY_STOP thì dừng ngay
                if "EMERGENCY_STOP" in str(stp):
                    print(f"🛑 Dừng xử lý file {file_name} do stop: {stp}")
                    raise  # Re-raise để caller có thể catch và break
                # Nếu không phải EMERGENCY_STOP thì xử lý như lỗi thông thường
                print(f"❌ Lỗi RuntimeError khi xử lý post_id {post_id}: {stp}")
                result = None
            
            if result:
                results.append(result)
                
                # Append full result vào all_results_<timestamp>.json (summary-style)
                append_to_all_results(file_name, result)

                # Cập nhật tiến trình
                INFO_PROGRESS["current"] += 1

                # Xóa post_id đã xử lý khỏi file nguồn
                post_ids.pop(idx)
                try:
                    with open(file_path, "w", encoding="utf-8") as f:
                        json.dump(post_ids, f, ensure_ascii=False, indent=2)
                    print(f"🗑️ Đã xóa post_id {post_id} khỏi {file_name}")
                except Exception as e:
                    print(f"⚠️ Không thể ghi lại file {file_name} sau khi xóa post_id: {e}")
                # không tăng idx vì đã pop, danh sách đã dịch sang trái
                continue
            
            # Nếu không có result (lỗi) thì tăng idx để tránh loop vô hạn
            idx += 1
            # Vẫn cập nhật tiến trình dù có lỗi
            INFO_PROGRESS["current"] += 1
        
        return results
        
    except ValueError as e:
        # Re-raise ValueError để caller có thể catch và xử lý
        if "không có dữ liệu bài viết" in str(e):
            raise
        print(f"❌ Lỗi: {e}")
        return []
    except FileNotFoundError:
        print(f"❌ Không tìm thấy file: {file_path}")
        return []
    except json.JSONDecodeError as e:
        print(f"❌ Lỗi: File {file_name} không phải JSON hợp lệ: {e}")
        return []
    except Exception as e:
        print(f"❌ Lỗi khi xử lý file {file_name}: {e}")
        import traceback
        traceback.print_exc()
        return []


def get_all_info_from_post_ids_dir():
    """
    Xử lý tất cả các file JSON trong thư mục data/post_ids/
    Mỗi file sẽ tự động sử dụng profile_id từ tên file
    """
    global INFO_PROGRESS
    
    print("\n" + "="*70)
    print("🚀 BẮT ĐẦU XỬ LÝ TẤT CẢ POST IDs")
    print("="*70)
    print("ℹ️  Mỗi file sẽ tự động sử dụng profile_id từ tên file")
    print("="*70)
    
    # Lấy tất cả file JSON trong thư mục
    post_ids_path = Path(POST_IDS_DIR)
    if not post_ids_path.exists():
        print(f"❌ Không tìm thấy thư mục: {POST_IDS_DIR}")
        INFO_PROGRESS["is_running"] = False
        return
    
    json_files = list(post_ids_path.glob("*.json"))
    
    if not json_files:
        print(f"⚠️ Không tìm thấy file JSON nào trong {POST_IDS_DIR}")
        INFO_PROGRESS["is_running"] = False
        raise ValueError("Không có dữ liệu bài viết để xử lý")
    
    print(f"📁 Tìm thấy {len(json_files)} file(s) JSON")
    
    # Tính tổng số bài trước khi bắt đầu
    total_posts = 0
    for file_path in json_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    total_posts += len(data)
        except Exception:
            pass
    
    # Khởi tạo tiến trình
    INFO_PROGRESS = {
        "is_running": True,
        "current": 0,
        "total": total_posts,
        "current_file": "",
    }
    
    all_results = {}
    has_data = False
    
    # Xử lý từng file (mỗi file sẽ tự động extract profile_id từ tên file)
    for file_path in json_files:
        try:
            _check_stop_pause(None)
        except RuntimeError as stp:
            print(f"🛑 Dừng toàn bộ do stop/pause: {stp}")
            break
        file_name = file_path.name
        INFO_PROGRESS["current_file"] = file_name
        try:
            results = process_post_ids_file(str(file_path))
            all_results[file_name] = results
            if results:
                has_data = True
        except ValueError as e:
            # Nếu file trống thì bỏ qua và tiếp tục với file khác
            if "không có dữ liệu bài viết" in str(e):
                print(f"⚠️ {e}")
                all_results[file_name] = []
                continue
            raise
    
    # Kiểm tra nếu không có file nào có dữ liệu
    if not has_data:
        INFO_PROGRESS["is_running"] = False
        raise ValueError("Không có dữ liệu bài viết để xử lý")
    
    # Kết quả đã được ghi vào ALL_RESULTS_FILE trong quá trình chạy
    print("\n" + "="*70)
    print("✅ HOÀN THÀNH XỬ LÝ TẤT CẢ POST IDs")
    print("="*70)
    print(f"📊 Tổng số file đã xử lý: {len(json_files)}")
    print(f"📊 Tổng số post đã xử lý: {ALL_RESULTS_DATA['total_posts_processed']}")
    print(f"📊 Tổng số reactions: {ALL_RESULTS_DATA['total_reactions']}")
    print(f"📊 Tổng số comments: {ALL_RESULTS_DATA['total_comments']}")
    print(f"💾 Đã lưu kết quả vào: {ALL_RESULTS_FILE}")
    print("="*70)
    
    # Reset tiến trình
    INFO_PROGRESS["is_running"] = False
    INFO_PROGRESS["current"] = 0
    INFO_PROGRESS["total"] = 0
    INFO_PROGRESS["current_file"] = ""


def get_info_for_profile_ids(profile_ids):
    """
    Xử lý chỉ các profile_id được chọn (dựa vào file tên <profile_id>.json trong data/post_ids).
    
    Args:
        profile_ids (list[str]): Danh sách profile_id cần xử lý
    
    Returns:
        dict: summary tương tự get_all_info_from_post_ids_dir nhưng chỉ cho profile đã chọn
    """
    if not profile_ids:
        print("⚠️ Không có profile_id nào được cung cấp.")
        return {}

    post_ids_path = Path(POST_IDS_DIR)
    if not post_ids_path.exists():
        print(f"❌ Không tìm thấy thư mục: {POST_IDS_DIR}")
        return {}

    # Chuẩn hóa và loại bỏ trùng
    target_ids = {str(pid).strip() for pid in profile_ids if str(pid).strip()}
    if not target_ids:
        print("⚠️ Danh sách profile_id sau khi lọc rỗng.")
        return {}

    # Lọc file theo profile_id
    json_files = []
    for pid in target_ids:
        candidate = post_ids_path / f"{pid}.json"
        if candidate.exists():
            json_files.append(candidate)
        else:
            print(f"⚠️ Bỏ qua: không tìm thấy file post_ids cho profile_id={pid} ({candidate})")

    if not json_files:
        print("⚠️ Không có file JSON nào khớp profile_id được chọn.")
        INFO_PROGRESS["is_running"] = False
        raise ValueError("Không có dữ liệu bài viết để xử lý")

    print(f"📁 Tìm thấy {len(json_files)} file(s) JSON theo danh sách profile đã chọn.")

    # Tính tổng số bài trước khi bắt đầu
    total_posts = 0
    for file_path in json_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    total_posts += len(data)
        except Exception:
            pass

    # Khởi tạo tiến trình
    INFO_PROGRESS = {
        "is_running": True,
        "current": 0,
        "total": total_posts,
        "current_file": "",
    }

    all_results = {}
    has_data = False
    for file_path in json_files:
        try:
            _check_stop_pause(None)
        except RuntimeError as stp:
            print(f"🛑 Dừng do stop/pause: {stp}")
            break
        file_name = file_path.name
        INFO_PROGRESS["current_file"] = file_name
        try:
            results = process_post_ids_file(str(file_path))
            all_results[file_name] = results
            if results:
                has_data = True
        except ValueError as e:
            # Nếu file trống thì bỏ qua và tiếp tục với file khác
            if "không có dữ liệu bài viết" in str(e):
                print(f"⚠️ {e}")
                all_results[file_name] = []
                continue
            raise
    
    # Kiểm tra nếu không có file nào có dữ liệu
    if not has_data:
        INFO_PROGRESS["is_running"] = False
        raise ValueError("Không có dữ liệu bài viết để xử lý")

    # Kết quả đã được ghi vào ALL_RESULTS_FILE trong quá trình chạy
    print("\n" + "="*70)
    print("✅ HOÀN THÀNH XỬ LÝ PROFILE ĐÃ CHỌN")
    print("="*70)
    print(f"📊 Tổng số file đã xử lý: {len(json_files)}")
    print(f"📊 Tổng số post đã xử lý: {ALL_RESULTS_DATA['total_posts_processed']}")
    print(f"📊 Tổng số reactions: {ALL_RESULTS_DATA['total_reactions']}")
    print(f"📊 Tổng số comments: {ALL_RESULTS_DATA['total_comments']}")
    print(f"💾 Đã lưu kết quả vào: {ALL_RESULTS_FILE}")
    print("="*70)

    # Reset tiến trình
    INFO_PROGRESS["is_running"] = False
    INFO_PROGRESS["current"] = 0
    INFO_PROGRESS["total"] = 0
    INFO_PROGRESS["current_file"] = ""

    return ALL_RESULTS_DATA


if __name__ == "__main__":
    get_all_info_from_post_ids_dir()
