@echo off
setlocal
cd /d "%~dp0"
if not exist .venv (
  py -3 -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
pyinstaller --noconfirm --clean --onefile --windowed ^
  --name OrionSSH ^
  --icon assets\orionssh.ico ^
  --add-data "assets\orionssh.png;assets" ^
  --add-data "contacts.json;." ^
  --collect-all tkinterdnd2 ^
  --hidden-import keyring.backends.Windows ^
  --hidden-import keyring.backends.fail ^
  --hidden-import pyte.screens ^
  --hidden-import pyte.streams ^
  src\main.py

if exist contacts.json copy /Y contacts.json dist\contacts.json >nul

echo.
echo Portable EXE created at: dist\OrionSSH.exe
echo To create an installer, install Inno Setup and compile installer\OrionSSH.iss
pause
