// TAJ front-end.
//
// Speech runs IN THE BROWSER — no installs:
//   • SpeechRecognition  → turns your voice into text (the mic)
//   • speechSynthesis     → speaks TAJ's reply out loud (the voice)
// The browser sends/receives only TEXT over the WebSocket; the server runs the
// tutor brain. This is why it works on any Python version with nothing to install.

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
let choice = { native: "en", target: "ar-LEV", level: "A1", rtl: true };
let providers = {};

// Map a target profile to a BCP-47 code the browser's speech engine understands.
const SPEECH_LANG = {
  "ar-LEV": "ar-SA",
  "ar-MSA": "ar-SA",
  "zh-CN": "zh-CN",
  "ja-JP": "ja-JP",
};

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

  const saved = loadChoice();
  if (saved) {
    $("ob-native").value = saved.native;
    $("ob-target").value = saved.target;
    $("ob-level").value = saved.level;
  }

  if (!speechSupported()) {
    $("ob-note").innerHTML =
      "⚠ This browser can't do speech. Please open TAJ in <strong>Chrome</strong> " +
      "or <strong>Microsoft Edge</strong> (Edge has the best built-in Arabic voice).";
  } else if (providers.llm === "mock") {
    $("ob-note").innerHTML =
      "✅ Your mic and a built-in voice are ready — no installs needed. The tutor " +
      "brain is still in practice mode (canned replies); we'll switch on a real " +
      "tutor next.";
  }

  $("ob-start").addEventListener("click", start);
  // Warm up the voice list (some browsers load it lazily).
  if (window.speechSynthesis) speechSynthesis.getVoices();
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
  conversationEl.innerHTML = "";
  correctionsEl.innerHTML = "";

  const targetName = targetSel.selectedOptions[0]?.textContent || choice.target;
  setStatus(`${targetName} · ${choice.level} · 🎤 browser · 🧠 ${providers.llm}`, "ready");

  if (providers.llm === "mock") {
    showBanner(
      "Speech works now (no installs!). The tutor brain is still in practice " +
        "mode — replies are canned. Ask me to switch on a real tutor for live lessons."
    );
  } else {
    hideBanner();
  }

  connect();
  refreshDeck();
}

// --------------------------------------------------------------------------- //
// WebSocket (text in, text out — the browser handles the audio)
// --------------------------------------------------------------------------- //
function connect() {
  if (ws) {
    try {
      ws.onclose = null;
      ws.close();
    } catch (e) {}
  }
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const qs =
    `lang=${encodeURIComponent(choice.target)}` +
    `&level=${encodeURIComponent(choice.level)}` +
    `&native=${encodeURIComponent(choice.native)}` +
    `&speech=browser`;
  ws = new WebSocket(`${proto}://${location.host}/ws?${qs}`);

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
      // We already show the user's words from the browser; ignore the echo.
      break;
    case "message":
      addBubble("assistant", msg.text, msg.translation);
      renderCorrections(msg.corrections);
      speak(msg.text); // browser speaks the reply
      if (msg.vocab && msg.vocab.length) refreshDeck();
      break;
    case "audio":
      break; // browser speech mode ignores server audio
    case "error":
      addBubble("error", msg.message, "");
      break;
  }
}

// --------------------------------------------------------------------------- //
// Speech-to-text (the microphone) — browser SpeechRecognition
// --------------------------------------------------------------------------- //
let recog;
let recognizing = false;
let finalText = "";

function speechSupported() {
  return !!(window.SpeechRecognition || window.webkitSpeechRecognition);
}

function ensureRecog() {
  if (recog) return recog;
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {
    showBanner("Speech isn't supported here — please use Chrome or Microsoft Edge.");
    return null;
  }
  recog = new SR();
  recog.continuous = false;
  recog.interimResults = false;
  recog.maxAlternatives = 1;
  recog.onresult = (e) => {
    finalText = e.results[0][0].transcript;
  };
  recog.onerror = (e) => {
    if (e.error === "not-allowed" || e.error === "service-not-allowed") {
      showBanner(
        "Microphone blocked. Click the 🔒 icon left of the address bar → set " +
          "Microphone to Allow → reload."
      );
    } else if (e.error === "no-speech") {
      // ignore — they just didn't say anything
    }
  };
  recog.onend = () => {
    recognizing = false;
    setTalkLabel("Hold to speak");
    talkBtn.classList.remove("recording");
    if (finalText.trim()) {
      submitText(finalText.trim());
      finalText = "";
    }
  };
  return recog;
}

function startRecording() {
  const r = ensureRecog();
  if (!r || recognizing) return;
  r.lang = SPEECH_LANG[choice.target] || "en-US";
  finalText = "";
  try {
    r.start();
    recognizing = true;
    talkBtn.classList.add("recording");
    setTalkLabel("Listening…");
  } catch (e) {
    /* start() throws if called twice; ignore */
  }
}

function stopRecording() {
  if (recog && recognizing) {
    try {
      recog.stop();
    } catch (e) {}
  }
}

function submitText(text) {
  // Stop any ongoing speech so TAJ doesn't talk over the next turn.
  if (window.speechSynthesis) speechSynthesis.cancel();
  addBubble("user", text, "");
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(text);
}

// --------------------------------------------------------------------------- //
// Text-to-speech (the voice) — browser speechSynthesis
// --------------------------------------------------------------------------- //
let _voices = [];
function loadVoices() {
  if (window.speechSynthesis) _voices = speechSynthesis.getVoices() || [];
}
if (window.speechSynthesis) {
  loadVoices();
  speechSynthesis.onvoiceschanged = loadVoices;
}

function pickVoice(langBase) {
  if (!_voices.length) loadVoices();
  return (
    _voices.find((v) => v.lang && v.lang.toLowerCase().startsWith(langBase)) || null
  );
}

function speak(text) {
  if (!window.speechSynthesis || !text) return;
  const u = new SpeechSynthesisUtterance(text);
  u.lang = SPEECH_LANG[choice.target] || "en-US";
  const v = pickVoice(u.lang.split("-")[0].toLowerCase());
  if (v) u.voice = v;
  u.rate = 0.95;
  speechSynthesis.cancel();
  speechSynthesis.speak(u);
}

// --------------------------------------------------------------------------- //
// Button + key bindings
// --------------------------------------------------------------------------- //
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

$("change").addEventListener("click", () => {
  if (ws) {
    ws.onclose = null;
    try {
      ws.close();
    } catch (e) {}
  }
  if (window.speechSynthesis) speechSynthesis.cancel();
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

// --------------------------------------------------------------------------- //
// Helpers
// --------------------------------------------------------------------------- //
function setStatus(text, cls) {
  statusEl.textContent = text;
  statusEl.className = "status" + (cls ? " " + cls : "");
}
function setTalkLabel(t) {
  const el = talkBtn.querySelector(".talk-label");
  if (el) el.textContent = t;
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
