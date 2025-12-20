import time  # [Cần thêm thư viện này để đếm giờ]
from multiprocessing import Process
from typing import Optional, Sequence
from urllib.parse import quote_plus

from core.browser import FBController
from core.nst import connect_profile
from core.scraper import SimpleBot
from core.settings import get_settings
from core.utils import clean_profile_list
from core import control as control_state


class AppRunner:
    def __init__(
        self,
        run_minutes: Optional[int] = None,
        rest_minutes: Optional[int] = None,
        profile_ids: Optional[Sequence[str]] = None,
        text: Optional[str] = None,
        mode: Optional[str] = None,
    ):
        cfg = get_settings()
        self.target_url = cfg.target_url
        # Cho phép override danh sách profile từ API (/run) để không chạy hết.
        base_profiles = profile_ids if profile_ids is not None else cfg.profile_ids
        self.profiles = clean_profile_list(base_profiles)
        self.text = str(text or "").strip()
        self.mode = str(mode or "feed").strip().lower()
        if self.mode not in ("feed", "search"):
            self.mode = "feed"

        # Nếu là search => target_url sẽ là trang search posts.
        # Vẫn dùng core/browser.py để scan/like/share/bắt id.
        if self.mode == "search" and self.text:
            q = quote_plus(self.text)
            self.target_url = f"https://www.facebook.com/search/posts/?q={q}"

        # Ưu tiên giá trị truyền từ API; fallback cấu hình; cuối cùng là default.
        self.RUN_MINUTES = self._coerce_positive_int(
            run_minutes,
            cfg.run_minutes,
            default=30,
        )
        # REST_MINUTES mặc định 120p (tương đương 2h như cấu hình cũ)
        self.REST_MINUTES = self._coerce_positive_int(
            rest_minutes,
            cfg.rest_minutes,
            default=120,
        )

    @staticmethod
    def _coerce_positive_int(value, fallback=None, default=0):
        """
        Trả về số nguyên dương; nếu không hợp lệ dùng fallback, cuối cùng dùng default.
        """
        for candidate in (value, fallback, default):
            try:
                num = int(candidate)
                if num > 0:
                    return num
            except (TypeError, ValueError):
                continue
        return default

    def worker(self, profile_id):
        """Hàm xử lý cho từng profile (Process con)"""
        # trạng thái profile
        try:
            control_state.set_profile_state(profile_id, "RUNNING")
        except Exception:
            pass
        try:
            # STOP/PAUSE check trước khi connect
            stop, paused, reason = control_state.check_flags(profile_id)
            if stop:
                print(f"🛑 [{profile_id}] EMERGENCY_STOP trước khi connect ({reason})")
                try:
                    control_state.set_profile_state(profile_id, "STOPPED")
                except Exception:
                    pass
                return
            if paused:
                print(f"⏸️ [{profile_id}] PAUSED trước khi connect ({reason})")
                control_state.wait_if_paused(profile_id, sleep_seconds=0.5)

            # 1. Kết nối NST
            ws = connect_profile(profile_id)

            # 2. Khởi tạo trình duyệt
            fb = FBController(ws)
            fb.profile_id = profile_id
            # ✅ Chỉ dispatch/get_id trong phạm vi các profile đang chạy (đã chọn),
            # tránh loop toàn bộ PROFILE_IDS trong settings.json gây log "thiếu cookie".
            try:
                fb.all_profile_ids = list(self.profiles or [])
            except Exception:
                fb.all_profile_ids = [profile_id]
            # Filter thêm theo text nhập từ UI (nếu có)
            try:
                raw = self.text
                if raw:
                    # Tách theo dấu phẩy / xuống dòng, giữ nguyên cụm từ (VD "hà nội")
                    parts = []
                    for chunk in raw.replace("\n", ",").split(","):
                        s = " ".join(str(chunk).strip().split())
                        if s:
                            parts.append(s)
                    # unique giữ thứ tự
                    seen = set()
                    user_keywords = []
                    for x in parts:
                        k = x.lower()
                        if k in seen:
                            continue
                        seen.add(k)
                        user_keywords.append(x)
                    fb.user_keywords = user_keywords
                    if user_keywords:
                        print(f"🔎 [{profile_id}] Scan filter text: {user_keywords}")
            except Exception:
                pass
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
            try:
                control_state.set_profile_state(profile_id, "ERROR")
            except Exception:
                pass
        finally:
            # nếu đang emergency stop thì set STOPPED
            try:
                stop, _paused, _reason = control_state.check_flags(profile_id)
                if stop:
                    control_state.set_profile_state(profile_id, "STOPPED")
            except Exception:
                pass

    def run(self):
        """Hàm điều phối chính (Vòng lặp vĩnh cửu)"""
        
        # Đổi thời gian nghỉ sang giây
        rest_seconds = self.REST_MINUTES * 60
        
        print(f"∞ Kích hoạt chế độ nuôi tuần hoàn: Chạy {self.RUN_MINUTES}p -> Nghỉ {self.REST_MINUTES}p")

        while True:
            # STOP ALL: thoát ngay
            stop, _paused, _reason = control_state.check_flags(None)
            if stop:
                print("🛑 [RUNNER] EMERGENCY_STOP -> thoát vòng lặp AppRunner")
                break

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
            print(f"💤 [SLEEP] Xong phiên này. Bot sẽ ngủ {self.REST_MINUTES} phút.")
            print(f"⏰ Dự kiến chạy lại vào lúc: {wake_up_str}")
            print("="*60 + "\n")
            
            # 4. Bot đi ngủ
            # sleep theo chunk để vẫn check được STOP/PAUSE
            slept = 0
            while slept < rest_seconds:
                stop, paused, _reason = control_state.check_flags(None)
                if stop:
                    print("🛑 [RUNNER] EMERGENCY_STOP trong lúc sleep -> thoát")
                    return
                # pause all: vẫn cho runner sống nhưng không chạy phiên mới
                if paused:
                    time.sleep(1)
                    continue
                time.sleep(1)
                slept += 1