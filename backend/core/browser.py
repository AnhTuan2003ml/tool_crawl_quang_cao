import time
import random
from playwright.sync_api import sync_playwright
import json
import re
from urllib.parse import urlparse, parse_qs, unquote
import os
from worker.get_id import get_id_from_url
import sys
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
        self.all_profile_ids = [
        p.strip()
        for p in os.getenv("PROFILE_IDS", "").split(",")
        if p.strip()
        ]
        # [THAY ĐỔI] Tách thành 2 biến để quản lý ưu tiên
        self.captured_payload_url = None  # ID từ Request (Dự phòng)
        self.captured_response_id = None # ID từ Response (Ưu tiên)
        
        self.job_keywords = [
            "tuyển dụng", "tuyển nhân viên", "tuyển gấp", "việc làm", 
            "lương", "phỏng vấn", "hồ sơ",
            "full-time", "part-time", "thực tập", "kế toán", "may mặc", "kcn" ,"Ứng viên " , "Ứng tuyển"
        ]

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
        print("🛰  Đã kích hoạt Sniffer: Chế độ Response > Payload URL...")

        # 1. BẮT URL TỪ REQUEST (DỰ PHÒNG CHO VIEW-SOURCE)
        def on_request(request):
            if "facebook.com/api/graphql" in request.url and request.method == "POST":
                try:
                    raw_url = parse_graphql_payload(request.post_data)
                    if raw_url:
                        # Chỉ lưu nếu nó giống link bài viết
                        if "facebook.com" in raw_url or "pfbid" in raw_url:
                            self.captured_payload_url = raw_url
                            # print(f"🔗 [DEBUG] Bắt được Link tiềm năng: {raw_url[:50]}...")
                except: pass

        # 2. BẮT ID TỪ RESPONSE (ƯU TIÊN TUYỆT ĐỐI)
        def on_response(response):
            if "facebook.com/api/graphql" in response.url and response.status == 200:
                if not self.captured_response_id:
                    try:
                        data = response.json()
                        preview_data = data.get("data", {}).get("xma_preview_data", {})
                        pid = preview_data.get("post_id")
                        if pid:
                            self.captured_response_id = str(pid)
                            print(f"🎯 [RES-Json] Bắt dính ID CHÍNH THỨC: {self.captured_response_id}")
                    except: pass

        self.page.on("request", on_request)
        self.page.on("response", on_response)

    # ===================== SHARE & CHỜ ID (LOGIC MỚI) =====================
    def share_center_ad(self, post_handle, post_type):
        try:
            print("🚀 Share → bắt ID (Response → Payload → ViewSource)")

            self.captured_payload_url = None
            self.captured_response_id = None

            share_btn = post_handle.query_selector(
                'xpath=.//div[@data-ad-rendering-role="share_button"]/ancestor::div[@role="button"]'
            )
            if not share_btn:
                print("⚠️ Không tìm thấy nút Share")
                return False

            share_btn.scroll_into_view_if_needed()
            self.page.wait_for_timeout(300)
            share_btn.click()

            # ===== ƯU TIÊN RESPONSE =====
            for _ in range(50):
                if self.captured_response_id:
                    self.dispatch_get_id_for_all_profiles(self.captured_response_id)
                    self.save_post_id(self.captured_response_id, post_type)
                    self.page.keyboard.press("Escape")
                    return True
                self.page.wait_for_timeout(150)

            # ===== FALLBACK VIEW-SOURCE =====
            if self.captured_payload_url:
                source_id = self.get_id_blocking_mode(self.captured_payload_url)
                if source_id:
                    self.save_post_id(source_id, post_type)
                    self.page.keyboard.press("Escape")
                    return True

            print("⚠️ Không lấy được ID")
            self.page.keyboard.press("Escape")
            return False

        except Exception as e:
            print(f"❌ share_center_ad lỗi: {e}")
            self.page.keyboard.press("Escape")
            return False

    # ===================== CÁC HÀM KHÁC GIỮ NGUYÊN =====================
    def save_post_id(self, post_id, post_type):
        try:
            folder = "data/post_ids"
            os.makedirs(folder, exist_ok=True)
            filepath = f"{folder}/{self.profile_id}.json"

            data = []
            if os.path.exists(filepath):
                try:
                    with open(filepath, "r", encoding="utf8") as f:
                        data = json.load(f)
                except:
                    data = []

            # 1. Tránh trùng ID (Check cả format cũ post_id và mới id)
            for item in data:
                existing_id = item.get("id") or item.get("post_id")
                if existing_id == post_id:
                    print(f"🔁 ID {post_id} đã tồn tại -> bỏ qua.")
                    return False

            # 2. [NEW] Gọi Worker lấy thông tin chi tiết
            print(f"📥 Đang fetch chi tiết bài viết {post_id} (chờ worker)...")
            
            # Tạo link giả lập để worker xử lý
            target_url = f"https://www.facebook.com/{post_id}"
            
            details = {}
            if get_id_from_url:
                try:
                    # Truyền profile_id để worker dùng đúng cookie của trình duyệt đang chạy
                    details = get_id_from_url(target_url, self.profile_id)
                except Exception as e:
                    print(f"⚠️ Lỗi khi gọi get_id_from_url: {e}")
            
            # 3. [NEW] Format dữ liệu JSON theo yêu cầu
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

            with open(filepath, "w", encoding="utf8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            print(f"💾 Đã lưu Post {post_id} | Chủ bài: {owning_profile.get('name', 'N/A')}")
            
            # Dispatch cho các profile khác (nếu Sếp dùng logic cũ)
            self.dispatch_get_id_for_all_profiles(post_id)
            
            return True
        except Exception as e:
            print(f"❌ Lỗi save_post_id: {e}")
            return False


    def scan_while_scrolling(self):
        try:
            viewport = self.page.viewport_size
            height = viewport['height'] if viewport else 800

            normal_step = height * 0.12
            escape_step = height * 0.35  # 👈 THOÁT MODULE RÁC

            print("⬇️ Scan theo center-post (LOCK khi thấy xanh)")

            while True:
                post = self.get_center_post()

                # =========================
                # ❌ KHÔNG PHẢI POST → THOÁT NGAY
                # =========================
                if not post:
                    # đang đứng trên ref / kết bạn / module rác
                    self.page.mouse.wheel(0, escape_step)
                    time.sleep(random.uniform(0.12, 0.13))
                    continue

                # =========================
                # POST ĐÃ XỬ LÝ → ĐẨY RA KHỎI VIEW
                # =========================
                if self.check_post_is_processed(post):
                    self.page.mouse.wheel(0, normal_step)
                    time.sleep(random.uniform(0.08, 0.15))
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
            print(f"⚠️ Lỗi scan: {e}")
            return None, None




       

    def like_current_post(self, post_handle):
        print("❤️ Đang thực hiện Like bài viết này...")
        try:
            element = post_handle.as_element()
            if not element: return False
            already_liked = element.query_selector('div[role="button"][aria-label="Gỡ Thích"], div[role="button"][aria-label="Remove Like"]')
            if already_liked:
                print("⚠️ Bài này đã Like rồi -> Bỏ qua.")
                return False
            selector = 'div[role="button"][aria-label="Thích"], div[role="button"][aria-label="Like"]'
            like_btn = element.query_selector(selector)
            if like_btn:
                like_btn.scroll_into_view_if_needed()
                time.sleep(0.5)
                like_btn.click()
                print("✅ Đã Bấm Like thành công!")
                return True
            else:
                print("⚠️ Không tìm thấy nút Like phù hợp.")
                return False
        except Exception as e:
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
        """Lưu Cookie dạng Dictionary: { 'PROFILE_ID': 'COOKIE_STRING' }"""
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

            # 4. Tạo cấu trúc dữ liệu theo yêu cầu Sếp
            # Key là Profile ID, Value là chuỗi Cookie
            data_to_save = {
                self.profile_id: cookie_string
            }

            # 5. Lưu vào file JSON
            folder = "data/cookies"
            os.makedirs(folder, exist_ok=True)
            
            # Tên file vẫn là ID profile cho dễ quản lý
            json_path = f"{folder}/{self.profile_id}.json"
            
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(data_to_save, f, indent=2, ensure_ascii=False)
                
            print(f"✅ Đã lưu Cookie format {{ID: String}} vào: {json_path}")
            print(f"\n🔑 DỮ LIỆU ĐÃ LƯU:\n{json.dumps(data_to_save, indent=2)}\n")
            
            return data_to_save
            
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
            print(f"🧠 Xử lý bài viết type={post_type}")

            # 1. Expand nội dung
            expanded = self.page.evaluate(JS_EXPAND_SCRIPT, post_handle)
            if expanded > 0:
                print(f"📖 Đã mở {expanded} 'Xem thêm'")
                time.sleep(1.2)

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
                    self.page.mouse.wheel(0, height * 0.4)
                except:
                    pass

                return False

            print("✅ Có keyword")

            # 3. Like
            self.like_current_post(post_handle)

            # 4. Share để bắt ID
            ok = self.share_center_ad(post_handle, post_type)
            if not ok:
                self.mark_post_as_processed(post_handle)
                print("⚠️ Không bắt được ID -> skip")
                return False
            # 5. Lưu ID + flag

            # 6. Mark processed
            self.mark_post_as_processed(post_handle)
            

            return True

        except Exception as e:
            print(f"❌ Lỗi process_post: {e}")
            return False

    def check_post_is_processed(self, post_handle):
        """Kiểm tra attribute data-bot-processed để tránh quét lại"""
        try:
            return post_handle.evaluate("(post) => post.getAttribute('data-bot-processed') === 'true'")
        except:
            return False
    
    def get_id_blocking_mode(self, url):
        """
        Mở tab mới -> Soi Code -> Tìm chữ "post_id" đầu tiên -> Trả về ngay.
        """
        print(f"⛔ [BLOCKING] Tạm dừng để soi source URL: {url}")
        new_page = None
        found_id = None
        
        try:
            context = self.page.context
            # 1. Mở tab mới
            new_page = context.new_page()
            
            # 2. Truy cập view-source (Treo bot ở đây chờ tải xong mới chạy tiếp)
            target = f"view-source:{url}"
            print("    -> Đang tải source code (Chờ DOMContentLoaded)...")
            new_page.goto(target, wait_until='domcontentloaded', timeout=20000)
            
            # 3. Lấy toàn bộ HTML
            content = new_page.content()
            
            # 4. TÌM KIẾM CHÍNH XÁC "post_id"
            # re.search mặc định sẽ quét từ trên xuống dưới và trả về kết quả ĐẦU TIÊN nó thấy.
            # Đúng ý Sếp: Thấy cái đầu là chốt luôn.
            
            # Pattern 1: Dạng chuẩn "post_id":"12345"
            match = re.search(r'"post_id":"(\d+)"', content)
            
            if match:
                found_id = match.group(1)
                print(f"    -> 💉 BẮT ĐƯỢC ID ĐẦU TIÊN (post_id): {found_id}")
            else:
                # Fallback: Nếu không thấy "post_id" thì mới tìm "story_fbid" (dự phòng)
                match_sub = re.search(r'"story_fbid":"(\d+)"', content)
                if match_sub:
                    found_id = match_sub.group(1)
                    print(f"    -> 💉 Không có post_id, lấy tạm story_fbid: {found_id}")

            if not found_id:
                print("    -> ⚠️ Không tìm thấy ID nào trong source.")

        except Exception as e:
            print(f"    -> ❌ Lỗi khi soi source: {e}")
        finally:
            # 5. Đóng tab ngay lập tức
            if new_page: 
                new_page.close()
                print("    -> Đã đóng tab soi code. Quay lại tab chính...")
                
        return found_id
    
    def dispatch_get_id_for_all_profiles(self, post_id: str):
        """
        Khi đã có post_id → gọi get_id cho toàn bộ PROFILE_IDS
        """
        print(f"📡 Dispatch get_id cho post_id={post_id}")

        for pid in self.all_profile_ids:
            # ❌ Bỏ qua profile hiện tại (tránh tự bắn vào mình)
            if pid == self.profile_id:
                continue

            try:
                print(f"   ➜ Gọi get_id(profile_id={pid}, post_id={post_id})")
                get_id_from_url(pid, post_id)
            except Exception as e:
                print(f"   ❌ Lỗi get_id với profile {pid}: {e}")