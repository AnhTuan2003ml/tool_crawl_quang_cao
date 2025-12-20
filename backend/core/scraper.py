import time
import random
import os

class SimpleBot:
    def __init__(self, fb):
        self.fb = fb 

    def run(self, url, duration=None):
        print(f"🚀 Đang truy cập: {url}")
        self.fb.goto(url) 
        
        start_time = time.time()
        
        while True:
            try:
                # 1. Kiểm tra thời gian chạy
                if duration and (time.time() - start_time > duration):
                    print("⏳ Hết giờ chạy.")
                    break
                
                # ============================================================
                # CHIẾN THUẬT: SCAN & SCROLL (ĐỒNG BỘ)
                # ============================================================
                
                # Bot cuộn và trả về bài viết (nếu có) cùng loại (green/yellow)
                post, post_type = self.fb.scan_while_scrolling()

                if post:
                    self.fb.process_post(post, post_type)

                    delay = random.uniform(5.0, 8.0)
                    print(f"😴 Nghỉ sau khi xử lý bài {delay:.1f}s")
                    time.sleep(delay)
                else:
                    delay = random.uniform(3.0, 5.0)
                    print(f"😴 Không có bài – nghỉ {delay:.1f}s")
                    time.sleep(delay)



                # Random mouse move nhẹ cho đỡ bị check bot
                
            
            except RuntimeError as e:
                # Nếu là exception đặc biệt BROWSER_CLOSED thì dừng ngay
                if "BROWSER_CLOSED" in str(e):
                    print(f"🛑 Browser đã bị đóng -> Dừng bot ngay lập tức")
                    break
                raise  # Re-raise nếu không phải BROWSER_CLOSED
            except Exception as e:
                error_msg = str(e).lower()
                # Nếu browser/page đã bị đóng thì dừng luôn
                if any(keyword in error_msg for keyword in ["closed", "disconnected", "target page", "context or browser"]):
                    print(f"🛑 Browser đã bị đóng -> Dừng bot")
                    break
                print(f"⚠️ Lỗi scan: {e}")
                time.sleep(2)