@echo off
echo ==========================================
echo DANG BUILD TOOL RA EXE...
echo ==========================================

:: 1. Dọn dẹp bản build cũ
rmdir /s /q build
rmdir /s /q dist

:: 2. Chạy PyInstaller
pyinstaller build_exe.spec --noconfirm

:: 3. Copy các thư mục cần thiết ra ngoài để Sếp dễ sửa
echo.
echo Dang copy du lieu (Config, Data, Frontend)...

:: Copy config (chứa settings.json, groups.json...)
xcopy "config" "dist\ToolCrawl\config\" /E /I /Y

:: Copy frontend (HTML/CSS/JS) - lấy từ thư mục cha
xcopy "..\frontend" "dist\ToolCrawl\frontend\" /E /I /Y

:: Tạo thư mục data rỗng nếu chưa có
if not exist "dist\ToolCrawl\data" mkdir "dist\ToolCrawl\data"

echo.
echo ==========================================
echo BUILD THANH CONG!
echo File exe nam tai: backend\dist\ToolCrawl\ToolCrawl.exe
echo ==========================================
pause