Clear-Host

Write-Host '========================================' -ForegroundColor Cyan
Write-Host '   BUILD TOOL FACEBOOK ADS - .EXE' -ForegroundColor Cyan
Write-Host '========================================' -ForegroundColor Cyan
Write-Host ''

# -------------------------------------------------
# CHECK VENV
# -------------------------------------------------
try {
    $venvActive = $env:VIRTUAL_ENV -ne $null -or (Get-Command python).Source -like '*venv*'
    if (-not $venvActive) {
        Write-Host '[ERROR] Venv chua duoc kich hoat!' -ForegroundColor Red
        Write-Host 'Hay chay: .\venv\Scripts\Activate.ps1' -ForegroundColor Yellow
        Read-Host 'Nhan Enter de thoat'
        exit 1
    }
} catch {
    Write-Host '[WARNING] Khong the kiem tra venv, tiep tuc...' -ForegroundColor Yellow
}

# -------------------------------------------------
# CHECK PYINSTALLER
# -------------------------------------------------
Write-Host '[1/6] Kiem tra PyInstaller...' -ForegroundColor Green
python -c 'import PyInstaller' 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host '[WARNING] Dang cai PyInstaller...' -ForegroundColor Yellow
    python -m pip install pyinstaller
    if ($LASTEXITCODE -ne 0) {
        Write-Host '[ERROR] Cai PyInstaller that bai!' -ForegroundColor Red
        Read-Host 'Nhan Enter de thoat'
        exit 1
    }
}

# -------------------------------------------------
# CLEAN BUILD
# -------------------------------------------------
Write-Host '[2/6] Xoa build cu...' -ForegroundColor Green
if (Test-Path 'build') { Remove-Item -Recurse -Force 'build' }
if (Test-Path 'dist')  { Remove-Item -Recurse -Force 'dist' }

# -------------------------------------------------
# BUILD EXE
# -------------------------------------------------
Write-Host '[3/6] Dang build exe...' -ForegroundColor Green
python -m PyInstaller build_exe.spec --clean
if ($LASTEXITCODE -ne 0) {
    Write-Host '[ERROR] Build that bai!' -ForegroundColor Red
    Read-Host 'Nhan Enter de thoat'
    exit 1
}

# -------------------------------------------------
# CHECK EXE
# -------------------------------------------------
Write-Host '[4/6] Kiem tra exe...' -ForegroundColor Green

$exe1 = 'dist\ToolFacebookAds\ToolFacebookAds.exe'
$exe2 = 'dist\ToolFacebookAds.exe'

if (Test-Path $exe1) {
    $exePath  = $exe1
    $distPath = 'dist\ToolFacebookAds'
}
elseif (Test-Path $exe2) {
    $exePath  = $exe2
    $distPath = 'dist'
}
else {
    Write-Host '[ERROR] Khong tim thay file exe!' -ForegroundColor Red
    Read-Host 'Nhan Enter de thoat'
    exit 1
}

Write-Host ''
Write-Host '========== BUILD THANH CONG ==========' -ForegroundColor Green
Write-Host ('Exe: ' + $exePath) -ForegroundColor Cyan
Write-Host ''

# -------------------------------------------------
# COPY RESOURCE
# -------------------------------------------------
Write-Host '[5/6] Copy config / frontend / data...' -ForegroundColor Green

# config
if (-not (Test-Path (Join-Path $distPath 'config'))) {
    if (Test-Path 'config') {
        Copy-Item -Recurse -Force 'config' (Join-Path $distPath 'config')
        Write-Host '  ✓ config/' -ForegroundColor Green
    }
}

# frontend
$frontendSrc = '..\frontend'
if (-not (Test-Path (Join-Path $distPath 'frontend'))) {
    if (Test-Path $frontendSrc) {
        Copy-Item -Recurse -Force $frontendSrc (Join-Path $distPath 'frontend')
        Write-Host '  ✓ frontend/' -ForegroundColor Green
    }
}

# data
$dataPath = Join-Path $distPath 'data'
$postIds  = Join-Path $dataPath 'post_ids'
$results  = Join-Path $dataPath 'results'

if (-not (Test-Path $dataPath)) {
    New-Item -ItemType Directory -Force -Path $postIds | Out-Null
    New-Item -ItemType Directory -Force -Path $results | Out-Null
    Write-Host '  ✓ data/' -ForegroundColor Green
}

# -------------------------------------------------
# FINAL
# -------------------------------------------------
Write-Host '[6/6] Thong bao' -ForegroundColor Green
Write-Host 'Config  : dist\ToolFacebookAds\config\settings.json' -ForegroundColor Cyan
Write-Host 'Frontend: dist\ToolFacebookAds\frontend\index.html' -ForegroundColor Cyan
Write-Host 'Data    : dist\ToolFacebookAds\data' -ForegroundColor Cyan
Write-Host ''

$open = Read-Host 'Mo thu muc dist? (Y/N)'
if ($open -match '^[Yy]$') {
    explorer $distPath
}
