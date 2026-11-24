@echo off
cd /d "%~dp0"
python keyboard_drive.py --aduc814 %*
if errorlevel 1 pause
