import time
import random
from playwright.sync_api import sync_playwright
import json
import pyperclip
import re
from urllib.parse import urlparse, parse_qs, unquote
import os

# ==============================================================================
# JS TOOLS & HELPER FUNCTIONS
# ==============================================================================
JS_EXPAND_SCRIPT = """
(node) => {
    if (!node) return 0;
    const keywords = ["Xem thêm", "See more"];
    let clickedCount = 0;
    const buttons = node.querySelectorAll('[role="button"]');
    buttons.forEach(btn => {
        const text = btn.innerText ? btn.innerText.trim() : "";
        if (keywords.includes(text)) {
            if (btn.offsetWidth > 0 && btn.offsetHeight > 0) {
                btn.scrollIntoView({block: "center", inline: "nearest"});
                btn.click();
                clickedCount++;
                btn.style.border = "2px solid red";
            }
        }
    });
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
        
        # [THAY ĐỔI] Tách thành 2 biến để quản lý ưu tiên
        # self.captured_payload_id = None  # ID từ Request (Dự phòng)
        self.captured_response_id = None # ID từ Response (Ưu tiên)
        
        self.job_keywords = [
            "tuyển dụng", "tuyển nhân viên", "tuyển gấp", "việc làm", 
            "lương", "thu nhập", "phỏng vấn", "cv", "hồ sơ",
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
        print("🛰  Đã kích hoạt Sniffer: Chế độ ưu tiên Response > Payload...")

        # 1. BẮT PAYLOAD (DỰ PHÒNG)
        # def on_request(request):
        #     if "facebook.com/api/graphql" in request.url and request.method == "POST":
        #         # Chỉ lưu nếu chưa có Payload ID (để tránh ghi đè liên tục)
        #         if not self.captured_payload_id:
        #             try:
        #                 raw_url = parse_graphql_payload(request.post_data)
        #                 if raw_url:
        #                     pid = extract_facebook_post_id(raw_url)
        #                     if pid:
        #                         self.captured_payload_id = pid
        #                         print(f"⚡ [REQ-Payload] Đã lưu ID dự phòng: {pid}")
        #             except: pass

        # 2. BẮT RESPONSE (ƯU TIÊN)
        def on_response(response):
            if "facebook.com/api/graphql" in response.url and response.status == 200:
                # Nếu chưa bắt được Response ID thì mới xử lý
                if not self.captured_response_id:
                    try:
                        data = response.json()
                        preview_data = data.get("data", {}).get("xma_preview_data", {})
                        pid = preview_data.get("post_id")
                        
                        if pid:
                            self.captured_response_id = str(pid)
                            print(f"🎯 [RES-Json] Bắt dính ID CHÍNH THỨC: {self.captured_response_id}")
                    except: pass

        # self.page.on("request", on_request)
        self.page.on("response", on_response)

    # ===================== SHARE & CHỜ ID (LOGIC MỚI) =====================
    def share_center_ad(self, post_handle):
        try:
            print("🚀 Đang thực hiện share để bắt ID (Ưu tiên Response)...")
            
            # 1. Reset sạch sẽ cả 2 biến
            # self.captured_payload_id = None
            self.captured_response_id = None
            
            # 2. Click nút Share
            xpath_selector = 'xpath=.//div[@data-ad-rendering-role="share_button"]/ancestor::div[@role="button"]'
            share_btn = post_handle.query_selector(xpath_selector)
            
            if share_btn:
                share_btn.scroll_into_view_if_needed()
                self.page.wait_for_timeout(500) 
                share_btn.click()
                print("✅ Đã click nút Share. Đang đợi Server trả lời...")
                
                # 3. Vòng lặp chờ (Chờ RESPONSE là chính)
                # Chờ tối đa 10 giây (50 * 200ms)
                for i in range(50): 
                    # ƯU TIÊN 1: Nếu có Response ID -> Lấy luôn, nghỉ khỏe
                    if self.captured_response_id:
                        print(f"🎉 SUCCESS: Server đã trả về ID chuẩn: {self.captured_response_id}")
                        self.save_post_id(self.captured_response_id)
                        
                        self.page.wait_for_timeout(2000) # Đợi 2s như ý Sếp
                        self.page.keyboard.press("Escape")
                        return True
                    
                    # Chưa thấy Response thì đợi tiếp, KHÔNG check Payload vội
                    # Để cho Payload có thời gian "xếp hàng" chờ Response
                    self.page.wait_for_timeout(200)
                
                # 4. HẾT GIỜ MÀ KHÔNG CÓ RESPONSE -> DÙNG PHAO CỨU SINH (PAYLOAD)
                # print("⚠️ Server phản hồi chậm/lỗi. Kiểm tra ID dự phòng từ Payload...")
                
                # if self.captured_payload_id:
                #      print(f"🎉 OK! Dùng tạm ID từ Payload (Request): {self.captured_payload_id}")
                #      self.save_post_id(self.captured_payload_id)
                     
                #      self.page.wait_for_timeout(2000)
                #      self.page.keyboard.press("Escape")
                #      return True

                # 5. Cả 2 đều không có
                print("⚠️ Server không trả ID -> BỎ QUA (Skip).")
                self.page.keyboard.press("Escape") # Tắt popup để còn cuộn tiếp
                return False
            else:
                print("⚠️ Không tìm thấy nút Share.")
                return False
                
        except Exception as e:
            print(f"❌ Lỗi share_center_ad: {e}")
            self.page.keyboard.press("Escape")
            return False

    # ===================== CÁC HÀM KHÁC GIỮ NGUYÊN =====================
    def save_post_id(self, post_id):
        try:
            folder = "data/post_ids"
            os.makedirs(folder, exist_ok=True)
            filepath = f"{folder}/{self.profile_id}.json"
            data = []
            if os.path.exists(filepath):
                try:
                    with open(filepath, "r", encoding="utf8") as f: data = json.load(f)
                except: pass
            if post_id in data:
                print("🔁 ID trùng -> bỏ qua.")
                return False
            data.append(post_id)
            with open(filepath, "w", encoding="utf8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"💾 Đã lưu ID {post_id} vào file.")
            return True
        except: return False

    def scan_while_scrolling(self):
        try:
            viewport = self.page.viewport_size
            if viewport: height = viewport['height']
            else: height = 800 
            total_distance = int(height * 0.6) 
            steps = random.randint(15, 25)
            step_size = total_distance / steps
            print(f"⬇️ Đang lướt {total_distance}px (vừa lướt vừa soi)...")

            for i in range(steps):
                self.page.mouse.wheel(0, step_size)
                time.sleep(random.uniform(0.03, 0.08)) 
                if i > 0 and i % 4 == 0:
                    current_post = self.get_center_post()
                    if current_post and self.check_current_post_is_ad(current_post):
                        print(f"🛑 ĐANG CUỘN THÌ BẮT ĐƯỢC ADS! (Tại bước {i}/{steps})")
                        current_post.scroll_into_view_if_needed()
                        return current_post
            
            delay = random.uniform(2.0, 3.5)
            print(f"⬇️ Đã cuộn xong (Không có Ads mới). Nghỉ {delay:.1f}s...")
            time.sleep(delay)
            return None
        except Exception as e:
            print(f"⚠️ Lỗi cuộn: {e} -> Dùng PageDown đỡ.")
            try: self.page.keyboard.press("PageDown"); time.sleep(2)
            except: pass
            return None

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

    def process_ad_content(self, post_handle):
        try:
            print("    -> 🔍 Đang soi chi tiết bài Ads...")
            expanded = self.page.evaluate(JS_EXPAND_SCRIPT, post_handle)
            if expanded > 0:
                print(f"    -> 📖 Đã click {expanded} nút 'Xem thêm'.")
                time.sleep(1.5)
            has_keyword = self.page.evaluate(JS_CHECK_AND_HIGHLIGHT_SCOPED, [post_handle, self.job_keywords])
            if has_keyword:
                print("    -> ✅ FOUND: Bài Ads chứa từ khóa!")
                return True
            else:
                print("    -> ❌ SKIP: Không thấy từ khóa tuyển dụng.")
                return False
        except Exception as e:
            print(f"❌ Lỗi process_ad_content: {e}")
            return False

    def get_center_post(self):
        try:
            return self.page.evaluate_handle("""
                () => {
                    const x = window.innerWidth / 2;
                    const y = window.innerHeight * 0.45;
                    let el = document.elementFromPoint(x, y);
                    if (!el) return null;
                    const post = el.closest('div[role="article"], div.x1lliihq');
                    if (post) {
                        post.style.outline = "3px solid #00ff00";
                        return post;
                    }
                    return null;
                }
            """)
        except: return None

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