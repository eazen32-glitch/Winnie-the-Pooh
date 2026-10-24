# AI and external-resource disclosure

This is a draft for the team to review and adapt before submission. It does not establish competition eligibility or replace the organizers' rules.

## Development assistance

**ChatGPT/Codex** assisted with interpreting the supplied briefs, researching public sources, generating Python/HTML/CSS/JavaScript code and documentation, and proposing checks. The team's final submission should identify what it kept, changed and independently reviewed. Do not claim the work was written entirely without AI assistance.

The handbook permits AI development assistance but expects the team's own problem understanding, solution design and technical decisions (printed pages 18–19). It also says teams must review/adapt generated work and be able to explain substantial components; submitting substantially generated material without that understanding can affect originality assessment. The generated prototype is a starting point for that work, not proof that the rule has been met.

This draft assumes all substantial **human** contributors are registered team members. Verify that assumption before submission. An AI assistant is a development tool, not a registered team member.

## AI inside the application

- The default guided mode uses no runtime language model or external LLM API. The application remains usable without credentials.
- An optional OpenAI intent-classification adapter can be enabled with `NEXTSTEP_ENABLE_LLM=1`, `NEXTSTEP_OPENAI_API_KEY` and `NEXTSTEP_OPENAI_MODEL`. Enabling the server capability does not itself consent to sending a question: the user must explicitly opt in through the interface.
- In the optional mode, the submitted question, public role names/IDs and the supported intent schema are sent to OpenAI for classification. Saved resumes, selected skills/interests, account credentials, application snapshots and message conversations are not included. A person can still type personal information into their question, so the interface asks them to use fictional information. The provider processes the submitted question under its own terms. The consent checkbox resets after each question.
- The provider selects a supported intent; advice, roles, resources, scores and citations still come from the local bounded engine. Unavailable, invalid or unsupported provider responses fall back to the guided mode. The model is not permitted to invent jobs, courses or replacement probabilities.
- Matching combines skill coverage, lexical TF-IDF relevance and dated trend evidence. TF-IDF compares word usage; it is not deep semantic understanding.
- Scenario adjustments are explicit prototype assumptions, not a trained labour-market forecasting model.
- The role, skill, resource and SDG catalogue is curated. Recommendations are constrained to those entries and linked evidence.
- A match score is neither a hiring probability nor a promise of employment. The user remains responsible for career decisions.
- Published occupational evidence comes from Gmyrek et al.'s ILO Working Paper 140 (May 2025), using the first author's accompanying dataset under CC BY 4.0. Six catalogue roles have explicit broader ISCO-08 proxies and two have no supported mapping. The source occupation mean is displayed on a 0–100 scale; that rescaling does not make it a proportion of jobs/tasks replaced or a job-loss probability. Source task SD is not a confidence interval. Profile inputs, scenarios and editable assumptions do not alter the published value.
- Four separately labelled probabilities come from Frey and Osborne's 17 September 2013 working-paper appendix: 0.65% for historical computer systems analysts, 1.4% for training/development specialists, and 4.2%/13% for distinct applications/systems-software developer suboccupations. They are historical modelled full-computerisation probabilities, not GenAI forecasts or validated job-loss rates. The official Oxford host was blocked; inspected primary-paper mirror provenance and its limitations are recorded. No full historical PDF is distributed.
- Any editable task-assistance calculator uses six authored example tasks, equal weights and user assistance assumptions. Its mean and ±15-point clipped sensitivity illustration are a separate planning exercise, not research findings, a confidence interval or a replacement probability. The source report excludes personal profiles and conversations. [EVIDENCE.md](EVIDENCE.md) supplies the exact values, citations, scope, derivation and license disclaimer.

Before demonstrating the optional integration, record the exact provider/model configured on that server, the enabled date, any provider charges, and the team's reason for using it. Do not claim that a model was configured or tested merely because the adapter exists. Keep API keys outside the repository and never include them in slides, screenshots or logs.

## External material and data

Declare the actual dependencies used, including Python, Flask and any matching libraries recorded in the repository's dependency files. Public source references include:

- Coder Quad/Simplify new-graduate job listings: <https://github.com/SimplifyJobs/New-Grad-Positions>
- Hugging Face Transformers release feed: <https://github.com/huggingface/transformers/releases.atom>
- Gmyrek et al. (2025), ILO Working Paper 140: <https://doi.org/10.54394/HETP0387>; first-author dataset <https://github.com/pgmyrek/2025_GenAI_scores_ISCO08>, CC BY 4.0. The app selects source rows, applies explicit catalogue proxies and rescales the stored mean; full attribution and the required adaptation disclaimer appear in [EVIDENCE.md](EVIDENCE.md) and downloadable reports.
- Frey and Osborne (17 September 2013), *The Future of Employment: How Susceptible Are Jobs to Computerisation?*, factual appendix values via the pinned primary-paper mirror documented in [EVIDENCE.md](EVIDENCE.md). Current official-file byte equality was not established; no open license or modern predictive validation is claimed.
- Optional public evidence providers: GLEIF Global LEI Index (<https://www.gleif.org/>) and Google Public DNS over HTTPS (<https://developers.google.com/speed/public-dns/docs/doh>). These are separate from recruitment integrations; the default employer-check mode uses local synthetic fixtures.
- Microsoft public learning curricula listed in [FEATURE_RESEARCH.md](FEATURE_RESEARCH.md)
- UN Sustainable Development Goals: <https://sdgs.un.org/goals>
- Domain 1 and the SDC Hackathon 2026 Handbook supplied by the user as requirements references

The catalogue additionally cites O*NET OnLine occupation summaries (<https://www.onetonline.org/>), Kaggle Learn (<https://www.kaggle.com/learn>), IBM SkillsBuild (<https://skillsbuild.org/>), Khan Academy (<https://www.khanacademy.org/>), Microsoft Learn (<https://learn.microsoft.com/>) and UN SDG:Learn (<https://www.unsdglearn.org/>). Runtime software includes Python, Flask, Werkzeug, Jinja2, MarkupSafe, Click, ItsDangerous, Blinker and tzdata; SQLite is provided by Python and pytest is used for development checks. TF-IDF is implemented in Python without an external ML framework. The default assistant uses guided intents and the same evidence; the optional model adapter follows the narrower data flow above. Generated Jitsi links point to a third-party video service whose availability and terms are outside the application. Source availability does not imply endorsement. Follow attribution and applicable resource terms. Synthetic profiles are for demonstration; do not upload real personal CVs or identity documents for this hackathon demo.

The default employer badge records **synthetic registry/domain checks and an independent moderator review**. Salary figures, companies and recruiter references are fictional. An optional GLEIF/DNS mode can inspect public legal-entity records and a domain owner's DNS challenge, with dated results, expiry and revocation. It is not Malaysia's SSM service, personal identity verification, mailbox proof or evidence that a person may recruit for that organization. Both modes require fictional recruiter references and a separate documented moderator authorization assessment. GLEIF access was proxy-blocked here; mocked provider checks do not demonstrate a successfully live-verified company. No real identity documents are collected, and no email or recruitment outreach is sent. Messages and notifications remain local prototype records. The app accountability score is not an independent reputation certification.

## Team review before submitting

- [ ] We can explain the matching weights, TF-IDF baseline, source normalization, scenario assumptions and pathway ordering.
- [ ] We checked real source/resource links and separated observed data from estimates.
- [ ] We adapted the prototype to a user problem we understand and can justify our design decisions.
- [ ] We reviewed the code, ran the relevant checks and recorded actual results.
- [ ] We disclosed all tools, datasets, models, services and any pre-existing material actually used.
- [ ] We checked current organizer guidance and confirmed eligible human contributions.
