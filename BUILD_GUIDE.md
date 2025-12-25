# Hướng dẫn Build Project thành file .exe

## Yêu cầu

1. **Python** đã được cài đặt (khuyến nghị Python 3.10+)
2. **Virtual environment (venv)** đã được tạo và kích hoạt
3. Tất cả các package đã được cài đặt trong venv (từ `requirements.txt`)

## Các bước Build

### Bước 1: Kích hoạt Virtual Environment

Mở PowerShell hoặc Command Prompt và di chuyển đến thư mục `backend`:

```powershell
cd D:\FreeLand\tool_crawl_quang_cao\backend
```

Kích hoạt venv:

**PowerShell:**

```powershell
.\venv\Scripts\Activate.ps1
```

**Command Prompt (cmd):**

```cmd
.\venv\Scripts\activate.bat
```

### Bước 2: Cài đặt PyInstaller (nếu chưa có)

Kiểm tra PyInstaller đã được cài chưa:

```powershell
python -c "import PyInstaller"
```

Nếu chưa có, cài đặt:

```powershell
python -m pip install pyinstaller
```

**Lưu ý:** Nếu bạn đã cài các package trong venv từ `requirements.txt`, có thể PyInstaller đã được cài rồi. Hãy thử build trước.

### Bước 3: Build file .exe

Có 2 cách để build:

#### Cách 1: Sử dụng script tự động (Khuyến nghị)

**PowerShell:**

```powershell
.\build.ps1
```

**Command Prompt:**

```cmd
build.bat
```

#### Cách 2: Chạy PyInstaller trực tiếp

```powershell
python -m PyInstaller build_exe.spec --clean
```

### Bước 4: Kiểm tra kết quả

Sau khi build xong, thư mục build sẽ nằm tại:

```
backend\dist\ToolFacebookAds\
```

Trong thư mục này sẽ có:

- `ToolFacebookAds.exe` - File thực thi chính
- `config/` - Thư mục cấu hình (settings.json, payload.txt, ...)
- `frontend/` - Thư mục frontend (index.html, script.js, style.css, icon/, ...)
- `data/` - Thư mục dữ liệu (post_ids/, results/, ...)
- Các file DLL và thư viện khác cần thiết

## Chạy file .exe

### Cách 1: Double-click

Double-click vào file `ToolFacebookAds.exe` trong thư mục `dist\ToolFacebookAds\`

### Cách 2: Chạy từ Command Line

```powershell
cd dist\ToolFacebookAds
.\ToolFacebookAds.exe
```

### Cách 3: Chạy với đường dẫn đầy đủ

```powershell
.\backend\dist\ToolFacebookAds\ToolFacebookAds.exe
```

## Lưu ý quan trọng

### 1. Cấu trúc thư mục khi chạy .exe

Sau khi build, trong thư mục `dist\ToolFacebookAds\` sẽ có:

- `ToolFacebookAds.exe` - File thực thi chính
- `config/` - Thư mục cấu hình (settings.json, payload.txt, groups.json, cloneM.txt)
- `frontend/` - Thư mục frontend (index.html, script.js, style.css, icon/, data.json)
- `data/` - Thư mục dữ liệu (post_ids/, results/, account_status.json, runtime_control.json)
- Các file DLL và thư viện cần thiết

**Tất cả các file này đều nằm cùng thư mục với .exe, dễ dàng chỉnh sửa và quản lý.**

**Lưu ý:**

- Bạn có thể chỉnh sửa `config/settings.json` trực tiếp để cấu hình ứng dụng
- Frontend có thể mở file `frontend/index.html` bằng trình duyệt
- Dữ liệu được lưu trong thư mục `data/`

### 2. Playwright Browser

Nếu ứng dụng sử dụng Playwright, bạn cần đảm bảo browser đã được cài đặt. File .exe có thể cần cài lại Playwright browsers sau khi build:

```powershell
# Chạy từ thư mục chứa .exe
python -m playwright install chromium
```

Tuy nhiên, nếu browser không được đóng gói, bạn có thể cần cài đặt Playwright riêng trên máy chạy .exe.

### 3. Port 8000

Ứng dụng sẽ chạy API server trên port 8000. Đảm bảo port này không bị chiếm dụng bởi ứng dụng khác.

### 4. Frontend

Sau khi chạy .exe:

- **Trình duyệt sẽ tự động mở** file `frontend/index.html` sau khoảng 2 giây
- Nếu không tự động mở, bạn có thể mở thủ công file `frontend/index.html` bằng trình duyệt
- API server chạy tại: `http://localhost:8000`

### 5. Logs và Console

File .exe được build với `console=True`, nghĩa là sẽ hiển thị cửa sổ console để xem logs. Điều này giúp debug dễ dàng hơn.

## Xử lý lỗi

### Lỗi: "Module not found"

Nếu gặp lỗi thiếu module, bạn có thể cần:

1. Thêm module vào `hiddenimports` trong file `build_exe.spec`
2. Build lại

### Lỗi: "File not found" hoặc đường dẫn sai

Kiểm tra lại cấu trúc thư mục trong `build_exe.spec` ở phần `datas`. Đảm bảo các đường dẫn đúng.

### Lỗi: File .exe quá lớn

File .exe có thể khá lớn (50-200MB) vì đã đóng gói tất cả dependencies. Đây là bình thường.

### Build lâu

Quá trình build có thể mất 2-5 phút tùy vào máy tính và số lượng dependencies.

## Tùy chỉnh Build

Nếu cần tùy chỉnh, chỉnh sửa file `backend/build_exe.spec`:

- **Thay đổi tên file .exe:** Sửa `name='ToolFacebookAds'`
- **Thêm/bớt file dữ liệu:** Sửa phần `datas`
- **Thêm/bớt module:** Sửa phần `hiddenimports`
- **Ẩn console:** Đổi `console=True` thành `console=False`
- **Thêm icon:** Thêm `icon='path/to/icon.ico'` vào phần `EXE`

## Phân phối file .exe

Khi phân phối file .exe cho người khác:

**Cần đóng gói toàn bộ thư mục `dist\ToolFacebookAds\`** bao gồm:

- `ToolFacebookAds.exe` (và tất cả file .dll, .pyd đi kèm)
- `config/` (thư mục và tất cả file trong đó)
- `frontend/` (thư mục và tất cả file trong đó)
- `data/` (thư mục và cấu trúc thư mục con)

Bạn có thể:

1. Zip toàn bộ thư mục `dist\ToolFacebookAds\` và gửi cho người khác
2. Hoặc copy toàn bộ nội dung thư mục `dist\ToolFacebookAds\` vào một thư mục khác

**Người nhận chỉ cần:**

1. Giải nén vào một thư mục bất kỳ
2. Chạy `ToolFacebookAds.exe` từ trong thư mục đó
3. Mở `frontend/index.html` bằng trình duyệt để sử dụng giao diện

**Lưu ý:** Đảm bảo giữ nguyên cấu trúc thư mục (config/, frontend/, data/ phải cùng cấp với .exe).

---

**Chúc bạn build thành công! 🎉**
