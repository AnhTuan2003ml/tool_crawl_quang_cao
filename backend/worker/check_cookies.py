import requests


def _import_get_cookies():
    try:
        from get_payload import get_cookies_by_profile_id  # type: ignore
        return get_cookies_by_profile_id
    except Exception:
        try:
            from backend.worker.get_payload import get_cookies_by_profile_id  # type: ignore
            return get_cookies_by_profile_id
        except Exception:
            from worker.get_payload import get_cookies_by_profile_id  # type: ignore
            return get_cookies_by_profile_id


get_cookies_by_profile_id = _import_get_cookies()


def check_cookie_by_title(profile_id: str) -> dict:
    """
    Tải facebook.com với cookies và kiểm tra title đăng nhập.
    Title "Facebook – log in or sign up" => cookies die.
    """
    cookie = get_cookies_by_profile_id(profile_id)
    if not cookie:
        return {"status": "dead", "message": "❌ Không lấy được cookie"}

    url = "https://www.facebook.com/"
    headers = {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "accept-encoding": "gzip, deflate",
        "accept-language": "en,vi;q=0.9,en-US;q=0.8",
        "referer": "https://www.facebook.com/",
        "sec-ch-ua": '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "upgrade-insecure-requests": "1",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
        "cookie": cookie,
    }

    try:
        resp = requests.get(url, headers=headers, timeout=20, allow_redirects=True)
        login_title = '<title id="pageTitle">Facebook – log in or sign up</title>'
        html_lower = resp.text.lower()

        if login_title.lower() in html_lower:
            return {
                "status": "dead",
                "message": "❌ Phát hiện title login: cookies die",
                "status_code": resp.status_code,
                "final_url": resp.url,
            }

        # Không thấy title login => coi là cookies còn sống (dù status khác 200)
        return {
            "status": "alive",
            "message": "✅ Không thấy title login, coi cookies còn sống",
            "status_code": resp.status_code,
            "final_url": resp.url,
        }
    except Exception as e:
        return {"status": "error", "message": f"❌ Lỗi: {e}"}


if __name__ == "__main__":
    profile_id = "031ca13d-e8fa-400c-a603-df57a2806788"
    result = check_cookie_by_title(profile_id)
    print(result["message"])

