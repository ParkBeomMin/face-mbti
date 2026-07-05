/* ============================================================
 *  얼굴 MBTI · 성격 데이터 + 추론 로직
 *  ------------------------------------------------------------
 *  инференс(inferMbti)는 face-api.js의 표정/랜드마크 결과를 받아
 *  4개 축의 0~1 점수를 돌려주는 "교체 가능한" 함수입니다.
 *
 *  ▶ 나중에 연예인 사진으로 학습한 모델을 붙이고 싶다면
 *    inferMbti() 하나만 여러분의 모델 추론 함수로 갈아끼우면 돼요.
 *    (예: TensorFlow.js / ONNX 모델의 4-way 확률 출력)
 * ============================================================ */
(function () {
"use strict";

const MBTI_INFO = {
  INTJ: { emoji: "🦉", nick: "용의주도한 전략가", color: "#b8a7ff", desc: "머릿속에 이미 3수 앞을 그려둔 얼굴! 조용하지만 계획은 완벽해요." },
  INTP: { emoji: "🔭", nick: "호기심 많은 발명가", color: "#a7c8ff", desc: "\"근데 그게 왜 그런 거지?\" 세상 모든 게 궁금한 표정이에요." },
  ENTJ: { emoji: "🦁", nick: "대담한 리더", color: "#ffb18f", desc: "가만있어도 리더 오라가 뿜뿜! 밀어붙이는 카리스마가 느껴져요." },
  ENTP: { emoji: "🦊", nick: "재기발랄한 논쟁가", color: "#ffcf8f", desc: "장난기와 아이디어가 반짝반짝. 토론이 세상 제일 재밌는 얼굴!" },
  INFJ: { emoji: "🌙", nick: "선의의 옹호자", color: "#c8b7ff", desc: "말없이 남을 헤아리는 다정함이 눈빛에 담겨 있어요." },
  INFP: { emoji: "🌸", nick: "몽글몽글 중재자", color: "#ffb7d5", desc: "마음이 말랑말랑, 상상 속을 걷는 순수한 감성이 느껴져요." },
  ENFJ: { emoji: "🌻", nick: "따뜻한 선도자", color: "#ffd98f", desc: "모두를 챙기는 햇살 같은 얼굴! 곁에 있으면 든든해요." },
  ENFP: { emoji: "🦋", nick: "반짝반짝 활동가", color: "#ff9fc4", desc: "에너지가 팡팡 터지는 표정! 어디서든 분위기 메이커예요." },
  ISTJ: { emoji: "🐢", nick: "청렴결백한 관리자", color: "#9fd6c0", desc: "믿음직스럽고 성실한 기운. 한 번 맡으면 끝까지 해내는 얼굴!" },
  ISFJ: { emoji: "🐑", nick: "다정한 수호자", color: "#bde8d0", desc: "포근하고 배려 넘치는 인상. 옆에 있으면 마음이 놓여요." },
  ESTJ: { emoji: "🦅", nick: "엄격한 관리자", color: "#ffbf8f", desc: "딱 부러지는 야무진 표정! 정리정돈과 규칙의 아이콘이에요." },
  ESFJ: { emoji: "🐰", nick: "사교적인 외교관", color: "#ffc2dc", desc: "사람 좋아하는 게 얼굴에 다 보여요. 다정한 인싸 기운 뿜뿜!" },
  ISTP: { emoji: "🐺", nick: "만능 재주꾼", color: "#a7d0e8", desc: "쿨하고 손재주 좋은 관찰자. 말은 적지만 다 알고 있는 눈빛!" },
  ISFP: { emoji: "🍓", nick: "호기심 많은 예술가", color: "#ffbccb", desc: "감각적이고 자유로운 감성. 소소한 아름다움을 아는 얼굴이에요." },
  ESTP: { emoji: "⚡", nick: "모험을 즐기는 사업가", color: "#ffd07a", desc: "지금 이 순간을 즐기는 활력! 즉흥적이고 대담한 매력이 있어요." },
  ESFP: { emoji: "🎈", nick: "자유로운 연예인", color: "#ff9fb0", desc: "타고난 분위기 메이커! 어디서든 스포트라이트를 받는 얼굴이에요." },
};

/** 4축 점수(0~1)를 4글자 타입으로 변환 */
function scoresToType(s) {
  return (
    (s.ei >= 0.5 ? "E" : "I") +
    (s.sn >= 0.5 ? "N" : "S") +
    (s.tf >= 0.5 ? "F" : "T") +
    (s.jp >= 0.5 ? "P" : "J")
  );
}

/* ---------- 기하 헬퍼 ---------- */
function dist(a, b) { return Math.hypot(a.x - b.x, a.y - b.y); }
function avgY(pts) { return pts.reduce((s, p) => s + p.y, 0) / pts.length; }
function clamp01(v) { return Math.max(0, Math.min(1, v)); }
// 값 v를 [lo, hi] 구간에서 0~1로 매핑
function ramp(v, lo, hi) { return clamp01((v - lo) / (hi - lo)); }

/**
 * 얼굴 한 개의 face-api 결과 → MBTI 4축 점수(0~1)
 * @param {object} det  face-api detection (withFaceLandmarks + withFaceExpressions)
 * @returns {{ei:number, sn:number, tf:number, jp:number}}
 */
function inferMbti(det) {
  const expr = det.expressions || {};
  const lm = det.landmarks;
  const box = det.detection.box;
  const H = box.height || 1;
  const pts = lm.positions;

  const happy = expr.happy || 0;
  const surprised = expr.surprised || 0;
  const neutral = expr.neutral || 0;
  const sad = expr.sad || 0;
  const angry = expr.angry || 0;
  const fearful = expr.fearful || 0;
  const disgusted = expr.disgusted || 0;

  // --- 이목구비 기하 ---
  // 눈썹 올라감 정도 (눈썹 17~26 vs 눈 위쪽 37,38,43,44)
  const browY = avgY(pts.slice(17, 27));
  const eyeTopY = avgY([pts[37], pts[38], pts[43], pts[44]]);
  const browRaise = (eyeTopY - browY) / H; // 클수록 눈썹이 위로

  // 눈 크기 (세로 열림 / 얼굴)
  const eyeOpen = (
    dist(pts[37], pts[41]) + dist(pts[38], pts[40]) +
    dist(pts[43], pts[47]) + dist(pts[44], pts[46])
  ) / 4 / H;

  // 입 벌어짐 (안쪽 입술 62-66)
  const mouthOpen = dist(pts[62], pts[66]) / H;

  // 입꼬리 올라감 (양 끝 48,54 가 입 중앙보다 위면 미소)
  const mouthCornerY = (pts[48].y + pts[54].y) / 2;
  const mouthMidY = (pts[51].y + pts[57].y) / 2;
  const smileCurve = (mouthMidY - mouthCornerY) / H; // +면 웃는 입

  // 좌우 대칭성 (코 27 기준 양쪽 눈끝까지 거리 차이)
  const leftSpan = dist(pts[27], pts[36]);
  const rightSpan = dist(pts[27], pts[45]);
  const asym = Math.abs(leftSpan - rightSpan) / (leftSpan + rightSpan);

  /* ---------- 4축 점수 (E/N/F/P 방향이 1) ---------- */

  // E(외향): 미소·놀람·입꼬리·입 벌어짐이 크면 표현적 → E
  const ei = clamp01(
    0.5 * happy + 0.25 * surprised + 6 * Math.max(0, smileCurve)
    + 5 * mouthOpen - 0.35 * neutral + 0.15
  );

  // N(직관): 눈썹 올라감·놀람 → 상상력/개방적
  const sn = clamp01(
    ramp(browRaise, 0.06, 0.16) * 0.7 + surprised * 0.5 + 0.1
  );

  // F(감정): 미소·슬픔·두려움(감정표현) 많으면 F, 무표정/화남/혐오는 T
  const tf = clamp01(
    0.5 * happy + 0.6 * sad + 0.5 * fearful
    - 0.6 * angry - 0.5 * disgusted - 0.25 * neutral + 0.45
  );

  // P(인식): 입 벌어짐·비대칭(즉흥/자유) → P, 대칭/다문 입 → J
  const jp = clamp01(
    4 * mouthOpen + ramp(asym, 0.0, 0.14) * 0.5
    + ramp(eyeOpen, 0.05, 0.11) * 0.3 + 0.15
  );

  return { ei, sn, tf, jp };
}

/* 브라우저 전역으로 노출 */
window.MBTI = { MBTI_INFO, inferMbti, scoresToType, clamp01 };

})();
