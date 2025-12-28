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
xcopy "config" "dist\ToolFacebook\config\" /E /I /Y

:: Copy frontend (HTML/CSS/JS) - lấy từ thư mục cha
xcopy "..\frontend" "dist\ToolFacebook\frontend\" /E /I /Y

:: Copy toàn bộ data (không tạo mới, copy hết)
if exist "data" (
    xcopy "data" "dist\ToolFacebook\data\" /E /I /Y
) else (
    echo Warning: Thu muc data khong ton tai, tao thu muc rong...
    if not exist "dist\ToolFacebook\data" mkdir "dist\ToolFacebook\data"
)

echo.
echo ==========================================
echo BUILD THANH CONG!
echo File exe nam tai: backend\dist\ToolFacebook\ToolFacebook.exe
echo ==========================================
pause