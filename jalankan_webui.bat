@echo off
title Absensi Wajah - Web UI
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo.
  echo Python tidak ditemukan di PATH.
  echo Install Python 3.11 terlebih dahulu, lalu jalankan file ini lagi.
  echo.
  pause
  exit /b 1
)

echo.
echo ============================================================
echo   SISTEM ABSENSI WAJAH - WEB UI
echo   Browser akan terbuka otomatis di http://127.0.0.1:5000
echo   Tekan Ctrl+C di jendela ini untuk menghentikan server.
echo ============================================================
echo.

python webui.py --buka
pause
