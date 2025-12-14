import os
import time
from dotenv import load_dotenv
from core.nst import connect_profile
from core.browser import FBController

load_dotenv()

def test_check_resolution():
    profile_list = os.getenv("PROFILE_IDS", "").split(",")
    profile_id = profile_list[0].strip()
    
    if not profile_id:
        print("❌ Lỗi: Không tìm thấy PROFILE_IDS")
        return

    print(f"🧪 Đang test Profile: {profile_id}")

    try:
        ws_url = connect_profile(profile_id)
        fb = FBController(ws_url)
        fb.profile_id = profile_id
        
        # Kết nối
        fb.connect() 
        
        # --- [ĐOẠN KIỂM TRA QUAN TRỌNG] ---
        # 1. Lấy thông số kích thước viewport thực tế
        vp = fb.page.viewport_size
        print(f"\n📊 KÍCH THƯỚC MÀN HÌNH HIỆN TẠI: {vp}")
        
        if vp and vp['width'] == 1920 and vp['height'] == 1080:
            print("✅ OK! Đã Full HD 1920x1080.")
        else:
            print("⚠️ CẢNH BÁO: Màn hình chưa Full HD! Bot có thể bị lỗi giao diện mobile.")

        # 2. Mở Facebook và chụp ảnh bằng chứng
        print("🚀 Đang vào Facebook để chụp ảnh...")
        fb.goto("https://www.facebook.com")
        time.sleep(5)
        
        fb.page.screenshot(path="debug_resolution.png")
        print("📸 Đã lưu ảnh: debug_resolution.png (Sếp mở lên xem có bị bé không)\n")
        # -----------------------------------

        # (Phần sau giữ nguyên logic share cũ để test tiếp...)
        # ...

    except Exception as e:
        print(f"❌ Lỗi: {e}")
    finally:
        print("🛑 Đóng trình duyệt...")
        try:
            if fb.browser: fb.browser.close()
            if fb.play: fb.play.stop()
        except: pass

if __name__ == "__main__":
    test_check_resolution()