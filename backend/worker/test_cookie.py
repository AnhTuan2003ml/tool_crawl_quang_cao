import requests
import json
from get_payload import get_cookies_by_profile_id

def test_cookie_validity(profile_id):
    """
    Test xem cookie co hop le khong bang cach gui GET request toi Facebook
    """
    # Lay cookie tu profile_id
    cookie_str = get_cookies_by_profile_id(profile_id)
    if not cookie_str:
        print(f"Khong tim thay cookie cho profile_id: {profile_id}")
        return False

    print(f"Cookie string: {cookie_str[:100]}...")

    # Parse cookie thanh dict
    cookie_dict = {}
    for part in cookie_str.split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            cookie_dict[k.strip()] = v.strip()

    # In ra cac truong quan trong
    print("\nCookie fields:")
    important_fields = ["c_user", "xs", "fr", "sb", "datr"]
    for field in important_fields:
        value = cookie_dict.get(field, "MISSING")
        print(f"  {field}: {value}")

    # Headers giong browser
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en,vi;q=0.9,en-US;q=0.8",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "sec-ch-ua": '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "none",
        "sec-fetch-user": "?1",
        "upgrade-insecure-requests": "1"
    }

    try:
        # Test 1: GET toi trang chu Facebook
        print("\nTest 1: GET https://www.facebook.com")
        response = requests.get("https://www.facebook.com", cookies=cookie_dict, headers=headers, allow_redirects=True, timeout=15)

        print(f"   Status Code: {response.status_code}")
        print(f"   Final URL: {response.url}")

        # Kiem tra redirect toi login
        if "login" in response.url.lower() or "checkpoint" in response.url.lower():
            print("   FAIL: Redirected to login/checkpoint")
            return False

        # Kiem tra noi dung co dau hieu login form
        content = response.text.lower()
        if 'id="login_form"' in content or 'name="email"' in content or 'action="/login/' in content:
            print("   FAIL: Login form detected in response")
            return False

        # Kiem tra co fb_dtsg trong response (dau hieu logged in)
        if 'fb_dtsg' in content or 'name="fb_dtsg"' in content:
            print("   SUCCESS: fb_dtsg found in response - likely logged in")
            return True
        else:
            print("   WARNING: No fb_dtsg found, might not be fully logged in")

        # Test 2: GET toi URL post cu the
        print("\nTest 2: GET https://www.facebook.com/share/p/1BsAYutMg8/")
        response2 = requests.get("https://www.facebook.com/share/p/1BsAYutMg8/", cookies=cookie_dict, headers=headers, allow_redirects=True, timeout=15)

        print(f"   Status Code: {response2.status_code}")
        print(f"   Final URL: {response2.url}")

        if "login" in response2.url.lower() or "checkpoint" in response2.url.lower():
            print("   FAIL: Redirected to login/checkpoint")
            return False
        else:
            print("   SUCCESS: No redirect to login")
            return True

    except Exception as e:
        print(f"ERROR: {e}")
        return False

if __name__ == "__main__":
    profile_id = "621e1f5d-0c42-481e-9ddd-7abaafce68ed"
    print(f"Testing cookie validity for profile_id: {profile_id}")
    is_valid = test_cookie_validity(profile_id)
    print(f"\nFinal result: {'VALID' if is_valid else 'INVALID'}")
