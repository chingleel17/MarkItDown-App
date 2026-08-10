@echo off
chcp 65001 > nul
echo ========================================
echo  MarkItDown App - 首次環境設定
echo ========================================
echo.

REM 確認 uv
uv --version > nul 2>&1
if errorlevel 1 (
    echo [錯誤] 找不到 uv，請先安裝 uv
    echo 安裝說明：https://docs.astral.sh/uv/getting-started/installation/
    pause
    exit /b 1
)

set "UV_PROJECT_ENVIRONMENT=.venv312"

echo [1/2] 建立 Python 3.12 環境並同步套件...
uv sync --python 3.12
if errorlevel 1 (
    echo [錯誤] uv 環境建立或套件同步失敗
    pause
    exit /b 1
)

echo.
echo ========================================
echo  設定完成！
echo  使用環境：.venv312（Python 3.12）
echo  執行 run.bat 啟動程式（開發模式）
echo  執行 build.bat 打包為獨立 exe
echo ========================================
pause
