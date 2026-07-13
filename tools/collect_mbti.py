#!/usr/bin/env python3
"""연예인 MBTI 정보 수집기 — 나무위키에서 MBTI + 프로필 사진을 모아 celebs.csv를 채운다 📋

이름 목록만 주면, 나무위키 인물 문서에서:
  1) 프로필 표의 MBTI (예: "MBTI | INFJ" — 최신 정보!)
  2) 프로필 사진 URL (수집기의 본인 확인 앵커로 사용됨)
를 뽑아서 tools/celebs.csv 에 병합합니다.

- 기존 행은 보존 (MBTI가 다르면 알려주기만 하고 덮어쓰지 않음)
- 이미 있는 인물은 기준 사진 URL이 비어 있을 때만 채움
- MBTI를 못 찾은 인물은 건너뜀 (직접 추가하면 됨)

준비:  pip install playwright && playwright install chromium
사용법:
    python tools/collect_mbti.py                       # 동봉 시드 목록(seed_names.txt) 전체
    python tools/collect_mbti.py --names 아이유 카리나  # 특정 인물만
    python tools/collect_mbti.py --dry-run             # csv 수정 없이 결과만 보기

⚠️ 나무위키는 봇 차단이 있어 해외 IP(CI)에서는 실패할 수 있어요 — 내 PC에서 실행 추천.
"""

import argparse
import os
import re
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "tools" / "celebs.csv"
SEED_PATH = ROOT / "tools" / "seed_names.txt"
MBTI_RE = re.compile(r"\b([EI][SN][TF][JP])(?:-[AT])?\b")
BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def fetch_profile(page, name: str, base: str, img_pattern: str):
    """나무위키 문서에서 (MBTI, 프로필사진URL)을 뽑는다. 못 찾으면 None."""
    page.goto(f"{base}/w/{urllib.parse.quote(name)}",
              timeout=30000, wait_until="domcontentloaded")
    page.wait_for_timeout(2000)
    data = page.evaluate(
        """(pat) => {
            let img = null;
            for (const im of document.querySelectorAll('img')) {
                const s = im.currentSrc || im.src || '';
                if (s.includes(pat) && im.naturalWidth >= 150 && im.naturalHeight >= 150) {
                    img = s; break;
                }
            }
            return { text: (document.body.innerText || '').slice(0, 30000), img };
        }""", img_pattern)

    # 'MBTI' 라벨 바로 뒤에 나오는 유형을 채택 (프로필 표 형태)
    mbti = None
    for m in re.finditer(r"MBTI", data["text"]):
        t = MBTI_RE.search(data["text"][m.end(): m.end() + 60])
        if t:
            mbti = t.group(1)
            break
    return mbti, data["img"]


def load_names(args) -> list[str]:
    if args.names:
        return args.names
    if not SEED_PATH.exists():
        sys.exit(f"시드 목록이 없어요: {SEED_PATH}\n--names 이름1 이름2 ... 로 지정해주세요")
    return [l.strip() for l in SEED_PATH.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.strip().startswith("#")]


def merge_csv(found: list[tuple[str, str, str]], dry_run: bool) -> None:
    """found = [(이름, MBTI, 사진URL)] 을 celebs.csv에 병합."""
    lines = CSV_PATH.read_text(encoding="utf-8").splitlines() if CSV_PATH.exists() else ["MBTI,이름"]
    existing: dict[str, int] = {}  # 이름 → 줄 번호
    for i, line in enumerate(lines):
        t = line.strip()
        if not t or t.startswith("#") or t.upper().startswith("MBTI,"):
            continue
        parts = t.split(",")
        if len(parts) >= 2:
            existing[parts[1].strip()] = i

    added = updated = 0
    for name, mbti, img in found:
        if name in existing:
            i = existing[name]
            parts = [p.strip() for p in lines[i].split(",")]
            if parts[0].upper() != mbti:
                print(f"  ℹ️ {name}: 목록엔 {parts[0]}, 나무위키엔 {mbti} — 기존 값 유지 (직접 확인해주세요)")
            if img and (len(parts) < 3 or not parts[2]):  # 빈 기준 사진만 채움
                lines[i] = f"{parts[0]},{parts[1]},{img}"
                updated += 1
                print(f"  🔗 {name}: 기준 사진 URL 채움")
        else:
            lines.append(f"{mbti},{name}" + (f",{img}" if img else ""))
            added += 1
            print(f"  ➕ {name}: {mbti}" + (" (사진 포함)" if img else ""))

    if dry_run:
        print(f"\n(--dry-run: csv 미수정) 추가 예정 {added}명, 사진 채움 {updated}명")
        return
    CSV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n💾 celebs.csv 저장: {added}명 추가, {updated}명 사진 채움")


def main() -> None:
    ap = argparse.ArgumentParser(description="나무위키에서 연예인 MBTI + 프로필 사진 수집")
    ap.add_argument("--names", nargs="*", help="수집할 인물 이름들 (생략 시 seed_names.txt)")
    ap.add_argument("--base", default="https://namu.wiki", help=argparse.SUPPRESS)
    ap.add_argument("--img-pattern", default="namu.wiki/i/", help=argparse.SUPPRESS)
    ap.add_argument("--dry-run", action="store_true", help="csv 수정 없이 결과만 보기")
    args = ap.parse_args()

    names = load_names(args)
    print(f"📋 {len(names)}명의 MBTI를 나무위키에서 조회합니다\n")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("playwright가 필요해요:  pip install playwright && playwright install chromium")

    found: list[tuple[str, str, str]] = []
    skipped: list[str] = []
    with sync_playwright() as p:
        exe = os.environ.get("FACE_MBTI_CHROMIUM")  # 테스트용 오버라이드
        browser = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
        page = browser.new_page(user_agent=BROWSER_UA, locale="ko-KR")
        for i, name in enumerate(names, 1):
            try:
                mbti, img = fetch_profile(page, name, args.base, args.img_pattern)
            except Exception as e:
                print(f"[{i}/{len(names)}] {name}: 조회 실패 ({e})")
                skipped.append(name)
                continue
            if mbti:
                print(f"[{i}/{len(names)}] {name}: {mbti}" + (" 📷" if img else ""))
                found.append((name, mbti, img or ""))
            else:
                print(f"[{i}/{len(names)}] {name}: MBTI 정보 없음 → 건너뜀")
                skipped.append(name)
        browser.close()

    print(f"\n✅ 조회 완료: {len(found)}명 확보, {len(skipped)}명 건너뜀")
    if found:
        merge_csv(found, args.dry_run)
    if skipped:
        print(f"건너뛴 인물: {', '.join(skipped[:20])}" + (" ..." if len(skipped) > 20 else ""))


if __name__ == "__main__":
    main()
