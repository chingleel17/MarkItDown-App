@echo off
chcp 65001 > nul
echo ========================================
echo  MarkItDown App - 打包為獨立執行檔
echo ========================================
echo.

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

echo [1/3] 清除舊版打包檔...
if exist "dist\MarkItDownApp" rmdir /s /q "dist\MarkItDownApp"
if exist "build\MarkItDownApp" rmdir /s /q "build\MarkItDownApp"

echo [2/3] 開始打包（此過程需要數分鐘，請耐心等候）...
uv run --locked --python 3.12 python -m PyInstaller app.spec --noconfirm
if errorlevel 1 (
    echo.
    echo [錯誤] 打包失敗，請查看上方訊息
    echo 提示：如有缺少模組，請在 app.spec 的 hiddenimports 中補充
    pause
    exit /b 1
)

echo [3/3] 驗證輸出...
if not exist "dist\MarkItDownApp\MarkItDownApp.exe" (
    echo [錯誤] 找不到輸出的 exe 檔
    pause
    exit /b 1
)

echo.
echo ========================================
echo  打包完成！
echo  輸出位置：dist\MarkItDownApp\
echo  請將整個 MarkItDownApp 資料夾分發給使用者
echo  使用者直接執行 MarkItDownApp.exe 即可
echo ========================================
echo.
echo 是否立即開啟輸出資料夾？(Y/N)
set /p open_folder=
if /i "%open_folder%"=="Y" explorer "dist\MarkItDownApp"
pause
