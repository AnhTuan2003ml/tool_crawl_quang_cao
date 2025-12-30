import sys
import os
import json
import time
import random
import re
from pathlib import Path

# --- SETUP ĐƯỜNG DẪN ĐỂ IMPORT CORE ---
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from core.nst import connect_profile
from core.nst import stop_profile
from core.browser import FBController
from core import control as control_state
from core.control import smart_sleep
from core.paths import get_config_dir, get_data_dir
GROUPS_JSON_PATH = get_config_dir() / "groups.json"
# Worker lấy page_id/post_id từ URL (dùng cookie theo profile_id trong settings.json)
try:
    from worker.get_id import get_id_from_url
except Exception:
    try:
        from get_id import get_id_from_url
    except Exception:
        get_id_from_url = None

# Lưu mapping group -> page_id theo profile_id

GROUPS_LOCK_PATH = Path(str(GROUPS_JSON_PATH) + ".lock")


def _normalize_group_url(raw: str) -> str:
    s = str(raw or "").strip()
    if not s:
        return ""
    if re.match(r"^https?://", s, flags=re.IGNORECASE):
        return s
    if s.lower().startswith("facebook.com/") or s.lower().startswith("www.facebook.com/"):
        return "https://" + s
    if "/groups/" in s:
        if s.startswith("/"):
            return "https://www.facebook.com" + s
        return "https://www.facebook.com/" + s.lstrip("/")
    return f"https://www.facebook.com/groups/{s}"


def _acquire_groups_lock(timeout_seconds: float = 60.0, poll: float = 0.1):
    """
    Lock file đơn giản (cross-platform): tạo file .lock bằng O_EXCL để chống ghi đè khi nhiều process cùng ghi.
    """
    start = time.time()
    while True:
        try:
            fd = os.open(str(GROUPS_LOCK_PATH), os.O_CREAT | os.O_EXCL | os.O_RDWR)
            return fd
        except FileExistsError:
            # timeout_seconds <= 0 => chờ vô hạn
            if timeout_seconds and timeout_seconds > 0 and (time.time() - start >= timeout_seconds):
                return None
            time.sleep(poll)
        except Exception:
            return None


def _release_groups_lock(fd) -> None:
    try:
        if fd is not None:
            try:
                os.close(fd)
            except Exception:
                pass
        try:
            if GROUPS_LOCK_PATH.exists():
                GROUPS_LOCK_PATH.unlink()
        except Exception:
            pass
    except Exception:
        pass


def _read_groups_json() -> dict:
    try:
        if not GROUPS_JSON_PATH.exists():
            return {}
        raw = GROUPS_JSON_PATH.read_text(encoding="utf-8").strip()
        if not raw:
            return {}
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_groups_json(data: dict) -> None:
    GROUPS_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(GROUPS_JSON_PATH) + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(str(tmp), str(GROUPS_JSON_PATH))


def save_group_page_id(profile_id: str, page_id: str, url_page: str) -> bool:
    """
    Lưu vào backend/config/groups.json theo format:
    {
      "<profile_id>": [
        {"page_id": "...", "url_page": "..."}
      ]
    }
    """
    pid = str(profile_id or "").strip()
    pg = str(page_id or "").strip()
    urlp = str(url_page or "").strip()
    if not pid or not pg or not urlp:
        return False

    fd = _acquire_groups_lock()
    if fd is None:
        # Không có lock => không ghi để tránh race condition khi chạy đa process
        print(f"⚠️ [groups.json] Không lấy được lock trong thời gian chờ -> bỏ qua ghi (profile_id={pid})")
        return False
    try:
        data = _read_groups_json()
        arr = data.get(pid)
        if not isinstance(arr, list):
            arr = []

        # chống trùng theo page_id
        updated = False
        for item in arr:
            if isinstance(item, dict) and str(item.get("page_id") or "").strip() == pg:
                item["url_page"] = urlp
                updated = True
                break

        if not updated:
            arr.append({"page_id": pg, "url_page": urlp})

        data[pid] = arr
        _write_groups_json(data)
        return True
    finally:
        _release_groups_lock(fd)


def replace_all_groups_for_profile(profile_id: str, groups: list[dict]) -> bool:
    """
    Ghi đè toàn bộ groups cho một profile vào groups.json.
    
    Args:
        profile_id: ID của profile
        groups: List các dict với format [{"page_id": "...", "url_page": "..."}, ...]
    
    Returns:
        True nếu thành công, False nếu lỗi
    """
    pid = str(profile_id or "").strip()
    if not pid:
        return False
    
    # Validate groups format
    if not isinstance(groups, list):
        return False
    
    fd = _acquire_groups_lock()
    if fd is None:
        print(f"⚠️ [groups.json] Không lấy được lock trong thời gian chờ -> bỏ qua ghi (profile_id={pid})")
        return False
    
    try:
        data = _read_groups_json()
        # Ghi đè toàn bộ groups cho profile này
        data[pid] = groups
        _write_groups_json(data)
        return True
    except Exception as e:
        print(f"❌ Lỗi khi ghi đè groups.json cho profile {pid}: {e}")
        return False
    finally:
        _release_groups_lock(fd)


def remove_profile_groups(profile_id: str) -> bool:
    """
    Xóa toàn bộ groups của một profile khỏi groups.json.
    
    Args:
        profile_id: ID của profile cần xóa
    
    Returns:
        True nếu thành công, False nếu lỗi
    """
    pid = str(profile_id or "").strip()
    if not pid:
        return False
    
    fd = _acquire_groups_lock()
    if fd is None:
        print(f"⚠️ [groups.json] Không lấy được lock trong thời gian chờ -> bỏ qua xóa (profile_id={pid})")
        return False
    
    try:
        data = _read_groups_json()
        if pid in data:
            del data[pid]
            _write_groups_json(data)
            print(f"✅ Đã xóa groups của profile {pid} khỏi groups.json")
            return True
        else:
            # Profile không có trong groups.json, coi như thành công
            return True
    except Exception as e:
        print(f"❌ Lỗi khi xóa groups của profile {pid} khỏi groups.json: {e}")
        return False
    finally:
        _release_groups_lock(fd)

class GroupJoiner(FBController):
    """
    Class chuyên dụng để đi xin vào nhóm
    """
    def join_group(self, group_id):
        # STOP/PAUSE checkpoint
        try:
            self.control_checkpoint("join_group_start")
        except RuntimeError:
            raise
        raw = str(group_id or "").strip()
        if not raw:
            print("⚠️ group rỗng, bỏ qua")
            return False

        url = _normalize_group_url(raw)
        print(f"\n🚀 Đang truy cập nhóm: {group_id}")
        print(f"🔗 Link: {url}")
        
        try:
            self.control_checkpoint("before_goto_group")
            self.goto(url)
            smart_sleep(random.uniform(3, 5), self.profile_id)  # Chờ load trang

            # 1. Kiểm tra xem đã tham gia chưa
            is_joined = self.page.query_selector('div[aria-label="Đã tham gia"], div[aria-label="Mời"]')
            if is_joined:
                print(f"✅ [SKIP] Đã là thành viên của nhóm {group_id}")
                # coi như "thành công" để vẫn lấy page_id và lưu groups.json
                return True

            # 2. Tìm nút "Tham gia nhóm"
            join_btn_selector = 'div[aria-label="Tham gia nhóm"][role="button"]'
            join_btn = self.page.query_selector(join_btn_selector)

            if not join_btn:
                join_btn = self.page.get_by_text("Tham gia nhóm", exact=True).first
            
            if join_btn:
                print("point 👉 Tìm thấy nút 'Tham gia nhóm'. Đang click...")
                self.control_checkpoint("before_click_join_group")
                join_btn.click()
                
                # ======================================================
                # [MỚI] ẤN ESC 2 LẦN ĐỂ TẮT POPUP CÂU HỎI / NỘI QUY
                # ======================================================
                # Thay sleep cứng bằng auto-wait popup/dialog
                # ======================================================
                try:
                    # Chờ popup dialog (nếu có) rồi đóng
                    self.page.wait_for_selector('div[role="dialog"]', timeout=3000)
                    self.page.keyboard.press("Escape")
                except:
                    pass
                
                try:
                    # Chờ UI cập nhật sau khi đóng popup (không sleep cứng)
                    self.page.wait_for_timeout(800)
                except:
                    pass
                
                # 3. Kiểm tra lại trạng thái
                # Nếu nút chuyển thành "Hủy yêu cầu" hoặc "Đã tham gia" -> Thành công
                check_success = None
                try:
                    # chờ UI cập nhật tối đa 6s (đỡ sai do load chậm)
                    self.page.wait_for_selector('div[aria-label="Hủy yêu cầu"], div[aria-label="Đã tham gia"]', timeout=6000)
                    check_success = self.page.query_selector('div[aria-label="Hủy yêu cầu"], div[aria-label="Đã tham gia"]')
                except Exception:
                    check_success = self.page.query_selector('div[aria-label="Hủy yêu cầu"], div[aria-label="Đã tham gia"]')

                if check_success:
                    print(f"✅ Đã gửi yêu cầu tham gia / đã tham gia: {group_id}")
                    return True

                # Nếu vẫn chưa thấy đổi trạng thái -> coi là chưa join thành công (thường do câu hỏi bắt buộc)
                print(f"⚠️ Click join nhưng chưa thấy đổi trạng thái (có thể cần trả lời câu hỏi): {group_id}")
                return False
            else:
                print(f"❌ Không tìm thấy nút tham gia (Có thể nhóm kín, bị chặn, hoặc layout khác).")
                return False

        except Exception as e:
            if isinstance(e, RuntimeError) and ("EMERGENCY_STOP" in str(e) or "BROWSER_CLOSED" in str(e)):
                raise
            print(f"❌ Lỗi khi xử lý nhóm {group_id}: {e}")
            return False

def run_batch_join_from_list(profile_id, group_ids):
    """
    Chạy join group cho 1 profile với danh sách group truyền trực tiếp (list).
    Dùng cho API (đa luồng/đa process).
    """
    try:
        items = list(group_ids or [])
    except Exception:
        items = []

    # Clean
    cleaned = []
    for gid in items:
        s = str(gid or "").strip()
        if s:
            cleaned.append(s)

    if not cleaned:
        print("⚠️ Danh sách group rỗng.")
        return

    print(f"📋 Tìm thấy {len(cleaned)} nhóm cần tham gia.")

    # 2. Kết nối Profile
    try:
        # STOP/PAUSE checkpoint trước connect
        stop, paused, reason = control_state.check_flags(profile_id)
        if stop:
            print(f"🛑 [JOIN] EMERGENCY_STOP trước khi connect ({reason})")
            return
        if paused:
            print(f"⏸️ [JOIN] PAUSED trước khi connect ({reason})")
            control_state.wait_if_paused(profile_id, sleep_seconds=0.5)

        print(f"🔌 Đang kết nối profile {profile_id}...")
        ws_url = connect_profile(profile_id)
        fb = GroupJoiner(ws_url)
        fb.profile_id = profile_id
        fb.connect()
        
        # 3. Chạy vòng lặp
        for idx, gid in enumerate(cleaned):
            # STOP/PAUSE checkpoint trước mỗi group
            stop, paused, reason = control_state.check_flags(profile_id)
            if stop:
                print(f"🛑 [JOIN] {profile_id} EMERGENCY_STOP ({reason}) -> dừng")
                break
            if paused:
                print(f"⏸️ [JOIN] {profile_id} PAUSED ({reason}) -> sleep")
                control_state.wait_if_paused(profile_id, sleep_seconds=0.5)

            # 3a) Join group (hoặc skip nếu đã join)
            url = _normalize_group_url(gid)
            joined_ok = False
            try:
                joined_ok = bool(fb.join_group(url))
            except Exception as e:
                if isinstance(e, RuntimeError) and ("EMERGENCY_STOP" in str(e) or "BROWSER_CLOSED" in str(e)):
                    raise
                print(f"⚠️ Lỗi join_group: {e}")
                joined_ok = False

            # 3b) Chỉ khi join thành công/đã là member -> lấy page_id và lưu groups.json
            if joined_ok and get_id_from_url and url:
                try:
                    fb.control_checkpoint("before_get_id_from_url_group")
                    res = get_id_from_url(url, profile_id)
                    if isinstance(res, dict) and res.get("url_type") == "group":
                        page_id = str(res.get("page_id") or "").strip()
                        if page_id:
                            ok = save_group_page_id(profile_id, page_id, url)
                            if ok:
                                print(f"💾 Đã lưu group: profile_id={profile_id} page_id={page_id}")
                            else:
                                print(f"⚠️ Không lưu được groups.json (profile_id={profile_id}, page_id={page_id})")
                except Exception as e:
                    if isinstance(e, RuntimeError) and ("EMERGENCY_STOP" in str(e) or "BROWSER_CLOSED" in str(e)):
                        raise
                    print(f"⚠️ Lỗi get_id_from_url khi join group: {e}")
            
            # Nghỉ ngẫu nhiên (trừ khi là group cuối)
            if idx < len(cleaned) - 1:
                sleep_time = random.uniform(10, 20) 
                print(f"💤 Nghỉ {sleep_time:.1f}s trước khi qua nhóm tiếp theo...")
                try:
                    smart_sleep(sleep_time, profile_id)
                except RuntimeError as e:
                    if "EMERGENCY_STOP" in str(e):
                        print(f"🛑 [JOIN] {profile_id} EMERGENCY_STOP trong sleep -> dừng")
                        raise
                    raise
            
    except Exception as e:
        print(f"❌ Lỗi kết nối/browser: {e}")
    finally:
        print("🏁 Hoàn tất danh sách.")
        # Đóng sạch tab/context playwright + stop NST profile (best-effort)
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

def run_batch_join(profile_id, json_file_path):
    # 1. Đọc file JSON
    # Chuyển đổi thành Path nếu là string
    json_file_path = Path(json_file_path) if not isinstance(json_file_path, Path) else json_file_path
    try:
        with json_file_path.open("r", encoding="utf-8") as f:
            group_ids = json.load(f)
        
        if not group_ids:
            print("⚠️ File JSON rỗng.")
            return
            
        print(f"📋 Tìm thấy {len(group_ids)} nhóm cần tham gia.")
        
    except Exception as e:
        print(f"❌ Lỗi đọc file JSON: {e}")
        return

    run_batch_join_from_list(profile_id, group_ids)

if __name__ == "__main__":
    # --- CẤU HÌNH ---
    MY_PROFILE_ID = "621e1f5d-0c42-481e-9ddd-7abaafce68ed" 
    JSON_PATH = get_config_dir() / "groups.json"
    
    run_batch_join(MY_PROFILE_ID, str(JSON_PATH))