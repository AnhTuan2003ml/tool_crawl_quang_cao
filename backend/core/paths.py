# backend/core/paths.py
import sys
import os
from pathlib import Path

def get_base_dir() -> Path:
    """
    Trả về thư mục gốc:
    - Nếu chạy .exe: là thư mục chứa file .exe (để load config/data bên ngoài)
    - Nếu chạy code: là thư mục backend
    """
    if getattr(sys, 'frozen', False):
        # Đang chạy từ file .exe -> Lấy thư mục chứa file exe
        return Path(sys.executable).parent
    else:
        # Đang chạy code python -> Lấy thư mục chứa file hiện tại (core) rồi ra ngoài 2 cấp
        return Path(__file__).resolve().parent.parent

def get_config_dir() -> Path:
    """Folder config nằm cùng cấp file exe"""
    return get_base_dir() / "config"

def get_data_dir() -> Path:
    """Folder data nằm cùng cấp file exe"""
    return get_base_dir() / "data"

def get_frontend_dir() -> Path:
    """Folder frontend nằm cùng cấp file exe"""
    base = get_base_dir()
    if getattr(sys, 'frozen', False):
        return base / "frontend"
    else:
        # Nếu chạy code thì frontend nằm ngang hàng với backend
        return base.parent / "frontend"

def get_settings_path() -> Path:
    return get_config_dir() / "settings.json"