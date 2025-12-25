@echo off
REM Script build .exe cho Windows
REM Chạy script này từ thư mục backend

echo ========================================
echo    BUILD TOOL FACEBOOK ADS - .EXE
echo ========================================
echo.

REM Kiểm tra venv đã được kích hoạt chưa
python -c "import sys; sys.exit(0 if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix) else 1)" 2>nul
if errorlevel 1 (
    echo [ERROR] Venv chua duoc kich hoat!
    echo Vui long chay: .\venv\Scripts\Activate.ps1 hoac .\venv\Scripts\activate.bat
    pause
    exit /b 1
)

echo [1/4] Kiem tra PyInstaller...
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo [ERROR] PyInstaller chua duoc cai dat!
    echo Dang cai dat PyInstaller...
    python -m pip install pyinstaller
    if errorlevel 1 (
        echo [ERROR] Khong the cai dat PyInstaller!
        pause
        exit /b 1
    )
)

echo [2/4] Xoa cac file build cu (neu co)...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo [3/4] Dang build .exe (co the mat 2-5 phut)...
python -m PyInstaller build_exe.spec --clean

if errorlevel 1 (
    echo [ERROR] Build that bai!
    pause
    exit /b 1
)

echo [4/5] Kiem tra file .exe...
if exist "dist\ToolFacebookAds\ToolFacebookAds.exe" (
    echo.
    echo ========================================
    echo    BUILD THANH CONG!
    echo ========================================
    echo.
    echo Thu muc build: dist\ToolFacebookAds\
    echo.
    echo File .exe: dist\ToolFacebookAds\ToolFacebookAds.exe
    echo Cac thu muc: frontend/, config/, data/
    echo.
    echo De chay: dist\ToolFacebookAds\ToolFacebookAds.exe
    echo.
) else if exist "dist\ToolFacebookAds.exe" (
    echo.
    echo ========================================
    echo    BUILD THANH CONG!
    echo ========================================
    echo.
    echo File .exe: dist\ToolFacebookAds.exe
    echo.
    echo De chay: dist\ToolFacebookAds.exe
    echo.
) else (
    echo [ERROR] Khong tim thay file .exe trong thu muc dist!
    pause
    exit /b 1
)

echo [5/6] Copy config va frontend tu source (lan dau tien)...
set "distPath=dist\ToolFacebookAds"

REM Copy config neu chua co
if not exist "%distPath%\config" (
    if exist "config" (
        xcopy /E /I /Y "config" "%distPath%\config"
        echo   [OK] Da copy: config/ tu source
    )
)

REM Copy frontend neu chua co
if not exist "%distPath%\frontend" (
    set "frontendSource=..\frontend"
    if exist "%frontendSource%" (
        xcopy /E /I /Y "%frontendSource%" "%distPath%\frontend"
        echo   [OK] Da copy: frontend/ tu source
    )
)

REM Tao thu muc data neu chua co
if not exist "%distPath%\data" (
    mkdir "%distPath%\data"
    mkdir "%distPath%\data\post_ids"
    mkdir "%distPath%\data\results"
    echo   [OK] Da tao: data/ (se duoc ghi khi chay)
)

echo [6/6] Thong bao quan trong...
echo.
echo Luu y: Ung dung se doc/ghi truc tiep tu cung cap voi .exe
echo   - Doc config tu: dist\ToolFacebookAds\config\settings.json
echo   - Doc frontend tu: dist\ToolFacebookAds\frontend\index.html
echo   - Ghi data vao: dist\ToolFacebookAds\data\
echo.
echo Ban co the chinh sua config/ truc tiep de cau hinh ung dung!

pause

