#!/usr/bin/env bash
# 내 PC에서 수집하기 (Mac/Linux) — 한국 IP라 검색 정확도가 CI보다 훨씬 좋아요
# uv가 설치되어 있으면 uv를 사용 (Python 3.11 자동 확보), 없으면 pip 사용
set -e
cd "$(dirname "$0")/.."

if command -v uv >/dev/null 2>&1; then
  echo "📦 uv로 환경 준비 중 (Python 3.11)..."
  uv venv --python 3.11 .venv
  uv pip install -r tools/requirements-collect.txt
  RUN=".venv/bin/python"
  "$RUN" -m playwright install chromium
else
  echo "📦 pip로 의존성 설치 중... (⚠️ Python 3.11 필요 — 3.12+면 uv 설치를 추천: https://docs.astral.sh/uv/)"
  pip install -r tools/requirements-collect.txt
  playwright install chromium
  RUN="python"
fi

echo ""
echo "🔎 수집 시작! (옵션은 그대로 전달돼요. 예: ./tools/collect_local.sh --only ENFP --limit 40)"
"$RUN" tools/collect_faces.py "$@"

echo ""
echo "✅ 끝! dataset/ 폴더를 열어 사진을 확인하세요."
echo "   다음 단계:"
echo "   A) 티처블 머신(teachablemachine.withgoogle.com)에 폴더별 업로드 → 학습 →"
echo "      TF.js 내보내기 → 3개 파일을 models/tm/ 에 넣고 커밋"
echo "   B) 또는 로컬 학습:  $RUN tools/train_model.py  → models/tm/ 커밋"
