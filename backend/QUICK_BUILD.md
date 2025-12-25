# Hướng dẫn Build Nhanh

## Bước 1: Kích hoạt venv

```powershell
cd backend
.\venv\Scripts\Activate.ps1
```

## Bước 2: Cài PyInstaller (nếu chưa có)

```powershell
python -m pip install pyinstaller
```

## Bước 3: Build

```powershell
.\build.ps1
```

Hoặc:
```cmd
build.bat
```

## Bước 4: Chạy .exe

File `.exe` nằm tại: `dist\ToolFacebookAds\ToolFacebookAds.exe`

Double-click hoặc chạy từ command line:
```powershell
.\dist\ToolFacebookAds\ToolFacebookAds.exe
```

**Lưu ý:** 
- Tất cả file (config/, frontend/, data/) đều nằm cùng thư mục với .exe
- **Trình duyệt sẽ tự động mở** file `frontend/index.html` sau khi server khởi động (khoảng 2 giây)
- Nếu không tự động mở, bạn có thể mở thủ công file `frontend/index.html` bằng trình duyệt

---

**Lưu ý:** Xem file `BUILD_GUIDE.md` ở thư mục gốc để biết chi tiết và xử lý lỗi.

