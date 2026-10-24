# Multi-role workflow guide

NextStep extends the original future-skills prototype with jobseeker, HR and guest entry choices, plus a separate moderator demo. The recruitment workflow is a **local simulation using synthetic profiles, companies, vacancies and verification evidence**. Public job listings remain a separate source of trend evidence. Applications and messages stay in the local application; no real recruiter or employer is contacted.

## Start and choose a role

Run the commands in [README.md](../README.md), then open the address printed by Flask. Use the entry screen's jobseeker or HR demo button for a seeded synthetic account, or continue as guest. No demo password needs to be copied into the code. Registration creates a separate account; its role is stored and enforced by the server.

New jobseekers are directed to the resume form. Include a fictional display name, headline and selected skills; education, experience, location, interests and weekly learning hours make the profile more useful. New HR accounts complete their company information before publishing jobs. The profile icon returns to the editable resume or company page later.

## Guest demonstration

1. Choose **Continue as guest**. No resume or company onboarding is required.
2. Explore the skills radar. Search a skill or role, inspect the dated source and compare recent versus earlier posting counts.
3. Try a synthetic skills profile and compare career matches, missing skills and moderate/fast adoption assumptions.
4. Open a learning pathway, inspect its resources and SDG rationale, then download the plan.
5. Browse the synthetic job board. The sign-in prompt explains that applying or saving account information requires an account.

Guest exploration does not create a stored resume. Learning progress is browser-local. Guests cannot inspect application records, operate HR controls or change another person's data.

## Jobseeker demonstration

1. Open the jobseeker demo account, or register a separate jobseeker and complete its fictional resume.
2. Open **Find a job**. Search and filter the synthetic vacancies. Best skills fit is the default order; newest is also available. Inspect the salary range, pay period and company review state. Compare the required skills already present in the resume with the missing ones. Expand **Learning plan for this vacancy** for a plan covering that company's exact requirements; **Explore career-role plan** opens the broader occupation pathway.
3. Apply to one open job before its deadline. The server prevents duplicate applications and records the submitted resume version.
4. Open **My applications** using the cart. Inspect the stage, history, response deadline and any decision reason. Editing the current resume does not change the resume snapshot already sent with that application.
5. Use **Contact HR** on a vacancy or the message action on an application to open its private candidate–company conversation. An account is required; guests cannot read private messages.
6. Keep the application view open while a separate HR session acts. Periodic updates bring in changes and unread in-app notifications. Confirm or cancel a scheduled interview in the calendar; an active application can also be withdrawn.
7. Inspect the career assistant's cited occupational evidence, exact source group and mapping caveat. Download the public research report, then compare the separate editable task assumptions. Follow a suggested learning path and retain the exported plan.

The job's **requirements fulfilled** percentage counts selected required skills. The broader **career-fit score** uses weighted skill coverage, TF-IDF interest relevance and sampled market support. Neither score verifies ability or predicts hiring success.

## HR demonstration

1. Open the HR demo account to see a seeded company and synthetic applicant records. For a separate HR account, complete the company form first.
2. Review the company profile. In the default mode, load the fixed **fictional** registry claims and recruiter reference, submit them, then complete the explicit simulated domain-token challenge. An independent moderator must assess registration, domain control and fictional recruiter authorization separately. An HR account cannot approve its own company. See the configuration section below for the optional public-provider boundary.
3. After current checks and approval, create a synthetic vacancy with a title, occupation, description, location, work arrangement, employment type, required skills, deadline and salary minimum/maximum, currency and pay period. Missing salary information or incomplete/expired company checks prevent publication or reopening. Existing seeded vacancies remain browseable; their presence does not imply verified identity.
4. Open **Applicant inbox** using the cart. Search applicants and expand a submitted resume to record the explicit Viewed stage. Inspect requirement coverage, response deadlines and the history. Only the company's applications are accessible.
5. Move an active application to under review or shortlisted, or explicitly accept or reject it. Acceptance and rejection require an explanation visible to the candidate. Decisions are made by the human operating the demo, not by the assistant or match score.
6. Send a candidate a message in the application-linked conversation. Pending applications, unread updates and overdue responses are visible in the role-aware cart.
7. Schedule an online interview with a future date/time, duration and an HTTPS meeting link. Alternatively, generate a unique Jitsi link. The app stores the schedule and notifies the candidate inside the prototype; it does not provision a guaranteed video room or email an invitation.
8. Open the calendar, inspect interviews and job deadlines, and download the `.ics` calendar file. Close a vacancy when it should stop accepting applications.

Accepted, rejected and withdrawn applications are terminal in this demo. Rejection and withdrawal cancel active interview records. Active interview schedules can be changed through the HR scheduling action; applicants can respond to their own interview invitations.

The application response SLA is an app-level target. An overdue item is flagged/escalated in the prototype and affects the transparent employer accountability calculation; it does not force an employer to respond. Compliance incidents and score deductions must be interpreted using the explanation shown by the app, not as an independently assessed employer reputation.

## Moderator demonstration

1. In a separate browser profile, choose the **moderator demo**. This opens a seeded synthetic account with moderator permission; public account registration does not grant that permission.
2. Open the moderation area in the profile page. Inspect a pending company's structured claims, registry match, domain result, evidence dates and limitations. An unavailable, mismatched or expired result cannot be approved.
3. Independently assess the fictional recruiter's authorization. Explicitly confirm registration, domain control and authorization, provide an HTTPS authorization reference on the claimed company domain and a review note, then approve with a reason. The note must describe the evidence reviewed; repeating an employer's assertion is not independent proof. Reject incomplete evidence with a reason.
4. Verify that the dated review state, expiry and explanation appear for HR and that job cards identify the synthetic result. Revoke an approval with a reason to demonstrate withdrawal of publishing permission. A second company account claiming the same currently approved legal entity is blocked until the earlier approval is revoked.
5. Confirm that ordinary HR cannot call the moderation API, that moderators cannot approve their own company, and that company-profile changes invalidate the active checks. Earlier text-only approvals require the new checks; migration retains accounts, jobs and histories.

The review demonstrates a workflow, not real identity verification. Default-mode badges say **Synthetic checks complete**. Public-provider results describe registry/domain checks and a demo authorization review, not a verified real recruiter. Do not enter identity cards, passports, personal CVs or real recruiter email addresses.

## Employer-check configuration

The default requires no external provider. Configure these server environment variables before startup:

| Variable | Default | Effect |
| --- | --- | --- |
| `NEXTSTEP_VERIFICATION_MODE` | `synthetic` | `synthetic` uses fixed fictional registry data and a simulated challenge; `gleif` enables public GLEIF and DNS requests |
| `NEXTSTEP_VERIFICATION_TTL_DAYS` | `30` | Evidence/approval lifetime, bounded to 1–90 days |
| `NEXTSTEP_DOMAIN_CHALLENGE_MINUTES` | `30` | Token validity before challenge completion, bounded to 1–60 minutes |
| `NEXTSTEP_REQUIRE_VERIFIED_EMPLOYERS` | `1` | Require current registry, domain and moderator checks before publishing/reopening; `0` disables that gate for an explicitly configured local experiment |
| `NEXTSTEP_MODERATOR_USER_IDS` | empty | Comma-separated existing user IDs trusted by the server operator; email addresses and invalid IDs are rejected |

Keep the hackathon demo in `synthetic` mode. The capabilities endpoint supplies the fixed fixture: Verdant Labs (Demo), country `MY`, registration `SYNTHETIC-REG-2026-01`, LEI `SYNTHETIC00000000001`, domain `verdant.example.invalid` and fictional recruiter `hr@verdant.example.invalid`. Exact claims are compared with the fixture; invented free-text claims do not establish a match. A fresh token is generated at `_nextstep-verification.<domain>`; entering that token explicitly completes the **simulated** DNS check. No email is sent.

In explicitly configured `gleif` mode, the provider performs an exact LEI lookup against the public GLEIF registry, compares structured entity fields/status, and queries Google Public DNS over HTTPS for the exact token at the claimed domain. Use only a domain whose owner authorized the DNS change. There is no arbitrary URL/document fetch and no fallback from unavailable public evidence to approval. GLEIF is not Malaysia's SSM company register; entities without an LEI cannot match this provider. DNS demonstrates domain control, not mailbox access, personal identity, employment or recruiter authorization. Both modes accept **fictional recruiter references ending in `.invalid` only**, and a separate moderator must document the authorization assessment. No email, personal identity proof or external recruitment outreach is supported.

The shared moderator demo is disabled in `gleif` mode, and an existing demo moderator session loses its privilege unless its ID is explicitly trusted by the operator. Configure a trusted existing account with `NEXTSTEP_MODERATOR_USER_IDS` before startup; registration cannot grant moderation access. Public registry and DNS checks have a persistent 30-second per-company/provider-check cooldown. Late responses cannot overwrite a newer company profile or review. Free-text review reasons stay visible only to the company owner and moderators; public cards expose a limited legal-record source summary instead.

Registry rechecking resets approval to pending. Evidence expiry, revocation, a changed company profile or a provider-mode change prevents active approval from being reused. Registry/domain results and review events retain dated snapshots/digests; a digest helps detect changes but does not certify the truth of a claim. Existing jobs remain browseable, while publishing or reopening is gated by current checks. Conflicting current approvals for the same LEI or country/registration number are blocked; an independent moderator must revoke the previous approval before a transfer.

GLEIF's live request was blocked by the workspace egress proxy. Local fixtures and mocked provider tests exercise the code path without establishing a successfully live-verified company. Do not demonstrate a synthetic result as a real registry or SSM check. Public-provider availability must be checked separately in an authorized deployment.

## Demonstrate a complete shared lifecycle

Use separate browser profiles or an incognito window to keep simultaneous jobseeker and HR sessions separate. Alternatively, sign out and change roles in one browser.

1. As the jobseeker demo, apply to a vacancy owned by the HR demo company.
2. As the matching HR demo, open that application's resume. Verify its Viewed stage, send a message and schedule an interview.
3. Return to the jobseeker demo. Verify the message, notification, timeline and matching calendar event, then confirm the interview and reply.
4. Return to HR and verify the confirmation and reply. Reschedule or cancel an active interview and verify the changed state on both sides.
5. Make a final decision with an explanation. Verify that the candidate sees the same reason and event history, and that the pending count changes.

To check isolation, register two separate HR accounts and create a different company/job for each. Each inbox should contain only its own company's applications. A registered jobseeker should see only their own application records. The demo buttons intentionally reopen shared synthetic demo accounts; use registered accounts when checking account isolation.

## Calendar, assistant and evidence boundaries

The workspace presents schedule times in **Asia/Kuala_Lumpur**. Interview inputs are sent with an explicit timezone/offset and stored consistently; the calendar export allows importing the saved schedule into another calendar application. Exporting does not send an invitation. Check the displayed date/time after import, especially on a device configured for another timezone.

The assistant's default mode is a source-grounded guide. It explains skill gaps, suggests catalogue roles, points to learning resources and directs users to relevant workspace views. HR guidance opens workflows; it does not accept or reject a person. Optional model-assisted question classification requires a configured server and explicit user opt-in; answers remain bounded to the cited engine. Check [AI_DISCLOSURE.md](AI_DISCLOSURE.md) before enabling it.

Published ILO 2025 exposure means appear with their source occupation, date, mapping, scope and limitations. Six catalogue roles use broader occupational proxies; BI and project management show unavailable evidence. The primary score is technical potential on a 0–100 scale, not a fraction of jobs/tasks replaced. Historical Frey–Osborne 2013 probabilities are shown separately for supported historical counterparts/suboccupations; the two developer subgroups stay separate. The editable six-task calculator is an authored planning exercise. Changing its assumptions or the scenario does not change the published research. [EVIDENCE.md](EVIDENCE.md) supplies the exact values and source/license provenance. Downloaded research reports contain public evidence, not account profiles or conversations.

The public-source monitor runs automatically after startup, then every 900 seconds by default. `NEXTSTEP_AUTO_REFRESH=0` or `python app.py --no-monitor` disables scheduling. `NEXTSTEP_REFRESH_SECONDS` accepts 300–86,400 seconds. Use the monitor state to distinguish scheduled, paused, cached and failed-refresh states; do not label an old snapshot as live. The browser checks for changed evidence and recalculates matches when a new content revision is available.

The six Domain 1 capabilities remain central: skills intake, updatable evidence, explainable matching, reskilling pathways, SDG mappings and multiple scenarios. The international graduate-job sample is not representative Malaysian labour-market data. Course hours describe introductory study budgets; ticking a completed step does not establish proficiency.

## Backend and interface map

| Endpoint family | Purpose |
| --- | --- |
| `/api/auth/session` | Current account/role and session CSRF token |
| `/api/auth/register`, `/login`, `/demo`, `/logout` | Account and session actions under `/api/auth` |
| `/api/workflow/profile` | Read/edit the signed-in resume or company |
| `/api/workflow/jobs` | Browse synthetic jobs; HR publishes owned jobs |
| `/api/workflow/verification/capabilities` | Current provider mode, synthetic fixture, publishing gate and limits |
| `/api/workflow/company/verification` | Submit structured company claims; capture registry result and create domain challenge |
| `/api/workflow/company/verification/challenge`, `/recheck` | Check the current domain token or recheck the registry under the verification path |
| `/api/workflow/moderation` | Permitted moderator's evidence queue and review actions |
| `/api/workflow/applications` | Submit, list and update scoped applications |
| `/api/workflow/applications/<id>/viewed` | Explicit HR resume-view action and history event |
| `/api/workflow/applications/<id>/interview` | HR schedules or reschedules an interview |
| `/api/workflow/interviews/<id>` | Scoped interview responses/cancellation |
| `/api/workflow/updates`, `/notifications/read` | Scoped notification polling/read state under `/api/workflow` |
| `/api/messages/threads` | Scoped candidate–company conversations, messages and read state |
| `/api/workflow/calendar`, `/calendar.ics` | Scoped events and calendar export under `/api/workflow` |
| `/api/assistant`, `/api/exposure` | Evidence-backed replies, published research and a separate authored task assessment |
| `/api/exposure/evidence`, `/methodology`, `/report/<role_id>` | Public role evidence, research method and downloadable JSON report under `/api/exposure` |
| `/api/monitor/status`, `/api/monitor/discoveries` | Monitor state and exact observed source titles |
| `/api/catalog`, `/api/radar`, `/api/match` | Existing catalogue, dated evidence and career matching |

Use the role returned by the backend rather than trusting a client-selected role. Account/workflow mutations include the session's `X-CSRF-Token` header. The server also checks ownership and input values; hiding a button is not an authorization boundary. Job applications store a submitted resume snapshot, so HR can review a stable version.

The original home, radar and learning views live in `templates/index.html` and `static/app.js`. Role entry lives in `templates/access.html`; job search, application carts, profile forms and calendar live in `templates/workflow.html` and `static/workflow.js`. Conversations live in `templates/messages.html`, `static/messages.js` and `career/communication.py`. The corresponding CSS files extend the existing visual style. Backend account/application logic lives in `career/workflow.py`; bounded registry/DNS adapters live in `career/verification.py`; assistant logic lives in `career/assistant.py`; published occupational research is isolated in `career/exposure.py` and `data/exposure_evidence.json`.

Local SQLite and the signing key are retained under ignored `instance/`. Restarting the server should preserve the workflow. Before any deliberate reset, stop only the server you started and back up the database and signing key. Do not delete persistent state as a routine troubleshooting step. Keep all demo information synthetic.
