@echo off
chcp 65001 >nul
echo ========================================
echo   公司請假系統 - Windows .exe 一鍵打包
echo ========================================
echo.

:: 檢查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [錯誤] 找不到 Python，請先安裝 Python 3.10 以上
    echo 下載：https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/3] 安裝必要套件...
pip install -r requirements.txt pyinstaller --quiet
if errorlevel 1 (
    echo [錯誤] 套件安裝失敗
    pause
    exit /b 1
)

echo [2/3] 開始打包成 exe（約需 1~2 分鐘）...
pyinstaller --onefile --name LeaveSystem --noconsole ^
  --add-data "templates;templates" ^
  --add-data "static;static" ^
  --hidden-import=uvicorn.logging ^
  --hidden-import=uvicorn.loops ^
  --hidden-import=uvicorn.loops.auto ^
  --hidden-import=uvicorn.protocols ^
  --hidden-import=uvicorn.protocols.http ^
  --hidden-import=uvicorn.protocols.http.auto ^
  --hidden-import=uvicorn.protocols.websockets ^
  --hidden-import=uvicorn.protocols.websockets.auto ^
  --hidden-import=uvicorn.lifespan ^
  --hidden-import=uvicorn.lifespan.on ^
  --hidden-import=sqlalchemy.dialects.sqlite ^
  --collect-all uvicorn ^
  --collect-all fastapi ^
  --collect-all jinja2 ^
  main.py

if errorlevel 1 (
    echo [錯誤] 打包失敗
    pause
    exit /b 1
)

echo.
echo [3/3] 完成！
echo.
echo 您的程式檔位於：
echo   dist\LeaveSystem.exe
echo.
echo 雙擊 LeaveSystem.exe 即可執行，會自動開啟瀏覽器。
echo.
pause
