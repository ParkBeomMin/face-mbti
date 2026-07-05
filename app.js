/* ============================================================
 *  실시간 얼굴 MBTI · 카메라 + 얼굴 인식 루프
 * ============================================================ */

const MODEL_URL = "./models";

const video = document.getElementById("video");
const overlay = document.getElementById("overlay");
const ctx = overlay.getContext("2d");

const startHint = document.getElementById("startHint");
const startBtn = document.getElementById("startBtn");
const loading = document.getElementById("loading");
const resultCard = document.getElementById("resultCard");
const elEmoji = document.getElementById("resultEmoji");
const elType = document.getElementById("resultType");
const elNick = document.getElementById("resultNick");
const elDesc = document.getElementById("resultDesc");
const elBars = document.getElementById("bars");

const { MBTI_INFO, inferMbti, scoresToType } = window.MBTI;

// 부드럽게 흔들림을 줄이기 위한 지수이동평균 상태
let smooth = null;          // {ei, sn, tf, jp}
const ALPHA = 0.14;         // 낮을수록 더 부드럽게(천천히) 변함
let lastType = null;
let running = false;

/* ---------- 모델 로드 ---------- */
async function loadModels() {
  await Promise.all([
    faceapi.nets.tinyFaceDetector.loadFromUri(MODEL_URL),
    faceapi.nets.faceLandmark68Net.loadFromUri(MODEL_URL),
    faceapi.nets.faceExpressionNet.loadFromUri(MODEL_URL),
  ]);
}

/* ---------- 카메라 시작 ---------- */
async function startCamera() {
  const stream = await navigator.mediaDevices.getUserMedia({
    video: { facingMode: "user", width: { ideal: 640 }, height: { ideal: 480 } },
    audio: false,
  });
  video.srcObject = stream;
  await new Promise((res) => (video.onloadedmetadata = res));
  await video.play();
  overlay.width = video.videoWidth;
  overlay.height = video.videoHeight;
}

/* ---------- 시작 버튼 ---------- */
startBtn.addEventListener("click", async () => {
  startHint.hidden = true;
  loading.hidden = false;
  try {
    await loadModels();
    await startCamera();
  } catch (err) {
    loading.hidden = true;
    startHint.hidden = false;
    alert("카메라를 켤 수 없어요 😢\n브라우저의 카메라 권한을 허용했는지 확인해주세요.\n\n" + err.message);
    return;
  }
  loading.hidden = true;
  running = true;
  requestAnimationFrame(loop);
});

/* ---------- 메인 루프 ---------- */
const detectorOptions = new faceapi.TinyFaceDetectorOptions({ inputSize: 320, scoreThreshold: 0.4 });
let busy = false;
let latestDet = null;

async function loop() {
  if (!running) return;
  if (!busy) {
    busy = true;
    faceapi
      .detectSingleFace(video, detectorOptions)
      .withFaceLandmarks()
      .withFaceExpressions()
      .then((det) => { latestDet = det || null; })
      .catch(() => { latestDet = null; })
      .finally(() => { busy = false; });
  }
  render(latestDet);
  requestAnimationFrame(loop);
}

/* ---------- 화면 그리기 ---------- */
function render(det) {
  ctx.clearRect(0, 0, overlay.width, overlay.height);

  if (!det) {
    // 얼굴이 사라지면 결과는 마지막 상태 유지, 오버레이만 지움
    return;
  }

  // 4축 점수 계산 + 부드럽게
  const raw = inferMbti(det);
  if (!smooth) smooth = { ...raw };
  else for (const k of ["ei", "sn", "tf", "jp"]) smooth[k] += ALPHA * (raw[k] - smooth[k]);

  const type = scoresToType(smooth);
  const info = MBTI_INFO[type];

  drawFaceLabel(det, type, info);
  updateCard(type, info, smooth);
}

/** 얼굴 박스 + 귀여운 말풍선 라벨 */
function drawFaceLabel(det, type, info) {
  const W = overlay.width;
  const box = det.detection.box;
  // 비디오는 CSS로 좌우반전 → 캔버스 좌표도 x를 반전
  const x = W - (box.x + box.width);
  const y = box.y;
  const w = box.width;
  const h = box.height;
  const color = info.color;

  // 둥근 얼굴 테두리 (점선 느낌)
  ctx.save();
  ctx.lineWidth = Math.max(3, W * 0.006);
  ctx.strokeStyle = color;
  ctx.setLineDash([W * 0.03, W * 0.02]);
  roundRect(x, y, w, h, Math.min(w, h) * 0.28);
  ctx.stroke();
  ctx.restore();

  // 말풍선 라벨 (얼굴 위쪽)
  const label = `${info.emoji} ${type}`;
  const fs = Math.max(22, w * 0.16);
  ctx.font = `${fs}px "Jua", system-ui, sans-serif`;
  const tw = ctx.measureText(label).width;
  const padX = fs * 0.5;
  const padY = fs * 0.32;
  const bw = tw + padX * 2;
  const bh = fs + padY * 2;
  let bx = x + w / 2 - bw / 2;
  let by = y - bh - fs * 0.5;
  if (by < 6) by = y + h + fs * 0.4; // 위 공간 없으면 아래로
  bx = Math.max(6, Math.min(bx, W - bw - 6));

  // 풍선 배경
  ctx.save();
  ctx.fillStyle = "rgba(255,255,255,0.92)";
  ctx.shadowColor = "rgba(0,0,0,0.15)";
  ctx.shadowBlur = 10;
  ctx.shadowOffsetY = 4;
  roundRect(bx, by, bw, bh, bh * 0.5);
  ctx.fill();
  ctx.restore();

  // 풍선 테두리
  ctx.save();
  ctx.lineWidth = Math.max(2, W * 0.004);
  ctx.strokeStyle = color;
  roundRect(bx, by, bw, bh, bh * 0.5);
  ctx.stroke();
  ctx.restore();

  // 텍스트
  ctx.fillStyle = "#5a4a63";
  ctx.textBaseline = "middle";
  ctx.textAlign = "center";
  ctx.fillText(label, bx + bw / 2, by + bh / 2 + fs * 0.03);
}

function roundRect(x, y, w, h, r) {
  r = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

/* ---------- 결과 카드 ---------- */
const AXES = [
  { key: "ei", left: "I 내향", right: "외향 E", cls: "ei" },
  { key: "sn", left: "S 감각", right: "직관 N", cls: "sn" },
  { key: "tf", left: "T 사고", right: "감정 F", cls: "tf" },
  { key: "jp", left: "J 계획", right: "인식 P", cls: "jp" },
];

function updateCard(type, info, s) {
  if (resultCard.hidden) resultCard.hidden = false;

  if (type !== lastType) {
    lastType = type;
    elEmoji.textContent = info.emoji;
    elType.textContent = type;
    elNick.textContent = info.nick;
    elDesc.textContent = info.desc;
    elType.style.color = info.color;
    // 카드 살짝 튕기기
    resultCard.style.animation = "none";
    void resultCard.offsetWidth;
    resultCard.style.animation = "cardIn .4s ease";
  }

  if (!elBars.children.length) {
    for (const a of AXES) {
      const row = document.createElement("div");
      row.className = "bar-row";
      row.innerHTML =
        `<div class="bar-label"><span>${a.left}</span><span>${a.right}</span></div>` +
        `<div class="bar-track"><div class="bar-fill ${a.cls}" data-k="${a.key}"></div></div>`;
      elBars.appendChild(row);
    }
  }
  for (const a of AXES) {
    const fill = elBars.querySelector(`.bar-fill[data-k="${a.key}"]`);
    fill.style.width = (s[a.key] * 100).toFixed(0) + "%";
  }
}

/* 창 크기 바뀌어도 캔버스 해상도 유지 (비디오 픽셀 기준) */
window.addEventListener("resize", () => {
  if (video.videoWidth) {
    overlay.width = video.videoWidth;
    overlay.height = video.videoHeight;
  }
});
