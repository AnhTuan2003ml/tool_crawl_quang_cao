import time
import random
from playwright.sync_api import sync_playwright
import json
import re
from urllib.parse import urlparse, parse_qs, unquote
import os
import sys
import threading
from core.settings import get_settings, SETTINGS_PATH
from core import control as control_state
from core.control import smart_sleep
from core.paths import get_data_dir

# Lock để bảo vệ việc ghi settings.json (tránh race condition khi nhiều profile cùng lưu cookie)
_settings_write_lock = threading.Lock()
# ==============================================================================
# JS TOOLS & HELPER FUNCTIONS
# ==============================================================================
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
worker_path = os.path.join(parent_dir, 'worker')

if worker_path not in sys.path:
    sys.path.append(worker_path)

# Import hàm lấy thông tin an toàn
try:
    from get_id import get_id_from_url
except ImportError:
    try:
        from worker.get_id import get_id_from_url
    except:
        print("⚠️ Cảnh báo: Không import được worker/get_id.py")
        get_id_from_url = None


JS_EXPAND_SCRIPT = """
(node) => {
    if (!node) return 0;

    const keywords = ["Xem thêm", "See more"];
    let clickedCount = 0;

    // 🔒 Chỉ tìm trong nội dung bài viết
    const scopes = [
        '[data-ad-preview="message"]',
        '[data-ad-rendering-role="story_message"]',
        '.userContent'
    ];

    let target = null;
    for (const sel of scopes) {
        const found = node.querySelector(sel);
        if (found) {
            target = found;
            break;
        }
    }

    if (!target) return 0;

    const buttons = Array.from(
        target.querySelectorAll('[role="button"]')
    );

    for (const btn of buttons) {
        const text = btn.innerText ? btn.innerText.trim() : "";
        if (!keywords.includes(text)) continue;

        const rect = btn.getBoundingClientRect();

        // ❗ Chỉ click nếu nút đang nằm trong viewport
        if (rect.top < 0 || rect.bottom > window.innerHeight) continue;

        if (btn.offsetWidth > 0 && btn.offsetHeight > 0) {
            btn.click();
            btn.style.border = "2px solid red";
            clickedCount++;
        }
    }

    return clickedCount;
}
"""

JS_CHECK_AND_HIGHLIGHT_SCOPED = """
([node, keywords]) => { 
    if (!node || !keywords || keywords.length === 0) return false;
    
    // [CỰC KỲ QUAN TRỌNG] 
    // Chỉ định chính xác các selector bao bọc nội dung bài viết mà Sếp đã cung cấp.
    // Bot sẽ chỉ hoạt động bên trong các thẻ này.
    const strictSelectors = [
        '[data-ad-preview="message"]',              // Ưu tiên 1: Chuẩn Ads
        '[data-ad-rendering-role="story_message"]', // Ưu tiên 2: Wrapper của message
        '.userContent'                              // Ưu tiên 3: Các dạng bài cũ
    ];

    let targetScope = null;

    // 1. Tìm đúng cái hộp nội dung
    for (const selector of strictSelectors) {
        const found = node.querySelector(selector);
        if (found) {
            targetScope = found;
            break;
        }
    }

    // [CHỐT CHẶN]
    // Nếu không tìm thấy cái hộp nội dung này -> Coi như không phải bài viết hợp lệ -> RETURN FALSE NGAY.
    // Điều này đảm bảo không bao giờ quét nhầm tên Page hay Header bên ngoài.
    if (!targetScope) return false;

    // 2. Logic quét và highlight (Chỉ chạy trong targetScope)
    const sortedKeywords = keywords.sort((a, b) => b.length - a.length);
    const pattern = new RegExp(`(${sortedKeywords.join('|')})`, 'gi');
    let foundCount = 0;

    function highlightTextNode(textNode) {
        const text = textNode.nodeValue;
        if (!pattern.test(text)) return;
        
        const fragment = document.createDocumentFragment();
        const parts = text.split(pattern);
        parts.forEach(part => {
            if (pattern.test(part)) {
                const span = document.createElement('span');
                // Style cho dễ nhìn khi debug
                Object.assign(span.style, {
                    backgroundColor: 'yellow', color: 'red', fontWeight: 'bold',
                    border: '2px solid red', padding: '2px', zIndex: '9999'
                });
                span.innerText = part;
                fragment.appendChild(span);
                foundCount++;
            } else {
                fragment.appendChild(document.createTextNode(part));
            }
            pattern.lastIndex = 0; 
        });
        textNode.parentNode.replaceChild(fragment, textNode);
    }

    const walker = document.createTreeWalker(targetScope, NodeFilter.SHOW_TEXT, {
        acceptNode: n => {
            // Vẫn giữ bộ lọc thẻ rác để sạch sẽ nhất có thể
            if (['SCRIPT', 'STYLE', 'NOSCRIPT', 'BUTTON', 'INPUT'].includes(n.parentNode.nodeName)) {
                return NodeFilter.FILTER_REJECT;
            }
            if (n.parentNode.isContentEditable) return NodeFilter.FILTER_REJECT;
            return NodeFilter.FILTER_ACCEPT;
        }
    });

    const textNodes = [];
    while (walker.nextNode()) textNodes.push(walker.currentNode);
    textNodes.forEach(highlightTextNode);
    
    return foundCount > 0;
}
"""

def extract_facebook_post_id(url: str):
    if not url: return None
    try: url = unquote(url)
    except: pass
    
    patterns = [
        r"(pfbid[A-Za-z0-9]+)", 
        r"/posts/(\d+)", 
        r"/videos/(\d+)", 
        r"/reel/(\d+)",
        r"story_fbid=(\d+)", 
        r"fbid=(\d+)",
        r"id=(\d+)"
    ]
    for p in patterns:
        m = re.search(p, url)
        if m: return m.group(1)
        
    qs = parse_qs(urlparse(url).query)
    for k in ["story_fbid", "fbid", "id"]:
        if k in qs: return qs[k][0]
    return None

def parse_graphql_payload(post_data):
    """Phân tích data gửi đi để tìm biến 'url'."""
    if not post_data: return None
    variables_str = None
    
    try:
        if isinstance(post_data, str):
            json_body = json.loads(post_data)
        else:
            json_body = post_data
        variables_str = json.dumps(json_body.get("variables", {}))
    except:
        try:
            qs = parse_qs(post_data)
            if "variables" in qs:
                variables_str = qs["variables"][0]
        except: pass

    if variables_str and '"url":' in variables_str:
        match = re.search(r'"url"\s*:\s*"([^"]+)"', variables_str)
        if match:
            raw_url = match.group(1)
            return raw_url.replace(r"\/", "/")
            
    return None


class FBController:
    def __init__(self, ws_url):
        self.ws_url = ws_url
        self.browser = None
        self.page = None
        self.play = None
        self.profile_id = "unknown"
        # keyword filter thêm từ UI (Setting profile -> Quét bài viết)
        # nếu rỗng => chỉ lọc theo job_keywords mặc định
        self.user_keywords = []
        cfg = get_settings()
        self.all_profile_ids = cfg.profile_ids
        # Chỉ bắt URL payload từ request
        self.captured_payload_url = None
        
        self.job_keywords = [
            "tuyển dụng", "tuyển nhân viên", "tuyển gấp", "việc làm", "tuyển",
            "lương", "phỏng vấn", "hồ sơ",
            "full-time", "part-time", "thực tập", "kế toán", "may mặc", "kcn" ,"Ứng viên " , "Ứng tuyển"
        ]
        # cache nhẹ để tránh spam IO khi check control liên tục
        self._last_control_check_ts = 0.0
        self._last_control_snapshot = (False, False, "")

    def control_checkpoint(self, where: str = "") -> None:
        """
        Ưu tiên flag theo spec:
          1) GLOBAL_EMERGENCY_STOP -> STOP NGAY
          2) GLOBAL_PAUSE -> SLEEP
          3) PAUSED_PROFILES[pid] -> SLEEP
        """
        now = time.time()
        if now - float(getattr(self, "_last_control_check_ts", 0.0)) > 0.35:
            self._last_control_check_ts = now
            self._last_control_snapshot = control_state.check_flags(getattr(self, "profile_id", None))

        stop, paused, reason = self._last_control_snapshot

        if stop:
            try:
                control_state.set_profile_state(self.profile_id, "STOPPED")
            except Exception:
                pass
            print(f"🛑 [STOP] {self.profile_id} @ {where} ({reason})")
            raise RuntimeError("EMERGENCY_STOP")

        if paused:
            try:
                control_state.set_profile_state(self.profile_id, "PAUSED")
            except Exception:
                pass
            if where:
                print(f"⏸️ [PAUSE] {self.profile_id} @ {where} ({reason})")
            # chờ đến khi hết pause hoặc emergency stop
            control_state.wait_if_paused(self.profile_id, sleep_seconds=0.5)
            try:
                control_state.set_profile_state(self.profile_id, "RUNNING")
            except Exception:
                pass

    def connect(self):
        self.play = sync_playwright().start()
        self.browser = self.play.chromium.connect_over_cdp(self.ws_url)
        context = self.browser.contexts[0]
        self.page = context.pages[0]
        
        self.start_network_sniffer()
        
        try:
            viewport = self.page.viewport_size
            self.page.mouse.click(viewport['width']/2, viewport['height']/2)
        except: pass

    def goto(self, url):
        self.page.goto(url, timeout=0)

    # ===================== [CORE] NETWORK SNIFFER =====================
    def start_network_sniffer(self):
        print("🛰  Đã kích hoạt Sniffer: Chế độ bắt Payload URL...")

        # BẮT URL TỪ REQUEST (chỉ bắt URL có chứa "share")
        def on_request(request):
            if "facebook.com/api/graphql" in request.url and request.method == "POST":
                try:
                    raw_url = parse_graphql_payload(request.post_data)
                    if raw_url:
                        # Chỉ lưu nếu URL có chứa "share" (ví dụ: https://www.facebook.com/share/p/1HYNUE6FzL/)
                        if "/share/" in raw_url:
                            self.captured_payload_url = raw_url
                            print(f"🔗 [DEBUG] Bắt được Share URL: {raw_url}")
                except: pass

        self.page.on("request", on_request)

    # ===================== SHARE & CHỜ ID (LOGIC MỚI) =====================
    def share_center_ad(self, post_handle, post_type):
            
        try:
            self.control_checkpoint("before_share")
            viewport = self.page.viewport_size
            height = viewport['height'] if viewport else 800
            escape_step = height * 0.35  # 👈 THOÁT MODULE RÁC
            print("🚀 Share → bắt Payload URL → gọi get_id_from_url")

            self.captured_payload_url = None

            share_btn = post_handle.query_selector(
                'xpath=.//div[@data-ad-rendering-role="share_button"]/ancestor::div[@role="button"]'
            )
            if not share_btn:
                print("⚠️ Không tìm thấy nút Share")
                self.scroll_past_post(post_handle)
                time.sleep(random.uniform(0.12, 0.13))
                return False

            self.bring_element_into_view_smooth(share_btn)
            self.page.wait_for_timeout(300)
            share_btn.click()

            # Đợi bắt được payload URL
            for _ in range(50):
                self.control_checkpoint("after_share_click_wait_payload")
                if self.captured_payload_url:
                    # Gọi get_id_from_url trực tiếp từ URL payload
                    if get_id_from_url:
                        try:
                            self.control_checkpoint("before_get_id_from_url")
                            print(f"📥 Đang gọi get_id_from_url với URL: {self.captured_payload_url}")
                            details = get_id_from_url(self.captured_payload_url, self.profile_id)
                            if details and details.get("post_id"):
                                self.save_post_id_from_details(details, post_type)
                                self.page.keyboard.press("Escape")
                                return True
                            else:
                                print("⚠️ Không lấy được post_id từ get_id_from_url")
                        except Exception as e:
                            # Không được nuốt STOP/PAUSE
                            if isinstance(e, RuntimeError) and ("EMERGENCY_STOP" in str(e) or "BROWSER_CLOSED" in str(e)):
                                raise
                            print(f"❌ Lỗi khi gọi get_id_from_url: {e}")
                    break
                self.page.wait_for_timeout(150)

            print("⚠️ Không lấy được Payload URL")
            self.page.keyboard.press("Escape")
            return False

        except Exception as e:
            # Không được nuốt STOP/PAUSE
            if isinstance(e, RuntimeError) and ("EMERGENCY_STOP" in str(e) or "BROWSER_CLOSED" in str(e)):
                raise
            print(f"❌ share_center_ad lỗi: {e}")
            self.page.keyboard.press("Escape")
            return False

    # ===================== CÁC HÀM KHÁC GIỮ NGUYÊN =====================
    def save_post_id_from_details(self, details, post_type):
        """
        Lưu post từ dict details trả về từ get_id_from_url
        details chứa: post_id, owning_profile, post_text
        """
        try:
            post_id = details.get("post_id")
            if not post_id:
                print("⚠️ Không có post_id trong details")
                return False
                
            folder = get_data_dir() / "post_ids"
            folder.mkdir(parents=True, exist_ok=True)
            filepath = folder / f"{self.profile_id}.json"

            data = []
            if filepath.exists():
                try:
                    with filepath.open("r", encoding="utf8") as f:
                        data = json.load(f)
                except:
                    data = []

            # 1. Tránh trùng ID (Check cả format cũ post_id và mới id)
            for item in data:
                existing_id = item.get("id") or item.get("post_id")
                if existing_id == post_id:
                    print(f"🔁 ID {post_id} đã tồn tại -> bỏ qua.")
                    return False

            # 2. Format dữ liệu JSON theo yêu cầu
            # Map flag: green -> xanh, yellow -> vàng
            flag_vn = "xanh" if post_type == "green" else "vàng" if post_type == "yellow" else post_type
            
            # Lấy thông tin từ kết quả worker trả về
            post_text = details.get("post_text", "")
            owning_profile = details.get("owning_profile", {})

            record = {
                "id": post_id,
                "flag": flag_vn,
                "text": post_text,
                "owning_profile": owning_profile
            }

            data.append(record)

            with filepath.open("w", encoding="utf8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            print(f"💾 Đã lưu Post {post_id} | Chủ bài: {owning_profile.get('name', 'N/A')}")
            
            return True
        except Exception as e:
            print(f"❌ Lỗi save_post_id_from_details: {e}")
            return False


    def scan_while_scrolling(self):
        try:
            viewport = self.page.viewport_size
            height = viewport['height'] if viewport else 800

            normal_step = height * 0.12
            escape_step = height * 0.35  # 👈 THOÁT MODULE RÁC

            print("⬇️ Scan theo center-post (LOCK khi thấy xanh)")

            while True:
                self.control_checkpoint("before_scroll_loop")
                post = self.get_center_post()

                # =========================
                # ❌ KHÔNG PHẢI POST → THOÁT NGAY
                # =========================
                if not post:
                    # đang đứng trên ref / kết bạn / module rác
                    self.control_checkpoint("before_escape_wheel")
                    self.smooth_scroll(escape_step)
                    # Đợi một chút để trang render lại sau khi scroll
                    time.sleep(random.uniform(0.12, 0.15))
                    continue

                # =========================
                # POST ĐÃ XỬ LÝ → ĐẨY RA KHỎI VIEW
                # =========================
                if self.check_post_is_processed(post):
                    try:
                        self.control_checkpoint("before_normal_wheel")
                        self.smooth_scroll(normal_step)
                        # Đợi một chút để trang render lại sau khi scroll
                        time.sleep(random.uniform(0.08, 0.12))
                    except Exception as e:
                        error_msg = str(e).lower()
                        if any(keyword in error_msg for keyword in ["closed", "disconnected", "target page", "context or browser"]):
                            raise RuntimeError("BROWSER_CLOSED") from e
                        raise
                    continue

                # =========================
                # LOCK POST HỢP LỆ
                # =========================
                is_ad = self.check_current_post_is_ad(post)

                if is_ad:
                    print("🟥 ADS detected (center-post)")
                    return post, "green"
                else:
                    print("🟨 Bài thường detected (center-post)")
                    return post, "yellow"

        except Exception as e:
            error_msg = str(e).lower()
            # Nếu browser/page đã bị đóng thì raise exception đặc biệt để bot dừng
            if any(keyword in error_msg for keyword in ["closed", "disconnected", "target page", "context or browser"]):
                print(f"🛑 Browser đã bị đóng trong scan_while_scrolling -> Raise exception")
                raise RuntimeError("BROWSER_CLOSED") from e
            print(f"⚠️ Lỗi scan: {e}")
            return None, None

    def like_current_post(self, post_handle):
        print("❤️ Đang thực hiện Like bài viết này...")
        try:
            self.control_checkpoint("before_like")
            element = post_handle.as_element()
            if not element: return False
            already_liked = element.query_selector('div[role="button"][aria-label="Gỡ Thích"], div[role="button"][aria-label="Remove Like"]')
            if already_liked:
                print("⚠️ Bài này đã Like rồi -> Bỏ qua.")
                return False
            
            # Like theo xác suất để đảm bảo khoảng cách 45-90 giây giữa các lần like:
            # - Với nghỉ 12-20s sau mỗi bài, để có khoảng cách 45-90s cần like 20-30% bài
            # - Sau đó roll để quyết định có Like hay không
            p = random.uniform(0.3, 0.4)
            roll = random.random()
            should_like = roll < p
            print(f"🎲 [LikeProb] p={p:.2f} roll={roll:.2f} -> {'LIKE' if should_like else 'SKIP'}")
            
            if not should_like:
                print("⏭️ Skip Like theo xác suất random")
                return False
            
            selector = 'div[role="button"][aria-label="Thích"], div[role="button"][aria-label="Like"]'
            like_btn = element.query_selector(selector)
            if like_btn:
                self.bring_element_into_view_smooth(like_btn)
                smart_sleep(0.5, self.profile_id)
                self.control_checkpoint("before_like_click")
                like_btn.click()
                self.control_checkpoint("after_like_click")
                print("✅ Đã Bấm Like thành công!")
                return True
            else:
                print("⚠️ Không tìm thấy nút Like phù hợp.")
                return False
        except Exception as e:
            if isinstance(e, RuntimeError) and ("EMERGENCY_STOP" in str(e) or "BROWSER_CLOSED" in str(e)):
                raise
            print(f"❌ Lỗi Like: {e}")
            return False

    


    def get_center_post(self):
        try:
            return self.page.evaluate_handle("""
                () => {
                    const x = window.innerWidth / 2;
                    const y = window.innerHeight * 0.45;
                    const el = document.elementFromPoint(x, y);
                    if (!el) return null;

                    // =========================
                    // 1. CHECK CONTEXT: SEARCH PAGE?
                    // =========================
                    const isSearchPage = !!document.querySelector(
                        'h1, span'
                    ) && [...document.querySelectorAll('h1, span')]
                        .some(e => e.innerText?.trim() === 'Kết quả tìm kiếm');

                    // =========================
                    // 2. CHỌN CONTAINER PHÙ HỢP
                    // =========================
                    const POST_SELECTOR = isSearchPage
                        ? 'div.x78zum5.xdt5ytf'   // search page
                        : 'div.x1lliihq';         // home / feed

                    let cur = el.closest(POST_SELECTOR);

                    while (cur) {
                        // ✅ PHẢI CÓ LIKE BUTTON → mới là post thật
                        const hasLike = cur.querySelector(
                            'div[aria-label="Thích"], div[aria-label="Like"],' +
                            'div[aria-label="Gỡ Thích"], div[aria-label="Remove Like"]'
                        );

                        if (hasLike) {
                            cur.style.outline = "4px solid #00ff00";
                            cur.setAttribute('data-center-post', 'true'); // 🔒 MARK
                            return cur;
                        }

                        cur = cur.parentElement?.closest(POST_SELECTOR);
                    }

                    return null;
                }
            """)
        except:
            return None

    def check_current_post_is_ad(self, post_handle):
        if not post_handle or not post_handle.as_element(): return False
        return post_handle.evaluate("""
            (post) => {
                if (post.getAttribute('data-bot-processed') === 'true') return false;
                const checkAnchors = (element) => {
                    if (!element) return false;
                    const anchors = Array.from(element.querySelectorAll('a[href*="__cft__"]'));
                    for (const a of anchors) {
                        const href = a.getAttribute('href');
                        if (!href) continue;
                        if (href.includes('__tn__')) continue;
                        let m = href.match(/__cft__\\[0\\]=([^&#]+)/) || href.match(/__cft__%5B0%5D=([^&#]+)/);
                        if (m && m[1]) return true; 
                    }
                    return false;
                };
                if (checkAnchors(post)) { post.style.outline = "5px solid red"; return true; }
                if (post.parentElement && checkAnchors(post.parentElement)) { post.style.outline = "5px solid red"; return true; }
                if (post.parentElement && post.parentElement.parentElement && checkAnchors(post.parentElement.parentElement)) { post.style.outline = "5px solid red"; return true; }
                return false;
            }
        """)

    def mark_post_as_processed(self, post_handle):
        try:
            post_handle.evaluate("""(post) => {
                post.setAttribute('data-bot-processed', 'true');
                post.style.outline = "5px solid gray"; 
                post.style.opacity = "0.7";
            }""")
            print("🏁 Đã đánh dấu bài viết: DONE.")
        except: pass
        
    def save_cookies(self):
        """
        Lấy cookie từ browser context và lưu thẳng vào:
        backend/config/settings.json -> PROFILE_IDS[profile_id]["cookie"]
        Trả về cookie_string.
        """
        try:
            print("🍪 Đang trích xuất Cookie (Key=ID, Value=String)...")
            
            # 1. Lấy toàn bộ cookies
            all_cookies = self.page.context.cookies()
            if not all_cookies:
                print("⚠️ Chưa đăng nhập.")
                return None

            # 2. Danh sách các trường cần lấy (Đúng thứ tự Sếp gửi)
            target_keys = [
                "sb", "ps_l", "ps_n", "datr", "c_user", 
                "ar_debug", "fr", "xs", "wd"
            ]
            
            # Tạo map để tra cứu
            cookie_map = {c['name']: c['value'] for c in all_cookies}
            
            # 3. Ghép chuỗi string
            cookie_parts = []
            for key in target_keys:
                if key in cookie_map:
                    cookie_parts.append(f"{key}={cookie_map[key]}")
            
            # Tạo chuỗi kết quả (nếu có dữ liệu)
            if cookie_parts:
                cookie_string = "; ".join(cookie_parts) + ";"
            else:
                cookie_string = ""

            # 4. Lưu vào settings.json theo đúng profile_id (với lock để tránh race condition)
            try:
                if not SETTINGS_PATH.exists():
                    print(f"⚠️ Không tìm thấy settings.json: {SETTINGS_PATH}")
                    return cookie_string

                pid = str(self.profile_id or "").strip()
                if not pid:
                    print("⚠️ profile_id rỗng, không ghi vào settings.json")
                    return cookie_string

                # 🔒 Dùng lock để tránh race condition khi nhiều profile cùng lưu cookie
                with _settings_write_lock:
                    # Đọc lại file trong lock để đảm bảo có dữ liệu mới nhất
                    with SETTINGS_PATH.open("r", encoding="utf-8") as f:
                        raw = json.load(f)

                    if not isinstance(raw, dict):
                        raw = {}

                    profiles = raw.get("PROFILE_IDS")
                    if profiles is None or isinstance(profiles, (list, str)):
                        profiles = {}
                    if not isinstance(profiles, dict):
                        profiles = {}

                    cfg = profiles.get(pid)
                    if not isinstance(cfg, dict):
                        cfg = {}
                    cfg["cookie"] = cookie_string
                    profiles[pid] = cfg
                    raw["PROFILE_IDS"] = profiles

                    # Ghi file (atomic write: temp file rồi replace)
                    import tempfile
                    directory = str(SETTINGS_PATH.parent)
                    os.makedirs(directory, exist_ok=True)
                    fd, tmp_path = tempfile.mkstemp(prefix="settings_", suffix=".json", dir=directory)
                    try:
                        with os.fdopen(fd, "w", encoding="utf-8") as f:
                            json.dump(raw, f, ensure_ascii=False, indent=2)
                            f.write("\n")
                        os.replace(tmp_path, str(SETTINGS_PATH))
                    except Exception:
                        try:
                            os.remove(tmp_path)
                        except Exception:
                            pass
                        raise

                print(f"✅ Đã cập nhật cookie vào settings.json cho profile_id={pid}")
            except Exception as e:
                print(f"⚠️ Không ghi được cookie vào settings.json: {e}")

            return cookie_string
            
        except Exception as e:
            print(f"❌ Lỗi lưu cookies: {e}")
            return None
        
    def process_post(self, post_handle, post_type):
        """
        post_type: 'green' (ads) | 'yellow' (normal)
        """
        viewport = self.page.viewport_size
        if viewport: height = viewport['height']
        else: height = 800 
        try:
            self.control_checkpoint("before_process_post")
            print(f"🧠 Xử lý bài viết type={post_type}")

            # 1. Expand nội dung
            expanded = self.page.evaluate(JS_EXPAND_SCRIPT, post_handle)
            if expanded > 0:
                print(f"📖 Đã mở {expanded} 'Xem thêm'")
                smart_sleep(1.2, self.profile_id)

            # 2. Check keyword (chung cho cả ads & thường)
            has_keyword = self.page.evaluate(
                JS_CHECK_AND_HIGHLIGHT_SCOPED,
                [post_handle, self.job_keywords]
            )

            if not has_keyword:
                print("❌ Không có keyword -> skip bài")

                # 1. Đánh dấu đã xử lý
                self.mark_post_as_processed(post_handle)

                # 2. 🚨 ĐẨY POST RA KHỎI VIEWPORT (QUAN TRỌNG)
                try:
                    viewport = self.page.viewport_size
                    height = viewport['height'] if viewport else 800
                    self.smooth_scroll(height * 0.4)
                except Exception as e:
                    error_msg = str(e).lower()
                    if any(keyword in error_msg for keyword in ["closed", "disconnected", "target page", "context or browser"]):
                        raise RuntimeError("BROWSER_CLOSED") from e
                    pass

                return False

            print("✅ Có keyword")

            # 2b. Nếu user nhập text (Setting profile -> Quét bài viết) thì bắt buộc
            # bài phải có ít nhất 1 trong các từ/cụm từ đó (lọc giống Nuôi acc).
            if getattr(self, "user_keywords", None):
                try:
                    has_user_text = self.page.evaluate(
                        JS_CHECK_AND_HIGHLIGHT_SCOPED,
                        [post_handle, self.user_keywords]
                    )
                except Exception:
                    has_user_text = False
                if not has_user_text:
                    print("❌ Không đạt text nhập -> skip bài")

                    # Đánh dấu đã xử lý + đẩy ra khỏi view
                    self.mark_post_as_processed(post_handle)
                    try:
                        viewport = self.page.viewport_size
                        height = viewport['height'] if viewport else 800
                        self.smooth_scroll(height * 0.4)
                    except Exception as e:
                        error_msg = str(e).lower()
                        if any(keyword in error_msg for keyword in ["closed", "disconnected", "target page", "context or browser"]):
                            raise RuntimeError("BROWSER_CLOSED") from e
                        pass
                    return False

            # 3. Like
            self.like_current_post(post_handle)
            self.control_checkpoint("after_like")

            # 4. Share để bắt ID
            ok = self.share_center_ad(post_handle, post_type)
            self.control_checkpoint("after_share")
            
            # Nếu share_center_ad return False, đợi thêm một chút và kiểm tra lại URL
            # (vì URL có thể được bắt bất đồng bộ sau khi hàm đã return)
            if not ok:
                print("⏳ Đợi thêm 2 giây để kiểm tra lại URL...")
                for _ in range(20):  # 20 lần x 0.1s = 2 giây
                    self.control_checkpoint("wait_for_url_after_share")
                    if self.captured_payload_url:
                        print(f"✅ Phát hiện URL sau khi share_center_ad return: {self.captured_payload_url}")
                        if get_id_from_url:
                            try:
                                print(f"📥 Đang gọi get_id_from_url với URL: {self.captured_payload_url}")
                                details = get_id_from_url(self.captured_payload_url, self.profile_id)
                                if details and details.get("post_id"):
                                    self.save_post_id_from_details(details, post_type)
                                    # Đảm bảo đóng modal nếu chưa đóng
                                    try:
                                        self.page.keyboard.press("Escape")
                                    except:
                                        pass
                                    ok = True
                                    break
                                else:
                                    print("⚠️ Không lấy được post_id từ get_id_from_url")
                            except Exception as e:
                                if isinstance(e, RuntimeError) and ("EMERGENCY_STOP" in str(e) or "BROWSER_CLOSED" in str(e)):
                                    raise
                                print(f"❌ Lỗi khi gọi get_id_from_url: {e}")
                        else:
                            print("⚠️ get_id_from_url không khả dụng (import failed)")
                    self.page.wait_for_timeout(100)
                
                if not ok:
                    self.mark_post_as_processed(post_handle)
                    print("⚠️ Không bắt được ID -> skip")
                    return False
            # 5. Lưu ID + flag

            # 6. Mark processed
            self.mark_post_as_processed(post_handle)
            

            return True

        except Exception as e:
            if isinstance(e, RuntimeError) and ("EMERGENCY_STOP" in str(e) or "BROWSER_CLOSED" in str(e)):
                raise
            print(f"❌ Lỗi process_post: {e}")
            return False

    def check_post_is_processed(self, post_handle):
        """Kiểm tra attribute data-bot-processed để tránh quét lại"""
        try:
            return post_handle.evaluate("(post) => post.getAttribute('data-bot-processed') === 'true'")
        except:
            return False
    
    def smooth_scroll(self, distance):
        """
        Cuộn mượt mà với nhiều step nhỏ để giống người dùng thật.
        - Chia thành 15-25 step ngẫu nhiên
        - Mỗi step nghỉ 0.01-0.05s
        """
        try:
            num_steps = random.randint(15, 25)
            step_distance = distance / num_steps
            
            for _ in range(num_steps):
                self.page.mouse.wheel(0, step_distance)
                sleep_time = random.uniform(0.01, 0.03)
                self.page.wait_for_timeout(int(sleep_time * 1000))
        except Exception as e:
            # Fallback: scroll một lần nếu lỗi
            try:
                self.page.mouse.wheel(0, distance)
            except:
                pass
    
    def bring_element_into_view_smooth(self, element):
        """
        Kiểm tra element (nút Share) có trong màn hình không.
        Nếu không, cuộn chuột nhẹ nhàng tới nó (Không dùng scroll_into_view gây giật).
        """
        try:
            box = element.bounding_box()
            if not box: return False # Element chưa render

            viewport = self.page.viewport_size
            vh = None
            try:
                if viewport and isinstance(viewport, dict):
                    vh = viewport.get('height')
            except Exception:
                vh = None

            # Fallback: đôi khi connect qua CDP => viewport_size = None
            if not vh:
                try:
                    vh = self.page.evaluate("() => window.innerHeight") or 800
                except Exception:
                    vh = 800
            
            # Tọa độ Y của element so với đỉnh màn hình hiện tại
            element_y = box['y']
            element_height = box['height']

            # Kiểm tra: Nút có nằm lọt thỏm trong màn hình không?
            # (Cho phép lề trên 100px, lề dưới 100px để chắc chắn click được)
            is_in_view = (element_y > 100) and (element_y + element_height < vh - 100)

            if is_in_view:
                return True # Đang đẹp rồi, không cần cuộn

            # Nếu nút nằm dưới đáy màn hình -> Cần cuộn xuống
            if element_y > vh - 100:
                # Tính khoảng cách cần cuộn: Đưa nút lên vị trí khoảng 70% màn hình
                scroll_distance = element_y - (vh * 0.7)
                print(f"    -> 🔽 Nút Share bị che, cuộn xuống {int(scroll_distance)}px")
                
                # Cuộn mượt
                self.smooth_scroll(scroll_distance)
                return True
            
            return True
        except Exception as e:
            # Log nhẹ để không spam, lỗi thường do viewport null / element detach
            print(f"⚠️ Lỗi tính toán cuộn: {e}")
            return False

    def scroll_past_post(self, post_handle):
        """
        Cuộn qua bài viết hiện tại một cách thông minh.
        - Bài ngắn: Cuộn ít.
        - Bài dài: Cuộn nhiều.
        -> Tránh việc dùng PageDown bị trôi bài.
        """
        try:
            box = post_handle.bounding_box()
            if not box:
                # Fallback nếu không lấy được kích thước -> Dùng PageDown
                self.page.keyboard.press("PageDown")
                return

            post_height = box['height']
            post_y = box['y']
            
            # Chiến thuật: Cuộn sao cho ĐÁY bài viết hiện tại trôi lên mép trên màn hình
            # Cộng thêm 50px padding để tách biệt bài sau
            scroll_distance = post_y + post_height + 50
            
            # Cuộn mượt với nhiều step
            self.smooth_scroll(scroll_distance)
                
            print(f"    -> 📉 Đã cuộn qua bài (height={int(post_height)}px)")

        except Exception as e:
            print(f"⚠️ Lỗi scroll_past_post: {e}")
            self.page.keyboard.press("PageDown")