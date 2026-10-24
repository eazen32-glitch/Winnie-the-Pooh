# Domain 1 feature research

This research prioritizes the supplied **Aiversecity Future-Ready Workforce** brief. The strongest preliminary demo connects a real, dated signal to an explainable recommendation. A polished dashboard with only hard-coded demand labels would miss that requirement.

## Scope and priorities

| Priority | Feature in the prototype scope | Why it matters |
| --- | --- | --- |
| P0 | Synthetic profile form and sample profiles | Starts the required user journey without collecting real CVs |
| P0 | Refreshable public job signals and AI-release evidence | Demonstrates an updatable source instead of a static list |
| P0 | Explainable ranked roles and skills gaps | Makes the primary recommendation inspectable |
| P0 | Ordered learning pathway with real resources | Converts a recommendation into an actionable next step |
| P0 | Role/skill SDG mappings with reasons | Connects the career choice to the domain's sustainability aim |
| P0 | Moderate/fast disruption scenarios | Exposes assumptions and uncertainty |
| P1 | Search/filter for skills, roles and evidence | Helps a learner investigate a recommendation during the demo |
| P1 | Cached evidence, scheduled refresh and visible source status | Keeps a useful demo available during a source outage and updates it without repeated manual work |
| P1 | Browser-local progress and downloadable plan | Lets the learner track introductory steps and retain cited recommendations |
| P1 | Published occupational AI evidence with explicit mapping gaps and research export | Replaces an authored task index as the primary evidence without relabelling exposure as job loss |
| P1 | Salary bounds, structured employer checks, direct messages and response tracking | Completes the team's recruitment workflow while keeping it separate from the official trend-to-pathway demonstration |

These priorities describe the chosen implementation scope. Verify actual behaviour using the repository's tests and a full manual demo; the research alone does not establish readiness.

### Useful later additions

- **Progress reminders and assessment:** extend the implemented self-reported progress checkboxes with a reviewed assessment. Marking a step complete does not establish professional proficiency.
- **Reviewed re-planning:** scheduled refresh and changed-evidence recalculation are implemented; a richer before/after explanation and explicit acceptance of a changed saved plan remain useful additions.
- **Employer view:** aggregate skills gaps for a synthetic team. Useful after individual recommendations are credible.
- **English/Bahasa Malaysia/Chinese:** translate interface and explanations, then verify terminology with speakers rather than relying on automatic translation alone.
- **Fairness evaluation:** test matched synthetic profiles differing only in irrelevant demographic attributes. Avoid using age, gender or protected traits as fit inputs.
- **Malaysian evidence adapter:** add a permitted local dataset with dates and documented coverage. Do not relabel international data as Malaysian demand.

The Domain 1 brief labels these kinds of enhancements optional and not separately scored (printed page 5). They should not displace the six required capabilities.

## Verified data sources

### Public new-graduate job listings

- Repository: <https://github.com/SimplifyJobs/New-Grad-Positions>
- Refreshable JSON: <https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/.github/scripts/listings.json>
- Scope/contribution rules: <https://github.com/SimplifyJobs/New-Grad-Positions/blob/dev/CONTRIBUTING.md>

The JSON endpoint returned HTTP 200 during research on **22 October 2026**. The inspected response had 19,165 records, including 2,998 marked active. Those are observations from that response, not durable statistics or a count of Malaysian vacancies. Fields include `title`, `category`, `company_name`, `date_posted`, `active`, `url` and `locations`; publication dates are Unix timestamps. The repository describes its maintenance as daily.

The list covers entry-level technical roles, with contributor guidance specifying US, Canadian or remote locations. It is a biased sample. It is suitable for a preliminary signal demonstration, not population-level predictions. No explicit dataset license was identified at common repository license paths during this check; retain source attribution, link to records, and avoid copying unnecessary content. Do not invent an open-data license. Cache responses rather than downloading on every page view.

### AI advancement feed

- Official releases: <https://github.com/huggingface/transformers/releases>
- Atom feed: <https://github.com/huggingface/transformers/releases.atom>

The feed returned HTTP 200 during research, with ten entries containing titles, update dates, links and release content. It provides identifiable AI-tool advancement events. A new release is not evidence that a particular occupation is growing. Keep that distinction visible when combining technical and job signals.

### Other candidates checked

Remotive's documented API is <https://remotive.com/api/remote-jobs>, with official documentation at <https://github.com/remotive-com/remote-jobs-api>. Its documentation requires attribution and links back, delays listings by 24 hours, advises a maximum of four requests daily, and warns against excessive requests. The API itself was blocked by this environment's egress proxy, so it was not used as a verified working feed. Jobicy and the arXiv API were also blocked here. GitHub-hosted sources worked without API keys. A blocked request establishes an access limitation in this environment, not that the service is unavailable everywhere.

### Occupational AI evidence — researched 23 October 2026

The selected current source is Gmyrek et al. (2025), *Generative AI and Jobs: A Refined Global Index of Occupational Exposure*, ILO Working Paper 140, <https://doi.org/10.54394/HETP0387>. Its first-author [repository](https://github.com/pgmyrek/2025_GenAI_scores_ISCO08) provides the paper, full task workbook, data dictionary and CC BY 4.0 license; the paper links the accompanying dataset. These artifacts were downloaded and inspected. Official ILO web access was blocked here, so the provenance identifies the author-hosted workbook, immutable commit, SHA-256 checksum and source row locations.

The source's 427 occupational groups and 3,265 task rows support a technical-potential index, not an observed replacement rate. The published mean is displayed on a 0–100 scale without changing its meaning. Six catalogue roles use explicit broader ISCO-08 proxies; BI and project management are unavailable because no defensible mapping was established. Equal task weighting, group-level mapping, worker/expert judgment, model extrapolation and early-2025 capabilities limit interpretation. Source task SD is not predictive uncertainty. User assumptions cannot change a published source value.

The separate historical comparison retains four factual probabilities from Frey and Osborne's **17 September 2013 working paper**, for systems analysts, training/development specialists and two distinct software suboccupations. It does not substitute them for modern GenAI evidence or average the developer subgroups. A pinned primary-paper mirror was inspected, but current canonical Oxford byte equality was not established because the official host was blocked. No explicit reuse license was found; the project cites factual values and distributes no full historical PDF. [EVIDENCE.md](EVIDENCE.md) contains the exact table, scope and license/adaptation details.

### Employer evidence and registry research

The default implementation uses a fixed fictional legal entity, an explicit simulated domain challenge and separate moderator authorization review. This makes the claim reviewable without collecting real identity documents. Timestamped snapshots, SHA-256 digests, expiry, revocation and legal-entity collision checks support review history; a digest is not proof that a claim is true.

The optional public adapter uses [GLEIF's Global LEI Index](https://www.gleif.org/) for an exact LEI lookup and [Google Public DNS over HTTPS](https://developers.google.com/speed/public-dns/docs/doh) for an exact TXT token on the claimed company domain. An LEI record establishes information about a legal entity; it does not establish a recruiter's identity or employment. DNS demonstrates domain control only. GLEIF is **not Malaysia's SSM registry**, and organizations without an LEI cannot match this provider. Both modes require fictional recruiter references and a separate documented authorization assessment; the system does not collect personal identity documents or send email/recruitment outreach.

The live GLEIF attempt was blocked by this environment's proxy. Fixture/parser/network-boundary tests must not be described as a successful live company check. Unavailable or mismatching provider results block approval and publishing rather than falling back to an approval. The default hackathon demonstration remains synthetic. [WORKFLOWS.md](WORKFLOWS.md#employer-check-configuration) documents the opt-in configuration and limitations.

## Real learning resources

The following official Microsoft curriculum README endpoints were successfully fetched during research. Link to their published repositories; do not invent course titles, certificates or fees.

| Resource | Suitable learning area |
| --- | --- |
| [AI for Beginners](https://github.com/microsoft/AI-For-Beginners) | AI foundations |
| [Machine Learning for Beginners](https://github.com/microsoft/ML-For-Beginners) | Applied machine learning |
| [Data Science for Beginners](https://github.com/microsoft/Data-Science-For-Beginners) | Data analysis and visualization |
| [Generative AI for Beginners](https://github.com/microsoft/generative-ai-for-beginners) | Generative AI applications |
| [AI Agents for Beginners](https://github.com/microsoft/ai-agents-for-beginners) | AI agent concepts |
| [Web Development for Beginners](https://github.com/microsoft/Web-Dev-For-Beginners) | Web application foundations |

Reading is publicly accessible; some optional exercises need paid API/cloud services. Any pathway duration is the planner's estimate, not a provider guarantee.

Authoritative SDG descriptions are at <https://sdgs.un.org/goals>. O*NET/My Next Move can support occupation definitions: <https://www.mynextmove.org/>. Their sites and Microsoft Learn were blocked by this environment's proxy during research, so live accessibility was not verified here. SDG contribution explanations remain editorial mappings and should cite the relevant official goal.
