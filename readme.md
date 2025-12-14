# NST Tool - Hướng dẫn nhanh

## Backend (FastAPI + AppRunner)

1. Tạo và kích hoạt venv (Windows PowerShell):
   ```pwsh
   cd D:\FreeLand\nst_tool\backend
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```
2. Cài thư viện:
   ```pwsh
   python -m pip install -r requirements.txt
   ```
3. (Tuỳ chọn) Cài browser cho Playwright nếu chưa có:
   ```pwsh
   python -m playwright install chromium
   ```
4. Chạy API:

   ```pwsh
   uvicorn api:app --host 0.0.0.0 --port 8000 --reload
   ```

   - Endpoint chính:
     - `POST /run` → khởi động AppRunner (tự spawn process con)
     - `POST /stop` → dừng AppRunner
     - `GET /status` → kiểm tra đang chạy hay không
     - `GET /health` → ping sống

5. Biến môi trường (tùy chỉnh trong `.env`):
   - `TARGET_URL` (mặc định `https://facebook.com`)
   - `PROFILE_IDS` danh sách id, phân tách dấu phẩy.

## Frontend (tĩnh)

1. Mở file `D:\FreeLand\nst_tool\frontend\index.html` trên trình duyệt (có thể double-click hoặc serve tĩnh).
2. Nút “Chạy backend (FastAPI)”/“Bắt đầu quét” sẽ gọi API ở `http://localhost:8000`.
3. Nút “Dừng quét” gửi lệnh dừng `/stop`.

## Lưu ý

- Khi chạy backend từ IDE/terminal khác, vẫn cần kích hoạt đúng venv: `.\\venv\\Scripts\\Activate.ps1`.
- Nếu đổi port hoặc host, cập nhật `API_BASE` trong `frontend/script.js` cho khớp.
