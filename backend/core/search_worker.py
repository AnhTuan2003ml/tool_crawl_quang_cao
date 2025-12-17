import sys
import os
import urllib.parse
import time

# --- SETUP ĐƯỜNG DẪN ĐỂ IMPORT CORE ---
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from core.nst import connect_profile
from core.browser import FBController, JS_EXPAND_SCRIPT, JS_CHECK_AND_HIGHLIGHT_SCOPED
from core.scraper import SimpleBot

# ==============================================================================
# CLASS CONTROLLER MỚI (CHỈ LIKE, KHÔNG SHARE/SAVE)
# ==============================================================================
class SearchBotController(FBController):
    """
    Kế thừa FBController nhưng sửa lại hàm process_post
    để chỉ thực hiện hành động Like, bỏ qua Share và Save ID.
    """
    def process_post(self, post_handle, post_type):
        try:
            print(f"🧠 [FilterMode] Đang soi bài viết (type={post_type})...")

            # 1. Expand nội dung (để check keyword cho chuẩn)
            self.page.evaluate(JS_EXPAND_SCRIPT, post_handle)

            # 2. Check keyword
            has_keyword = self.page.evaluate(
                JS_CHECK_AND_HIGHLIGHT_SCOPED,
                [post_handle, self.job_keywords]
            )

            if not has_keyword:
                print("❌ Không có keyword -> Bỏ qua")
                self.mark_post_as_processed(post_handle)
                
                # Đẩy bài viết lên để bot không bị kẹt
                try:
                    viewport = self.page.viewport_size
                    height = viewport['height'] if viewport else 800
                    self.page.mouse.wheel(0, height * 0.4)
                except: pass
                
                return False

            print("✅ Phát hiện bài có Keyword phù hợp!")

            # 3. THỰC HIỆN LIKE (Quan trọng nhất)
            self.like_current_post(post_handle)

            # 4. Đánh dấu đã xử lý (Để bot lướt tiếp bài sau)
            self.mark_post_as_processed(post_handle)
            
            return True

        except Exception as e:
            print(f"❌ Lỗi process_post: {e}")
            return False

# ==============================================================================
# HÀM 1: TÌM KIẾM & LIKE (Trang Search)
# ==============================================================================
def search_and_like(profile_id: str, search_text: str, duration_minutes: int = 30):
    """Nhập từ khóa -> Vào trang Search -> Lướt & Like bài có từ khóa"""
    try:
        # 1. Tạo URL Tìm kiếm
        encoded_query = urllib.parse.quote_plus(search_text)
        target_url = f"https://www.facebook.com/search/posts?q={encoded_query}"
        
        print(f"🔍 [Search] Từ khóa: '{search_text}'")
        print(f"🔗 Link: {target_url}")

        _run_bot_logic(profile_id, target_url, search_text, duration_minutes)

    except Exception as e:
        print(f"❌ Lỗi search_and_like: {e}")

# ==============================================================================
# HÀM 2: LƯỚT NEWFEED & LIKE (Trang Chủ)
# ==============================================================================
def feed_and_like(profile_id: str, filter_text: str, duration_minutes: int = 30):
    """Vào trang chủ (Feed) -> Lướt -> Chỉ Like bài nào chứa filter_text"""
    try:
        # 1. URL là Trang chủ
        target_url = "https://www.facebook.com/"
        
        print(f"🏠 [Feed] Lướt News Feed tìm từ khóa: '{filter_text}'")
        
        _run_bot_logic(profile_id, target_url, filter_text, duration_minutes)

    except Exception as e:
        print(f"❌ Lỗi feed_and_like: {e}")

# ==============================================================================
# HÀM CHẠY CHUNG (CORE LOGIC)
# ==============================================================================
def _run_bot_logic(profile_id, url, keywords_str, duration_minutes):
    try:
        # 1. Kết nối
        print(f"🚀 Đang mở profile: {profile_id}")
        ws_url = connect_profile(profile_id)
        
        # Dùng Controller đã cắt bỏ Share/Save
        fb = SearchBotController(ws_url)
        fb.profile_id = profile_id
        fb.connect()

        # 2. Inject Keywords
        # Bot sẽ chỉ dừng lại Like nếu bài viết chứa các từ này
        if keywords_str:
            new_keywords = [keywords_str] + keywords_str.split()
            fb.job_keywords.extend(new_keywords)
            # Lọc trùng và từ quá ngắn
            fb.job_keywords = list(set([k for k in fb.job_keywords if len(k) > 1]))
            print(f"✅ Filter Keywords: {fb.job_keywords}")
        
        # 3. Chạy Bot
        bot = SimpleBot(fb)
        print(f"▶️ Bắt đầu lướt trong {duration_minutes} phút...")
        duration_seconds = duration_minutes * 60
        
        bot.run(url, duration=duration_seconds)
        
    except Exception as e:
        print(f"❌ Lỗi Runner: {e}")
    finally:
        print("🛑 Kết thúc.")

if __name__ == "__main__":
    # --- TEST ---
    TEST_ID = "621e1f5d-0c42-481e-9ddd-7abaafce68ed"
    "3013041542259942",
    "1884004131909284"
    print("--- CHỌN CHẾ ĐỘ ---")
    print("1. Search & Like (Vào trang tìm kiếm)")
    print("2. Feed & Like (Lướt trang chủ)")
    mode = input("Nhập 1 hoặc 2: ")
    
    text = "bắc ninh bắc giang"
    
    if mode == "1":
        search_and_like(TEST_ID, text, duration_minutes=15)
    elif mode == "2":
        feed_and_like(TEST_ID, text, duration_minutes=15)