"use strict";

// CSI 통합 웹 대시보드 프런트엔드 — csi/gui(PyQt) 데스크톱 GUI 의 웹 포팅.
//  - WebSocket(/ws) 으로 보드 감지/role/flash/신호원/로깅/학습/3상태/방상태 voting 을 처리.
//  - rx 가 감지되면 카드(amplitude/phase/waterfall/doppler 차트)를 동적 생성한다.
//  - 차트는 외부 라이브러리 없이 canvas 로 직접 그린다(서버가 보내는 숫자 배열 사용).
//  - 메트릭/3상태/voting 계산은 서버(csi/common/classifier.py)가 GUI 와 동일하게 수행.

const $ = (id) => document.getElementById(id);

let ws = null;
let boards = [];          // [{port, serial, by_id, vid_pid, accessible, ...}]
let roles = {};           // port -> {role, source}
const rxCards = {};       // port -> {el, ctx{amp,phase,wf,dop}, serial}
let loggingMode = null;   // 공용 로깅 토글 상태(null | empty | presence | motion)
const moveTimes = [];     // 최근 1분 움직임 이벤트 타임스탬프(분당 카운트)

// 3상태 표시 정보(GUI 와 동일 이모지/색/라벨).
const STATE_INFO = {
  empty:    { label: "⚪ Empty",    color: "#888888" },
  presence: { label: "🔵 Presence", color: "#4aa3ff" },
  motion:   { label: "🟢 Motion",   color: "#2ecc71" },
};

// ---- WebSocket -------------------------------------------------------------
function connectWs() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.onopen = () => {
    $("ws-status").textContent = "WebSocket: on";
    $("ws-status").className = "ws-on";
    refresh();
  };
  ws.onclose = () => {
    $("ws-status").textContent = "WebSocket: off — reconnecting";
    $("ws-status").className = "ws-off";
    setTimeout(connectWs, 1500);
  };
  ws.onmessage = (ev) => handle(JSON.parse(ev.data));
}
function send(o) { if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(o)); }
function refresh() { $("board-list").textContent = "Detecting…"; send({ action: "refresh" }); }

function handle(m) {
  switch (m.type) {
    case "boards":       boards = m.boards; roles = {}; renderBoards(); break;
    case "role":         roles[m.port] = { role: m.role, source: m.source }; renderBoards(); break;
    case "flash_progress": appendLog(m.line); break;
    case "flash_done":   appendLog(m.ok ? `✓ flash done (${m.port})` : `✗ flash failed (${m.port}) ${m.msg || ""}`); break;
    case "rx_added":     addRxCard(m.port, m.serial, m.source); break;
    case "rx_removed":   removeRxCard(m.port); break;
    case "csi":          drawRx(m); break;
    case "room":         renderRoom(m.room, m.rx_states); break;
    case "move_event":   onMoveEvent(m.serial, m.doppler, m.ts); break;
    case "mode":         renderMode(m.mode, m.detail); break;
    case "log":          appendLog(m.line); break;
    case "stream_status": appendLog(m.msg); break;
    case "stream_stopped": if (m.error) appendLog(`[${m.port}] stream: ${m.error}`); break;
    case "need_wifi":    appendLog("→ Enter router SSID/password in the Wi-Fi panel above."); break;
    default: break;
  }
}

// ---- 보드 카드 -------------------------------------------------------------
function renderBoards() {
  const box = $("board-list");
  if (!boards.length) { box.innerHTML = '<p class="hint">No boards connected.</p>'; return; }
  box.innerHTML = "";
  for (const b of boards) {
    const r = roles[b.port];
    let badge;
    if (!r) badge = '<span class="badge detecting">detecting…</span>';
    else if (r.role === "tx") badge = '<span class="badge tx">TX</span>';
    else if (r.role === "rx") badge = '<span class="badge rx">RX</span>';
    else badge = '<span class="badge unknown">role?</span>';

    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML = `
      <div class="row">
        <span class="name">${b.port}</span>${badge}
      </div>
      <div class="meta">serial: ${b.serial || "-"} · ${b.vid_pid}${b.accessible ? "" : ' · <b class="warn">no permission</b>'}</div>
      <div class="meta byid">${b.by_id || ""}</div>
      <div class="actions">
        <button class="btn-mini tx" data-port="${b.port}" data-role="tx">tx flash</button>
        <button class="btn-mini rx" data-port="${b.port}" data-role="rx">rx flash</button>
      </div>`;
    card.querySelectorAll(".actions .btn-mini").forEach((btn) => {
      btn.onclick = () => {
        const role = btn.dataset.role, port = btn.dataset.port;
        if (!confirm(`Flash ${role} firmware to ${port}? (overwrites existing firmware)`)) return;
        appendLog(`--- flash ${role} → ${port} ---`);
        send({ action: "flash", role, port });
      };
    });
    box.appendChild(card);
  }
}

// ---- rx 카드(차트) 생성/제거 ----------------------------------------------
function addRxCard(port, serial, source) {
  if (rxCards[port]) return;
  $("no-rx").hidden = true;
  const tpl = $("rx-card-tpl").content.cloneNode(true);
  const el = tpl.querySelector(".rx-card");
  el.querySelector(".rx-title").textContent = `rx: ${serial ? serial.slice(-4) : port} (${port})`;
  const sel = el.querySelector(".rx-source");
  sel.value = source;   // 첫 rx=router, 그 외 tx (서버가 결정해 보내준 값)
  sel.onchange = () => send({ action: "set_source", port, source: sel.value });
  $("rx-cards").appendChild(el);
  rxCards[port] = {
    el, serial,
    ctx: {
      amp: el.querySelector(".amp").getContext("2d"),
      phase: el.querySelector(".phase").getContext("2d"),
      wf: el.querySelector(".waterfall").getContext("2d"),
      dop: el.querySelector(".doppler").getContext("2d"),
    },
    stats: el.querySelector(".rx-stats"),
    state: el.querySelector(".rx-state"),
  };
}

function removeRxCard(port) {
  const c = rxCards[port];
  if (!c) return;
  c.el.remove();
  delete rxCards[port];
  if (!Object.keys(rxCards).length) $("no-rx").hidden = false;
}

// ---- rx 차트 그리기 --------------------------------------------------------
function drawRx(m) {
  const c = rxCards[m.port];
  if (!c) return;
  // 메트릭 라인(GUI lbl_stats 와 동일 포맷).
  c.stats.textContent = `[${m.source}] rate ${fmt(m.rate)} RSSI ${m.rssi}  |  ` +
    `std(presence) ${fmt(m.std)}   doppler(motion) ${fmt(m.doppler)}`;
  // 3상태 라벨(GUI lbl_state: "⚪ Empty  (w std/std_th, j dop/dop_th)").
  const info = STATE_INFO[m.state] || STATE_INFO.empty;
  c.state.textContent = `${info.label}  (w ${fmt(m.std)}/${fmt(m.std_th)}, j ${Math.round(m.doppler)}/${Math.round(m.doppler_th)})`;
  c.state.style.color = info.color;

  drawSeries(c.ctx.amp, m.amplitude, "#4aa3ff", true);
  drawSeries(c.ctx.phase, m.phase, "#f5a623", false, -Math.PI, Math.PI);
  drawWaterfall(c.ctx.wf, m.waterfall);
  drawDoppler(c.ctx.dop, m.doppler_freqs, m.doppler_mags);
}

function fmt(v) { return (typeof v === "number") ? v.toFixed(2) : v; }

function drawSeries(ctx, data, color, autoMax, fixedMin, fixedMax) {
  const cv = ctx.canvas, W = cv.width, H = cv.height;
  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = "#0f1115"; ctx.fillRect(0, 0, W, H);
  if (!data || !data.length) return;
  let mn = fixedMin !== undefined ? fixedMin : 0;
  let mx = fixedMax !== undefined ? fixedMax : 1;
  if (autoMax) { mx = Math.max(1, ...data); mn = 0; }
  const range = (mx - mn) || 1;
  ctx.strokeStyle = "#2a2f3a";
  ctx.beginPath();
  const zeroY = H - ((0 - mn) / range) * H;
  ctx.moveTo(0, zeroY); ctx.lineTo(W, zeroY); ctx.stroke();
  ctx.strokeStyle = color; ctx.lineWidth = 1.5;
  ctx.beginPath();
  data.forEach((v, i) => {
    const x = (i / (data.length - 1)) * W;
    const y = H - ((v - mn) / range) * H;
    i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
  });
  ctx.stroke();
}

// 워터폴: 2D 배열(시간 × 서브캐리어)을 viridis 비슷한 컬러맵으로. 마지막 행이 최신 → 위.
function drawWaterfall(ctx, wf) {
  const cv = ctx.canvas, W = cv.width, H = cv.height;
  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = "#0f1115"; ctx.fillRect(0, 0, W, H);
  if (!wf || !wf.length || !wf[0].length) return;
  const rows = wf.length, cols = wf[0].length;
  // 자동 레벨(GUI autoLevels).
  let lo = Infinity, hi = -Infinity;
  for (const row of wf) for (const v of row) { if (v < lo) lo = v; if (v > hi) hi = v; }
  const rng = (hi - lo) || 1;
  const img = ctx.createImageData(W, H);
  for (let y = 0; y < H; y++) {
    // 위(y=0)가 최신: 마지막 행을 위로.
    const r = rows - 1 - Math.floor((y / H) * rows);
    const row = wf[Math.max(0, Math.min(rows - 1, r))];
    for (let x = 0; x < W; x++) {
      const c = Math.min(cols - 1, Math.floor((x / W) * cols));
      const t = (row[c] - lo) / rng;
      const [rr, gg, bb] = viridis(t);
      const idx = (y * W + x) * 4;
      img.data[idx] = rr; img.data[idx + 1] = gg; img.data[idx + 2] = bb; img.data[idx + 3] = 255;
    }
  }
  ctx.putImageData(img, 0, 0);
}

// 간이 viridis 컬러맵(0~1 → rgb). pyqtgraph viridis 근사.
function viridis(t) {
  t = Math.max(0, Math.min(1, t));
  const stops = [
    [68, 1, 84], [59, 82, 139], [33, 145, 140], [94, 201, 98], [253, 231, 37],
  ];
  const s = t * (stops.length - 1);
  const i = Math.floor(s), f = s - i;
  const a = stops[i], b = stops[Math.min(stops.length - 1, i + 1)];
  return [Math.round(a[0] + (b[0] - a[0]) * f),
          Math.round(a[1] + (b[1] - a[1]) * f),
          Math.round(a[2] + (b[2] - a[2]) * f)];
}

// 도플러 스펙트럼: stem(각 주파수 빈에 수직선 + 끝점). x: 0~10Hz 고정.
function drawDoppler(ctx, freqs, mags) {
  const cv = ctx.canvas, W = cv.width, H = cv.height;
  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = "#0f1115"; ctx.fillRect(0, 0, W, H);
  if (!freqs || !freqs.length || !mags || !mags.length) return;
  const xmax = 10.0;
  const ymax = Math.max(30, Math.max(...mags) * 1.3);
  ctx.strokeStyle = "#2ecc71"; ctx.fillStyle = "#2ecc71"; ctx.lineWidth = 1.5;
  for (let i = 0; i < freqs.length; i++) {
    const x = (freqs[i] / xmax) * W;
    const y = H - (mags[i] / ymax) * H;
    ctx.beginPath(); ctx.moveTo(x, H); ctx.lineTo(x, y); ctx.stroke();
    ctx.beginPath(); ctx.arc(x, y, 2.5, 0, Math.PI * 2); ctx.fill();
  }
}

// ---- Space Monitoring(방 상태 voting + rx 상태) ---------------------------
function renderRoom(room, rxStates) {
  const info = STATE_INFO[room] || STATE_INFO.empty;
  const el = $("room-state");
  el.textContent = `ROOM: ${info.label}`;
  el.className = `room ${room}`;
  // rx 별 현재 상태(가로 배치).
  const row = $("rx-state-row");
  row.innerHTML = "";
  for (const [serial, st] of Object.entries(rxStates || {})) {
    const si = STATE_INFO[st] || STATE_INFO.empty;
    const span = document.createElement("span");
    span.className = "rx-pill";
    span.style.color = si.color;
    span.textContent = `${serial.slice(-4)}: ${si.label}`;
    row.appendChild(span);
  }
}

function onMoveEvent(serial, doppler, ts) {
  const el = $("event-log");
  el.textContent += `${ts}   [${serial.slice(-4)}]   Motion (doppler ${fmt(doppler)})\n`;
  el.scrollTop = el.scrollHeight;
  const now = Date.now();
  moveTimes.push(now);
  while (moveTimes.length && now - moveTimes[0] > 60000) moveTimes.shift();
  $("motion-count").textContent = `Motion in last 1 min: ${moveTimes.length}`;
}

// ---- 모드 표시(Idle/Logging/Detecting) ------------------------------------
function renderMode(mode, detail) {
  const el = $("mode-badge");
  if (mode === "logging") {
    el.textContent = `⏺ Logging ${detail}…`; el.className = "mode-logging";
  } else if (mode === "detecting") {
    el.textContent = "🟢 Detecting (live)"; el.className = "mode-detecting";
  } else {
    el.textContent = "⏸ Idle"; el.className = "mode-idle";
  }
}

// ---- 공용 로깅 토글 --------------------------------------------------------
function setLogButtons() {
  document.querySelectorAll(".btn-log").forEach((b) => {
    const m = b.dataset.mode;
    if (loggingMode === null) {
      b.disabled = false;
      b.textContent = `Log ${cap(m)}`;
      b.classList.remove("active");
    } else if (loggingMode === m) {
      b.disabled = false;
      b.textContent = `⏺ ${cap(m)} (click to finish)`;
      b.classList.add("active");
    } else {
      b.disabled = true;
      b.classList.remove("active");
    }
  });
  $("btn-train").disabled = loggingMode !== null;
}
function cap(s) { return s.charAt(0).toUpperCase() + s.slice(1); }

document.querySelectorAll(".btn-log").forEach((b) => {
  b.onclick = () => {
    const mode = b.dataset.mode;
    if (loggingMode === null) {
      if (!Object.keys(rxCards).length) { appendLog("No rx to log (connect/detect an rx board first)."); return; }
      loggingMode = mode;
      send({ action: "log_start", mode });
    } else if (loggingMode === mode) {
      loggingMode = null;
      send({ action: "log_stop" });
    }
    setLogButtons();
  };
});

// ---- 로그 ------------------------------------------------------------------
function appendLog(line) {
  const el = $("flash-log");
  el.textContent += line + "\n";
  el.scrollTop = el.scrollHeight;
}

// ---- 이벤트 ----------------------------------------------------------------
$("btn-refresh").onclick = refresh;
$("btn-log-clear").onclick = () => { $("flash-log").textContent = ""; };
$("btn-train").onclick = () => send({ action: "train" });
$("btn-wifi").onclick = () => {
  send({ action: "set_wifi", ssid: $("wifi-ssid").value, password: $("wifi-pw").value });
};

setLogButtons();
connectWs();
