/* Extracted radar interactions; unrelated whole-app state/navigation removed. */
"use strict";
(() => {
  const colors = {1:"#e5243b",2:"#dda63a",3:"#4c9f38",4:"#c5192d",5:"#ff3a21",6:"#26bde2",7:"#fcc30b",8:"#a21942",9:"#fd6925",10:"#dd1367",11:"#fd9d24",12:"#bf8b2e",13:"#3f7e44",14:"#0a97d9",15:"#56c02b",16:"#00689d",17:"#19486a"};
  const paths = {
    rising: '<path d="m3 17 6-6 4 4 8-10M15 5h6v6"/>',
    declining: '<path d="m3 7 6 6 4-4 8 10M15 19h6v-6"/>',
    stable: '<path d="M4 12h16M16 8l4 4-4 4"/>'
  };
  const e = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[c]);
  const integer = value => Number.isFinite(Number(value)) ? Math.round(Number(value)).toLocaleString() : "0";
  function safeURL(value) {
    try { const url = new URL(value); return ["https:","http:"].includes(url.protocol) ? url.href : null; }
    catch { return null; }
  }
  function date(value, full = false) {
    if (!value) return "Not available";
    const parsed = new Date(value);
    if (!Number.isFinite(parsed.getTime())) return "Not available";
    return parsed.toLocaleString("en-MY", {
      day: "numeric", month: "short", year: "numeric", timeZone: "Asia/Kuala_Lumpur",
      ...(full ? {hour:"2-digit",minute:"2-digit"} : {})
    });
  }
  function trend(item) {
    const label = ["rising", "declining", "stable"].includes(item?.label) ? item.label : "insufficient";
    const text = {rising:"Rising",declining:"Declining",stable:"Stable",insufficient:"Limited evidence"}[label];
    const icon = paths[label] ? `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[label]}</svg>` : "◦";
    return `<span class="trend-badge ${label}">${icon}${text}</span>`;
  }
  async function json(url, signal) {
    const response = await fetch(url, {signal, headers:{Accept:"application/json"}});
    if (!response.ok) throw new Error(`Unable to load radar (${response.status}).`);
    return response.json();
  }
  const mounted = new WeakMap();
  function mount(root, options = {}) {
    if (mounted.has(root)) return mounted.get(root);
    const $ = selector => root.querySelector(selector);
    const search = $("[data-sr-search]");
    const filter = $("[data-sr-filter]");
    const body = $("[data-sr-body]");
    const monitor = $("[data-sr-monitor]");
    const tabs = [...root.querySelectorAll("[data-sr-tab]")];
    const radarUrl = options.radarUrl ?? root.dataset.radarUrl;
    const monitorUrl = options.monitorUrl ?? root.dataset.monitorUrl;
    const controller = new AbortController();
    let data = options.data ?? window.SKILLS_RADAR_PREVIEW ?? {skills:[],roles:[]};
    let tab = "skills", revision = null, timer = null, busy = false, destroyed = false;
    const pollMs = Math.max(5000, Number(options.pollMs) || 20000);

    function badges(ids) {
      return (ids || []).map(id => {
        const goal = (data.sdgs || []).find(goal => Number(goal.id) === Number(id));
        const url = safeURL(goal?.url) || `https://sdgs.un.org/goals/goal${Number(id)}`;
        return `<a class="sdg-badge" href="${e(url)}" target="_blank" rel="noopener noreferrer" title="${e(goal?.title || `Goal ${id}`)}"><span class="sdg-dot" style="--sdg-color:${colors[Number(id)] || '#689656'}"></span>SDG ${e(id)}</a>`;
      }).join("");
    }
    function render() {
      const query = search.value.toLowerCase().trim();
      const items = (data[tab] || []).filter(item =>
        (item.name || item.title || "").toLowerCase().includes(query) &&
        (filter.value === "all" || (item.label || "insufficient") === filter.value)
      );
      body.innerHTML = items.length ? items.map(item => {
        const evidence = item.evidence?.[0];
        const url = safeURL(evidence?.url);
        return `<tr><td>${e(item.name || item.title)}</td><td>${integer(item.recent_count)}</td><td>${integer(item.previous_count)}</td><td>${trend(item)}</td><td><div class="sdg-badges">${badges(item.sdgs)}</div></td><td>${url ? `<a class="evidence-link" href="${e(url)}" target="_blank" rel="noopener noreferrer">${evidence.kind === 'ai_release' ? 'View AI release' : 'View posting'} ↗</a><time class="evidence-date" datetime="${e(evidence.date)}">${e(date(evidence.date))}</time>` : '<span class="muted small">No current evidence</span>'}</td></tr>`;
      }).join("") : '<tr><td colspan="6"><div class="empty-state">No signals match your search. Try another skill, role, or signal filter.</div></td></tr>';
    }
    function showSnapshotStatus() {
      const stamp = data.signal_status?.fetched_at;
      monitor.textContent = `Dated snapshot${stamp ? `: ${date(stamp, true)} MYT` : ''}. Automatic source refresh is off in this preview.`;
    }
    function setData(value) {
      if (!value || !Array.isArray(value.skills) || !Array.isArray(value.roles)) throw new Error("Expected radar data with skills and roles arrays.");
      data = value;
      render();
      if (!monitorUrl) showSnapshotStatus();
    }
    async function reload() {
      if (!radarUrl || destroyed) return;
      root.setAttribute("aria-busy", "true");
      try { setData(await json(radarUrl, controller.signal)); }
      finally { if (!destroyed) root.setAttribute("aria-busy", "false"); }
    }
    async function poll() {
      if (busy || destroyed || document.hidden) return;
      busy = true;
      try {
        const status = await json(monitorUrl, controller.signal);
        // Reload whenever the evidence revision differs, including on the first
        // poll. This closes the race between initial data and status requests.
        if (status.revision !== revision) { await reload(); revision = status.revision; }
        monitor.textContent = status.enabled
          ? `Automatic source refresh every ${Math.round(status.interval_seconds / 60)} minutes. ${status.refreshing ? 'Checking sources now.' : status.next_refresh_at ? `Next check: ${date(status.next_refresh_at, true)} MYT.` : 'Waiting for the next source check.'}${status.last_error ? ' Latest check could not refresh; using dated cached evidence.' : ''}`
          : 'Automatic source refresh is paused. Showing dated source evidence.';
      } catch (error) {
        if (error.name !== "AbortError") monitor.textContent = "Automatic update status is unavailable. Showing the last loaded dated evidence.";
      } finally {
        busy = false;
        if (!destroyed) { clearTimeout(timer); timer = setTimeout(poll, pollMs); }
      }
    }
    search.addEventListener("input", render, {signal:controller.signal});
    filter.addEventListener("change", render, {signal:controller.signal});
    tabs.forEach(button => button.addEventListener("click", () => {
      tab = button.dataset.srTab;
      tabs.forEach(item => {
        const selected = item === button;
        item.classList.toggle("selected", selected);
        item.setAttribute("aria-pressed", String(selected));
      });
      render();
    }, {signal:controller.signal}));
    document.addEventListener("visibilitychange", () => {
      clearTimeout(timer);
      if (!document.hidden && monitorUrl) poll();
    }, {signal:controller.signal});
    const api = {
      setData, reload,
      destroy() { destroyed = true; clearTimeout(timer); controller.abort(); mounted.delete(root); }
    };
    mounted.set(root, api);
    render();
    if (!radarUrl) showSnapshotStatus();
    api.ready = (async () => {
      try { await reload(); }
      catch (error) { if (error.name !== "AbortError") monitor.textContent = "Radar data is unavailable. Check the configured API address."; }
      if (monitorUrl) await poll();
    })();
    return api;
  }
  window.SkillsRadar = {mount};
  const start = () => document.querySelectorAll("[data-skills-radar]").forEach(root => mount(root));
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start, {once:true});
  else start();
})();
