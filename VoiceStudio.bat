@echo off
chcp 65001 > nul
cd /d "%~dp0"
title VoiceStudio
if not exist ".venv\Scripts\python.exe" (
  echo [오류] 설치가 안 되어 있습니다. scripts\install.ps1 을 먼저 실행하세요.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m app.main %*
if errorlevel 1 (
  echo.
  echo [오류] VoiceStudio가 비정상 종료되었습니다. 위 메시지를 확인하세요.
  pause
)
