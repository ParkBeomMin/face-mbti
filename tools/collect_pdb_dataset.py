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
from collect_mbti import _walk_profiles  # noqa: E402

PDB_WEB = "https://www.personality-database.com"
PDB_API = "https://api.personality-database.com"


class PdbClient:
    """PDB는 Cloudflare가 일반 요청을 차단하므로, 실제 브라우저로 사이트를
    한 번 방문해 통과 쿠키를 얻은 뒤 그 세션으로 API를 호출한다.
    (탐침으로 확인한 실제 엔드포인트: /api/v2/search/top?query=&limit=&nextCursor=0)
    """

    def __init__(self, base_web: str = PDB_WEB, base_api: str = PDB_API):
        import os

        from playwright.sync_api import sync_playwright

        self.base_api = base_api
        self._pw = sync_playwright().start()
        exe = os.environ.get("FACE_MBTI_CHROMIUM")  # 테스트용 오버라이드
        launch_args = {"args": ["--disable-blink-features=AutomationControlled"]}
        self._browser = (self._pw.chromium.launch(executable_path=exe, **launch_args)
                         if exe else self._pw.chromium.launch(**launch_args))
        self.page = self._browser.new_page(user_agent=BROWSER_UA, locale="en-US")
        # Cloudflare 통과 + 세션 쿠키 확보
        self.page.goto(f"{base_web}/search?keyword=kpop",
                       timeout=45000, wait_until="domcontentloaded")
        self.page.wait_for_timeout(4000)

    def search(self, query: str, limit: int) -> list[dict]:
        """프로필 목록 [{name, mbti, img}] (이미지 있는 것만)."""
        resp = self.page.request.get(
            f"{self.base_api}/api/v2/search/top",
            params={"query": query, "limit": limit, "nextCursor": 0},
            timeout=20000)
        if resp.status != 200:
            raise RuntimeError(f"HTTP {resp.status}")
        self.last_raw = resp.text()[:900]  # 파싱 0건일 때 형식 확인용
        out: list[dict] = []
        _walk_profiles(resp.json(), out)
        return [p for p in out if p.get("img")]

    def fetch_image(self, url: str) -> bytes:
        resp = self.page.request.get(url, timeout=20000)
        if resp.status != 200:
            raise RuntimeError(f"이미지 HTTP {resp.status}")
        return resp.body()

    def close(self) -> None:
        self._browser.close()
        self._pw.stop()


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


def save_profile_image(data: bytes, mbti: str, name: str, out_dir: Path,
                       detector, min_face: int, excluded: set[str],
                       seen_hashes: set[str]) -> bool:
    """프로필 사진 바이트를 얼굴 크롭 후 저장. 성공 시 True."""
    import cv2
    import numpy as np

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
    ap.add_argument("--min-face", type=int, default=72,
                    help="얼굴 최소 크기 px (PDB 프로필 썸네일은 작아서 낮게, 기본 72)")
    ap.add_argument("--delay", type=float, default=1.5,
                    help="검색 간 대기 초 (속도 제한 예방, 기본 1.5)")
    ap.add_argument("--no-crop", action="store_true")
    ap.add_argument("--base-web", default=PDB_WEB, help=argparse.SUPPRESS)
    ap.add_argument("--base-api", default=PDB_API, help=argparse.SUPPRESS)
    args = ap.parse_args()

    queries = load_queries(args)
    if not queries:
        sys.exit("검색어가 없어요. tools/pdb_queries.txt 를 확인하거나 --queries 를 지정해주세요")
    print(f"🔎 검색어 {len(queries)}개로 PDB 프로필을 수집합니다 (유형당 최대 {args.per_type}명)\n")

    detector = None if args.no_crop else make_detector()
    excluded = load_excluded()
    client = PdbClient(args.base_web, args.base_api)
    seen_names: set[str] = set()
    seen_hashes: set[str] = set()
    counts: dict[str, int] = {}
    failed_queries = 0

    import time

    debug_shown = False
    for qi, query in enumerate(queries, 1):
        profiles = None
        for attempt in (1, 2):
            try:
                profiles = client.search(query, args.limit_per_query)
                break
            except Exception as e:
                if "429" in str(e) and attempt == 1:
                    print(f"[{qi}/{len(queries)}] '{query}': 속도 제한(429) — 25초 쉬었다 재시도")
                    time.sleep(25)
                    continue
                failed_queries += 1
                print(f"[{qi}/{len(queries)}] '{query}': 검색 실패 ({e})")
                break
        if profiles is None:
            if failed_queries >= 5 and failed_queries == qi:
                sys.exit("연속 실패 — PDB API 접근이 막힌 것 같아요. 네트워크/응답 형식을 확인해주세요.")
            time.sleep(args.delay)
            continue
        if not profiles and not debug_shown and getattr(client, "last_raw", ""):
            # 200인데 파싱 0건 — 응답 형식이 바뀐 경우를 대비해 원문 샘플 출력
            debug_shown = True
            print(f"   ⓘ 응답 샘플(파싱 0건): {client.last_raw}")
        got = 0
        for p in profiles:
            name, mbti = p["name"], p["mbti"]
            if name in seen_names or counts.get(mbti, 0) >= args.per_type:
                continue
            try:
                data = client.fetch_image(p["img"])
                if save_profile_image(data, mbti, name, args.out,
                                      detector, args.min_face, excluded, seen_hashes):
                    seen_names.add(name)
                    counts[mbti] = counts.get(mbti, 0) + 1
                    got += 1
            except Exception:
                continue
        print(f"[{qi}/{len(queries)}] '{query}': 프로필 {len(profiles)}개 중 {got}명 저장")
        time.sleep(args.delay)  # 속도 제한 예방
    client.close()

    total = sum(counts.values())
    print(f"\n✅ 완료! 총 {total}명 저장 → {args.out}")
    for t in sorted(counts):
        print(f"   {t}: {counts[t]}명")
    if total == 0:
        sys.exit("수집 결과가 0명이에요 — 위의 응답 샘플/오류를 확인해주세요.")
    print("\n다음 단계: dataset/ 검수 → 티처블 머신 또는 python tools/train_model.py")


if __name__ == "__main__":
    main()
