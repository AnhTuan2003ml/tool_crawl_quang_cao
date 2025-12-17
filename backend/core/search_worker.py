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
# UI HELPERS
# ==============================================================================
def click_notifications_button(fb: FBController) -> bool:
    """
    Bấm vào nút "Thông báo" trên Facebook top bar.
    Lưu ý: không dùng selector theo class (x...) vì thay đổi liên tục, ưu tiên aria-label/role.
    """
    if not fb or not getattr(fb, "page", None):
        return False

    page = fb.page

    # Ưu tiên button role + name bắt đầu bằng "Thông báo"
    try:
        btn = page.get_by_role("button", name=re.compile(r"^Thông báo", re.IGNORECASE)).first
        if btn:
            btn.click(timeout=3000)
            return True
    except Exception:
        pass

    # Fallback: query selector theo aria-label
    try:
        el = page.query_selector('div[role="button"][aria-label^="Thông báo"]')
        if el:
            el.click()
            return True
    except Exception:
        pass

    # Fallback cuối: tìm text "Số thông báo chưa đọc" (nằm trong badge)
    try:
        badge = page.get_by_text("Số thông báo chưa đọc", exact=False).first
        if badge:
            badge.click(timeout=3000)
            return True
    except Exception:
        pass

    return False


def _get_notifications_panel_locator(page):
    """
    Trả về locator của panel Thông báo (ưu tiên scope trong dialog/popup).
    """
    # Thường notifications mở ra dưới dạng dialog có aria-label bắt đầu bằng "Thông báo"
    try:
        panel = page.locator('div[role="dialog"][aria-label^="Thông báo"]').first
        if panel and panel.count() > 0:
            return panel
    except Exception:
        pass

    # Fallback: tìm dialog có chứa text "Thông báo"
    try:
        panel = page.locator('div[role="dialog"]').filter(has_text=re.compile(r"Thông báo", re.IGNORECASE)).first
        if panel and panel.count() > 0:
            return panel
    except Exception:
        pass

    # Fallback cuối: không tìm thấy dialog, trả về toàn trang (kém an toàn nhưng còn hơn fail)
    return page


def click_random_notification_in_open_panel(fb: FBController) -> bool:
    """
    Giả định panel Thông báo đã mở.
    Chỉ tìm link thông báo bên trong panel, chọn ngẫu nhiên 1 cái và click.
    """
    if not fb or not getattr(fb, "page", None):
        return False

    page = fb.page
    panel = _get_notifications_panel_locator(page)

    try:
        # Đúng theo snippet bạn đưa: listitem -> a role=link
        links = panel.locator('div[role="listitem"] a[role="link"]')
        count = links.count()
        if count <= 0:
            print("⚠️ Không tìm thấy thông báo nào có link trong panel.")
            return False

        def _is_skip_href(href: Optional[str]) -> bool:
            if not href:
                return True
            h = str(href).strip()
            if not h:
                return True
            # bỏ qua link trỏ về trang notifications
            if h == "/notifications/" or h.startswith("/notifications/?"):
                return True
            if "facebook.com/notifications/" in h:
                return True
            return False

        # thử chọn vài lần để tránh rơi vào /notifications/
        max_tries = min(10, count)
        for _ in range(max_tries):
            idx = random.randint(0, count - 1)
            link = links.nth(idx)
            href = None
            try:
                href = link.get_attribute("href")
            except Exception:
                href = None
            if _is_skip_href(href):
                continue

            print(f"🔔 Đã chọn thông báo #{idx + 1}/{count}: {href or '(no href)'}")
            link.click(timeout=5000)
            return True

        print("⚠️ Không tìm thấy link thông báo hợp lệ (đã bỏ qua /notifications/).")
        return False
    except Exception as e:
        print(f"❌ Lỗi click_random_notification_in_open_panel: {e}")
        return False


def open_notifications_click_random_then_back(fb: FBController, wait_seconds: Optional[int] = None) -> bool:
    """
    Flow đầy đủ:
    - mở Thông báo
    - click ngẫu nhiên 1 thông báo trong panel
    - đợi 10–15s (hoặc wait_seconds)
    - bấm Back (giống nút quay lại trên Chrome)
    """
    if not fb or not getattr(fb, "page", None):
        return False

    page = fb.page

    if not click_notifications_button(fb):
        print("⚠️ Không mở được panel Thông báo.")
        return False

    # Chờ panel render (cố định 5s theo yêu cầu) rồi mới click 1 thông báo bất kỳ
    try:
        page.wait_for_timeout(5000)
    except Exception:
        time.sleep(5)

    if not click_random_notification_in_open_panel(fb):
        return False

    # Đợi rồi quay lại
    delay = int(wait_seconds) if wait_seconds is not None else random.randint(10, 15)
    print(f"⏳ Đợi {delay}s rồi Back...")
    try:
        page.wait_for_timeout(delay * 1000)
    except Exception:
        time.sleep(delay)

    try:
        page.go_back(timeout=0)
        return True
    except Exception:
        # Fallback: Alt+Left
        try:
            page.keyboard.press("Alt+ArrowLeft")
            return True
        except Exception as e:
            print(f"❌ Không Back được: {e}")
            return False


def test_click_notifications(profile_id: str) -> bool:
    """
    Test nhanh: mở profile -> vào facebook.com -> click nút Thông báo -> chờ vài giây rồi thoát.
    Dùng để kiểm tra selector click có đúng không.
    """
    fb = None
    ok = False
    try:
        print(f"🧪 [TEST] Mở profile: {profile_id}")
        ws_url = connect_profile(profile_id)
        fb = FBController(ws_url)
        fb.profile_id = profile_id
        fb.connect()

        try:
            fb.goto("https://www.facebook.com/")
            fb.page.wait_for_timeout(1500)
        except Exception:
            time.sleep(1.5)

        ok = click_notifications_button(fb)
        print(f"🧪 [TEST] Click Thông báo: {'OK' if ok else 'FAIL'}")

        try:
            fb.page.wait_for_timeout(3000)
        except Exception:
            time.sleep(3)

        return ok
    except Exception as e:
        print(f"❌ [TEST] Lỗi test_click_notifications: {e}")
        return False
    finally:
        # cleanup giống các luồng khác
        try:
            if fb:
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


def test_notifications_random_click_then_back(profile_id: str) -> bool:
    """
    Test nhanh:
    - vào FB
    - mở Thông báo
    - click random 1 thông báo
    - đợi 10–15s
    - back
    """
    fb = None
    try:
        print(f"🧪 [TEST] Mở profile: {profile_id}")
        ws_url = connect_profile(profile_id)
        fb = FBController(ws_url)
        fb.profile_id = profile_id
        fb.connect()

        fb.goto("https://www.facebook.com/")
        try:
            fb.page.wait_for_timeout(1500)
        except Exception:
            time.sleep(1.5)

        ok = open_notifications_click_random_then_back(fb)
        print(f"🧪 [TEST] Flow notifications->random->back: {'OK' if ok else 'FAIL'}")
        try:
            fb.page.wait_for_timeout(1500)
        except Exception:
            time.sleep(1.5)
        return ok
    except Exception as e:
        print(f"❌ [TEST] Lỗi test_notifications_random_click_then_back: {e}")
        return False
    finally:
        try:
            if fb:
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
                
                # Đẩy bài viết lên để bot không bị kẹt
                try:
                    viewport = self.page.viewport_size
                    height = viewport['height'] if viewport else 800
                    self.page.mouse.wheel(0, height * 0.4)
                except: pass
                
                return False

            print("✅ Bài đạt điều kiện (keyword mặc định + text nhập)!")

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
def _run_bot_logic(profile_id, url, raw_text, duration_minutes):
    try:
        # 1. Kết nối
        print(f"🚀 Đang mở profile: {profile_id}")
        ws_url = connect_profile(profile_id)
        
        # Dùng Controller đã cắt bỏ Share/Save
        fb = SearchBotController(ws_url)
        fb.profile_id = profile_id
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
            if not locations:
                print("⚠️ Không có địa điểm hợp lệ từ input. Hãy nhập dạng: 'bắc ninh , bắc giang'")
                return

        fb.required_locations = locations
        if locations:
            print(f"✅ Filter location (OR): {locations}")
        else:
            print("✅ Filter location: (none) -> chỉ dùng keyword mặc định")
        print(f"✅ Filter job keywords (default): {getattr(fb, 'job_keywords', [])}")
        
        # 3. Chạy Bot
        bot = SimpleBot(fb)
        print(f"▶️ Bắt đầu lướt trong {duration_minutes} phút...")
        duration_seconds = duration_minutes * 60
        
        bot.run(url, duration=duration_seconds)
        
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
    # --- TEST ---
    TEST_ID = "621e1f5d-0c42-481e-9ddd-7abaafce68ed"

    # Chạy test tạm: mở FB -> Thông báo -> click random -> đợi -> Back
    test_notifications_random_click_then_back(TEST_ID)
    # if mode == "1":
    #     search_and_like(TEST_ID, text, duration_minutes=15)
    # elif mode == "2":
    #     feed_and_like(TEST_ID, text, duration_minutes=15)