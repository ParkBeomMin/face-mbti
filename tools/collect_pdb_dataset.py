#!/usr/bin/env python3
"""PDB 데이터셋 빌더 — Personality Database에서 인물·MBTI·사진을 한 번에 📸

personality-database.com의 검색 API로 프로필(이름 + 커뮤니티 투표 MBTI +
프로필 사진)을 대량으로 모아, 바로 학습 가능한 dataset/ 구조로 저장합니다.

    dataset/
    ├── ENFP/Karina_ab12cd34.jpg   (인물당 1장, 본인 보증!)
    └── ...

핵심 아이디어: "소수 인물 × 사진 여러 장" 대신 "수백 명 × 프로필 1장".
- PDB 프로필 사진은 본인임이 보증되어 본인 확인 필터가 필요 없음
- 유형당 다양한 얼굴 → 모델이 특정 인물이 아니라 유형의 인상을 학습

검색어는 그룹/프로그램 이름이 효율적이에요 (멤버 전원이 한 번에 나옴).
기본 검색어 목록: tools/pdb_queries.txt (+ celebs.csv의 인물들)

준비:  pip install -r tools/requirements-collect.txt
사용법:
    python tools/collect_pdb_dataset.py                  # 기본 검색어 + csv 인물 전체
    python tools/collect_pdb_dataset.py --per-type 60    # 유형당 최대 60명
    python tools/collect_pdb_dataset.py --queries aespa BTS  # 특정 검색어만
"""

import argparse
import hashlib
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUERIES_PATH = ROOT / "tools" / "pdb_queries.txt"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_faces import (  # noqa: E402
    BROWSER_UA, IMG_EXTS, MBTI_RE, crop_main_face, load_celebs, load_excluded,
    make_detector)
from collect_mbti import PDB_API, _walk_profiles  # noqa: E402


def pdb_search(query: str, base: str, limit: int) -> list[dict]:
    """검색어 하나로 프로필 목록 [{name, mbti, img}] 을 가져온다."""
    import json
    import urllib.parse

    q = urllib.parse.urlencode({"keyword": query, "limit": limit})
    req = urllib.request.Request(
        f"{base}/api/v1/search/top?{q}",
        headers={"User-Agent": BROWSER_UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.load(r)
    out: list[dict] = []
    _walk_profiles(data, out)
    # 이미지가 있는 프로필만 (사진이 목적이므로)
    return [p for p in out if p.get("img")]


def load_queries(args) -> list[str]:
    queries: list[str] = []
    if args.queries:
        return args.queries
    if QUERIES_PATH.exists():
        queries += [l.strip() for l in QUERIES_PATH.read_text(encoding="utf-8").splitlines()
                    if l.strip() and not l.strip().startswith("#")]
    csv_path = ROOT / "tools" / "celebs.csv"
    if not args.no_csv_names and csv_path.exists():
        queries += [name for _, name, _ in load_celebs(csv_path, None)]
    # 순서 유지 중복 제거
    seen = set()
    return [q for q in queries if not (q in seen or seen.add(q))]


def save_profile_image(url: str, mbti: str, name: str, out_dir: Path,
                       detector, min_face: int, excluded: set[str],
                       seen_hashes: set[str]) -> bool:
    """프로필 사진을 내려받아 얼굴 크롭 후 저장. 성공 시 True."""
    import cv2
    import numpy as np

    req = urllib.request.Request(url, headers={"User-Agent": BROWSER_UA})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = r.read()
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return False
    if detector is not None:
        face = crop_main_face(img, detector, min_face)
        if face is None:
            return False
        img = face
    if min(img.shape[:2]) < min_face:
        return False
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 92])
    if not ok:
        return False
    digest = hashlib.md5(buf.tobytes()).hexdigest()
    if digest in excluded or digest in seen_hashes:
        return False
    seen_hashes.add(digest)
    safe = re.sub(r"[^\w가-힣]+", "_", name).strip("_")[:40] or "unknown"
    d = out_dir / mbti
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{safe}_{digest[:8]}.jpg").write_bytes(buf.tobytes())
    return True


def main() -> None:
    ap = argparse.ArgumentParser(description="PDB에서 인물·MBTI·사진을 모아 데이터셋 구축")
    ap.add_argument("--queries", nargs="*", help="검색어들 (생략 시 pdb_queries.txt + celebs.csv)")
    ap.add_argument("--no-csv-names", action="store_true", help="celebs.csv 인물은 검색하지 않음")
    ap.add_argument("--out", type=Path, default=ROOT / "dataset")
    ap.add_argument("--per-type", type=int, default=60, help="유형당 최대 인원 (기본 60)")
    ap.add_argument("--limit-per-query", type=int, default=20, help="검색어당 프로필 수 (기본 20)")
    ap.add_argument("--min-face", type=int, default=100)
    ap.add_argument("--no-crop", action="store_true")
    ap.add_argument("--base", default=PDB_API, help=argparse.SUPPRESS)
    args = ap.parse_args()

    queries = load_queries(args)
    if not queries:
        sys.exit("검색어가 없어요. tools/pdb_queries.txt 를 확인하거나 --queries 를 지정해주세요")
    print(f"🔎 검색어 {len(queries)}개로 PDB 프로필을 수집합니다 (유형당 최대 {args.per_type}명)\n")

    detector = None if args.no_crop else make_detector()
    excluded = load_excluded()
    seen_names: set[str] = set()
    seen_hashes: set[str] = set()
    counts: dict[str, int] = {}
    failed_queries = 0

    for qi, query in enumerate(queries, 1):
        try:
            profiles = pdb_search(query, args.base, args.limit_per_query)
        except Exception as e:
            failed_queries += 1
            print(f"[{qi}/{len(queries)}] '{query}': 검색 실패 ({e})")
            if failed_queries >= 5 and failed_queries == qi:
                sys.exit("연속 실패 — PDB API 접근이 막힌 것 같아요. 네트워크/응답 형식을 확인해주세요.")
            continue
        got = 0
        for p in profiles:
            name, mbti = p["name"], p["mbti"]
            if name in seen_names or counts.get(mbti, 0) >= args.per_type:
                continue
            try:
                if save_profile_image(p["img"], mbti, name, args.out,
                                      detector, args.min_face, excluded, seen_hashes):
                    seen_names.add(name)
                    counts[mbti] = counts.get(mbti, 0) + 1
                    got += 1
            except Exception:
                continue
        print(f"[{qi}/{len(queries)}] '{query}': 프로필 {len(profiles)}개 중 {got}명 저장")

    total = sum(counts.values())
    print(f"\n✅ 완료! 총 {total}명 저장 → {args.out}")
    for t in sorted(counts):
        print(f"   {t}: {counts[t]}명")
    print("\n다음 단계: dataset/ 검수 → 티처블 머신 또는 python tools/train_model.py")


if __name__ == "__main__":
    main()
