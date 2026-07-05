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


def load_celebs(csv_path: Path, only: set[str] | None) -> list[tuple[str, str]]:
    """CSV에서 (MBTI, 이름) 목록을 읽는다. 형식: MBTI,이름 (헤더/주석/빈줄 허용)"""
    rows: list[tuple[str, str]] = []
    with open(csv_path, encoding="utf-8") as f:
        for lineno, row in enumerate(csv.reader(f), 1):
            if not row or row[0].strip().startswith("#"):
                continue
            if len(row) < 2:
                print(f"  [무시] {csv_path.name}:{lineno} — 열이 부족해요: {row}")
                continue
            mbti = row[0].strip().upper()
            name = row[1].strip()
            if mbti == "MBTI":  # 헤더
                continue
            if not MBTI_RE.match(mbti):
                print(f"  [무시] {csv_path.name}:{lineno} — MBTI 형식이 아니에요: {mbti!r}")
                continue
            if not name:
                continue
            if only and mbti not in only:
                continue
            rows.append((mbti, name))
    return rows


def download_images(name: str, limit: int, out_dir: Path) -> int:
    """Bing 이미지 검색으로 인물 사진을 out_dir에 다운로드한다."""
    from icrawler.builtin import BingImageCrawler

    crawler = BingImageCrawler(
        storage={"root_dir": str(out_dir)},
        downloader_threads=4,
        log_level=40,  # ERROR만 (조용히)
    )
    # 얼굴이 크게 나오도록 검색어에 '얼굴' 추가 + 인물 필터
    crawler.crawl(
        keyword=f"{name} 얼굴",
        max_num=limit,
        filters={"type": "photo"},
    )
    return sum(1 for p in out_dir.iterdir() if p.suffix.lower() in IMG_EXTS)


YUNET_URL = ("https://github.com/opencv/opencv_zoo/raw/main/models/"
             "face_detection_yunet/face_detection_yunet_2023mar.onnx")


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


def detect_largest_face(img, detector, min_face: int):
    """가장 큰 얼굴의 (x, y, w, h)를 반환. 없으면 None."""
    import cv2

    kind, det = detector
    H, W = img.shape[:2]

    if kind == "haar":
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = det.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5,
                                     minSize=(min_face, min_face))
        if len(faces) == 0:
            return None
        return tuple(int(v) for v in max(faces, key=lambda f: f[2] * f[3]))

    # YuNet: 큰 이미지는 축소해서 검출 후 좌표 복원
    scale = min(1.0, 1024 / max(W, H))
    small = cv2.resize(img, (int(W * scale), int(H * scale))) if scale < 1.0 else img
    det.setInputSize((small.shape[1], small.shape[0]))
    _, faces = det.detect(small)
    if faces is None or len(faces) == 0:
        return None
    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])[:4]
    return (int(x / scale), int(y / scale), int(w / scale), int(h / scale))


def crop_largest_face(img, detector, min_face: int, margin: float = 0.35):
    """이미지에서 가장 큰 얼굴 하나를 여유를 두고 잘라 반환. 없으면 None."""
    found = detect_largest_face(img, detector, min_face)
    if found is None:
        return None
    x, y, w, h = found
    if min(w, h) < min_face:
        return None
    H, W = img.shape[:2]
    mx, my = int(w * margin), int(h * margin)
    x0, y0 = max(0, x - mx), max(0, y - my)
    x1, y1 = min(W, x + w + mx), min(H, y + h + my)
    return img[y0:y1, x0:x1]


def process_person(mbti: str, name: str, limit: int, dataset: Path,
                   crop: bool, min_face: int,
                   excluded: set[str] | None = None) -> tuple[int, int]:
    """한 인물의 이미지를 다운로드하고 (크롭해서) dataset/<MBTI>/에 저장.

    파일명에 사진 지문(md5 앞 8자리)을 붙여서, 관리자 페이지에서 '제외'한
    사진(tools/excluded.txt)은 다음 수집부터 자동으로 걸러진다.
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

        saved = 0
        seen: set[str] = set()
        for src in sorted(tmp_dir.iterdir()):
            if src.suffix.lower() not in IMG_EXTS:
                continue
            img = cv2.imread(str(src))
            if img is None:
                continue
            if crop:
                face = crop_largest_face(img, detector, min_face)
                if face is None:
                    continue
                img = face
            if min(img.shape[:2]) < min_face:
                continue
            ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 92])
            if not ok:
                continue
            digest = hashlib.md5(buf.tobytes()).hexdigest()
            if digest in excluded or digest in seen:  # 검수 제외분/중복 스킵
                continue
            seen.add(digest)
            saved += 1
            (out_dir / f"{safe}_{digest[:8]}.jpg").write_bytes(buf.tobytes())
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
    for mbti, name in celebs:
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

    total_saved = 0
    for i, (mbti, name) in enumerate(celebs, 1):
        print(f"\n[{i}/{len(celebs)}] {mbti} · {name} 수집 중...")
        try:
            downloaded, saved = process_person(
                mbti, name, args.limit, args.out, not args.no_crop, args.min_face,
                excluded=excluded)
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
