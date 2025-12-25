"""
Entry point để chạy FastAPI server
Script này sẽ được build thành .exe
"""
import uvicorn
import sys
import os
import webbrowser
import threading
import time
from pathlib import Path

# Đảm bảo đường dẫn đúng khi chạy từ .exe
if getattr(sys, 'frozen', False):
    # Chạy từ .exe (PyInstaller)
    # sys.executable là đường dẫn đến .exe
    exe_dir = Path(sys.executable).parent
    base_path = Path(sys._MEIPASS)  # Thư mục tạm khi giải nén
else:
    # Chạy từ Python script
    exe_dir = Path(__file__).parent
    base_path = Path(__file__).parent

# Thêm base_path vào sys.path để import được các module
if str(base_path) not in sys.path:
    sys.path.insert(0, str(base_path))

def open_browser():
    """Đợi server khởi động rồi mở trình duyệt"""
    time.sleep(2)  # Đợi server khởi động
    
    # Tìm file frontend/index.html - luôn ở cùng cấp với .exe
    try:
        from core.paths import get_frontend_dir
        frontend_path = get_frontend_dir() / "index.html"
    except ImportError:
        # Fallback nếu không import được
        frontend_path = exe_dir / "frontend" / "index.html"
    
    if frontend_path.exists():
        # Mở file HTML trực tiếp
        file_url = frontend_path.as_uri()
        print(f"\n🌐 Đang mở trình duyệt: {file_url}")
        webbrowser.open(file_url)
    else:
        print(f"\n⚠️ Không tìm thấy file frontend/index.html tại: {frontend_path}")
        print(f"   Hãy đảm bảo thư mục frontend/ nằm cùng cấp với file .exe")

if __name__ == "__main__":
    # Tự động mở trình duyệt trong thread riêng
    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()
    
    # Chạy uvicorn server
    print("=" * 60)
    print("🚀 Đang khởi động API Server...")
    print("=" * 60)
    uvicorn.run(
        "app.api:app",
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )

