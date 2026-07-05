#!/usr/bin/env python3
"""dataset/ 폴더로 MBTI 얼굴 분류 모델 학습 → models/tm/ 에 내보내기 🎓

collect_faces.py 로 모은 dataset/<MBTI>/사진들 을 MobileNetV2 전이학습으로
분류 모델을 만들고, 앱이 읽는 티처블 머신과 동일한 형식
(model.json / weights.bin / metadata.json)으로 내보냅니다.
→ 내보낸 뒤 커밋/배포하면 앱이 자동으로 이 모델을 사용해요.

준비:
    pip install tensorflow-cpu==2.15.1 tensorflowjs==4.17.0 numpy==1.26.4

사용법:
    python tools/train_model.py                    # dataset/ → models/tm/
    python tools/train_model.py --epochs 15
    python tools/train_model.py --data mydata --out models/tm

폴더 구조 (클래스 이름 = MBTI 4글자):
    dataset/
    ├── ENFP/ *.jpg
    ├── ISTJ/ *.jpg
    └── ...   (2개 유형 이상, 유형당 최소 10장 권장)
"""

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

MBTI_RE = re.compile(r"^[EI][SN][TF][JP]$")
ROOT = Path(__file__).resolve().parent.parent
IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}
IMG_SIZE = 224


def find_classes(data_dir: Path, min_images: int) -> list[str]:
    labels = []
    for d in sorted(data_dir.iterdir()):
        if not d.is_dir():
            continue
        name = d.name.upper()
        n = sum(1 for p in d.iterdir() if p.suffix.lower() in IMG_EXTS)
        if not MBTI_RE.match(name):
            print(f"  [무시] {d.name}/ — 폴더 이름이 MBTI 4글자가 아니에요")
            continue
        if n < min_images:
            print(f"  [무시] {name}/ — 사진이 {n}장뿐이에요 (최소 {min_images}장)")
            continue
        labels.append(d.name)
        print(f"  ✓ {name}: {n}장")
    return labels


def build_model(n_classes: int, alpha: float, pretrained: bool):
    import tensorflow as tf

    # 앱(tmPredict)이 픽셀을 [-1, 1]로 넣어주므로 모델도 그 범위를 입력으로 받음
    base = tf.keras.applications.MobileNetV2(
        input_shape=(IMG_SIZE, IMG_SIZE, 3),
        alpha=alpha,
        include_top=False,
        pooling="avg",
        weights="imagenet" if pretrained else None,
    )
    base.trainable = False

    inputs = tf.keras.Input(shape=(IMG_SIZE, IMG_SIZE, 3))
    x = base(inputs, training=False)
    x = tf.keras.layers.Dropout(0.25)(x)
    outputs = tf.keras.layers.Dense(n_classes, activation="softmax")(x)
    model = tf.keras.Model(inputs, outputs)
    model.compile(
        optimizer=tf.keras.optimizers.Adam(1e-3),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model


def load_datasets(data_dir: Path, labels: list[str], batch: int, val_split: float, seed: int):
    import tempfile

    import tensorflow as tf

    # keras는 class_names가 하위 폴더 전체와 일치해야 함 —
    # 사진이 부족해 제외된 유형 폴더가 섞여 있으면 거부하므로,
    # 유효한 유형 폴더만 복사한 스테이징 디렉터리에서 학습한다.
    staging = Path(tempfile.mkdtemp(prefix="train_ds_"))
    for label in labels:
        dst = staging / label
        dst.mkdir()
        for p in (data_dir / label).iterdir():
            if p.suffix.lower() in IMG_EXTS:
                shutil.copy2(p, dst / p.name)

    common = dict(
        directory=str(staging),
        labels="inferred",
        label_mode="int",
        class_names=labels,
        image_size=(IMG_SIZE, IMG_SIZE),
        batch_size=batch,
        seed=seed,
    )
    train = tf.keras.utils.image_dataset_from_directory(
        validation_split=val_split, subset="training", shuffle=True, **common)
    val = tf.keras.utils.image_dataset_from_directory(
        validation_split=val_split, subset="validation", shuffle=False, **common)

    # 증강(좌우반전) + [-1,1] 정규화는 데이터 파이프라인에서 (내보내는 모델은 깔끔하게)
    flip = tf.keras.layers.RandomFlip("horizontal", seed=seed)
    norm = lambda x: (x / 127.5) - 1.0
    train = train.map(lambda x, y: (norm(flip(x, training=True)), y)).prefetch(2)
    val = val.map(lambda x, y: (norm(x), y)).prefetch(2)
    return train, val


def export_tfjs(model, labels: list[str], out_dir: Path) -> None:
    import tensorflowjs as tfjs

    if out_dir.exists():
        for p in out_dir.glob("*.bin"):
            p.unlink()
    out_dir.mkdir(parents=True, exist_ok=True)
    tfjs.converters.save_keras_model(model, str(out_dir))

    # 앱/티처블머신 호환 metadata.json
    from datetime import datetime, timezone
    (out_dir / "metadata.json").write_text(json.dumps({
        "tfjsVersion": "4.17.0",
        "packageName": "face-mbti/train_model",
        "modelName": "face-mbti",
        "imageSize": IMG_SIZE,
        "trainedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "labels": labels,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    # weights 파일 이름을 weights.bin 하나로 통일 (셔딩된 경우 병합)
    manifest_path = out_dir / "model.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    shard_paths = manifest["weightsManifest"][0]["paths"]
    merged = out_dir / "weights.bin"
    with open(merged, "wb") as w:
        for sp in shard_paths:
            w.write((out_dir / sp).read_bytes())
            if sp != "weights.bin":
                (out_dir / sp).unlink()
    manifest["weightsManifest"][0]["paths"] = ["weights.bin"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="MBTI 얼굴 분류 모델 학습 → TF.js 내보내기")
    ap.add_argument("--data", type=Path, default=ROOT / "dataset")
    ap.add_argument("--out", type=Path, default=ROOT / "models" / "tm")
    ap.add_argument("--epochs", type=int, default=12)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--alpha", type=float, default=0.35,
                    help="MobileNetV2 크기 (0.35=가볍고 빠름/기본, 1.0=크고 정확)")
    ap.add_argument("--val-split", type=float, default=0.15)
    ap.add_argument("--min-images", type=int, default=10, help="유형당 최소 장수")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--no-pretrained", action="store_true",
                    help="ImageNet 가중치 없이 학습 (테스트용)")
    args = ap.parse_args()

    if not args.data.exists():
        sys.exit(f"데이터 폴더가 없어요: {args.data}\n"
                 f"먼저 수집해주세요:  python tools/collect_faces.py")

    print(f"📁 데이터 확인: {args.data}")
    labels = find_classes(args.data, args.min_images)
    if len(labels) < 2:
        sys.exit("학습하려면 사진이 충분한 유형 폴더가 2개 이상 필요해요!")

    print(f"\n🧠 모델 구성 (MobileNetV2 x{args.alpha}, 클래스 {len(labels)}개)")
    import tensorflow as tf  # noqa: F401  (여기서 실패하면 안내)
    model = build_model(len(labels), args.alpha, not args.no_pretrained)
    train, val = load_datasets(args.data, labels, args.batch, args.val_split, args.seed)

    print(f"\n🏃 학습 시작 ({args.epochs} epochs)")
    model.fit(train, validation_data=val, epochs=args.epochs, verbose=2)

    loss, acc = model.evaluate(val, verbose=0)
    print(f"\n📊 검증 정확도: {acc:.1%} (찍기 기준선: {1/len(labels):.1%})")

    print(f"💾 내보내기: {args.out}")
    export_tfjs(model, [l.upper() for l in labels], args.out)
    for p in sorted(args.out.iterdir()):
        print(f"   {p.name}  ({p.stat().st_size:,} bytes)")
    print("\n✅ 완료! models/tm/ 을 커밋·배포하면 앱이 자동으로 이 모델을 사용해요.")


if __name__ == "__main__":
    main()
