@echo off
chcp 65001 >nul
REM 내 PC에서 수집하기 (Windows) — 한국 IP라 검색 정확도가 CI보다 훨씬 좋아요
REM uv가 설치되어 있으면 uv 사용 (Python 3.11 자동 확보), 없으면 pip 사용
cd /d "%~dp0.."

where uv >nul 2>&1
if %errorlevel%==0 (
  echo 📦 uv로 환경 준비 중 ^(Python 3.11^)...
  uv venv --python 3.11 .venv
  uv pip install -r tools\requirements.txt
  set "RUN=.venv\Scripts\python.exe"
) else (
  echo 📦 pip로 의존성 설치 중... ^(주의: Python 3.11 필요 — 3.12+면 uv 설치 추천^)
  pip install -r tools\requirements.txt
  set "RUN=python"
)

"%RUN%" -m playwright install chromium

echo.
echo 🔎 수집 시작! (옵션 전달 가능: collect_local.bat --only ENFP --limit 40)
"%RUN%" tools\collect_faces.py %*

echo.
echo ✅ 끝! dataset\ 폴더를 열어 사진을 확인하세요.
echo    다음 단계:
echo    A) 티처블 머신(teachablemachine.withgoogle.com)에 폴더별 업로드 - 학습 -
echo       TF.js 내보내기 - 3개 파일을 models\tm\ 에 넣고 커밋
echo    B) 또는 로컬 학습:  "%RUN%" tools\train_model.py  - models\tm\ 커밋
pause
