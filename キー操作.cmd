@echo off
cd /d "%~dp0"
python keyboard_drive.py %*
if errorlevel 1 pause
