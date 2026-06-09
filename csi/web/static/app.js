"use strict";

// CSI 웹 모니터 프론트엔드.
//  - /api/devices 를 주기적으로 폴링해 디바이스 상태판을 갱신.
//  - rx 카드의 "모니터 시작" → WebSocket(/ws) 으로 해당 보드 CSI 스트림 구독.
//  - 수신한 진폭 배열을 canvas 막대그래프로 그린다(외부 차트 라이브러리 없음).

const el = (id) => document.getElementById(id);
const wsState = el("ws-state");

let ws = null;
let activeDevice = null;

// ---- 디바이스 상태판 -------------------------------------------------------
async function loadDevices() {
  try {
    const res = await fetch("/api/devices");
    const data = await res.json();
    renderDevices(data.devices || []);
  } catch (e) {
    el("devices").innerHTML = `<p class="hint">디바이스 조회 실패: ${e}</p>`;
  }
}

function renderDevices(devices) {
  const grid = el("devices");
  grid.innerHTML = "";
  if (!devices.length) {
    grid.innerHTML = `<p class="hint">esp32_device.yaml 의 devices 가 비어 있습니다.</p>`;
    return;
  }
  for (const d of devices) {
    const card = document.createElement("div");
    card.className = "card";
    const dot = d.connected ? "on" : "off";
    const portTxt = d.port || "(미연결)";
    card.innerHTML = `
      <div class="row">
        <span class="name"><span class="dot ${dot}"></span>${d.name}</span>
        <span class="badge ${d.role}">${d.role}</span>
      </div>
      <div class="meta">serial: ${d.serial}</div>
      <div class="meta">port: ${portTxt}</div>
      <div class="meta">firmware: ${d.firmware || "-"}</div>
    `;
    if (d.role === "rx" && d.connected) {
      const btn = document.createElement("button");
      btn.className = "btn-mini";
      btn.textContent = "모니터 시작";
      btn.onclick = () => startMonitor(d.name);
      card.appendChild(btn);
    }
    grid.appendChild(card);
  }
}

// ---- WebSocket CSI 스트림 --------------------------------------------------
function ensureWs() {
  if (ws && ws.readyState === WebSocket.OPEN) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(`${proto}://${location.host}/ws`);
    ws.onopen = () => {
      wsState.textContent = "WebSocket: 연결됨";
      wsState.className = "ws-on";
      resolve();
    };
    ws.onclose = () => {
      wsState.textContent = "WebSocket: 미연결";
      wsState.className = "ws-off";
    };
    ws.onerror = (e) => reject(e);
    ws.onmessage = (ev) => handleMessage(JSON.parse(ev.data));
  });
}

async function startMonitor(deviceName) {
  await ensureWs();
  activeDevice = deviceName;
  el("live-target").textContent = `수신: ${deviceName}`;
  el("stop").disabled = false;
  ws.send(JSON.stringify({ action: "start", device: deviceName }));
}

function stopMonitor() {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ action: "stop" }));
  }
  el("stop").disabled = true;
}

function handleMessage(msg) {
  if (msg.type === "csi") {
    el("m-rate").textContent = msg.rate;
    el("m-rssi").textContent = msg.rssi;
    el("m-sub").textContent = msg.n_sub;
    drawAmplitude(msg.amplitude || []);
  } else if (msg.type === "status") {
    el("live-target").textContent = `${activeDevice || ""} — ${msg.msg}`;
  } else if (msg.type === "stopped") {
    el("stop").disabled = true;
    if (msg.error) {
      el("live-target").textContent = `중지(오류): ${msg.error}`;
    }
  }
}

// ---- canvas 진폭 막대그래프 ------------------------------------------------
function drawAmplitude(amp) {
  const canvas = el("chart");
  const ctx = canvas.getContext("2d");
  const W = canvas.width;
  const H = canvas.height;
  ctx.clearRect(0, 0, W, H);
  if (!amp.length) return;

  const pad = 24;
  const plotW = W - pad * 2;
  const plotH = H - pad * 2;
  const maxAmp = Math.max(1, ...amp);
  const barW = plotW / amp.length;

  // 축
  ctx.strokeStyle = "#2a2f3a";
  ctx.beginPath();
  ctx.moveTo(pad, H - pad);
  ctx.lineTo(W - pad, H - pad);
  ctx.stroke();

  // 막대
  ctx.fillStyle = "#4aa3ff";
  for (let i = 0; i < amp.length; i++) {
    const h = (amp[i] / maxAmp) * plotH;
    ctx.fillRect(pad + i * barW, H - pad - h, Math.max(1, barW - 1), h);
  }

  // 최대값 라벨
  ctx.fillStyle = "#8b929e";
  ctx.font = "11px sans-serif";
  ctx.fillText(`max |H| ≈ ${maxAmp.toFixed(0)}`, pad, pad - 6);
}

// ---- 초기화 ----------------------------------------------------------------
el("refresh").onclick = loadDevices;
el("stop").onclick = stopMonitor;
loadDevices();
setInterval(loadDevices, 3000); // 디바이스 연결 상태 주기 갱신
