#!/usr/bin/env python3
"""dataset/ → 관리자 페이지용 미리보기 생성 🖼

수집된 사진들의 저해상 썸네일과 색인(index.json)을 만들어요.
워크플로가 이 결과를 dataset-preview 브랜치에 올리면
admin.html 이 갤러리로 보여주고, 사진 검수(제외)가 가능해집니다.

    preview/
    ├── index.json                  # [{type, person, file, hash}, ...]
    └── thumbs/ENFP/이름_해시.jpg   # 긴 변 기준 THUMB px

사용법:
    python tools/make_preview.py [--data dataset] [--out preview] [--size 128]
"""

import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

MBTI_RE = re.compile(r"^[EI][SN][TF][JP]$")
ROOT = Path(__file__).resolve().parent.parent
IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}


def main() -> None:
    ap = argparse.ArgumentParser(description="dataset/ 미리보기(썸네일+index.json) 생성")
    ap.add_argument("--data", type=Path, default=ROOT / "dataset")
    ap.add_argument("--out", type=Path, default=ROOT / "preview")
    ap.add_argument("--size", type=int, default=128, help="썸네일 긴 변 px (기본 128)")
    args = ap.parse_args()

    if not args.data.exists():
        sys.exit(f"데이터 폴더가 없어요: {args.data}")

    import cv2

    if args.out.exists():
        shutil.rmtree(args.out)
    (args.out / "thumbs").mkdir(parents=True)

    entries = []
    for type_dir in sorted(args.data.iterdir()):
        if not (type_dir.is_dir() and MBTI_RE.match(type_dir.name.upper())):
            continue
        mbti = type_dir.name.upper()
        (args.out / "thumbs" / mbti).mkdir(exist_ok=True)
        for src in sorted(type_dir.iterdir()):
            if src.suffix.lower() not in IMG_EXTS:
                continue
            img = cv2.imread(str(src))
            if img is None:
                continue
            h, w = img.shape[:2]
            scale = args.size / max(h, w)
            if scale < 1.0:
                img = cv2.resize(img, (max(1, int(w * scale)), max(1, int(h * scale))))
            rel = f"thumbs/{mbti}/{src.stem}.jpg"
            cv2.imwrite(str(args.out / rel), img, [cv2.IMWRITE_JPEG_QUALITY, 70])
            # 원본(학습에 쓰인 파일) 기준 md5 — excluded.txt 와 매칭되는 지문
            digest = hashlib.md5(src.read_bytes()).hexdigest()
            person = src.stem.rsplit("_", 1)[0].replace("_", " ")
            entries.append({"type": mbti, "person": person, "file": rel, "hash": digest})

    (args.out / "index.json").write_text(json.dumps({
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "count": len(entries),
        "items": entries,
    }, ensure_ascii=False), encoding="utf-8")

    by_type: dict[str, int] = {}
    for e in entries:
        by_type[e["type"]] = by_type.get(e["type"], 0) + 1
    print(f"🖼 미리보기 {len(entries)}장 생성 → {args.out}")
    for t in sorted(by_type):
        print(f"   {t}: {by_type[t]}장")


if __name__ == "__main__":
    main()
