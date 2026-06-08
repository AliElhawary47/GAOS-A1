/**
 * GAOS™ Website Chatbot Widget
 * Drop-in embeddable AI chatbot for any website.
 *
 * Usage:
 *   <script src="https://your-gaos-server.railway.app/widget.js"
 *           data-gaos-url="https://your-gaos-server.railway.app"
 *           data-business-name="Your Business">
 *   </script>
 */
(function () {
  "use strict";

  const script       = document.currentScript;
  const SERVER_URL   = (script && script.getAttribute("data-gaos-url")      || "").replace(/\/$/, "");
  const BUSINESS     = (script && script.getAttribute("data-business-name") || "How can we help?");
  const SESSION_KEY  = "gaos_session_id";

  if (!SERVER_URL) {
    console.warn("[GAOS Widget] data-gaos-url is required.");
    return;
  }

  // ── Session ID ───────────────────────────────────────────────
  function getSessionId() {
    let id = sessionStorage.getItem(SESSION_KEY);
    if (!id) {
      id = "sess_" + Math.random().toString(36).slice(2) + Date.now().toString(36);
      sessionStorage.setItem(SESSION_KEY, id);
    }
    return id;
  }

  // ── Styles ───────────────────────────────────────────────────
  const CSS = `
    #gaos-widget * { box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }
    #gaos-btn {
      position: fixed; bottom: 24px; right: 24px; z-index: 9998;
      width: 56px; height: 56px; border-radius: 50%;
      background: #1a1a2e; color: #fff; border: none; cursor: pointer;
      box-shadow: 0 4px 16px rgba(0,0,0,0.25);
      display: flex; align-items: center; justify-content: center;
      transition: transform 0.2s, box-shadow 0.2s;
    }
    #gaos-btn:hover { transform: scale(1.08); box-shadow: 0 6px 20px rgba(0,0,0,0.3); }
    #gaos-btn svg { width: 26px; height: 26px; }
    #gaos-panel {
      position: fixed; bottom: 90px; right: 24px; z-index: 9999;
      width: 360px; max-height: 520px;
      background: #fff; border-radius: 16px;
      box-shadow: 0 8px 32px rgba(0,0,0,0.18);
      display: flex; flex-direction: column; overflow: hidden;
      transform: scale(0.92) translateY(12px); opacity: 0;
      transition: transform 0.22s ease, opacity 0.22s ease;
      pointer-events: none;
    }
    #gaos-panel.gaos-open { transform: scale(1) translateY(0); opacity: 1; pointer-events: all; }
    #gaos-header {
      background: #1a1a2e; color: #fff; padding: 14px 16px;
      display: flex; align-items: center; justify-content: space-between;
    }
    #gaos-header-title { font-size: 15px; font-weight: 600; }
    #gaos-header-sub { font-size: 11px; color: rgba(255,255,255,0.6); margin-top: 2px; }
    #gaos-close {
      background: none; border: none; color: rgba(255,255,255,0.7);
      cursor: pointer; padding: 4px; font-size: 20px; line-height: 1;
    }
    #gaos-close:hover { color: #fff; }
    #gaos-messages {
      flex: 1; overflow-y: auto; padding: 16px 12px;
      display: flex; flex-direction: column; gap: 10px;
      scroll-behavior: smooth;
    }
    .gaos-msg {
      max-width: 80%; padding: 10px 13px; border-radius: 14px;
      font-size: 14px; line-height: 1.45; word-break: break-word;
    }
    .gaos-msg.bot { background: #f0f2f5; color: #1a1a2e; align-self: flex-start; border-bottom-left-radius: 4px; }
    .gaos-msg.user { background: #1a1a2e; color: #fff; align-self: flex-end; border-bottom-right-radius: 4px; }
    .gaos-msg.error { background: #fff0f0; color: #c0392b; align-self: flex-start; }
    .gaos-typing { display: flex; align-items: center; gap: 5px; padding: 10px 13px; }
    .gaos-dot {
      width: 7px; height: 7px; border-radius: 50%; background: #aaa;
      animation: gaos-bounce 1.2s infinite ease-in-out;
    }
    .gaos-dot:nth-child(2) { animation-delay: 0.2s; }
    .gaos-dot:nth-child(3) { animation-delay: 0.4s; }
    @keyframes gaos-bounce {
      0%, 80%, 100% { transform: translateY(0); }
      40% { transform: translateY(-6px); }
    }
    #gaos-footer { padding: 10px 12px; border-top: 1px solid #eee; display: flex; gap: 8px; }
    #gaos-input {
      flex: 1; border: 1.5px solid #e0e0e0; border-radius: 22px;
      padding: 9px 14px; font-size: 14px; outline: none;
      transition: border-color 0.15s;
    }
    #gaos-input:focus { border-color: #e94560; }
    #gaos-send {
      background: #e94560; color: #fff; border: none;
      border-radius: 50%; width: 38px; height: 38px; cursor: pointer;
      display: flex; align-items: center; justify-content: center;
      transition: background 0.15s;
      flex-shrink: 0;
    }
    #gaos-send:hover { background: #c73250; }
    #gaos-send svg { width: 17px; height: 17px; }
    #gaos-powered { text-align: center; font-size: 10px; color: #bbb; padding: 4px 0 8px; }
    @media (max-width: 480px) {
      #gaos-panel { width: calc(100vw - 16px); right: 8px; bottom: 80px; }
      #gaos-btn { bottom: 16px; right: 16px; }
    }
  `;

  // ── DOM ──────────────────────────────────────────────────────
  function buildWidget() {
    const styleTag = document.createElement("style");
    styleTag.textContent = CSS;
    document.head.appendChild(styleTag);

    const wrap = document.createElement("div");
    wrap.id = "gaos-widget";
    wrap.innerHTML = `
      <button id="gaos-btn" aria-label="Open chat" title="Chat with us">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
        </svg>
      </button>
      <div id="gaos-panel" role="dialog" aria-label="Chat">
        <div id="gaos-header">
          <div>
            <div id="gaos-header-title">${escHtml(BUSINESS)}</div>
            <div id="gaos-header-sub">Online — reply in seconds</div>
          </div>
          <button id="gaos-close" aria-label="Close chat">&times;</button>
        </div>
        <div id="gaos-messages"></div>
        <div id="gaos-footer">
          <input id="gaos-input" type="text" placeholder="Type a message…" autocomplete="off" maxlength="500"/>
          <button id="gaos-send" aria-label="Send">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
            </svg>
          </button>
        </div>
        <div id="gaos-powered">Powered by GAOS™</div>
      </div>
    `;
    document.body.appendChild(wrap);
  }

  function escHtml(s) {
    return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
  }

  // ── State ────────────────────────────────────────────────────
  let isOpen    = false;
  let isBusy    = false;
  let messages  = [];  // {role, text}

  function togglePanel() {
    isOpen = !isOpen;
    document.getElementById("gaos-panel").classList.toggle("gaos-open", isOpen);
    if (isOpen) {
      if (messages.length === 0) addBotMsg("Hi! 👋 How can I help you today?");
      document.getElementById("gaos-input").focus();
    }
  }

  function addMsg(role, text) {
    messages.push({ role, text });
    const el = document.getElementById("gaos-messages");
    const div = document.createElement("div");
    div.className = "gaos-msg " + role;
    div.textContent = text;
    el.appendChild(div);
    el.scrollTop = el.scrollHeight;
    return div;
  }

  function addBotMsg(text)   { return addMsg("bot",   text); }
  function addUserMsg(text)  { return addMsg("user",  text); }
  function addErrorMsg(text) { return addMsg("error", text); }

  function showTyping() {
    const el = document.getElementById("gaos-messages");
    const div = document.createElement("div");
    div.className = "gaos-msg bot gaos-typing";
    div.id = "gaos-typing-indicator";
    div.innerHTML = '<span class="gaos-dot"></span><span class="gaos-dot"></span><span class="gaos-dot"></span>';
    el.appendChild(div);
    el.scrollTop = el.scrollHeight;
  }

  function hideTyping() {
    const t = document.getElementById("gaos-typing-indicator");
    if (t) t.remove();
  }

  // ── Send ─────────────────────────────────────────────────────
  async function sendMessage() {
    if (isBusy) return;
    const input = document.getElementById("gaos-input");
    const text  = input.value.trim();
    if (!text) return;

    input.value = "";
    addUserMsg(text);
    isBusy = true;
    showTyping();

    try {
      const res = await fetch(SERVER_URL + "/chat", {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: getSessionId(), message: text }),
      });
      hideTyping();
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();
      addBotMsg(data.reply || "Sorry, I didn't get a response.");
    } catch (e) {
      hideTyping();
      addErrorMsg("Connection error — please try again.");
    } finally {
      isBusy = false;
      document.getElementById("gaos-messages").scrollTop = 99999;
    }
  }

  // ── Boot ─────────────────────────────────────────────────────
  function init() {
    buildWidget();
    document.getElementById("gaos-btn").addEventListener("click", togglePanel);
    document.getElementById("gaos-close").addEventListener("click", togglePanel);
    document.getElementById("gaos-send").addEventListener("click", sendMessage);
    document.getElementById("gaos-input").addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
      if (e.key === "Escape") { if (isOpen) togglePanel(); }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
