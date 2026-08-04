@echo off
cd /d "%~dp0"
echo Starting Diso public license...
start "DisoLicense" /MIN python diso_license_server.py
timeout /t 2 /nobreak >nul
start "DisoTunnel" /MIN cloudflared.exe tunnel --url http://127.0.0.1:7474
echo.
echo Server + tunnel started (minimized).
echo Keep this PC ON and connected to internet.
echo Check cloudflared window for the https://....trycloudflare.com URL
echo If URL changed, re-run set URL + rebuild OR re-run this after updating ACTIVE_URL.
pause
