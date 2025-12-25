# backend/run_api.py
import uvicorn
import sys
import os
import webbrowser
import threading
import time
from multiprocessing import freeze_support
from pathlib import Path

# --- CẤU HÌNH ĐƯỜNG DẪN QUAN TRỌNG ---
# Lấy đường dẫn thư mục chứa file chạy hiện tại (backend)
base_dir = os.path.dirname(os.path.abspath(__file__))

# 1. Thêm 'backend' vào sys.path để gọi được 'app', 'core'
if base_dir not in sys.path:
    sys.path.append(base_dir)

# 2. Thêm 'backend/worker' vào sys.path để gọi được 'single_get_reactions', 'get_id', ...
worker_dir = os.path.join(base_dir, "worker")
if worker_dir not in sys.path:
    sys.path.append(worker_dir)
# --------------------------------------

# === ÉP PYINSTALLER NHẬN DIỆN MODULE ===
try:
    import core.paths
    import core.settings
    # Import app chính
    from app.api import app 
    
    # Import thủ công các file trong worker để PyInstaller không bỏ sót
    # (Dùng try-except lồng để tránh crash nếu file chưa chạy tới)
    try:
        import worker.single_get_reactions
        import worker.single_get_comment
        import worker.get_all_info
        import worker.get_id
    except ImportError:
        pass
        
except ImportError as e:
    print(f"CRITICAL ERROR: Thiếu module! Chi tiết: {e}")
    print("Sếp kiểm tra lại xem đã có file __init__.py trong thư mục 'worker' chưa nhé!")
    input("An Enter de thoat...")
    sys.exit(1)
# =======================================

def open_browser():
    """Đợi server chạy rồi mở trình duyệt"""
    time.sleep(2) 
    try:
        from core.paths import get_frontend_dir
        frontend_path = get_frontend_dir() / "index.html"
        
        if frontend_path.exists():
            print(f"\n🌐 Đang mở giao diện: {frontend_path}")
            webbrowser.open(frontend_path.as_uri())
        else:
            print(f"\n⚠️ Không tìm thấy frontend tại: {frontend_path}")
    except Exception as e:
        print(f"Lỗi mở trình duyệt: {e}")

if __name__ == "__main__":
    freeze_support()
    
    threading.Thread(target=open_browser, daemon=True).start()
    
    print("=" * 60)
    print("🚀 Đang khởi động Tool Crawl...")
    print("=" * 60)
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=False 
    )