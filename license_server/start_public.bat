@echo off
cd /d "%~dp0"
echo === Diso public license ===
echo Starting license server...
start "DisoLicense" /MIN python diso_license_server.py
timeout /t 3 /nobreak >nul
echo Starting Cloudflare tunnel (keep PC ON)...
start "DisoTunnel" cloudflared.exe tunnel --url http://127.0.0.1:7474 --no-autoupdate
echo.
echo Wait for a line: https://xxxxx.trycloudflare.com
echo Then on PC run:
echo   python ..\tools\fix_and_verify_license.py
echo   python ..\tools\build_debs_and_repo.py
echo And reinstall deb on iPhone IF the tunnel URL changed.
echo.
echo Do NOT close the DisoTunnel window.
pause
