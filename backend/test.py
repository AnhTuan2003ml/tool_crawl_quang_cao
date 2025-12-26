import requests
import json

# 1. Điền API KEY thật của Sếp vào đây (lấy từ settings.json)
API_KEY = "YOUR_NST_API_KEY_HERE" 

# 2. ID profile đang bị lỗi
PROFILE_ID = "b77da63d-af55-43c2-ab7f-364250b20e30"

BASE_URL = "http://127.0.0.1:8848/api/v2"

def debug_nst():
    print("--- BẮT ĐẦU KIỂM TRA NST ---")
    
    # TEST 1: Kiểm tra kết nối và list profile đang chạy
    try:
        r = requests.get(f"{BASE_URL}/browsers", headers={"x-api-key": API_KEY}, timeout=5)
        print(f"✅ Kết nối NST OK. Status: {r.status_code}")
        print(f"   Response: {r.text[:200]}...") # In một phần response
    except Exception as e:
        print(f"❌ Không kết nối được NST (127.0.0.1:8848). App đã bật chưa? Lỗi: {e}")
        return

    # TEST 2: Thử start profile bằng cấu hình tối giản nhất (POST Array)
    print(f"\n--- Đang thử Start Profile {PROFILE_ID} (Cách Array) ---")
    url_start = f"{BASE_URL}/browsers"
    payload_list = [PROFILE_ID]
    
    try:
        r = requests.post(url_start, headers={"x-api-key": API_KEY}, json=payload_list)
        print(f"📡 Status Code: {r.status_code}")
        print(f"📄 Full Response: {r.text}")
        
        if r.status_code == 400:
            print("\n❌ KẾT LUẬN: Lỗi 400.")
            print("👉 Khả năng cao nhất: Profile ID này KHÔNG TỒN TẠI trong tài khoản NST đang đăng nhập.")
            print("👉 Hãy mở App NST lên, search ID này xem có thấy không?")
        elif r.status_code == 200:
            print("\n✅ Start thành công! Vấn đề nằm ở code cũ truyền sai tham số.")
            
    except Exception as e:
        print(f"❌ Lỗi request: {e}")

if __name__ == "__main__":
    debug_nst()