#!/usr/bin/env bash
# 내 PC에서 수집하기 (Mac/Linux) — 한국 IP라 검색 정확도가 CI보다 훨씬 좋아요
set -e
cd "$(dirname "$0")/.."

echo "📦 의존성 설치 중..."
pip install -r tools/requirements.txt
playwright install chromium

echo ""
echo "🔎 수집 시작! (옵션은 그대로 전달돼요. 예: ./tools/collect_local.sh --only ENFP --limit 40)"
python tools/collect_faces.py "$@"

echo ""
echo "✅ 끝! dataset/ 폴더를 열어 사진을 확인하세요."
echo "   다음 단계:"
echo "   A) 티처블 머신(teachablemachine.withgoogle.com)에 폴더별 업로드 → 학습 →"
echo "      TF.js 내보내기 → 3개 파일을 models/tm/ 에 넣고 커밋"
echo "   B) 또는 로컬 학습:  python tools/train_model.py  → models/tm/ 커밋"
