@echo off
chcp 65001 > nul

if not exist ".venv\Scripts\python.exe" (
    echo [提示] 尚未設定環境，正在執行首次安裝...
    call setup.bat
)

.venv\Scripts\python app.py
