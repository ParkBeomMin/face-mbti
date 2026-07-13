@echo off
chcp 65001 >nul
REM 연예인 MBTI 정보 수집 (Windows) — 나무위키에서 MBTI+프로필 사진을 celebs.csv로
cd /d "%~dp0.."

where uv >nul 2>&1
if %errorlevel%==0 (
  if not exist .venv uv venv --python 3.11 .venv
  uv pip install -r tools\requirements-collect.txt
  set "RUN=.venv\Scripts\python.exe"
) else (
  pip install -r tools\requirements-collect.txt
  set "RUN=python"
)
"%RUN%" -m playwright install chromium

echo.
echo 📋 MBTI 수집 시작! (예: mbti_local.bat --names 아이유 카리나 / 생략 시 시드 목록 전체)
"%RUN%" tools\collect_mbti.py %*

echo.
echo ✅ tools\celebs.csv 를 열어 확인하고, 커밋하면 다음 수집부터 반영돼요.
echo    이어서 사진 수집:  tools\collect_local.bat
pause
