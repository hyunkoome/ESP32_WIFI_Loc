"use strict";

// CSI 통합 대시보드 프론트엔드.
//  - WebSocket(/ws) 으로 보드 감지(refresh) / role 자동표시 / tx·rx flash / CSI 스트림.
//  - 진폭·위상은 canvas 라인차트로 그린다(외부 차트 라이브러리 없음).

const $ = (id) => document.getElementById(id);

let ws = null;
let boards = [];          // [{port, serial, by_id, vid_pid, accessible, ...}]
let roles = {};           // port -> {role, source}
let streaming = false;

// ---- WebSocket -------------------------------------------------------------
function connectWs() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.onopen = () => {
    $("ws-status").textContent = "WebSocket: 연결됨";
    $("ws-status").className = "ws-on";
    refresh();
  };
  ws.onclose = () => {
    $("ws-status").textContent = "WebSocket: 끊김 — 재연결";
    $("ws-status").className = "ws-off";
    setTimeout(connectWs, 1500);
  };
  ws.onmessage = (ev) => handle(JSON.parse(ev.data));
}
function send(o) { if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(o)); }
function refresh() { $("board-list").textContent = "탐색 중…"; send({ action: "refresh" }); }

function handle(m) {
  if (m.type === "boards") {
    boards = m.boards; roles = {};
    renderBoards(); renderRxSelect();
  } else if (m.type === "role") {
    roles[m.port] = { role: m.role, source: m.source };
    renderBoards(); renderRxSelect();
  } else if (m.type === "flash_progress") {
    appendLog(m.line);
  } else if (m.type === "flash_done") {
    appendLog(m.ok ? `✓ flash 완료 (${m.port})` : `✗ flash 실패 (${m.port}) ${m.msg || ""}`);
  } else if (m.type === "csi") {
    drawCsi(m);
  } else if (m.type === "stream_stopped") {
    streaming = false; $("btn-stream").textContent = "▶ 스트림 시작";
    if (m.error) appendLog("스트림: " + m.error);
  }
}

// ---- 보드 카드 -------------------------------------------------------------
function renderBoards() {
  const box = $("board-list");
  if (!boards.length) { box.innerHTML = '<p class="hint">연결된 보드가 없습니다.</p>'; return; }
  box.innerHTML = "";
  for (const b of boards) {
    const r = roles[b.port];
    let badge;
    if (!r) badge = '<span class="badge detecting">감지중…</span>';
    else if (r.role === "tx") badge = '<span class="badge tx">TX</span>';
    else if (r.role === "rx") badge = '<span class="badge rx">RX</span>';
    else badge = '<span class="badge unknown">role?</span>';

    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML = `
      <div class="row">
        <span class="name">${b.port}</span>${badge}
      </div>
      <div class="meta">serial: ${b.serial || "-"} · ${b.vid_pid}${b.accessible ? "" : ' · <b class="warn">권한없음</b>'}</div>
      <div class="meta byid">${b.by_id || ""}</div>
      <div class="actions">
        <button class="btn-mini tx" data-port="${b.port}" data-role="tx">tx flash</button>
        <button class="btn-mini rx" data-port="${b.port}" data-role="rx">rx flash</button>
      </div>`;
    card.querySelectorAll(".actions .btn-mini").forEach((btn) => {
      btn.onclick = () => {
        const role = btn.dataset.role, port = btn.dataset.port;
        if (!confirm(`${port} 에 ${role} 펌웨어를 flash할까요? (보드의 기존 펌웨어를 덮어씁니다)`)) return;
        $("log-panel").hidden = false;
        appendLog(`--- flash ${role} → ${port} ---`);
        send({ action: "flash", role, port });
      };
    });
    box.appendChild(card);
  }
}

function renderRxSelect() {
  const sel = $("rx-select");
  const prev = sel.value;
  sel.innerHTML = "";
  for (const b of boards) {
    const r = roles[b.port];
    const opt = document.createElement("option");
    opt.value = b.port;
    opt.textContent = `${b.port}${r && r.role ? ` (${r.role})` : ""}`;
    sel.appendChild(opt);
  }
  if (prev) sel.value = prev;
}

// ---- CSI 차트 (진폭/위상) --------------------------------------------------
function drawCsi(m) {
  $("m-rate").textContent = m.rate;
  $("m-rssi").textContent = m.rssi;
  $("m-sub").textContent = m.n_sub;
  drawSeries($("amp-canvas"), m.amplitude, "#4aa3ff", true);
  drawSeries($("phase-canvas"), m.phase, "#f5a623", false, -Math.PI, Math.PI);
}

function drawSeries(cv, data, color, autoMax, fixedMin, fixedMax) {
  const ctx = cv.getContext("2d");
  const W = cv.width, H = cv.height;
  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = "#0f1115"; ctx.fillRect(0, 0, W, H);
  if (!data || !data.length) return;

  let mn = fixedMin !== undefined ? fixedMin : 0;
  let mx = fixedMax !== undefined ? fixedMax : 1;
  if (autoMax) { mx = Math.max(1, ...data); mn = 0; }
  const range = (mx - mn) || 1;

  // 0(또는 중앙) 기준선
  ctx.strokeStyle = "#2a2f3a";
  ctx.beginPath();
  const zeroY = H - ((0 - mn) / range) * H;
  ctx.moveTo(0, zeroY); ctx.lineTo(W, zeroY); ctx.stroke();

  // 데이터 라인
  ctx.strokeStyle = color; ctx.lineWidth = 1.5;
  ctx.beginPath();
  data.forEach((v, i) => {
    const x = (i / (data.length - 1)) * W;
    const y = H - ((v - mn) / range) * H;
    i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
  });
  ctx.stroke();
}

// ---- flash 로그 ------------------------------------------------------------
function appendLog(line) {
  const el = $("flash-log");
  el.textContent += line + "\n";
  el.scrollTop = el.scrollHeight;
}

// ---- 이벤트 ----------------------------------------------------------------
$("btn-refresh").onclick = refresh;
$("btn-log-clear").onclick = () => { $("flash-log").textContent = ""; };
$("btn-stream").onclick = () => {
  if (streaming) {
    send({ action: "stream_stop" });
    streaming = false; $("btn-stream").textContent = "▶ 스트림 시작";
  } else {
    const port = $("rx-select").value;
    if (!port) { alert("rx 보드를 선택하세요"); return; }
    streaming = true; $("btn-stream").textContent = "⏸ 중지";
    send({ action: "stream_start", port });
  }
};

connectWs();
