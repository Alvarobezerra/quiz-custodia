@echo off
title Quiz Interativo
echo Iniciando Servidor e Link Publico...
cd /d "%~dp0"
start "Servidor Quiz" python server.py
timeout /t 2 /nobreak >nul
start "Tunnel Publico" cloudflared.exe tunnel --url http://localhost:8888
echo.
echo =======================================================
echo Servidor iniciado com sucesso!
echo Olhe a janela "Tunnel Publico" para ver sua URL HTTPS.
echo =======================================================
pause
