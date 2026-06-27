// TAJ front-end: capture a spoken utterance, ship it over the WebSocket, render
// the tutor's reply + corrections, and play the synthesized voice back.

const conversationEl = document.getElementById("conversation");
const correctionsEl = document.getElementById("corrections");
const deckEl = document.getElementById("deck");
const statusEl = document.getElementById("status");
const talkBtn = document.getElementById("talk");

let ws;
let mediaRecorder;
let chunks = [];
let rtl = false;

// --------------------------------------------------------------------------- //
// Boot
// --------------------------------------------------------------------------- //
async function boot() {
  try {
    const cfg = await fetch("/api/config").then((r) => r.json());
    rtl = cfg.rtl;
    setStatus(
      `${cfg.name} · ${cfg.dialect} · ${cfg.level} · ` +
        `stt:${cfg.providers.stt} llm:${cfg.providers.llm} tts:${cfg.providers.tts}`,
      "ready"
    );
    document.title = `TAJ — ${cfg.name}`;
  } catch (e) {
    setStatus("could not load config", "error");
  }
  connect();
  refreshDeck();
}

function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.binaryType = "arraybuffer";

  ws.onopen = () => {
    talkBtn.disabled = false;
  };
  ws.onclose = () => {
    talkBtn.disabled = true;
    setStatus("disconnected — reconnecting…", "error");
    setTimeout(connect, 1500);
  };
  ws.onmessage = (ev) => handleMessage(JSON.parse(ev.data));
}

function handleMessage(msg) {
  switch (msg.type) {
    case "transcript":
      addBubble("user", msg.text, "");
      break;
    case "message":
      addBubble("assistant", msg.text, msg.translation);
      renderCorrections(msg.corrections);
      if (msg.vocab && msg.vocab.length) refreshDeck();
      break;
    case "audio":
      playAudio(msg.data, msg.format);
      break;
    case "error":
      addBubble("error", msg.message, "");
      break;
  }
}

// --------------------------------------------------------------------------- //
// Push-to-talk recording
// --------------------------------------------------------------------------- //
async function ensureMic() {
  if (mediaRecorder) return true;
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream);
    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunks.push(e.data);
    };
    mediaRecorder.onstop = sendUtterance;
    return true;
  } catch (e) {
    setStatus("microphone permission denied", "error");
    return false;
  }
}

async function startRecording() {
  if (!(await ensureMic())) return;
  if (mediaRecorder.state === "recording") return;
  chunks = [];
  mediaRecorder.start();
  talkBtn.classList.add("recording");
  talkBtn.querySelector(".talk-label").textContent = "Listening…";
}

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state === "recording") {
    mediaRecorder.stop();
  }
  talkBtn.classList.remove("recording");
  talkBtn.querySelector(".talk-label").textContent = "Hold to speak";
}

async function sendUtterance() {
  const blob = new Blob(chunks, { type: "audio/webm" });
  const buf = await blob.arrayBuffer();
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(buf);
  }
}

// Mouse + touch + spacebar bindings.
talkBtn.addEventListener("mousedown", startRecording);
talkBtn.addEventListener("mouseup", stopRecording);
talkBtn.addEventListener("mouseleave", stopRecording);
talkBtn.addEventListener("touchstart", (e) => {
  e.preventDefault();
  startRecording();
});
talkBtn.addEventListener("touchend", (e) => {
  e.preventDefault();
  stopRecording();
});
document.addEventListener("keydown", (e) => {
  if (e.code === "Space" && !e.repeat && !talkBtn.disabled) {
    e.preventDefault();
    startRecording();
  }
});
document.addEventListener("keyup", (e) => {
  if (e.code === "Space") {
    e.preventDefault();
    stopRecording();
  }
});

// --------------------------------------------------------------------------- //
// Rendering
// --------------------------------------------------------------------------- //
function addBubble(role, text, translation) {
  const el = document.createElement("div");
  el.className = `bubble ${role}` + (rtl && role !== "error" ? " rtl" : "");
  const main = document.createElement("div");
  main.className = "main-text";
  main.textContent = text;
  el.appendChild(main);
  if (translation) {
    const tr = document.createElement("div");
    tr.className = "translation";
    tr.textContent = translation;
    el.appendChild(tr);
  }
  conversationEl.appendChild(el);
  conversationEl.scrollTop = conversationEl.scrollHeight;
}

function renderCorrections(corrections) {
  if (!corrections || !corrections.length) return;
  for (const c of corrections) {
    const li = document.createElement("li");
    li.innerHTML =
      `<span class="err">${escapeHtml(c.error)}</span> → ` +
      `<span class="fix">${escapeHtml(c.fix)}</span>` +
      (c.why ? `<span class="why">${escapeHtml(c.why)}</span>` : "");
    correctionsEl.prepend(li);
  }
}

async function refreshDeck() {
  try {
    const data = await fetch("/api/srs/due").then((r) => r.json());
    const { total, due } = data.counts;
    deckEl.textContent = `${total} cards · ${due} due for review`;
  } catch (e) {
    deckEl.textContent = "—";
  }
}

function playAudio(b64, format) {
  const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
  const blob = new Blob([bytes], { type: format === "wav" ? "audio/wav" : "audio/mpeg" });
  const url = URL.createObjectURL(blob);
  const audio = new Audio(url);
  audio.play().catch(() => {});
  audio.onended = () => URL.revokeObjectURL(url);
}

function setStatus(text, cls) {
  statusEl.textContent = text;
  statusEl.className = "status" + (cls ? " " + cls : "");
}

function escapeHtml(s) {
  return (s || "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[c]));
}

boot();
