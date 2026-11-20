@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo Перевірка залежностей (openai, pyinstaller)...
python -m pip install --quiet openai pyinstaller

echo Збірка AI_Game_Master.exe...
python -m PyInstaller --noconfirm --onefile --windowed --name "AI_Game_Master" main.py

if exist "dist\AI_Game_Master.exe" (
    copy /Y "dist\AI_Game_Master.exe" "AI_Game_Master.exe" >nul
    rmdir /s /q build 2>nul
    rmdir /s /q dist 2>nul
    del /q AI_Game_Master.spec 2>nul
    echo.
    echo [ГОТОВО] Файл AI_Game_Master.exe створено! Запускайте його подвійним кліком.
) else (
    echo [ПОМИЛКА] Не вдалося створити AI_Game_Master.exe.
)
pause