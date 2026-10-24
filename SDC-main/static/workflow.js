/* Account, application and interview flows layered over the original NextStep app. */
"use strict";
(() => {
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [
    ...root.querySelectorAll(selector),
  ];
  const escape = (value) =>
    String(value ?? "").replace(
      /[&<>"']/g,
      (char) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[char],
    );
  const num = (value) => (Number.isFinite(Number(value)) ? Number(value) : 0);
  const percentage = (value) => Math.max(0, Math.min(100, num(value)));
  const url = (value) => {
    try {
      const parsed = new URL(value);
      return parsed.protocol === "https:" &&
        !parsed.username &&
        !parsed.password
        ? parsed.href
        : "#";
    } catch {
      return "#";
    }
  };
  const label = (value) =>
    String(value ?? "")
      .replaceAll("_", " ")
      .replaceAll("-", " ");
  const pendingStatuses = new Set([
    "submitted",
    "viewed",
    "under_review",
    "shortlisted",
    "interview_scheduled",
  ]);
  const terminalStatuses = new Set(["accepted", "rejected", "withdrawn"]);
  const state = {
    session: { user: null, role: "guest", csrf_token: "" },
    profile: null,
    applications: [],
    jobs: [],
    events: [],
    ownJobs: [],
    authMode: "login",
    authRole: "jobseeker",
    authBusy: false,
    booted: false,
    booting: false,
    generation: 0,
    jobsSequence: 0,
    applicationsSequence: 0,
    calendarSequence: 0,
    month: malaysiaToday().slice(0, 7),
    selectedDay: null,
    searchTimer: null,
    updatesTimer: null,
    updatesBusy: false,
    revision: null,
    updates: { notifications: [], unread_count: 0 },
    pendingRefresh: false,
    decisionDrafts: new Map(),
    verificationCapabilities: null,
  };

  function bridge() {
    return window.NextStep;
  }
  function role() {
    return state.session.role || "guest";
  }
  function malaysiaParts(value, includeTime = false) {
    const date = value ? new Date(value) : new Date();
    if (!Number.isFinite(date.getTime())) return null;
    return Object.fromEntries(
      new Intl.DateTimeFormat("en-CA", {
        timeZone: "Asia/Kuala_Lumpur",
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        ...(includeTime
          ? { hour: "2-digit", minute: "2-digit", hourCycle: "h23" }
          : {}),
      })
        .formatToParts(date)
        .filter((part) => part.type !== "literal")
        .map((part) => [part.type, part.value]),
    );
  }
  function malaysiaToday() {
    const parts = malaysiaParts();
    return `${parts.year}-${parts.month}-${parts.day}`;
  }
  function malaysiaDate(value) {
    const parts = malaysiaParts(value);
    return parts ? `${parts.year}-${parts.month}-${parts.day}` : "";
  }
  function date(value, includeTime = false) {
    const parsed = new Date(value);
    if (!value || !Number.isFinite(parsed.getTime())) return "Date unavailable";
    return parsed.toLocaleString("en-MY", {
      timeZone: "Asia/Kuala_Lumpur",
      day: "numeric",
      month: "short",
      year: "numeric",
      ...(includeTime
        ? { hour: "2-digit", minute: "2-digit", hourCycle: "h23" }
        : {}),
    });
  }
  function localInputValue(value) {
    const parts = malaysiaParts(value, true);
    return parts
      ? `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}`
      : "";
  }
  function status(value) {
    return `<span class="workflow-status ${escape(String(value || "submitted").replace(/[^a-z_]/g, ""))}">${escape(label(value || "submitted"))}</span>`;
  }
  function skills(items, missing = false) {
    return (items || [])
      .map(
        (item) =>
          `<span class="skill-chip ${missing ? "missing" : ""}">${missing ? "+" : "✓"} ${escape(item.name || item.id || item)}</span>`,
      )
      .join("");
  }
  function message(id, text = "", kind = "success") {
    const box = $(`#${id}`);
    if (!box) return;
    box.hidden = !text;
    box.className = `workflow-message ${kind}`;
    box.textContent = text;
  }
  function empty(title, text, action = "") {
    return `<div class="card workflow-empty"><div class="workflow-empty-icon">↗</div><h2>${escape(title)}</h2><p>${escape(text)}</p>${action ? `<div class="workflow-actions">${action}</div>` : ""}</div>`;
  }
  function loading(text) {
    return empty("One moment…", text);
  }
  function signInAction() {
    return '<button type="button" class="button button-primary" data-open-access>Sign in or try a demo</button>';
  }
  function notify(text) {
    bridge()?.toast(text);
  }
  function navigate(view) {
    if (bridge()) bridge().navigate(view);
    else location.hash = view;
  }
  function decorateMeters() {
    $$("[data-workflow-meter]").forEach(
      (item) =>
        (item.style.width = `${percentage(item.dataset.workflowMeter)}%`),
    );
  }
  function currentView() {
    return location.hash.slice(1) || "overview";
  }
  function guestEntered() {
    try {
      return sessionStorage.getItem("nextstep-guest-entered") === "yes";
    } catch {
      return false;
    }
  }
  function rememberGuest() {
    try {
      sessionStorage.setItem("nextstep-guest-entered", "yes");
    } catch {
      /* Guest entry still works without storage. */
    }
  }

  async function request(path, options = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 35000);
    try {
      const headers = {
        "Content-Type": "application/json",
        ...(options.headers || {}),
      };
      if (options.method && options.method !== "GET")
        headers["X-CSRF-Token"] = state.session.csrf_token || "";
      const response = await fetch(path, {
        ...options,
        headers,
        signal: controller.signal,
        credentials: "same-origin",
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok)
        throw new Error(
          data.error || `The request could not complete (${response.status}).`,
        );
      return data;
    } catch (error) {
      if (error.name === "AbortError")
        throw new Error(
          "The request took too long. Check the Python server and try again.",
        );
      throw error;
    } finally {
      clearTimeout(timer);
    }
  }
  async function formAction(form, action) {
    const generation = state.generation;
    const button = $('button[type="submit"]', form);
    const original = button?.textContent;
    if (button) button.dataset.idleLabel = original;
    if (button) {
      button.disabled = true;
      button.textContent = "Saving…";
    }
    form.setAttribute("aria-busy", "true");
    try {
      await action();
    } finally {
      if (generation === state.generation) {
        if (button) {
          button.disabled = false;
          button.textContent = original;
        }
        form.setAttribute("aria-busy", "false");
      }
    }
  }
  function emitSession() {
    window.NextStepSession = {
      ...state.session,
      csrfToken: state.session.csrf_token,
    };
    document.dispatchEvent(
      new CustomEvent("nextstep:session", {
        detail: { ...state.session },
        bubbles: true,
      }),
    );
  }
  function renderAudience() {
    document.body.dataset.role = role();
    $("#global-search").placeholder = role() === "hr"
      ? "Search applicants, roles or skills…"
      : "Search jobs or skills…";
    $$("[data-audience]").forEach(
      (item) =>
        (item.hidden = !item.dataset.audience.split(/\s+/).includes(role())),
    );
    $$(".hr-only").forEach((item) => (item.hidden = role() !== "hr"));
    const account = state.session.user;
    const badge = $("#workspace-role");
    if (badge)
      badge.textContent = account
        ? `${account.display_name} · ${role() === "hr" ? "HR" : "Job seeker"}`
        : "Guest workspace";
    $("#workspace-signin")?.toggleAttribute("hidden", Boolean(account));
    if ($("#workspace-signin")) $("#workspace-signin").disabled = state.authBusy;
    $("#workspace-signout")?.toggleAttribute("hidden", !account);
    const cart = $("#workspace-cart");
    if (cart) {
      const view = role() === "hr" ? "applicants" : "applications";
      cart.href = `#${view}`;
      cart.dataset.view = view;
      cart.setAttribute(
        "aria-label",
        role() === "hr" ? "Applicant inbox" : "My applications",
      );
    }
    if ($("#home-title"))
      $("#home-title").textContent =
        role() === "hr"
          ? "Build a future-ready team."
          : "Your future, within reach.";
    if ($("#home-description"))
      $("#home-description").textContent =
        role() === "hr"
          ? "Connect opportunities, applicants and the skills your team needs next."
          : "See where your skills can take you in a changing world of work.";
    if ($("#hero-title"))
      $("#hero-title").textContent =
        role() === "hr"
          ? "Good opportunities start with people."
          : "You already have a place to start.";
    if ($("#hero-description"))
      $("#hero-description").textContent =
        role() === "hr"
          ? "Review profiles, plan interviews and understand the skills behind your next hire."
          : "Connect what you know with what's next. A career path built around your potential.";
    $("#workspace-profile")?.setAttribute(
      "aria-label",
      account
        ? role() === "hr"
          ? "Edit company profile"
          : "Edit resume"
        : "Guest profile and sign in",
    );
    $("#workspace-notifications")?.toggleAttribute("hidden", !account);
    renderCartCount();
  }
  function renderCartCount() {
    const count =
      role() === "guest"
        ? 0
        : state.applications.filter((application) =>
            pendingStatuses.has(application.status),
          ).length;
    const badge = $("#workspace-cart-count");
    if (badge) {
      badge.textContent = String(count);
      badge.hidden = count === 0;
    }
  }
  function openGate() {
    if (state.authBusy) return;
    $("#access-gate").hidden = false;
    document.body.classList.add("access-gated");
    $$(".sidebar, .app-shell").forEach((item) => (item.inert = true));
    $("#access-close").hidden = !guestEntered() && !state.session.user;
    $("#access-choice").hidden = false;
    $("#access-auth").hidden = true;
    $("#access-title").textContent = "Your next chapter starts here.";
    $("#access-description").textContent =
      "Choose how you would like to explore NextStep.";
    message("access-error");
    $("#access-title").focus();
  }
  function closeGate(force = false) {
    if (state.authBusy && !force) return;
    $("#access-gate").hidden = true;
    document.body.classList.remove("access-gated");
    $$(".sidebar, .app-shell").forEach((item) => (item.inert = false));
    $("#main")?.focus({ preventScroll: true });
  }
  function showAuth(mode = "login", selectedRole = state.authRole) {
    state.authMode = mode;
    state.authRole = selectedRole;
    $("#access-choice").hidden = true;
    $("#access-auth").hidden = false;
    $("#access-register-fields").hidden = mode !== "register";
    $("#access-name").required = mode === "register";
    $("#access-role").value = selectedRole;
    $("#access-title").textContent =
      mode === "register"
        ? "Make this workspace yours."
        : "Welcome to your next step.";
    $("#access-description").textContent =
      mode === "register"
        ? "Create an account, then complete your synthetic profile."
        : "Sign in to continue with your saved resume or company profile.";
    $("#access-submit").textContent =
      mode === "register" ? "Create account →" : "Sign in →";
    $("#access-password").autocomplete =
      mode === "register" ? "new-password" : "current-password";
    $$("[data-auth-mode]").forEach((button) => {
      const selected = button.dataset.authMode === mode;
      button.classList.toggle("selected", selected);
      button.setAttribute("aria-pressed", String(selected));
    });
    message("access-error");
    (mode === "register" ? $("#access-name") : $("#access-email")).focus();
  }
  function clearAccountData() {
    state.generation += 1;
    state.profile = null;
    state.applications = [];
    state.jobs = [];
    state.events = [];
    state.ownJobs = [];
    state.updates = { notifications: [], unread_count: 0 };
    state.revision = null;
    state.pendingRefresh = false;
    state.decisionDrafts.clear();
    clearTimeout(state.updatesTimer);
    state.updatesTimer = null;
    $$("[data-notification-feed]").forEach((item) => { item.replaceChildren(); delete item.dataset.fingerprint; item.hidden = true; });
    $$("[data-refresh-updates]").forEach((item) => item.hidden = true);
    $("#moderation-queue")?.replaceChildren();
    $("#moderation-audit")?.replaceChildren();
    $("#moderation-overdue")?.replaceChildren();
    $("#moderation-incidents")?.replaceChildren();
    $("#company-trust-summary")?.replaceChildren();
    $("#verification-domain-challenge")?.replaceChildren();
    $("#company-verification-form")?.reset();
    $("#workspace-notification-count")?.toggleAttribute("hidden", true);
    [
      "jobs-grid",
      "applications-list",
      "applicants-list",
      "calendar-events",
      "company-jobs",
      "hr-overview",
    ].forEach((id) => $(`#${id}`)?.replaceChildren());
    ["applications-summary", "applicants-summary", "calendar-days"].forEach(
      (id) => $(`#${id}`)?.replaceChildren(),
    );
    $("#resume-form")?.reset();
    $("#company-form")?.reset();
    $("#job-create-form")?.reset();
    $$(".workflow-message").forEach((box) => {
      box.hidden = true;
      box.textContent = "";
    });
    $$(
      ".workflow-form, .workflow-schedule-form, .workflow-status-form",
    ).forEach((form) => {
      form.setAttribute("aria-busy", "false");
      $$("button", form).forEach((button) => {
        button.disabled = false;
        if (button.dataset.idleLabel)
          button.textContent = button.dataset.idleLabel;
      });
    });
    bridge()?.clearProfile?.();
  }
  async function applySession(data, isLogin = false) {
    clearAccountData();
    state.session = {
      ...state.session,
      ...data,
      role: data.role || data.user?.role || "guest",
    };
    const generation = state.generation;
    bridge()?.setProgressScope?.(state.session.user?.id ?? null);
    emitSession();
    renderAudience();
    renderProfile();
    if (state.session.user) {
      try {
        const profile = await request("/api/workflow/profile");
        if (generation !== state.generation) return;
        state.profile = profile;
        if (role() === "hr") await loadVerificationCapabilities();
        if (generation !== state.generation) return;
        renderProfile();
        if (role() === "jobseeker" && profile.resume)
          await bridge()?.applyProfile(profile.resume);
      } catch (error) {
        if (generation === state.generation)
          message("profile-message", error.message, "error");
      }
      if (generation !== state.generation) return;
      await loadApplications();
      if (generation !== state.generation) return;
      if (!state.session.user.onboarding_complete) navigate("profile");
      else if (isLogin) navigate("overview");
      closeGate(true);
    } else {
      const sample = bridge()?.catalog()?.profiles?.[0];
      if (sample) await bridge()?.applyProfile(sample);
      if (generation !== state.generation) return;
      if (guestEntered() || isLogin) {
        rememberGuest();
        closeGate(true);
        if (isLogin) navigate("overview");
      } else openGate();
    }
    await loadView(currentView());
    if (generation === state.generation) startUpdates();
  }
  async function guestEntry() {
    if (state.authBusy) return;
    const generation = state.generation;
    try {
      if (state.session.user) {
        await signOut();
      } else {
        rememberGuest();
        closeGate();
        renderAudience();
        await loadView(currentView());
      }
    } catch (error) {
      if (generation === state.generation)
        message("access-error", error.message, "error");
    }
  }
  async function authenticate(path, body) {
    if (state.authBusy) return;
    state.authBusy = true;
    const generation = state.generation;
    const buttons = $$("#access-gate button");
    buttons.forEach((button) => (button.disabled = true));
    message("access-error");
    try {
      const data = await request(path, {
        method: "POST",
        body: JSON.stringify(body),
      });
      if (generation !== state.generation) return;
      $("#access-password").value = "";
      rememberGuest();
      await applySession(data, true);
    } catch (error) {
      if (generation === state.generation)
        message("access-error", error.message, "error");
    } finally {
      state.authBusy = false;
      if ($("#workspace-signin")) $("#workspace-signin").disabled = false;
      buttons.forEach((button) => (button.disabled = false));
    }
  }
  async function signOut() {
    if (state.authBusy) return;
    state.authBusy = true;
    const generation = state.generation;
    const button = $("#workspace-signout");
    if (button) button.disabled = true;
    try {
      const data = await request("/api/auth/logout", {
        method: "POST",
        body: "{}",
      });
      if (generation !== state.generation) return;
      rememberGuest();
      await applySession(data, true);
      notify("Signed out. You are now exploring as a guest.");
    } catch (error) {
      if (generation === state.generation) notify(error.message);
    } finally {
      state.authBusy = false;
      if ($("#workspace-signin")) $("#workspace-signin").disabled = false;
      if (button) button.disabled = false;
    }
  }
  function skillPicker(container, selected = []) {
    const values = new Set(selected);
    $(container).innerHTML = (bridge()?.catalog()?.skills || [])
      .map(
        (skill) =>
          `<label class="skill-checkbox"><input type="checkbox" value="${escape(skill.id)}"${values.has(skill.id) ? " checked" : ""}><span title="${escape(skill.description)}">${escape(skill.name)}</span></label>`,
      )
      .join("");
  }
  function renderProfile() {
    $("#guest-profile").hidden = role() !== "guest";
    $("#resume-form").hidden = role() !== "jobseeker";
    $("#company-form").hidden = role() !== "hr";
    $("#hr-job-management").hidden = role() !== "hr";
    $("#workspace-profile-title").textContent =
      role() === "hr"
        ? "Your company, your opportunities."
        : "Your profile, your next step.";
    $("#workspace-profile-description").textContent =
      role() === "hr"
        ? "Introduce your company and give applicants a clear picture of the work."
        : "Your saved resume connects skills, opportunities and future learning.";
    if (role() === "jobseeker") {
      const resume = state.profile?.resume || {};
      [
        "display_name",
        "headline",
        "education",
        "experience",
        "location",
        "interests",
        "weekly_hours",
      ].forEach((key) => {
        const element = $(`#resume-${key.replaceAll("_", "-")}`);
        element.value =
          resume[key] ??
          (key === "display_name"
            ? state.session.user?.display_name || ""
            : key === "weekly_hours"
              ? 6
              : "");
      });
      skillPicker("#resume-skills", resume.skills || []);
      $("#resume-version-note").textContent = resume.version
        ? `Saved resume version ${resume.version}. New applications use this version; previous submissions stay unchanged.`
        : "Save your resume before applying. Select at least one skill and add a headline.";
    }
    if (role() === "hr") {
      const company = state.profile?.company || {};
      ["name", "industry", "location", "description", "website"].forEach(
        (key) => ($(`#company-${key}`).value = company[key] || ""),
      );
      $("#job-role").innerHTML = (bridge()?.catalog()?.roles || [])
        .map(
          (item) =>
            `<option value="${escape(item.id)}">${escape(item.title)}</option>`,
        )
        .join("");
      populateJobRequirements();
      $("#job-deadline").min = nextDate(malaysiaToday());
      $("#job-create-form").hidden = !state.session.user?.onboarding_complete;
      renderCompanyTrust(true);
      if (!state.session.user?.onboarding_complete)
        $("#company-jobs").innerHTML = empty(
          "Start with your company profile",
          "Save the details above to create vacancies and manage applicants.",
        );
    }
    $("#company-trust").hidden = role() !== "hr" || !state.profile?.company;
    $("#moderator-workspace").hidden = !state.session.user?.is_moderator;
  }
  function nextDate(value) {
    const parsed = new Date(`${value}T00:00:00Z`);
    parsed.setUTCDate(parsed.getUTCDate() + 1);
    return parsed.toISOString().slice(0, 10);
  }
  function populateJobRequirements() {
    const selected = (bridge()?.catalog()?.roles || []).find(
      (item) => item.id === $("#job-role").value,
    );
    skillPicker(
      "#job-required-skills",
      selected?.skills.map((item) => item.id) || [],
    );
  }
  async function saveResume(form) {
    const generation = state.generation;
    message("profile-message");
    const body = Object.fromEntries(new FormData(form));
    body.weekly_hours = Number(body.weekly_hours);
    body.skills = $$("#resume-skills input:checked").map(
      (input) => input.value,
    );
    if (!body.skills.length) {
      message("profile-message", "Select at least one current skill.", "error");
      return;
    }
    await formAction(form, async () => {
      try {
        const data = await request("/api/workflow/profile", {
          method: "PUT",
          body: JSON.stringify(body),
        });
        if (generation !== state.generation) return;
        state.profile = data;
        if (data.user) state.session.user = data.user;
        emitSession();
        renderAudience();
        renderProfile();
        const matched = await bridge()?.applyProfile(data.resume);
        if (generation !== state.generation) return;
        message(
          "profile-message",
          matched === false
            ? "Resume saved. Career matches could not reload; try again from Overview."
            : `Resume version ${data.resume?.version || ""} saved. Your skills gaps, job matches and learning plan are updated.`,
          matched === false ? "info" : "success",
        );
        await loadJobs();
      } catch (error) {
        if (generation === state.generation)
          message("profile-message", error.message, "error");
      }
    });
  }
  async function saveCompany(form) {
    const generation = state.generation;
    await formAction(form, async () => {
      try {
        const data = await request("/api/workflow/profile", {
          method: "PUT",
          body: JSON.stringify(Object.fromEntries(new FormData(form))),
        });
        if (generation !== state.generation) return;
        state.profile = data;
        if (data.user) state.session.user = data.user;
        emitSession();
        renderAudience();
        renderProfile();
        message(
          "profile-message",
          "Company profile saved. Complete the employer evidence checks before publishing vacancies.",
        );
        await loadOwnJobs();
      } catch (error) {
        if (generation === state.generation)
          message("profile-message", error.message, "error");
      }
    });
  }
  async function createJob(form) {
    if (!publishingAllowed()) {
      message("job-create-message", "Complete current employer evidence checks and independent moderator review before publishing.", "error");
      return;
    }
    const generation = state.generation;
    const body = Object.fromEntries(new FormData(form));
    body.salary_min = Number(body.salary_min);
    body.salary_max = Number(body.salary_max);
    body.required_skills = $$("#job-required-skills input:checked").map(
      (input) => input.value,
    );
    if (!body.required_skills.length) {
      message(
        "job-create-message",
        "Choose at least one required skill.",
        "error",
      );
      return;
    }
    await formAction(form, async () => {
      try {
        await request("/api/workflow/jobs", {
          method: "POST",
          body: JSON.stringify(body),
        });
        if (generation !== state.generation) return;
        form.reset();
        populateJobRequirements();
        message(
          "job-create-message",
          "Demo vacancy published. It is now available in Find a job.",
        );
        await Promise.all([loadOwnJobs(), loadJobs()]);
      } catch (error) {
        if (generation === state.generation)
          message("job-create-message", error.message, "error");
      }
    });
  }
  function matchBox(match) {
    return `<div class="workflow-match-box"><div class="workflow-match-heading"><span>Stated skill requirements fulfilled</span><strong>${Math.round(percentage(match?.percentage))}%</strong></div><div class="workflow-match-meter"><span data-workflow-meter="${percentage(match?.percentage)}"></span></div></div>`;
  }
  function salaryBox(job) {
    const salary = job.salary || {};
    const minimum = salary.minimum ?? job.salary_min;
    const maximum = salary.maximum ?? job.salary_max;
    const currency = salary.currency || job.salary_currency || "MYR";
    if (!(num(minimum) > 0) || !(num(maximum) >= num(minimum)))
      return '<div class="workflow-salary salary-missing">Salary information required before this vacancy can reopen.</div>';
    const format = (value) => Number(value).toLocaleString("en-MY", { maximumFractionDigits: 2 });
    return `<div class="workflow-salary"><strong>${escape(currency)} ${format(minimum)}–${format(maximum)}</strong><span>base salary / ${escape(salary.period || job.salary_period || "month")}</span><small>Illustrative demo salary · excludes bonuses</small></div>`;
  }
  function effectiveVerificationStatus(verification = {}) {
    const expires = new Date(verification.expires_at).getTime();
    if (verification.status === "verified" &&
        (!Number.isFinite(expires) || expires <= Date.now() ||
         verification.checks?.registry !== "matched" ||
         verification.checks?.domain !== "matched" ||
         verification.checks?.moderator !== "approved")) return "expired";
    return verification.status || "unverified";
  }
  function verificationLabel(verification = {}) {
    const current = effectiveVerificationStatus(verification);
    if (current === "verified") return verification.simulation
      ? "Demo evidence checks complete" : "Public registry & DNS · demo review complete";
    return ({pending: "Evidence review pending", rejected: "Evidence review rejected",
      revoked: "Evidence approval revoked", expired: "Evidence expired · recheck required",
      unverified: "Employer evidence incomplete"})[current] || "Employer evidence incomplete";
  }
  function companyBadges(company = {}) {
    const verification = company.verification || {};
    const complete = effectiveVerificationStatus(verification) === "verified";
    const accountability = company.accountability;
    return `<div class="workflow-trust-badges"><span class="workflow-verification ${complete ? "checks-complete" : "unverified"}" title="Company record, domain control and moderator authorisation review are separate checks. They do not guarantee identity, hiring authority or a safe job.">${escape(verificationLabel(verification))}</span>${accountability ? `<span class="workflow-accountability" title="App score based on recorded salary violations and overdue responses. Not an external company rating.">Response & transparency: ${num(accountability.score)}/100</span>` : ""}</div>`;
  }
  function checkLabel(value) {
    return ({matched: "Passed", approved: "Reviewed", mismatch: "Does not match", missing: "Not demonstrated",
      unavailable: "Source unavailable", unchecked: "Not checked", pending: "Awaiting review", rejected: "Rejected", expired: "Expired · recheck required"})[value] || "Not checked";
  }
  function missingVerificationSteps(verification = {}) {
    const missing = Array.isArray(verification.missing_steps) ? verification.missing_steps : [];
    if (missing.length) return missing.map((item) => typeof item === "string" ? label(item) : item.label || item.detail || "Evidence check required");
    const result = [];
    if (verification.checks?.registry !== "matched") result.push("Match the company record against the registry source.");
    if (verification.checks?.domain !== "matched") result.push("Demonstrate business domain control.");
    if (verification.checks?.moderator !== "approved") result.push("Complete independent recruiter authorisation review.");
    if (["expired", "revoked"].includes(effectiveVerificationStatus(verification))) result.unshift("Run fresh checks and request a new review.");
    return result;
  }
  function verificationDetails(company = {}, inspect = false) {
    const verification = company.verification || {};
    const checks = verification.checks || {};
    const missing = missingVerificationSteps(verification);
    const provider = verification.simulation || verification.mode === "synthetic" ? "Synthetic fixture · simulated checks"
      : verification.provider === "gleif" || verification.mode === "gleif" ? "GLEIF public company record" : "No current provider result";
    return `<details class="workflow-trust-details"${inspect ? " open" : ""}><summary>${inspect ? "Inspect evidence and dates" : "Employer evidence details"}</summary><p class="verification-source-label">${escape(provider)}</p><ol class="verification-checklist">${[["registry", "Company record match"], ["domain", "Business domain control"], ["moderator", "Fictional recruiter authorisation review"]].map(([key, title]) => `<li class="${["matched", "approved"].includes(checks[key]) ? "check-passed" : "check-needed"}"><strong>${escape(title)}</strong><span>${escape(checkLabel(checks[key]))}</span></li>`).join("")}</ol><div class="verification-dates"><span>Last checked: ${verification.checked_at ? escape(date(verification.checked_at, true)) + " MYT" : "No current check"}</span><span>Evidence valid until: ${verification.expires_at ? escape(date(verification.expires_at, true)) + " MYT" : "Not established"}</span></div>${missing.length ? `<p class="form-note"><strong>Still needed</strong></p><ul class="verification-missing">${missing.map((item) => `<li>${escape(item)}</li>`).join("")}</ul>` : ""}${inspect ? registryEvidence(verification) : publicRegistryEvidence(verification)}<p class="form-note">GLEIF covers entities with an LEI. It is not Malaysia’s SSM register and does not establish recruiter identity, authority to hire or job safety. ${verification.simulation ? "These results use fictional records and do not verify a real employer." : "A public company record alone cannot verify a recruiter."}</p></details>`;
  }
  function publicRegistryEvidence(verification) {
    const source = verification.registry_source || {};
    const record = source.record || {};
    if (!source.checked_at) return '<p class="form-note">No dated public registry evidence is available for this employer.</p>';
    const synthetic = source.simulation === true;
    const reference = url(source.source_url);
    return `<div class="verification-evidence"><h4>${synthetic ? "Fictional registry fixture" : "Public registry source"}</h4><p>${escape(source.provider || "Registry source")} · ${escape(checkLabel(source.status))}</p><dl class="verification-record"><div><dt>Registry legal name</dt><dd>${escape(record.legal_name || "Not available")}</dd></div><div><dt>Registration country / number</dt><dd>${escape(record.country || "Not available")} · ${escape(record.registration_number || "Not available")}</dd></div><div><dt>LEI / entity status</dt><dd>${escape(record.lei || "Not available")} · ${escape([record.entity_status, record.registration_status].filter(Boolean).join(" / ") || "Not available")}</dd></div></dl><p class="form-note">Source checked ${escape(date(source.checked_at, true))} MYT · Evidence expires ${source.expires_at ? escape(date(source.expires_at, true)) + " MYT" : "not established"}.</p>${synthetic ? '<p class="form-note">This is a fixed fictional source record. It does not verify a real legal entity.</p>' : reference !== "#" ? `<a class="text-link" href="${escape(reference)}" target="_blank" rel="noopener noreferrer">Inspect the public registry record ↗</a>` : '<p class="form-note">A public source link is unavailable.</p>'}</div>`;
  }
  function registryEvidence(verification) {
    const registry = verification.registry_snapshot || {};
    const domain = verification.domain_snapshot || {};
    const record = registry.record || {};
    const matches = registry.matches || {};
    const review = verification.review || {};
    const fields = [["legal_name", "Legal name"], ["country", "Registration country"], ["registration_number", "Registration number"], ["lei", "LEI"], ["active", "Active entity / registration"]];
    const source = (snapshot) => snapshot.simulation ? escape(snapshot.provider || "Synthetic fixture") : url(snapshot.source) !== "#"
      ? `<a href="${escape(url(snapshot.source))}" target="_blank" rel="noopener noreferrer">Open public source ↗</a>`
      : escape(snapshot.source || snapshot.provider || "No source result");
    return `<div class="verification-evidence"><h4>Registry result</h4><p>${source(registry)}</p><dl class="verification-record">${fields.map(([key, title]) => `<div><dt>${escape(title)}</dt><dd>${escape(key === "active" ? [record.entity_status, record.registration_status].filter(Boolean).join(" / ") || "Unavailable" : record[key] || "Unavailable")} <span class="verification-field-result">${matches[key] === true ? "Matches" : matches[key] === false ? "Mismatch" : "Not confirmed"}</span></dd></div>`).join("")}</dl><p class="form-note">Checked ${registry.checked_at ? escape(date(registry.checked_at, true)) + " MYT" : "not yet"} · Expires ${registry.expires_at ? escape(date(registry.expires_at, true)) + " MYT" : "not established"}</p>${registry.error ? `<p class="verification-warning">${escape(registry.error)}</p>` : ""}<h4>Domain control result</h4><p>${escape(checkLabel(domain.status))} · ${source(domain)}</p><p class="form-note">Checked ${domain.checked_at ? escape(date(domain.checked_at, true)) + " MYT" : "not yet"} · Expires ${domain.expires_at ? escape(date(domain.expires_at, true)) + " MYT" : "not established"}</p>${domain.error ? `<p class="verification-warning">${escape(domain.error)}</p>` : ""}${review.authorization_note ? `<h4>Independent moderator authorisation evidence</h4><p>${escape(review.authorization_note)}</p>${url(review.authorization_reference) !== "#" ? `<a href="${escape(url(review.authorization_reference))}" target="_blank" rel="noopener noreferrer">Inspect recorded public authorisation source ↗</a>` : ""}<p class="form-note">Reviewed ${review.reviewed_at ? escape(date(review.reviewed_at, true)) + " MYT" : "date unavailable"}. This review concerns a fictional recruiter reference only.</p>` : ""}</div>`;
  }
  function salaryFields(job = {}) {
    const prefix = `salary-${job.id || "edit"}`;
    return `<div class="workflow-form-grid"><div><label class="field-label" for="${prefix}-min">Minimum *</label><input id="${prefix}-min" type="number" name="salary_min" min="0.01" max="1000000000" step="0.01" required value="${escape(job.salary_min ?? job.salary?.minimum ?? "")}"></div><div><label class="field-label" for="${prefix}-max">Maximum *</label><input id="${prefix}-max" type="number" name="salary_max" min="0.01" max="1000000000" step="0.01" required value="${escape(job.salary_max ?? job.salary?.maximum ?? "")}"></div><div><label class="field-label" for="${prefix}-currency">Currency</label><select id="${prefix}-currency" name="salary_currency">${["MYR", "USD", "SGD", "GBP", "EUR", "AUD"].map((currency) => `<option${currency === (job.salary_currency || job.salary?.currency) ? " selected" : ""}>${currency}</option>`).join("")}</select></div><div><label class="field-label" for="${prefix}-period">Period</label><select id="${prefix}-period" name="salary_period">${["month", "year", "hour"].map((period) => `<option value="${period}"${period === (job.salary_period || job.salary?.period) ? " selected" : ""}>Per ${period}</option>`).join("")}</select></div></div>`;
  }
  function applicationProgress(application) {
    const history = application.history || [];
    const sla = application.sla || {};
    const final = terminalStatuses.has(application.status);
    const due = sla.due_at || application.response_due_at;
    return `<div class="workflow-progress" data-application-progress="${escape(application.id)}">${due ? `<div class="workflow-sla ${sla.overdue ? "overdue" : final ? "resolved" : ""}"><strong>${final ? "Decision recorded" : sla.overdue ? "Employer response overdue" : "Employer response commitment"}</strong><span>${final ? `Updated ${escape(date(application.updated_at, true))} MYT` : `Due ${escape(date(due, true))} MYT`}</span>${sla.escalated ? '<small>Overdue response flagged for moderator review.</small>' : ""}</div>` : ""}${application.decision_reason ? `<div class="workflow-decision"><strong>Employer’s decision reason</strong><p>${escape(application.decision_reason)}</p></div>` : ""}<details class="workflow-timeline-details"><summary>Application timeline · ${history.length} event${history.length === 1 ? "" : "s"}</summary><ol class="workflow-timeline">${history.length ? history.map((event) => `<li><span class="timeline-dot" aria-hidden="true"></span><div><strong>${escape(label(event.status))}</strong><time>${escape(date(event.created_at, true))} MYT</time>${event.reason ? `<p>${escape(event.reason)}</p>` : ""}</div></li>`).join("") : `<li><div><strong>Submitted</strong><time>${escape(date(application.created_at, true))} MYT</time></div></li>`}</ol></details></div>`;
  }
  async function loadVerificationCapabilities() {
    if (state.verificationCapabilities) return;
    try {
      state.verificationCapabilities = await request("/api/workflow/verification/capabilities");
      $$('[data-demo-role="moderator"]').forEach((button) => {
        button.hidden = state.verificationCapabilities.moderator_demo_available !== true;
      });
    } catch {
      // Publishing stays blocked until the server supplies a current evidence result.
    }
  }
  function renderVerificationMode() {
    const capabilities = state.verificationCapabilities;
    const mode = capabilities?.mode;
    const box = $("#verification-mode");
    if (!box) return;
    box.textContent = mode === "synthetic"
      ? "Synthetic demonstration mode. The registry record and domain challenge are fictional fixtures. No real employer, person or mailbox is verified. No email is sent."
      : mode === "gleif"
        ? "GLEIF provider mode. The server can check public LEI records and a business domain’s DNS TXT record. These checks do not establish recruiter identity or authority. Use public company data and a synthetic recruiter contact only."
        : "Evidence provider unavailable. Current evidence checks are required before publishing. Try loading this workspace again.";
    $("[data-verification-fixture]")?.toggleAttribute("hidden", mode !== "synthetic" || !capabilities?.fixture);
  }
  function publishingAllowed() {
    return state.verificationCapabilities?.publishing_requires_verification === false ||
      (state.profile?.company?.verification?.can_publish === true &&
       effectiveVerificationStatus(state.profile.company.verification) === "verified");
  }
  function renderPublishingPolicy() {
    const box = $("#job-publishing-policy");
    const form = $("#job-create-form");
    if (!box || !form) return;
    const allowed = publishingAllowed();
    box.hidden = allowed;
    box.textContent = "Publishing is paused until the company record matches, business domain control passes and an independent moderator approves recruiter authorisation. Complete the evidence checks above; expired or revoked approvals require a fresh review.";
    const submit = $('button[type="submit"]', form);
    if (submit) submit.disabled = !allowed;
  }
  function renderCompanyTrust(fill = false) {
    const company = state.profile?.company;
    if (!company) return;
    const verification = company.verification || {};
    const evidence = verification.evidence || {};
    renderVerificationMode();
    if (fill) {
      const values = {legal_name: evidence.legal_name || company.name || "", country: evidence.country || "MY",
        registration_number: evidence.registration_number || company.registration_number || "",
        lei: evidence.lei || "", domain: evidence.domain || "", recruiter_email: evidence.recruiter_email || "",
        evidence_note: evidence.evidence_note || company.evidence_note || ""};
      Object.entries(values).forEach(([key, value]) => {
        const input = $(`[name="${key}"]`, $("#company-verification-form"));
        if (input) input.value = value;
      });
    }
    const accountability = company.accountability || {};
    $("#company-trust-summary").innerHTML = `${companyBadges(company)}${verification.reason ? `<p class="workflow-review-reason"><strong>Review note:</strong> ${escape(verification.reason)}</p>` : ""}${verificationDetails(company, true)}<p class="form-note">${num(accountability.violations)} recorded salary compliance incident${num(accountability.violations) === 1 ? "" : "s"} · ${num(accountability.overdue_applications)} overdue application response${num(accountability.overdue_applications) === 1 ? "" : "s"}. This accountability score covers activity in this app only.</p>`;
    renderDomainChallenge(verification);
    $("[data-verification-recheck]")?.toggleAttribute("hidden", !verification.evidence);
    renderPublishingPolicy();
  }
  function renderDomainChallenge(verification) {
    const challenge = verification.domain_challenge;
    const box = $("#verification-domain-challenge");
    if (!box) return;
    if (!challenge || verification.checks?.domain === "matched") {
      box.replaceChildren();
      return;
    }
    const synthetic = challenge.simulation === true;
    const expired = !challenge.expires_at || new Date(challenge.expires_at).getTime() <= Date.now();
    box.innerHTML = `<section class="verification-challenge"><h3>${synthetic ? "Complete the synthetic domain challenge" : "Demonstrate control of the business domain"}</h3><p>${escape(challenge.instructions || (synthetic ? "Enter the local demonstration token below. This simulates a challenge and sends no email." : "Publish this token as a DNS TXT record at the name below, then ask the server to check it."))}</p><dl class="verification-record"><div><dt>${synthetic ? "Demo challenge name" : "DNS TXT record name"}</dt><dd><code>${escape(challenge.name || "Not available")}</code></dd></div><div><dt>${synthetic ? "Local demo token" : "TXT value"}</dt><dd><code>${escape(challenge.token || "Not available")}</code></dd></div></dl><p class="form-note">Owner-only challenge · Expires ${challenge.expires_at ? escape(date(challenge.expires_at, true)) + " MYT" : "not established"}. ${synthetic ? "This is a local fixture, not proof of a real domain." : "DNS control is separate from recruiter identity and hiring authorisation."}</p>${expired ? '<p class="verification-warning">This challenge expired. Submit the evidence form again to create a new challenge.</p>' : `<form data-verification-challenge class="verification-challenge-form">${synthetic ? '<label class="field-label" for="verification-challenge-token">Local demo token</label><input id="verification-challenge-token" name="token" maxlength="200" autocomplete="off" required><button type="button" class="text-link" data-fill-challenge>Fill the local demo token</button>' : ""}<div class="workflow-actions"><button type="submit" class="button button-primary button-small">${synthetic ? "Confirm synthetic challenge" : "Check public DNS TXT record"}</button></div></form>`}</section>`;
  }
  async function refreshVerification(messageText) {
    const generation = state.generation;
    const profile = await request("/api/workflow/profile");
    if (generation !== state.generation) return;
    state.profile = profile;
    renderCompanyTrust();
    message("verification-message", messageText);
  }
  async function submitVerification(form) {
    const generation = state.generation;
    await formAction(form, async () => {
      try {
        await request("/api/workflow/company/verification", { method: "PUT", body: JSON.stringify(Object.fromEntries(new FormData(form))) });
        if (generation !== state.generation) return;
        await refreshVerification("Company record check recorded. Complete the domain challenge below, then an independent moderator must inspect recruiter authorisation. No approval is implied by submission.");
      } catch (error) {
        if (generation === state.generation) message("verification-message", error.message, "error");
      }
    });
  }
  async function confirmDomainChallenge(form) {
    const generation = state.generation;
    await formAction(form, async () => {
      try {
        await request("/api/workflow/company/verification/challenge", { method: "POST", body: JSON.stringify(Object.fromEntries(new FormData(form))) });
        if (generation !== state.generation) return;
        await refreshVerification("Domain check recorded. Review the result above; an independent moderator still needs to inspect recruiter authorisation.");
      } catch (error) {
        if (generation === state.generation) message("verification-message", error.message, "error");
      }
    });
  }
  function moderationCompany(company) {
    const verification = company.verification || {};
    const evidence = verification.evidence || {};
    const current = effectiveVerificationStatus(verification);
    const ownCompany = Number(company.owner_id) === Number(state.session.user?.id);
    const ready = verification.checks?.registry === "matched" && verification.checks?.domain === "matched" &&
      new Date(verification.expires_at).getTime() > Date.now();
    let review = '<p class="form-note">The company must submit fresh evidence before another review.</p>';
    if (ownCompany) review = '<p class="form-note">Another authorised moderator must review your own company.</p>';
    else if (["pending", "verified"].includes(current)) {
      const id = escape(company.id);
      review = `<form data-moderation-form="${id}" class="workflow-moderation-form"><label class="field-label" for="moderation-status-${id}">Review decision *</label><select id="moderation-status-${id}" name="status" required><option value="">Choose a decision</option>${current === "verified" ? '<option value="revoked">Revoke evidence approval</option>' : `<option value="verified"${ready ? "" : " disabled"}>${verification.simulation ? "Approve synthetic evidence review" : "Approve evidence review"}</option><option value="rejected">Reject evidence review</option>`}</select>${current === "pending" ? `<p class="form-note">${ready ? "The registry and domain checks passed. Inspect the sources and independently review recruiter authorisation before approving." : "Approval is blocked until fresh registry and domain checks both pass. You may record a rejection with a reason."}</p><fieldset class="verification-review-checklist"><legend>Independent confirmations required to approve</legend><label class="workflow-checkbox"><input type="checkbox" name="registration_confirmed"> I inspected the registry source and confirmed the legal name, registration, country and active status.</label><label class="workflow-checkbox"><input type="checkbox" name="domain_control_confirmed"> I inspected the fresh domain control result and its relationship to this company.</label><label class="workflow-checkbox"><input type="checkbox" name="recruiter_authorization_confirmed"> I independently reviewed public company evidence of the fictional recruiter's hiring authorisation.</label></fieldset><label class="field-label" for="authorization-reference-${id}">Public company authorisation source (HTTPS)</label><input id="authorization-reference-${id}" name="authorization_reference" type="url" maxlength="500" placeholder="https://company.example.invalid/team"><label class="field-label" for="authorization-note-${id}">What independent authorisation evidence did you inspect?</label><textarea id="authorization-note-${id}" name="authorization_note" rows="3" minlength="20" maxlength="1500" placeholder="Describe the public company evidence, who it authorises and how it supports this recruiter's authority. An employer's assertion alone is insufficient."></textarea>` : ""}<label class="field-label" for="moderation-reason-${id}">Decision reason *</label><textarea id="moderation-reason-${id}" name="reason" rows="3" maxlength="1000" required placeholder="Record the evidence supporting this decision and any unresolved concerns."></textarea><div class="workflow-actions"><button type="submit" class="button button-primary button-small">Record evidence decision</button></div></form>`;
    }
    return `<article class="workflow-moderation-item"><div class="workflow-card-top"><h3>${escape(company.name)}</h3>${companyBadges(company)}</div>${verificationDetails(company, true)}<dl class="workflow-resume-details"><div><dt>Submitted legal name / country</dt><dd>${escape(evidence.legal_name || "Not submitted")} · ${escape(evidence.country || "Not submitted")}</dd></div><div><dt>Submitted registration / LEI</dt><dd>${escape(evidence.registration_number || "Not submitted")} · ${escape(evidence.lei || "Not supplied")}</dd></div><div><dt>Business domain / synthetic recruiter contact</dt><dd>${escape(evidence.domain || "Not submitted")} · ${escape(evidence.recruiter_email || "Not submitted")}</dd></div><div><dt>Employer's synthetic authorisation note</dt><dd>${escape(evidence.evidence_note || "Not submitted")}</dd></div></dl>${verification.reason ? `<p class="workflow-review-reason"><strong>Previous decision:</strong> ${escape(verification.reason)}</p>` : ""}${review}</article>`;
  }
  function syncModerationRequirements(form) {
    const approving = $('[name="status"]', form).value === "verified";
    $$('input[type="checkbox"], [name="authorization_reference"], [name="authorization_note"]', form).forEach((input) => {
      input.required = approving;
      if (input.name === "authorization_note") input.minLength = approving ? 20 : 0;
    });
  }
  async function loadModeration() {
    if (!state.session.user?.is_moderator) return;
    const generation = state.generation;
    try {
      const data = await request("/api/workflow/moderation");
      if (generation !== state.generation) return;
      const companies = data.companies || [];
      $("#moderation-queue").innerHTML = companies.length ? companies.map(moderationCompany).join("") : empty("No company reviews waiting", "New evidence submissions will appear here.");
      $("#moderation-overdue").innerHTML = (data.overdue_applications || []).map((item) => `<div class="workflow-audit-row"><strong>${escape(item.company_name)} · ${escape(item.job_title)}</strong><time>Response due ${escape(date(item.due_at, true))} MYT</time><p>Application #${num(item.application_id)} · ${escape(label(item.status))}${item.escalated_at ? " · Escalated for review" : ""}</p></div>`).join("") || '<p class="form-note">No employer responses are currently overdue.</p>';
      $("#moderation-incidents").innerHTML = (data.incidents || []).map((item) => `<div class="workflow-audit-row"><strong>Company #${num(item.company_id)} · ${escape(label(item.kind))}</strong><time>${escape(date(item.created_at, true))} MYT</time><p>${escape(item.detail)}</p></div>`).join("") || '<p class="form-note">No salary compliance incidents recorded.</p>';
      $("#moderation-audit").innerHTML = (data.audit || []).slice(0, 30).map((item) => `<div class="workflow-audit-row"><strong>${escape(item.company_name || item.company_id || "Company")} · ${escape(label(item.status || item.action || "reviewed"))}</strong><time>${escape(date(item.created_at || item.reviewed_at, true))}</time><p>${escape(item.reason || "")}</p></div>`).join("") || '<p class="form-note">No moderation decisions recorded yet.</p>';
    } catch (error) {
      if (generation === state.generation) message("moderation-message", error.message, "error");
    }
  }
  async function saveModeration(form) {
    const generation = state.generation;
    await formAction(form, async () => {
      try {
        const payload = Object.fromEntries(new FormData(form));
        ["registration_confirmed", "domain_control_confirmed", "recruiter_authorization_confirmed"].forEach((key) => {
          payload[key] = $(`[name="${key}"]`, form)?.checked === true;
        });
        await request(`/api/workflow/moderation/companies/${encodeURIComponent(form.dataset.moderationForm)}`, { method: "PATCH", body: JSON.stringify(payload) });
        if (generation !== state.generation) return;
        message("moderation-message", "Review decision recorded with its reason and audit entry.");
        await loadModeration();
      } catch (error) {
        if (generation === state.generation) message("moderation-message", error.message, "error");
      }
    });
  }
  async function saveSalary(form) {
    const generation = state.generation;
    const payload = Object.fromEntries(new FormData(form));
    payload.salary_min = Number(payload.salary_min);
    payload.salary_max = Number(payload.salary_max);
    await formAction(form, async () => {
      try {
        await request(`/api/workflow/jobs/${encodeURIComponent(form.dataset.salaryForm)}`, { method: "PATCH", body: JSON.stringify(payload) });
        if (generation !== state.generation) return;
        message("profile-message", "Base salary range updated. Applicants can review it before applying.");
        await loadOwnJobs();
      } catch (error) {
        if (generation === state.generation) message("profile-message", error.message, "error");
      }
    });
  }
  function exposureDetails(exposure) {
    if (!exposure) return "";
    const research = exposure.research_evidence || {};
    const value = research.metric?.percent;
    const available = research.status === "available" && value !== null && value !== undefined && Number.isFinite(Number(value));
    const published = available ? Number(value).toLocaleString("en-MY", {maximumFractionDigits: 1}) : null;
    const source = research.source || {};
    const mapping = research.mapping || {};
    const scope = research.scope || {};
    const uncertainty = typeof research.uncertainty === "string" ? research.uncertainty : research.uncertainty?.text || "";
    const evidence = available
      ? `<div class="published-exposure"><strong>Published exposure index: ${escape(published)}/100</strong><p>${escape(research.metric?.interpretation || "Technical exposure to generative AI at occupation level; not a probability of job loss.")}</p><p>${escape(source.publisher || "ILO")} · ${escape(source.year || "")} · ${escape(source.title || "Published occupational research")}</p><p><strong>${mapping.relation === "broader_proxy" ? "Broader occupation proxy" : "Occupation mapping"}:</strong> ${escape(mapping.source_code || "")} ${escape(mapping.source_title || "")}. ${escape(mapping.rationale || "")}</p><p class="form-note">${escape([scope.geography, scope.population, scope.time_horizon].filter(Boolean).join(" · "))}</p>${uncertainty ? `<p class="form-note">${escape(uncertainty)}</p>` : ""}${Array.isArray(research.limitations) && research.limitations.length ? `<ul>${research.limitations.map((item) => `<li>${escape(item)}</li>`).join("")}</ul>` : ""}${url(source.url) !== "#" ? `<a class="text-link" href="${escape(url(source.url))}" target="_blank" rel="noopener noreferrer">Read the research source ↗</a>` : ""}<p class="form-note">This published index is fixed to the cited study and mapping. Scenario edits and authored task examples do not change it. It is not a measured job-replacement probability.</p></div>`
      : '<div class="published-exposure"><strong>Published exposure index unavailable</strong><p>No usable published occupation mapping is available for this role. An unavailable index is not zero exposure.</p></div>';
    return `<details class="workflow-exposure"><summary>${available ? `Published exposure index: ${escape(published)}/100` : "Published exposure index unavailable"} · Research & task scenarios</summary>${evidence}<p><strong>Authored task scenario: ${escape(exposure.level || "estimated")}</strong></p><p>${escape(exposure.summary || "")}</p>${exposure.task_assessment ? `<p><strong>${percentage(exposure.task_assessment.percentage)}/100 illustrative task-assistance index.</strong> ${escape(exposure.task_assessment.scope || "Six authored task examples; not a job-replacement probability.")}</p><p>${escape(exposure.task_assessment.formula || "")}</p>` : ""}${exposure.task_examples?.length ? `<ul>${exposure.task_examples.map((item) => `<li>${escape(typeof item === "string" ? item : item.task || item.title || "")}</li>`).join("")}</ul>` : ""}<p><strong>Human strengths:</strong> ${escape(Array.isArray(exposure.human_strengths) ? exposure.human_strengths.join(" · ") : exposure.human_strengths || "")}</p><p>${escape(exposure.method || "Scenario assumption, not a replacement probability.")}</p>${exposure.source_url ? `<a class="text-link" href="${escape(url(exposure.source_url))}" target="_blank" rel="noopener noreferrer">Occupation reference ↗</a>` : ""}</details>`;
  }
  function vacancyPathway(pathway) {
    if (!pathway) return "";
    const steps = pathway.steps || [];
    return `<details class="workflow-vacancy-pathway"><summary>Learning plan for this vacancy</summary><p>${num(pathway.total_hours)} introductory study hours · ${num(pathway.weeks)} weeks at your learning budget. This plan covers the vacancy’s missing skills and prerequisites.</p>${steps.length ? `<ol>${steps.map((step) => `<li><strong>${escape(step.name)}</strong><span>${num(step.hours)} estimated hours · Week ${num(step.week_start)}${step.week_start !== step.week_end ? `–${num(step.week_end)}` : ""} · SDGs ${(step.sdgs || []).map(escape).join(", ")}</span>${(step.resources || []).map((resource) => `<a href="${escape(url(resource.url))}" target="_blank" rel="noopener noreferrer">${escape(resource.title)} · ${escape(resource.provider)} ↗</a>`).join("")}</li>`).join("")}</ol>` : "<p>You cover all stated catalogue skills. Review the responsibilities and build practical evidence of your capabilities.</p>"}<p>Estimated study time does not establish skill mastery or job readiness.</p></details>`;
  }
  function renderJobs() {
    $("#jobs-count").textContent =
      `${state.jobs.length} demo opportunit${state.jobs.length === 1 ? "y" : "ies"}${role() === "jobseeker" ? " · matched to your saved resume" : " · matched to the current exploratory skills profile"}`;
    $("#jobs-grid").innerHTML = state.jobs.length
      ? state.jobs
          .map((job) => {
            const company = job.company || {};
            let action =
              role() === "guest"
                ? '<button type="button" class="button button-primary" data-open-access>Sign in to apply</button>'
                : role() === "hr"
                  ? '<a class="button button-secondary" href="#profile" data-view="profile">Manage company</a>'
                  : !state.session.user?.onboarding_complete
                    ? '<a class="button button-primary" href="#profile" data-view="profile">Complete resume to apply</a>'
                    : job.application_id
                      ? `<a class="button button-secondary" href="#applications" data-view="applications">${escape(label(job.application_status || "Applied"))} · View application</a>`
                      : job.status !== "open" || job.deadline < malaysiaToday()
                        ? '<span class="workflow-status closed">Applications closed</span>'
                        : `<button type="button" class="button button-primary" data-apply-job="${escape(job.id)}">Apply to demo job →</button>`;
            return `<article class="card workflow-job-card"><div class="workflow-card-top"><div class="workflow-company"><span class="workflow-company-avatar" aria-hidden="true">${escape((company.name || "D").slice(0, 1))}</span><div><strong>${escape(company.name)}</strong><small>${escape(company.industry)}</small></div></div><span class="subtle-badge">Synthetic vacancy</span></div><div><h2>${escape(job.title)}</h2><p>${escape(job.location)} · ${escape(label(job.work_mode))}</p></div><div class="workflow-tags"><span class="workflow-tag">${escape(label(job.employment_type))}</span><span class="workflow-tag">Apply by ${escape(date(job.deadline))}</span>${status(job.status)}</div>${salaryBox(job)}${companyBadges(company)}${verificationDetails(company)}<p>${escape(job.description)}</p>${matchBox(job.match)}<div class="skill-block"><p class="skill-block-label">Skills you bring</p><div class="skill-chip-list">${skills(job.match?.matched_skills) || '<span class="muted small">Build a starting point with the skills below.</span>'}</div></div><div class="skill-block"><p class="skill-block-label">Skills to develop</p><div class="skill-chip-list">${skills(job.match?.missing_skills, true) || '<span class="skill-chip">✓ All stated skills covered</span>'}</div></div>${vacancyPathway(job.pathway)}${exposureDetails(job.exposure)}<div class="workflow-actions">${action}<button type="button" class="button button-secondary" data-chat-job="${escape(job.id)}">Contact HR</button><button type="button" class="button button-secondary" data-plan-role="${escape(job.role_id)}">Explore career-role plan</button><span class="muted small">The broader career-role plan may include skills beyond this vacancy.</span></div></article>`;
          })
          .join("")
      : empty(
          "A different search could open a door.",
          "No demo vacancies match these filters. Try another role, skill, company or location.",
        );
    decorateMeters();
  }
  async function loadJobs() {
    const generation = state.generation,
      sequence = ++state.jobsSequence;
    const params = new URLSearchParams({
      sort: $("#jobs-sort")?.value || "match",
      search: $("#jobs-search").value.trim(),
      location: $("#jobs-location").value.trim(),
      work_mode: $("#jobs-work-mode").value,
    });
    if (role() === "guest")
      params.set("skills", (bridge()?.profile()?.skills || []).join(","));
    if (role() === "guest")
      params.set(
        "weekly_hours",
        String(bridge()?.profile()?.weekly_hours || 6),
      );
    try {
      const data = await request(`/api/workflow/jobs?${params}`);
      if (generation !== state.generation || sequence !== state.jobsSequence)
        return;
      state.jobs = data.jobs || [];
      renderJobs();
      message("jobs-message");
    } catch (error) {
      if (generation === state.generation && sequence === state.jobsSequence) {
        message("jobs-message", error.message, "error");
        if (!state.jobs.length)
          $("#jobs-grid").innerHTML = empty(
            "Opportunities could not load.",
            "Check the Python server, then try searching again.",
          );
      }
    }
  }
  async function loadOwnJobs() {
    if (role() !== "hr" || !state.session.user?.onboarding_complete) return;
    const generation = state.generation;
    try {
      const data = await request("/api/workflow/jobs?mine=1");
      if (generation !== state.generation) return;
      state.ownJobs = data.jobs || [];
      $("#company-jobs").innerHTML = state.ownJobs.length
        ? state.ownJobs
            .map(
              (job) =>
                `<article class="card workflow-application"><div class="workflow-card-top"><div><h3>${escape(job.title)}</h3><p>${escape(job.location)} · ${escape(date(job.deadline))}</p></div>${status(job.status)}</div>${salaryBox(job)}<details><summary>Edit base salary range</summary><form data-salary-form="${escape(job.id)}" class="workflow-salary-form">${salaryFields(job)}<div class="workflow-actions"><button type="submit" class="button button-primary button-small">Save salary range</button></div></form></details><div class="workflow-actions"><button type="button" class="button button-secondary button-small" data-job-status="${job.status === "open" ? "closed" : "open"}" data-job-id="${escape(job.id)}"${job.status !== "open" && !publishingAllowed() ? " disabled" : ""}>${job.status === "open" ? "Close applications" : "Reopen applications"}</button></div></article>`,
            )
            .join("")
        : empty(
            "Your next opportunity starts here.",
            "Create a synthetic vacancy below to see it in the job explorer.",
          );
    } catch (error) {
      if (generation === state.generation)
        message("profile-message", error.message, "error");
    }
  }
  async function applyToJob(button) {
    const generation = state.generation;
    button.disabled = true;
    try {
      await request("/api/workflow/applications", {
        method: "POST",
        body: JSON.stringify({ job_id: Number(button.dataset.applyJob) }),
      });
      if (generation !== state.generation) return;
      await Promise.all([loadJobs(), loadApplications()]);
      if (generation !== state.generation) return;
      message(
        "jobs-message",
        "Application submitted to the demo company. Track it in My applications; your submitted resume version has been preserved.",
      );
      notify("Demo application submitted.");
    } catch (error) {
      if (generation === state.generation)
        message("jobs-message", error.message, "error");
    } finally {
      if (generation === state.generation && button.isConnected)
        button.disabled = false;
    }
  }
  function interviewDetails(interview) {
    if (!interview) return "";
    return `<div class="workflow-interview"><span>${status(interview.status)}</span><strong>Online interview · ${escape(date(interview.start, true))} MYT</strong><span>Ends ${escape(date(interview.end, true))} MYT</span>${interview.meeting_url ? `<a href="${escape(url(interview.meeting_url))}" target="_blank" rel="noopener noreferrer">Open meeting link ↗</a>` : ""}${interview.notes ? `<p>${escape(interview.notes)}</p>` : ""}<a href="#calendar" data-view="calendar">See in calendar →</a></div>`;
  }
  function applicationSummary(container, applications, isHr = false) {
    const counts = [
      {
        value: applications.length,
        title: isHr ? "Applications received" : "Applications submitted",
      },
      {
        value: applications.filter((item) => pendingStatuses.has(item.status))
          .length,
        title: "Pending next steps",
      },
      {
        value: applications.filter(
          (item) => item.interview && item.interview.status !== "cancelled",
        ).length,
        title: "Interview sessions",
      },
    ];
    counts.push({ value: applications.filter((item) => item.sla?.overdue).length, title: "Response overdue" });
    $(container).innerHTML = counts
      .map(
        (item) =>
          `<article class="workflow-summary"><strong>${item.value}</strong><span>${escape(item.title)}</span></article>`,
      )
      .join("");
  }
  function renderApplications() {
    if (role() === "guest") {
      $("#applications-summary").replaceChildren();
      $("#applications-list").innerHTML = empty(
        "Your applications can live here.",
        "Sign in as a job seeker to submit demo applications and track replies.",
        signInAction(),
      );
      return;
    }
    if (role() === "hr") {
      $("#applications-summary").replaceChildren();
      $("#applications-list").innerHTML = empty(
        "Your workspace is the applicant inbox.",
        "Review your company’s applications and pending actions there.",
        '<a class="button button-primary" href="#applicants" data-view="applicants">Open applicant inbox</a>',
      );
      return;
    }
    applicationSummary("#applications-summary", state.applications);
    $("#applications-list").innerHTML = state.applications.length
      ? state.applications
          .map(
            (application) =>
              `<article class="card workflow-application" data-application-id="${escape(application.id)}"><div class="workflow-card-top"><span class="card-kicker">${escape(application.job?.company?.name || "Demo company")}</span>${status(application.status)}</div><h2>${escape(application.job?.title)}</h2><p>Applied ${escape(date(application.created_at))} · Resume version ${escape(application.applicant?.resume?.version || 1)} · ${Math.round(percentage(application.match?.percentage))}% stated skill requirements fulfilled</p>${companyBadges(application.job?.company)}${applicationProgress(application)}${interviewDetails(application.interview)}<details><summary>Your submitted skills</summary><div class="skill-chip-list">${skills(application.match?.matched_skills)}</div><p class="small muted">Gaps at submission</p><div class="skill-chip-list">${skills(application.match?.missing_skills, true) || '<span class="skill-chip">All stated skills covered</span>'}</div></details><div class="workflow-actions"><button class="button button-primary button-small" type="button" data-chat-application="${escape(application.id)}">Message HR</button><button class="button button-secondary button-small" type="button" data-plan-role="${escape(application.job?.role_id)}">Explore learning path</button>${!terminalStatuses.has(application.status) ? `<button class="button button-secondary button-small" type="button" data-withdraw-application="${escape(application.id)}">Withdraw application</button>` : ""}</div></article>`,
          )
          .join("")
      : empty(
          "Take your first next step.",
          "Apply to a synthetic opportunity to see it in your application cart.",
          '<a class="button button-primary" href="#jobs" data-view="jobs">Find a job</a>',
        );
  }
  function resumeDetails(resume) {
    if (!resume) return "<p>No submitted resume available.</p>";
    return `<dl class="workflow-resume-details"><div><dt>Headline</dt><dd>${escape(resume.headline)}</dd></div><div><dt>Education</dt><dd>${escape(resume.education || "Not provided")}</dd></div><div><dt>Experience</dt><dd>${escape(resume.experience || "Not provided")}</dd></div><div><dt>Location</dt><dd>${escape(resume.location || "Not provided")}</dd></div><div><dt>Interests</dt><dd>${escape(resume.interests || "Not provided")}</dd></div></dl>`;
  }
  function scheduleForm(application) {
    const interview = application.interview;
    const active = interview && interview.status !== "cancelled";
    return `<details><summary>${active ? "Reschedule online interview" : "Schedule an online interview"}</summary><form class="workflow-schedule-form" data-schedule-form="${escape(application.id)}"><h3>${active ? "Update the session" : "Arrange a conversation"}</h3><div class="workflow-form-grid"><div><label class="field-label" for="interview-start-${escape(application.id)}">Date & time (MYT / UTC+8)</label><input id="interview-start-${escape(application.id)}" name="start" type="datetime-local" required value="${active ? escape(localInputValue(interview.start)) : ""}"></div><div><label class="field-label" for="interview-duration-${escape(application.id)}">Duration (minutes)</label><input id="interview-duration-${escape(application.id)}" name="duration_minutes" type="number" min="30" max="180" step="1" value="${active ? Math.max(30, Math.round((new Date(interview.end) - new Date(interview.start)) / 60000)) : 30}" required></div></div><label class="workflow-checkbox"><input type="checkbox" name="generate_link" data-generate-meeting${active ? "" : " checked"}> Generate a unique Jitsi meeting link</label><label class="field-label" for="interview-link-${escape(application.id)}">Your meeting URL (HTTPS)</label><input id="interview-link-${escape(application.id)}" name="meeting_url" type="url" maxlength="500"${active ? " required" : " disabled"} placeholder="https://example.test/demo-interview" value="${active ? escape(interview.meeting_url) : ""}"><label class="field-label" for="interview-notes-${escape(application.id)}">Notes for the applicant</label><textarea id="interview-notes-${escape(application.id)}" name="notes" maxlength="1000" rows="2">${active ? escape(interview.notes) : ""}</textarea><p class="form-note">Saved to both calendars with an in-app invitation. A generated link opens an external Jitsi room when you join; the provider may require host sign-in and sets its own access rules. No email is sent.</p><div class="workflow-actions"><button class="button button-primary button-small" type="submit">${active ? "Save rescheduled interview" : "Schedule demo interview"}</button>${active ? `<button class="button button-secondary button-small" type="button" data-interview-action="cancelled" data-interview-id="${escape(interview.id)}">Cancel interview</button>` : ""}</div></form></details>`;
  }
  function renderApplicants() {
    if (role() !== "hr") {
      $("#applicants-summary").replaceChildren();
      $("#applicants-list").innerHTML = empty(
        "This is the HR workspace.",
        "Sign in with an HR account to manage applicants for your company.",
        signInAction(),
      );
      return;
    }
    applicationSummary("#applicants-summary", state.applications, true);
    const search = $("#applicant-search").value.toLowerCase().trim(),
      filter = $("#applicant-filter").value;
    const matches = state.applications.filter(
      (application) =>
        (filter === "all" ||
          (filter === "pending"
            ? pendingStatuses.has(application.status)
            : filter === "overdue" ? application.sla?.overdue : application.status === filter)) &&
        `${application.applicant?.display_name} ${application.job?.title} ${application.applicant?.resume?.headline} ${(application.match?.matched_skills || []).map((item) => item.name).join(" ")}`
          .toLowerCase()
          .includes(search),
    );
    $("#applicants-list").innerHTML = matches.length
      ? matches
          .map(
            (application) =>
              `<article class="card workflow-application" data-application-id="${escape(application.id)}"><div class="workflow-card-top"><div><span class="card-kicker">${escape(application.job?.title)}</span><h2>${escape(application.applicant?.display_name || "Demo applicant")}</h2></div>${status(application.status)}</div><p>${escape(application.applicant?.resume?.headline || "Synthetic applicant profile")} · Submitted ${escape(date(application.created_at))} · Resume v${escape(application.applicant?.resume?.version || 1)}</p>${matchBox(application.match)}${applicationProgress(application)}<details data-review-application="${escape(application.id)}"><summary>Review submitted resume and skills${application.status === "submitted" ? " · marks as viewed" : ""}</summary>${resumeDetails(application.applicant?.resume)}<p class="skill-block-label">Skills matching your vacancy</p><div class="skill-chip-list">${skills(application.match?.matched_skills) || '<span class="muted small">No stated skills matched.</span>'}</div><p class="skill-block-label">Skills gaps</p><div class="skill-chip-list">${skills(application.match?.missing_skills, true) || '<span class="skill-chip">All stated skills covered</span>'}</div></details>${interviewDetails(application.interview)}<div class="workflow-actions"><button type="button" class="button button-secondary button-small" data-chat-application="${escape(application.id)}">Message candidate</button></div>${!terminalStatuses.has(application.status) ? `<form class="workflow-status-form" data-status-form="${escape(application.id)}"><label class="sr-only" for="application-status-${escape(application.id)}">Update ${escape(application.applicant?.display_name)} application</label><select id="application-status-${escape(application.id)}" name="status"><option value="under_review">Under review</option><option value="shortlisted"${application.status === "shortlisted" ? " selected" : ""}>Shortlisted</option><option value="accepted">Accepted</option><option value="rejected">Rejected</option></select><label class="field-label" for="decision-reason-${escape(application.id)}">Decision reason <span data-reason-required>(required for acceptance or rejection)</span></label><textarea id="decision-reason-${escape(application.id)}" name="reason" rows="2" maxlength="1500" placeholder="Give the applicant constructive, role-related feedback. Required for an acceptance or rejection."></textarea><div class="workflow-actions"><button type="submit" class="button button-secondary button-small">Update decision</button></div></form>${scheduleForm(application)}` : '<p class="form-note">This application has a final status. The submitted profile remains available for review.</p>'}</article>`,
          )
          .join("")
      : empty(
          "Your inbox is clear for this view.",
          state.applications.length
            ? "Try All applications or a different search."
            : "Applicants to your company’s demo vacancies will appear here.",
        );
    restoreDecisionDrafts();
    decorateMeters();
  }
  function restoreDecisionDrafts() {
    $$("[data-status-form]").forEach((form) => {
      const select = $('select[name="status"]', form);
      const textarea = $('textarea[name="reason"]', form);
      select.dataset.initialValue = select.value;
      const draft = state.decisionDrafts.get(form.dataset.statusForm);
      if (draft) {
        select.value = draft.status;
        textarea.value = draft.reason;
      }
      const required = ["accepted", "rejected"].includes(select.value);
      textarea.required = required;
      $('[data-reason-required]', form).textContent = required ? "*" : "(required for acceptance or rejection)";
    });
  }
  function rememberDecisionDraft(form) {
    const select = $('select[name="status"]', form);
    const reason = $('textarea[name="reason"]', form).value;
    if (reason || select.value !== select.dataset.initialValue)
      state.decisionDrafts.set(form.dataset.statusForm, {status: select.value, reason});
    else state.decisionDrafts.delete(form.dataset.statusForm);
  }
  function renderHrOverview() {
    const target = $("#hr-overview");
    if (!target || role() !== "hr") return;
    const pending = state.applications.filter((application) =>
      pendingStatuses.has(application.status),
    ).length;
    target.innerHTML = `<div class="section-heading"><div><h2>Your hiring workspace</h2><p>People and opportunities, with the next action in view.</p></div><a class="text-link" href="#applicants" data-view="applicants">Open applicant inbox →</a></div><div class="workflow-summary-grid"><article class="workflow-summary"><strong>${state.applications.length}</strong><span>Applications received</span></article><article class="workflow-summary"><strong>${pending}</strong><span>Pending next steps</span></article><article class="workflow-summary"><strong>${state.applications.filter((application) => application.interview && application.interview.status !== "cancelled").length}</strong><span>Interview sessions</span></article></div><div class="workflow-notice">${escape(state.profile?.company?.name || "Complete your company profile")} · Synthetic hiring workspace. Your decisions and interview schedules stay inside this prototype.</div>`;
  }
  function hasOpenWork() {
    const section = $$(".view[data-section]").find((item) => item.dataset.section === currentView());
    if (!section) return false;
    return Boolean(section.querySelector("details[open]")) ||
      $$("[data-status-form]", section).some((form) => state.decisionDrafts.has(form.dataset.statusForm)) ||
      (section.contains(document.activeElement) && document.activeElement?.matches("input, textarea, select")) ||
      Boolean(section.querySelector('[aria-busy="true"]'));
  }
  function renderNotifications() {
    const notifications = state.updates.notifications || [];
    const unread = num(state.updates.unread_count);
    const badge = $("#workspace-notification-count");
    if (badge) { badge.textContent = String(unread); badge.hidden = !unread || role() === "guest"; }
    $$("[data-notification-feed]").forEach((feed) => {
      feed.hidden = role() === "guest";
      const fingerprint = JSON.stringify(notifications);
      if (feed.dataset.fingerprint === fingerprint) return;
      feed.dataset.fingerprint = fingerprint;
      const wasOpen = feed.querySelector("details")?.open;
      feed.innerHTML = `<details class="workflow-notifications"><summary>Notifications <span class="subtle-badge">${unread} unread</span></summary><div class="workflow-notification-heading"><p class="form-note">Status changes, messages, interviews and response reminders appear here.</p>${unread ? '<button class="text-link" type="button" data-read-notifications>Mark all as read</button>' : ""}</div><ul>${notifications.length ? notifications.slice(0, 30).map((item) => `<li class="${item.read_at ? "" : "unread"}"><div><strong>${escape(item.title || label(item.kind))}</strong><time>${escape(date(item.created_at, true))} MYT</time></div>${item.application_id || ["moderation", "messages"].includes(item.view) ? `<button type="button" class="text-link" data-notification-application="${escape(item.application_id || "")}" data-notification-view="${escape(item.view || "")}" data-notification-id="${escape(item.id)}">${item.view === "messages" ? "Open messages" : item.view === "moderation" ? "Open review desk" : "View application"} →</button>` : ""}</li>`).join("") : '<li><p>You’re all caught up. Your next notification will appear here.</p></li>'}</ul></details>`;
      if (wasOpen) feed.querySelector("details").open = true;
    });
  }
  async function readNotifications(ids) {
    const generation = state.generation;
    if (Array.isArray(ids) && !ids.length) return;
    try {
      await request("/api/workflow/notifications/read", { method: "PATCH", body: JSON.stringify(ids === "all" ? { all: true } : { ids }) });
      if (generation !== state.generation) return;
      await pollUpdates();
    } catch (error) { if (generation === state.generation) notify(error.message); }
  }
  async function refreshUpdates() {
    const generation = state.generation;
    await loadApplications();
    if (generation !== state.generation) return;
    if (currentView() === "calendar") await loadCalendar();
    if (generation !== state.generation) return;
    state.pendingRefresh = false;
    $$("[data-refresh-updates]").forEach((item) => item.hidden = true);
  }
  async function pollUpdates() {
    if (!state.session.user || document.hidden || state.updatesBusy) return;
    const generation = state.generation;
    state.updatesBusy = true;
    try {
      const data = await request("/api/workflow/updates");
      if (generation !== state.generation) return;
      const changed = state.revision !== null && String(data.revision) !== String(state.revision);
      state.revision = data.revision;
      state.updates = data;
      renderNotifications();
      document.dispatchEvent(new CustomEvent("nextstep:workspace-updates", { detail: data }));
      if (changed) {
        if (["applications", "applicants"].includes(currentView()) && hasOpenWork()) {
          state.pendingRefresh = true;
          $$("[data-refresh-updates]").forEach((item) => item.hidden = false);
        } else await refreshUpdates();
      } else if (state.pendingRefresh && !hasOpenWork()) await refreshUpdates();
    } catch {
      // A transient network failure must not erase the current inbox or draft.
    } finally { state.updatesBusy = false; }
  }
  function startUpdates() {
    clearTimeout(state.updatesTimer);
    if (!state.session.user) return;
    const generation = state.generation;
    const tick = async () => {
      if (generation !== state.generation) return;
      await pollUpdates();
      if (generation === state.generation) state.updatesTimer = setTimeout(tick, 10000);
    };
    tick();
  }
  async function markApplicationViewed(details) {
    if (!details.open || role() !== "hr" || details.dataset.viewing === "true") return;
    const id = Number(details.dataset.reviewApplication);
    const application = state.applications.find((item) => Number(item.id) === id);
    if (!application || application.viewed_at) return;
    const generation = state.generation;
    details.dataset.viewing = "true";
    try {
      const data = await request(`/api/workflow/applications/${id}/viewed`, { method: "POST", body: "{}" });
      if (generation !== state.generation) return;
      const updated = data.application;
      if (updated) {
        state.applications = state.applications.map((item) => Number(item.id) === id ? updated : item);
        const card = details.closest("[data-application-id]");
        const badge = $(".workflow-card-top > .workflow-status", card);
        if (badge) badge.outerHTML = status(updated.status);
        const progress = $("[data-application-progress]", card);
        if (progress) progress.outerHTML = applicationProgress(updated);
        $("summary", details).textContent = "Review submitted resume and skills";
        renderCartCount();
      }
      await pollUpdates();
    } catch (error) { if (generation === state.generation) message("applicants-message", error.message, "error"); }
    finally { if (details.isConnected) details.dataset.viewing = "false"; }
  }
  async function loadApplications() {
    if (role() === "guest") {
      state.applications = [];
      renderApplications();
      renderApplicants();
      renderCartCount();
      return;
    }
    const generation = state.generation,
      sequence = ++state.applicationsSequence;
    try {
      const data = await request("/api/workflow/applications");
      if (
        generation !== state.generation ||
        sequence !== state.applicationsSequence
      )
        return;
      state.applications = data.applications || [];
      renderApplications();
      renderApplicants();
      renderHrOverview();
      renderCartCount();
      renderNotifications();
    } catch (error) {
      if (generation === state.generation)
        message(
          role() === "hr" ? "applicants-message" : "applications-message",
          error.message,
          "error",
        );
    }
  }
  async function updateApplication(
    id,
    statusValue,
    origin = "applicants-message",
    reason = "",
  ) {
    const generation = state.generation;
    try {
      await request(`/api/workflow/applications/${encodeURIComponent(id)}`, {
        method: "PATCH",
        body: JSON.stringify({ status: statusValue, reason }),
      });
      if (generation !== state.generation) return;
      state.decisionDrafts.delete(String(id));
      message(
        origin,
        `Application ${label(statusValue)}. The other workspace will see the updated status.`,
      );
      await Promise.all([loadApplications(), loadJobs(), loadCalendar()]);
    } catch (error) {
      if (generation === state.generation)
        message(origin, error.message, "error");
    }
  }
  async function saveInterview(form) {
    const generation = state.generation;
    const body = Object.fromEntries(new FormData(form));
    body.duration_minutes = Number(body.duration_minutes);
    body.generate_link = body.generate_link === "on";
    if (body.generate_link) body.meeting_url = "";
    // The displayed input is explicitly Malaysia time, regardless of browser timezone.
    const start = new Date(`${body.start}:00+08:00`);
    if (!Number.isFinite(start.getTime())) {
      message(
        "applicants-message",
        "Choose a valid interview date and time.",
        "error",
      );
      return;
    }
    body.start = start.toISOString();
    await formAction(form, async () => {
      try {
        await request(
          `/api/workflow/applications/${encodeURIComponent(form.dataset.scheduleForm)}/interview`,
          { method: "POST", body: JSON.stringify(body) },
        );
        if (generation !== state.generation) return;
        message(
          "applicants-message",
          "Interview saved to both calendars and the applicant’s notifications. Open the meeting link at the scheduled time.",
        );
        await Promise.all([loadApplications(), loadCalendar()]);
      } catch (error) {
        if (generation === state.generation)
          message("applicants-message", error.message, "error");
      }
    });
  }
  async function updateInterview(id, statusValue) {
    const generation = state.generation;
    try {
      await request(`/api/workflow/interviews/${encodeURIComponent(id)}`, {
        method: "PATCH",
        body: JSON.stringify({ status: statusValue }),
      });
      if (generation !== state.generation) return;
      message("calendar-message", `Interview ${label(statusValue)}.`);
      message(
        role() === "hr" ? "applicants-message" : "applications-message",
        `Interview ${label(statusValue)}.`,
      );
      await Promise.all([loadApplications(), loadCalendar()]);
    } catch (error) {
      if (generation === state.generation)
        message(
          currentView() === "calendar"
            ? "calendar-message"
            : role() === "hr"
              ? "applicants-message"
              : "applications-message",
          error.message,
          "error",
        );
    }
  }
  function calendarActions(event) {
    if (event.type !== "interview" || event.status === "cancelled") return "";
    const interviewId =
      event.interview_id ?? String(event.id).replace(/^interview[-_:]?/, "");
    return `<div class="workflow-actions">${role() === "jobseeker" && event.status === "scheduled" ? `<button type="button" class="button button-primary button-small" data-interview-action="confirmed" data-interview-id="${escape(interviewId)}">Confirm attendance</button>` : ""}<button type="button" class="button button-secondary button-small" data-interview-action="cancelled" data-interview-id="${escape(interviewId)}">Cancel interview</button></div>`;
  }
  function renderCalendar() {
    const content = $("#calendar-content");
    content.hidden = role() === "guest";
    $("#calendar-export").hidden = role() === "guest";
    if (role() === "guest") {
      message(
        "calendar-message",
        "Sign in to see application deadlines and scheduled interviews. Guest exploration remains available in the other views.",
        "info",
      );
      return;
    }
    const [year, month] = state.month.split("-").map(Number);
    const first = new Date(Date.UTC(year, month - 1, 1)),
      totalDays = new Date(Date.UTC(year, month, 0)).getUTCDate(),
      offset = (first.getUTCDay() + 6) % 7;
    $("#calendar-month").textContent = first.toLocaleDateString("en-MY", {
      timeZone: "UTC",
      month: "long",
      year: "numeric",
    });
    const blanks = Array.from(
      { length: offset },
      () => '<div class="calendar-day blank" aria-hidden="true"></div>',
    );
    const days = Array.from({ length: totalDays }, (_, index) => {
      const value = `${state.month}-${String(index + 1).padStart(2, "0")}`,
        events = state.events.filter(
          (event) => malaysiaDate(event.start) === value,
        );
      return `<button type="button" class="calendar-day${value === malaysiaToday() ? " today" : ""}${value === state.selectedDay ? " selected" : ""}" data-calendar-day="${value}" aria-label="${escape(date(`${value}T00:00:00+08:00`))}, ${events.length} event${events.length === 1 ? "" : "s"}" aria-pressed="${value === state.selectedDay}"><span class="calendar-day-number">${index + 1}</span>${events
        .slice(0, 3)
        .map(
          (event) =>
            `<span class="calendar-event-dot ${escape(event.type)} ${event.status === "cancelled" ? "cancelled" : ""}" title="${escape(event.title)}"></span>`,
        )
        .join("")}</button>`;
    });
    $("#calendar-days").innerHTML = [...blanks, ...days].join("");
    $("#calendar-agenda-title").textContent = state.selectedDay
      ? date(`${state.selectedDay}T00:00:00+08:00`)
      : "Upcoming events";
    const events = state.events
      .filter((event) =>
        state.selectedDay
          ? malaysiaDate(event.start) === state.selectedDay
          : malaysiaDate(event.start) >= malaysiaToday(),
      )
      .sort((a, b) => String(a.start).localeCompare(String(b.start)));
    $("#calendar-events").innerHTML = events.length
      ? events
          .map(
            (event) =>
              `<article class="card workflow-event"><div class="workflow-card-top"><span class="card-kicker">${event.type === "interview" ? "ONLINE INTERVIEW" : "APPLICATION DEADLINE"}</span>${event.status ? status(event.status) : ""}</div><time class="event-date">${escape(date(event.start, event.type === "interview"))}${event.type === "interview" ? " MYT" : ""}</time><h3>${escape(event.title)}</h3>${event.type === "interview" && event.end ? `<p>Ends ${escape(date(event.end, true))} MYT</p>` : ""}${event.meeting_url ? `<a href="${escape(url(event.meeting_url))}" target="_blank" rel="noopener noreferrer">Open meeting link ↗</a>` : ""}${calendarActions(event)}</article>`,
          )
          .join("")
      : empty(
          "A little breathing room.",
          state.selectedDay
            ? "There are no events for this date. Select another date or show all upcoming events."
            : "Upcoming deadlines and interview sessions will appear here.",
        );
  }
  async function loadCalendar() {
    if (role() === "guest") {
      state.events = [];
      renderCalendar();
      return;
    }
    const generation = state.generation,
      sequence = ++state.calendarSequence;
    try {
      const data = await request("/api/workflow/calendar");
      if (
        generation !== state.generation ||
        sequence !== state.calendarSequence
      )
        return;
      state.events = data.events || [];
      message("calendar-message");
      renderCalendar();
    } catch (error) {
      if (generation === state.generation)
        message("calendar-message", error.message, "error");
    }
  }
  async function loadView(view) {
    if (!state.booted) return;
    if (view === "jobs") await loadJobs();
    if (view === "applications" || view === "applicants" || view === "overview")
      await loadApplications();
    if (view === "profile") {
      if (state.session.user) {
        const generation = state.generation;
        try {
          const profile = await request("/api/workflow/profile");
          if (generation !== state.generation) return;
          state.profile = profile;
        } catch (error) {
          if (generation === state.generation) message("profile-message", error.message, "error");
        }
      }
      if (role() === "hr") await loadVerificationCapabilities();
      renderProfile();
      if (role() === "hr") await Promise.all([loadOwnJobs(), loadModeration()]);
    }
    if (view === "calendar") await loadCalendar();
  }

  document.addEventListener("click", async (event) => {
    if (event.target.closest("[data-verification-fixture]")) {
      const fixture = state.verificationCapabilities?.fixture;
      if (fixture) {
        Object.entries(fixture).forEach(([key, value]) => {
          const input = $(`[name="${key}"]`, $("#company-verification-form"));
          if (input) input.value = value;
        });
        message("verification-message", "Fictional sample filled. Submit to run the simulated registry check, then complete its local domain challenge.", "info");
      }
    }
    if (event.target.closest("[data-fill-challenge]")) {
      const input = $("#verification-challenge-token");
      if (input) input.value = state.profile?.company?.verification?.domain_challenge?.token || "";
    }
    const recheck = event.target.closest("[data-verification-recheck]");
    if (recheck) {
      const generation = state.generation;
      recheck.disabled = true;
      try {
        await request("/api/workflow/company/verification/recheck", { method: "POST", body: "{}" });
        if (generation === state.generation)
          await refreshVerification("Fresh evidence checks requested. Previous approval is reset; inspect the results and complete a new independent review.");
      } catch (error) {
        if (generation === state.generation) message("verification-message", error.message, "error");
      } finally {
        if (generation === state.generation && recheck.isConnected) recheck.disabled = false;
      }
    }
    const chatJob = event.target.closest("[data-chat-job]");
    const chatApplication = event.target.closest("[data-chat-application]");
    if (chatJob || chatApplication) {
      document.dispatchEvent(new CustomEvent("nextstep:open-chat", {
        detail: chatJob ? { job_id: Number(chatJob.dataset.chatJob) } : { application_id: Number(chatApplication.dataset.chatApplication) },
      }));
    }
    if (event.target.closest("#workspace-notifications")) {
      navigate(role() === "hr" ? "applicants" : "applications");
      const feed = $$("[data-notification-feed]").find((item) => !item.closest(".view")?.hidden);
      const details = feed?.querySelector("details");
      if (details) { details.open = true; details.querySelector("summary")?.focus(); }
    }
    if (event.target.closest("[data-read-notifications]"))
      await readNotifications("all");
    const notification = event.target.closest("[data-notification-application]");
    if (notification) {
      const generation = state.generation;
      const notificationView = notification.dataset.notificationView;
      const applicationId = notification.dataset.notificationApplication;
      await readNotifications([Number(notification.dataset.notificationId)]);
      if (generation !== state.generation) return;
      if (notificationView === "messages") navigate("messages");
      else if (notificationView === "moderation") { navigate("profile"); $("#moderator-workspace")?.scrollIntoView({ behavior: "smooth", block: "start" }); }
      else {
        navigate(role() === "hr" ? "applicants" : "applications");
        if (role() === "hr") { $("#applicant-filter").value = "all"; renderApplicants(); }
        const card = $$('[data-application-id]').find((item) => item.dataset.applicationId === applicationId && !item.closest(".view")?.hidden);
        card?.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    }
    if (event.target.closest("[data-refresh-updates]")) await refreshUpdates();
    const open = event.target.closest("[data-open-access], #workspace-signin");
    if (open) {
      event.preventDefault();
      openGate();
    }
    const choice = event.target.closest("[data-choose-role]");
    if (choice) showAuth("register", choice.dataset.chooseRole);
    const authMode = event.target.closest("[data-auth-mode]");
    if (authMode) showAuth(authMode.dataset.authMode, $("#access-role").value);
    const demo = event.target.closest("[data-demo-role]");
    if (demo)
      await authenticate("/api/auth/demo", { role: demo.dataset.demoRole });
    if (event.target.closest("#access-back")) openGate();
    if (event.target.closest("#access-close")) closeGate();
    if (event.target.closest("#access-guest")) await guestEntry();
    if (event.target.closest("#workspace-signout")) await signOut();
    const apply = event.target.closest("[data-apply-job]");
    if (apply) await applyToJob(apply);
    const plan = event.target.closest("[data-plan-role]");
    if (plan) {
      if (bridge()?.selectRole) bridge().selectRole(plan.dataset.planRole);
      else navigate("pathway");
    }
    const withdraw = event.target.closest("[data-withdraw-application]");
    if (withdraw) {
      withdraw.disabled = true;
      await updateApplication(
        withdraw.dataset.withdrawApplication,
        "withdrawn",
        "applications-message",
      );
      if (withdraw.isConnected) withdraw.disabled = false;
    }
    const jobStatus = event.target.closest("[data-job-status]");
    if (jobStatus) {
      const generation = state.generation;
      jobStatus.disabled = true;
      try {
        await request(
          `/api/workflow/jobs/${encodeURIComponent(jobStatus.dataset.jobId)}`,
          {
            method: "PATCH",
            body: JSON.stringify({ status: jobStatus.dataset.jobStatus }),
          },
        );
        if (generation !== state.generation) return;
        message(
          "profile-message",
          `Vacancy ${jobStatus.dataset.jobStatus === "open" ? "opened" : "closed"}.`,
        );
        await loadOwnJobs();
      } catch (error) {
        if (generation === state.generation)
          message("profile-message", error.message, "error");
      } finally {
        if (generation === state.generation && jobStatus.isConnected)
          jobStatus.disabled = false;
      }
    }
    const interview = event.target.closest("[data-interview-action]");
    if (interview) {
      interview.disabled = true;
      await updateInterview(
        interview.dataset.interviewId,
        interview.dataset.interviewAction,
      );
      if (interview.isConnected) interview.disabled = false;
    }
    const move = event.target.closest("[data-calendar-move]");
    if (move) {
      const [year, month] = state.month.split("-").map(Number);
      const next = new Date(
        Date.UTC(year, month - 1 + Number(move.dataset.calendarMove), 1),
      );
      state.month = next.toISOString().slice(0, 7);
      state.selectedDay = null;
      renderCalendar();
    }
    const day = event.target.closest("[data-calendar-day]");
    if (day) {
      state.selectedDay = day.dataset.calendarDay;
      renderCalendar();
    }
    if (event.target.closest("#calendar-today")) {
      state.month = malaysiaToday().slice(0, 7);
      state.selectedDay = malaysiaToday();
      renderCalendar();
    }
    if (event.target.closest("#calendar-show-all")) {
      state.selectedDay = null;
      renderCalendar();
    }
  });
  document.addEventListener("submit", async (event) => {
    const form = event.target;
    if (form.id === "access-form") {
      event.preventDefault();
      if (!form.reportValidity()) return;
      const body = Object.fromEntries(new FormData(form));
      if (state.authMode === "login") {
        delete body.role;
        delete body.display_name;
      }
      await authenticate(
        `/api/auth/${state.authMode === "register" ? "register" : "login"}`,
        body,
      );
    }
    if (form.id === "resume-form") {
      event.preventDefault();
      if (form.reportValidity()) await saveResume(form);
    }
    if (form.id === "company-form") {
      event.preventDefault();
      if (form.reportValidity()) await saveCompany(form);
    }
    if (form.id === "job-create-form") {
      event.preventDefault();
      if (form.reportValidity()) await createJob(form);
    }
    if (form.id === "company-verification-form") {
      event.preventDefault();
      if (form.reportValidity()) await submitVerification(form);
    }
    if (form.matches("[data-moderation-form]")) {
      event.preventDefault();
      syncModerationRequirements(form);
      if (form.reportValidity()) await saveModeration(form);
    }
    if (form.matches("[data-verification-challenge]")) {
      event.preventDefault();
      if (form.reportValidity()) await confirmDomainChallenge(form);
    }
    if (form.matches("[data-salary-form]")) {
      event.preventDefault();
      if (form.reportValidity()) await saveSalary(form);
    }
    if (form.id === "jobs-search-form") {
      event.preventDefault();
      await loadJobs();
    }
    if (form.matches("[data-status-form]")) {
      event.preventDefault();
      if (!form.reportValidity()) return;
      await formAction(form, () =>
        updateApplication(
          form.dataset.statusForm,
          new FormData(form).get("status"),
          "applicants-message",
          String(new FormData(form).get("reason") || ""),
        ),
      );
    }
    if (form.matches("[data-schedule-form]")) {
      event.preventDefault();
      if (form.reportValidity()) await saveInterview(form);
    }
    if (form.id === "global-search-form") {
      event.preventDefault();
      const query = $("#global-search").value.trim();
      if (role() === "hr") {
        $("#applicant-search").value = query;
        $("#applicant-filter").value = "all";
        navigate("applicants");
        renderApplicants();
      } else {
        $("#jobs-search").value = query;
        navigate("jobs");
        await loadJobs();
      }
    }
  });
  document.addEventListener("toggle", (event) => {
    if (event.target.matches("[data-review-application]")) markApplicationViewed(event.target);
  }, true);
  document.addEventListener("input", (event) => {
    const form = event.target.closest("[data-status-form]");
    if (form) rememberDecisionDraft(form);
  });
  document.addEventListener("change", (event) => {
    if (event.target.matches('[data-moderation-form] select[name="status"]'))
      syncModerationRequirements(event.target.closest("form"));
    if (event.target.matches('[data-status-form] select[name="status"]')) {
      const form = event.target.closest("form");
      const required = ["accepted", "rejected"].includes(event.target.value);
      const textarea = $('textarea[name="reason"]', form);
      textarea.required = required;
      $('[data-reason-required]', form).textContent = required ? "*" : "(required for acceptance or rejection)";
      rememberDecisionDraft(form);
    }
    if (event.target.matches("[data-generate-meeting]")) {
      const link = $('input[name="meeting_url"]', event.target.closest("form"));
      link.disabled = event.target.checked;
      link.required = !event.target.checked;
    }
  });
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && state.booted) pollUpdates();
  });
  $("#jobs-search").addEventListener("input", () => {
    clearTimeout(state.searchTimer);
    state.searchTimer = setTimeout(loadJobs, 250);
  });
  $("#jobs-location").addEventListener("input", () => {
    clearTimeout(state.searchTimer);
    state.searchTimer = setTimeout(loadJobs, 250);
  });
  $("#jobs-work-mode").addEventListener("change", loadJobs);
  $("#jobs-sort")?.addEventListener("change", loadJobs);
  $("#applicant-search").addEventListener("input", renderApplicants);
  $("#applicant-filter").addEventListener("change", renderApplicants);
  $("#job-role").addEventListener("change", populateJobRequirements);
  $("#access-gate").addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !$("#access-close").hidden) closeGate();
    if (event.key !== "Tab") return;
    const controls = $$(
      "button:not([disabled]), a[href], input, select",
      $("#access-gate"),
    ).filter((item) => item.getClientRects().length && !item.hidden);
    const first = controls[0],
      last = controls[controls.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last?.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first?.focus();
    }
  });
  document.addEventListener("nextstep:view", (event) => {
    if (state.booted)
      loadView(event.detail.view).catch((error) => notify(error.message));
  });
  document.addEventListener("nextstep:matched", () => {
    if (state.booted && role() === "guest" && currentView() === "jobs")
      loadJobs();
  });
  async function boot() {
    if (state.booted || state.booting || !bridge()?.catalog()) return;
    state.booting = true;
    try {
      const data = await request("/api/auth/session");
      await loadVerificationCapabilities();
      state.booted = true;
      await applySession(data);
    } catch (error) {
      openGate();
      message(
        "access-error",
        `Account options could not load: ${error.message} Reload this page to retry.`,
        "error",
      );
    } finally {
      state.booting = false;
    }
  }
  window.NextStepWorkspace = {
    session: () => ({ ...state.session }),
    openAccess: openGate,
    reload: () => loadView(currentView()),
    refreshApplications: loadApplications,
    refreshUpdates: pollUpdates,
  };
  document.addEventListener("nextstep:ready", boot);
  if (bridge()?.ready?.()) boot();
})();
