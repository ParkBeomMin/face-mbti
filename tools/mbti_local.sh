#!/usr/bin/env bash
# 연예인 MBTI 정보 수집 (Mac/Linux) — 나무위키에서 MBTI+프로필 사진을 celebs.csv로
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
"$RUN" -m playwright install chromium

echo ""
echo "📋 MBTI 수집 시작! (예: ./tools/mbti_local.sh --names 아이유 카리나 / 생략 시 시드 목록 전체)"
"$RUN" tools/collect_mbti.py "$@"

echo ""
echo "✅ tools/celebs.csv 를 열어 확인하고, 커밋하면 다음 수집부터 반영돼요."
echo "   이어서 사진 수집:  ./tools/collect_local.sh"
