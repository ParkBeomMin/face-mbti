/* 더 루키 ⚾ 야구선수 키우기 */
"use strict";

// ---------- 데이터 ----------
const REGIONS = [
  {
    id: "seoul", name: "서울", emoji: "🏙️",
    school: "서울고", teams: ["LG 트윈스", "두산 베어스", "키움 히어로즈"],
    win: 0.70, growth: 1.0, spot: 1.1,
    desc: "미디어와 스카우트가 몰리는 수도. 주목받기 좋아요",
  },
  {
    id: "gyeongin", name: "인천·경기", emoji: "🌊",
    school: "인천고", teams: ["SSG 랜더스", "KT 위즈"],
    win: 0.62, growth: 1.05, spot: 1.0,
    desc: "탄탄한 유망주 산실. 성장 환경이 좋아요",
  },
  {
    id: "chungcheong", name: "대전·충청", emoji: "🌰",
    school: "대전고", teams: ["한화 이글스"],
    win: 0.58, growth: 1.1, spot: 1.05,
    desc: "팀은 약하지만 출전 기회가 많아 크게 성장해요",
  },
  {
    id: "honam", name: "광주·전라", emoji: "🍚",
    school: "광주제일고", teams: ["KIA 타이거즈"],
    win: 0.78, growth: 0.92, spot: 0.95,
    desc: "최강 명문. 우승은 쉽지만 주전 경쟁이 치열해요",
  },
  {
    id: "daegu", name: "대구·경북", emoji: "🍎",
    school: "대구상원고", teams: ["삼성 라이온즈"],
    win: 0.72, growth: 0.97, spot: 1.0,
    desc: "전통의 야구 도시. 밸런스가 좋아요",
  },
  {
    id: "busan", name: "부산·경남", emoji: "⚓",
    school: "부산고", teams: ["롯데 자이언츠", "NC 다이노스"],
    win: 0.74, growth: 0.95, spot: 1.0,
    desc: "구도(球都) 부산. 열광적인 응원 속에 큰 무대 경험",
  },
];

const STAT_DEFS = {
  batter: [
    { key: "contact", name: "타격", emoji: "🏏", sub: "안타 생산" },
    { key: "power", name: "파워", emoji: "💪", sub: "홈런 파워" },
    { key: "run", name: "주루", emoji: "👟", sub: "도루·주루" },
    { key: "defense", name: "수비", emoji: "🧤", sub: "수비 안정감" },
    { key: "stamina", name: "체력", emoji: "🫀", sub: "지구력" },
  ],
  pitcher: [
    { key: "velocity", name: "구속", emoji: "🔥", sub: "빠른 공" },
    { key: "control", name: "제구", emoji: "🎯", sub: "정확한 공" },
    { key: "breaking", name: "변화구", emoji: "🌀", sub: "현란한 공" },
    { key: "defense", name: "수비", emoji: "🧤", sub: "견제·수비" },
    { key: "stamina", name: "체력", emoji: "🫀", sub: "이닝 소화" },
  ],
};

const SURNAMES = ["김", "이", "박", "최", "정", "강", "조", "윤", "장", "임"];
const GIVEN = ["도윤", "시우", "하준", "은찬", "민재", "태양", "강민", "준서", "지호", "건우", "현빈", "서준"];

const OPPONENTS = ["북일고", "덕수고", "경남고", "유신고", "장충고", "휘문고", "마산용마고", "전주고", "세광고", "강릉고", "경북고", "천안북일고", "충암고", "성남고"];

const TOURNAMENTS = { 6: "황금사자기", 8: "청룡기" };
const ROUNDS = ["16강", "8강", "4강", "결승"];

// ---------- 상태 ----------
const SAVE_KEY = "rookie-save-v1";
let S = null; // 게임 상태
let tour = null; // 진행 중인 대회 상태

const $ = (id) => document.getElementById(id);
const rand = (a, b) => a + Math.random() * (b - a);
const randInt = (a, b) => Math.floor(rand(a, b + 1));
const pick = (arr) => arr[Math.floor(Math.random() * arr.length)];
const clamp = (v, a, b) => Math.min(b, Math.max(a, v));

function newState(region, pos, name) {
  const stats = {};
  const talents = {};
  for (const d of STAT_DEFS[pos]) {
    stats[d.key] = randInt(28, 44);
    talents[d.key] = rand(0.8, 1.45);
  }
  return {
    region: region.id, pos, name,
    year: 1, month: 3,
    stats, talents,
    condition: 80,
    scout: 0,
    buff: false, // 다음 훈련 효율 상승
    trophies: [],
    games: 0, // 대회 출전 경기 수
    log: [],
  };
}

const regionOf = () => REGIONS.find((r) => r.id === S.region);
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
let chosenRegion = null;
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
    renderRegions();
    show("screen-region");
  };
}

function renderRegions() {
  const box = $("region-list");
  box.innerHTML = "";
  for (const r of REGIONS) {
    const btn = document.createElement("button");
    btn.className = "card";
    btn.innerHTML = `
      <span class="card-emoji">${r.emoji}</span>
      <span class="card-title">${r.name}</span>
      <span class="card-sub">${r.school} · ${r.teams.join(" / ")}</span>
      <span class="card-desc">${r.desc}</span>
      <span class="card-tags">
        <span class="tag">팀 전력 ${"★".repeat(Math.round(r.win * 5))}</span>
        <span class="tag">성장 ${"★".repeat(Math.round(r.growth * 3))}</span>
      </span>`;
    btn.onclick = () => {
      chosenRegion = r;
      $("position-hint").textContent = `${r.school}에 입학했어요! 어떤 선수가 될까요?`;
      show("screen-position");
    };
    box.appendChild(btn);
  }
}

document.querySelectorAll("#position-list .card").forEach((btn) => {
  btn.addEventListener("click", () => {
    chosenPos = btn.dataset.pos;
    $("name-hint").textContent = `${chosenRegion.school} ${chosenPos === "batter" ? "타자" : "투수"} 유망주의 이름은?`;
    $("input-name").value = pick(SURNAMES) + pick(GIVEN);
    show("screen-name");
  });
});

$("btn-random-name").addEventListener("click", () => {
  $("input-name").value = pick(SURNAMES) + pick(GIVEN);
});

$("btn-start").addEventListener("click", () => {
  const name = $("input-name").value.trim() || pick(SURNAMES) + pick(GIVEN);
  S = newState(chosenRegion, chosenPos, name);
  addLog(`⚾ ${chosenRegion.school} 입학! ${name}의 야구 인생이 시작됐어요.`);
  save();
  renderMain();
  show("screen-main");
});

// ---------- 메인 렌더 ----------
function renderMain() {
  const r = regionOf();
  $("hud-name").textContent = `${S.name} (${S.pos === "batter" ? "타자" : "투수"})`;
  $("hud-school").textContent = `${r.emoji} ${r.school} · 종합 ${Math.round(overall())}`;
  $("hud-turn").textContent = `${S.year}학년 ${S.month}월`;

  $("cond-num").textContent = Math.round(S.condition);
  const condBar = $("cond-bar");
  condBar.style.width = `${S.condition}%`;
  condBar.classList.toggle("low", S.condition < 35);

  const scoutPct = clamp((S.scout / 450) * 100, 0, 100);
  $("scout-num").textContent = Math.round(S.scout);
  $("scout-bar").style.width = `${scoutPct}%`;

  // 스탯
  const statsBox = $("stats-box");
  statsBox.innerHTML = "";
  for (const d of STAT_DEFS[S.pos]) {
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

  // 행동 버튼
  const actBox = $("action-list");
  actBox.innerHTML = "";
  for (const d of STAT_DEFS[S.pos]) {
    const btn = document.createElement("button");
    btn.className = "action-btn";
    btn.innerHTML = `<span class="a-emoji">${d.emoji}</span>${d.name} 훈련<span class="a-sub">${d.sub}</span>`;
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
  S.log.unshift(`[${S.year}학년 ${S.month}월] ${msg}`);
  S.log = S.log.slice(0, 40);
}

function renderLog() {
  const box = $("log-box");
  box.innerHTML = S.log
    .map((l, i) => `<div class="${i === 0 ? "new" : ""}">${l}</div>`)
    .join("");
}

// ---------- 행동 ----------
function doTraining(def) {
  const r = regionOf();

  // 컨디션이 바닥일 때 무리하면 부상
  if (S.condition < 25 && Math.random() < 0.4) {
    S.condition = clamp(S.condition + 20, 0, 100);
    addLog(`🤕 지친 몸으로 무리하다 ${def.name} 훈련 중 부상! 한 달을 재활로 날렸어요.`);
    endMonth();
    return;
  }

  const condMod = S.condition >= 70 ? 1.15 : S.condition >= 40 ? 1.0 : 0.6;
  const buffMod = S.buff ? 1.5 : 1.0;
  S.buff = false;
  let gain = rand(2.2, 4.2) * S.talents[def.key] * r.growth * condMod * buffMod;
  gain = Math.round(gain * 10) / 10;
  S.stats[def.key] = clamp(S.stats[def.key] + gain, 0, 100);
  S.condition = clamp(S.condition - randInt(12, 18), 0, 100);
  addLog(`${def.emoji} ${def.name} 훈련 완료! +${gain.toFixed(1)} (${Math.round(S.stats[def.key])})`);

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
  const r = regionOf();
  const events = [
    () => {
      const d = pick(STAT_DEFS[S.pos]);
      S.stats[d.key] = clamp(S.stats[d.key] + 3, 0, 100);
      addLog(`🧢 감독님의 특별 지도! ${d.name} +3`);
    },
    () => {
      const pts = Math.round(8 * r.spot);
      S.scout += pts;
      addLog(`📸 프로 스카우트가 연습 경기를 지켜봤어요! 주목도 +${pts}`);
    },
    () => {
      S.condition = clamp(S.condition - 20, 0, 100);
      addLog(`🤒 감기 몸살로 며칠 고생했어요. 컨디션 -20`);
    },
    () => {
      S.condition = clamp(S.condition + 12, 0, 100);
      addLog(`🍜 급식에 특식이 나왔어요! 컨디션 +12`);
    },
    () => {
      S.buff = true;
      addLog(`🔥 라이벌의 도발에 불이 붙었어요! 다음 훈련 효율 1.5배`);
    },
    () => {
      S.stats.stamina = clamp(S.stats.stamina + 2, 0, 100);
      addLog(`🏃 아침 러닝 습관이 몸에 붙었어요. 체력 +2`);
    },
  ];
  pick(events)();
}

// ---------- 월 진행 ----------
function endMonth() {
  save();
  renderMain();

  // 대회 달이면 대회 시작
  const tname = TOURNAMENTS[S.month];
  if (tname) {
    startTournament(tname);
    return;
  }
  advanceMonth();
}

function advanceMonth() {
  // 3학년 9월 = 드래프트
  if (S.year === 3 && S.month === 9) {
    showDraft();
    return;
  }
  S.month += 1;
  if (S.month === 13) S.month = 1;
  if (S.month === 3 && S.year < 3) S.year += 1;
  // 학년은 3월에 올라감 (1·2월은 겨울 훈련)
  save();
  renderMain();
}

// ---------- 대회 ----------
function startTournament(name) {
  tour = { name, round: 0, alive: true, totalPts: 0, results: [] };
  $("tour-title").textContent = `🏆 ${name} 전국고교야구대회`;
  $("tour-round").textContent = "";
  $("tour-card").innerHTML = `
    <div class="tour-vs">⚾ ${regionOf().school}, ${name} 출전!</div>
    <div class="tour-line">전국의 강호들과 겨룰 시간이에요.<br/>좋은 활약을 보이면 스카우트 주목도가 크게 올라요.</div>`;
  $("btn-tour-next").textContent = "1차전 시작";
  $("btn-tour-next").onclick = playTourGame;
  show("screen-tournament");
}

function playTourGame() {
  const r = regionOf();
  const roundName = ROUNDS[tour.round];
  const opp = pick(OPPONENTS);

  // 승률: 학교 전력 + 선수 능력 + 컨디션 - 라운드 페널티
  const p = clamp(
    r.win + (overall() - 50) / 130 + (S.condition - 50) / 700 - tour.round * 0.06,
    0.15, 0.92
  );
  const win = Math.random() < p;
  S.games += 1;

  // 개인 성적
  const perf = S.pos === "batter" ? batterLine() : pitcherLine();
  let pts = perf.pts + (win ? 4 : 1) + tour.round * 3;
  pts = Math.round(pts * r.spot);
  S.scout += pts;
  tour.totalPts += pts;
  S.condition = clamp(S.condition - 6, 0, 100);

  $("tour-round").textContent = `${roundName} vs ${opp}`;
  $("tour-card").innerHTML = `
    <div class="tour-vs">${r.school} <span class="${win ? "win" : "lose"}">${win ? "승리! 🎉" : "패배… 😢"}</span></div>
    <div class="tour-line">${perf.line}</div>
    ${perf.highlight ? `<div class="tour-line tour-highlight">${perf.highlight}</div>` : ""}
    <div class="tour-pts">🔭 스카우트 주목도 +${pts}</div>`;

  if (win && tour.round < ROUNDS.length - 1) {
    tour.round += 1;
    $("btn-tour-next").textContent = `${ROUNDS[tour.round]} 진출!`;
    $("btn-tour-next").onclick = playTourGame;
  } else {
    tour.alive = false;
    const champion = win && tour.round === ROUNDS.length - 1;
    if (champion) {
      S.trophies.push(`${S.year}학년 ${tour.name} 우승`);
      S.scout += 30;
      tour.totalPts += 30;
    }
    $("btn-tour-next").textContent = champion ? "🏆 우승 세리머니!" : "대회 마치기";
    $("btn-tour-next").onclick = () => finishTournament(champion, roundName);
  }
}

function finishTournament(champion, lastRound) {
  if (champion) {
    addLog(`🏆 ${tour.name} 우승!! 전국이 ${S.name}을(를) 주목해요. (주목도 +${tour.totalPts})`);
  } else {
    addLog(`🏟️ ${tour.name} ${lastRound}에서 마무리. (주목도 +${tour.totalPts})`);
  }
  tour = null;
  show("screen-main");
  advanceMonth();
}

function batterLine() {
  const ab = randInt(3, 5);
  let hits = 0, hr = 0, sb = 0;
  for (let i = 0; i < ab; i++) {
    if (Math.random() < 0.04 + S.stats.contact / 150) {
      hits++;
      if (Math.random() < S.stats.power / 260) hr++;
    }
  }
  if (hits > 0 && Math.random() < S.stats.run / 250) sb++;
  const pts = hits * 7 + hr * 16 + sb * 4 + Math.round(S.stats.defense / 25);
  const line = `${S.name}: ${ab}타수 ${hits}안타${hr ? ` ${hr}홈런` : ""}${sb ? ` ${sb}도루` : ""}`;
  let highlight = "";
  if (hr) highlight = "💥 담장을 넘기는 큼지막한 홈런! 관중석이 술렁여요.";
  else if (hits >= 3) highlight = "🔥 멀티히트를 넘어 맹타! 타격감이 뜨거워요.";
  else if (hits === 0 && Math.random() < 0.5) highlight = "😶 오늘은 방망이가 침묵했어요…";
  return { pts, line, highlight };
}

function pitcherLine() {
  const ip = clamp(3 + Math.floor(S.stats.stamina / 22) + randInt(-1, 1), 2, 8);
  const kRate = (S.stats.velocity + S.stats.breaking) / 2;
  const k = clamp(Math.round(ip * (0.4 + kRate / 90) + randInt(-1, 1)), 0, ip * 3);
  const runs = clamp(Math.round(ip * (0.9 - S.stats.control / 130) + randInt(-1, 1)), 0, 9);
  const pts = ip * 2 + k * 2.5 - runs * 2;
  const line = `${S.name}: ${ip}이닝 ${k}탈삼진 ${runs}실점`;
  let highlight = "";
  if (runs === 0 && ip >= 5) highlight = "🧊 압도적인 무실점 호투! 스카우트들이 수첩을 꺼내요.";
  else if (k >= ip * 1.5) highlight = "🔥 탈삼진 쇼! 상대 타자들이 방망이를 헛돌려요.";
  else if (runs >= 5) highlight = "😵 난타당한 하루… 다음을 기약해요.";
  return { pts: Math.max(pts, 2), line, highlight };
}

// ---------- 드래프트 ----------
function showDraft() {
  const r = regionOf();
  const score = S.scout + overall() * 2;
  const team = pick(r.teams);

  let emoji, title, teamLine, msg;
  if (score >= 660) {
    emoji = "👑"; title = "1라운드 전체 상위 지명!";
    teamLine = `${team} 1라운드 지명`;
    msg = "전국이 주목한 최대어! 계약금이 역대급이라는 소문이 돌아요.";
  } else if (score >= 560) {
    emoji = "🌟"; title = "1라운드 지명!";
    teamLine = `${team} 1라운드 지명`;
    msg = "연고 구단이 1라운드에서 호명! 홈 팬들의 환호가 쏟아져요.";
  } else if (score >= 450) {
    emoji = "🎉"; title = "상위 라운드 지명!";
    teamLine = `${team} 2~4라운드 지명`;
    msg = "당당히 프로 유니폼을 입어요. 1군 데뷔가 머지않았어요.";
  } else if (score >= 360) {
    emoji = "🧢"; title = "중·하위 라운드 지명";
    teamLine = `${team} 5~10라운드 지명`;
    msg = "프로의 문을 통과! 여기서부터가 진짜 시작이에요.";
  } else if (score >= 300) {
    emoji = "🌱"; title = "육성선수 계약";
    teamLine = `${team} 육성선수 입단`;
    msg = "정식 지명은 아니지만 기회는 있어요. 흙 속의 진주가 되어봐요.";
  } else {
    emoji = "🎓"; title = "지명 소식이 없었어요…";
    teamLine = "대학 진학 후 재도전";
    msg = "아쉽지만 야구 인생은 길어요. 4년 뒤 대졸 드래프트를 노려봐요!";
  }

  const statLines = STAT_DEFS[S.pos]
    .map((d) => `${d.emoji} ${d.name} ${Math.round(S.stats[d.key])}`)
    .join(" · ");
  const trophyLine = S.trophies.length
    ? `🏆 ${S.trophies.join(", ")}`
    : "🏆 우승 경력 없음";

  $("draft-card").innerHTML = `
    <div class="draft-emoji">${emoji}</div>
    <div class="draft-title">${title}</div>
    <div class="draft-team">${teamLine}</div>
    <div>${msg}</div>
    <div class="draft-summary">
      ${regionOf().emoji} ${r.school} · ${S.pos === "batter" ? "타자" : "투수"} ${S.name}<br/>
      ${statLines}<br/>
      🔭 최종 주목도 ${Math.round(S.scout)} · 대회 ${S.games}경기 출전<br/>
      ${trophyLine}
    </div>`;

  $("btn-share").onclick = () => {
    const text = `⚾ 더 루키 결과\n${r.school} ${S.name} — ${title}\n${teamLine}\n주목도 ${Math.round(S.scout)} / ${trophyLine}`;
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
  show("screen-draft");
}

// ---------- 시작 ----------
initTitle();
