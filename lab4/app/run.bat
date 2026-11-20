@echo off
chcp 65001 >nul
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo [ПОМИЛКА] Python не знайдено в PATH. Встановіть Python 3.10+ з python.org
    pause
    exit /b 1
)

python -c "import openai" 2>nul
if errorlevel 1 (
    echo Встановлення бібліотеки openai...
    pip install openai
)

start "" pythonw main.py