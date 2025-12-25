import sys
import os
import urllib.parse
import time
import re
import random
from typing import Optional

# --- SETUP ĐƯỜNG DẪN ĐỂ IMPORT CORE ---
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from core.nst import connect_profile
from core.nst import stop_profile
from core.browser import FBController, JS_EXPAND_SCRIPT, JS_CHECK_AND_HIGHLIGHT_SCOPED
from core.scraper import SimpleBot
from core.control import smart_sleep
from core.account_status import check_account_status_brutal, save_account_status

# ==============================================================================
# "HÀNH VI NGƯỜI THẬT": thi thoảng mở Thông báo rồi Back (8–15 phút/lần)
# ==============================================================================
def _random_notification_interval_seconds() -> int:
    return random.randint(12 * 60 , 15 * 60 )


def click_notifications_button(fb: FBController) -> bool:
    """
    Click nút 'Thông báo' trên Facebook (top bar).
    Ưu tiên role + aria-label, không dùng class động.
    """
    if not fb or not getattr(fb, "page", None):
        return False

    page = fb.page

    # Ưu tiên role=button + aria-label
    try:
        btn = page.get_by_role(
            "button",
            name=re.compile(r"(Thông báo|Notifications)", re.IGNORECASE),
        )
        if btn.count() > 0:
            btn.first.click(timeout=3000)
            return True
    except Exception:
        pass

    # Fallback: querySelector
    try:
        clicked = page.evaluate(
            """
            () => {
                const el = document.querySelector(
                    '[role="button"][aria-label^="Thông báo"], [role="button"][aria-label^="Notifications"]'
                );
                if (el) { el.click(); return true; }
                return false;
            }
            """
        )
        return bool(clicked)
    except Exception:
        return False


def get_notifications_panel(page):
    """
    Lấy scope panel Thông báo (dialog).
    Nếu không tìm được thì fallback về page.
    """
    try:
        panel = page.locator(
            'div[role="dialog"][aria-label^="Thông báo"], div[role="dialog"][aria-label^="Notifications"]'
        )
        if panel.count() > 0:
            return panel.first
    except Exception:
        pass

    return page


def click_random_notification(fb: FBController) -> bool:
    """
    Giả định panel Thông báo đã mở.
    Click ngẫu nhiên 1 thông báo hợp lệ.
    """
    if not fb or not getattr(fb, "page", None):
        return False

    page = fb.page
    panel = get_notifications_panel(page)

    try:
        links = panel.locator('div[role="listitem"] a[role="link"]')
        count = links.count()
        if count == 0:
            print("⚠️ Không có thông báo nào để click")
            return False

        def skip(href: Optional[str]) -> bool:
            if not href:
                return True
            h = str(href).strip()
            return (
                h == "/notifications/"
                or h.startswith("/notifications/?")
                or "facebook.com/notifications" in h
            )

        for _ in range(min(10, count)):
            idx = random.randint(0, count - 1)
            link = links.nth(idx)
            try:
                href = link.get_attribute("href")
            except Exception:
                href = None
            if skip(href):
                continue

            print(f"🔔 Click thông báo random: {href}")
            link.click(timeout=5000)
            return True

        print("⚠️ Không tìm được thông báo hợp lệ")
        return False

    except Exception as e:
        print(f"❌ Lỗi click_random_notification: {e}")
        return False


def open_notifications_random_then_back(
    fb: FBController,
    wait_seconds: Optional[int] = None,
    reload_after_back: bool = False,
) -> bool:
    """
    Flow hoàn chỉnh:
    - Mở Thông báo
    - Click random 1 thông báo
    - Đợi (10–15s hoặc custom)
    - Back
    - (Tuỳ chọn) Reload để reset feed state (chỉ nên dùng cho Feed)
    """
    if not fb or not getattr(fb, "page", None):
        return False

    page = fb.page

    if not click_notifications_button(fb):
        print("⚠️ Không mở được Thông báo")
        return False

    # Chờ panel render
    try:
        smart_sleep(5.0, fb.profile_id)
    except RuntimeError as e:
        if "EMERGENCY_STOP" in str(e):
            raise
        smart_sleep(5.0, fb.profile_id)

    if not click_random_notification(fb):
        return False

    delay = int(wait_seconds) if wait_seconds is not None else random.randint(10, 15)
    print(f"⏳ Đợi {delay}s rồi back")
    try:
        smart_sleep(float(delay), fb.profile_id)
    except RuntimeError as e:
        if "EMERGENCY_STOP" in str(e):
            raise
        smart_sleep(float(delay), fb.profile_id)

    # ===== BACK =====
    try:
        page.go_back(timeout=0)
    except Exception:
        try:
            page.keyboard.press("Alt+ArrowLeft")
        except Exception:
            print("⚠️ go_back fail")
            return False

    # ===== RELOAD (chỉ cho Feed nếu bật) =====
    if not reload_after_back:
        return True

    try:
        print("🔄 Reload feed để reset state")
        smart_sleep(random.uniform(1.5, 3.0), fb.profile_id)  # human-like
        page.reload(wait_until="domcontentloaded")
        smart_sleep(3.0, fb.profile_id)
        return True
    except RuntimeError as e:
        if "EMERGENCY_STOP" in str(e):
            raise
        print(f"⚠️ Reload fail: {e}")
        return False
    except Exception as e:
        print(f"⚠️ Reload fail: {e}")
        return False


class HumanLikeBot(SimpleBot):
    """
    Kế thừa SimpleBot để gắn nhịp mở Thông báo 8–15 phút/lần,
    CHỈ trigger sau khi đã xử lý xong 1 post + nghỉ tự nhiên.
    Sử dụng ACTIVE TIME thay vì wall-clock time.
    """
    def run(self, url, duration=None):
        print(f"🚀 Đang truy cập: {url}")
        # Điều hướng trực tiếp tới URL mục tiêu (feed/search)
        self.fb.goto(url)

        # ==== CHECK ACCOUNT STATUS MỘT LẦN SAU KHI VÀO TRANG MỤC TIÊU ====
        # - Chỉ kiểm tra 1 lần lúc bắt đầu
        # - Nếu nghi bị khóa/bị ban => dừng bot cho profile này (ACCOUNT_BANNED)
        # - Không tự điều hướng thêm lần nữa
        profile_id = getattr(self.fb, "profile_id", None)
        if profile_id:
            try:
                print(f"🔍 [ACCOUNT_STATUS] Kiểm tra trạng thái account cho profile {profile_id} (sau khi vào URL)...")
                status = check_account_status_brutal(self.fb)
                status["profile_id"] = profile_id
                status["checked_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                save_account_status(profile_id, status)

                if status.get("banned"):
                    error_msg = f"⛔ [ACCOUNT_BANNED] Profile {profile_id} bị khóa/bị ban: {status.get('message')}"
                    print(error_msg)
                    # DỪNG BOT cho profile này (quét/nuôi) nhưng không ảnh hưởng profile khác
                    raise RuntimeError(f"ACCOUNT_BANNED: {status.get('message')}")
                else:
                    print(f"✅ [ACCOUNT_STATUS] Profile {profile_id} OK: {status.get('message')}")
            except RuntimeError:
                # ACCOUNT_BANNED hoặc STOP/PAUSE sẽ được xử lý ở layer trên
                raise
            except Exception as e:
                # Không cho phép lỗi check account làm vỡ luồng cũ
                print(f"⚠️ [ACCOUNT_STATUS] Không kiểm tra được trạng thái account: {e}")

        # ACTIVE TIME tracking (chỉ tăng khi không pause)
        active_time = 0.0
        next_notify_active_time = _random_notification_interval_seconds()

        while True:
            try:
                # Check duration bằng ACTIVE TIME
                if duration and active_time >= duration:
                    print("⏳ Hết giờ chạy.")
                    break

                post, post_type = self.fb.scan_while_scrolling()

                if post:
                    self.fb.process_post(post, post_type)

                    delay = random.uniform(12.0, 20.0)
                    print(f"😴 Nghỉ sau khi xử lý bài {delay:.1f}s")
                    try:
                        smart_sleep(delay, self.fb.profile_id)
                        # Chỉ tăng active_time khi smart_sleep return bình thường (không pause)
                        active_time += delay
                    except RuntimeError as e:
                        if "EMERGENCY_STOP" in str(e):
                            raise
                        # Nếu pause thì không tăng active_time

                    # ===== ĐIỂM CHỐT: chỉ mở thông báo sau DONE + nghỉ =====
                    if active_time >= next_notify_active_time:
                        # Chỉ reload sau khi back nếu đang chạy Feed (trang chủ).
                        is_feed = str(url or "").strip().rstrip("/") == "https://www.facebook.com"
                        try:
                            open_notifications_random_then_back(self.fb, reload_after_back=is_feed)
                            next_notify_active_time = active_time + _random_notification_interval_seconds()
                        except RuntimeError as e:
                            if "EMERGENCY_STOP" in str(e):
                                raise
                else:
                    delay = random.uniform(3.0, 5.0)
                    print(f"😴 Không có bài – nghỉ {delay:.1f}s")
                    try:
                        smart_sleep(delay, self.fb.profile_id)
                        # Chỉ tăng active_time khi smart_sleep return bình thường (không pause)
                        active_time += delay
                    except RuntimeError as e:
                        if "EMERGENCY_STOP" in str(e):
                            raise
                        # Nếu pause thì không tăng active_time

            except RuntimeError as e:
                if "EMERGENCY_STOP" in str(e):
                    print("🛑 Dừng do EMERGENCY_STOP")
                    raise
                print(f"❌ Lỗi vòng lặp: {e}")
                try:
                    smart_sleep(2.0, self.fb.profile_id)
                    active_time += 2.0
                except RuntimeError as stop_e:
                    if "EMERGENCY_STOP" in str(stop_e):
                        raise

def _parse_location_terms(raw_text: str, strip_terms: Optional[list[str]] = None) -> list[str]:
    """
    User input dạng: "bắc ninh , bắc giang" hoặc "tuyển dụng bắc ninh , bắc giang"
    => trả về ["bắc ninh", "bắc giang"]
    """
    text = str(raw_text or "").strip().lower()
    if not text:
        return []

    parts = [p.strip() for p in re.split(r"[,;\n]+", text) if p.strip()]
    out: list[str] = []
    seen: set[str] = set()
    strip_terms = strip_terms or []

    for part in parts:
        cleaned = part
        # remove "job keywords" khỏi input nếu user dính vào location
        for term in strip_terms:
            t = str(term or "").strip().lower()
            if not t:
                continue
            cleaned = cleaned.replace(t, " ")
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if not cleaned:
            continue
        if cleaned in seen:
            continue
        seen.add(cleaned)
        out.append(cleaned)

    return out

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

            required_locations: list[str] = getattr(self, "required_locations", []) or []
            # 2) Dùng đúng hàm có sẵn của browser.py (JS_CHECK_AND_HIGHLIGHT_SCOPED)
            # - has_job_keyword: có ít nhất 1 keyword mặc định (job_keywords) trong NỘI DUNG BÀI
            # - has_location_term: có ít nhất 1 cụm text user nhập (required_locations) trong NỘI DUNG BÀI
            # => CHỈ LIKE KHI (job_keyword) AND (location_term)
            has_job_keyword = self.page.evaluate(
                JS_CHECK_AND_HIGHLIGHT_SCOPED,
                [post_handle, self.job_keywords]
            )
            # Nếu user không nhập text (feed mode), thì bỏ qua điều kiện location (coi như pass)
            has_location_term = True if not required_locations else self.page.evaluate(
                JS_CHECK_AND_HIGHLIGHT_SCOPED,
                [post_handle, required_locations]
            )

            has_keyword = bool(has_job_keyword and has_location_term)

            if not has_keyword:
                print("❌ Không đạt điều kiện (cần keyword mặc định + có 1 trong text nhập) -> Bỏ qua")
                self.mark_post_as_processed(post_handle)
                
                
                
                return False

            print("✅ Bài đạt điều kiện (keyword mặc định + text nhập)!")

            # Like theo xác suất để đảm bảo khoảng cách 45-90 giây giữa các lần like:
            # - Với nghỉ 12-20s sau mỗi bài, để có khoảng cách 45-90s cần like 20-30% bài
            # - Sau đó roll để quyết định có Like hay không
            p = random.uniform(0.20, 0.30)
            roll = random.random()
            should_like = roll < p
            print(f"🎲 [LikeProb] p={p:.2f} roll={roll:.2f} -> {'LIKE' if should_like else 'SKIP'}")
            if should_like:
                # like_current_post tự bỏ qua nếu bài đã Like
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
def search_and_like(profile_id: str, search_text: str, duration_minutes: int = 30, all_profile_ids=None):
    """Nhập từ khóa -> Vào trang Search -> Lướt & Like bài có từ khóa"""
    try:
        # 1. Tạo URL Tìm kiếm
        encoded_query = urllib.parse.quote_plus(search_text)
        target_url = f"https://www.facebook.com/search/posts?q={encoded_query}"
        
        print(f"🔍 [Search] Từ khóa: '{search_text}'")
        print(f"🔗 Link: {target_url}")

        _run_bot_logic(profile_id, target_url, search_text, duration_minutes, all_profile_ids=all_profile_ids)

    except Exception as e:
        print(f"❌ Lỗi search_and_like: {e}")

# ==============================================================================
# HÀM 2: LƯỚT NEWFEED & LIKE (Trang Chủ)
# ==============================================================================
def feed_and_like(profile_id: str, filter_text: str, duration_minutes: int = 30, all_profile_ids=None):
    """Vào trang chủ (Feed) -> Lướt -> Chỉ Like bài nào chứa filter_text"""
    try:
        # 1. URL là Trang chủ
        target_url = "https://www.facebook.com/"
        
        print(f"🏠 [Feed] Lướt News Feed tìm từ khóa: '{filter_text}'")
        
        _run_bot_logic(profile_id, target_url, filter_text, duration_minutes, all_profile_ids=all_profile_ids)

    except Exception as e:
        print(f"❌ Lỗi feed_and_like: {e}")

# ==============================================================================
# HÀM CHẠY CHUNG (CORE LOGIC)
# ==============================================================================
def _run_bot_logic(profile_id, url, raw_text, duration_minutes, all_profile_ids=None):
    try:
        # 1. Kết nối
        print(f"🚀 Đang mở profile: {profile_id}")
        ws_url = connect_profile(profile_id)
        
        # Dùng Controller đã cắt bỏ Share/Save
        fb = SearchBotController(ws_url)
        fb.profile_id = profile_id
        # ✅ giới hạn dispatch/get_id chỉ trong các profile đang chạy (đã chọn)
        try:
            if all_profile_ids:
                fb.all_profile_ids = list(all_profile_ids)
            else:
                fb.all_profile_ids = [profile_id]
        except Exception:
            fb.all_profile_ids = [profile_id]
        fb.connect()

        # 2. Setup filter rules
        # - Feed: cho phép raw_text rỗng => không lọc location, chỉ dùng job_keywords mặc định
        # - Nếu user có nhập raw_text nhưng parse ra rỗng (vd chỉ nhập "tuyển dụng") thì coi như sai input
        raw_text_str = str(raw_text or "").strip()
        if not raw_text_str:
            locations = []
        else:
            # text nhập chỉ dùng làm "location terms" (OR), tách theo dấu phẩy
            locations = _parse_location_terms(raw_text_str, strip_terms=getattr(fb, "job_keywords", []))
            # Nếu user chỉ nhập keyword (vd: "tuyển dụng") thì locations có thể rỗng sau khi strip.
            # Khi đó: không lọc location, vẫn chạy bình thường theo job_keywords mặc định.
            if not locations:
                print("ℹ️ Không có location từ input -> chỉ dùng keyword mặc định để lọc.")

        fb.required_locations = locations
        if locations:
            print(f"✅ Filter location (OR): {locations}")
        else:
            print("✅ Filter location: (none) -> chỉ dùng keyword mặc định")
        print(f"✅ Filter job keywords (default): {getattr(fb, 'job_keywords', [])}")
        
        # 3. Chạy Bot (human-like: thỉnh thoảng mở thông báo)
        bot = HumanLikeBot(fb)
        print(f"▶️ Bắt đầu lướt trong {duration_minutes} phút...")
        duration_seconds = duration_minutes * 60
        
        try:
            bot.run(url, duration=duration_seconds)
        except RuntimeError as e:
            if "EMERGENCY_STOP" in str(e):
                print("🛑 Dừng bot do EMERGENCY_STOP")
                return
            if "ACCOUNT_BANNED" in str(e):
                print(f"🛑 Dừng bot do ACCOUNT_BANNED: {e}")
                return
            raise
        
    except RuntimeError as e:
        if "EMERGENCY_STOP" in str(e):
            print("🛑 Dừng runner do EMERGENCY_STOP")
            return
        if "ACCOUNT_BANNED" in str(e):
            print(f"🛑 Dừng runner do ACCOUNT_BANNED: {e}")
            return
        print(f"❌ Lỗi Runner: {e}")
    except Exception as e:
        print(f"❌ Lỗi Runner: {e}")
    finally:
        print("🛑 Kết thúc.")
        # Đóng sạch tab/context playwright + stop NST (giống join group / cookie)
        try:
            if 'fb' in locals() and fb:
                try:
                    if getattr(fb, "page", None):
                        try:
                            fb.page.close()
                        except Exception:
                            pass
                except Exception:
                    pass
                try:
                    if getattr(fb, "browser", None) and getattr(fb.browser, "contexts", None):
                        for ctx in list(fb.browser.contexts):
                            try:
                                ctx.close()
                            except Exception:
                                pass
                except Exception:
                    pass
                try:
                    if getattr(fb, "browser", None):
                        try:
                            fb.browser.close()
                        except Exception:
                            pass
                except Exception:
                    pass
                try:
                    if getattr(fb, "play", None):
                        try:
                            fb.play.stop()
                        except Exception:
                            pass
                except Exception:
                    pass
        finally:
            try:
                stop_profile(profile_id)
            except Exception:
                pass

if __name__ == "__main__":
    # Module này được gọi qua FastAPI (/feed/start). Không chạy standalone.
    pass