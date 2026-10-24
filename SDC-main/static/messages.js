"use strict";
(() => {
  const section = document.querySelector('[data-section="messages"]');
  if (!section) return;
  const $ = (selector) => section.querySelector(selector);
  const state = { session: { user: null, role: "guest", csrf_token: "" }, generation: 0, active: null, threads: [], messages: [], nextThreads: null, nextMessages: null, drafts: new Map(), acknowledged: new Map(), reading: new Set(), loading: false, sending: false, sequence: 0, threadSequence: 0, pendingNonce: null };
  let readTimer;
  const node = (tag, className, text) => {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  };
  const activeView = () => !section.hidden && !document.hidden;
  const date = (value) => {
    const parsed = new Date(value);
    return Number.isFinite(parsed.getTime()) ? new Intl.DateTimeFormat("en-MY", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Kuala_Lumpur" }).format(parsed) : "";
  };
  function status(text, error = false) {
    const box = $("#messages-status");
    box.textContent = text;
    box.hidden = !text;
    box.classList.toggle("error", error);
  }
  async function api(path, options = {}) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 20000);
    try {
      const response = await fetch(path, { ...options, signal: controller.signal, credentials: "same-origin", headers: { "Content-Type": "application/json", ...(options.method ? { "X-CSRF-Token": state.session.csrf_token || "" } : {}) } });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.error || "Messages could not load. Try refreshing.");
      return data;
    } catch (error) {
      if (error.name === "AbortError") throw new Error("Messages took too long to load. Check your connection and try again.");
      throw error;
    } finally { clearTimeout(timeout); }
  }
  function badge(count) {
    document.querySelectorAll("[data-message-unread], #messages-unread-count").forEach((element) => {
      element.textContent = count > 99 ? "99+" : String(count);
      element.hidden = !count;
    });
    $("#messages-total-unread").textContent = count ? `${count} unread` : "All caught up";
  }
  function renderThreads() {
    const list = $("#messages-threads");
    list.replaceChildren();
    if (!state.threads.length) list.append(node("p", "muted small", "Your conversations will appear here."));
    for (const thread of state.threads) {
      const button = node("button", "messages-thread");
      button.type = "button";
      button.setAttribute("aria-current", String(thread.id === state.active));
      const heading = node("span", "messages-thread-title");
      heading.append(node("strong", "", thread.counterpart));
      if (thread.unread_count) heading.append(node("span", "messages-unread-count", thread.unread_count));
      button.append(heading, node("p", "", thread.job_title), node("p", "", thread.last_message?.preview || "Start the conversation."));
      if (thread.last_message) button.append(node("time", "", date(thread.last_message.created_at)));
      button.addEventListener("click", () => selectThread(thread.id));
      list.append(button);
    }
    $("#messages-more-threads").hidden = !state.nextThreads;
  }
  async function loadThreads(append = false) {
    if (!state.session.user) return;
    const generation = state.generation, sequence = ++state.threadSequence;
    const path = `/api/messages/threads${append && state.nextThreads ? `?before=${state.nextThreads}` : ""}`;
    const data = await api(path);
    if (generation !== state.generation || sequence !== state.threadSequence) return;
    const previousCursor = state.nextThreads;
    const byId = new Map([...state.threads, ...data.threads].map((item) => [item.id, item]));
    state.threads = [...byId.values()].sort((a, b) => b.id - a.id);
    state.nextThreads = append ? data.next_before : previousCursor || (data.has_more ? Math.min(...state.threads.map((item) => item.id)) : null);
    badge(data.unread_count);
    renderThreads();
  }
  function renderMessages(keepScroll = false) {
    const history = $("#messages-history"), previousHeight = history.scrollHeight, previousTop = history.scrollTop;
    const nearBottom = history.scrollHeight - history.scrollTop - history.clientHeight < 80;
    const signature = state.messages.map((item) => item.id).join(",");
    if (history.dataset.signature !== signature) {
      history.replaceChildren();
      if (!state.messages.length) history.append(node("p", "muted small", "No messages yet. Say hello and ask your question."));
      for (const item of state.messages) {
        const article = node("article", `message-bubble${item.mine ? " message-mine" : ""}`);
        article.dataset.messageId = item.id;
        article.append(node("strong", "", item.mine ? "You" : item.sender_name), node("p", "", item.body), node("time", "", date(item.created_at)));
        history.append(article);
      }
      history.dataset.signature = signature;
      if (keepScroll) history.scrollTop = previousTop + history.scrollHeight - previousHeight;
      else if (nearBottom) history.scrollTop = history.scrollHeight;
    }
    $("#messages-older").hidden = !state.nextMessages;
  }
  async function acknowledgeDisplayed() {
    if (!activeView() || !state.active || !state.session.user) return false;
    const identifier = state.active, generation = state.generation;
    if (state.reading.has(identifier)) return false;
    const viewport = $("#messages-history").getBoundingClientRect();
    const top = Math.max(0, viewport.top), bottom = Math.min(innerHeight, viewport.bottom);
    const acknowledged = state.acknowledged.get(identifier) || new Set();
    const incoming = new Set(state.messages.filter((message) => !message.mine).map((message) => message.id));
    const displayed = [];
    $("#messages-history").querySelectorAll("[data-message-id]").forEach((element) => {
      const rect = element.getBoundingClientRect();
      const messageId = Number(element.dataset.messageId);
      if (top < bottom && rect.top < bottom && rect.bottom > top && incoming.has(messageId) && !acknowledged.has(messageId)) displayed.push(messageId);
    });
    if (!displayed.length) return false;
    state.reading.add(identifier);
    try {
      for (let offset = 0; offset < displayed.length; offset += 100) {
        const messageIds = displayed.slice(offset, offset + 100);
        await api(`/api/messages/threads/${identifier}/read`, { method: "POST", body: JSON.stringify({ message_ids: messageIds }) });
        if (generation !== state.generation) return false;
        messageIds.forEach((messageId) => acknowledged.add(messageId));
        state.acknowledged.set(identifier, acknowledged);
      }
      return true;
    } finally { if (generation === state.generation) state.reading.delete(identifier); }
  }
  async function loadMessages(older = false) {
    if (!state.active || !state.session.user) return;
    const generation = state.generation, identifier = state.active, sequence = ++state.sequence;
    const data = await api(`/api/messages/threads/${identifier}/messages${older && state.nextMessages ? `?before=${state.nextMessages}` : ""}`);
    if (generation !== state.generation || identifier !== state.active || sequence !== state.sequence) return;
    if (older) {
      state.messages = [...data.messages.filter((item) => !state.messages.some((message) => message.id === item.id)), ...state.messages];
      state.nextMessages = data.next_before;
    } else if (state.messages.length) {
      // Bridge every new page back to loaded history before merging. A burst
      // larger than one page must never leave an unreachable gap in the thread.
      const newestLoaded = state.messages[state.messages.length - 1].id;
      const received = [...data.messages];
      let page = data;
      while (page.has_more && page.messages[0]?.id > newestLoaded) {
        page = await api(`/api/messages/threads/${identifier}/messages?before=${page.next_before}`);
        if (generation !== state.generation || identifier !== state.active || sequence !== state.sequence) return;
        received.push(...page.messages);
      }
      const byId = new Map([...state.messages, ...received].map((item) => [item.id, item]));
      state.messages = [...byId.values()].sort((a, b) => a.id - b.id);
    } else {
      state.messages = data.messages;
      state.nextMessages = data.next_before;
    }
    $("#messages-counterpart").textContent = data.thread.counterpart;
    $("#messages-job").textContent = `${data.thread.job_title} · ${data.thread.company.name}`;
    renderMessages(older);
    if (await acknowledgeDisplayed()) if (generation === state.generation) await loadThreads();
  }
  async function selectThread(identifier) {
    const generation = state.generation;
    if (state.active) state.drafts.set(state.active, $("#message-body").value);
    state.active = identifier;
    state.messages = [];
    state.nextMessages = null;
    $("#messages-history").dataset.signature = "";
    $("#messages-history").replaceChildren(node("p", "muted small", "Loading conversation…"));
    $("#message-body").value = state.drafts.get(identifier) || "";
    $("#messages-select-prompt").hidden = true;
    $("#messages-detail").hidden = false;
    $("#message-body").dispatchEvent(new Event("input"));
    renderThreads();
    try { await loadMessages(); if (generation === state.generation) status(""); } catch (error) { if (generation === state.generation) status(error.message, true); }
  }
  async function refresh() {
    if (state.loading || !state.session.user || !activeView()) return;
    const generation = state.generation;
    state.loading = true;
    try {
      await loadThreads();
      if (generation === state.generation && state.active && !state.sending) await loadMessages();
    } catch (error) { if (generation === state.generation) status(error.message, true); }
    finally { if (generation === state.generation) state.loading = false; }
  }
  function applySession(session) {
    const previousId = state.session.user?.id;
    state.session = session || { user: null, role: "guest", csrf_token: "" };
    if (previousId !== state.session.user?.id) {
      state.generation++;
      state.active = null; state.threads = []; state.messages = []; state.drafts.clear(); state.acknowledged.clear(); state.reading.clear(); state.pendingNonce = null;
      state.loading = false; state.sending = false; state.nextThreads = null; state.nextMessages = null;
      $("#message-body").value = "";
      $("#message-send").disabled = false;
      $("#message-send").textContent = "Send message";
      $("#messages-detail").hidden = true;
      $("#messages-select-prompt").hidden = false;
      $("#messages-history").replaceChildren();
      $("#messages-counterpart").textContent = "";
      $("#messages-job").textContent = "";
      badge(0); renderThreads(); status("");
    }
    $("#messages-guest").hidden = Boolean(state.session.user);
    $("#messages-workspace").hidden = !state.session.user;
    $("#messages-refresh").hidden = !state.session.user;
    if (state.session.user) loadThreads().catch((error) => status(error.message, true));
  }
  $("#message-compose").addEventListener("submit", async (event) => {
    event.preventDefault();
    const body = $("#message-body").value.trim();
    if (state.sending || !state.active || !body || !$("#message-compose").reportValidity()) return;
    const generation = state.generation, identifier = state.active, button = $("#message-send");
    if (!state.pendingNonce || state.pendingNonce.body !== body || state.pendingNonce.thread !== identifier) state.pendingNonce = { body, thread: identifier, nonce: globalThis.crypto?.randomUUID?.() || `message_${Date.now()}_${Math.random().toString(36).slice(2)}` };
    state.sending = true; button.disabled = true; button.textContent = "Sending…";
    try {
      await api(`/api/messages/threads/${identifier}/messages`, { method: "POST", body: JSON.stringify({ body, client_nonce: state.pendingNonce.nonce }) });
      if (generation !== state.generation) return;
      state.drafts.delete(identifier); state.pendingNonce = null;
      if (state.active === identifier) {
        if ($("#message-body").value.trim() === body) $("#message-body").value = "";
        $("#message-body").dispatchEvent(new Event("input"));
        await loadMessages();
        if (generation !== state.generation) return;
        $("#messages-history").scrollTop = $("#messages-history").scrollHeight;
        await acknowledgeDisplayed();
        if (generation !== state.generation) return;
      }
      await loadThreads();
      if (generation === state.generation) status("Message sent.");
    } catch (error) { if (generation === state.generation) status(error.message, true); }
    finally { if (generation === state.generation) { state.sending = false; button.disabled = false; button.textContent = "Send message"; } }
  });
  $("#message-body").addEventListener("input", () => { $("#message-length").textContent = `${$("#message-body").value.length.toLocaleString()} / 2,000`; });
  function queueRead() {
    clearTimeout(readTimer);
    readTimer = setTimeout(() => {
      if (activeView()) acknowledgeDisplayed().then((changed) => { if (changed) return loadThreads(); }).catch(() => {});
    }, 150);
  }
  $("#messages-history").addEventListener("scroll", queueRead, { passive: true });
  window.addEventListener("scroll", queueRead, { passive: true });
  $("#messages-refresh").addEventListener("click", refresh);
  $("#messages-signin").addEventListener("click", () => window.NextStepWorkspace?.openAccess());
  $("#messages-more-threads").addEventListener("click", () => loadThreads(true).catch((error) => status(error.message, true)));
  $("#messages-older").addEventListener("click", () => loadMessages(true).catch((error) => status(error.message, true)));
  document.addEventListener("nextstep:session", (event) => applySession(event.detail));
  document.addEventListener("nextstep:view", (event) => { if (event.detail.view === "messages") refresh(); });
  document.addEventListener("visibilitychange", () => { if (activeView()) refresh(); });
  document.addEventListener("nextstep:open-chat", async (event) => {
    window.NextStep?.navigate("messages");
    if (!state.session.user) { window.NextStepWorkspace?.openAccess(); return; }
    const generation = state.generation;
    try {
      const data = await api("/api/messages/threads", { method: "POST", body: JSON.stringify(event.detail || {}) });
      if (generation !== state.generation) return;
      await loadThreads();
      if (generation !== state.generation) return;
      await selectThread(data.thread.id);
      if (generation !== state.generation) return;
      $("#message-body").focus();
    } catch (error) { if (generation === state.generation) status(error.message, true); }
  });
  setInterval(() => {
    if (document.hidden || !state.session.user) return;
    if (activeView()) refresh();
    else loadThreads().catch(() => {});
  }, 10000);
  if (window.NextStepWorkspace?.session) applySession(window.NextStepWorkspace.session());
})();
