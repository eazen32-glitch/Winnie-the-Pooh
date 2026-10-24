"use strict";
(() => {
  const root = document.querySelector("#career-assistant");
  if (!root) return;
  const toggle = root.querySelector("#assistant-toggle");
  const panel = root.querySelector("#assistant-panel");
  const close = root.querySelector("#assistant-close");
  const form = root.querySelector("#assistant-form");
  const input = root.querySelector("#assistant-message");
  const send = root.querySelector("#assistant-send");
  const conversation = root.querySelector("#assistant-conversation");
  const quick = root.querySelector("#assistant-quick-actions");
  let role = "guest";
  let busy = false;
  let generation = 0;
  let taskSequence = 0;
  let capabilitiesLoaded = false;
  const taskLab = root.querySelector("#assistant-task-lab");
  const taskForm = root.querySelector("#assistant-task-form");
  const taskRole = root.querySelector("#assistant-task-role");
  const taskScenario = root.querySelector("#assistant-task-scenario");
  const taskSummary = root.querySelector("#assistant-task-summary");
  const taskFields = root.querySelector("#assistant-task-fields");
  const researchPanel = root.querySelector("#assistant-research-evidence");
  const modelConsent = root.querySelector("#assistant-model-consent");
  const initialMessage = conversation.firstElementChild.cloneNode(true);

  function openPanel(open) {
    panel.hidden = !open;
    toggle.setAttribute("aria-expanded", String(open));
    if (open) {
      input.focus();
      loadCapabilities();
    }
    else toggle.focus();
  }

  async function loadCapabilities() {
    if (capabilitiesLoaded || !window.NextStep) return;
    try {
      const data = await window.NextStep.api("/api/assistant/capabilities");
      root.querySelector("#assistant-model-option").hidden = !data.model_available;
      root.querySelector("#assistant-mode").textContent = data.model_available
        ? `Local guide · optional ${data.model} question interpretation`
        : "Local source-grounded guide · external model not configured";
      capabilitiesLoaded = true;
    } catch {
      // Offline guidance remains available when optional capability discovery fails.
    }
  }

  function taskChoices() {
    const roles = window.NextStep?.catalog()?.roles || [];
    if (!taskRole.options.length) {
      roles.forEach((item) => {
        const option = document.createElement("option");
        option.value = item.id;
        option.textContent = item.title;
        taskRole.append(option);
      });
      const selected = window.NextStep?.selectedRole();
      if (selected && roles.some((item) => item.id === selected)) taskRole.value = selected;
      taskScenario.value = window.NextStep?.scenario() || "moderate";
    }
  }

  function renderTaskAssessment(data) {
    const assessment = data.task_assessment;
    if (!assessment) return;
    researchPanel.replaceChildren(researchCard(data.research_evidence));
    taskSummary.textContent = `${assessment.percentage}% authored task-assistance index · sensitivity example ${assessment.sensitivity_band.lower}–${assessment.sensitivity_band.upper}%. Not a published study result or replacement probability.`;
    taskFields.replaceChildren(...assessment.tasks.map((task) => {
      const label = document.createElement("label");
      const text = document.createElement("span");
      text.textContent = task.label;
      const control = document.createElement("input");
      control.type = "number";
      control.min = "0";
      control.max = "100";
      control.step = "0.1";
      control.required = true;
      control.value = String(task.assistance_percent);
      control.dataset.taskId = task.id;
      control.setAttribute("aria-label", `Assumed assistance percentage: ${task.label}`);
      label.append(text, control);
      return label;
    }));
    root.querySelector("#assistant-task-method").textContent = `${assessment.formula} ${assessment.scope} ${assessment.uncertainty}`;
    const source = root.querySelector("#assistant-task-source");
    const href = citationURL(data.source_url);
    source.hidden = !href;
    if (href) source.href = href;
  }

  async function calculateTasks(customised = false) {
    taskChoices();
    if (!taskRole.value || !window.NextStep) return;
    const requestSequence = ++taskSequence;
    const requestGeneration = generation;
    const button = root.querySelector("#assistant-task-calculate");
    button.disabled = true;
    taskSummary.textContent = "Checking the task assumptions…";
    researchPanel.textContent = "Loading the published evidence for this role…";
    try {
      const assumptions = {};
      taskFields.querySelectorAll("input[data-task-id]").forEach((control) => {
        assumptions[control.dataset.taskId] = Number(control.value);
      });
      const data = customised
        ? await window.NextStep.api("/api/exposure/what-if", {
          method: "POST",
          headers: {"X-CSRF-Token": window.NextStepSession?.csrfToken || ""},
          body: JSON.stringify({role_id: taskRole.value, scenario: taskScenario.value, task_assumptions: assumptions}),
        })
        : await window.NextStep.api(`/api/exposure?role_id=${encodeURIComponent(taskRole.value)}&scenario=${encodeURIComponent(taskScenario.value)}`);
      if (requestSequence !== taskSequence || requestGeneration !== generation) return;
      renderTaskAssessment(data);
    } catch (error) {
      if (requestSequence !== taskSequence || requestGeneration !== generation) return;
      taskSummary.textContent = error.message || "The task assumptions could not load.";
      researchPanel.replaceChildren(researchCard(null));
    } finally {
      if (requestSequence === taskSequence && requestGeneration === generation) button.disabled = false;
    }
  }

  function renderQuickActions() {
    const prompts =
      role === "hr"
        ? ["Review applicants", "Schedule interviews", "Company verification", "Explain AI exposure"]
        : [
            "Find my skill gaps",
            "Suggest roles",
            "Plan my learning",
            "Explain AI exposure",
          ];
    quick.replaceChildren(
      ...prompts.map((message) => {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = message;
        button.disabled = busy;
        button.addEventListener("click", () => ask(message));
        return button;
      }),
    );
  }

  function bubble(message, kind = "response") {
    const article = document.createElement("article");
    article.className = `assistant-bubble assistant-${kind}`;
    const text = document.createElement("p");
    text.textContent = message;
    article.append(text);
    conversation.append(article);
    // Keep the current account's local conversation bounded.
    while (conversation.children.length > 24)
      conversation.firstElementChild.remove();
    conversation.scrollTop = conversation.scrollHeight;
    return article;
  }

  function citationURL(value) {
    try {
      const url = new URL(value);
      return url.protocol === "https:" && !url.username && !url.password
        ? url.href
        : null;
    } catch {
      return null;
    }
  }

  function researchCard(evidence) {
    const card = document.createElement("section");
    card.className = "assistant-research-card";
    const heading = document.createElement("h3");
    heading.textContent = "Published occupational research";
    card.append(heading);
    if (!evidence || typeof evidence !== "object") {
      const unavailable = document.createElement("p");
      unavailable.textContent = "Published measure unavailable. No research score is inferred from the what-if calculator.";
      card.append(unavailable);
      return card;
    }
    const metric = evidence.metric || {};
    const mapping = evidence.mapping || {};
    const scope = evidence.scope || {};
    const source = evidence.source || {};
    const score = document.createElement("p");
    score.className = "assistant-research-score";
    score.textContent = evidence.status === "available" && Number.isFinite(metric.percent)
      ? `${metric.percent} / 100 · ${metric.name || "published exposure index"}`
      : "Published exposure measure unavailable";
    card.append(score);
    const definition = document.createElement("p");
    definition.textContent = evidence.status === "available"
      ? metric.interpretation || "An occupational technical-exposure index, not a job-loss probability."
      : evidence.unavailable_reason || evidence.reason || "No defensible published occupation mapping is available. A score is not inferred from another occupation.";
    card.append(definition);
    const facts = document.createElement("dl");
    function fact(label, value) {
      if (!value) return;
      const term = document.createElement("dt");
      const description = document.createElement("dd");
      term.textContent = label;
      description.textContent = String(value);
      facts.append(term, description);
    }
    fact("Study", [source.publisher, source.year].filter(Boolean).join(" · "));
    fact("Country / scope", [scope.geography, scope.population].filter(Boolean).join(" · "));
    fact("Time horizon", scope.time_horizon);
    if (mapping.relation) {
      const relation = mapping.relation === "exact" ? "Exact occupation match" : mapping.relation === "broader_proxy" ? "Broader occupation proxy" : "Occupation mapping unavailable";
      fact("Mapping", `${relation}: ${[mapping.source_classification, mapping.source_code, mapping.source_title].filter(Boolean).join(" · ")}`);
    }
    fact("Mapping basis", mapping.rationale);
    const uncertainty = typeof evidence.uncertainty === "object" ? evidence.uncertainty?.text : evidence.uncertainty;
    fact("Uncertainty", uncertainty);
    if (facts.children.length) card.append(facts);
    if (Array.isArray(evidence.limitations) && evidence.limitations.length) {
      const details = document.createElement("details");
      const summary = document.createElement("summary");
      summary.textContent = "Study limits";
      const list = document.createElement("ul");
      evidence.limitations.forEach((value) => {
        const item = document.createElement("li");
        item.textContent = String(value);
        list.append(item);
      });
      details.append(summary, list);
      card.append(details);
    }
    const links = document.createElement("div");
    links.className = "assistant-research-links";
    [[source.url, source.title || "Read the study"], [source.dataset_url, "Published data and method"]].forEach(([value, label]) => {
      const href = citationURL(value);
      if (!href) return;
      const link = document.createElement("a");
      link.href = href;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = `${label} ↗`;
      links.append(link);
    });
    if (typeof evidence.role_id === "string" && /^[a-z-]{1,80}$/.test(evidence.role_id)) {
      const report = document.createElement("a");
      report.href = `/api/exposure/report/${encodeURIComponent(evidence.role_id)}`;
      report.textContent = "Download cited role evidence ↗";
      links.append(report);
    }
    if (links.children.length) card.append(links);
    if (Array.isArray(evidence.historical_estimates) && evidence.historical_estimates.length) {
      const history = document.createElement("details");
      history.className = "assistant-historical-evidence";
      const summary = document.createElement("summary");
      summary.textContent = "Historical 2013 computerisation estimates";
      const warning = document.createElement("p");
      warning.textContent = "These older source-model probabilities concern broad computerisation of US occupations. They are not current GenAI replacement percentages, personal forecasts or directly comparable with the 2025 exposure index. Distinct suboccupations are shown separately.";
      history.append(summary, warning);
      evidence.historical_estimates.forEach((estimate) => {
        const historicalMetric = estimate.metric || {};
        const historicalMapping = estimate.mapping || {};
        const historicalSource = estimate.source || {};
        const historicalScope = estimate.scope || {};
        const record = document.createElement("section");
        const title = document.createElement("h4");
        title.textContent = `${historicalMapping.source_title || "Source occupation"} · ${historicalMapping.source_code || ""}`;
        const value = document.createElement("p");
        value.textContent = `${historicalMetric.display_value || "Unavailable"} · ${historicalMetric.name || "2013 source-model estimate"}`;
        const interpretation = document.createElement("p");
        interpretation.textContent = [historicalMetric.interpretation, historicalMapping.rationale, historicalMapping.caveat].filter(Boolean).join(" ");
        const scopeNote = document.createElement("p");
        scopeNote.textContent = `${historicalSource.year || "2013"} · ${[historicalScope.geography, historicalScope.population, historicalScope.reference_period].filter(Boolean).join(" · ")}. ${historicalScope.time_horizon || ""} ${estimate.uncertainty?.text || ""}`;
        record.append(title, value, interpretation, scopeNote);
        [[historicalSource.url, historicalSource.title || "Original study"], [historicalSource.mirror_url, "Read the archived paper mirror"]].forEach(([url, label]) => {
          const href = citationURL(url);
          if (!href) return;
          const link = document.createElement("a");
          link.href = href;
          link.target = "_blank";
          link.rel = "noopener noreferrer";
          link.textContent = `${label} ↗`;
          record.append(link);
        });
        history.append(record);
      });
      card.append(history);
    }
    const note = document.createElement("p");
    note.className = "assistant-research-note";
    note.textContent = "This study does not give a validated personal job-loss probability. Its score is independent of the editable what-if assumptions.";
    card.append(note);
    return card;
  }

  function renderReply(data, article) {
    article.querySelector("p").textContent =
      data.answer || "Choose a suggested question to explore your next step.";
    if (data.research_evidence) article.append(researchCard(data.research_evidence));
    if (Array.isArray(data.sources) && data.sources.length) {
      const list = document.createElement("ul");
      list.className = "assistant-citations";
      data.sources.forEach((source) => {
        const href = citationURL(source.url);
        if (!href) return;
        const item = document.createElement("li");
        const link = document.createElement("a");
        link.href = href;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = `${source.title || "Source"} ↗`;
        item.append(link);
        if (source.date) {
          const timestamp = document.createElement("time");
          timestamp.textContent = String(source.date);
          item.append(timestamp);
        }
        list.append(item);
      });
      if (list.children.length) article.append(list);
    }
    if (Array.isArray(data.actions)) {
      const actions = document.createElement("div");
      actions.className = "assistant-response-actions";
      data.actions.forEach((action) => {
        if (
          ![
            "overview",
            "jobs",
            "matches",
            "pathway",
            "sources",
            "profile",
            "calendar",
            "applications",
            "applicants",
            "radar",
            "messages",
          ].includes(action.view)
        )
          return;
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = action.label || "Explore";
        button.addEventListener("click", () => {
          const bridge = window.NextStep;
          if (!bridge) return;
          if (action.role_id && typeof bridge.selectRole === "function")
            bridge.selectRole(action.role_id);
          bridge.navigate(action.view);
          if (window.innerWidth < 700) openPanel(false);
        });
        actions.append(button);
      });
      if (actions.children.length) article.append(actions);
    }
    if (data.disclaimer) {
      const note = document.createElement("p");
      note.className = "assistant-source-note";
      note.textContent = data.disclaimer;
      article.append(note);
    }
    if (data.model_info?.notice || data.model_info?.used) {
      const note = document.createElement("p");
      note.className = "assistant-source-note";
      note.textContent = data.model_info.notice || `${data.model_info.model} interpreted the question; local cited facts supplied this answer.`;
      article.append(note);
    }
    conversation.scrollTop = conversation.scrollHeight;
  }

  async function ask(message) {
    if (busy || !message.trim()) return;
    if (!window.NextStep) {
      bubble("The workspace is still loading. Try again in a moment.", "error");
      return;
    }
    const requestGeneration = generation;
    busy = true;
    send.disabled = true;
    input.disabled = true;
    const useModel = !root.querySelector("#assistant-model-option").hidden && modelConsent.checked;
    modelConsent.checked = false;
    modelConsent.disabled = true;
    renderQuickActions();
    bubble(message, "question");
    const pending = bubble("Checking your profile and source evidence…");
    try {
      const bridge = window.NextStep;
      const profile =
        typeof bridge.profile === "function" ? bridge.profile() : null;
      const scenario =
        typeof bridge.scenario === "function"
          ? bridge.scenario()
          : profile?.scenario || "moderate";
      const selectedRole =
        typeof bridge.selectedRole === "function"
          ? bridge.selectedRole()
          : null;
      const data = await bridge.api("/api/assistant", {
        method: "POST",
        headers: {"X-CSRF-Token": window.NextStepSession?.csrfToken || ""},
        body: JSON.stringify({
          message,
          profile: profile || { skills: [], interests: "", weekly_hours: 6 },
          scenario,
          role_id: selectedRole || undefined,
          use_model: useModel,
          external_consent: useModel,
        }),
      });
      if (requestGeneration !== generation) return;
      renderReply(data, pending);
    } catch (error) {
      if (requestGeneration !== generation) return;
      pending.classList.add("assistant-error");
      pending.querySelector("p").textContent =
        error.message || "The guide could not respond. Try again.";
    } finally {
      if (requestGeneration === generation) {
        busy = false;
        send.disabled = false;
        input.disabled = false;
        modelConsent.disabled = false;
        renderQuickActions();
        input.focus();
      }
    }
  }

  toggle.addEventListener("click", () => openPanel(panel.hidden));
  taskLab.addEventListener("toggle", () => {
    panel.classList.toggle("assistant-task-open", taskLab.open);
    if (taskLab.open) calculateTasks();
  });
  taskRole.addEventListener("change", () => calculateTasks());
  taskScenario.addEventListener("change", () => calculateTasks());
  root.querySelector("#assistant-task-reset").addEventListener("click", () => calculateTasks());
  taskForm.addEventListener("submit", (event) => {
    event.preventDefault();
    if (taskForm.reportValidity()) calculateTasks(true);
  });
  close.addEventListener("click", () => openPanel(false));
  panel.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      openPanel(false);
    }
  });
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    const message = input.value.trim();
    if (!message) return;
    input.value = "";
    ask(message);
  });
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      form.requestSubmit();
    }
  });
  document.addEventListener("nextstep:session", (event) => {
    role = event.detail?.role || event.detail?.user?.role || "guest";
    // Never retain the previous account's conversation across sign-in/out.
    generation += 1;
    busy = false;
    send.disabled = false;
    input.disabled = false;
    input.value = "";
    modelConsent.checked = false;
    modelConsent.disabled = false;
    taskSequence += 1;
    taskFields.replaceChildren();
    researchPanel.replaceChildren();
    taskRole.replaceChildren();
    taskLab.open = false;
    taskSummary.textContent = "Choose a role to inspect its assumptions.";
    root.querySelector("#assistant-task-method").textContent = "";
    root.querySelector("#assistant-task-source").hidden = true;
    root.querySelector("#assistant-task-calculate").disabled = false;
    conversation.replaceChildren(initialMessage.cloneNode(true));
    renderQuickActions();
  });
  renderQuickActions();
})();
