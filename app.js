/* ============================================================
 *  실시간 얼굴 MBTI · 카메라 + 얼굴 인식 루프
 *  ------------------------------------------------------------
 *  흐름: 카메라 켜기 → 얼굴이 보이는 동안 5초간 측정(점수 누적)
 *        → 결과 확정(고정) → "다시 측정하기"로 리셋
 * ============================================================ */

const MODEL_URL = "./models";

const video = document.getElementById("video");
const overlay = document.getElementById("overlay");
const ctx = overlay.getContext("2d");

const cameraWrap = document.getElementById("cameraWrap");
const startHint = document.getElementById("startHint");
const startBtn = document.getElementById("startBtn");
const loading = document.getElementById("loading");
const resultCard = document.getElementById("resultCard");
const elEmoji = document.getElementById("resultEmoji");
const elType = document.getElementById("resultType");
const elNick = document.getElementById("resultNick");
const elDesc = document.getElementById("resultDesc");
const elBars = document.getElementById("bars");
const retryBtn = document.getElementById("retryBtn");
const tmBadge = document.getElementById("tmBadge");

const { MBTI_INFO, inferMbti, scoresToType } = window.MBTI;

/* ---------- 상태 ---------- */
const MEASURE_MS = 5000;    // 얼굴이 보이는 동안 이만큼 측정하면 결과 확정
const ALPHA = 0.14;         // EMA 계수: 낮을수록 부드럽게(천천히) 변함

let smooth = null;          // 4축 점수의 지수이동평균 {ei, sn, tf, jp}
let running = false;
let busy = false;
let latestDet = null;

let measured = 0;           // 얼굴이 보인 누적 시간(ms)
let lastTs = null;          // 직전 프레임 타임스탬프 (얼굴 사라지면 null)
let locked = false;         // 결과 확정 여부
let lockedType = null;      // 확정된 타입 (예: "ENFP")
let cardMode = null;        // 카드 표시 상태: "measuring" | 타입 문자열

/* ---------- 티처블 머신(선택) ----------
 * models/tm/ 에 티처블 머신 TensorFlow.js 내보내기 3파일
 * (model.json, weights.bin, metadata.json)을 넣으면 자동으로 사용합니다.
 * 클래스 이름은 MBTI 4글자(예: ENFP)여야 해요. 없으면 기본 관상 로직 사용. */
let tmModel = null;         // { model, labels }
let tmAxes = null;          // 최근 TM 추론 결과 {ei, sn, tf, jp}
const tmCanvas = document.createElement("canvas");
tmCanvas.width = tmCanvas.height = 224;
const tmCtx = tmCanvas.getContext("2d", { willReadFrequently: true });

async function tryLoadTmModel() {
  try {
    const res = await fetch("./models/tm/metadata.json");
    if (!res.ok) return null;
    const meta = await res.json();
    const labels = (meta.labels || []).map((s) => String(s).trim().toUpperCase());
    if (labels.length < 2 || !labels.every((l) => /^[EI][SN][TF][JP]$/.test(l))) {
      console.warn("[TM] 클래스 이름이 MBTI 4글자가 아니에요. 기본 로직을 사용합니다:", labels);
      return null;
    }
    const model = await faceapi.tf.loadLayersModel("./models/tm/model.json");
    console.log("[TM] 나만의 학습 모델 로드 완료! 클래스:", labels.join(", "));
    return { model, labels };
  } catch (e) {
    console.warn("[TM] 학습 모델 로드 실패 → 기본 관상 로직 사용:", e.message);
    return null;
  }
}

/** 얼굴 영역을 224x224로 잘라 TM 모델로 추론 → 4축 점수 */
async function tmPredict(det) {
  const b = det.detection.box;
  const m = 0.25; // 박스 주변 여유
  const sx = Math.max(0, b.x - b.width * m);
  const sy = Math.max(0, b.y - b.height * m);
  const sw = Math.min(video.videoWidth - sx, b.width * (1 + 2 * m));
  const sh = Math.min(video.videoHeight - sy, b.height * (1 + 2 * m));
  tmCtx.drawImage(video, sx, sy, sw, sh, 0, 0, 224, 224);

  const tfjs = faceapi.tf;
  const out = tfjs.tidy(() =>
    tmModel.model.predict(
      tfjs.browser.fromPixels(tmCanvas).toFloat().div(127.5).sub(1).expandDims(0)
    )
  );
  const probs = await out.data();
  out.dispose();

  // 각 축의 점수 = 해당 글자를 가진 클래스들의 확률 합 (예: ei = E***들의 합)
  const axes = { ei: 0, sn: 0, tf: 0, jp: 0 };
  tmModel.labels.forEach((l, i) => {
    const p = probs[i] || 0;
    if (l[0] === "E") axes.ei += p;
    if (l[1] === "N") axes.sn += p;
    if (l[2] === "F") axes.tf += p;
    if (l[3] === "P") axes.jp += p;
  });
  return axes;
}

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
    [, tmModel] = await Promise.all([loadModels(), tryLoadTmModel()]);
    tmBadge.hidden = !tmModel;
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

/* ---------- 다시 측정하기 ---------- */
retryBtn.addEventListener("click", () => {
  smooth = null;
  measured = 0;
  lastTs = null;
  locked = false;
  lockedType = null;
  cardMode = null;
  tmAxes = null;
  retryBtn.hidden = true;
});

/* ---------- 메인 루프 ---------- */
const detectorOptions = new faceapi.TinyFaceDetectorOptions({ inputSize: 320, scoreThreshold: 0.4 });

function loop(ts) {
  if (!running) return;
  if (!busy) {
    busy = true;
    faceapi
      .detectSingleFace(video, detectorOptions)
      .withFaceLandmarks()
      .withFaceExpressions()
      .then(async (det) => {
        latestDet = det || null;
        if (det && tmModel && !locked) {
          try { tmAxes = await tmPredict(det); } catch (e) { /* TM 실패 시 기본 로직으로 */ }
        }
      })
      .catch(() => { latestDet = null; })
      .finally(() => { busy = false; });
  }
  render(latestDet, ts);
  requestAnimationFrame(loop);
}

/* ---------- 프레임 처리 ---------- */
function render(det, ts) {
  ctx.clearRect(0, 0, overlay.width, overlay.height);

  // 결과가 확정된 뒤에는 점수 갱신 없이 고정된 타입만 따라다니게
  if (locked) {
    if (det) {
      const info = MBTI_INFO[lockedType];
      drawBubble(det, `${info.emoji} ${lockedType}`, info.color);
    }
    return;
  }

  if (!det) {
    lastTs = null; // 얼굴이 사라지면 측정 일시정지 (누적 시간은 유지)
    return;
  }

  if (lastTs !== null) measured = Math.min(MEASURE_MS, measured + (ts - lastTs));
  lastTs = ts;

  // 4축 점수 계산 + 부드럽게 누적 (학습 모델이 있으면 그 결과를 우선 사용)
  const raw = (tmModel && tmAxes) ? tmAxes : inferMbti(det);
  if (!smooth) smooth = { ...raw };
  else for (const k of ["ei", "sn", "tf", "jp"]) smooth[k] += ALPHA * (raw[k] - smooth[k]);

  const progress = measured / MEASURE_MS;

  if (progress < 1) {
    drawBubble(det, `🔮 두근두근 ${Math.round(progress * 100)}%`, "#c9b6ff");
    updateMeasuringCard(progress);
  } else {
    // 측정 완료 → 결과 확정!
    locked = true;
    lockedType = scoresToType(smooth);
    const info = MBTI_INFO[lockedType];
    showFinalCard(lockedType, info);
    drawBubble(det, `${info.emoji} ${lockedType}`, info.color);
    burstConfetti(info.emoji);
  }
}

/* ---------- 얼굴 테두리 + 말풍선 ---------- */
function drawBubble(det, label, color) {
  const W = overlay.width;
  const box = det.detection.box;
  // 비디오는 CSS로 좌우반전 → 캔버스 좌표도 x를 반전
  const x = W - (box.x + box.width);
  const y = box.y;
  const w = box.width;
  const h = box.height;

  // 둥근 얼굴 테두리 (점선 느낌)
  ctx.save();
  ctx.lineWidth = Math.max(3, W * 0.006);
  ctx.strokeStyle = color;
  ctx.setLineDash([W * 0.03, W * 0.02]);
  roundRect(x, y, w, h, Math.min(w, h) * 0.28);
  ctx.stroke();
  ctx.restore();

  // 말풍선 (얼굴 위쪽, 공간 없으면 아래)
  const fs = Math.max(22, w * 0.16);
  ctx.font = `${fs}px "Jua", system-ui, sans-serif`;
  const tw = ctx.measureText(label).width;
  const padX = fs * 0.5;
  const padY = fs * 0.32;
  const bw = tw + padX * 2;
  const bh = fs + padY * 2;
  let bx = x + w / 2 - bw / 2;
  let by = y - bh - fs * 0.5;
  if (by < 6) by = y + h + fs * 0.4;
  bx = Math.max(6, Math.min(bx, W - bw - 6));

  ctx.save();
  ctx.fillStyle = "rgba(255,255,255,0.92)";
  ctx.shadowColor = "rgba(0,0,0,0.15)";
  ctx.shadowBlur = 10;
  ctx.shadowOffsetY = 4;
  roundRect(bx, by, bw, bh, bh * 0.5);
  ctx.fill();
  ctx.restore();

  ctx.save();
  ctx.lineWidth = Math.max(2, W * 0.004);
  ctx.strokeStyle = color;
  roundRect(bx, by, bw, bh, bh * 0.5);
  ctx.stroke();
  ctx.restore();

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

function ensureBars() {
  if (elBars.children.length) return;
  for (const a of AXES) {
    const row = document.createElement("div");
    row.className = "bar-row";
    row.innerHTML =
      `<div class="bar-label"><span>${a.left}</span><span>${a.right}</span></div>` +
      `<div class="bar-track"><div class="bar-fill ${a.cls}" data-k="${a.key}"></div></div>`;
    elBars.appendChild(row);
  }
}

function setBars(s) {
  for (const a of AXES) {
    const fill = elBars.querySelector(`.bar-fill[data-k="${a.key}"]`);
    fill.style.width = (s[a.key] * 100).toFixed(0) + "%";
  }
}

function updateMeasuringCard(progress) {
  if (resultCard.hidden) resultCard.hidden = false;
  ensureBars();
  if (cardMode !== "measuring") {
    cardMode = "measuring";
    elEmoji.textContent = "🔮";
    elType.textContent = "????";
    elType.style.color = "#b8a7ff";
    elNick.textContent = "관상을 읽는 중...";
  }
  elDesc.textContent = `얼굴을 가만히 보여주세요! ${Math.round(progress * 100)}% 🫧`;
  setBars(smooth);
}

function showFinalCard(type, info) {
  if (resultCard.hidden) resultCard.hidden = false;
  ensureBars();
  cardMode = type;
  elEmoji.textContent = info.emoji;
  elType.textContent = type;
  elType.style.color = info.color;
  elNick.textContent = info.nick;
  elDesc.textContent = info.desc;
  setBars(smooth);
  retryBtn.hidden = false;
  // 카드 살짝 튕기기
  resultCard.style.animation = "none";
  void resultCard.offsetWidth;
  resultCard.style.animation = "cardIn .4s ease";
}

/* ---------- 결과 확정 축하 이펙트 ---------- */
function burstConfetti(emoji) {
  const pool = ["🎉", "✨", "💖", "🌸", emoji, "⭐", emoji];
  for (let i = 0; i < 14; i++) {
    const s = document.createElement("span");
    s.className = "confetti";
    s.textContent = pool[i % pool.length];
    s.style.left = 10 + Math.random() * 80 + "%";
    s.style.animationDelay = (Math.random() * 0.4).toFixed(2) + "s";
    s.style.fontSize = 18 + Math.random() * 22 + "px";
    cameraWrap.appendChild(s);
    setTimeout(() => s.remove(), 2200);
  }
}

/* 창 크기 바뀌어도 캔버스 해상도 유지 (비디오 픽셀 기준) */
window.addEventListener("resize", () => {
  if (video.videoWidth) {
    overlay.width = video.videoWidth;
    overlay.height = video.videoHeight;
  }
});
