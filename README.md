# 몽글몽글 얼굴 MBTI 🫧

웹캠으로 얼굴을 비추면 **실시간으로 얼굴 위에 MBTI를 아기자기하게 표시**해주는 웹앱이에요.
표정과 이목구비를 분석해서 성격 유형을 재미있게 추측하고, 파스텔톤 말풍선으로 얼굴 위에 띄워줍니다.

<img src="https://img.shields.io/badge/재미로-보는%20관상%20MBTI-ff8fbf" />

## ✨ 특징

- 🎥 **실시간 얼굴 인식** — 브라우저에서 [face-api.js](https://github.com/vladmandic/face-api)로 얼굴/표정/68개 랜드마크를 잡아요.
- 🫧 **얼굴 위 라이브 오버레이** — 인식된 얼굴 주변에 둥근 테두리 + 귀여운 MBTI 말풍선이 따라다녀요.
- 🔮 **5초 측정 → 결과 확정** — 얼굴이 보이는 동안 5초간 관상을 읽고, 결과가 정해지면 컨페티와 함께 고정돼요. "다시 측정하기"로 언제든 재도전!
- 🌸 **아기자기한 UI** — 둥근 한글 폰트(Jua/Gaegu), 파스텔 그라데이션, 둥실둥실 떠다니는 구름/반짝이.
- 📊 **4축 성향 바** — E/I · S/N · T/F · J/P 를 실시간 게이지로 보여줘요.
- 🔒 **프라이버시** — 모든 처리는 브라우저 안에서만 일어나고, 영상·사진은 어디에도 저장/전송되지 않아요.

## 🚀 실행 방법

카메라(`getUserMedia`)는 보안 컨텍스트가 필요해서 `file://` 로 열면 동작하지 않아요.
간단한 로컬 서버로 띄워주세요.

```bash
# 방법 1) Python
python3 -m http.server 8000

# 방법 2) Node
npx serve .
```

그다음 브라우저에서 <http://localhost:8000> 접속 → **카메라 켜기** 버튼을 누르면 끝!
(배포 시에도 `https://` 환경이어야 카메라가 켜집니다. GitHub Pages 등에서 바로 동작해요.)

## 🧠 MBTI는 어떻게 정해지나요?

`mbti.js` 의 `inferMbti()` 함수가 face-api의 표정/랜드마크 결과를 받아
아래처럼 **4개 축의 점수(0~1)** 를 계산해요.

| 축 | 1에 가까워지는 신호 |
|----|----------------------|
| **E**/I | 미소·놀람·입꼬리 상승·입 벌어짐 (표현이 풍부할수록 E) |
| S/**N** | 눈썹 올라감·놀란 표정 (개방적일수록 N) |
| T/**F** | 미소·슬픔·두려움 등 감정 표현 (무표정/화남은 T) |
| J/**P** | 입 벌어짐·좌우 비대칭·큰 눈 (즉흥적일수록 P) |

얼굴이 보이는 동안 **5초간** 여러 프레임의 점수를 지수이동평균(EMA)으로 부드럽게 누적한 뒤, 최종 유형을 **확정(고정)**합니다. 확정 후에는 말풍선이 고정된 유형으로 얼굴을 따라다니고, "다시 측정하기" 버튼으로 재측정할 수 있어요.

> ⚠️ **재미로만 즐겨주세요!** 얼굴로 성격을 판별하는 과학적 근거는 없어요. 관상 놀이용 앱입니다 🎈

## 🤖 구글 티처블 머신으로 나만의 모델 만들기

기본 관상 로직 대신, [구글 티처블 머신](https://teachablemachine.withgoogle.com/)에서 직접 학습한
모델을 쓸 수 있어요. **모델 파일만 넣으면 앱이 자동으로 인식**하고, 화면 위에 `🤖 나만의 학습 모델 사용 중` 배지가 떠요.

### 📋 연예인 MBTI 자동 수집 (목록 만들기)

인물 이름만 있으면 **Personality Database(커뮤니티 투표) → 나무위키** 순으로 MBTI와 프로필 사진을 자동으로 가져와 `tools/celebs.csv`를 채워줍니다.
프로필 사진 URL은 사진 수집 때 "본인 확인 앵커"로 그대로 쓰여서 일석이조예요.

```bash
# Mac/Linux                              # Windows
./tools/mbti_local.sh                    tools\mbti_local.bat
./tools/mbti_local.sh --names 아이유 카리나   (특정 인물만)
./tools/mbti_local.sh --dry-run          (csv 수정 없이 미리보기)
./tools/mbti_local.sh --source namu      (나무위키만 사용)
```

- 이름 목록은 `tools/seed_names.txt` 에 자유롭게 추가하세요 (나무위키 문서 제목과 같게)
- **전원 최신화**: `./tools/mbti_local.sh --csv-names --update` — celebs.csv의 100명 전원을 PDB/나무위키 실데이터로 갱신
- 기존 celebs.csv 행은 보존돼요 — MBTI가 다르면 알려주기만 하고, 빈 기준 사진 URL만 채웁니다
- 나무위키는 봇 차단이 있어 **내 PC에서 실행**을 추천해요 (CI에서는 실패할 수 있음)

### 📸 PDB 원스톱 데이터셋 (인물·MBTI·사진 한 번에! 추천)

[Personality Database](https://www.personality-database.com/)에서 **인물 + 커뮤니티 투표 MBTI + 프로필 사진**을
한 번에 수집해 바로 학습 가능한 `dataset/`을 만듭니다. 프로필 사진은 **본인임이 보증**되어
본인 확인 필터가 필요 없고, "수백 명 × 1장" 구성이라 모델이 특정 인물이 아닌 유형의 인상을 학습해요.

```bash
# Mac/Linux                                   # Windows
./tools/pdb_dataset_local.sh                  tools\pdb_dataset_local.bat
./tools/pdb_dataset_local.sh --per-type 60    (유형당 최대 인원)
./tools/pdb_dataset_local.sh --queries aespa BTS   (특정 검색어만)
```

- 검색어는 `tools/pdb_queries.txt` (그룹명 위주 — 멤버 전원이 한 번에 나와요) + `celebs.csv`의 인물들
- 수집 후 `dataset/` 검수 → 티처블 머신 업로드 또는 `train_model.py` 로컬 학습 → `models/tm/` 커밋

### 💻 내 PC에서 수집하기 (가장 정확! 추천)

GitHub Actions 러너는 해외 데이터센터 IP라서 한국어 인물 검색 결과가 부정확할 수 있어요.
**내 PC(한국 IP + 진짜 브라우저)에서 수집하면 다음(Daum) 검색이 제대로 동작**해서 품질이 훨씬 좋습니다.

```bash
# Mac/Linux
./tools/collect_local.sh              # 전체 수집
./tools/collect_local.sh --only ENFP  # 특정 유형만

# Windows: tools\collect_local.bat 더블클릭 (또는 터미널에서 옵션과 함께)
```

끝나면 `dataset/` 폴더를 탐색기로 열어 눈으로 검수하고, 둘 중 편한 방법으로 학습하세요:
- **A. 티처블 머신 사이트**에 유형 폴더별로 드래그 업로드 → 학습 → TF.js 내보내기 → 3개 파일을 `models/tm/`에 커밋
- **B. 로컬 학습**: `python tools/train_model.py` → `models/tm/` 커밋

커밋하면 Pages가 재배포되어 앱에 바로 적용돼요. (사진 자체는 절대 커밋하지 마세요 — `dataset/`은 .gitignore에 있어요)

### 0️⃣ 학습 데이터 자동 수집 (동봉된 수집기 사용)

`tools/collect_faces.py` 가 `tools/celebs.csv` 의 "MBTI,연예인" 목록을 읽어
이미지를 검색·다운로드하고 **얼굴만 잘라** 유형별 폴더로 정리해줘요.

```bash
pip install icrawler opencv-python

python tools/collect_faces.py --dry-run        # 수집 대상 확인만
python tools/collect_faces.py                  # 인물당 30장 수집 → dataset/
python tools/collect_faces.py --limit 50       # 인물당 50장
python tools/collect_faces.py --only ENFP ISTJ # 특정 유형만
```

- `tools/celebs.csv` 에 인물을 자유롭게 추가/수정하세요 (한 유형에 여러 명일수록 좋아요)
- **본인 확인 필터** 🧑‍🤝‍🧑: 수집된 얼굴들을 서로 대조해 가장 큰 "같은 인물" 무리만 남겨요.
  더 확실하게 하려면 CSV 3번째 칸에 **기준 사진 URL**(위키 프로필 등)을 넣으세요 — 그 얼굴과 닮은 사진만 수집돼요.
- 수집 후 폴더(또는 관리자 페이지 갤러리)에서 **남은 오염 사진을 지워주세요** — 데이터 품질이 정확도의 90%예요!
- `dataset/` 은 `.gitignore` 에 등록돼 있어 실수로 커밋되지 않아요 (개인 학습용으로만 사용)

### 1️⃣ 학습하기 (코딩 필요 없음, 브라우저에서 끝!)

1. https://teachablemachine.withgoogle.com/train/image 접속 → **이미지 프로젝트(표준 이미지 모델)** 선택
2. 클래스 이름을 **MBTI 4글자**로 지정 — 예: `ENFP`, `INFP`, `ESTJ`... (16개 전부가 아니어도 OK)
3. 각 클래스에 `dataset/<유형>/` 폴더의 사진을 드래그해서 업로드 (클래스당 30~50장 이상, 수량은 비슷하게)
4. **모델 학습시키기** 클릭 → 웹캠 미리보기로 확인
5. **모델 내보내기 → Tensorflow.js 탭 → 다운로드** 선택 → zip 안의 3개 파일 획득

### 🛠 관리자 페이지 — 폰에서 전부 관리하기 (추천!)

**`/admin.html`** 이 관리자 페이지예요. 서버 없이 GitHub Pages + GitHub API로 동작해요.

👉 `https://<계정>.github.io/face-mbti/admin.html`

| 기능 | 설명 |
|---|---|
| 📋 연예인 목록 편집 | celebs.csv를 표로 편집하고 버튼 한 번으로 커밋 |
| 🚀 수집·학습 실행 | 옵션(장수/유형/에폭) 넣고 실행, 진행 상태 실시간 표시 |
| 🖼 사진 검수 갤러리 | 수집된 사진을 유형별로 보고, 클릭으로 🚫 제외 → 다음 수집부터 자동 필터 |
| 🤖 현재 모델 확인 | 적용 중인 모델의 클래스·학습 시각 표시 |

**처음 한 번만**: 쓰기 기능(편집·실행·검수 저장)을 위해
[Fine-grained 토큰](https://github.com/settings/personal-access-tokens/new)을 만들어 페이지에 등록하세요
(face-mbti 저장소만 · Contents / Actions 쓰기 권한). 토큰은 본인 브라우저에만 저장되고, 보기 전용은 토큰 없이도 돼요.

동작 원리: 실행하면 GitHub Actions가 사진 수집 → 얼굴 크롭 → 검수용 저해상 **썸네일을
`dataset-preview` 브랜치에 게시**(갤러리가 이걸 표시) → 모델 학습 → `models/tm/` 자동 커밋 →
Pages 재배포. 사진 원본은 러너와 함께 사라지고 저장소에 커밋되지 않아요.
갤러리에서 제외한 사진은 `tools/excluded.txt`(사진 지문 md5)에 기록되어 다음 수집부터 걸러져요.

> 참고: 검수용 썸네일(128px)은 공개 브랜치에 올라가요. 원치 않으면 관리자 페이지의
> 갤러리 대신 Run 옵션의 `upload_dataset` 아티팩트(3일 보관)로 검수하세요.

이 방식은 티처블 머신 사이트 대신 동봉된 `tools/train_model.py` (MobileNetV2 전이학습)로
학습하지만, **내보내는 형식이 티처블 머신과 동일**해서 앱은 구분 없이 그대로 사용해요.

### 2️⃣ 적용하기

다운받은 3개 파일을 `models/tm/` 폴더에 넣고 배포(또는 새로고침)하면 끝!

```
models/tm/
├── model.json
├── weights.bin
└── metadata.json
```

앱이 시작될 때 `models/tm/metadata.json`을 확인해서, 있으면 얼굴 영역을 224×224로 잘라
학습 모델로 분류하고 클래스 확률을 4축 점수로 변환해요 (예: E점수 = `E***` 클래스들의 확률 합).
파일이 없거나 클래스 이름이 MBTI 형식이 아니면 자동으로 기본 관상 로직을 사용합니다.

> ⚠️ 데이터셋을 만들 때는 **초상권·저작권·개인정보**에 유의하세요. 개인 학습/재미 용도로만 쓰고,
> 사진 자체를 저장소에 올려 배포하는 건 피하는 게 안전해요. (모델 파일에는 사진이 들어있지 않아요)
> 그리고 인터넷에 알려진 연예인 MBTI 라벨 자체가 부정확할 수 있다는 점도 기억해주세요 🎈

## 📁 구조

```
index.html   화면 구조
style.css    아기자기한 스타일
mbti.js      16유형 데이터 + 기본 관상 추론 로직
app.js       카메라 + 얼굴 인식 루프 + 오버레이 렌더링 + 티처블 머신 연동
models/      face-api 모델 가중치
models/tm/   (선택) 티처블 머신 학습 모델을 넣는 곳
vendor/      face-api.js 라이브러리
```

## 🛠 기술

- [@vladmandic/face-api](https://github.com/vladmandic/face-api) (CDN)
- Vanilla JS + Canvas 2D
- Google Fonts (Jua, Gaegu)

---

재미로 보는 얼굴 관상 MBTI 🎀 · Made with 💗
