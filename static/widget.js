/*!
 * LeadDesk chat widget. Add to any website with one line:
 *   <script src="https://YOUR-SERVER/widget.js" data-business="estate" data-title="Harbour & Finch" defer></script>
 * Optional: data-color, data-note (small line under the input), data-api (server address).
 * The page can call LeadDesk.open() or LeadDesk.ask("question") from its own buttons.
 * No dependencies. Styles live in a shadow root, so they never clash with the host page.
 */
(function () {
  "use strict";
  if (window.LeadDesk) return;

  var script = document.currentScript;
  var src = script && script.src ? script.src : location.href;
  var API = ((script && script.getAttribute("data-api")) || new URL(src, location.href).origin).replace(/\/$/, "");
  var TITLE = (script && script.getAttribute("data-title")) || "Chat with us";
  var COLOR = (script && script.getAttribute("data-color")) || "#B4552D";
  var NOTE = (script && script.getAttribute("data-note")) || "AI assistant: answers come from our own documents.";
  var BUSINESS = script && script.getAttribute("data-business");
  var BASE = API + (BUSINESS ? "/api/" + encodeURIComponent(BUSINESS) : "/api");
  var KEY = "leaddesk:" + BASE;
  var pending = null;  // a question asked with LeadDesk.ask() before the greeting arrived

  function load() {
    try { return JSON.parse(sessionStorage.getItem(KEY)) || {}; } catch (e) { return {}; }
  }
  function save(state) {
    try { sessionStorage.setItem(KEY, JSON.stringify(state)); } catch (e) { /* private mode: keep in memory */ }
  }

  var state = load();
  state.messages = state.messages || [];

  var CSS = [
    ":host{all:initial}",
    "*{box-sizing:border-box;font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif}",
    ".bubble{position:fixed;right:20px;bottom:20px;width:60px;height:60px;border-radius:50%;border:0;cursor:pointer;",
    "background:var(--c);color:#fff;box-shadow:0 8px 24px rgba(0,0,0,.25);display:flex;align-items:center;",
    "justify-content:center;z-index:2147483000;transition:transform .15s}",
    ".bubble:hover{transform:scale(1.06)}.bubble:focus-visible{outline:3px solid #222;outline-offset:3px}",
    ".panel{position:fixed;right:20px;bottom:92px;width:370px;max-width:calc(100vw - 24px);height:560px;",
    "max-height:calc(100vh - 120px);background:#fff;color:#1d1d1f;border-radius:16px;overflow:hidden;",
    "box-shadow:0 18px 50px rgba(0,0,0,.28);display:flex;flex-direction:column;z-index:2147483000}",
    ".panel[hidden]{display:none}",
    "header{background:var(--c);color:#fff;padding:14px 16px;display:flex;align-items:center;gap:10px}",
    "header .t{font-weight:650;font-size:15px;flex:1}header .s{font-size:12px;opacity:.85;font-weight:400}",
    "header button{background:transparent;border:0;color:#fff;font-size:22px;cursor:pointer;line-height:1}",
    ".log{flex:1;overflow-y:auto;padding:14px;display:flex;flex-direction:column;gap:8px;background:#faf8f6}",
    ".m{max-width:85%;padding:9px 12px;border-radius:14px;font-size:14px;line-height:1.45;white-space:pre-wrap;",
    "word-wrap:break-word}",
    ".bot{background:#fff;border:1px solid #ece7e2;align-self:flex-start;border-bottom-left-radius:4px}",
    ".me{background:var(--c);color:#fff;align-self:flex-end;border-bottom-right-radius:4px}",
    ".err{background:#fff4f2;border:1px solid #f3c7bd;color:#8a2c14;align-self:flex-start}",
    ".chips{display:flex;flex-wrap:wrap;gap:6px;padding:0 14px 10px;background:#faf8f6}",
    ".chips button{border:1px solid var(--c);color:var(--c);background:#fff;border-radius:999px;padding:6px 11px;",
    "font-size:13px;cursor:pointer}.chips button:hover{background:var(--c);color:#fff}",
    "form{display:flex;gap:8px;padding:10px;border-top:1px solid #eee;background:#fff}",
    "input{flex:1;border:1px solid #ddd;border-radius:10px;padding:10px 12px;font-size:14px;outline:none}",
    "input:focus{border-color:var(--c)}",
    "form button{border:0;background:var(--c);color:#fff;border-radius:10px;padding:0 14px;font-size:14px;cursor:pointer}",
    "form button:disabled,input:disabled{opacity:.6;cursor:default}",
    ".note{font-size:11px;color:#8a8580;text-align:center;padding:0 10px 8px;background:#fff}",
    ".dots{display:inline-flex;gap:4px}.dots i{width:6px;height:6px;border-radius:50%;background:#bbb;",
    "animation:b 1s infinite}.dots i:nth-child(2){animation-delay:.15s}.dots i:nth-child(3){animation-delay:.3s}",
    "@keyframes b{0%,80%,100%{opacity:.3}40%{opacity:1}}",
    "@media (max-width:480px){.panel{right:8px;left:8px;width:auto;bottom:84px;height:calc(100vh - 100px)}}",
  ].join("");

  var ICON = '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3h11A2.5 2.5 0 0 1 20 5.5v8a2.5 2.5 0 0 1-2.5 2.5H10l-4.2 3.6c-.5.4-1.3.1-1.3-.6V16A2.5 2.5 0 0 1 4 13.5v-8Z" fill="currentColor"/></svg>';

  var host, root, panel, log, chips, form, input, sendBtn, bubble;
  var busy = false;

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function scroll() { log.scrollTop = log.scrollHeight; }

  function addMessage(who, text, remember) {
    log.appendChild(el("div", "m " + who, text));
    if (remember !== false && who !== "err") {
      state.messages.push({ who: who, text: text });
      state.messages = state.messages.slice(-40);
      save(state);
    }
    scroll();
  }

  function setChips(list) {
    chips.innerHTML = "";
    (list || []).forEach(function (label) {
      var b = el("button", "", label);
      b.type = "button";
      b.addEventListener("click", function () { send(label); });
      chips.appendChild(b);
    });
    state.chips = list || [];
    save(state);
  }

  function setBusy(on) {
    busy = on;
    input.disabled = on;
    sendBtn.disabled = on;
    var typing = root.querySelector(".typing");
    if (on && !typing) {
      typing = el("div", "m bot typing");
      typing.innerHTML = '<span class="dots"><i></i><i></i><i></i></span>';
      typing.setAttribute("aria-label", "The assistant is typing");
      log.appendChild(typing);
      scroll();
    } else if (!on && typing) {
      typing.remove();
    }
  }

  function request(path, body) {
    return fetch(BASE + path, body ? {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body)
    } : undefined).then(function (res) {
      return res.json().catch(function () { return {}; }).then(function (data) { return { ok: res.ok, data: data }; });
    });
  }

  function send(text) {
    text = (text || "").trim();
    if (!text || busy) return;
    if (text.length > 500) text = text.slice(0, 500);
    addMessage("me", text);
    setChips([]);
    input.value = "";
    setBusy(true);
    request("/chat", { message: text, session_id: state.session_id || null, page: location.href.slice(0, 300) })
      .then(function (r) {
        setBusy(false);
        if (r.data.session_id) { state.session_id = r.data.session_id; save(state); }
        if (r.ok && r.data.reply) {
          addMessage("bot", r.data.reply);
          setChips(r.data.quick_replies);
        } else {
          addMessage("err", r.data.error || "Sorry, something went wrong. Please try again.");
        }
        input.focus();
        flush();
      })
      .catch(function () {
        setBusy(false);
        addMessage("err", "Can't reach the assistant right now. Please check your connection and try again.");
      });
  }

  function flush() {
    if (pending && !busy) { var text = pending; pending = null; send(text); }
  }

  function greet() {
    if (state.messages.length || busy) return flush();
    setBusy(true);
    request("/greeting").then(function (r) {
      setBusy(false);
      addMessage("bot", (r.data && r.data.reply) || "Hi! How can I help you today?");
      setChips(r.data && r.data.quick_replies);
      flush();
    }).catch(function () {
      setBusy(false);
      addMessage("bot", "Hi! How can I help you today?");
      flush();
    });
  }

  function open() {
    panel.hidden = false;
    bubble.setAttribute("aria-expanded", "true");
    state.open = true;
    save(state);
    greet();
    setTimeout(function () { input.focus(); }, 50);
  }

  function close() {
    panel.hidden = true;
    bubble.setAttribute("aria-expanded", "false");
    state.open = false;
    save(state);
    bubble.focus();
  }

  function build() {
    host = el("div");
    host.id = "leaddesk-widget";
    document.body.appendChild(host);
    root = host.attachShadow({ mode: "open" });
    var style = el("style");
    style.textContent = CSS;
    root.appendChild(style);
    host.style.setProperty("--c", COLOR);

    bubble = el("button", "bubble");
    bubble.type = "button";
    bubble.innerHTML = ICON;
    bubble.setAttribute("aria-label", "Open chat");
    bubble.setAttribute("aria-expanded", "false");
    bubble.addEventListener("click", function () { panel.hidden ? open() : close(); });

    panel = el("section", "panel");
    panel.hidden = true;
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-label", TITLE);
    var header = el("header");
    var titles = el("div", "t", TITLE);
    titles.appendChild(el("div", "s", "Usually replies instantly"));
    var x = el("button", "", "×");
    x.type = "button";
    x.setAttribute("aria-label", "Close chat");
    x.addEventListener("click", close);
    header.appendChild(titles);
    header.appendChild(x);

    log = el("div", "log");
    log.setAttribute("aria-live", "polite");
    chips = el("div", "chips");
    form = el("form");
    input = el("input");
    input.type = "text";
    input.maxLength = 500;
    input.placeholder = "Type your message…";
    input.setAttribute("aria-label", "Your message");
    sendBtn = el("button", "", "Send");
    sendBtn.type = "submit";
    form.appendChild(input);
    form.appendChild(sendBtn);
    form.addEventListener("submit", function (e) { e.preventDefault(); send(input.value); });
    panel.addEventListener("keydown", function (e) { if (e.key === "Escape") close(); });

    panel.appendChild(header);
    panel.appendChild(log);
    panel.appendChild(chips);
    panel.appendChild(form);
    panel.appendChild(el("div", "note", NOTE));
    root.appendChild(panel);
    root.appendChild(bubble);

    state.messages.forEach(function (m) { addMessage(m.who, m.text, false); });
    setChips(state.chips);
    if (state.open) open();
  }

  window.LeadDesk = {
    open: function () { if (panel) open(); },
    ask: function (text) { if (!panel) return; pending = String(text || "").slice(0, 500); open(); },
    close: function () { if (panel) close(); }
  };
  if (document.body) build(); else document.addEventListener("DOMContentLoaded", build);
})();
