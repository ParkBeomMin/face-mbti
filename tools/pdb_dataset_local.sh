#!/usr/bin/env bash
# PDB에서 인물·MBTI·프로필 사진을 한 번에 수집 (Mac/Linux)
set -e
cd "$(dirname "$0")/.."

if command -v uv >/dev/null 2>&1; then
  [ -d .venv ] || uv venv --python 3.11 .venv
  uv pip install -r tools/requirements-collect.txt
  RUN=".venv/bin/python"
else
  pip install -r tools/requirements-collect.txt
  RUN="python"
fi

echo ""
echo "📸 PDB 데이터셋 수집 시작! (예: ./tools/pdb_dataset_local.sh --per-type 60)"
"$RUN" tools/collect_pdb_dataset.py "$@"

echo ""
echo "✅ dataset/ 폴더를 검수한 뒤 학습하세요:"
echo "   A) 티처블 머신에 유형 폴더별 업로드 → TF.js 내보내기 → models/tm/ 커밋"
echo "   B) uv pip install -r tools/requirements.txt && $RUN tools/train_model.py"
