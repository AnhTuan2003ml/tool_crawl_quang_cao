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
                detected_post, post_type = self.fb.scan_while_scrolling()
                
                # ============================================================
                # XỬ LÝ BÀI VIẾT TÌM THẤY
                # ============================================================
                detected_post, post_type = self.fb.scan_while_scrolling()

                if detected_post:
                    self.fb.process_post(detected_post, post_type)

                    # 💤 Nghỉ sau khi xử lý bài
                    delay = random.uniform(5.0, 10.0)
                    print(f"😴 Nghỉ sau khi xử lý bài {delay:.1f}s")
                    time.sleep(delay)

                else:
                    # 💤 Nghỉ khi scroll không gặp bài
                    delay = random.uniform(5.0, 10.0)
                    print(f"😴 Không có bài – nghỉ {delay:.1f}s")
                    time.sleep(delay)


                # Random mouse move nhẹ cho đỡ bị check bot
                
            
            except Exception as e:
                print(f"❌ Lỗi vòng lặp: {e}")
                time.sleep(2)