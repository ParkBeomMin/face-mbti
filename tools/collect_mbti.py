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
MBTI_SET = {a + b + c + d for a in "EI" for b in "SN" for c in "TF" for d in "JP"}
BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
PDB_API = "https://api.personality-database.com"


MBTI_TOKEN_RE = re.compile(r"\b(" + "|".join(sorted(MBTI_SET)) + r")\b")
# 우선순위 순서 (subcategory("K-pop" 등)가 실제 이름을 가리지 않도록 뒤에)
_NAME_KEYS = ("name", "mbti_profile", "profile_name", "title", "display_name",
              "alt_name", "subcategory")
_IMG_HINTS = ("image", "picture", "avatar", "pic", "img", "photo", "thumb")


def _extract_mbti_from(value) -> str | None:
    """문자열 또는 dict/list 안의 문자열들에서 MBTI 토큰을 찾는다."""
    if isinstance(value, str):
        m = MBTI_TOKEN_RE.search(value.upper())
        return m.group(1) if m else None
    if isinstance(value, dict):
        for vv in value.values():
            got = _extract_mbti_from(vv)
            if got:
                return got
    if isinstance(value, list):
        for vv in value:
            got = _extract_mbti_from(vv)
            if got:
                return got
    return None


def _walk_profiles(obj, out: list) -> None:
    """PDB API 응답(JSON)에서 {이름, MBTI, 사진} 꼴의 프로필을 찾는다.

    실제 v2 응답 기준 (run #11 로그에서 확인):
      {"name": "RM (BTS)", "image": {"picURL": "https://..."},
       "personalities": [{"system": "Four Letter", "personality": "INFJ"},
                         {"system": "Enneagram", "personality": "4w5"}], ...}
    - MBTI: personalities 배열(커뮤니티 투표) 우선, mbti/personality/type
      힌트가 있는 문자열·중첩 구조에서 정규식 추출 (엔네아그램 "4w5"는 미매칭)
    - 이미지: image 계열 키의 직접 문자열 또는 중첩 오브젝트({picURL})
    - 이름: name > mbti_profile > ... > subcategory 우선순위 (오인 방지)
    """
    if isinstance(obj, dict):
        mbti = img = None
        names: dict[str, str] = {}
        for k, v in obj.items():
            kl = k.lower()
            if isinstance(v, str):
                if (not mbti and kl not in _NAME_KEYS
                        and ("personality" in kl or "mbti" in kl or "type" in kl)):
                    mbti = _extract_mbti_from(v)
                if not img and any(h in kl for h in _IMG_HINTS) and v.startswith("http"):
                    img = v
                if kl in _NAME_KEYS and v.strip() and kl not in names:
                    names[kl] = v.strip()
            elif isinstance(v, (dict, list)):
                if not mbti and ("personalit" in kl or "mbti" in kl):
                    mbti = _extract_mbti_from(v)
                if (not img and isinstance(v, dict)
                        and any(h in kl for h in _IMG_HINTS)):
                    for vv in v.values():  # 중첩 이미지 오브젝트 {picURL: ...}
                        if isinstance(vv, str) and vv.startswith("http"):
                            img = vv
                            break
        name = next((names[k] for k in _NAME_KEYS if k in names), None)
        if mbti and name:
            out.append({"name": name, "mbti": mbti, "img": img})
        for v in obj.values():
            _walk_profiles(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _walk_profiles(v, out)


def pdb_lookup(name: str, base: str = PDB_API):
    """Personality Database에서 (MBTI, 사진URL, 매칭된이름)을 찾는다. 실패 시 (None, None, None)."""
    import json
    import urllib.parse
    import urllib.request

    query = urllib.parse.urlencode({"keyword": name, "limit": 10})
    req = urllib.request.Request(
        f"{base}/api/v1/search/top?{query}",
        headers={"User-Agent": BROWSER_UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.load(r)
    except Exception as e:
        raise RuntimeError(f"PDB 조회 실패: {e}")

    profiles: list[dict] = []
    _walk_profiles(data, profiles)
    if not profiles:
        return None, None, None
    # 검색어가 이름에 포함된 프로필 우선, 없으면 첫 결과
    low = name.lower()
    best = next((p for p in profiles if low in p["name"].lower()), profiles[0])
    return best["mbti"], best.get("img"), best["name"]


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
    if getattr(args, "csv_names", False):  # celebs.csv의 전원 재조회 (--update와 조합)
        if not CSV_PATH.exists():
            sys.exit(f"celebs.csv가 없어요: {CSV_PATH}")
        names = []
        for line in CSV_PATH.read_text(encoding="utf-8").splitlines():
            t = line.strip()
            if not t or t.startswith("#") or t.upper().startswith("MBTI,"):
                continue
            parts = t.split(",")
            if len(parts) >= 2 and parts[1].strip():
                names.append(parts[1].strip())
        return names
    if not SEED_PATH.exists():
        sys.exit(f"시드 목록이 없어요: {SEED_PATH}\n--names 이름1 이름2 ... 로 지정해주세요")
    return [l.strip() for l in SEED_PATH.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.strip().startswith("#")]


def merge_csv(found: list[tuple[str, str, str]], dry_run: bool, update: bool = False) -> None:
    """found = [(이름, MBTI, 사진URL)] 을 celebs.csv에 병합.

    update=True면 기존 인물의 MBTI·기준 사진도 조회 결과로 덮어쓴다
    (수기로 채운 1차 시드를 실데이터로 최신화할 때 사용).
    """
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
            old_mbti = parts[0].upper()
            old_img = parts[2] if len(parts) > 2 else ""
            if update:
                new_img = img or old_img
                if old_mbti != mbti or (img and img != old_img):
                    if old_mbti != mbti:
                        print(f"  🔄 {name}: {old_mbti} → {mbti}")
                    lines[i] = f"{mbti},{parts[1]}" + (f",{new_img}" if new_img else "")
                    updated += 1
            else:
                if old_mbti != mbti:
                    print(f"  ℹ️ {name}: 목록엔 {old_mbti}, 조회 결과는 {mbti} — 기존 값 유지 (--update로 덮어쓰기 가능)")
                if img and not old_img:  # 빈 기준 사진만 채움
                    lines[i] = f"{parts[0]},{parts[1]},{img}"
                    updated += 1
                    print(f"  🔗 {name}: 기준 사진 URL 채움")
        else:
            lines.append(f"{mbti},{name}" + (f",{img}" if img else ""))
            added += 1
            print(f"  ➕ {name}: {mbti}" + (" (사진 포함)" if img else ""))

    if dry_run:
        print(f"\n(--dry-run: csv 미수정) 추가 예정 {added}명, 갱신 예정 {updated}명")
        return
    CSV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n💾 celebs.csv 저장: {added}명 추가, {updated}명 갱신")


def main() -> None:
    ap = argparse.ArgumentParser(description="연예인 MBTI + 프로필 사진 수집 (PDB → 나무위키)")
    ap.add_argument("--names", nargs="*", help="수집할 인물 이름들 (생략 시 seed_names.txt)")
    ap.add_argument("--source", choices=["auto", "pdb", "namu"], default="auto",
                    help="auto: PDB 먼저, 실패 시 나무위키 (기본)")
    ap.add_argument("--base", default="https://namu.wiki", help=argparse.SUPPRESS)
    ap.add_argument("--pdb-base", default=PDB_API, help=argparse.SUPPRESS)
    ap.add_argument("--img-pattern", default="namu.wiki/i/", help=argparse.SUPPRESS)
    ap.add_argument("--csv-names", action="store_true",
                    help="celebs.csv에 있는 전원을 재조회 (--update와 조합해 최신화)")
    ap.add_argument("--update", action="store_true",
                    help="기존 인물의 MBTI·기준 사진도 조회 결과로 덮어쓰기")
    ap.add_argument("--dry-run", action="store_true", help="csv 수정 없이 결과만 보기")
    args = ap.parse_args()

    names = load_names(args)
    print(f"📋 {len(names)}명의 MBTI를 조회합니다 (소스: {args.source})\n")

    found: list[tuple[str, str, str]] = []
    skipped: list[str] = []
    browser = page = pw = None

    def namu_page():
        """나무위키가 필요할 때만 브라우저를 띄운다."""
        nonlocal browser, page, pw
        if page is None:
            from playwright.sync_api import sync_playwright
            pw = sync_playwright().start()
            exe = os.environ.get("FACE_MBTI_CHROMIUM")  # 테스트용 오버라이드
            browser = pw.chromium.launch(executable_path=exe) if exe else pw.chromium.launch()
            page = browser.new_page(user_agent=BROWSER_UA, locale="ko-KR")
        return page

    for i, name in enumerate(names, 1):
        mbti = img = None
        src = ""
        # 1) Personality Database (커뮤니티 투표 기반, 사진 포함)
        if args.source in ("auto", "pdb"):
            try:
                mbti, img, matched = pdb_lookup(name, args.pdb_base)
                if mbti:
                    src = f"PDB:{matched}" if matched and matched != name else "PDB"
            except RuntimeError as e:
                print(f"[{i}/{len(names)}] {name}: {e}")
        # 2) 나무위키 폴백
        if not mbti and args.source in ("auto", "namu"):
            try:
                mbti, img = fetch_profile(namu_page(), name, args.base, args.img_pattern)
                if mbti:
                    src = "나무위키"
            except ImportError:
                if args.source == "namu":
                    sys.exit("playwright가 필요해요:  pip install playwright && playwright install chromium")
            except Exception as e:
                print(f"[{i}/{len(names)}] {name}: 나무위키 조회 실패 ({e})")

        if mbti:
            print(f"[{i}/{len(names)}] {name}: {mbti} ({src})" + (" 📷" if img else ""))
            found.append((name, mbti, img or ""))
        else:
            print(f"[{i}/{len(names)}] {name}: MBTI 정보 없음 → 건너뜀")
            skipped.append(name)

    if browser is not None:
        browser.close()
        pw.stop()

    print(f"\n✅ 조회 완료: {len(found)}명 확보, {len(skipped)}명 건너뜀")
    if found:
        merge_csv(found, args.dry_run, update=args.update)
    if skipped:
        print(f"건너뛴 인물: {', '.join(skipped[:20])}" + (" ..." if len(skipped) > 20 else ""))


if __name__ == "__main__":
    main()
