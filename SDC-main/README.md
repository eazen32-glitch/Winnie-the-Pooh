# NextStep · Future-ready careers

A Python + HTML prototype for **SDC Hackathon 2026, Domain 1: The Aiversecity Future-Ready Workforce**. Start with a synthetic skills profile, inspect dated public evidence, compare explainable career matches and follow an SDG-linked learning plan. The same application includes jobseeker, HR and guest journeys with a synthetic recruitment workflow.

## Run it

Requires Python 3.10 or newer. No API keys, Node.js, external database or paid services are required for the default application. The optional model-backed assistant needs separately configured credentials and user opt-in. The dependencies include timezone data so the Malaysia-time calendar also works on systems without an installed IANA timezone database.

```bash
cd /workspace/SDC
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python app.py
```

Open the local address printed by Flask in your browser. If you download the project to your computer, replace `/workspace/SDC` with the extracted project folder. On Windows, activate with `.venv\Scripts\activate` instead of `source .venv/bin/activate`.

The server binds to your computer's loopback interface with debug mode disabled. For a hosted development environment, use `python app.py --host 0.0.0.0 --port 5000` and your platform's supported port access. This is a hackathon development server, not a production deployment.

On the entry screen, choose **jobseeker**, **HR**, or **Continue as guest**. The demo buttons open seeded synthetic accounts without needing credentials. You can also register a separate account or sign in to an account you created. New jobseekers complete a resume form; new HR accounts complete their company form. Use fictional names and information throughout this hackathon demo.

### Refresh the public evidence

```bash
python app.py --refresh
```

The interface also has a refresh button. Manual refreshes are limited to once per five minutes in the running server. Sources may return identical records; refresh does not guarantee a changed recommendation. The included, genuinely fetched **22 October 2026 UTC** snapshot supports an offline demonstration, labelled cached. Later refreshes are saved to ignored `instance/signals.json`; a restart reads that cache before the bundled snapshot.

Scheduled monitoring refreshes the public feeds in the background, without blocking startup. It retains the last usable cache when a source fails. The monitor reports its enabled/running state and next refresh; observed source titles remain distinct from the curated role catalogue. See [the workflow guide](docs/WORKFLOWS.md) for monitor controls. Monitoring does not turn sampled observations into validated forecasts.

Monitoring is enabled by default, checks after startup, and then runs every 900 seconds. Set `NEXTSTEP_AUTO_REFRESH=0` or run `python app.py --no-monitor` for an offline/manual-only demo. `NEXTSTEP_REFRESH_SECONDS` accepts intervals from 300 to 86,400 seconds. The browser detects a changed evidence revision and refreshes its matches without pretending that every fetch changes the data.

### Optional model-assisted questions

The guided assistant works without credentials. To let a language model classify a free-text question into a supported career/workflow intent, configure `NEXTSTEP_ENABLE_LLM=1`, `NEXTSTEP_OPENAI_API_KEY` and `NEXTSTEP_OPENAI_MODEL` on the server. Keep the key outside source control. The interface additionally requires explicit consent before sending the question, public role names/IDs and the supported intent schema to OpenAI. Saved resumes are not included; answers still come from the bounded, cited recommendation engine. Model intent classification does not add general-purpose generated career advice. See [AI_DISCLOSURE.md](docs/AI_DISCLOSURE.md).

## Features

| Domain requirement | Working implementation |
| --- | --- |
| Skills profile intake | Editable skill selection, interests and weekly learning time; three synthetic profiles |
| Updatable trend layer | Public job-listing JSON and official AI release feed, timestamps, evidence links, recent/previous 30-day comparisons, scheduled refresh and cached fallback |
| Explainable matching | Eight source-backed roles ranked using skills coverage, lexical interest relevance and sampled market support; explicit missing skills |
| Personalised pathway | Ordered skill gaps and prerequisites, real free learning links, estimated hours and weeks |
| SDG mapping | Every role and skill mapped to relevant goals; all 17 goals in the reference catalogue |
| Uncertainty | Moderate and fast AI-adoption assumptions with comparable scores and visible caveats |

The account and application features extend that core journey:

| Journey | Features |
| --- | --- |
| Guest | Explore trends, synthetic jobs, role matches, skills gaps and sample learning plans without an account |
| Jobseeker | Edit a synthetic resume, browse skills-ranked vacancies with salary ranges, contact HR, apply once per job, inspect application history/reasons/deadlines, withdraw and respond to interviews |
| HR | Edit company details, submit structured registry claims, complete a domain challenge, publish after current checks, message candidates, explain decisions and schedule interviews |
| Moderator | Review registry/domain results and fictional recruiter authorization separately; approve, reject or revoke with a reason; self-approval is blocked |
| Shared workspace | Search, dated trends, role-aware application cart, profile access, calendar, scoped messages, in-app updates and source-grounded career assistant |
| Learning | Prerequisite-aware plans, SDG explanations, browser-local progress and downloadable plans |

The job board contains **synthetic vacancies and companies**, distinct from the public listings used as trend evidence. Applying and messaging change only this local demo. HR can supply a meeting URL or generate a unique Jitsi link; a generated link is not a provisioned or guaranteed video session. In-app notifications and calendar export do not send email invitations. See [the role-by-role workflow guide](docs/WORKFLOWS.md) for the full demo.

Salary bounds are required when publishing a job. By default, employer checks use a **fixed fictional registry record, a simulated domain challenge and a separate moderator review**. Current registry/domain results and moderator approval are required to publish or reopen a vacancy. Approval expires; revocation, profile changes and conflicting legal-entity claims block reuse. Existing vacancies remain browseable. Response deadlines, overdue applications and compliance incidents support an app accountability score, not a legal employer rating or guaranteed reply.

The optional `NEXTSTEP_VERIFICATION_MODE=gleif` adapter queries public GLEIF legal-entity records and DNS TXT records. GLEIF is not Malaysia's SSM register; domain control does not establish a recruiter's identity or employment. Both modes require fictional recruiter references ending in `.invalid`, a documented independent moderator review and no personal identity documents. The public-provider request was blocked by this environment's proxy, so this build does not claim a successfully live-verified employer. The default stays synthetic; no email or external recruitment action is sent. See [the verification guide](docs/WORKFLOWS.md#employer-check-configuration).

Guest matching requests are processed in memory. Signed-in synthetic resumes, company profiles, jobs, applications, histories, conversations and interviews are stored in local SQLite; submitted applications keep a snapshot of the resume version used. Learning progress stays in the current browser. No real CV upload is needed.

## How matching works

```text
fit = 0.65 × weighted skill coverage
    + 0.20 × TF-IDF interest relevance
    + 0.15 × source-sample support
```

The TF-IDF cosine baseline compares interests to curated role descriptions. It is lexical information retrieval, not a generative model or an assessment of a person's potential. Role skill weights are editorial; current evidence and scenario assumptions adjust skill priorities. Scores are not hiring probabilities. The app does not automatically make employment or hiring decisions; HR status changes are explicit human actions in the demo.

**Job requirements fulfilled** is a separate calculation: the number of required skills selected in the resume divided by the job's total required skills. It is not the career-fit formula above, a professional qualification check or a probability of receiving an offer. HR sees the match against the submitted resume snapshot, so later profile edits do not rewrite an existing application.

Each vacancy also has its own expandable learning plan based on that company's actual missing requirements and their prerequisites. The broader career-role plan is available separately, since its curated skill list may differ from an employer's vacancy.

The assistant uses guided intents, the existing matching engine and cited resources by default. An optional server-configured language model helps classify questions into supported intents after explicit user opt-in; answers remain bounded to the same cited engine. The application works without it.

Occupational AI evidence now comes from the **ILO–NASK 2025 GenAI exposure study**, with exact source values, dates, occupation codes, mapping caveats and a downloadable research report. Six catalogue roles have explicit broader occupational proxies; Business Intelligence Analyst and Project Management Specialist have no defensible mapping and show unavailable evidence. The published 0–1 mean is displayed on a 0–100 scale: it measures technical potential, **not the percentage of jobs or tasks replaced**. Scenario choices and editable task assumptions do not change that published score. A separate historical table preserves four Frey–Osborne **2013 modelled computerisation probabilities**, including distinct applications/system-software suboccupations; those are not current GenAI job-loss forecasts. [EVIDENCE.md](docs/EVIDENCE.md) explains the values, limitations and attribution. Any editable task calculator remains an illustrative planning exercise. See [AI_DISCLOSURE.md](docs/AI_DISCLOSURE.md) for the model/data-flow boundary.

Market support combines direct occupation-title matches and mentions of relevant skills in the source sample. Role, skill and curriculum mappings are curated, with original occupation and resource links. The baseline never generates new job titles, courses or employment statistics. Learning hours budget introductory study, not skill mastery or job readiness. They are our estimates, not provider-certified course durations; some free resources require an account, and optional cloud/model exercises may cost money. A fixed role's pathway follows curated prerequisite order; scenarios adjust scoring priorities rather than that order.

## Data and limits

- **Jobs:** [Simplify / Coder Quad New-Grad Positions](https://github.com/SimplifyJobs/New-Grad-Positions), via [public dated listings](https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/.github/scripts/listings.json). Only minimal factual metadata is retained. The sample mainly covers US/Canada/remote technical graduate roles and includes inactive historical postings. It is **not representative Malaysian workforce data**. Respect the original source's terms and attribution.
- **AI advancements:** [Hugging Face Transformers releases](https://github.com/huggingface/transformers/releases.atom). Release activity is technology evidence, not an employer-demand count.
- **Occupations:** [O*NET OnLine](https://www.onetonline.org/), linked per role. O*NET is a US occupation reference, not a Malaysian labour forecast.
- **GenAI exposure:** [Gmyrek et al., ILO Working Paper 140 (May 2025)](https://doi.org/10.54394/HETP0387), via the [first-author dataset](https://github.com/pgmyrek/2025_GenAI_scores_ISCO08), CC BY 4.0, accessed 23 October 2026. The bundled factual extract identifies its pinned workbook, checksum and source rows; role mappings and scale conversion are our adaptations. Source SD measures differences among tasks, not statistical confidence.
- **Historical computerisation probabilities:** Frey and Osborne's 17 September 2013 working paper, factual appendix values obtained through a pinned public mirror. Official Oxford retrieval was blocked and byte equality with its current file was not established. No full paper is distributed in this project; see [source provenance](docs/EVIDENCE.md).
- **Learning:** provider links include Microsoft, Kaggle, IBM SkillsBuild, Khan Academy and UN SDG:Learn. These are cited resources, not sponsored recommendations.
- **SDGs:** [United Nations Sustainable Development Goals](https://sdgs.un.org/goals). The mappings express potential contribution, not measured impact or UN endorsement.

Trend labels compare keyword-matched posting counts in equal dated windows, with a minimum observation threshold. They describe this sample. Changing feed coverage, hiring seasons and missing terms can distort apparent momentum. An absent skill mention is not evidence of obsolescence. Scenarios are transparent sensitivity assumptions, not validated forecasts. New snapshot data can change both match scores and priorities; automated tests verify that sensitivity, not forecast accuracy.

## Local storage

The application creates these ignored files under `instance/` as needed:

- `workflow.sqlite3`: accounts, password hashes, synthetic profiles, jobs, verification reviews, application histories, notifications, messages and interviews. SQLite is included with Python; no database server is needed.
- `session-secret`: the local signing key for cookie-based sessions. Keep it private and retain it across restarts so existing sessions remain usable.
- `signals.json`: the latest successfully saved public evidence cache.

Registration stores password hashes, not plaintext passwords. Roles and company ownership are checked by the backend; changing a navigation item does not grant HR permissions. Account and workflow mutations require the session's CSRF token. Public demo accounts are deliberately accessible through the demo buttons and should hold synthetic data only. Separate registered accounts have their own profiles and access scopes.

Startup adds the new schema without replacing existing work. Existing vacancies missing salary information are withheld until corrected; demo salaries are explicitly illustrative. Back up local data before an upgrade or intentional reset. Do not remove the database or signing key merely to restart the app. The bundled `data/signals_seed.json` is a public-data fallback, separate from private local account state.

## Tests

```bash
python -m pytest -q
python -m pip check
```

Tests use local synthetic fixtures, with no internet required. They cover source ingestion/cache failures, matching and pathway constraints, account/workflow validation, permissions and the application/interview lifecycle. Use the manual journeys in [WORKFLOWS.md](docs/WORKFLOWS.md) to check the browser integration; actual validation results are recorded separately in [VALIDATION.md](docs/VALIDATION.md).

## Project files

```text
app.py                       Flask routes, validation and security headers
career/catalog.py            Skills, occupations, courses, SDGs and demo profiles
career/sources.py            Bounded public-feed refresh and dated caching
career/recommendations.py    TF-IDF, scoring, scenarios and learning pathways
career/workflow.py           Accounts, salary/compliance, employer review, applications and SLA
career/communication.py      Scoped candidate–HR conversations and read state
career/monitor.py            Scheduled public-source refresh and observed discoveries
career/assistant.py          Source-backed replies and separate task-planning exercise
career/exposure.py           Published exposure/probability evidence and explicit mappings
career/verification.py       Fixed synthetic or public GLEIF/DNS evidence adapters
templates/index.html         HTML interface
templates/access.html        Role choice, registration and sign-in
templates/workflow.html      Jobs, applications, profile and calendar views
templates/assistant.html     Career-assistant panel
templates/messages.html      Candidate–HR conversation view
static/styles.css            Responsive styling
static/app.js                Search, API interactions, progress and export
static/workflow.*            Multi-role forms, navigation and workflow styling
static/assistant.*           Assistant interactions and styling
static/messages.*            Scoped conversation interface and styling
data/signals_seed.json       Dated public-source fallback snapshot
data/exposure_evidence.json  Cited occupational research extract, mappings and attribution
tests/                       Source, matching, account and workflow tests
docs/                        Preliminary proposal, research and AI disclosure
```

See [the requirements completion map](docs/REQUIREMENTS_AUDIT.md), [preliminary proposal and demo script](docs/PRELIMINARY.md), [researched feature priorities](docs/FEATURE_RESEARCH.md) and [AI-assistance disclosure](docs/AI_DISCLOSURE.md). The supplied documents do not give exact proposal length or pitch duration; use the organizers' latest submission instructions. A working codebase does not replace the required live pitch, accessible GitHub link, team review or original problem understanding.
