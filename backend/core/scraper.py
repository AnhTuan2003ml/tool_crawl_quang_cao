import time
import random
import os
from core import control as control_state
from core.control import smart_sleep

class SimpleBot:
    def __init__(self, fb):
        self.fb = fb 

    def _sleep_with_pause_check(self, total_seconds, profile_id, active_time_list, last_check_time_list):
        """
        Sleep nhưng check pause: chỉ tính thời gian không pause vào active_time.
        active_time_list và last_check_time_list là list để pass by reference.
        Sử dụng smart_sleep để handle STOP/PAUSE.
        """
        start_time = time.time()
        try:
            smart_sleep(total_seconds, profile_id)
            # Nếu smart_sleep return bình thường (không pause), tính vào active_time
            end_time = time.time()
            elapsed = end_time - start_time
            active_time_list[0] += elapsed
            last_check_time_list[0] = end_time
        except RuntimeError as e:
            if "EMERGENCY_STOP" in str(e):
                raise
            # Nếu pause thì không tính vào active_time
            last_check_time_list[0] = time.time()

    def run(self, url, duration=None):
        print(f"🚀 Đang truy cập: {url}")
        self.fb.goto(url) 
        
        # Track "active time" (chỉ tăng khi không pause) thay vì wall clock time
        # Dùng list để pass by reference cho helper function
        active_time_list = [0.0]
        last_check_time_list = [time.time()]
        profile_id = getattr(self.fb, 'profile_id', None)
        
        while True:
            try:
                # STOP/PAUSE checkpoint (ưu tiên STOP ALL)
                try:
                    if hasattr(self.fb, "control_checkpoint"):
                        self.fb.control_checkpoint("before_loop")
                except RuntimeError as ce:
                    if "EMERGENCY_STOP" in str(ce) or "BROWSER_CLOSED" in str(ce):
                        print("🛑 Dừng bot do control flag / browser closed")
                        break
                    raise

                # Chỉ bắt đầu đo elapsed SAU checkpoint (vì checkpoint có thể wait khi pause)
                now = time.time()
                elapsed_since_last_check = now - last_check_time_list[0]
                last_check_time_list[0] = now

                # Check pause: nếu không pause thì cộng thời gian đã trôi qua vào active_time
                stop, paused, _reason = control_state.check_flags(profile_id)
                if stop:
                    print("🛑 Dừng bot do STOP flag")
                    break
                
                # Chỉ tăng active_time khi KHÔNG pause (đóng băng timer khi pause)
                if paused:
                    # Nếu vẫn đang pause (hiếm), reset mốc thời gian để không cộng dồn
                    last_check_time_list[0] = time.time()
                    continue
                active_time_list[0] += elapsed_since_last_check
                
                # 1. Kiểm tra thời gian chạy (dùng active_time thay vì wall clock)
                if duration and active_time_list[0] >= duration:
                    print(f"⏳ Hết giờ chạy (đã chạy {active_time_list[0]:.1f}s / {duration}s).")
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
                    # Sleep với pause check: chỉ tính thời gian không pause vào active_time
                    self._sleep_with_pause_check(delay, profile_id, active_time_list, last_check_time_list)
                else:
                    delay = random.uniform(3.0, 5.0)
                    print(f"😴 Không có bài – nghỉ {delay:.1f}s")
                    # Sleep với pause check
                    self._sleep_with_pause_check(delay, profile_id, active_time_list, last_check_time_list)



                # Random mouse move nhẹ cho đỡ bị check bot
                
            
            except RuntimeError as e:
                # Nếu là exception đặc biệt BROWSER_CLOSED thì dừng ngay
                if "BROWSER_CLOSED" in str(e) or "EMERGENCY_STOP" in str(e):
                    print(f"🛑 Dừng bot ngay lập tức ({e})")
                    break
                raise  # Re-raise nếu không phải BROWSER_CLOSED
            except Exception as e:
                error_msg = str(e).lower()
                # Nếu browser/page đã bị đóng thì dừng luôn
                if any(keyword in error_msg for keyword in ["closed", "disconnected", "target page", "context or browser"]):
                    print(f"🛑 Browser đã bị đóng -> Dừng bot")
                    break
                print(f"⚠️ Lỗi scan: {e}")
                # Sleep với pause check cho lỗi
                self._sleep_with_pause_check(2.0, profile_id, active_time_list, last_check_time_list)