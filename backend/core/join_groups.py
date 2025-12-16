import sys
import os
import json
import time
import random

# --- SETUP ĐƯỜNG DẪN ĐỂ IMPORT CORE ---
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from core.nst import connect_profile
from core.browser import FBController

class GroupJoiner(FBController):
    """
    Class chuyên dụng để đi xin vào nhóm
    """
    def join_group(self, group_id):
        url = f"https://www.facebook.com/groups/{group_id}"
        print(f"\n🚀 Đang truy cập nhóm: {group_id}")
        print(f"🔗 Link: {url}")
        
        try:
            self.goto(url)
            time.sleep(random.uniform(3, 5)) # Chờ load trang

            # 1. Kiểm tra xem đã tham gia chưa
            is_joined = self.page.query_selector('div[aria-label="Đã tham gia"], div[aria-label="Mời"]')
            if is_joined:
                print(f"✅ [SKIP] Đã là thành viên của nhóm {group_id}")
                return False

            # 2. Tìm nút "Tham gia nhóm"
            join_btn_selector = 'div[aria-label="Tham gia nhóm"][role="button"]'
            join_btn = self.page.query_selector(join_btn_selector)

            if not join_btn:
                join_btn = self.page.get_by_text("Tham gia nhóm", exact=True).first
            
            if join_btn:
                print("point 👉 Tìm thấy nút 'Tham gia nhóm'. Đang click...")
                join_btn.click()
                
                # ======================================================
                # [MỚI] ẤN ESC 2 LẦN ĐỂ TẮT POPUP CÂU HỎI / NỘI QUY
                # ======================================================
                # Thay sleep cứng bằng auto-wait popup/dialog
                # ======================================================
                try:
                    # Chờ popup dialog (nếu có) rồi đóng
                    self.page.wait_for_selector('div[role="dialog"]', timeout=3000)
                    self.page.keyboard.press("Escape")
                except:
                    pass
                
                try:
                    # Chờ UI cập nhật sau khi đóng popup (không sleep cứng)
                    self.page.wait_for_timeout(800)
                except:
                    pass
                
                # 3. Kiểm tra lại trạng thái
                # Nếu nút chuyển thành "Hủy yêu cầu" hoặc "Đã tham gia" -> Thành công
                check_success = self.page.query_selector('div[aria-label="Hủy yêu cầu"], div[aria-label="Đã tham gia"]')
                
                if check_success:
                    print(f"✅ Đã gửi yêu cầu tham gia thành công: {group_id}")
                else:
                    # Nếu vẫn còn nút tham gia -> Có thể do chưa trả lời câu hỏi bắt buộc
                    print(f"⚠️ Đã click nhưng chưa thấy đổi trạng thái (Có thể cần trả lời câu hỏi bắt buộc): {group_id}")
                
                return True
            else:
                print(f"❌ Không tìm thấy nút tham gia (Có thể nhóm kín, bị chặn, hoặc layout khác).")
                return False

        except Exception as e:
            print(f"❌ Lỗi khi xử lý nhóm {group_id}: {e}")
            return False

def run_batch_join(profile_id, json_file_path):
    # 1. Đọc file JSON
    try:
        with open(json_file_path, "r", encoding="utf-8") as f:
            group_ids = json.load(f)
        
        if not group_ids:
            print("⚠️ File JSON rỗng.")
            return
            
        print(f"📋 Tìm thấy {len(group_ids)} nhóm cần tham gia.")
        
    except Exception as e:
        print(f"❌ Lỗi đọc file JSON: {e}")
        return

    # 2. Kết nối Profile
    try:
        print(f"🔌 Đang kết nối profile {profile_id}...")
        ws_url = connect_profile(profile_id)
        fb = GroupJoiner(ws_url)
        fb.profile_id = profile_id
        fb.connect()
        
        # 3. Chạy vòng lặp
        for gid in group_ids:
            fb.join_group(gid)
            
            # Nghỉ ngẫu nhiên
            sleep_time = random.uniform(10, 20) 
            print(f"💤 Nghỉ {sleep_time:.1f}s trước khi qua nhóm tiếp theo...")
            time.sleep(sleep_time)
            
    except Exception as e:
        print(f"❌ Lỗi kết nối/browser: {e}")
    finally:
        print("🏁 Hoàn tất danh sách.")
        # fb.browser.close() 

if __name__ == "__main__":
    # --- CẤU HÌNH ---
    MY_PROFILE_ID = "621e1f5d-0c42-481e-9ddd-7abaafce68ed" 
    JSON_PATH = os.path.join(parent_dir, "data", "groups.json")
    
    run_batch_join(MY_PROFILE_ID, JSON_PATH)