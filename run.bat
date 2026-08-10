@echo off
chcp 65001 > nul

uv --version > nul 2>&1
if errorlevel 1 (
    echo [錯誤] 找不到 uv，請先安裝 uv
    pause
    exit /b 1
)

set "UV_PROJECT_ENVIRONMENT=.venv312"

if not exist ".venv312\Scripts\python.exe" (
    echo [提示] 尚未設定環境，正在執行首次安裝...
    call setup.bat
    if errorlevel 1 exit /b 1
)

uv run --locked --python 3.12 python app.py
