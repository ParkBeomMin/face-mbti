/* 더 트레이니 🎤 아이돌 연습생 키우기 */
"use strict";

// ---------- 데이터 ----------
const AGENCIES = [
  {
    id: "sw", name: "SW엔터", emoji: "🏢", tier: "대형",
    debut: 0.76, growth: 0.92, spot: 1.15,
    desc: "빅3 대형 기획사. 데뷔만 하면 대박, 대신 경쟁이 지옥이에요",
  },
  {
    id: "onlyone", name: "온리원컴퍼니", emoji: "🌐", tier: "대형",
    debut: 0.72, growth: 0.97, spot: 1.1,
    desc: "글로벌 시스템 명가. 해외 팬덤이 빠르게 붙어요",
  },
  {
    id: "luna", name: "루나엔터", emoji: "🌙", tier: "중형",
    debut: 0.62, growth: 1.05, spot: 1.0,
    desc: "알짜 중형 기획사. 기회와 경쟁의 균형이 좋아요",
  },
  {
    id: "byeol", name: "별빛엔터", emoji: "⭐", tier: "소형",
    debut: 0.55, growth: 1.12, spot: 0.95,
    desc: "소형이지만 1:1 트레이닝. 실력이 쑥쑥 자라요",
  },
  {
    id: "garage", name: "개러지뮤직", emoji: "🎸", tier: "신생",
    debut: 0.5, growth: 1.15, spot: 1.05,
    desc: "신생 기획사. 뭐든 시켜줘서 무대 경험이 쌓여요",
  },
];

const STAT_DEFS = [
  { key: "vocal", name: "보컬", emoji: "🎤", sub: "가창력" },
  { key: "dance", name: "댄스", emoji: "🕺", sub: "춤·퍼포먼스" },
  { key: "rap", name: "랩", emoji: "🎙️", sub: "랩·작사" },
  { key: "charm", name: "매력", emoji: "✨", sub: "표정·무대 장악" },
  { key: "stamina", name: "체력", emoji: "🫀", sub: "연습 지구력" },
];

const POS_INFO = {
  vocal: { name: "보컬", stat: "vocal" },
  dance: { name: "댄스", stat: "dance" },
  rap: { name: "랩", stat: "rap" },
};

const STAGE_NAMES = ["하람", "다온", "세인", "벼리", "라온", "누리", "시안", "도담", "늘봄", "여름", "가온", "미르"];

// 평가 무대 종류: 주 스탯 / 보조 스탯 가중치
const STAGE_TYPES = [
  { name: "보컬 무대", main: "vocal", aux: "charm" },
  { name: "댄스 무대", main: "dance", aux: "stamina" },
  { name: "랩 무대", main: "rap", aux: "charm" },
  { name: "포지션 자유 무대", main: null, aux: "charm" }, // main = 내 포지션 스탯
];

const EVALS = { 6: "상반기 쇼케이스", 12: "연말 평가" };
const SURVIVAL_ROUNDS = ["예선", "본선", "세미파이널", "파이널"];

// ---------- 상태 ----------
const SAVE_KEY = "trainee-save-v1";
let S = null;
let ev = null; // 진행 중인 평가/서바이벌

const $ = (id) => document.getElementById(id);
const rand = (a, b) => a + Math.random() * (b - a);
const randInt = (a, b) => Math.floor(rand(a, b + 1));
const pick = (arr) => arr[Math.floor(Math.random() * arr.length)];
const clamp = (v, a, b) => Math.min(b, Math.max(a, v));

function newState(agency, pos, name) {
  const stats = {};
  const talents = {};
  for (const d of STAT_DEFS) {
    stats[d.key] = randInt(28, 44);
    talents[d.key] = rand(0.8, 1.45);
  }
  stats[POS_INFO[pos].stat] = clamp(stats[POS_INFO[pos].stat] + 8, 0, 100);
  talents[POS_INFO[pos].stat] = Math.max(talents[POS_INFO[pos].stat], 1.05);
  return {
    agency: agency.id, pos, name,
    year: 1, month: 1,
    stats, talents,
    condition: 80,
    fandom: 0,
    buff: false,
    trophies: [],
    stages: 0, // 오른 무대 수
    log: [],
  };
}

const agencyOf = () => AGENCIES.find((a) => a.id === S.agency);
const overall = () => {
  const vals = Object.values(S.stats);
  return vals.reduce((a, b) => a + b, 0) / vals.length;
};

function save() { localStorage.setItem(SAVE_KEY, JSON.stringify(S)); }
function clearSave() { localStorage.removeItem(SAVE_KEY); }

// ---------- 화면 전환 ----------
function show(id) {
  document.querySelectorAll(".screen").forEach((el) => el.classList.remove("active"));
  $(id).classList.add("active");
  window.scrollTo(0, 0);
}

// ---------- 시작 흐름 ----------
let chosenAgency = null;
let chosenPos = null;

function initTitle() {
  const saved = localStorage.getItem(SAVE_KEY);
  if (saved) {
    $("btn-continue").classList.remove("hidden");
    $("btn-continue").onclick = () => {
      S = JSON.parse(saved);
      renderMain();
      show("screen-main");
    };
  }
  $("btn-new").onclick = () => {
    renderAgencies();
    show("screen-agency");
  };
}

function renderAgencies() {
  const box = $("agency-list");
  box.innerHTML = "";
  for (const a of AGENCIES) {
    const btn = document.createElement("button");
    btn.className = "card";
    btn.innerHTML = `
      <span class="card-emoji">${a.emoji}</span>
      <span class="card-title">${a.name}</span>
      <span class="card-sub">${a.tier} 기획사</span>
      <span class="card-desc">${a.desc}</span>
      <span class="card-tags">
        <span class="tag">데뷔 파워 ${"★".repeat(Math.round(a.debut * 5))}</span>
        <span class="tag">성장 ${"★".repeat(Math.round(a.growth * 3))}</span>
      </span>`;
    btn.onclick = () => {
      chosenAgency = a;
      $("position-hint").textContent = `${a.name} 오디션 합격! 어떤 포지션을 노릴까요?`;
      show("screen-position");
    };
    box.appendChild(btn);
  }
}

document.querySelectorAll("#position-list .card").forEach((btn) => {
  btn.addEventListener("click", () => {
    chosenPos = btn.dataset.pos;
    $("name-hint").textContent = `${chosenAgency.name} ${POS_INFO[chosenPos].name} 연습생의 활동명은?`;
    $("input-name").value = pick(STAGE_NAMES);
    show("screen-name");
  });
});

$("btn-random-name").addEventListener("click", () => {
  $("input-name").value = pick(STAGE_NAMES);
});

$("btn-start").addEventListener("click", () => {
  const name = $("input-name").value.trim() || pick(STAGE_NAMES);
  S = newState(chosenAgency, chosenPos, name);
  addLog(`🎤 ${chosenAgency.name} 연습생 계약! ${name}의 연습실 생활이 시작됐어요.`);
  save();
  renderMain();
  show("screen-main");
});

// ---------- 메인 렌더 ----------
function renderMain() {
  const a = agencyOf();
  $("hud-name").textContent = `${S.name} (${POS_INFO[S.pos].name})`;
  $("hud-school").textContent = `${a.emoji} ${a.name} · 종합 ${Math.round(overall())}`;
  $("hud-turn").textContent = `${S.year}년차 ${S.month}월`;

  $("cond-num").textContent = Math.round(S.condition);
  const condBar = $("cond-bar");
  condBar.style.width = `${S.condition}%`;
  condBar.classList.toggle("low", S.condition < 35);

  const pct = clamp((S.fandom / 450) * 100, 0, 100);
  $("scout-num").textContent = Math.round(S.fandom);
  $("scout-bar").style.width = `${pct}%`;

  const statsBox = $("stats-box");
  statsBox.innerHTML = "";
  for (const d of STAT_DEFS) {
    const v = Math.round(S.stats[d.key]);
    const stars = "⭐".repeat(clamp(Math.round((S.talents[d.key] - 0.6) * 4), 1, 5));
    const row = document.createElement("div");
    row.className = "stat-row";
    row.innerHTML = `
      <span class="stat-name">${d.emoji} ${d.name}</span>
      <div class="bar"><div class="bar-fill stat" style="width:${v}%"></div></div>
      <span class="stat-val">${v}</span>
      <span class="stat-pot" title="잠재력">${stars}</span>`;
    statsBox.appendChild(row);
  }

  const actBox = $("action-list");
  actBox.innerHTML = "";
  for (const d of STAT_DEFS) {
    const btn = document.createElement("button");
    btn.className = "action-btn";
    btn.innerHTML = `<span class="a-emoji">${d.emoji}</span>${d.name} 연습<span class="a-sub">${d.sub}</span>`;
    btn.onclick = () => doTraining(d);
    actBox.appendChild(btn);
  }
  const rest = document.createElement("button");
  rest.className = "action-btn rest";
  rest.innerHTML = `<span class="a-emoji">🛌</span>휴식 <span class="a-sub">컨디션 대폭 회복</span>`;
  rest.onclick = doRest;
  actBox.appendChild(rest);

  renderLog();
}

function addLog(msg) {
  S.log.unshift(`[${S.year}년차 ${S.month}월] ${msg}`);
  S.log = S.log.slice(0, 40);
}

function renderLog() {
  $("log-box").innerHTML = S.log
    .map((l, i) => `<div class="${i === 0 ? "new" : ""}">${l}</div>`)
    .join("");
}

// ---------- 행동 ----------
function doTraining(def) {
  const a = agencyOf();

  if (S.condition < 25 && Math.random() < 0.4) {
    S.condition = clamp(S.condition + 20, 0, 100);
    addLog(`🤕 지친 몸으로 무리하다 ${def.name} 연습 중 몸이 상했어요. 한 달을 회복으로 날렸어요.`);
    endMonth();
    return;
  }

  const condMod = S.condition >= 70 ? 1.15 : S.condition >= 40 ? 1.0 : 0.6;
  const buffMod = S.buff ? 1.5 : 1.0;
  S.buff = false;
  let gain = rand(2.2, 4.2) * S.talents[def.key] * a.growth * condMod * buffMod;
  gain = Math.round(gain * 10) / 10;
  S.stats[def.key] = clamp(S.stats[def.key] + gain, 0, 100);
  S.condition = clamp(S.condition - randInt(12, 18), 0, 100);
  addLog(`${def.emoji} ${def.name} 연습 완료! +${gain.toFixed(1)} (${Math.round(S.stats[def.key])})`);

  maybeEvent();
  endMonth();
}

function doRest() {
  S.condition = clamp(S.condition + randInt(30, 42), 0, 100);
  S.stats.stamina = clamp(S.stats.stamina + 0.5, 0, 100);
  addLog(`🛌 푹 쉬었어요. 컨디션 회복! (${Math.round(S.condition)})`);
  maybeEvent();
  endMonth();
}

function maybeEvent() {
  if (Math.random() > 0.3) return;
  const a = agencyOf();
  const events = [
    () => {
      const d = pick(STAT_DEFS);
      S.stats[d.key] = clamp(S.stats[d.key] + 3, 0, 100);
      addLog(`🧑‍🏫 트레이너 선생님의 특별 레슨! ${d.name} +3`);
    },
    () => {
      const pts = Math.round(8 * a.spot);
      S.fandom += pts;
      addLog(`📱 연습 직캠이 SNS에서 소소하게 화제! 팬덤 +${pts}`);
    },
    () => {
      S.condition = clamp(S.condition - 20, 0, 100);
      addLog(`🤒 감기 몸살로 며칠 앓았어요. 컨디션 -20`);
    },
    () => {
      S.condition = clamp(S.condition + 12, 0, 100);
      addLog(`🧋 연습실에 간식 차가 왔어요! 컨디션 +12`);
    },
    () => {
      S.buff = true;
      addLog(`🔥 월말평가 1위 라이벌의 무대에 자극받았어요! 다음 연습 효율 1.5배`);
    },
    () => {
      S.stats.stamina = clamp(S.stats.stamina + 2, 0, 100);
      addLog(`🏃 새벽 러닝 루틴이 몸에 붙었어요. 체력 +2`);
    },
  ];
  pick(events)();
}

// ---------- 월 진행 ----------
function endMonth() {
  save();
  renderMain();

  // 3년차 12월 = 데뷔 서바이벌
  if (S.year === 3 && S.month === 12) {
    startSurvival();
    return;
  }
  const evalName = EVALS[S.month];
  if (evalName) {
    startEval(evalName);
    return;
  }
  advanceMonth();
}

function advanceMonth() {
  S.month += 1;
  if (S.month === 13) {
    S.month = 1;
    S.year += 1;
  }
  save();
  renderMain();
}

// ---------- 무대 공통 ----------
function stageScore(type) {
  const mainKey = type.main || POS_INFO[S.pos].stat;
  const score =
    S.stats[mainKey] * 0.55 +
    S.stats[type.aux] * 0.2 +
    S.stats.charm * 0.1 +
    S.condition / 8 +
    rand(-9, 9);
  return { mainKey, score };
}

function gradeOf(score) {
  if (score >= 76) return { g: "S", pts: 30, txt: "🌟 완벽한 무대! 심사위원 전원이 기립했어요." };
  if (score >= 64) return { g: "A", pts: 22, txt: "🔥 시선을 사로잡는 무대! 카메라가 계속 따라와요." };
  if (score >= 52) return { g: "B", pts: 15, txt: "🙂 안정적인 무대. 나쁘지 않았어요." };
  if (score >= 40) return { g: "C", pts: 9, txt: "😬 아쉬운 실수가 있었어요. 다음에 만회해요." };
  return { g: "D", pts: 5, txt: "😢 무대 위에서 머리가 하얘졌어요…" };
}

// ---------- 정기 평가 (쇼케이스) ----------
function startEval(name) {
  ev = { kind: "eval", name, idx: 0, totalPts: 0, scores: [] };
  $("stage-title").textContent = `🎪 ${S.year}년차 ${name}`;
  $("stage-round").textContent = "";
  $("stage-card").innerHTML = `
    <div class="tour-vs">🎤 전 연습생 공개 평가!</div>
    <div class="tour-line">세 번의 무대에 올라요.<br/>좋은 무대를 보여주면 팬덤과 회사의 주목도가 올라요.</div>`;
  $("btn-stage-next").textContent = "첫 무대 오르기";
  $("btn-stage-next").onclick = playEvalStage;
  show("screen-stage");
}

function playEvalStage() {
  const a = agencyOf();
  // 1·2번째 무대는 보컬/댄스/랩 중 랜덤, 마지막은 포지션 자유 무대
  const type = ev.idx === 2 ? STAGE_TYPES[3] : STAGE_TYPES[pick([0, 1, 2])];
  const { score } = stageScore(type);
  const grade = gradeOf(score);
  const pts = Math.round(grade.pts * a.spot);
  S.fandom += pts;
  S.stages += 1;
  ev.totalPts += pts;
  ev.scores.push(score);
  S.condition = clamp(S.condition - 5, 0, 100);
  ev.idx += 1;

  $("stage-round").textContent = `${ev.idx}번째 무대 · ${type.name}`;
  $("stage-card").innerHTML = `
    <div class="tour-vs">무대 등급 <span class="${grade.g === "S" || grade.g === "A" ? "win" : grade.g === "D" ? "lose" : ""}">${grade.g}</span></div>
    <div class="tour-line">${grade.txt}</div>
    <div class="tour-pts">💖 팬덤 +${pts}</div>`;

  if (ev.idx < 3) {
    $("btn-stage-next").textContent = "다음 무대";
    $("btn-stage-next").onclick = playEvalStage;
  } else {
    $("btn-stage-next").textContent = "종합 순위 발표";
    $("btn-stage-next").onclick = finishEval;
  }
}

function finishEval() {
  const avg = ev.scores.reduce((x, y) => x + y, 0) / ev.scores.length;
  const rank = clamp(Math.round(28 - avg / 2.8 + rand(-2, 2)), 1, 24);
  let bonus = 0;
  if (rank === 1) {
    bonus = 25;
    S.trophies.push(`${S.year}년차 ${ev.name} 1위`);
  } else if (rank <= 3) bonus = 15;
  else if (rank <= 10) bonus = 8;
  S.fandom += bonus;
  $("stage-round").textContent = "종합 순위";
  $("stage-card").innerHTML = `
    <div class="tour-vs">연습생 24명 중 <span class="${rank <= 3 ? "win" : rank >= 18 ? "lose" : ""}">${rank}위</span></div>
    <div class="tour-line">${
      rank === 1 ? "🏆 전체 1위! 회사가 데뷔조 명단에 이름을 올려두기 시작했어요." :
      rank <= 3 ? "🌟 최상위권! 트레이너들 사이에서 데뷔조 후보로 불려요." :
      rank <= 10 ? "🙂 중상위권. 꾸준함이 무기예요." :
      rank <= 17 ? "😐 중하위권… 다음 평가까지 더 달려야 해요." :
      "😨 하위권. 월말 면담이 잡혔어요. 분발해야 해요!"
    }</div>
    ${bonus ? `<div class="tour-pts">🏅 순위 보너스 팬덤 +${bonus}</div>` : ""}
    <div class="tour-pts">이번 평가 팬덤 합계 +${ev.totalPts + bonus}</div>`;
  $("btn-stage-next").textContent = "연습실로 돌아가기";
  $("btn-stage-next").onclick = () => {
    addLog(`🎪 ${ev.name} ${rank}위! (팬덤 +${ev.totalPts + bonus})`);
    ev = null;
    show("screen-main");
    advanceMonth();
  };
}

// ---------- 데뷔 서바이벌 ----------
function startSurvival() {
  ev = { kind: "survival", round: 0, eliminated: false };
  $("stage-title").textContent = `📺 데뷔 서바이벌 <더 파이널>`;
  $("stage-round").textContent = "";
  $("stage-card").innerHTML = `
    <div class="tour-vs">🔥 전국 연습생 100명, 데뷔조는 단 7명</div>
    <div class="tour-line">3년의 연습이 오늘을 위해 있었어요.<br/>예선부터 파이널까지, 살아남으면 데뷔합니다.</div>`;
  $("btn-stage-next").textContent = "예선 무대 오르기";
  $("btn-stage-next").onclick = playSurvivalRound;
  show("screen-stage");
}

function playSurvivalRound() {
  const a = agencyOf();
  const roundName = SURVIVAL_ROUNDS[ev.round];
  const type = pick(STAGE_TYPES);
  const { score } = stageScore(type);
  const grade = gradeOf(score);
  const pts = Math.round(grade.pts * a.spot) + ev.round * 4;
  S.fandom += pts;
  S.stages += 1;
  S.condition = clamp(S.condition - 5, 0, 100);

  const p = clamp(
    0.40 + a.debut * 0.35 + (overall() - 50) / 90 + S.fandom / 1500 +
    (S.condition - 50) / 900 - ev.round * 0.05,
    0.12, 0.93
  );
  const pass = Math.random() < p;

  $("stage-round").textContent = `${roundName} · ${type.name}`;
  $("stage-card").innerHTML = `
    <div class="tour-vs">무대 등급 ${grade.g} — <span class="${pass ? "win" : "lose"}">${pass ? "생존! 🎉" : "탈락… 💧"}</span></div>
    <div class="tour-line">${grade.txt}</div>
    <div class="tour-pts">💖 팬덤 +${pts}</div>`;

  if (pass && ev.round < SURVIVAL_ROUNDS.length - 1) {
    ev.round += 1;
    $("btn-stage-next").textContent = `${SURVIVAL_ROUNDS[ev.round]} 진출!`;
    $("btn-stage-next").onclick = playSurvivalRound;
  } else {
    ev.eliminated = !pass;
    $("btn-stage-next").textContent = pass ? "🌟 최종 발표 보러 가기" : "결과 받아들이기";
    $("btn-stage-next").onclick = () => showEnding(pass, ev.round);
  }
}

// ---------- 엔딩 ----------
function showEnding(survivedFinal, lastRound) {
  const a = agencyOf();
  const score = S.fandom + overall() * 2;

  let emoji, title, teamLine, msg;
  if (survivedFinal && score >= 520) {
    emoji = "👑"; title = "데뷔조 센터 데뷔!";
    teamLine = `${a.name} 신인 그룹 — 센터 확정`;
    msg = "최종 1픽! 데뷔 무대의 정중앙은 당신의 자리예요.";
  } else if (survivedFinal) {
    emoji = "🌟"; title = "데뷔조 합류!";
    teamLine = `${a.name} 신인 그룹 데뷔 확정`;
    msg = "파이널 생존! 3년의 연습실 생활이 드디어 무대가 됐어요.";
  } else if (lastRound === 3) {
    emoji = "💜"; title = "파이널 탈락… 하지만!";
    teamLine = `${a.name} 차기 데뷔조 확정`;
    msg = "아쉽게 최종 데뷔조엔 들지 못했지만, 회사가 차기 그룹 데뷔를 약속했어요.";
  } else if (lastRound === 2 && score >= 420) {
    emoji = "📞"; title = "타사 캐스팅!";
    teamLine = "라이벌 기획사 이적 제안";
    msg = "세미파이널 무대를 본 타사에서 러브콜이! 새 둥지에서 데뷔를 노려요.";
  } else if (lastRound >= 1) {
    emoji = "🌱"; title = "연습생 재계약";
    teamLine = `${a.name} 연습생 연장`;
    msg = "이번엔 여기까지. 하지만 회사는 아직 당신을 믿고 있어요.";
  } else if (score >= 330) {
    emoji = "📹"; title = "홀로서기 선언";
    teamLine = "유튜브 채널 개설 → 역주행 노리기";
    msg = "예선 탈락… 하지만 쌓인 팬덤이 있어요. 커버 영상으로 역주행을 노려봐요!";
  } else {
    emoji = "🎒"; title = "연습실과 작별";
    teamLine = "평범한 일상으로 복귀";
    msg = "꿈은 이루지 못했지만 3년의 땀은 사라지지 않아요. 무대 밖에도 인생은 있으니까!";
  }

  const statLines = STAT_DEFS
    .map((d) => `${d.emoji} ${d.name} ${Math.round(S.stats[d.key])}`)
    .join(" · ");
  const trophyLine = S.trophies.length
    ? `🏆 ${S.trophies.join(", ")}`
    : "🏆 평가 1위 경력 없음";

  $("ending-card").innerHTML = `
    <div class="draft-emoji">${emoji}</div>
    <div class="draft-title">${title}</div>
    <div class="draft-team">${teamLine}</div>
    <div>${msg}</div>
    <div class="draft-summary">
      ${a.emoji} ${a.name} · ${POS_INFO[S.pos].name} ${S.name}<br/>
      ${statLines}<br/>
      💖 최종 팬덤 ${Math.round(S.fandom)} · 무대 ${S.stages}회<br/>
      ${trophyLine}
    </div>`;

  $("btn-share").onclick = () => {
    const text = `🎤 더 트레이니 결과\n${a.name} ${S.name} — ${title}\n${teamLine}\n팬덤 ${Math.round(S.fandom)} / ${trophyLine}`;
    navigator.clipboard?.writeText(text).then(
      () => ($("btn-share").textContent = "✅ 복사 완료!"),
      () => ($("btn-share").textContent = "복사 실패 😢")
    );
  };
  $("btn-restart").onclick = () => {
    clearSave();
    location.reload();
  };

  clearSave();
  show("screen-ending");
}

// ---------- 시작 ----------
initTitle();
