import json
import os
from pathlib import Path
from single_get_reactions import get_all_users_by_fid
from single_get_comment import get_all_comments_by_post_id

# ====== ĐƯỜNG DẪN ======
POST_IDS_DIR = "data/post_ids"
OUTPUT_DIR = "data/results"

# Tạo thư mục output nếu chưa có
os.makedirs(OUTPUT_DIR, exist_ok=True)


def process_post_id(post_id, file_name):
    """
    Xử lý một post_id: lấy reactions và comments
    
    Args:
        post_id (str): Facebook ID của post
        file_name (str): Tên file JSON chứa post_id này
        
    Returns:
        dict: Kết quả với reactions và comments
    """
    print("\n" + "="*70)
    print(f"📌 Xử lý Post ID: {post_id}")
    print(f"📁 Từ file: {file_name}")
    print("="*70)
    
    result = {
        "post_id": post_id,
        "source_file": file_name,
        "reactions": [],
        "comments": [],
        "reactions_count": 0,
        "comments_count": 0,
        "status": "success"
    }
    
    try:
        # 1. Lấy reactions
        print(f"\n🔵 Bắt đầu lấy REACTIONS cho post_id: {post_id}")
        reactions = get_all_users_by_fid(post_id)
        result["reactions"] = reactions
        result["reactions_count"] = len(reactions)
        print(f"✅ Đã lấy được {len(reactions)} reactions")
        
        # 2. Lấy comments
        print(f"\n🟢 Bắt đầu lấy COMMENTS cho post_id: {post_id}")
        comments = get_all_comments_by_post_id(post_id)
        result["comments"] = comments
        result["comments_count"] = len(comments)
        print(f"✅ Đã lấy được {len(comments)} comments")
        
    except Exception as e:
        print(f"❌ Lỗi khi xử lý post_id {post_id}: {e}")
        import traceback
        traceback.print_exc()
        result["status"] = "error"
        result["error"] = str(e)
    
    return result


def process_post_ids_file(file_path):
    """
    Xử lý một file JSON chứa danh sách post_ids
    
    Args:
        file_path (str): Đường dẫn đến file JSON
        
    Returns:
        list: Danh sách kết quả của tất cả post_ids trong file
    """
    file_name = os.path.basename(file_path)
    print("\n" + "="*70)
    print(f"📂 Đang xử lý file: {file_name}")
    print("="*70)
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            post_ids = json.load(f)
        
        if not isinstance(post_ids, list):
            print(f"⚠️ File {file_name} không chứa mảng post_ids")
            return []
        
        print(f"📋 Tìm thấy {len(post_ids)} post_ids trong file")
        
        results = []
        for i, post_id in enumerate(post_ids, 1):
            print(f"\n{'='*70}")
            print(f"📌 [{i}/{len(post_ids)}] Xử lý Post ID: {post_id}")
            print(f"{'='*70}")
            
            result = process_post_id(post_id, file_name)
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
    """
    print("\n" + "="*70)
    print("🚀 BẮT ĐẦU XỬ LÝ TẤT CẢ POST IDs")
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
    
    # Xử lý từng file
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

