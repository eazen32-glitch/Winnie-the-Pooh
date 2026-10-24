# Requirements completion map

This map separates the official Domain 1 brief, the team's discussion, and the additional job-platform problems in the supplied picture. It describes a hackathon proof of concept using synthetic people, companies, applications and employer-review evidence. Test results belong in [VALIDATION.md](VALIDATION.md).

**NextStep** is the prototype's working name, proposed during AI-assisted development. It is not a name required by the handbook or domain brief. The team can rename it.

## Official Domain 1 requirements

The six must-haves are on printed page 4. For the preliminary round, the proposal explains how all six will be delivered and the live demo proves the most important feature. Pages 6–7 identify trend signals feeding role matching as a typical central demonstration.

| Requirement | Prototype implementation | Interpretation and limit |
| --- | --- | --- |
| Skills intake | Resume/skills form, interests, weekly learning budget and sample profiles | A form is explicitly acceptable; a CV parser is not mandatory. Use fictional data. |
| Updatable trend layer | Dated public job and AI-release sources, refresh, cached fallback and scheduled monitoring | Source activity is sampled evidence, not a complete labour-market census. Cached data is labelled. |
| Explainable future-role matching | Ranked, source-backed catalogue roles, score components, skills coverage and gaps | Scores support a decision; they are not hiring probabilities or validated forecasts. |
| Personalised reskilling | Ordered missing skills and prerequisites, real learning links, estimated hours/weeks | Introductory study estimates do not certify skill mastery or employability. |
| SDG mapping | Every catalogue role and skill has SDG tags, with career-contribution explanations | Potential contribution is editorial, not measured impact or UN endorsement. |
| Uncertainty | Moderate/fast assumptions and visible limits | Scenario differences are sensitivity assumptions, not calibrated predictions. |

Observed source titles and their source links can inform exploration beyond the curated recommendation catalogue. They must not be described as newly predicted occupations. A working data pipeline does not establish forecasting accuracy.

## Team discussion

| Requested journey | Implementation |
| --- | --- |
| Jobseeker / HR / guest entry | Role entry, registered accounts, synthetic demo accounts and direct guest exploration |
| Different onboarding | Resume form for jobseekers; company form for HR; no guest onboarding |
| Shared workspace | Search, trends, role-aware cart, editable profile, calendar, messages and assistant |
| Find a job | Skills-first vacancy ordering, filters, salary ranges, skills coverage, missing skills and vacancy-specific learning plans |
| Plan a future | Ranked career roles, scenario comparison and prerequisite-aware learning pathways |
| Jobseeker cart | Own applied companies/jobs, application stages, reasons, response deadline, history, interview details and withdrawal |
| HR cart | Owned-company pending applicants, saved resume snapshots, review/shortlist/decision actions and interview scheduling |
| Interviews | Malaysia-time scheduling, conflict checks, supplied or generated meeting links, in-app updates and calendar export |
| AI assistant | Guided evidence-backed mode available without a key; optional model-assisted intent classification only when configured and explicitly opted into |
| Occupational AI evidence and requested replacement percentage | Published ILO 2025 technical-exposure mean on a 0–100 scale, six explicit broader occupational proxies and two unavailable mappings; separate four historical 2013 full-computerisation probabilities across three catalogue roles; cited research export. A current validated job-replacement probability is not available. |

Skills coverage, career-fit scores, published exposure, historical computerisation probabilities and editable task assumptions measure different things. None predicts whether an individual will receive an offer or lose a job. The [research evidence guide](EVIDENCE.md) records the exact source titles/codes, values, dates, mapping caveats, scope and license. ILO task SD is dispersion across tasks, not a confidence interval. Scenarios and user-edited assumptions do not change source values. BI and project management remain unavailable; the historical software suboccupations are never averaged.

## The five problems in the picture

| Problem | Added workflow | Honest boundary |
| --- | --- | --- |
| Salary transparency | Required salary minimum/maximum, currency and pay period; validation and visible company compliance/accountability | Demo ranges are illustrative. Compliance is an app rule, not a legal certification or external employer rating. |
| Trust and safety | Structured legal-entity claims; registry match; domain challenge; independent moderator authorization review; dated evidence snapshots, expiry/revocation, conflicting-entity checks and publishing/reopening gate | Default mode is a fixed fictional registry and simulated DNS. Optional GLEIF/DNS mode checks public LEI records and domain control, not SSM, identity or employment. Recruiter references remain fictional. GLEIF access was blocked here; no successful live verification is claimed. |
| Search fatigue | Vacancy ranking uses the current selected/resume skills by default; users can choose newest instead; missing skills and reasons remain visible | Self-declared skills have not been independently assessed. Career-role matching is a separate explained formula. |
| Contacting employers | Application/job-linked candidate–HR conversations, scoped access, unread indicators and in-app messages | Messages remain inside this local prototype. No real recruiter or external service is contacted. |
| Lack of feedback | Explicit Viewed action, review/decision states, mandatory decision reasons, event history, response deadline, overdue/escalation state and periodic updates | Live changes are polled while the page is open. There is no guaranteed external push/email delivery or enforced employer response. |

## Submission and research work remain human work

The handbook still requires a functional interface, working prototype and live pitch (printed page 15). Judge access to the team's private repository, current submission format, team review/adaptation and the ability to explain the major components cannot be completed by application code alone.

Domain 1 page 5 requires public/open/synthetic data and excludes real recruitment integrations. Demonstrate with fictional resumes and employer evidence. Do not collect real identity documents for a synthetic verification demo.

The public-registry adapter is an optional public-evidence capability, not a real recruitment integration. Keep the hackathon's default `NEXTSTEP_VERIFICATION_MODE=synthetic`. Even in explicitly configured GLEIF mode, only public company records, an authorized domain-control challenge and fictional recruiter references are supported; there is no personal identity or employment proof and no outreach. See [WORKFLOWS.md](WORKFLOWS.md#employer-check-configuration) for configuration and limits.

The handbook permits AI assistance but requires the team's own understanding, decisions and review/adaptation (§8.5). Keep [AI_DISCLOSURE.md](AI_DISCLOSURE.md) accurate, including the exact runtime model if the optional model integration is enabled.

The prototype does not claim production readiness, validated Malaysian labour-market forecasts, real identity verification, measured fairness, guaranteed course outcomes or an independently validated job-replacement probability. Protected demographic fields are not matching inputs; regression guardrails for that boundary are not a fairness evaluation. Historical published model probabilities do not establish present predictive accuracy. Those outcomes need suitable data, evaluation and operational services; adding a label or generating a number cannot establish them.
