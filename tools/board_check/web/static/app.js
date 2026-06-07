// ESP32-S3 보드 진단 대시보드 프런트엔드.
// 백엔드(app.py)와 REST(/api/*) + WebSocket(/ws)으로 통신한다.

let ws = null;
let labels = {};          // check key -> 라벨
let currentPort = null;   // 현재 진단/모니터 중인 포트
let liveOn = false;
let diagnosing = false;
let diagBtns = [];        // 보드별 "진단 시작" 버튼들

const $ = (id) => document.getElementById(id);

// 검사 항목 아이콘.
const ICONS = {
  usb_detection: "🔌", uart_connection: "🔗", bootloader_access: "⚙️",
  flash_access: "💾", flash_size: "📦", psram: "🧠", rgb_led: "🌈",
  boot_button: "🔘", wifi_scan: "📶", wifi_connect: "🌐", ble: "🔵",
  temperature: "🌡️", gpio: "📍",
};

// ---- 초기화 ----------------------------------------------------------------
window.addEventListener("DOMContentLoaded", async () => {
  $("btn-refresh").addEventListener("click", loadBoards);
  $("btn-live").addEventListener("click", toggleLive);
  await loadStatus();
  await loadBoards();
  connectWs();
});

async function loadStatus() {
  try {
    const r = await fetch("/api/status");
    const s = await r.json();
    labels = s.check_labels || {};
    const b = $("fw-status");
    if (s.firmware_available) {
      b.textContent = "✓ 진단 펌웨어 준비됨";
      b.className = "badge ok";
    } else {
      b.textContent = "✗ 펌웨어 없음 — step01 빌드 필요";
      b.className = "badge no";
    }
  } catch (e) {
    $("fw-status").textContent = "상태 조회 실패";
  }
}

async function loadBoards() {
  const list = $("board-list");
  list.textContent = "탐색 중…";
  diagBtns = [];
  try {
    const r = await fetch("/api/boards");
    const data = await r.json();
    const boards = data.boards || [];
    if (!boards.length) {
      list.innerHTML =
        '<div class="empty">연결된 보드가 없습니다. USB 케이블을 확인하고 새로고침하세요.</div>';
      return;
    }
    list.innerHTML = "";
    boards.forEach((b) => {
      const card = document.createElement("div");
      card.className = "board-card";
      const acc = b.accessible ? "" : '<span class="tag warn">권한없음</span>';
      card.innerHTML = `
        <div class="board-meta">
          <div><span class="port">${b.port}</span>
            <span class="tag">${b.vid_pid || "?"}</span>${acc}</div>
          <div class="meta">${b.bridge || (b.is_espressif ? "Espressif" : "미확인 보드")}
            · 시리얼 ${b.serial || "-"}</div>
        </div>`;
      const btn = document.createElement("button");
      btn.className = "btn";
      btn.textContent = "▶ 진단 시작";
      btn.onclick = () => startDiagnose(b.port, btn);
      diagBtns.push(btn);
      card.appendChild(btn);
      list.appendChild(card);
    });
    if (diagnosing) setDiagBtns(false, null); // 진단 중이면 다시 비활성
  } catch (e) {
    list.textContent = "보드 탐색 실패: " + e;
  }
}

function setDiagBtns(enabled, activeBtn) {
  diagBtns.forEach((b) => {
    b.disabled = !enabled;
    if (enabled) {
      b.textContent = "▶ 진단 시작";
      b.classList.remove("loading");
    } else if (b === activeBtn) {
      b.textContent = "⏳ 진단 진행중…";
      b.classList.add("loading");
    } else {
      b.textContent = "▶ 진단 시작";
    }
  });
}

// ---- WebSocket -------------------------------------------------------------
function connectWs() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.onmessage = (ev) => handleMsg(JSON.parse(ev.data));
  ws.onclose = () => setTimeout(connectWs, 1500); // 자동 재연결
}

function send(obj) {
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(obj));
}

// ---- 진단 진행 단계(시각화) ------------------------------------------------
const STEPS = [
  { key: "usb", label: "USB·포트 확인", match: ["USB 감지", "UART 연결"] },
  { key: "chip", label: "칩·Flash 검사", match: ["칩 정보", "Flash 접근"] },
  { key: "fw", label: "펌웨어 flash + 런타임 검사", match: ["펌웨어 flash"] },
  { key: "done", label: "결과 정리", match: ["결과:"] },
];
let elapsedTimer = null;
let startTime = 0;

function startDiagnose(port, btn) {
  if (diagnosing) return;
  diagnosing = true;
  currentPort = port;
  stopLive();
  setDiagBtns(false, btn);
  $("progress-panel").hidden = false;
  $("result-panel").hidden = true;
  $("phase-text").textContent = "진단 시작…";
  $("phase-sub").textContent = `${port} · 보드 flash + 검사로 20~40초 걸립니다`;
  $("spinner").classList.remove("done");
  renderSteps(-1);
  setBar(0);
  startElapsed();
  send({ action: "diagnose", port: port });
}

function renderSteps(activeIdx) {
  const box = $("steps");
  box.innerHTML = "";
  STEPS.forEach((s, i) => {
    const state = i < activeIdx ? "done" : i === activeIdx ? "active" : "pending";
    const icon = state === "done" ? "✓" : "";
    const el = document.createElement("div");
    el.className = "step " + state;
    el.innerHTML = `<span class="step-ic">${icon}</span><span>${s.label}</span>`;
    box.appendChild(el);
  });
}

function setBar(pct) { $("bar-fill").style.width = pct + "%"; }

function startElapsed() {
  startTime = Date.now();
  stopElapsed();
  elapsedTimer = setInterval(() => {
    $("elapsed").textContent = Math.round((Date.now() - startTime) / 1000) + "초";
  }, 500);
}
function stopElapsed() { if (elapsedTimer) { clearInterval(elapsedTimer); elapsedTimer = null; } }

function setPhase(rawMsg) {
  const action = rawMsg.replace(/^\[[^\]]*\]\s*/, ""); // 보드 prefix 제거
  $("phase-text").textContent = action;
  const idx = STEPS.findIndex((s) => s.match.some((m) => action.includes(m)));
  if (idx >= 0) {
    renderSteps(idx);
    setBar(Math.round(((idx + 1) / STEPS.length) * 100));
  }
}

function finishProgress() {
  stopElapsed();
  renderSteps(STEPS.length);
  setBar(100);
  $("spinner").classList.add("done");
  $("phase-text").textContent = "완료";
}

function handleMsg(msg) {
  if (msg.type === "progress") {
    setPhase(msg.msg);
  } else if (msg.type === "result") {
    diagnosing = false;
    setDiagBtns(true, null);
    finishProgress();
    renderResult(msg.data);
    setTimeout(() => { $("progress-panel").hidden = true; }, 700);
    // 결과 후 RGB LED 라이브 모니터 자동 시작.
    startLive();
  } else if (msg.type === "live") {
    applyLive(msg.data);
  } else if (msg.type === "live_stopped") {
    liveOn = false;
    $("btn-live").textContent = "▶ 라이브 모니터";
    $("led-indicator").classList.remove("live");
  } else if (msg.type === "error") {
    diagnosing = false;
    setDiagBtns(true, null);
    stopElapsed();
    $("spinner").classList.add("done");
    $("phase-text").textContent = "오류: " + msg.msg;
  }
}

// ---- 결과 렌더링 -----------------------------------------------------------
function renderResult(res) {
  $("result-panel").hidden = false;

  const checks = res.checks || {};
  // 요약 카운트
  let pass = 0, fail = 0, skip = 0;
  Object.values(checks).forEach((c) => {
    if (c.status === "PASS") pass++;
    else if (c.status === "FAIL") fail++;
    else skip++;
  });
  const ob = $("overall-badge");
  ob.textContent = res.overall === "PASS" ? "✓ PASS" : "✗ FAIL";
  ob.className = "overall " + (res.overall || "");
  $("counts").innerHTML =
    `<span class="cnt pass">● ${pass} PASS</span>` +
    `<span class="cnt fail">● ${fail} FAIL</span>` +
    `<span class="cnt skip">● ${skip} SKIP</span>`;

  // 보드 정보
  const usb = res.usb || {};
  const chip = res.chip || {};
  $("board-info").innerHTML = `
    <div><b>Port</b> ${res.port || ""}</div>
    <div><b>VID:PID</b> ${usb.vid_pid || ""}</div>
    <div><b>Serial</b> ${usb.serial || "-"}</div>
    <div><b>Chip</b> ${chip.chip || "-"} (rev ${chip.revision ?? "-"})</div>
    <div><b>MAC</b> ${chip.mac || "-"}</div>
    <div><b>Flash</b> ${chip.flash_size || "-"}</div>`;

  // 검사 항목 카드 그리드
  const order = Object.keys(labels).length ? Object.keys(labels) : Object.keys(checks);
  const box = $("checks");
  box.innerHTML = "";
  order.forEach((key) => {
    const c = checks[key];
    if (!c) return;
    const card = document.createElement("div");
    card.className = "check-card " + c.status;
    card.dataset.key = key;
    card.innerHTML = `
      <div class="cc-top">
        <span class="cc-icon">${ICONS[key] || "•"}</span>
        <span class="cc-label">${labels[key] || key}</span>
        <span class="dot ${c.status}"></span>
      </div>
      <div class="cc-detail">${escapeHtml(c.detail || "")}</div>`;
    box.appendChild(card);
  });

  renderWifi(checks.wifi_scan);
  renderBle(checks.ble);

  // BOOT 버튼 가이드 표시(라이브로 눌림 확인).
  const guide = $("btn-guide");
  guide.hidden = false;
  guide.className = "btn-guide waiting";
  $("btn-guide-title").textContent = "🔘 BOOT 버튼을 눌러보세요";
  $("btn-guide-sub").textContent = "보드의 BOOT 버튼을 누르면 여기에 표시됩니다 (라이브)";

  $("btn-live").disabled = false;
}

function renderWifi(c) {
  const box = $("wifi-box"), list = $("wifi-list");
  const aps = (c && c.aps) || [];
  if (!aps.length) { box.hidden = true; return; }
  box.hidden = false;
  $("wifi-count").textContent = `${aps.length}개`;
  list.innerHTML = "";
  aps.forEach((a) => list.appendChild(scanRow(a.ssid || "<숨김 SSID>", a.rssi, `ch${a.ch}`)));
}

function renderBle(c) {
  const box = $("ble-box"), list = $("ble-list");
  const devs = (c && c.ble_list) || [];
  if (!devs.length) { box.hidden = true; return; }
  box.hidden = false;
  $("ble-count").textContent = `${devs.length}개`;
  list.innerHTML = "";
  devs.forEach((d) => list.appendChild(scanRow(d.name || "<이름없음>", d.rssi, d.addr || "")));
}

function scanRow(name, rssi, right) {
  const row = document.createElement("div");
  row.className = "scan-row";
  row.innerHTML = `
    ${signalBars(rssi)}
    <span class="name">${escapeHtml(name)}</span>
    <span class="rssi">${rssi ?? "?"} dBm</span>
    <span class="ch">${escapeHtml(String(right))}</span>`;
  return row;
}

function signalBars(rssi) {
  let level = 0;
  if (rssi >= -50) level = 4;
  else if (rssi >= -60) level = 3;
  else if (rssi >= -70) level = 2;
  else if (rssi >= -80) level = 1;
  let html = '<span class="bars">';
  for (let i = 1; i <= 4; i++) html += `<i class="${i <= level ? "on" : ""}"></i>`;
  return html + "</span>";
}

// ---- 라이브 모니터 ---------------------------------------------------------
function toggleLive() { if (liveOn) stopLive(); else startLive(); }

function startLive() {
  if (!currentPort || liveOn) return;
  liveOn = true;
  $("btn-live").textContent = "⏸ 라이브 중지";
  $("led-indicator").classList.add("live");
  send({ action: "start_live", port: currentPort });
}

function stopLive() {
  if (!liveOn) return;
  liveOn = false;
  $("btn-live").textContent = "▶ 라이브 모니터";
  $("led-indicator").classList.remove("live");
  send({ action: "stop_live" });
}

// 라이브 사이클 도착 → 빠르게 변하는 값(버튼/온도) + 버튼 가이드 갱신.
function applyLive(cyc) {
  if (cyc.button) {
    updateCard("boot_button", liveButtonDetail(cyc.button), "PASS");
    updateButtonGuide(cyc.button);
  }
  if (cyc.temp && cyc.temp.ok) {
    updateCard("temperature", `${cyc.temp.celsius}°C (live)`, "PASS");
  }
}

function liveButtonDetail(b) {
  if (b.pressed_now) return "🔴 지금 눌림 (live)";
  if (b.ever_pressed) return "✓ 눌린 적 있음 (live)";
  return `유휴(idle=${b.idle_level}) — 눌러보세요 (live)`;
}

function updateButtonGuide(b) {
  const g = $("btn-guide");
  if (b.pressed_now) {
    g.className = "btn-guide ok";
    $("btn-guide-title").textContent = "✓ 지금 눌림 감지!";
    $("btn-guide-sub").textContent = "BOOT 버튼이 정상 동작합니다";
  } else if (b.ever_pressed) {
    g.className = "btn-guide ok";
    $("btn-guide-title").textContent = "✓ BOOT 버튼 정상 (눌림 확인됨)";
    $("btn-guide-sub").textContent = "한 번 더 눌러도 됩니다";
  } else {
    g.className = "btn-guide waiting";
    $("btn-guide-title").textContent = "🔘 BOOT 버튼을 눌러보세요";
    $("btn-guide-sub").textContent = "보드의 BOOT 버튼을 누르면 여기에 표시됩니다 (라이브)";
  }
}

function updateCard(key, detail, status) {
  const card = document.querySelector(`.check-card[data-key="${key}"]`);
  if (!card) return;
  card.querySelector(".cc-detail").textContent = detail;
}

function escapeHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
