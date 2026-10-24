"use strict";
(() => {
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [
    ...root.querySelectorAll(selector),
  ];
  const e = (value) =>
    String(value ?? "").replace(
      /[&<>"']/g,
      (c) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[c],
    );
  const n = (value) => (Number.isFinite(Number(value)) ? Number(value) : 0);
  const pct = (value) => Math.max(0, Math.min(100, n(value)));
  const integer = (value) => Math.round(n(value)).toLocaleString();
  const safeURL = (value) => {
    try {
      const url = new URL(value);
      return ["https:", "http:"].includes(url.protocol) ? url.href : "#";
    } catch {
      return "#";
    }
  };
  const icons = {
    "arrow-up-right": '<path d="M5 19 19 5M5 5h14v14"/>',
    overview:
      '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
    radar:
      '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/><path d="m12 12 7-7"/>',
    briefcase:
      '<rect x="3" y="7" width="18" height="14" rx="2"/><path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M3 12a24 24 0 0 0 18 0M12 11v4"/>',
    path: '<circle cx="6" cy="5" r="2"/><circle cx="18" cy="19" r="2"/><path d="M6 7v6a4 4 0 0 0 4 4h4a4 4 0 0 0 4-4V5M14 8l4-4 4 4"/>',
    sources:
      '<path d="M4 4h11l5 5v11a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1zM14 4v6h6M7 14h9M7 17h7"/>',
    leaf: '<path d="M20 3c-1 8 0 15-9 15a7 7 0 0 1-7-7c0-8 10-6 16-8zM3 21 15 9M8 16v-5M8 16h5"/>',
    download:
      '<path d="M12 3v12m-5-5 5 5 5-5M4 16v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4"/>',
    help: '<circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 1 1 4.3 1.7c-1.8 1.3-1.8 1.3-1.8 3.3M12 17h.01"/>',
    person:
      '<circle cx="12" cy="8" r="3.5"/><path d="M5 21v-2a7 7 0 0 1 14 0v2"/>',
    shield: '<path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6zM8 12l3 3 5-6"/>',
    refresh:
      '<path d="M20 7v5h-5M4 17v-5h5M5.6 7a8 8 0 0 1 13.6-1L20 8M4 16l.8 2a8 8 0 0 0 13.6-1"/>',
    search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/>',
    edit: '<path d="m14 5 5 5M4 20l5-1L21 7a2.1 2.1 0 0 0-4-4L5 15z"/>',
    sliders:
      '<path d="M4 6h5m4 0h7M4 12h10m4 0h2M4 18h2m4 0h10"/><circle cx="11" cy="6" r="2"/><circle cx="16" cy="12" r="2"/><circle cx="8" cy="18" r="2"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    spark:
      '<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5z"/>',
    check: '<path d="m5 12 4 4L19 6"/>',
    rising: '<path d="m3 17 6-6 4 4 8-10M15 5h6v6"/>',
    declining: '<path d="m3 7 6 6 4-4 8 10M15 19h6v-6"/>',
    stable: '<path d="M4 12h16M16 8l4 4-4 4"/>',
    cart: '<path d="M3 3h2l3 12h11l2-9H6M9 21h.01M18 21h.01"/><circle cx="9" cy="20" r="1"/><circle cx="18" cy="20" r="1"/>',
    calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 11h18M8 15h2M14 15h2"/>',
    people: '<circle cx="9" cy="8" r="3"/><path d="M3 21v-2a6 6 0 0 1 12 0v2M16 5a3 3 0 0 1 0 6M18 15a5 5 0 0 1 3 4v2"/>',
    message: '<path d="M21 11.5a8.4 8.4 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7a8.4 8.4 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.4 8.4 0 0 1 3.8-.9h.5a8.5 8.5 0 0 1 8 8v.5Z"/>',
    bell: '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/>',
  };
  const icon = (name) =>
    `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name] || icons.spark}</svg>`;
  const state = {
    catalog: null,
    radar: null,
    matches: [],
    profile: null,
    matchSignalStatus: null,
    scenario: "moderate",
    appliedScenario: "moderate",
    scenarioBusy: false,
    radarTab: "skills",
    selectedRole: null,
    matchSequence: 0,
    radarSequence: 0,
    progress: readProgress(),
    progressKey: "nextstep-progress",
    ready: false,
    toastTimer: null,
    evidenceRevision: null,
    monitorTimer: null,
    monitorBusy: false,
  };
  const viewNames = {
    overview: "Overview",
    radar: "Skills radar",
    matches: "Career matches",
    pathway: "My learning path",
    sources: "Evidence & sources",
    jobs: "Find a job",
    applications: "My applications",
    applicants: "Applicant inbox",
    profile: "My profile",
    calendar: "Calendar",
    messages: "Messages",
  };
  const sdgColors = {
    1: "#e5243b",
    2: "#dda63a",
    3: "#4c9f38",
    4: "#c5192d",
    5: "#ff3a21",
    6: "#26bde2",
    7: "#fcc30b",
    8: "#a21942",
    9: "#fd6925",
    10: "#dd1367",
    11: "#fd9d24",
    12: "#bf8b2e",
    13: "#3f7e44",
    14: "#0a97d9",
    15: "#56c02b",
    16: "#00689d",
    17: "#19486a",
  };
  function readProgress(key = "nextstep-progress") {
    try {
      const data = JSON.parse(
        localStorage.getItem(key) || "{}",
      );
      return data && typeof data === "object" && !Array.isArray(data)
        ? data
        : {};
    } catch {
      return {};
    }
  }
  function saveProgress() {
    try {
      localStorage.setItem(state.progressKey, JSON.stringify(state.progress));
    } catch {
      toast(
        "Your browser could not save progress. It will last for this session.",
      );
    }
  }
  function decorate() {
    $$("[data-icon]").forEach((el) => (el.innerHTML = icon(el.dataset.icon)));
    $$("[data-sdg-color]").forEach((el) =>
      el.style.setProperty(
        "--sdg-color",
        sdgColors[n(el.dataset.sdgColor)] || "#689656",
      ),
    );
    $$("[data-score]").forEach((el) =>
      el.style.setProperty("--score", pct(el.dataset.score)),
    );
    $$("[data-bar]").forEach(
      (el) => (el.style.width = `${pct(el.dataset.bar)}%`),
    );
  }
  function date(value, full = false) {
    if (!value) return "Not available";
    const parsed = new Date(value);
    if (!Number.isFinite(parsed.getTime())) return String(value);
    return parsed.toLocaleString(
      "en-MY",
      full
        ? {
            day: "numeric",
            month: "short",
            year: "numeric",
            hour: "2-digit",
            minute: "2-digit",
            timeZone: "Asia/Kuala_Lumpur",
          }
        : {
            day: "numeric",
            month: "short",
            year: "numeric",
            timeZone: "Asia/Kuala_Lumpur",
          },
    );
  }
  function relative(value) {
    if (!value) return "No refresh yet";
    const hours = Math.max(
      0,
      Math.floor((Date.now() - new Date(value).getTime()) / 3600000),
    );
    return hours < 1
      ? "Updated recently"
      : hours < 24
        ? `Updated ${hours}h ago`
        : `Updated ${Math.floor(hours / 24)}d ago`;
  }
  function sdg(id) {
    return (
      (state.catalog?.sdgs || []).find((x) => n(x.id) === n(id)) || {
        id,
        title: `Goal ${id}`,
        description:
          "Explore the goal and consider how your work can contribute.",
        url: `https://sdgs.un.org/goals/goal${id}`,
      }
    );
  }
  function badges(ids) {
    return (ids || [])
      .map((id) => {
        const goal = sdg(id);
        return `<a class="sdg-badge" href="${e(safeURL(goal.url))}" target="_blank" rel="noopener noreferrer" title="${e(goal.title)}"><span class="sdg-dot" data-sdg-color="${e(id)}"></span>SDG ${e(id)}</a>`;
      })
      .join("");
  }
  function skillChips(skills, missing = false) {
    return (skills || [])
      .map(
        (s) =>
          `<span class="skill-chip ${missing ? "missing" : ""}" title="SDG ${(s.sdgs || []).map(e).join(", ")}">${missing ? "＋" : "✓"} ${e(s.name || s.id)}</span>`,
      )
      .join("");
  }
  function trend(item) {
    const label = ["rising", "declining", "stable"].includes(item?.label)
      ? item.label
      : "insufficient";
    const text = {
      rising: "Rising",
      declining: "Declining",
      stable: "Stable",
      insufficient: "Limited evidence",
    }[label];
    return `<span class="trend-badge ${label}">${label !== "insufficient" ? icon(label) : "◦"}${text}</span>`;
  }
  function evidence(items, limit = 3) {
    return (items || [])
      .slice(0, limit)
      .map(
        (item) =>
          `<li><a href="${e(safeURL(item.url))}" target="_blank" rel="noopener noreferrer">${e(item.title || "View source")} ↗</a>${item.date || item.published_at ? `<time>${e(date(item.date || item.published_at))}</time>` : ""}</li>`,
      )
      .join("");
  }
  function statusHTML(status) {
    const label =
      status?.status === "live"
        ? "Fresh source snapshot"
        : status?.status === "cached"
          ? "Cached source snapshot"
          : "Source unavailable";
    return `<span class="status-label"><span class="status-dot ${e(status?.status || "offline")}"></span>${label}</span>`;
  }
  function showView(name) {
    if (!viewNames[name]) name = "overview";
    $$("[data-section]").forEach(
      (el) => (el.hidden = el.dataset.section !== name),
    );
    $$(".nav-item").forEach((el) => {
      el.classList.toggle("active", el.dataset.view === name);
      if (el.dataset.view === name) el.setAttribute("aria-current", "page");
      else el.removeAttribute("aria-current");
    });
    $("#breadcrumb-title").textContent = viewNames[name];
    document.title = `${viewNames[name]} — NextStep`;
    document.dispatchEvent(new CustomEvent("nextstep:view", {bubbles: true, detail: {view: name}}));
  }
  function toast(message) {
    const box = $("#toast");
    box.textContent = message;
    box.hidden = false;
    clearTimeout(state.toastTimer);
    state.toastTimer = setTimeout(() => (box.hidden = true), 5000);
  }
  function alert(message) {
    const box = $("#app-alert");
    if (!message) {
      box.hidden = true;
      box.replaceChildren();
      return;
    }
    box.innerHTML = `<span>${e(message)}</span><button type="button" data-dismiss-alert>Dismiss</button>`;
    box.hidden = false;
  }
  async function api(path, options = {}) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 35000);
    try {
      const response = await fetch(path, {
        ...options,
        signal: controller.signal,
        headers: {
          "Content-Type": "application/json",
          ...(options.headers || {}),
        },
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok)
        throw new Error(
          data.error || data.message || `Request failed (${response.status})`,
        );
      return data;
    } catch (error) {
      if (error.name === "AbortError")
        throw new Error(
          "The request took too long. Try again; cached data may still be available.",
        );
      throw error;
    } finally {
      clearTimeout(timeout);
    }
  }
  function fillProfile(profile) {
    if (!profile) return;
    const values = new Set(profile.skills || []);
    $$("#skill-picker input").forEach(
      (el) => (el.checked = values.has(el.value)),
    );
    $("#interests").value = profile.interests || "";
    $("#weekly-hours").value = profile.weekly_hours || 6;
    updateSkillCount();
  }
  function updateSkillCount() {
    $("#selected-skill-count").textContent =
      `${$$("#skill-picker input:checked").length} selected`;
  }
  function getProfile() {
    return {
      skills: $$("#skill-picker input:checked").map((el) => el.value),
      interests: $("#interests").value.trim(),
      weekly_hours: n($("#weekly-hours").value),
      scenario: state.scenario,
    };
  }
  function renderCatalogue() {
    const cat = state.catalog;
    $("#demo-profile").innerHTML = (cat.profiles || [])
      .map(
        (profile) =>
          `<option value="${e(profile.id)}">${e(profile.label)}</option>`,
      )
      .join("");
    $("#skill-picker").innerHTML = (cat.skills || [])
      .map(
        (skill) =>
          `<label class="skill-checkbox"><input type="checkbox" name="skills" value="${e(skill.id)}"><span title="Connected to SDG ${(skill.sdgs || []).map(e).join(", ")}">${e(skill.name)}</span></label>`,
      )
      .join("");
    $("#sdg-legend").innerHTML = (cat.sdgs || [])
      .map(
        (goal) =>
          `<a class="sdg-badge" href="${e(safeURL(goal.url))}" target="_blank" rel="noopener noreferrer"><span class="sdg-dot" data-sdg-color="${e(goal.id)}"></span>${e(goal.id)} · ${e(goal.title)}</a>`,
      )
      .join("");
    fillProfile(cat.profiles?.[0]);
    decorate();
  }
  function renderOverview() {
    const selected = (state.profile?.skills || []).length;
    const match = state.matches[0];
    const allGoals = new Set(state.matches.flatMap((m) => m.sdgs || []));
    const status = state.radar?.signal_status || {};
    const stats = [
      { number: selected, label: "Skills in your profile", icon: "person" },
      {
        number: state.matches.length,
        label: "Career paths to explore",
        icon: "briefcase",
      },
      {
        number: match?.pathway?.weeks || 0,
        suffix: "weeks",
        label: "Estimated top-match pathway",
        icon: "clock",
      },
      {
        number: allGoals.size,
        label: "SDGs your paths connect to",
        icon: "leaf",
      },
    ];
    $("#overview-stats").innerHTML = stats
      .map(
        (item) =>
          `<article class="stat-card"><div class="stat-icon">${icon(item.icon)}</div><div><div class="stat-number">${integer(item.number)}${item.suffix ? ` <span>${e(item.suffix)}</span>` : ""}</div><div class="stat-label">${e(item.label)}</div></div></article>`,
      )
      .join("");
    $("#overview-signal-status").innerHTML =
      `${statusHTML(status)}<span>${integer(status.jobs_count)} public postings · ${e(relative(status.fetched_at))}</span>`;
    $("#top-match-card").innerHTML = match
      ? `<div class="top-match-header"><span class="card-kicker">A PROMISING NEXT STEP</span><span class="top-pick-badge">Top match</span></div><div class="top-match-main"><div class="score-ring" data-score="${pct(match.score)}"><div><strong>${Math.round(pct(match.score))}<span>%</span></strong><small>match score</small></div></div><div><h3>${e(match.title)}</h3><p>${e(match.summary)}</p></div></div><div class="skill-block"><p class="skill-block-label">Skills you bring</p><div class="skill-chip-list">${skillChips(match.matched_skills) || '<span class="muted small">A fresh starting point — build the core skills below.</span>'}</div></div><div class="skill-block"><p class="skill-block-label">Room to grow</p><div class="skill-chip-list">${skillChips((match.missing_skills || []).slice(0, 4), true) || '<span class="skill-chip">✓ All catalogue skills covered</span>'}</div></div><div class="sdg-badges">${badges(match.sdgs)}</div><div class="top-match-bottom"><span class="tiny-meta">${icon("clock")}${integer(match.pathway?.total_hours)} learning hours · estimated</span><button class="button button-primary" type="button" data-start-role="${e(match.id)}">See my learning path <span aria-hidden="true">→</span></button></div>`
      : `<div class="empty-state"><h3>Your next step starts here.</h3><p>Select your current skills and interests to explore career paths.</p></div>`;
    const radar = (state.radar?.skills || [])
      .filter((s) => n(s.recent_count) + n(s.previous_count) > 0)
      .sort((a, b) => n(b.recent_count) - n(a.recent_count))
      .slice(0, 4);
    const max = Math.max(1, ...radar.map((s) => n(s.recent_count)));
    $("#mini-radar").innerHTML = radar.length
      ? radar
          .map(
            (skill) =>
              `<article class="mini-radar-card"><div class="mini-radar-top"><h3>${e(skill.name)}</h3>${trend(skill)}</div><div class="mini-radar-count">${integer(skill.recent_count)}<span>recent postings</span></div><div class="mini-bar"><span data-bar="${(n(skill.recent_count) / max) * 100}"></span></div></article>`,
          )
          .join("")
      : '<div class="empty-state"><p>No skill signals are available yet. Refresh the public source in Skills radar.</p></div>';
    decorate();
  }
  function renderSource() {
    const status = state.radar?.signal_status || {};
    const visibleTrend = (state.radar?.skills || []).find(skill => skill.label === "rising");
    $("#top-trend-summary").textContent = visibleTrend
      ? `${visibleTrend.name} · ${integer(visibleTrend.recent_count)} recent sampled postings · ${status.status || "offline"}`
      : `${integer(status.jobs_count)} dated sample postings · ${status.status || "offline"}`;
    const sourceLink = `<a class="evidence-link" href="${e(safeURL(status.source_url))}" target="_blank" rel="noopener noreferrer">${e(status.source_name || "Public job feed")} ↗</a>`;
    const banner = `<div><strong>${sourceLink} · ${integer(status.jobs_count)} public postings</strong><p>Snapshot: ${e(date(status.fetched_at, true))} MYT${status.active_jobs_count !== undefined ? ` · ${integer(status.active_jobs_count)} active postings` : ""}</p><p>${e(status.message || "No source status available.")}</p>${status.scope ? `<p>${e(status.scope)}</p>` : ""}</div>${statusHTML(status)}`;
    $("#radar-source-banner").innerHTML = banner;
    $("#sources-status").innerHTML =
      `<div class="evidence-banner">${banner}</div>${status.ai_source_name ? `<article class="card method-card ai-feed-card"><div class="card-kicker">AI ADVANCEMENT SIGNALS</div><h2>${e(status.ai_source_name)}</h2><p>AI technology updates are a separate context feed. Release activity is not evidence of job growth or decline. Last fetched ${e(date(status.ai_fetched_at, true))} MYT.</p><a class="text-link" href="${e(safeURL(status.ai_source_url))}" target="_blank" rel="noopener noreferrer">View source ↗</a><ul class="evidence-list ai-updates">${evidence(status.ai_updates, 5) || "<li>No AI updates are cached yet.</li>"}</ul></article>` : ""}`;
    const windows = status.windows || {};
    $("#radar-window-note").textContent =
      `Recent window: ${date(windows.recent_start)} – ${date(windows.recent_end)}. Earlier window: ${date(windows.previous_start)} – ${date(windows.previous_end)}. Dates are UTC; starts are inclusive and ends exclusive. Counts use this sample only. Skills are identified from available posting metadata; missing keywords do not imply a skill is absent.`;
    decorate();
  }
  function renderRadar() {
    const query = $("#radar-search").value.toLowerCase().trim();
    const filter = $("#trend-filter").value;
    const items = (state.radar?.[state.radarTab] || []).filter(
      (item) =>
        (item.name || item.title || "").toLowerCase().includes(query) &&
        (filter === "all" || (item.label || "insufficient") === filter),
    );
    $("#radar-table-body").innerHTML = items.length
      ? items
          .map(
            (item) =>
              `<tr><td>${e(item.name || item.title)}</td><td>${integer(item.recent_count)}</td><td>${integer(item.previous_count)}</td><td>${trend(item)}</td><td><div class="sdg-badges">${badges(item.sdgs)}</div></td><td>${item.evidence?.length ? `<a class="evidence-link" href="${e(safeURL(item.evidence[0].url))}" target="_blank" rel="noopener noreferrer">${item.evidence[0].kind === "ai_release" ? "View AI release" : "View posting"} ↗</a><time class="evidence-date">${e(date(item.evidence[0].date))}</time>` : '<span class="muted small">No current evidence</span>'}</td></tr>`,
          )
          .join("")
      : '<tr><td colspan="6"><div class="empty-state"><h3>No signals match your search.</h3><p>Try another skill, role, or signal filter.</p></div></td></tr>';
    decorate();
  }
  function component(label, value) {
    return `<div class="component-row"><span>${e(label)}</span><div class="component-track"><span data-bar="${pct(value)}"></span></div><strong>${Math.round(pct(value))}%</strong></div>`;
  }
  function renderMatches() {
    const query = $("#match-search").value.toLowerCase().trim();
    const matches = state.matches.filter((match) =>
      `${match.title} ${match.summary} ${(match.missing_skills || []).map((s) => s.name).join(" ")} ${(match.matched_skills || []).map((s) => s.name).join(" ")} ${(match.sdgs || []).map((id) => `SDG ${id} ${sdg(id).title}`).join(" ")}`
        .toLowerCase()
        .includes(query),
    );
    $("#nav-match-count").textContent = state.matches.length;
    $("#match-result-count").textContent =
      `${matches.length} of ${state.matches.length} paths · ${state.appliedScenario === "fast" ? "Fast" : "Moderate"} adoption scenario`;
    $("#match-grid").innerHTML = matches.length
      ? matches
          .map(
            (match) =>
              `<article class="card match-card"><div class="match-card-top"><span class="role-number">PATH ${String(state.matches.indexOf(match) + 1).padStart(2, "0")}</span>${trend(match.trend)}</div><h2>${e(match.title)}</h2><div class="match-score">${Math.round(pct(match.score))}<span>%</span><small>match score</small></div><p class="match-description">${e(match.summary)}</p><div class="score-components">${component("Skills coverage · 65%", match.components?.skill_coverage)}${component("Interest relevance · 20%", match.components?.interest_alignment)}${component("Market signal · 15%", match.components?.market_signal)}</div><div class="skill-block"><p class="skill-block-label">Your strengths</p><div class="skill-chip-list">${skillChips(match.matched_skills) || '<span class="muted small">Build the core skills to get started.</span>'}</div></div><div class="skill-block"><p class="skill-block-label">Your learning opportunities</p><div class="skill-chip-list">${skillChips(match.missing_skills, true) || '<span class="skill-chip">✓ All catalogue skills covered</span>'}</div></div><details><summary>Why this match? See the evidence</summary><p>${e(match.explanation)}</p><ul class="evidence-list">${evidence(match.evidence) || "<li>No direct postings in this sample. Explore the occupational reference.</li>"}</ul></details><div class="sdg-badges">${badges(match.sdgs)}</div><div class="match-card-bottom"><div class="scenario-compare">Moderate: <strong>${Math.round(pct(match.scenario_scores?.moderate))}%</strong> · Fast: <strong>${Math.round(pct(match.scenario_scores?.fast))}%</strong><br>${integer(match.pathway?.total_hours)} learning hours · ${integer(match.pathway?.weeks)} weeks estimated</div><button class="button button-primary" type="button" data-start-role="${e(match.id)}">Explore this path <span aria-hidden="true">→</span></button></div></article>`,
          )
          .join("")
      : '<div class="card empty-state"><h3>No career paths match your search.</h3><p>Try another role or skill, or update your profile to find a new direction.</p></div>';
    decorate();
  }
  function selectedMatch() {
    return (
      state.matches.find((match) => match.id === state.selectedRole) ||
      state.matches[0]
    );
  }
  function renderPathway() {
    const match = selectedMatch();
    if (!match) {
      $("#pathway-role").innerHTML = "";
      $("#pathway-steps").innerHTML =
        '<div class="card empty-state"><h3>A fresh path awaits.</h3><p>Complete your skills profile to build a learning plan.</p></div>';
      $("#pathway-summary").replaceChildren();
      $("#pathway-impact").replaceChildren();
      $("#progress-text").textContent = "Build a profile to start learning";
      $("#progress-percent").textContent = "0%";
      $("#progress-bar").style.width = "0%";
      return;
    }
    state.selectedRole = match.id;
    $("#pathway-role").innerHTML = state.matches
      .map(
        (role) =>
          `<option value="${e(role.id)}"${role.id === match.id ? " selected" : ""}>${e(role.title)}</option>`,
      )
      .join("");
    const plan = match.pathway || { steps: [] };
    $("#pathway-summary").innerHTML =
      `<div><strong>${integer(plan.total_hours)}</strong><span>estimated learning hours</span></div><div><strong>${integer(plan.weeks)}</strong><span>weeks at ${integer(state.profile?.weekly_hours || 6)}h / week</span></div>`;
    const steps = plan.steps || [];
    $("#pathway-steps").innerHTML = steps.length
      ? steps
          .map((step, index) => {
            const done = Boolean(state.progress[step.skill_id]);
            return `<article class="card pathway-step ${done ? "completed" : ""}"><span class="step-number">${done ? "✓" : index + 1}</span><div class="step-meta"><span>${icon("clock")}${integer(step.hours)} hours estimated</span><span>Week ${integer(step.week_start)}${n(step.week_end) !== n(step.week_start) ? `–${integer(step.week_end)}` : ""}</span></div><h3>${e(step.name)}</h3>${(step.resources || []).map((resource) => `<a class="resource-link" href="${e(safeURL(resource.url))}" target="_blank" rel="noopener noreferrer">${e(resource.title)}<small>${e(resource.provider || "Learning resource")} · Check provider access and certificate terms</small><span aria-hidden="true">↗</span></a>`).join("") || '<p class="muted small">Explore an appropriate introductory learning resource with a career adviser.</p>'}<div class="step-bottom"><div class="sdg-badges">${badges(step.sdgs)}</div><label class="complete-label"><input type="checkbox" data-complete-skill="${e(step.skill_id)}"${done ? " checked" : ""}> Mark as completed</label></div></article>`;
          })
          .join("")
      : '<div class="card empty-state"><h3>You have the core skills in this catalogue.</h3><p>Put them into practice with a small project, review real role requirements, and seek feedback from a career adviser.</p></div>';
    $("#pathway-impact").innerHTML =
      `<div class="icon-tile">${icon("leaf")}</div><h2>A career with purpose.</h2><p>${e(match.sdg_impact || "Your skills can make a difference beyond your next role. Explore how this path connects to the UN Sustainable Development Goals.")}</p>${(
        match.sdgs || []
      )
        .map((id) => {
          const goal = sdg(id);
          return `<div class="impact-goal"><span class="goal-number" data-sdg-color="${e(id)}">${e(id)}</span><div><h3>${e(goal.title)}</h3><p>${e(goal.description)}</p><a href="${e(safeURL(goal.url))}" target="_blank" rel="noopener noreferrer">Explore SDG ${e(id)} ↗</a></div></div>`;
        })
        .join(
          "",
        )}<p>These links describe potential contribution through your work. They do not measure impact or guarantee an outcome.</p>`;
    updateProgress();
    decorate();
  }
  function updateProgress() {
    const steps = selectedMatch()?.pathway?.steps || [];
    const complete = steps.filter(
      (step) => state.progress[step.skill_id],
    ).length;
    const percent = steps.length
      ? Math.round((complete / steps.length) * 100)
      : 100;
    $("#progress-text").textContent = steps.length
      ? `${complete} of ${steps.length} skills completed`
      : "No core skill gaps in this catalogue";
    $("#progress-percent").textContent = `${percent}%`;
    $("#progress-bar").style.width = `${percent}%`;
  }
  async function runMatch(profileOverride = null) {
    const seq = ++state.matchSequence;
    const button = $("#match-submit");
    button.disabled = true;
    button.textContent = "Finding your next step…";
    $("#match-grid").setAttribute("aria-busy", "true");
    try {
      const data = await api("/api/match", {
        method: "POST",
        body: JSON.stringify(profileOverride || getProfile()),
      });
      if (seq !== state.matchSequence) return false;
      state.matches = data.matches || [];
      state.profile = data.profile || profileOverride || getProfile();
      state.matchSignalStatus = data.signal_status || null;
      state.appliedScenario = data.scenario || state.scenario;
      if (data.signal_status && state.radar)
        state.radar.signal_status = data.signal_status;
      if (!state.matches.some((m) => m.id === state.selectedRole))
        state.selectedRole = state.matches[0]?.id;
      renderOverview();
      renderMatches();
      renderPathway();
      renderSource();
      if (state.radar) alert(null);
      document.dispatchEvent(new CustomEvent("nextstep:matched", {bubbles: true, detail: {
        profile: state.profile, matches: state.matches, scenario: state.appliedScenario,
      }}));
      return true;
    } catch (error) {
      if (seq === state.matchSequence) alert(error.message);
      return false;
    } finally {
      if (seq === state.matchSequence) {
        button.disabled = false;
        button.innerHTML =
          'Find my next step <span aria-hidden="true">→</span>';
        $("#match-grid").setAttribute("aria-busy", "false");
      }
    }
  }
  async function fetchRadar(refresh = false) {
    const seq = ++state.radarSequence;
    const data = await api(
      refresh
        ? "/api/signals/refresh"
        : `/api/radar?scenario=${state.scenario}`,
      refresh
        ? { method: "POST", body: JSON.stringify({ scenario: state.scenario }) }
        : {},
    );
    if (seq !== state.radarSequence) return;
    state.radar = data;
    renderRadar();
    renderSource();
    renderOverview();
    return data;
  }
  async function refreshSignals() {
    const buttons = $$(".refresh-button");
    buttons.forEach((button) => {
      button.disabled = true;
      button.innerHTML = `${icon("refresh")} Refreshing…`;
    });
    try {
      const data = await fetchRadar(true);
      const matched = await runMatch(
        state.profile
          ? { ...state.profile, scenario: state.appliedScenario }
          : null,
      );
      if (!matched) return;
      if (data?.refresh_attempted === false) {
        toast(
          `Using the existing snapshot. A new source refresh is available after ${date(data.signal_status?.refresh_allowed_at, true)} MYT.`,
        );
      } else {
        toast(
          state.radar?.signal_status?.status === "live"
            ? "Signals refreshed. Your matches and pathway have been recalculated."
            : state.radar?.signal_status?.message ||
                "Showing the latest cached signals.",
        );
      }
    } catch (error) {
      alert(error.message);
    } finally {
      buttons.forEach((button) => {
        button.disabled = false;
        button.innerHTML = `${icon("refresh")} Refresh signals`;
      });
    }
  }
  async function renderDiscoveries() {
    const root = $("#observed-title-list");
    if (!root) return;
    try {
      const data = await api("/api/monitor/discoveries");
      root.innerHTML = (data.items || []).slice(0, 12).map(item => {
        const example = item.examples?.[0];
        return `<article class="method-card"><strong>${e(item.title)}</strong><p>${integer(item.recent_count)} recent · ${integer(item.previous_count)} earlier · ${e(String(item.trend || "insufficient_evidence").replaceAll("_", " "))}</p>${example ? `<a class="evidence-link" href="${e(safeURL(example.url))}" target="_blank" rel="noopener noreferrer">Original posting ↗</a>` : ""}</article>`;
      }).join("") || "<p>No dated source observations are available.</p>";
    } catch {
      root.textContent = "Source observations are unavailable. The dated catalogue radar remains available above.";
    }
  }
  async function checkMonitor() {
    if (state.monitorBusy || document.hidden || !state.ready) return;
    state.monitorBusy = true;
    const profileAtStart = state.profile;
    try {
      const data = await api("/api/monitor/status");
      const label = $("#monitor-status");
      if (label) label.textContent = data.enabled
        ? `Automatic source refresh every ${Math.round(data.interval_seconds / 60)} minutes. ${data.refreshing ? "Checking sources now." : data.next_refresh_at ? `Next check: ${date(data.next_refresh_at, true)} MYT.` : "Waiting for the next source check."}${data.last_error ? " Latest check could not refresh; using dated cached evidence." : ""}`
        : "Automatic refresh is paused. Use Refresh signals to check the public sources.";
      if (!state.evidenceRevision) {
        state.evidenceRevision = data.revision;
        await renderDiscoveries();
      } else if (data.revision && data.revision !== state.evidenceRevision && !state.scenarioBusy && profileAtStart === state.profile) {
        await fetchRadar();
        if (profileAtStart === state.profile && state.profile) {
          const matched = await runMatch({...state.profile, scenario: state.appliedScenario});
          if (matched) toast("New source evidence is available. Your career matches and learning path have been updated.");
        }
        state.evidenceRevision = data.revision;
        await renderDiscoveries();
      }
    } catch {
      const label = $("#monitor-status");
      if (label) label.textContent = "The automatic update status is unavailable. Dated evidence and manual refresh remain available.";
    } finally {
      state.monitorBusy = false;
      clearTimeout(state.monitorTimer);
      state.monitorTimer = setTimeout(checkMonitor, 20000);
    }
  }
  document.addEventListener("visibilitychange", () => {
    clearTimeout(state.monitorTimer);
    if (!document.hidden) checkMonitor();
  });
  function syncScenarioSwitch() {
    $$("[data-scenario]").forEach((button) => {
      const active = button.dataset.scenario === state.scenario;
      button.classList.toggle("selected", active);
      button.setAttribute("aria-pressed", String(active));
      button.disabled = state.scenarioBusy;
    });
  }
  async function setScenario(scenario) {
    if (scenario === state.scenario || state.scenarioBusy) return;
    state.scenarioBusy = true;
    state.scenario = scenario;
    syncScenarioSwitch();
    try {
      const matched = await runMatch(
        state.profile ? { ...state.profile, scenario } : null,
      );
      if (!matched) {
        state.scenario = state.appliedScenario;
      } else {
        try {
          await fetchRadar();
        } catch (error) {
          alert(
            `Matches updated, but the radar could not reload: ${error.message}`,
          );
        }
        toast(
          `${state.appliedScenario === "fast" ? "Fast" : "Moderate"} adoption assumptions applied.`,
        );
      }
    } finally {
      state.scenarioBusy = false;
      syncScenarioSwitch();
    }
  }
  function exportPlan() {
    const match = selectedMatch();
    if (!match) {
      toast("Build a skills profile first to create a plan.");
      return;
    }
    const profile = state.profile || getProfile();
    const status = state.matchSignalStatus || state.radar?.signal_status || {};
    const lines = [
      `# NextStep — ${match.title}`,
      ``,
      `Generated: ${new Date().toISOString()}`,
      `Scenario: ${state.appliedScenario} AI adoption (illustrative assumption, not a forecast)`,
      `Match score: ${Math.round(pct(match.score))}% (not a hiring probability)`,
      `Learning budget: ${profile.weekly_hours} hours/week`,
      `Estimated duration: ${match.pathway?.total_hours || 0} hours / ${match.pathway?.weeks || 0} weeks`,
      ``,
      `## Why this path`,
      match.explanation || "",
      ``,
      `## Skills profile`,
      ...(profile.skills || []).map(
        (id) =>
          `- ${state.catalog.skills.find((skill) => skill.id === id)?.name || id}`,
      ),
      ``,
      `## Learning plan`,
    ];
    (match.pathway?.steps || []).forEach((step, index) => {
      lines.push(
        ``,
        `${index + 1}. ${step.name} — ${step.hours} estimated hours; week ${step.week_start}–${step.week_end}`,
        `   Status: ${state.progress[step.skill_id] ? "Completed" : "To learn"}`,
        `   SDGs: ${(step.sdgs || []).join(", ")}`,
        ...(step.resources || []).map(
          (resource) =>
            `   - ${resource.title} (${resource.provider || "Resource"}): ${safeURL(resource.url)}`,
        ),
      );
    });
    lines.push(
      ``,
      `## SDG connections`,
      match.sdg_impact || "",
      ...(match.sdgs || []).map(
        (id) => `- SDG ${id}: ${sdg(id).title} — ${sdg(id).description}`,
      ),
      ``,
      `## Evidence`,
      ...(match.evidence || []).map(
        (item) =>
          `- ${item.title} (${item.date || "Date unavailable"}): ${safeURL(item.url)}`,
      ),
      ``,
      `Source: ${status.source_name || "Unavailable"} ${safeURL(status.source_url)}`,
      `Snapshot: ${status.fetched_at || "Unavailable"}; ${status.jobs_count || 0} public postings.`,
      `Source state: ${status.status || "offline"}`,
      ``,
      `## Limits`,
      `International graduate-job sample; not Malaysian labor-market statistics. Career support only, not a hiring decision. Sparse evidence and keyword matching may miss skills. Course hours are estimates; check provider terms. SDG links describe potential contribution, not measured impact.`,
    );
    const blob = new Blob([lines.join("\n")], {
      type: "text/markdown;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `nextstep-${String(match.id).replace(/[^a-z0-9_-]/gi, "")}-plan.md`;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    toast("Your learning plan has been downloaded.");
  }
  document.addEventListener("click", (event) => {
    const nav = event.target.closest("[data-view]");
    if (nav) {
      const view = nav.dataset.view;
      if (viewNames[view]) {
        showView(view);
        window.scrollTo({ top: 0, behavior: "auto" });
      }
    }
    const role = event.target.closest("[data-start-role]");
    if (role) {
      state.selectedRole = role.dataset.startRole;
      renderPathway();
      location.hash = "pathway";
      showView("pathway");
      window.scrollTo({ top: 0, behavior: "auto" });
    }
    const scenario = event.target.closest("[data-scenario]");
    if (scenario) setScenario(scenario.dataset.scenario);
    const radarTab = event.target.closest("[data-radar-tab]");
    if (radarTab) {
      state.radarTab = radarTab.dataset.radarTab;
      $$("[data-radar-tab]").forEach((button) => {
        const selected = button === radarTab;
        button.classList.toggle("selected", selected);
        button.setAttribute("aria-pressed", String(selected));
      });
      renderRadar();
    }
    if (event.target.closest("[data-dismiss-alert]")) alert(null);
  });
  $("#profile-form").addEventListener("submit", (event) => {
    event.preventDefault();
    if (!$("#profile-form").reportValidity()) return;
    runMatch();
  });
  $("#demo-profile").addEventListener("change", () => {
    fillProfile(
      state.catalog.profiles.find(
        (profile) => profile.id === $("#demo-profile").value,
      ),
    );
    runMatch();
  });
  $("#skill-picker").addEventListener("change", updateSkillCount);
  $("#radar-search").addEventListener("input", renderRadar);
  $("#trend-filter").addEventListener("change", renderRadar);
  $("#match-search").addEventListener("input", renderMatches);
  $("#pathway-role").addEventListener("change", () => {
    state.selectedRole = $("#pathway-role").value;
    renderPathway();
  });
  $("#pathway-steps").addEventListener("change", (event) => {
    const input = event.target.closest("[data-complete-skill]");
    if (!input) return;
    state.progress[input.dataset.completeSkill] = input.checked;
    saveProgress();
    const card = input.closest(".pathway-step");
    card.classList.toggle("completed", input.checked);
    $(".step-number", card).textContent = input.checked
      ? "✓"
      : String(
          (selectedMatch()?.pathway?.steps || []).findIndex(
            (step) => step.skill_id === input.dataset.completeSkill,
          ) + 1,
        );
    updateProgress();
  });
  $$(".refresh-button").forEach((button) =>
    button.addEventListener("click", refreshSignals),
  );
  $("#overview-export").addEventListener("click", exportPlan);
  $("#pathway-export").addEventListener("click", exportPlan);
  $("#clear-progress").addEventListener("click", () => {
    state.progress = {};
    saveProgress();
    renderPathway();
    toast("Learning progress cleared from this browser.");
  });
  window.addEventListener("hashchange", () => showView(location.hash.slice(1)));
  async function init() {
    decorate();
    showView(location.hash.slice(1));
    try {
      state.catalog = await api("/api/catalog");
      renderCatalogue();
      try {
        await fetchRadar();
      } catch (error) {
        alert(`Trend data could not load: ${error.message}`);
      }
      await runMatch();
      $("#loading-state").hidden = true;
      $("#app-content").hidden = false;
      state.ready = true;
      document.dispatchEvent(new CustomEvent("nextstep:ready", {bubbles: true}));
      checkMonitor();
    } catch (error) {
      $("#loading-state").innerHTML =
        `<div class="empty-state"><h3>We couldn't load your workspace.</h3><p>${e(error.message)}</p><p>Check the Python server is running, then reload this page.</p><button class="button button-secondary" type="button" id="retry-load">Try again</button></div>`;
      $("#retry-load").addEventListener("click", () => location.reload());
    }
  }
  // A small bridge lets the new account/workflow pages reuse the original
  // matching and learning journey without duplicating its state or algorithm.
  window.NextStep = {
    api,
    catalog: () => state.catalog,
    profile: () => state.profile,
    matches: () => state.matches,
    scenario: () => state.appliedScenario,
    selectedRole: () => state.selectedRole,
    role: () => document.body.dataset.role || "guest",
    ready: () => state.ready,
    toast,
    navigate(view) {
      if (!viewNames[view]) return;
      history.replaceState(null, "", `#${view}`);
      showView(view);
      window.scrollTo({top: 0, behavior: "auto"});
    },
    selectRole(roleId) {
      if (!state.matches.some(match => match.id === roleId)) return;
      state.selectedRole = roleId;
      renderPathway();
      this.navigate("pathway");
    },
    async applyProfile(profile) {
      const scenario = ["moderate", "fast"].includes(profile.scenario) ? profile.scenario : state.appliedScenario;
      state.scenario = scenario;
      syncScenarioSwitch();
      fillProfile(profile);
      return runMatch({...profile, scenario});
    },
    clearProfile() {
      state.matchSequence += 1;
      state.scenarioBusy = false;
      $("#match-submit").disabled = false;
      $("#match-submit").innerHTML = 'Find my next step <span aria-hidden="true">→</span>';
      $("#match-grid").setAttribute("aria-busy", "false");
      alert(null);
      state.matches = [];
      state.profile = null;
      state.selectedRole = null;
      state.matchSignalStatus = null;
      state.scenario = "moderate";
      state.appliedScenario = "moderate";
      fillProfile({skills: [], interests: "", weekly_hours: 6});
      syncScenarioSwitch();
      renderOverview();
      renderMatches();
      renderPathway();
    },
    setProgressScope(scope) {
      state.progressKey = scope == null ? "nextstep-progress" : `nextstep-progress-${String(scope).replace(/[^a-z0-9_-]/gi, "")}`;
      state.progress = readProgress(state.progressKey);
      renderPathway();
    },
  };
  init();
})();
