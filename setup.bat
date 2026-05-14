@echo off
chcp 65001 > nul
echo ========================================
echo  MarkItDown App - 首次環境設定
echo ========================================
echo.

REM 確認 Python 版本
python --version > nul 2>&1
if errorlevel 1 (
    echo [錯誤] 找不到 Python，請先安裝 Python 3.10 以上版本
    echo 下載頁面：https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/3] 建立虛擬環境...
python -m venv .venv
if errorlevel 1 (
    echo [錯誤] 建立虛擬環境失敗
    pause
    exit /b 1
)

echo [2/3] 升級 pip...
.venv\Scripts\python -m pip install --upgrade pip --quiet

echo [3/3] 安裝套件（首次較慢，請耐心等候）...
.venv\Scripts\pip install -r requirements.txt
if errorlevel 1 (
    echo [錯誤] 套件安裝失敗
    pause
    exit /b 1
)

echo.
echo ========================================
echo  設定完成！
echo  執行 run.bat 啟動程式（開發模式）
echo  執行 build.bat 打包為獨立 exe
echo ========================================
pause
