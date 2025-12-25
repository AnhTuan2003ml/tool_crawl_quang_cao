# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file để build thành .exe

import sys
import os
from pathlib import Path

block_cipher = None

# Đường dẫn đến thư mục backend (nơi chứa file .spec này)
# PyInstaller tự động inject SPEC variable khi build
# Nếu chưa có, dùng đường dẫn tương đối từ thư mục hiện tại
try:
    spec_dir = os.path.dirname(os.path.abspath(SPEC))
except NameError:
    # Fallback: giả sử chạy từ thư mục backend
    spec_dir = os.getcwd()

backend_path = Path(spec_dir).resolve()
parent_path = backend_path.parent  # Thư mục gốc của project (tool_crawl_quang_cao)

# Thu thập tất cả các file Python
a = Analysis(
    ['run_api.py'],
    pathex=[str(backend_path)],
    binaries=[],
    datas=[
        # Bao gồm frontend folder (từ thư mục gốc)
        (str(parent_path / 'frontend'), 'frontend'),
        # Bao gồm config folder
        (str(backend_path / 'config'), 'config'),
        # Bao gồm data folder structure
        (str(backend_path / 'data'), 'data'),
    ],
    hiddenimports=[
        'app.api',
        'core.runner',
        'core.browser',
        'core.control',
        'core.join_groups',
        'core.nst',
        'core.scraper',
        'core.search_worker',
        'core.settings',
        'core.utils',
        'core.account_status',
        'worker.get_all_info',
        'worker.get_id',
        'worker.get_payload',
        'worker.get_post_from_page',
        'worker.single_get_comment',
        'worker.single_get_reactions',
        'worker.check_cookies',
        'uvicorn',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.logging',
        'fastapi',
        'pydantic',
        'starlette',
        'multipart',
        'playwright',
        'selenium',
        'requests',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Sử dụng onedir mode để các file config, frontend, data nằm bên cạnh .exe
# (dễ chỉnh sửa và quản lý hơn - người dùng có thể chỉnh sửa config, xem frontend)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,  # Không đóng gói binaries vào exe, để ở thư mục riêng
    name='ToolFacebookAds',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Hiển thị console để xem logs
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Có thể thêm icon file nếu muốn
)

# COLLECT để gom tất cả vào một thư mục
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ToolFacebookAds',
)

