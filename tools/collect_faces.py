#!/usr/bin/env python3
"""연예인 얼굴 데이터 수집기 — 티처블 머신 학습용 🤖

tools/celebs.csv 의 "MBTI,연예인이름" 목록을 읽어서
인물별로 이미지를 검색·다운로드하고, 얼굴 부분만 잘라
티처블 머신에 바로 업로드할 수 있는 폴더 구조로 정리합니다.

    dataset/
    ├── ENFP/
    │   ├── 아무개_001.jpg   (얼굴 크롭됨)
    │   └── ...
    ├── ISTJ/
    └── ...

준비:
    pip install icrawler opencv-python

사용법:
    python tools/collect_faces.py                  # celebs.csv 전체 수집 (인물당 30장)
    python tools/collect_faces.py --limit 50       # 인물당 50장
    python tools/collect_faces.py --only ENFP ISTJ # 특정 유형만
    python tools/collect_faces.py --no-crop        # 얼굴 크롭 없이 원본 저장
    python tools/collect_faces.py --csv my.csv     # 다른 목록 파일 사용

수집이 끝나면:
    1. dataset/ 안의 각 유형 폴더를 열어 잘못 잡힌 사진(다른 사람, 뒷모습 등)을 지워주세요
    2. 티처블 머신(이미지 프로젝트)에서 클래스 이름을 유형과 똑같이 만들고
       각 폴더의 사진을 드래그해서 업로드 → 학습 → Tensorflow.js로 내보내기
    3. 내보낸 3개 파일을 models/tm/ 에 넣으면 앱이 자동으로 사용해요!

⚠️  수집한 사진은 개인 학습용으로만 사용하고, 저장소나 웹에 재배포하지 마세요.
    (학습된 모델 파일에는 사진이 포함되지 않으므로 모델은 올려도 괜찮아요)
"""

import argparse
import csv
import hashlib
import re
import shutil
import sys
import tempfile
from pathlib import Path

MBTI_RE = re.compile(r"^[EI][SN][TF][JP]$")
ROOT = Path(__file__).resolve().parent.parent
IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
EXCLUDED_FILE = ROOT / "tools" / "excluded.txt"


def load_excluded(path: Path = EXCLUDED_FILE) -> set[str]:
    """관리자 페이지에서 '제외' 표시한 사진들의 md5 목록을 읽는다."""
    if not path.exists():
        return set()
    out = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.add(line.split()[0].lower())
    return out


def load_celebs(csv_path: Path, only: set[str] | None) -> list[tuple[str, str, str]]:
    """CSV에서 (MBTI, 이름, 기준사진URL) 목록을 읽는다.

    형식: MBTI,이름[,기준사진URL]  (헤더/주석/빈줄 허용, URL은 선택)
    URL이 있으면 그 사진과 닮은 얼굴만 수집한다 (본인 확인 앵커).
    """
    rows: list[tuple[str, str, str]] = []
    with open(csv_path, encoding="utf-8") as f:
        for lineno, row in enumerate(csv.reader(f), 1):
            if not row or row[0].strip().startswith("#"):
                continue
            if len(row) < 2:
                print(f"  [무시] {csv_path.name}:{lineno} — 열이 부족해요: {row}")
                continue
            mbti = row[0].strip().upper()
            name = row[1].strip()
            ref = row[2].strip() if len(row) > 2 else ""
            if mbti == "MBTI":  # 헤더
                continue
            if not MBTI_RE.match(mbti):
                print(f"  [무시] {csv_path.name}:{lineno} — MBTI 형식이 아니에요: {mbti!r}")
                continue
            if not name:
                continue
            if only and mbti not in only:
                continue
            rows.append((mbti, name, ref))
    return rows


def download_images(name: str, limit: int, out_dir: Path) -> int:
    """Bing 이미지 검색으로 인물 사진 후보를 out_dir에 다운로드한다.

    - 한 검색어만 쓰면 Bing이 엉뚱한 결과를 주거나 수량이 부족한 경우가
      많아서, 검색어 3종(이름/프로필/얼굴)으로 나눠 받아온다.
      (중복 사진은 이후 단계에서 지문으로 자동 제거됨)
    - 필터: 인물(portrait) + 대형(large) 사진 위주.
    """
    from icrawler.builtin import BingImageCrawler

    queries = [name, f"{name} 프로필", f"{name} 얼굴"]
    per_query = max(10, limit)
    offset = 0
    for q in queries:
        crawler = BingImageCrawler(
            storage={"root_dir": str(out_dir)},
            downloader_threads=4,
            log_level=40,  # ERROR만 (조용히)
        )
        try:
            crawler.crawl(
                keyword=q,
                max_num=per_query,
                file_idx_offset=offset,
                filters={"type": "photo", "size": "large", "people": "portrait"},
            )
        except Exception as e:  # 검색어 하나 실패해도 계속
            print(f"   ⚠️ '{q}' 검색 실패: {e}")
        offset += per_query
    return sum(1 for p in out_dir.iterdir() if p.suffix.lower() in IMG_EXTS)


YUNET_URL = ("https://github.com/opencv/opencv_zoo/raw/main/models/"
             "face_detection_yunet/face_detection_yunet_2023mar.onnx")
SFACE_URL = ("https://github.com/opencv/opencv_zoo/raw/main/models/"
             "face_recognition_sface/face_recognition_sface_2021dec.onnx")


def _download_model(url: str, filename: str) -> Path:
    path = Path(__file__).resolve().parent / ".cache" / filename
    if not path.exists():
        print(f"  {filename} 모델 다운로드 중 (최초 1회)...")
        path.parent.mkdir(parents=True, exist_ok=True)
        import urllib.request
        try:
            urllib.request.urlretrieve(url, path)
        except Exception:
            path.unlink(missing_ok=True)
            raise
    return path


def make_recognizer():
    """SFace 얼굴 인식기(본인 확인용). 사용 불가 환경이면 None (필터 생략)."""
    import cv2

    if not hasattr(cv2, "FaceRecognizerSF_create"):
        print("  ⚠️ OpenCV에 얼굴 인식 모듈이 없어 본인 확인을 건너뜁니다")
        return None
    try:
        model = _download_model(SFACE_URL, "sface.onnx")
        return cv2.FaceRecognizerSF_create(str(model), "")
    except Exception as e:
        print(f"  ⚠️ 얼굴 인식 모델 준비 실패({e}) — 본인 확인 없이 수집합니다")
        return None


def face_feature(recognizer, img):
    """얼굴 크롭 → 임베딩 벡터 (SFace 입력 112x112)."""
    import cv2

    face = cv2.resize(img, (112, 112))
    return recognizer.feature(face)


def cosine(a, b) -> float:
    import numpy as np

    a, b = np.ravel(a), np.ravel(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


def identity_filter(feats: list, ref_feat=None, thr: float = 0.30) -> list[int]:
    """'같은 인물' 얼굴들의 인덱스만 골라낸다.

    - ref_feat이 있으면: 기준 사진과 닮은 것만 (수동 앵커)
    - 없으면: 서로 가장 많이 닮은 무리(최대 클러스터)만
      — 검색 결과의 다수는 본인이라는 가정 (합의 필터)
    판별이 불가능하면(전부 제각각) 전체를 유지해 수집이 멈추지 않게 한다.
    """
    n = len(feats)
    if n == 0:
        return []
    if ref_feat is not None:
        return [i for i in range(n) if cosine(ref_feat, feats[i]) >= thr]
    if n <= 2:
        return list(range(n))
    sims = [[cosine(feats[i], feats[j]) for j in range(n)] for i in range(n)]
    counts = [sum(1 for j in range(n) if j != i and sims[i][j] >= thr) for i in range(n)]
    anchor = max(range(n), key=lambda i: counts[i])
    if counts[anchor] == 0:
        return list(range(n))  # 판별 불가 → 전부 유지
    return [i for i in range(n) if i == anchor or sims[anchor][i] >= thr]


BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def fetch_reference(url: str, detector, min_face: int):
    """기준 사진 URL을 내려받아 얼굴 크롭을 반환 (실패 시 None)."""
    import urllib.request

    import cv2
    import numpy as np

    try:
        req = urllib.request.Request(url, headers={"User-Agent": BROWSER_UA})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = r.read()
        img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            return None
        if detector is None:
            return img
        # 기준 사진에서 얼굴을 못 찾으면(로고/앨범커버 등) 앵커로 쓰지 않는다
        # — 엉뚱한 앵커는 후보 전원을 오판해 전멸시키기 때문
        return crop_main_face(img, detector, min_face // 2)
    except Exception as e:
        print(f"   ⚠️ 기준 사진 로드 실패({e}) — 합의 필터로 대체")
        return None


def wiki_reference_url(name: str) -> str | None:
    """한국어 위키백과 공식 API에서 인물 대표 이미지 URL을 찾는다."""
    import json
    import urllib.parse
    import urllib.request

    params = urllib.parse.urlencode({
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": name, "gsrlimit": "3",
        "prop": "pageimages", "piprop": "thumbnail", "pithumbsize": "600",
    })
    try:
        req = urllib.request.Request(
            f"https://ko.wikipedia.org/w/api.php?{params}",
            headers={"User-Agent": "face-mbti-collector/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.load(r)
        pages = (data.get("query") or {}).get("pages") or {}
        for p in sorted(pages.values(), key=lambda x: x.get("index", 99)):
            thumb = (p.get("thumbnail") or {}).get("source")
            if thumb:
                return thumb
    except Exception:
        pass
    return None


def namu_reference_url(name: str, base: str = "https://namu.wiki",
                       img_pattern: str = "namu.wiki/i/") -> str | None:
    """나무위키 문서에서 프로필(첫 본문) 이미지 URL을 찾는다. Playwright 필요."""
    import os
    import urllib.parse

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    try:
        with sync_playwright() as p:
            exe = os.environ.get("FACE_MBTI_CHROMIUM")  # 테스트용 오버라이드
            browser = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
            page = browser.new_page(user_agent=BROWSER_UA)
            page.goto(f"{base}/w/{urllib.parse.quote(name)}",
                      timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)  # 렌더링 대기
            src = page.evaluate(
                """(pat) => {
                    for (const im of document.querySelectorAll('img')) {
                        const s = im.currentSrc || im.src || '';
                        if (s.includes(pat) && im.naturalWidth >= 150 && im.naturalHeight >= 150)
                            return s;
                    }
                    return null;
                }""", img_pattern)
            browser.close()
            return src
    except Exception as e:
        print(f"   ⚠️ 나무위키 조회 실패({e})")
        return None


def auto_reference_url(name: str) -> tuple[str | None, str]:
    """기준 사진 URL 자동 탐색: 위키백과 → 나무위키 순. (url, 출처이름) 반환."""
    url = wiki_reference_url(name)
    if url:
        return url, "위키백과"
    url = namu_reference_url(name)
    if url:
        return url, "나무위키"
    return None, "합의 필터"


def make_detector():
    """OpenCV 버전에 맞는 얼굴 검출기를 만든다.
    - OpenCV 4.x: haar cascade (내장, 다운로드 불필요)
    - OpenCV 5.x: YuNet (최초 1회 모델 자동 다운로드, 더 정확함)
    """
    import cv2

    if hasattr(cv2, "CascadeClassifier"):
        cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        if cascade.empty():
            sys.exit("얼굴 검출기 로드 실패 — opencv-python 설치를 확인해주세요")
        return ("haar", cascade)

    # OpenCV 5.x: YuNet 모델 확보
    model_path = Path(__file__).resolve().parent / ".cache" / "yunet.onnx"
    if not model_path.exists():
        print("  YuNet 얼굴 검출 모델 다운로드 중 (최초 1회, 약 230KB)...")
        model_path.parent.mkdir(parents=True, exist_ok=True)
        import urllib.request
        try:
            urllib.request.urlretrieve(YUNET_URL, model_path)
        except Exception as e:
            model_path.unlink(missing_ok=True)
            sys.exit(f"모델 다운로드 실패({e}). 아래 파일을 직접 받아서\n"
                     f"  {model_path}\n에 저장해주세요:\n  {YUNET_URL}\n"
                     f"(또는 --no-crop 으로 크롭 없이 수집할 수 있어요)")
    det = cv2.FaceDetectorYN_create(str(model_path), "", (320, 320), 0.6)
    return ("yunet", det)


def detect_faces(img, detector, min_face: int) -> list[tuple[int, int, int, int]]:
    """이미지의 모든 얼굴 (x, y, w, h) 목록을 반환 (큰 순서)."""
    import cv2

    kind, det = detector
    H, W = img.shape[:2]

    if kind == "haar":
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        found = det.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5,
                                     minSize=(min_face // 2, min_face // 2))
        faces = [tuple(int(v) for v in f) for f in found]
    else:
        # YuNet: 큰 이미지는 축소해서 검출 후 좌표 복원
        scale = min(1.0, 1024 / max(W, H))
        small = cv2.resize(img, (int(W * scale), int(H * scale))) if scale < 1.0 else img
        det.setInputSize((small.shape[1], small.shape[0]))
        _, found = det.detect(small)
        faces = [] if found is None else [
            (int(f[0] / scale), int(f[1] / scale), int(f[2] / scale), int(f[3] / scale))
            for f in found]
    return sorted(faces, key=lambda f: f[2] * f[3], reverse=True)


def detect_largest_face(img, detector, min_face: int):
    """가장 큰 얼굴의 (x, y, w, h)를 반환. 없으면 None."""
    faces = detect_faces(img, detector, min_face)
    return faces[0] if faces else None


def crop_main_face(img, detector, min_face: int, margin: float = 0.35):
    """이미지의 '주인공 얼굴' 하나를 여유를 두고 잘라 반환.

    None을 반환하는 경우: 얼굴 없음 / 너무 작음 / 단체사진
    (두 번째 얼굴이 가장 큰 얼굴의 30% 이상 크기면 누구 얼굴인지
    보장할 수 없어서 통째로 버린다)
    """
    faces = detect_faces(img, detector, min_face)
    if not faces:
        return None
    x, y, w, h = faces[0]
    if min(w, h) < min_face:
        return None
    if len(faces) > 1:
        x2, y2, w2, h2 = faces[1]
        if w2 * h2 >= 0.3 * (w * h):
            return None
    H, W = img.shape[:2]
    mx, my = int(w * margin), int(h * margin)
    x0, y0 = max(0, x - mx), max(0, y - my)
    x1, y1 = min(W, x + w + mx), min(H, y + h + my)
    return img[y0:y1, x0:x1]


# 하위 호환 (기존 이름)
crop_largest_face = crop_main_face


def process_person(mbti: str, name: str, limit: int, dataset: Path,
                   crop: bool, min_face: int,
                   excluded: set[str] | None = None,
                   min_sharpness: float = 40.0,
                   recognizer=None, ref_url: str = "") -> tuple[int, int]:
    """한 인물의 이미지를 다운로드하고 (크롭해서) dataset/<MBTI>/에 저장.

    1) 품질 필터: 얼굴 크롭·단체사진 스킵·흐림 제거·중복/검수 제외
    2) 본인 확인: SFace 임베딩으로 후보들을 대조해 '같은 인물' 무리만 저장
       (celebs.csv에 기준 사진 URL이 있으면 그 사진 기준으로 대조)
    파일명의 사진 지문(md5 앞 8자리)으로 관리자 페이지의 제외 목록과 연동된다.
    """
    import cv2

    excluded = excluded or set()
    out_dir = dataset / mbti
    out_dir.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^\w가-힣]+", "_", name).strip("_") or "unknown"

    detector = make_detector() if crop else None

    with tempfile.TemporaryDirectory(prefix="collect_") as tmp:
        tmp_dir = Path(tmp)
        downloaded = download_images(name, limit, tmp_dir)

        # 1단계: 품질 필터를 통과한 후보 수집
        candidates: list[tuple] = []  # (img, digest, bytes)
        seen: set[str] = set()
        for src in sorted(tmp_dir.iterdir()):
            if src.suffix.lower() not in IMG_EXTS:
                continue
            img = cv2.imread(str(src))
            if img is None:
                continue
            if crop:
                face = crop_main_face(img, detector, min_face)
                if face is None:  # 얼굴 없음 / 너무 작음 / 단체사진
                    continue
                img = face
            if min(img.shape[:2]) < min_face:
                continue
            # 흐릿한 사진 제거 (라플라시안 분산이 낮으면 초점이 나간 사진)
            if min_sharpness > 0:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                if cv2.Laplacian(gray, cv2.CV_64F).var() < min_sharpness:
                    continue
            ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 92])
            if not ok:
                continue
            digest = hashlib.md5(buf.tobytes()).hexdigest()
            if digest in excluded or digest in seen:  # 검수 제외분/중복 스킵
                continue
            seen.add(digest)
            candidates.append((img, digest, buf.tobytes()))

        # 2단계: 본인 확인 (같은 인물 무리만 남김)
        if recognizer is not None and len(candidates) >= 3:
            ref_feat = None
            ref_src = "합의 필터"
            if not ref_url:  # 기준 사진 자동 탐색 (위키백과 → 나무위키)
                ref_url, ref_src = auto_reference_url(name)
            elif ref_url:
                ref_src = "CSV 지정"
            if ref_url:
                ref_img = fetch_reference(ref_url, detector, min_face)
                if ref_img is not None:
                    ref_feat = face_feature(recognizer, ref_img)
            feats = [face_feature(recognizer, c[0]) for c in candidates]
            keep = identity_filter(feats, ref_feat, thr=0.30)
            src_note = ref_src if ref_feat is not None else "합의 필터"
            if ref_feat is not None and len(keep) == 0:
                # 후보 전멸은 대부분 앵커(기준 사진)가 잘못된 경우 —
                # 진짜 사진까지 다 버리느니 합의 필터로 재시도
                print("   ⚠️ 기준 사진과 일치하는 후보가 없어요 — 합의 필터로 재시도")
                keep = identity_filter(feats, None, thr=0.30)
                src_note = "합의 필터(폴백)"
            print(f"   🧑‍🤝‍🧑 본인 확인({src_note}): 후보 {len(candidates)}장 중 "
                  f"{len(candidates) - len(keep)}장 제외")
            candidates = [candidates[i] for i in keep]

        saved = 0
        for img, digest, data in candidates[:limit]:
            saved += 1
            (out_dir / f"{safe}_{digest[:8]}.jpg").write_bytes(data)
    return downloaded, saved


def main() -> None:
    ap = argparse.ArgumentParser(
        description="티처블 머신 학습용 연예인 얼굴 데이터 수집기",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="예: python tools/collect_faces.py --limit 40 --only ENFP INFP")
    ap.add_argument("--csv", type=Path, default=ROOT / "tools" / "celebs.csv",
                    help="MBTI,이름 목록 파일 (기본: tools/celebs.csv)")
    ap.add_argument("--out", type=Path, default=ROOT / "dataset",
                    help="저장 폴더 (기본: dataset/)")
    ap.add_argument("--limit", type=int, default=30, help="인물당 다운로드 장수 (기본 30)")
    ap.add_argument("--only", nargs="*", metavar="MBTI",
                    help="이 유형들만 수집 (예: --only ENFP ISTJ)")
    ap.add_argument("--no-crop", action="store_true", help="얼굴 크롭 없이 원본 저장")
    ap.add_argument("--min-face", type=int, default=120,
                    help="이보다 작은 얼굴/이미지는 버림 (기본 120px)")
    ap.add_argument("--min-sharpness", type=float, default=40.0,
                    help="흐릿한 사진 버림 기준 (라플라시안 분산, 0이면 끔)")
    ap.add_argument("--no-verify", action="store_true",
                    help="본인 확인(얼굴 대조) 필터 끄기")
    ap.add_argument("--dry-run", action="store_true", help="다운로드 없이 목록만 확인")
    args = ap.parse_args()

    if not args.csv.exists():
        sys.exit(f"목록 파일이 없어요: {args.csv}\n"
                 f"tools/celebs.csv 를 참고해서 만들어주세요 (형식: MBTI,이름)")

    only = {t.strip().upper() for t in args.only} if args.only else None
    if only:
        bad = [t for t in only if not MBTI_RE.match(t)]
        if bad:
            sys.exit(f"--only 값이 MBTI 형식이 아니에요: {bad}")

    celebs = load_celebs(args.csv, only)
    if not celebs:
        sys.exit("수집할 인물이 없어요. CSV 내용을 확인해주세요!")

    by_type: dict[str, list[str]] = {}
    for mbti, name, _ref in celebs:
        by_type.setdefault(mbti, []).append(name)

    print(f"📋 수집 대상: {len(celebs)}명 / {len(by_type)}개 유형")
    for mbti in sorted(by_type):
        print(f"   {mbti}: {', '.join(by_type[mbti])}")

    if args.dry_run:
        print("\n(--dry-run: 여기서 종료)")
        return

    try:
        import cv2  # noqa: F401
        import icrawler  # noqa: F401
    except ImportError as e:
        sys.exit(f"\n필요한 패키지가 없어요: {e.name}\n"
                 f"먼저 실행해주세요:  pip install icrawler opencv-python")

    excluded = load_excluded()
    if excluded:
        print(f"🚫 검수 제외 목록: {len(excluded)}장 (tools/excluded.txt)")

    recognizer = None if args.no_verify else make_recognizer()
    if recognizer is not None:
        print("🧑‍🤝‍🧑 본인 확인 필터 켜짐 (엉뚱한 인물 사진 자동 제거)")

    total_saved = 0
    for i, (mbti, name, ref_url) in enumerate(celebs, 1):
        print(f"\n[{i}/{len(celebs)}] {mbti} · {name} 수집 중..."
              + (" (기준 사진 사용)" if ref_url else ""))
        try:
            downloaded, saved = process_person(
                mbti, name, args.limit, args.out, not args.no_crop, args.min_face,
                excluded=excluded, min_sharpness=args.min_sharpness,
                recognizer=recognizer, ref_url=ref_url)
        except Exception as e:  # 한 명 실패해도 계속
            print(f"   ⚠️  실패: {e}")
            continue
        total_saved += saved
        print(f"   다운로드 {downloaded}장 → 얼굴 저장 {saved}장  ({args.out / mbti})")

    print(f"\n✅ 완료! 총 {total_saved}장 저장 → {args.out}")
    print("다음 단계:")
    print("  1. 폴더를 열어 잘못 잡힌 사진(다른 사람/뒷모습 등)을 지워주세요")
    print("  2. 유형별 장수를 비슷하게 맞춰주세요 (한쪽 쏠림 방지)")
    print("  3. 티처블 머신에 클래스별로 업로드 → 학습 → TF.js 내보내기 → models/tm/에 배치!")


if __name__ == "__main__":
    main()
