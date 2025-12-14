import os
import time # [Cần thêm thư viện này để đếm giờ]
from multiprocessing import Process
from dotenv import load_dotenv
from core.utils import clean_profile_list
from core.nst import connect_profile
from core.browser import FBController
from core.scraper import SimpleBot

class AppRunner:
    def __init__(self):
        load_dotenv()
        self.target_url = os.getenv("TARGET_URL", "https://facebook.com")
        self.profiles = clean_profile_list(os.getenv("PROFILE_IDS", ""))
        
        # [CẤU HÌNH THỜI GIAN TẠI ĐÂY]
        self.RUN_MINUTES = 30       # Thời gian chạy mỗi phiên (phút)
        self.REST_HOURS = 2         # Thời gian nghỉ giữa các phiên (tiếng)

    def worker(self, profile_id):
        """Hàm xử lý cho từng profile (Process con)"""
        try:
            # 1. Kết nối NST
            ws = connect_profile(profile_id)

            # 2. Khởi tạo trình duyệt
            fb = FBController(ws)
            fb.profile_id = profile_id
            fb.connect()

            # 3. Chạy bot tương tác
            bot = SimpleBot(fb)
            
            # Đổi thời gian chạy sang giây
            duration_seconds = self.RUN_MINUTES * 60
            
            # Bot sẽ tự thoát vòng lặp sau khi đủ thời gian
            bot.run(self.target_url, duration=duration_seconds) 

            print(f"✅ [{profile_id}] Đã chạy đủ {self.RUN_MINUTES} phút. Đang tắt trình duyệt...")
            
            # [Quan trọng] Đóng trình duyệt sạch sẽ để giải phóng RAM
            try:
                if fb.browser: fb.browser.close()
                if fb.play: fb.play.stop()
            except: pass
            
        except Exception as e:
            print(f"❌ Lỗi ở profile {profile_id}: {e}")

    def run(self):
        """Hàm điều phối chính (Vòng lặp vĩnh cửu)"""
        
        # Đổi thời gian nghỉ sang giây
        rest_seconds = self.REST_HOURS * 60 * 60
        
        print(f"∞ Kích hoạt chế độ nuôi tuần hoàn: Chạy {self.RUN_MINUTES}p -> Nghỉ {self.REST_HOURS}h")

        while True:
            print("="*60)
            print(f"▶️ [START] Bắt đầu phiên chạy mới lúc {time.strftime('%H:%M:%S')}")
            print("="*60)

            # 1. Khởi chạy dàn profile
            processes = []
            for pid in self.profiles:
                p = Process(target=self.worker, args=(pid,))
                p.start()
                processes.append(p)

            # 2. Chờ tất cả các profile chạy xong (Hết 30 phút tụi nó sẽ tự dừng)
            for p in processes:
                p.join()

            # 3. Tính toán thời gian thức dậy
            wake_up_time = time.time() + rest_seconds
            wake_up_str = time.strftime('%H:%M:%S', time.localtime(wake_up_time))

            print("\n" + "="*60)
            print(f"💤 [SLEEP] Xong phiên này. Bot sẽ ngủ {self.REST_HOURS} tiếng.")
            print(f"⏰ Dự kiến chạy lại vào lúc: {wake_up_str}")
            print("="*60 + "\n")
            
            # 4. Bot đi ngủ
            time.sleep(rest_seconds)