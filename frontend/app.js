// TAJ front-end.
//
// Flow: English onboarding (pick native language + target + level) → open the
// WebSocket with those choices → spoken practice in the target language with
// native-language translations underneath every line.

const $ = (id) => document.getElementById(id);

const onboardingEl = $("onboarding");
const appEl = $("app");
const conversationEl = $("conversation");
const correctionsEl = $("corrections");
const deckEl = $("deck");
const statusEl = $("status");
const bannerEl = $("banner");
const talkBtn = $("talk");

let ws;
let mediaRecorder;
let chunks = [];
let choice = { native: "en", target: "ar-LEV", level: "A1", rtl: true };
let providers = {};

// --------------------------------------------------------------------------- //
// Onboarding
// --------------------------------------------------------------------------- //
async function initOnboarding() {
  let data;
  try {
    data = await fetch("/api/languages").then((r) => r.json());
  } catch (e) {
    $("ob-note").textContent =
      "Couldn't reach the TAJ server. Is it running? (python -m backend.main)";
    return;
  }
  providers = data.providers || {};

  fillSelect($("ob-native"), data.natives, "en");
  fillSelect(
    $("ob-target"),
    data.targets.map((t) => ({
      key: t.key,
      label: `${t.name} — ${t.dialect}`,
      rtl: t.rtl,
    })),
    "ar-LEV"
  );
  fillSelect($("ob-level"), data.levels, "A1");

  // Restore the learner's last choices, if any.
  const saved = loadChoice();
  if (saved) {
    $("ob-native").value = saved.native;
    $("ob-target").value = saved.target;
    $("ob-level").value = saved.level;
  }

  // Tell the user up front whether real speech recognition is on.
  if (providers.stt === "mock") {
    $("ob-note").innerHTML =
      "⚠ Speech recognition is in <strong>practice mode</strong> right now, so " +
      "TAJ can't understand your words yet — it'll still talk and you'll see the " +
      "full flow. Install <code>faster-whisper</code> to let it hear you (README).";
  }

  $("ob-start").addEventListener("click", start);
}

function fillSelect(sel, items, fallback) {
  sel.innerHTML = "";
  for (const it of items) {
    const opt = document.createElement("option");
    opt.value = it.key;
    opt.textContent = it.label;
    if (it.rtl !== undefined) opt.dataset.rtl = it.rtl;
    sel.appendChild(opt);
  }
  if ([...sel.options].some((o) => o.value === fallback)) sel.value = fallback;
}

function start() {
  const targetSel = $("ob-target");
  choice = {
    native: $("ob-native").value,
    target: targetSel.value,
    level: $("ob-level").value,
    rtl: targetSel.selectedOptions[0]?.dataset.rtl === "true",
  };
  saveChoice(choice);

  onboardingEl.classList.add("hidden");
  appEl.classList.remove("hidden");

  // Fresh conversation each time we (re)start.
  conversationEl.innerHTML = "";
  correctionsEl.innerHTML = "";

  const targetName = targetSel.selectedOptions[0]?.textContent || choice.target;
  setStatus(
    `${targetName} · ${choice.level} · ` +
      `stt:${providers.stt} llm:${providers.llm} tts:${providers.tts}`,
    "ready"
  );

  if (providers.stt === "mock") {
    showBanner(
      "Practice mode: TAJ can't understand speech yet (stt:mock). Your mic " +
        "still records — install faster-whisper so it can hear you. See README."
    );
  } else {
    hideBanner();
  }

  connect();
  refreshDeck();
}

// --------------------------------------------------------------------------- //
// WebSocket
// --------------------------------------------------------------------------- //
function connect() {
  if (ws) {
    try {
      ws.onclose = null;
      ws.close();
    } catch (e) {}
  }
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const qs = `lang=${encodeURIComponent(choice.target)}&level=${encodeURIComponent(
    choice.level
  )}&native=${encodeURIComponent(choice.native)}`;
  ws = new WebSocket(`${proto}://${location.host}/ws?${qs}`);
  ws.binaryType = "arraybuffer";

  ws.onopen = () => {
    talkBtn.disabled = false;
  };
  ws.onclose = () => {
    talkBtn.disabled = true;
    if (!appEl.classList.contains("hidden")) {
      setStatus("disconnected — reconnecting…", "error");
      setTimeout(connect, 1500);
    }
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
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    showBanner(
      "This browser can't access the microphone here. Use Chrome/Edge and open " +
        "the app at http://127.0.0.1:8000 (not a file:// path)."
    );
    return false;
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream);
    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunks.push(e.data);
    };
    mediaRecorder.onstop = sendUtterance;
    return true;
  } catch (e) {
    showBanner(
      "Microphone blocked. Click the 🔒/camera icon in the address bar → allow " +
        "the microphone, then reload. (" + (e.name || "error") + ")"
    );
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
  if (blob.size === 0) return;
  const buf = await blob.arrayBuffer();
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(buf);
}

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
  if (e.code === "Space" && !e.repeat && !talkBtn.disabled && !isOnboarding()) {
    e.preventDefault();
    startRecording();
  }
});
document.addEventListener("keyup", (e) => {
  if (e.code === "Space" && !isOnboarding()) {
    e.preventDefault();
    stopRecording();
  }
});

// "Change" button → back to onboarding.
$("change").addEventListener("click", () => {
  if (ws) {
    ws.onclose = null;
    try {
      ws.close();
    } catch (e) {}
  }
  appEl.classList.add("hidden");
  onboardingEl.classList.remove("hidden");
});

// --------------------------------------------------------------------------- //
// Rendering
// --------------------------------------------------------------------------- //
function addBubble(role, text, translation) {
  const el = document.createElement("div");
  el.className = `bubble ${role}` + (choice.rtl && role !== "error" ? " rtl" : "");
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
    const data = await fetch(
      `/api/srs/due?lang=${encodeURIComponent(choice.target)}`
    ).then((r) => r.json());
    const { total, due } = data.counts;
    deckEl.textContent = `${total} cards · ${due} due for review`;
  } catch (e) {
    deckEl.textContent = "—";
  }
}

function playAudio(b64, format) {
  const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
  const blob = new Blob([bytes], {
    type: format === "wav" ? "audio/wav" : "audio/mpeg",
  });
  const url = URL.createObjectURL(blob);
  const audio = new Audio(url);
  audio.play().catch(() => {});
  audio.onended = () => URL.revokeObjectURL(url);
}

// --------------------------------------------------------------------------- //
// Helpers
// --------------------------------------------------------------------------- //
function setStatus(text, cls) {
  statusEl.textContent = text;
  statusEl.className = "status" + (cls ? " " + cls : "");
}

function showBanner(text) {
  bannerEl.textContent = text;
  bannerEl.classList.remove("hidden");
}
function hideBanner() {
  bannerEl.classList.add("hidden");
}

function isOnboarding() {
  return !onboardingEl.classList.contains("hidden");
}

function saveChoice(c) {
  try {
    localStorage.setItem("taj.choice", JSON.stringify(c));
  } catch (e) {}
}
function loadChoice() {
  try {
    return JSON.parse(localStorage.getItem("taj.choice"));
  } catch (e) {
    return null;
  }
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

initOnboarding();
