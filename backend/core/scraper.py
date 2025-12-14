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
        
        # [THAY ĐỔI] Không cần đếm số lần cuộn để like random nữa
        # press_count = 0 
        
        while True:
            try:
                # 1. Kiểm tra thời gian chạy
                if duration and (time.time() - start_time > duration):
                    print("⏳ Hết giờ chạy.")
                    break

                # ============================================================
                # CHIẾN THUẬT: SCAN & SCROLL
                # ============================================================
                
                # Bot tự động cuộn, nếu thấy Ads thì dừng lại trả về element
                detected_ad = self.fb.scan_while_scrolling()
                
                # ============================================================
                # TRƯỜNG HỢP: BẮT ĐƯỢC ADS
                # ============================================================
                if detected_ad:
                    print("\n>>> 🎯 BẮT ĐƯỢC ADS KHI ĐANG TRƯỢT!")
                    
                    # Kiểm tra xem Ads có chứa từ khóa mục tiêu không
                    is_valid_ad = self.fb.process_ad_content(detected_ad)
                    
                    if is_valid_ad:
                        print("✅ Ads này NGON (đúng từ khóa) -> Tiến hành LIKE & SHARE!")
                        
                        # --- [SỬA ĐỔI] BƯỚC 1: LIKE TRƯỚC ---
                        self.fb.like_current_post(detected_ad)
                        time.sleep(random.uniform(1.0, 2.0)) # Nghỉ nhịp nhẹ cho giống người

                        # --- [SỬA ĐỔI] BƯỚC 2: SHARE SAU ---
                        self.fb.share_center_ad(detected_ad)
                        time.sleep(2)
                    else:
                        print("❌ Ads này không chứa từ khóa -> Bỏ qua không Like/Share.")
                    
                    # Đánh dấu đã xử lý để không quét lại
                    self.fb.mark_post_as_processed(detected_ad)
                    
                    # Xử lý xong thì cuộn mạnh để qua bài
                    print("👋 Xong bài này -> Cuộn tiếp...")
                    self.fb.page.mouse.wheel(0, 300) 
                    time.sleep(1.5)
                    
                    continue

                # ============================================================
                # [ĐÃ TẮT] LOGIC LIKE RANDOM BÀI THƯỜNG
                # ============================================================
                # Em đã comment phần này để bot tập trung Like Ads chuẩn chỉ hơn.
                # Nếu Sếp muốn bot like dạo cho "trust" acc thì mở lại đoạn dưới nhé.
                
                """
                press_count += 1
                if press_count >= random.randint(5, 10):
                    # Logic cũ: Like bài thường
                    pass 
                """

                # Random mouse move nhẹ cho đỡ bị check bot
                if random.random() < 0.1:
                    try:
                        vp = self.fb.page.viewport_size
                        if vp: self.fb.page.mouse.move(random.randint(0, vp['width']), random.randint(0, vp['height']))
                    except: pass
            
            except Exception as e:
                print(f"❌ Lỗi vòng lặp: {e}")
                time.sleep(2)