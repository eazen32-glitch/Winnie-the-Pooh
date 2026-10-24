# Occupational AI evidence and its limits

The primary metric is the published **2025 GenAI occupational exposure mean**, displayed on a 0–100 scale. It is not a job-replacement probability. Historical computerisation probabilities and editable planning assumptions are separate measures with separate sources and meanings.

## Current GenAI technical potential

Gmyrek, P., Berg, J., Kamiński, K., Konopczyński, F., Ładna, A., Nafradi, B., Rosłaniec, K., Troszyński, M. 2025. *Generative AI and Jobs: A Refined Global Index of Occupational Exposure*. ILO Working Paper 140. Geneva: International Labour Office. © ILO. <https://doi.org/10.54394/HETP0387>.

Published May 2025; capabilities are a snapshot of the start of 2025. Retrieved **23 October 2026** from the [first-author source repository](https://github.com/pgmyrek/2025_GenAI_scores_ISCO08), which the paper links on printed page 37. The repository includes the paper, workbook, dictionary and CC BY 4.0 license. Direct ILO retrieval was blocked by this environment's proxy; author-hosted primary material was downloaded and inspected.

The full source covers 427 ISCO-08 four-digit occupations and 3,265 task rows. Task scores use worker/expert assessments and model extrapolation to estimate technical potential with current GenAI. The occupation's `mean_score_2025` is the mean of its task scores; task frequency and importance are not available, so tasks receive equal weight. The bundled extract preserves the **published stored mean**, rather than recomputing a more precise mean from task rows. Multiplying by 100 only changes its scale. A score of 53/100 does not mean 53% of jobs, working hours or tasks will disappear.

All catalogue mappings below are explicit **editorial broader proxies**, not an official O*NET–ISCO crosswalk or source estimates for these exact catalogue titles. Two mappings remain unavailable.

| Catalogue role | Published ISCO-08 group | Mean / 0–100 score | Task SD | Source category | Mapping limit |
| --- | --- | --- | --- | --- | --- |
| Business Intelligence Analyst | Unavailable | — | — | — | No unambiguous group mapping; no neighboring occupation is substituted |
| Data Scientist | 2120 — Mathematicians, Actuaries and Statisticians | 0.56 / 56 | 0.09 | Exposed: Gradient 3 | Broad statistical-professional proxy including actuarial work; does not isolate data scientists |
| Software Developer | 2512 — Software Developers | 0.53 / 53 | 0.07 | Exposed: Gradient 3 | Close title/task alignment across different classification systems |
| Information Security Analyst | 2529 — Database and Network Professionals Not Elsewhere Classified | 0.49 / 49 | 0.06 | Exposed: Gradient 2 | Broader family whose listed tasks explicitly cover cybersecurity |
| Sustainability Specialist | 2133 — Environmental Protection Professionals | 0.38 / 38 | 0.04 | Minimal Exposure | Environmental management/audit proxy; not all sustainability or ESG work |
| Training and Development Specialist | 2424 — Training and Staff Development Professionals | 0.41 / 41 | 0.09 | Exposed: Gradient 2 | Close title/task alignment across different classification systems |
| Project Management Specialist | Unavailable | — | — | — | No unambiguous source group or verified crosswalk |
| Computer Systems Analyst | 2511 — Systems Analysts | 0.49 / 49 | 0.05 | Exposed: Gradient 2 | Close title/task alignment across different classification systems |

`SD_2025` describes differences between tasks inside a source occupation. It is **not** a confidence interval, uncertainty margin or variation between individual workers. The source classification combines the mean and task SD; preserve the published category rather than inventing probability bands.

Paper locations: Table A1, printed pages 48–51, contains these source rows; printed page 38, footnote 18, explains equal task weighting. Pages 39 and 44–45 describe subjectivity, adoption constraints and the gap between exposure and actual employment effects. The study does not account for future technology or newly created jobs. Its worker/expert and model assessments are not empirical validation of job-loss outcomes. Local tasks, infrastructure, costs, policy and organizational choices can change real effects.

## Separate historical computerisation probabilities

Carl Benedikt Frey and Michael A. Osborne, *The Future of Employment: How Susceptible Are Jobs to Computerisation?*, **17 September 2013 working paper**, University of Oxford. This is the dated working-paper version, not a claim about its later journal publication.

The appendix publishes model-derived probabilities of **full occupational computerisation** under the study's historical machine-learning/mobile-robotics assumptions, using US occupation information and 2010 employment data. These are published probabilities, not observed loss rates, personal probabilities, validated future outcomes or modern GenAI forecasts.

| Catalogue comparison | Exact historical source occupation and code | Published probability | Percentage representation | Appendix page |
| --- | --- | --- | --- | --- |
| Computer Systems Analyst | Computer Systems Analysts — 15-1121 | 0.0065 | 0.65% | 57 |
| Training and Development Specialist | Training and Development Specialists — 13-1151 | 0.014 | 1.4% | 58 |
| Software Developer, applications subgroup | Software Developers, Applications — 15-1132 | 0.042 | 4.2% | 59 |
| Software Developer, systems-software subgroup | Software Developers, Systems Software — 15-1133 | 0.13 | 13% | 60 |

Current catalogue codes differ from historical codes. The two software subgroups are preserved separately; the app does not average them into a probability for today's broader Software Developer role. There is no supported historical estimate for the other catalogue roles. In particular, the paper's 21% entry combines information security analysts, web developers and network architects; it is not an information-security-specific estimate.

On page 44 the authors write: “We make no attempt to estimate the number of jobs that will actually be automated, and focus on potential job automatability over some unspecified number of years.” Their discussion mentions a possible decade or two, not a fixed forecast deadline. Page 43 says the estimates concern full occupation automation and do not capture within-occupation task changes.

The [canonical Oxford link](https://www.oxfordmartin.ox.ac.uk/downloads/academic/The_Future_of_Employment.pdf) was blocked by this environment's proxy. Values were read from a [pinned mirror of the primary paper](https://raw.githubusercontent.com/BroderickHigby/job_automation/83d78265a3f5d56242b2f6c63d79902e870bc715/sources/The_Future_of_Employment.pdf), accessed 23 October 2026. The title, authors, date and appendix were inspected. Byte equality with the inaccessible current Oxford file was **not established**. No explicit reuse license was found; the project retains cited factual values and does not redistribute that full PDF.

## Provenance, reuse and downloadable reports

The factual extract is [data/exposure_evidence.json](../data/exposure_evidence.json). It carries citations, mapping explanations, source row/page locators, scope, limitations and attribution. Source values do not change with a user's profile, scenario or editable task assumptions.

| Source artifact | Immutable repository commit | SHA-256 |
| --- | --- | --- |
| ILO `Final_Scores_ISCO08_Gmyrek_et_al_2025.xlsx` | `ce5fc25c2a0db2757c5bfa797c4cfc8b408431ea` | `c1940b87e7293b1eb95b530b6d3da7cd806b61d217c4bff1e69372b2cff5c90a` |
| Historical `The_Future_of_Employment.pdf` mirror | `83d78265a3f5d56242b2f6c63d79902e870bc715` | `1d0ef561ebef9ececda63403a40860aa172be953fe2b050d27de8987c9e852fc` |

The ILO workbook's `Sheet1` columns are C=`ISCO_08`, D=`Title`, Q=`mean_score_2025`, S=`SD_2025` and T=`potential25`. Included row ranges: 2120 rows 336–345; 2133 rows 366–372; 2424 rows 804–811; 2511 rows 848–854; 2512 rows 855–862; 2529 rows 896–903. The API carries these locators alongside each applicable source value.

Public research endpoints:

- `GET /api/exposure/evidence?role_id=software-developer` returns one role's source evidence and mapping.
- `GET /api/exposure/methodology` returns definitions, sources, coverage and limitations.
- `GET /api/exposure/report/software-developer` downloads a JSON research report. It contains public research and catalogue metadata, not a personal profile, resume or conversation.

The ILO material is licensed under [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/). Credit the authors and ILO, retain the source/license links, and disclose changes. This application selects six occupation records, maps them to its catalogue and rescales means to 0–100. It does not imply ILO endorsement or use the ILO emblem/logo.

> This is an adaptation of a copyrighted work of the International Labour Organization (ILO). This adaptation has not been prepared, reviewed or endorsed by the ILO and should not be considered an official ILO adaptation. The ILO disclaims all responsibility for its content and accuracy. Responsibility rests solely with the author(s) of the adaptation.

The evidence adapter validates required provenance, bounded numeric values and explicit coverage before serving a report. Software checks can establish faithful extraction and separation of metrics; they cannot establish the studies' predictive accuracy or real employer/worker outcomes. Actual build checks are recorded in [VALIDATION.md](VALIDATION.md).
