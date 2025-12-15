import json
import os
from pathlib import Path
from single_get_reactions import get_all_users_by_fid
from single_get_comment import get_all_comments_by_post_id
from get_payload import get_payload_by_profile_id, get_cookies_by_profile_id

# ====== ĐƯỜNG DẪN THEO PROJECT ROOT ======
BASE_DIR = Path(__file__).resolve().parents[2]  # Thư mục gốc project
POST_IDS_DIR = BASE_DIR / "backend" / "data" / "post_ids"
OUTPUT_DIR = BASE_DIR / "backend" / "data" / "results"

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
        
    except Exception as e:
        print(f"❌ Lỗi khi xử lý post_id {post_id}: {e}")
        import traceback
        traceback.print_exc()
        result["status"] = "error"
        result["error"] = str(e)
    
    return result


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
        
        print(f"📋 Tìm thấy {len(post_ids)} post(s) trong file")
        
        # Load payload và cookies một lần cho tất cả posts
        print(f"\n🔄 Đang lấy payload và cookies từ profile_id: {profile_id}")
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
        for i, post_data in enumerate(post_ids, 1):
            # Xử lý cả format cũ (string) và format mới (object)
            if isinstance(post_data, str):
                post_id = post_data
            else:
                post_id = post_data.get("id")
            
            if not post_id:
                print(f"⚠️ [{i}/{len(post_ids)}] Bỏ qua item không có post_id: {post_data}")
                continue
            
            print(f"\n{'='*70}")
            print(f"📌 [{i}/{len(post_ids)}] Xử lý Post ID: {post_id}")
            print(f"{'='*70}")
            
            result = process_post_id(post_data, file_name, profile_id, payload_dict, cookies)
            if result:
                results.append(result)
                
                # Lưu kết quả riêng cho mỗi post_id
                post_output_file = os.path.join(OUTPUT_DIR, f"{post_id}_info.json")
                with open(post_output_file, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                print(f"💾 Đã lưu kết quả vào: {post_output_file}")
        
        return results
        
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
    print("\n" + "="*70)
    print("🚀 BẮT ĐẦU XỬ LÝ TẤT CẢ POST IDs")
    print("="*70)
    print("ℹ️  Mỗi file sẽ tự động sử dụng profile_id từ tên file")
    print("="*70)
    
    # Lấy tất cả file JSON trong thư mục
    post_ids_path = Path(POST_IDS_DIR)
    if not post_ids_path.exists():
        print(f"❌ Không tìm thấy thư mục: {POST_IDS_DIR}")
        return
    
    json_files = list(post_ids_path.glob("*.json"))
    
    if not json_files:
        print(f"⚠️ Không tìm thấy file JSON nào trong {POST_IDS_DIR}")
        return
    
    print(f"📁 Tìm thấy {len(json_files)} file(s) JSON")
    
    all_results = {}
    
    # Xử lý từng file (mỗi file sẽ tự động extract profile_id từ tên file)
    for file_path in json_files:
        file_name = file_path.name
        results = process_post_ids_file(str(file_path))
        all_results[file_name] = results
    
    # Lưu kết quả tổng hợp
    summary_file = os.path.join(OUTPUT_DIR, "all_results_summary.json")
    summary = {
        "total_files": len(json_files),
        "results_by_file": all_results,
        "total_posts_processed": sum(len(results) for results in all_results.values()),
        "total_reactions": sum(
            sum(r.get("reactions_count", 0) for r in results)
            for results in all_results.values()
        ),
        "total_comments": sum(
            sum(r.get("comments_count", 0) for r in results)
            for results in all_results.values()
        )
    }
    
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    print("\n" + "="*70)
    print("✅ HOÀN THÀNH XỬ LÝ TẤT CẢ POST IDs")
    print("="*70)
    print(f"📊 Tổng số file đã xử lý: {len(json_files)}")
    print(f"📊 Tổng số post đã xử lý: {summary['total_posts_processed']}")
    print(f"📊 Tổng số reactions: {summary['total_reactions']}")
    print(f"📊 Tổng số comments: {summary['total_comments']}")
    print(f"💾 Đã lưu kết quả tổng hợp vào: {summary_file}")
    print("="*70)


if __name__ == "__main__":
    get_all_info_from_post_ids_dir()

