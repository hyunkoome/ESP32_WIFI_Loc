// ESP32-S3 보드 진단 대시보드 프런트엔드.
// 백엔드(app.py)와 REST(/api/*) + WebSocket(/ws)으로 통신한다.

let ws = null;
let labels = {};         // check key -> 라벨
let currentPort = null;  // 현재 진단/모니터 중인 포트
let liveOn = false;

const $ = (id) => document.getElementById(id);

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
  try {
    const r = await fetch("/api/boards");
    const data = await r.json();
    const boards = data.boards || [];
    if (!boards.length) {
      list.innerHTML =
        '<div class="meta">연결된 보드가 없습니다. USB 케이블을 확인하세요.</div>';
      return;
    }
    list.innerHTML = "";
    boards.forEach((b) => {
      const card = document.createElement("div");
      card.className = "board-card";
      const acc = b.accessible
        ? ""
        : '<span class="tag warn">권한없음</span>';
      card.innerHTML = `
        <div>
          <span class="port">${b.port}</span>
          <span class="tag">${b.vid_pid || "?"}</span>${acc}
          <div class="meta">${b.bridge || (b.is_espressif ? "Espressif" : "미확인")}</div>
        </div>`;
      const btn = document.createElement("button");
      btn.className = "btn";
      btn.textContent = "▶ 진단 시작";
      btn.onclick = () => startDiagnose(b.port);
      card.appendChild(btn);
      list.appendChild(card);
    });
  } catch (e) {
    list.textContent = "보드 탐색 실패: " + e;
  }
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

function startDiagnose(port) {
  currentPort = port;
  stopLive();
  $("progress-panel").hidden = false;
  $("result-panel").hidden = true;
  $("progress").textContent = `진단 시작: ${port}\n(보드 flash + 검사로 20~40초 걸립니다)\n`;
  send({ action: "diagnose", port: port });
}

function handleMsg(msg) {
  if (msg.type === "progress") {
    $("progress").textContent += "· " + msg.msg + "\n";
    $("progress").scrollTop = $("progress").scrollHeight;
  } else if (msg.type === "result") {
    renderResult(msg.data);
  } else if (msg.type === "live") {
    applyLive(msg.data);
  } else if (msg.type === "live_stopped") {
    liveOn = false;
    $("btn-live").textContent = "▶ 라이브 모니터";
    $("led-indicator").classList.remove("live");
  } else if (msg.type === "error") {
    $("progress").textContent += "✗ " + msg.msg + "\n";
  }
}

// ---- 결과 렌더링 -----------------------------------------------------------
function renderResult(res) {
  $("result-panel").hidden = false;

  // overall 배지
  const ob = $("overall-badge");
  ob.textContent = res.overall || "";
  ob.className = res.overall || "";

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

  // 검사 항목 (녹색/적색 동그라미)
  const checks = res.checks || {};
  const order = Object.keys(labels).length ? Object.keys(labels) : Object.keys(checks);
  const box = $("checks");
  box.innerHTML = "";
  order.forEach((key) => {
    const c = checks[key];
    if (!c) return;
    const row = document.createElement("div");
    row.className = "check-row";
    row.innerHTML = `
      <span class="dot ${c.status}"></span>
      <span class="check-label">${labels[key] || key}</span>
      <span class="check-detail">${escapeHtml(c.detail || "")}</span>`;
    box.appendChild(row);
  });

  // WiFi / BLE 목록
  renderWifi(checks.wifi_scan);
  renderBle(checks.ble);

  // 라이브 버튼 활성화
  $("btn-live").disabled = false;
}

function renderWifi(c) {
  const box = $("wifi-box");
  const list = $("wifi-list");
  const aps = (c && c.aps) || [];
  if (!aps.length) { box.hidden = true; return; }
  box.hidden = false;
  list.innerHTML = "";
  aps.forEach((a) => {
    list.appendChild(scanRow(a.ssid || "<숨김 SSID>", a.rssi, `ch${a.ch}`));
  });
}

function renderBle(c) {
  const box = $("ble-box");
  const list = $("ble-list");
  const devs = (c && c.ble_list) || [];
  if (!devs.length) { box.hidden = true; return; }
  box.hidden = false;
  list.innerHTML = "";
  devs.forEach((d) => {
    list.appendChild(scanRow(d.name || "<이름없음>", d.rssi, d.addr || ""));
  });
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

// RSSI -> 4칸 막대 (강할수록 채워짐)
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
function toggleLive() {
  if (liveOn) stopLive();
  else startLive();
}

function startLive() {
  if (!currentPort) return;
  liveOn = true;
  $("btn-live").textContent = "■ 라이브 중지";
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

// 라이브 사이클 도착 시 빠르게 변하는 값(버튼/온도)만 갱신.
function applyLive(cyc) {
  const checks = {};
  // 라이브 데이터는 펌웨어 원본 키(button/temp/...) → 검사 행 갱신.
  updateCheckDetail("boot_button", liveButtonDetail(cyc.button));
  updateCheckDetail("temperature", liveTempDetail(cyc.temp));
}

function liveButtonDetail(b) {
  if (!b) return null;
  if (b.pressed_now) return "🔴 지금 눌림 (live)";
  if (b.ever_pressed) return "✓ 눌린 적 있음 (live)";
  return `유휴(idle=${b.idle_level}) — 버튼을 눌러보세요 (live)`;
}

function liveTempDetail(t) {
  if (!t || !t.ok) return null;
  return `${t.celsius}°C (live)`;
}

function updateCheckDetail(key, detail) {
  if (detail == null) return;
  const rows = document.querySelectorAll("#checks .check-row");
  rows.forEach((row) => {
    const label = row.querySelector(".check-label");
    if (label && label.textContent === (labels[key] || key)) {
      row.querySelector(".check-detail").textContent = detail;
    }
  });
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
