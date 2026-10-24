/* REFERENCE EXTRACT ONLY: these functions normally run inside workflow.js
   and use its shared state/helpers and the NextStep bridge. Do not load
   this file alongside the original script or use it as a replacement. */
"use strict";

// Source: static/workflow.js:183
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

// Source: static/workflow.js:215
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

// Source: static/workflow.js:534
function skillPicker(container, selected = []) {
  const values = new Set(selected);
  $(container).innerHTML = (bridge()?.catalog()?.skills || [])
    .map(
      (skill) =>
        `<label class="skill-checkbox"><input type="checkbox" value="${escape(skill.id)}"${values.has(skill.id) ? " checked" : ""}><span title="${escape(skill.description)}">${escape(skill.name)}</span></label>`,
    )
    .join("");
}

// Source: static/workflow.js:543
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

// Source: static/workflow.js:605
function nextDate(value) {
  const parsed = new Date(`${value}T00:00:00Z`);
  parsed.setUTCDate(parsed.getUTCDate() + 1);
  return parsed.toISOString().slice(0, 10);
}

// Source: static/workflow.js:610
function populateJobRequirements() {
  const selected = (bridge()?.catalog()?.roles || []).find(
    (item) => item.id === $("#job-role").value,
  );
  skillPicker(
    "#job-required-skills",
    selected?.skills.map((item) => item.id) || [],
  );
}

// Source: static/workflow.js:684
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

// Source: static/workflow.js:727
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

// Source: static/workflow.js:802
function salaryFields(job = {}) {
  const prefix = `salary-${job.id || "edit"}`;
  return `<div class="workflow-form-grid"><div><label class="field-label" for="${prefix}-min">Minimum *</label><input id="${prefix}-min" type="number" name="salary_min" min="0.01" max="1000000000" step="0.01" required value="${escape(job.salary_min ?? job.salary?.minimum ?? "")}"></div><div><label class="field-label" for="${prefix}-max">Maximum *</label><input id="${prefix}-max" type="number" name="salary_max" min="0.01" max="1000000000" step="0.01" required value="${escape(job.salary_max ?? job.salary?.maximum ?? "")}"></div><div><label class="field-label" for="${prefix}-currency">Currency</label><select id="${prefix}-currency" name="salary_currency">${["MYR", "USD", "SGD", "GBP", "EUR", "AUD"].map((currency) => `<option${currency === (job.salary_currency || job.salary?.currency) ? " selected" : ""}>${currency}</option>`).join("")}</select></div><div><label class="field-label" for="${prefix}-period">Period</label><select id="${prefix}-period" name="salary_period">${["month", "year", "hour"].map((period) => `<option value="${period}"${period === (job.salary_period || job.salary?.period) ? " selected" : ""}>Per ${period}</option>`).join("")}</select></div></div>`;
}

// Source: static/workflow.js:971
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

// Source: static/workflow.js:836
function publishingAllowed() {
  return state.verificationCapabilities?.publishing_requires_verification === false ||
    (state.profile?.company?.verification?.can_publish === true &&
     effectiveVerificationStatus(state.profile.company.verification) === "verified");
}

// Source: static/workflow.js:841
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

// Source: static/workflow.js:1007
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

// Source: static/workflow.js:1035
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

// Source: static/workflow.js:1069
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
