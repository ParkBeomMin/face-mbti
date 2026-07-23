@echo off
chcp 65001 >nul
REM PDB에서 인물·MBTI·프로필 사진을 한 번에 수집 (Windows)
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

echo.
echo 📸 PDB 데이터셋 수집 시작!
"%RUN%" tools\collect_pdb_dataset.py %*

echo.
echo ✅ dataset\ 폴더를 검수한 뒤 학습하세요 (티처블 머신 또는 train_model.py)
pause
