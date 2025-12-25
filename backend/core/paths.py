"""
Utility để xác định đường dẫn đúng khi chạy từ .exe hoặc từ script Python
"""
import sys
from pathlib import Path


def get_base_dir() -> Path:
    """
    Trả về thư mục gốc của project hoặc thư mục chứa .exe
    
    - Khi chạy từ .exe: trả về thư mục chứa .exe
    - Khi chạy từ script: trả về thư mục backend
    """
    if getattr(sys, 'frozen', False):
        # Chạy từ .exe - trả về thư mục chứa .exe
        return Path(sys.executable).parent
    else:
        # Chạy từ script - trả về thư mục backend (nơi chứa core/)
        return Path(__file__).resolve().parent.parent


def get_config_dir() -> Path:
    """Trả về thư mục config (cùng cấp với .exe hoặc backend/config)"""
    return get_base_dir() / "config"


def get_data_dir() -> Path:
    """Trả về thư mục data (cùng cấp với .exe hoặc backend/data)"""
    return get_base_dir() / "data"


def get_frontend_dir() -> Path:
    """Trả về thư mục frontend (cùng cấp với .exe hoặc ../frontend)"""
    base = get_base_dir()
    if getattr(sys, 'frozen', False):
        # Khi chạy từ .exe, frontend cùng cấp với .exe
        return base / "frontend"
    else:
        # Khi chạy từ script, frontend ở thư mục gốc project
        return base.parent / "frontend"


def get_settings_path() -> Path:
    """Trả về đường dẫn đến settings.json"""
    return get_config_dir() / "settings.json"

