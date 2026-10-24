/* REFERENCE ONLY. Wrappers expose fragments of existing listeners;
   these are not additional listeners to register in the app. */
"use strict";

// Source: static/workflow.js:1683
async function handleVacancyStatusExcerpt(event) {
  const form = event.target;
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
}

// Source: static/workflow.js:1766
async function handleVacancySubmitExcerpt(event) {
  const form = event.target;
    if (form.id === "job-create-form") {
      event.preventDefault();
      if (form.reportValidity()) await createJob(form);
    }
}

// Source: static/workflow.js:1783
async function handleSalarySubmitExcerpt(event) {
  const form = event.target;
    if (form.matches("[data-salary-form]")) {
      event.preventDefault();
      if (form.reportValidity()) await saveSalary(form);
    }
}

// Source: static/workflow.js:1861
function registerRoleChangeExcerpt() {
  $("#job-role").addEventListener("change", populateJobRequirements);
}
