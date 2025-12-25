from typing import Dict, Any
from pathlib import Path
import json

from core.browser import FBController


from core.paths import get_data_dir
STATUS_FILE = get_data_dir() / "account_status.json"


def check_account_status_brutal(fb: FBController) -> Dict[str, Any]:
    """
    CHECK BRUTAL MODE
    - Mục tiêu: không bỏ sót account lỗi
    - Chấp nhận false-positive nhẹ
    - Không tự dừng bot, chỉ trả về trạng thái để caller tự quyết định.
    """

    if not fb or not getattr(fb, "page", None):
        return {
            "status": "UNKNOWN",
            "banned": True,
            "reason": "no_browser",
            "message": "❌ Không có browser/page",
        }

    page = fb.page

    try:
        url = page.url.lower()
    except Exception:
        return {
            "status": "UNKNOWN",
            "banned": True,
            "reason": "cannot_get_url",
            "message": "❌ Không lấy được URL",
        }

    # =========================
    # 1. URL CHECK (CHẮC NHẤT)
    # =========================
    HARD_URL_KEYWORDS = [
        "checkpoint",
        "disabled",
        "account_recovery",
        "confirmidentity",
        "recover",
        "login.php",
        "login/",
        "two_step_verification",
        "security_checkup",
    ]

    for k in HARD_URL_KEYWORDS:
        if k in url:
            return {
                "status": "BANNED",
                "banned": True,
                "reason": "url_detected",
                "keyword": k,
                "url": url,
                "message": f"⛔ URL dính keyword khóa: {k}",
            }

    # =========================
    # 2. TITLE CHECK
    # =========================
    try:
        title = page.title().lower()
    except Exception:
        title = ""

    TITLE_KEYWORDS = [
        "log in or sign up",
        "đăng nhập",
        "your account has been disabled",
        "account disabled",
        "confirm your identity",
        "security check",
    ]

    for k in TITLE_KEYWORDS:
        if k in title:
            return {
                "status": "BANNED",
                "banned": True,
                "reason": "title_detected",
                "keyword": k,
                "title": title,
                "message": f"⛔ Title dính keyword khóa: {k}",
            }

    # =========================
    # 3. BODY TEXT SCAN (CÀN QUÉT)
    # =========================
    try:
        body_text = page.evaluate(
            """
            () => document.body ? document.body.innerText.toLowerCase() : ""
        """
        )
    except Exception:
        body_text = ""

    TEXT_KEYWORDS = [
        "your account has been disabled",
        "account disabled",
        "we’ve temporarily locked your account",
        "temporarily locked",
        "confirm your identity",
        "confirm it’s you",
        "tài khoản của bạn đã bị vô hiệu hóa",
        "tài khoản bị khóa",
        "tài khoản của bạn đã bị khóa",
        "xác minh danh tính",
        "bảo mật tài khoản",
        "security check",
        "phiên đăng nhập đã hết hạn",
    ]

    for k in TEXT_KEYWORDS:
        if k in body_text:
            return {
                "status": "BANNED",
                "banned": True,
                "reason": "text_detected",
                "keyword": k,
                "message": f"⛔ Text phát hiện trạng thái khóa: {k}",
            }

    # =========================
    # 4. FEED / MAIN CONTENT CHECK
    # =========================
    try:
        feed = page.query_selector(
            'div[role="feed"], div[aria-label*="Feed"], div[role="main"]'
        )
    except Exception:
        feed = None

    if "facebook.com" in url and not feed:
        return {
            "status": "BANNED",
            "banned": True,
            "reason": "no_feed",
            "url": url,
            "message": "⛔ Không tìm thấy feed / main content",
        }

    # =========================
    # 5. BASIC ACTION CHECK (SESSION DIE)
    # =========================
    try:
        page.evaluate("() => document.cookie")
    except Exception:
        return {
            "status": "BANNED",
            "banned": True,
            "reason": "session_invalid",
            "message": "⛔ Session/cookie không hợp lệ",
        }

    # =========================
    # OK
    # =========================
    return {
        "status": "OK",
        "banned": False,
        "url": url,
        "message": "✅ Account sống, chưa phát hiện dấu hiệu khóa",
    }


def save_account_status(profile_id: str, result: Dict[str, Any]) -> None:
    """
    Lưu trạng thái account vào file JSON để backend/frontend có thể đọc.
    Không raise lỗi để tránh ảnh hưởng luồng chính.
    """
    try:
        STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        data: Dict[str, Any] = {}
        if STATUS_FILE.exists():
            try:
                with STATUS_FILE.open("r", encoding="utf-8") as f:
                    data = json.load(f) or {}
            except Exception:
                data = {}

        data[str(profile_id)] = result

        with STATUS_FILE.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        # Không để bất kỳ lỗi ghi file nào làm vỡ luồng chính.
        pass





