import requests
import json
import base64
from urllib.parse import urlencode

# ====== LƯU Ý ======
# Cookies và payload được lấy từ cookies.json và payload.txt thông qua profile_id
# cookies.json có cấu trúc: {"profile_id": {"cookie": "...", "access_token": "..."}}
# Sử dụng get_payload.get_payload_by_profile_id(profile_id) để lấy payload
# Sử dụng get_payload.get_cookies_by_profile_id(profile_id) để lấy cookie

# ====== TẠO FEEDBACK ID TỪ POST_ID ======
def create_feedback_id(post_id):
    """Chuyển đổi post_id thành feedback ID bằng base64"""
    s = f"feedback:{post_id}"
    feedback_id = base64.b64encode(s.encode()).decode()
    return feedback_id


# ====== EXTRACT USERS TỪ JSON ======
def extract_users_from_json(data, users_list, seen_ids):
    """
    Đệ quy để tìm tất cả các user objects trong JSON structure và lấy text của comment
    
    Args:
        data: JSON data (dict, list, hoặc primitive)
        users_list: List để lưu các user đã tìm thấy
        seen_ids: Set để track các id đã thấy, tránh trùng lặp
    """
    if isinstance(data, dict):
        # Nếu có key "user" và value là dict có "id" và "name"
        if "user" in data and isinstance(data["user"], dict):
            user = data["user"]
            user_id = user.get("id")
            user_name = user.get("name")
            
            # Lấy text từ body nếu có
            comment_text = None
            if "body" in data and isinstance(data["body"], dict):
                comment_text = data["body"].get("text")
            
            if user_id and user_name:
                # Tạo key duy nhất từ user_id và text (để tránh trùng comment)
                unique_key = f"{user_id}_{comment_text}" if comment_text else user_id
                
                # Chỉ thêm nếu chưa có trong seen_ids
                if unique_key not in seen_ids:
                    seen_ids.add(unique_key)
                    users_list.append({
                        "id": user_id,
                        "name": user_name,
                        "text": comment_text if comment_text else ""
                    })
        
        # Đệ quy vào tất cả các values
        for value in data.values():
            extract_users_from_json(value, users_list, seen_ids)
    
    elif isinstance(data, list):
        # Đệ quy vào tất cả các items trong list
        for item in data:
            extract_users_from_json(item, users_list, seen_ids)


# ================================
#   GỬI REQUEST GRAPHQL VỚI CURSOR
# ================================
def send_request(post_id, payload_dict, profile_id, cookies, commentsAfterCursor=None):
    """Gửi request GraphQL để lấy comments với post_id và commentsAfterCursor (nếu có)"""
    
    # Tạo feedback ID từ post_id
    feedback_id = create_feedback_id(post_id)
    
    # Variables cho comments API
    variables = {
        "commentsAfterCount": -1,
        "commentsAfterCursor": commentsAfterCursor if commentsAfterCursor else None,
        "commentsBeforeCount": None,
        "commentsBeforeCursor": None,
        "commentsIntentToken": "RANKED_UNFILTERED_CHRONOLOGICAL_REPLIES_INTENT_V1",
        "feedLocation": "POST_PERMALINK_DIALOG",
        "focusCommentID": None,
        "scale": 1,
        "useDefaultActor": False,
        "id": feedback_id,
        "__relay_internal__pv__CometUFICommentAvatarStickerAnimatedImagerelayprovider": False,
        "__relay_internal__pv__IsWorkUserrelayprovider": False
    }
    
    # Thêm commentsAfterCursor nếu có
    if commentsAfterCursor:
        print(f"   🔄 Sử dụng commentsAfterCursor: {commentsAfterCursor[:50]}...")
    else:
        print(f"   🔄 Không có commentsAfterCursor (trang đầu tiên)")
    
    # Debug: In ra variables để kiểm tra
    print(f"   📋 Variables: {json.dumps(variables, ensure_ascii=False)}")
    
    # Sử dụng payload được truyền vào và thêm variables, doc_id, fb_api_req_friendly_name, __crn
    payload_dict = payload_dict.copy()
    payload_dict["variables"] = json.dumps(variables, ensure_ascii=False)
    payload_dict["doc_id"] = "25515916584706508"
    payload_dict["fb_api_req_friendly_name"] = "CommentListComponentsRootQuery"
    payload_dict["__crn"] = "comet.fbweb.CometSinglePostDialogRoute"  # Route riêng cho comments

    # Chuyển dictionary thành form-urlencoded string
    payload = urlencode(payload_dict)
    
    # Debug: In ra payload để kiểm tra (chỉ 500 ký tự đầu)
    print(f"   🔍 Payload preview: {payload[:500]}...")

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
        "x-fb-friendly-name": "CommentListComponentsRootQuery",
        "x-fb-lsd": payload_dict.get("lsd", "")
    }

    url = "https://www.facebook.com/api/graphql/"
    
    # Gửi payload dưới dạng form-urlencoded với headers
    response = requests.post(url, data=payload, headers=headers)
    
    return response


# ================================
#   HÀM HOÀN CHỈNH: LẤY TẤT CẢ COMMENTS TỪ POST_ID
# ================================
def get_all_comments_by_post_id(post_id, payload_dict, profile_id, cookies):
    """
    Hàm hoàn chỉnh để lấy tất cả comments từ post_id
    
    Args:
        post_id (str): Facebook ID của post
        payload_dict (dict): Dictionary chứa payload parameters
        profile_id (str): Profile ID
        cookies (str): Cookie string để sử dụng trong request
        
    Returns:
        list: Danh sách comments với format [{"id": "...", "text": "...", "author": {...}}, ...]
    """
    # Tạo feedback ID từ post_id
    feedback_id = create_feedback_id(post_id)
    
    print("\n" + "="*50)
    print(f"🚀 Bắt đầu lấy comments từ Post ID: {post_id}")
    print(f"🔗 Feedback ID: {feedback_id}")
    print("="*50)
    
    all_responses = []  # Lưu tất cả response JSON
    all_users = []  # Lưu tất cả users từ comments
    seen_user_ids = set()  # Set để track các user id đã thấy
    cursors_info = {}  # Lưu thông tin cursors
    commentsAfterCursor = None  # Cursor để pagination
    page_number = 1
    
    while True:
        print(f"\n📄 Trang {page_number} - Đang gửi request...")
        if commentsAfterCursor:
            print(f"   CommentsAfterCursor: {commentsAfterCursor[:50]}...")
        
        # Gửi request với post_id, payload, profile_id, cookies và commentsAfterCursor
        response = send_request(post_id, payload_dict, profile_id, cookies, commentsAfterCursor)
        
        print(f"   STATUS: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ Lỗi: Status code {response.status_code}")
            print(f"   📋 Response text (500 ký tự đầu):")
            print(f"   {response.text[:500]}")
            
            # Thử parse JSON để xem có error message không
            try:
                error_json = response.json()
                if "errors" in error_json:
                    print(f"   ❌ Errors từ response: {json.dumps(error_json.get('errors'), indent=2, ensure_ascii=False)}")
                else:
                    print(f"   📋 Response JSON: {json.dumps(error_json, indent=2, ensure_ascii=False)[:1000]}")
            except:
                pass
            
            # Lưu response để debug
            with open("error_response_comment.txt", "w", encoding="utf-8") as f:
                f.write(f"Status Code: {response.status_code}\n")
                f.write(f"Headers: {dict(response.headers)}\n")
                f.write(f"\nResponse Text:\n{response.text}")
            print(f"   💾 Đã lưu response vào error_response_comment.txt")
            break
        
        # Parse response thành JSON
        try:
            response_json = response.json()
            
            # Lưu response vào list để lưu tất cả vào một file sau
            all_responses.append(response_json)
            
            # Extract users từ response JSON
            extract_users_from_json(response_json, all_users, seen_user_ids)
            
            # Debug: Kiểm tra cấu trúc response
            if "data" not in response_json:
                print(f"   ⚠️ Response không có 'data': {list(response_json.keys())}")
            if "errors" in response_json:
                print(f"   ❌ Response có errors: {response_json.get('errors')}")
            
            # Trích xuất page_info từ response
            try:
                # Cấu trúc response: data.node.comment_rendering_instance_for_feed_location.comments
                node = response_json.get("data", {}).get("node", {})
                comment_rendering = node.get("comment_rendering_instance_for_feed_location", {})
                comments = comment_rendering.get("comments", {})
                edges = comments.get("edges", [])
                page_info = comments.get("page_info", {})
                end_cursor = page_info.get("end_cursor")
                start_cursor = page_info.get("start_cursor")
                has_next_page = page_info.get("has_next_page", False)
                
                print(f"   🔍 Debug: Số edges trong response: {len(edges)}")
                print(f"   🔗 End cursor: {end_cursor if end_cursor else 'None'}")
                print(f"   🔗 Start cursor: {start_cursor if start_cursor else 'None'}")
                print(f"   📄 Has next page: {has_next_page}")
                
                # Lưu cursors vào dict (lưu của trang cuối cùng)
                cursors_info = {
                    "end_cursor": end_cursor,
                    "start_cursor": start_cursor,
                    "has_next_page": has_next_page,
                    "edges_count": len(edges),
                    "page_number": page_number
                }
                
                if len(edges) == 0:
                    print(f"   ⚠️ Không có edges trong response!")
                    print(f"   🔍 Debug: Comments keys: {list(comments.keys()) if comments else 'None'}")
                
                # Kiểm tra có trang tiếp theo không
                if not has_next_page:
                    print(f"\n✅ Đã lấy hết tất cả comments! (has_next_page = False)")
                    break
                
                if not end_cursor:
                    print(f"\n⚠️ Không có end_cursor để tiếp tục, dừng lại")
                    break
                
                # Cập nhật commentsAfterCursor cho lần lặp tiếp theo
                commentsAfterCursor = end_cursor
                page_number += 1
                print(f"   ➡️ CommentsAfterCursor đã được cập nhật: {commentsAfterCursor[:50]}...")
                
            except Exception as e:
                print(f"⚠️ Lỗi khi trích xuất page_info: {e}")
                import traceback
                traceback.print_exc()
                break
                
        except json.JSONDecodeError as e:
            print(f"❌ Lỗi: Response không phải JSON hợp lệ")
            print(f"   Chi tiết: {e}")
            # Lưu response để debug
            with open("response_debug.txt", "w", encoding="utf-8") as f:
                f.write(response.text)
            print(f"   Đã lưu response vào response_debug.txt")
            break
    
    # Hiển thị kết quả
    print(f"\n" + "="*50)
    print(f"✅ Hoàn thành!")
    print(f"📄 Tổng số response: {len(all_responses)}")
    
    # Hiển thị cursors info
    if cursors_info:
        print(f"   🔗 End cursor: {cursors_info.get('end_cursor', 'None')}")
        print(f"   🔗 Start cursor: {cursors_info.get('start_cursor', 'None')}")
    
    # Hiển thị users đã extract
    if all_users:
        print(f"\n📋 Danh sách users (10 đầu tiên):")
        for i, user in enumerate(all_users[:10], 1):
            text_preview = user.get('text', '')[:50] + "..." if len(user.get('text', '')) > 50 else user.get('text', '')
            print(f"  {i}. ID: {user['id']}, Name: {user['name']}, Text: {text_preview}")
        if len(all_users) > 10:
            print(f"  ... và {len(all_users) - 10} users khác")
    
    print("="*50)
    
    return all_users


# ================================
#   HÀM ĐƠN GIẢN: LẤY COMMENTS TỪ CURSOR
# ================================
def get_comments_by_cursor(post_id, payload_dict, profile_id, cookies, cursor=None):
    """
    Hàm đơn giản: truyền cursor vào, trả về comments và end_cursor
    
    Args:
        post_id (str): Facebook ID của post
        payload_dict (dict): Dictionary chứa payload parameters
        profile_id (str): Profile ID
        cookies (str): Cookie string để sử dụng trong request
        cursor (str, optional): Cursor để lấy trang tiếp theo. None nếu là trang đầu tiên
        
    Returns:
        dict: {
            "comments": [{"id": "...", "text": "...", "author": {...}}, ...],
            "end_cursor": "...",
            "has_next_page": bool
        }
    """
    # Gửi request
    response = send_request(post_id, payload_dict, profile_id, cookies, cursor)
    
    if response.status_code != 200:
        print(f"❌ Lỗi: Status code {response.status_code}")
        return {"comments": [], "end_cursor": None, "has_next_page": False}
    
    # Parse response
    try:
        response_json = response.json()
        node = response_json.get("data", {}).get("node", {})
        comments = node.get("comments", {})
        edges = comments.get("edges", [])
        page_info = comments.get("page_info", {})
        end_cursor = page_info.get("end_cursor")
        has_next_page = page_info.get("has_next_page", False)
        
        # Tách lấy comments
        comments_list = []
        for edge in edges:
            comment_node = edge.get("node", {})
            comment_id = comment_node.get("id")
            comment_text = comment_node.get("text")
            author = comment_node.get("author", {})
            
            if comment_id:
                comments_list.append({
                    "id": comment_id,
                    "text": comment_text,
                    "author": author
                })
        
        return {
            "comments": comments_list,
            "end_cursor": end_cursor,
            "has_next_page": has_next_page
        }
        
    except json.JSONDecodeError as e:
        print(f"❌ Lỗi: Response không phải JSON hợp lệ: {e}")
        return {"comments": [], "end_cursor": None, "has_next_page": False}
    except Exception as e:
        print(f"❌ Lỗi khi parse response: {e}")
        return {"comments": [], "end_cursor": None, "has_next_page": False}


if __name__ == "__main__":
    # Ví dụ sử dụng hàm hoàn chỉnh với vòng lặp tự động
    from get_payload import get_payload_by_profile_id, get_cookies_by_profile_id
    
    profile_id = "031ca13d-e8fa-400c-a603-df57a2806788"
    payload_dict = get_payload_by_profile_id(profile_id)
    cookies = get_cookies_by_profile_id(profile_id)
    
    if payload_dict and cookies:
        post_id = "2664708703928050"  # Thay đổi Post ID ở đây
        comments = get_all_comments_by_post_id(post_id, payload_dict, profile_id, cookies)

