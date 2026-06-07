// ESP32-S3 보드 진단 대시보드 프런트엔드.
// 백엔드(app.py)와 REST(/api/*) + WebSocket(/ws)으로 통신한다.

let ws = null;
let labels = {};
let currentPort = null;
let liveOn = false;
let diagnosing = false;
let diagBtns = [];
let lastChecks = {};          // 마지막 진단 결과(WiFi/BLE 탭에서 사용)
let pendingConnectSsid = null; // 접속 시도 중인 SSID

const $ = (id) => document.getElementById(id);
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
  document.querySelectorAll(".tab").forEach((t) =>
    t.addEventListener("click", () => switchTab(t.dataset.tab)));
  await loadStatus();
  renderSkeleton();
  await loadBoards();
  connectWs();
});

function switchTab(name) {
  document.querySelectorAll(".tab").forEach((t) =>
    t.classList.toggle("active", t.dataset.tab === name));
  document.querySelectorAll(".tab-page").forEach((p) =>
    p.classList.toggle("active", p.id === "page-" + name));
}

async function loadStatus() {
  try {
    const s = await (await fetch("/api/status")).json();
    labels = s.check_labels || {};
    const b = $("fw-status");
    if (s.firmware_available) { b.textContent = "✓ 진단 펌웨어 준비됨"; b.className = "badge ok"; }
    else { b.textContent = "✗ 펌웨어 없음 — step01 빌드 필요"; b.className = "badge no"; }
  } catch (e) { $("fw-status").textContent = "상태 조회 실패"; }
}

async function loadBoards() {
  const list = $("board-list");
  list.textContent = "탐색 중…";
  diagBtns = [];
  try {
    const data = await (await fetch("/api/boards")).json();
    const boards = data.boards || [];
    if (!boards.length) {
      list.innerHTML = '<div class="empty">연결된 보드가 없습니다. USB 케이블을 확인하고 새로고침하세요.</div>';
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
          <div class="meta">${b.bridge || (b.is_espressif ? "Espressif" : "미확인 보드")} · 시리얼 ${b.serial || "-"}</div>
        </div>`;
      const btn = document.createElement("button");
      btn.className = "btn";
      btn.textContent = "▶ 진단 시작";
      btn.onclick = () => startDiagnose(b.port, btn);
      diagBtns.push(btn);
      card.appendChild(btn);
      list.appendChild(card);
    });
    if (diagnosing) setDiagBtns(false, null);
  } catch (e) { list.textContent = "보드 탐색 실패: " + e; }
}

function setDiagBtns(enabled, activeBtn) {
  diagBtns.forEach((b) => {
    b.disabled = !enabled;
    b.textContent = (!enabled && b === activeBtn) ? "⏳ 진단 진행중…" : "▶ 진단 시작";
    b.classList.toggle("loading", !enabled && b === activeBtn);
  });
}

// ---- 스켈레톤(결과 전 미리 카드 배치) --------------------------------------
function renderSkeleton() {
  const order = Object.keys(labels);
  const box = $("checks");
  box.innerHTML = "";
  order.forEach((key) => box.appendChild(makeCard(key, "SKIP", "대기 중…")));
}

function makeCard(key, status, detail) {
  const card = document.createElement("div");
  card.className = "check-card " + status;
  card.dataset.key = key;
  const swatch = key === "rgb_led" ? '<span class="cc-swatch" id="led-swatch"></span>' : "";
  card.innerHTML = `
    <div class="cc-top">
      <span class="cc-icon">${ICONS[key] || "•"}</span>
      <span class="cc-label">${labels[key] || key}</span>
      ${swatch}
      <span class="dot ${status}"></span>
    </div>
    <div class="cc-detail">${escapeHtml(detail)}</div>`;
  return card;
}

function updateCard(key, status, detail) {
  let card = document.querySelector(`.check-card[data-key="${key}"]`);
  if (!card) { card = makeCard(key, status, detail); $("checks").appendChild(card); }
  if (status) {
    card.className = "check-card " + status;
    const dot = card.querySelector(".dot");
    if (dot) dot.className = "dot " + status;
  }
  if (detail != null) card.querySelector(".cc-detail").textContent = detail;
  return card;
}

// ---- WebSocket -------------------------------------------------------------
function connectWs() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.onmessage = (ev) => handleMsg(JSON.parse(ev.data));
  ws.onclose = () => setTimeout(connectWs, 1500);
}
function send(obj) { if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(obj)); }

// ---- 진행 단계 -------------------------------------------------------------
const STEPS = [
  { key: "usb", label: "USB·포트 확인", match: ["USB 감지", "UART 연결"] },
  { key: "chip", label: "칩·Flash 검사", match: ["칩 정보", "Flash 접근"] },
  { key: "fw", label: "펌웨어 flash + 런타임 검사", match: ["펌웨어 flash"] },
  { key: "done", label: "결과 정리", match: ["결과:"] },
];
let elapsedTimer = null, startTime = 0;

function startDiagnose(port, btn) {
  if (diagnosing) return;
  diagnosing = true;
  currentPort = port;
  stopLive();
  setDiagBtns(false, btn);
  $("progress-panel").hidden = false;
  $("phase-text").textContent = "진단 시작…";
  $("phase-sub").textContent = `${port} · 보드 flash + 검사로 20~40초 걸립니다`;
  $("spinner").classList.remove("done");
  $("overall-badge").textContent = "진단 중…";
  $("overall-badge").className = "overall pending";
  renderSkeleton();
  renderSteps(-1); setBar(0); startElapsed();
  send({ action: "diagnose", port });
}

function renderSteps(activeIdx) {
  const box = $("steps"); box.innerHTML = "";
  STEPS.forEach((s, i) => {
    const state = i < activeIdx ? "done" : i === activeIdx ? "active" : "pending";
    const el = document.createElement("div");
    el.className = "step " + state;
    el.innerHTML = `<span class="step-ic">${state === "done" ? "✓" : ""}</span><span>${s.label}</span>`;
    box.appendChild(el);
  });
}
function setBar(pct) { $("bar-fill").style.width = pct + "%"; }
function startElapsed() {
  startTime = Date.now(); stopElapsed();
  elapsedTimer = setInterval(() => {
    $("elapsed").textContent = Math.round((Date.now() - startTime) / 1000) + "초";
  }, 500);
}
function stopElapsed() { if (elapsedTimer) { clearInterval(elapsedTimer); elapsedTimer = null; } }
function setPhase(raw) {
  const action = raw.replace(/^\[[^\]]*\]\s*/, "");
  $("phase-text").textContent = action;
  const idx = STEPS.findIndex((s) => s.match.some((m) => action.includes(m)));
  if (idx >= 0) { renderSteps(idx); setBar(Math.round(((idx + 1) / STEPS.length) * 100)); }
}
function finishProgress() {
  stopElapsed(); renderSteps(STEPS.length); setBar(100);
  $("spinner").classList.add("done"); $("phase-text").textContent = "완료";
}

function handleMsg(msg) {
  if (msg.type === "progress") setPhase(msg.msg);
  else if (msg.type === "result") {
    diagnosing = false; setDiagBtns(true, null); finishProgress();
    renderResult(msg.data);
    setTimeout(() => { $("progress-panel").hidden = true; }, 700);
    startLive();
  } else if (msg.type === "live") applyLive(msg.data);
  else if (msg.type === "live_stopped") {
    liveOn = false;
    $("btn-live").textContent = "▶ 라이브 모니터";
    $("led-indicator").classList.remove("live");
  } else if (msg.type === "wifi_connecting") {
    pendingConnectSsid = msg.ssid;
    setWifiFormStatus(msg.ssid, "⏳ 접속 시도 중… (최대 ~12초)", "");
  } else if (msg.type === "error") {
    diagnosing = false; setDiagBtns(true, null); stopElapsed();
    $("spinner").classList.add("done"); $("phase-text").textContent = "오류: " + msg.msg;
  }
}

// ---- 결과 렌더링 -----------------------------------------------------------
function renderResult(res) {
  const checks = res.checks || {};
  lastChecks = checks;
  let pass = 0, fail = 0, skip = 0;
  Object.values(checks).forEach((c) =>
    c.status === "PASS" ? pass++ : c.status === "FAIL" ? fail++ : skip++);

  const ob = $("overall-badge");
  ob.textContent = res.overall === "PASS" ? "✓ PASS" : "✗ FAIL";
  ob.className = "overall " + (res.overall || "");
  $("counts").innerHTML =
    `<span class="cnt pass">● ${pass}</span><span class="cnt fail">● ${fail}</span><span class="cnt skip">● ${skip}</span>`;

  // 보드 식별(중복 제거: Chip/Flash 는 카드에 있으므로 여기선 식별값만)
  const usb = res.usb || {}, chip = res.chip || {};
  $("board-ident").textContent =
    `${res.port} · ${usb.vid_pid || ""} · SN ${usb.serial || "-"} · MAC ${chip.mac || "-"}`;

  // 카드 채우기
  const order = Object.keys(labels).length ? Object.keys(labels) : Object.keys(checks);
  order.forEach((key) => {
    const c = checks[key];
    if (c) updateCard(key, c.status, c.detail || "");
  });

  renderWifiTab();
  renderBleTab();
  $("btn-live").disabled = false;
}

// ---- WiFi 탭 ---------------------------------------------------------------
function renderWifiTab() {
  const list = $("wifi-list");
  const aps = (lastChecks.wifi_scan && lastChecks.wifi_scan.aps) || [];
  $("wifi-count").textContent = aps.length ? `${aps.length}개` : "";
  if (!aps.length) { list.innerHTML = '<div class="empty">스캔된 AP 가 없습니다.</div>'; return; }
  list.innerHTML = "";
  aps.forEach((a) => {
    const ssid = a.ssid || "<숨김 SSID>";
    const row = document.createElement("div");
    row.className = "ap-item";
    row.innerHTML = `
      <div class="scan-row ap-head">
        ${signalBars(a.rssi)}
        <span class="name">${escapeHtml(ssid)}</span>
        <span class="rssi">${a.rssi} dBm</span>
        <span class="ch">ch${a.ch}</span>
        <span class="chevron">▾</span>
      </div>
      <div class="ap-form" hidden>
        <input type="text" placeholder="비밀번호 (개방형이면 비워두기)" class="pw-input" />
        <button class="btn secondary toggle-pw" type="button" title="비밀번호 표시/숨김">🙈 숨기기</button>
        <button class="btn connect-btn">접속 테스트</button>
        <div class="ap-status muted"></div>
      </div>`;
    const head = row.querySelector(".ap-head");
    const form = row.querySelector(".ap-form");
    head.onclick = () => {
      document.querySelectorAll(".ap-form").forEach((f) => { if (f !== form) f.hidden = true; });
      form.hidden = !form.hidden;
    };
    const pwInput = row.querySelector(".pw-input");
    row.querySelector(".toggle-pw").onclick = (e) => {
      const show = pwInput.type === "password";
      pwInput.type = show ? "text" : "password";
      e.target.textContent = show ? "🙈 숨기기" : "👁 표시";
    };
    row.querySelector(".connect-btn").onclick = () => doWifiConnect(ssid, pwInput.value);
    row.dataset.ssid = ssid;
    list.appendChild(row);
  });
}

function doWifiConnect(ssid, pw) {
  if (!currentPort) { alert("먼저 진단을 실행하세요."); return; }
  if (!liveOn) startLive(); // 라이브 스트림으로 명령을 보내야 함
  pendingConnectSsid = ssid;
  setWifiFormStatus(ssid, "⏳ 접속 시도 중… (최대 ~12초)", "");
  send({ action: "wifi_connect", ssid, password: pw });
}

function setWifiFormStatus(ssid, text, cls) {
  document.querySelectorAll(".ap-item").forEach((row) => {
    if (row.dataset.ssid === ssid) {
      const s = row.querySelector(".ap-status");
      if (s) { s.textContent = text; s.className = "ap-status " + cls; }
    }
  });
}

// ---- BLE 탭 ----------------------------------------------------------------
function renderBleTab() {
  const list = $("ble-list");
  const devs = (lastChecks.ble && lastChecks.ble.ble_list) || [];
  $("ble-count").textContent = devs.length ? `${devs.length}개` : "";
  if (!devs.length) { list.innerHTML = '<div class="empty">발견된 BLE 기기가 없습니다.</div>'; return; }
  list.innerHTML = "";
  devs.forEach((d) => list.appendChild(scanRow(d.name || "<이름없음>", d.rssi, d.addr || "")));
}

function scanRow(name, rssi, right) {
  const row = document.createElement("div");
  row.className = "scan-row";
  row.innerHTML = `${signalBars(rssi)}<span class="name">${escapeHtml(name)}</span>
    <span class="rssi">${rssi ?? "?"} dBm</span><span class="ch">${escapeHtml(String(right))}</span>`;
  return row;
}
function signalBars(rssi) {
  let level = 0;
  if (rssi >= -50) level = 4; else if (rssi >= -60) level = 3;
  else if (rssi >= -70) level = 2; else if (rssi >= -80) level = 1;
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

const LED_COLORS = { R: "#ff3030", G: "#30ff30", B: "#3030ff", "-": "#444" };
const LED_NAME = { R: "빨강", G: "초록", B: "파랑" };

function applyLive(cyc) {
  // RGB LED 라이브 색
  if (cyc.led && cyc.led.color) {
    const col = LED_COLORS[cyc.led.color] || "#444";
    const sw = $("led-swatch"); if (sw) sw.style.background = col;
    const ind = $("led-indicator"); if (ind) ind.style.background = col;
    updateCard("rgb_led", "PASS",
      `WS2812 정상 · 현재 색: ${LED_NAME[cyc.led.color] || cyc.led.color} (라이브 순환)`);
  }
  // BOOT 버튼 (그린/적색 상태)
  if (cyc.button) {
    if (cyc.button.pressed_now) updateCard("boot_button", "PASS", "🔴 지금 눌림! (live)");
    else if (cyc.button.ever_pressed) updateCard("boot_button", "PASS", "✓ 눌림 확인됨 — 정상 (live)");
    else updateCard("boot_button", "PASS", "🔘 BOOT 버튼을 눌러보세요 (live)");
  }
  // 온도 라이브
  if (cyc.temp && cyc.temp.ok) updateCard("temperature", "PASS", `${cyc.temp.celsius}°C (live)`);
  // WiFi 접속 결과(웹 AP 접속 명령의 응답이 여기로 들어옴)
  if (cyc.wifi_connect) applyWifiConnect(cyc.wifi_connect);
}

function applyWifiConnect(wc) {
  if (!wc || !wc.attempted) return;
  const ssid = wc.ssid;
  if (wc.connected) {
    updateCard("wifi_connect", "PASS", `'${ssid}' 접속 성공 — IP ${wc.ip}`);
    if (pendingConnectSsid && ssid === pendingConnectSsid) {
      setWifiFormStatus(ssid, `✓ 접속 성공 — IP ${wc.ip}`, "ok");
      pendingConnectSsid = null;
    }
  } else {
    updateCard("wifi_connect", "FAIL", `'${ssid}' 접속 실패`);
    if (pendingConnectSsid && ssid === pendingConnectSsid) {
      setWifiFormStatus(ssid, "✗ 접속 실패 — 비밀번호/신호 확인", "fail");
      pendingConnectSsid = null;
    }
  }
}

function escapeHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
