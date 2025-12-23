import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import json
import base64
from urllib.parse import urlencode
import os
from datetime import datetime
from pathlib import Path

# Import control state để check stop/pause
try:
    from backend.core.control import check_flags, wait_if_paused
except ImportError:
    try:
        from core.control import check_flags, wait_if_paused
    except ImportError:
        # Fallback: nếu không import được thì dùng dummy functions
        def check_flags(profile_id=None):
            return False, False, ""
        def wait_if_paused(profile_id=None, sleep_seconds=0.5):
            pass

# ====== LƯU Ý ======
# Cookies và payload được lấy từ cookies.json và payload.txt thông qua profile_id
# cookies.json có cấu trúc: {"profile_id": {"cookie": "...", "access_token": "..."}}
# Sử dụng get_payload.get_payload_by_profile_id(profile_id) để lấy payload
# Sử dụng get_payload.get_cookies_by_profile_id(profile_id) để lấy cookie

# ====== TẠO FEEDBACK TARGET ID TỪ FID ======
def create_feedback_target_id(fid):
    """Chuyển đổi fid thành feedbackTargetID bằng base64"""
    s = f"feedback:{fid}"
    feedback_target_id = base64.b64encode(s.encode()).decode()
    return feedback_target_id


# ================================
#   GỬI REQUEST GRAPHQL VỚI CURSOR
# ================================
def send_request(feedback_target_id, payload_dict, profile_id, cookies, cursor=None):
    """Gửi request GraphQL với feedbackTargetID và cursor (nếu có)"""
    
    # Payload dưới dạng dictionary (từ điển)
    variables = {
        "count": 100,
        "feedbackTargetID": feedback_target_id,
        "reactionID": None,
        "scale": 1,
        "id": feedback_target_id
    }
    
    # Thêm cursor nếu có
    if cursor:
        variables["cursor"] = cursor
        print(f"   🔄 Sử dụng cursor: {cursor[:50]}...")
    else:
        print(f"   🔄 Không có cursor (trang đầu tiên)")
    
    # Debug: In ra variables để kiểm tra
    print(f"   📋 Variables: {json.dumps(variables, ensure_ascii=False)}")
    
    # Sử dụng payload được truyền vào và thêm variables, doc_id, fb_api_req_friendly_name
    payload_dict = payload_dict.copy()
    # If caller provided a forced payload dict under key "__force_payload", use/merge it
    force_payload = payload_dict.pop("__force_payload", None)
    if isinstance(force_payload, dict):
        # merge force_payload into payload_dict (force overrides)
        for k, v in force_payload.items():
            payload_dict[k] = v

    payload_dict["variables"] = json.dumps(variables, ensure_ascii=False)
    payload_dict["doc_id"] = "31470716059194219"
    payload_dict["fb_api_req_friendly_name"] = "CometUFIReactionsDialogTabContentRefetchQuery"

    # Chuyển dictionary thành form-urlencoded string
    payload = urlencode(payload_dict)

    # Tạo headers với cookies
    headers = {
        "accept": "*/*",
        "accept-encoding": "gzip, deflate",
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
    
    # Chuẩn bị session với retry để giảm timeout/connection reset
    session = requests.Session()
    retry_cfg = Retry(
        total=2,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["POST"],
    )
    adapter = HTTPAdapter(max_retries=retry_cfg)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    
    # Gửi payload dưới dạng form-urlencoded với headers
    response = session.post(url, data=payload, headers=headers, timeout=20)
    
    return response


# ================================
#   HÀM HOÀN CHỈNH: LẤY TẤT CẢ USERS TỪ FID
# ================================
def get_all_users_by_fid(fid, payload_dict, profile_id, cookies):
    """
    Hàm hoàn chỉnh để lấy tất cả users (id và name) từ FID
    
    Args:
        fid (str): Facebook ID của post/photo
        payload_dict (dict): Dictionary chứa payload parameters
        profile_id (str): Profile ID
        cookies (str): Cookie string để sử dụng trong request
        
    Returns:
        list: Danh sách users với format [{"id": "...", "name": "..."}, ...]
    """
    # Tạo feedbackTargetID từ FID
    feedback_target_id = create_feedback_target_id(fid)
    
    print("\n" + "="*50)
    print(f"🚀 Bắt đầu lấy users từ FID: {fid}")
    print(f"🔗 FeedbackTargetID: {feedback_target_id}")
    print("="*50)
    
    all_users = []
    seen_ids = set()  # Set để track các id đã thấy, tránh trùng lặp
    cursor = None
    page_number = 1
    duplicate_count = 0  # Đếm số user trùng đã bỏ qua
    
    while True:
        # Check stop/pause trước mỗi request
        try:
            stop, paused, reason = check_flags(profile_id)
            if stop:
                print(f"🛑 Dừng lấy reactions do stop: {reason}")
                raise RuntimeError(f"EMERGENCY_STOP ({reason})")
            if paused:
                print(f"⏸️ Đang tạm dừng ({reason}), chờ tiếp tục...")
                wait_if_paused(profile_id, sleep_seconds=0.5)
                continue  # Tiếp tục check sau khi resume
        except RuntimeError:
            raise  # Re-raise RuntimeError để caller có thể catch
        except Exception as e:
            print(f"⚠️ Lỗi khi check stop/pause: {e}")
            # Tiếp tục nếu có lỗi check
        
        print(f"\n📄 Trang {page_number} - Đang gửi request...")
        if cursor:
            print(f"   Cursor: {cursor[:50]}...")
        
        # Gửi request với feedbackTargetID, payload, profile_id, cookies và cursor
        response = send_request(feedback_target_id, payload_dict, profile_id, cookies, cursor)
        
        print(f"   STATUS: {response.status_code}")

        # Decode response text for inspection (no file saving)
        saved_text = ""
        content_encoding = (response.headers.get("content-encoding") or "").lower()
        if "br" in content_encoding:
            try:
                import brotli
                saved_text = brotli.decompress(response.content).decode("utf-8", errors="replace")
            except Exception as e:
                print(f"   ⚠️ Brotli decompress failed: {e}")
                try:
                    saved_text = (response.content or b"").decode("utf-8", errors="replace")
                except Exception:
                    saved_text = ""
        else:
            # rely on requests to handle gzip/deflate; fall back to manual decode
            try:
                saved_text = response.text or ""
            except Exception:
                try:
                    saved_text = (response.content or b"").decode("utf-8", errors="replace")
                except Exception:
                    saved_text = ""

        if response.status_code != 200:
            print(f"❌ Lỗi: Status code {response.status_code}")
            break
        
        # Parse response thành JSON
        try:
            response_json = response.json()
            
            # Debug: Kiểm tra cấu trúc response
            if "data" not in response_json:
                print(f"   ⚠️ Response không có 'data': {list(response_json.keys())}")
            if "errors" in response_json:
                print(f"   ❌ Response có errors: {response_json.get('errors')}")
            
            # Trích xuất id và name từ mỗi node
            try:
                reactors = response_json.get("data", {}).get("node", {}).get("reactors", {})
                edges = reactors.get("edges", [])
                page_info = reactors.get("page_info", {})
                end_cursor = page_info.get("end_cursor")
                has_next_page = page_info.get("has_next_page", False)
                
                print(f"   🔍 Debug: Số edges trong response: {len(edges)}")
                if len(edges) == 0:
                    print(f"   ⚠️ Không có edges trong response!")
                    print(f"   🔍 Debug: Reactors keys: {list(reactors.keys()) if reactors else 'None'}")
                    print(f"   🔍 Debug: Data structure: {json.dumps(response_json.get('data', {}), indent=2, ensure_ascii=False)[:500]}")
                elif len(edges) > 0:
                    # Debug: In ra node đầu tiên để kiểm tra
                    first_node = edges[0].get("node", {})
                    first_id = first_node.get("id")
                    first_name = first_node.get("name")
                    print(f"   🔍 Debug node đầu tiên: id={first_id}, name={first_name}, đã có trong seen_ids: {first_id in seen_ids if first_id else 'N/A'}")
                
                page_users = []
                last_cursor = None
                
                for edge in edges:
                    node = edge.get("node", {})
                    node_id = node.get("id")
                    node_name = node.get("name")
                    edge_cursor = edge.get("cursor")  # Lấy cursor từ edge
                    
                    # Debug: In ra node đầu tiên để kiểm tra
                    if len(page_users) == 0 and len(edges) > 0:
                        print(f"   🔍 Debug node đầu tiên: id={node_id}, name={node_name}, node_keys={list(node.keys())}")
                    
                    if node_id and node_name:
                        # Kiểm tra xem id đã tồn tại chưa
                        if node_id not in seen_ids:
                            seen_ids.add(node_id)
                            page_users.append({
                                "id": node_id,
                                "name": node_name
                            })
                        else:
                            duplicate_count += 1
                    elif not node_id:
                        print(f"   ⚠️ Node không có id: {node}")
                    elif not node_name:
                        print(f"   ⚠️ Node không có name: id={node_id}")
                    
                    # Lưu cursor của edge cuối cùng
                    if edge_cursor:
                        last_cursor = edge_cursor
                
                all_users.extend(page_users)
                
                # Sử dụng end_cursor từ page_info (theo yêu cầu)
                next_cursor = end_cursor
                
                print(f"   ✅ Lấy được {len(page_users)} users mới (Tổng: {len(all_users)}, Trùng: {duplicate_count})")
                print(f"   🔗 End cursor (page_info): {end_cursor[:50] if end_cursor else 'None'}...")
                print(f"   🔗 Last cursor (edge): {last_cursor[:50] if last_cursor else 'None'}...")
                print(f"   🔗 Next cursor sẽ dùng: {next_cursor[:50] if next_cursor else 'None'}...")
                print(f"   📄 Has next page: {has_next_page}")
                
                # Kiểm tra có trang tiếp theo không
                if not has_next_page:
                    print(f"\n✅ Đã lấy hết tất cả users! (has_next_page = False)")
                    break
                
                if not next_cursor:
                    print(f"\n⚠️ Không có cursor để tiếp tục, dừng lại")
                    break
                
                # Cập nhật cursor cho lần lặp tiếp theo
                cursor = next_cursor
                page_number += 1
                print(f"   ➡️ Cursor đã được cập nhật: {cursor[:50]}...")
                
            except Exception as e:
                print(f"⚠️ Lỗi khi trích xuất nodes: {e}")
                break
                
        except json.JSONDecodeError as e:
            print(f"❌ Lỗi: Response không phải JSON hợp lệ")
            print(f"   Chi tiết: {e}")
            # Attempt to extract dynamic payload values (fb_dtsg, lsd, __spin_r, __spin_t)
            try:
                from get_payload import ensure_payload_from_bad_response, get_payload_by_profile_id, update_payload_file
                print("ℹ️ Thực hiện headless capture để lấy các giá trị động và cập nhật settings.json/payload.txt...")
                payload_values = ensure_payload_from_bad_response(profile_id, cookies, response_text=saved_text, timeout=8)
                if not payload_values:
                    print("❌ Headless capture không trả về giá trị nào, dừng.")
                    break

                # Update payload.txt with discovered dynamic values
                try:
                    updated = update_payload_file(payload_values)
                    if updated:
                        print("✅ Đã cập nhật backend/config/payload.txt từ headless capture")
                    else:
                        print("⚠️ Không thể cập nhật backend/config/payload.txt từ headless capture")
                except Exception as e_up:
                    print(f"⚠️ Lỗi khi cập nhật payload.txt: {e_up}")

                # Rebuild payload_dict from updated payload.txt / settings.json and retry once
                payload_dict = get_payload_by_profile_id(profile_id)
                if payload_dict:
                    print("ℹ️ Thử gửi lại request sau khi cập nhật payload...")
                    response = send_request(feedback_target_id, payload_dict, profile_id, cookies, cursor)
                    try:
                        response_json = response.json()
                        print("✅ Retry thành công, response JSON hợp lệ.")
                        # continue processing with new response_json
                    except Exception as e2:
                        print(f"❌ Retry vẫn không trả về JSON hợp lệ: {e2}")
                        break
                else:
                    print("❌ Không thể tạo payload mới từ payload.txt/settings.json, dừng.")
                    break
            except Exception as ee:
                print(f"⚠️ Lỗi khi cố gắng fix bằng headless: {ee}")
                break
    
    # Hiển thị kết quả
    print(f"\n" + "="*50)
    print(f"✅ Hoàn thành!")
    print(f"📊 Tổng số users (sau khi lọc trùng): {len(all_users)}")
    print(f"🔄 Số user trùng đã bỏ qua: {duplicate_count}")
    print(f"📄 Tổng số trang: {page_number}")
    print(f"\n📋 Danh sách users (10 đầu tiên):")
    for i, user in enumerate(all_users[:10], 1):
        print(f"  {i}. ID: {user['id']}, Name: {user['name']}")
    if len(all_users) > 10:
        print(f"  ... và {len(all_users) - 10} users khác")
    
    # Lưu vào file
    if all_users:
        extracted_data = {
            "users": all_users,
            "total_users": len(all_users),
            "duplicate_users_skipped": duplicate_count,
            "total_pages": page_number,
            "fid": fid,
            "feedback_target_id": feedback_target_id
        }
        
        print(f"\n✅ Đã lấy {len(all_users)} users")
    else:
        print("\n⚠️ Không có users")
    
    print("="*50)
    
    return all_users


# ================================
#   HÀM ĐƠN GIẢN: LẤY USERS TỪ CURSOR
# ================================
def get_users_by_cursor(fid, payload_dict, profile_id, cookies, cursor=None):
    """
    Hàm đơn giản: truyền cursor vào, trả về users (id, name) và end_cursor
    
    Args:
        fid (str): Facebook ID của post/photo
        payload_dict (dict): Dictionary chứa payload parameters
        profile_id (str): Profile ID
        cookies (str): Cookie string để sử dụng trong request
        cursor (str, optional): Cursor để lấy trang tiếp theo. None nếu là trang đầu tiên
        
    Returns:
        dict: {
            "users": [{"id": "...", "name": "..."}, ...],
            "end_cursor": "...",
            "has_next_page": bool
        }
    """
    # Tạo feedbackTargetID từ FID
    feedback_target_id = create_feedback_target_id(fid)
    
    # Gửi request
    response = send_request(feedback_target_id, payload_dict, profile_id, cookies, cursor)
    
    if response.status_code != 200:
        print(f"❌ Lỗi: Status code {response.status_code}")
        return {"users": [], "end_cursor": None, "has_next_page": False}
    
    # Parse response
    try:
        response_json = response.json()
        reactors = response_json.get("data", {}).get("node", {}).get("reactors", {})
        edges = reactors.get("edges", [])
        page_info = reactors.get("page_info", {})
        end_cursor = page_info.get("end_cursor")
        has_next_page = page_info.get("has_next_page", False)
        
        # Tách lấy users (id và name)
        users = []
        for edge in edges:
            node = edge.get("node", {})
            node_id = node.get("id")
            node_name = node.get("name")
            
            if node_id and node_name:
                users.append({
                    "id": node_id,
                    "name": node_name
                })
        
        return {
            "users": users,
            "end_cursor": end_cursor,
            "has_next_page": has_next_page
        }
        
    except json.JSONDecodeError as e:
        print(f"❌ Lỗi: Response không phải JSON hợp lệ: {e}")
        return {"users": [], "end_cursor": None, "has_next_page": False}
    except Exception as e:
        print(f"❌ Lỗi khi parse response: {e}")
        return {"users": [], "end_cursor": None, "has_next_page": False}


# ================================
#   HÀM GỌI CŨ (giữ lại để tương thích)
# ================================
def call_graphql(fid=None, profile_id=None):
    """Hàm wrapper để gọi get_all_users_by_fid"""
    if fid is None:
        fid = "965661076626843"  # FID mặc định
    
    if profile_id is None:
        profile_id = "031ca13d-e8fa-400c-a603-df57a2806788"  # Profile ID mặc định
    
    from get_payload import get_payload_by_profile_id, get_cookies_by_profile_id
    
    payload_dict = get_payload_by_profile_id(profile_id)
    cookies = get_cookies_by_profile_id(profile_id)
    
    if payload_dict and cookies:
        all_users = get_all_users_by_fid(fid, payload_dict, profile_id, cookies)
    else:
        print("❌ Không thể tạo payload dictionary hoặc lấy cookies")
        all_users = []
    
    # Hiển thị kết quả
    if all_users:
        print(f"\n✅ Đã lấy {len(all_users)} users")
    else:
        print("\n⚠️ Không lấy được users nào")


if __name__ == "__main__":
    # Ví dụ sử dụng hàm hoàn chỉnh với vòng lặp tự động
    from get_payload import get_payload_by_profile_id, get_cookies_by_profile_id
    
    profile_id = "b77da63d-af55-43c2-ab7f-364250b20e30"
    payload_dict = get_payload_by_profile_id(profile_id)
    cookies = get_cookies_by_profile_id(profile_id)
    
    if payload_dict and cookies:
        fid = "2672966333102287"  # Thay đổi FID ở đây
        users = get_all_users_by_fid(fid, payload_dict, profile_id, cookies)
