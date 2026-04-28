@echo off
echo Starting Budget Tracker...
cd /d "%~dp0backend"
set PATH=%PATH%;%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Python\Python311\Scripts
python app.py
pause
