# Domain 1 preliminary proposal and demo guide

## Problem → approach → expected outcome

**Target user:** a Malaysian final-year student or recent graduate who knows some digital skills but cannot tell which next skill will lead to a realistic role. The moment of need is choosing a short reskilling plan before applying for entry-level work.

**Problem:** course lists, job titles and AI news are disconnected. A learner needs evidence about what changed, an explanation of their gaps, and a manageable next step.

**Approach:** connect a synthetic skills profile to dated public job-listing signals and an official AI-release feed. Rank a bounded catalogue of roles, explain the score and missing skills, then build an ordered pathway using real free learning resources and SDG explanations. Compare moderate and fast AI-disruption assumptions instead of presenting one certain future.

**Expected outcome:** in one session, a learner can compare relevant roles, inspect the evidence, and leave with a practical learning plan. This prototype has not established employment outcomes or forecast accuracy.

### Short pitch draft

> AI is changing work faster than many learners can choose their next course. Our prototype helps a recent graduate answer: “Given what I know today, what should I learn next, and why?” It connects dated public job and AI signals to an explainable role match, shows the missing skills, and turns those gaps into a learning pathway with an estimated time commitment and meaningful SDG links. Learners can compare two disruption scenarios and inspect the sources behind the advice. We start with international entry-level technology signals and synthetic profiles; the next validation step is testing locally relevant data and recommendations with Malaysian learners and career advisers. People make the career decision—the tool makes the evidence easier to use.

Replace this framing with the team's own validated user insight before submission.

## What the preliminary brief actually asks for

Domain 1 says a proof of concept is acceptable. The proposal should explain all six final-product must-haves, while the live demo proves the most important feature. Its suggested core demonstration is **updatable trend signals feeding role matching**, rather than only a CV-to-chatbot interaction.

| Must-have | Prototype demonstration | Important boundary |
| --- | --- | --- |
| Skills intake | Select or enter skills and interests using synthetic examples | A form satisfies the brief; real CVs are unnecessary |
| Updatable signal layer | Inspect dated public job and AI-release evidence; refresh supported feeds | Show source, date, sample coverage and refresh status |
| Explainable matching | Compare ranked roles, score components and missing skills | Scores express prototype fit, not hiring probability |
| Personalised pathway | Follow ordered skill-gap steps with learning links and estimated effort | Resources are real; effort estimates are ours |
| SDG mapping | Inspect each role/skill's relevant goals and explanation | Tags describe a plausible contribution, not measured impact |
| Uncertainty | Compare moderate and fast disruption scenarios | Scenario assumptions are illustrative, not validated forecasts |

Domain 1 printed pages 3–5 describe the journey, must-haves and boundaries; pages 6–7 give the preliminary rubric. The rubric weights are innovation **30%**, problem–solution fit **25%**, feasibility **25%**, and clarity **20%**. The general handbook requires a working prototype, functional interface and live presentation/pitch on printed page 15.

**The supplied PDFs do not specify exact proposal length, slide count, pitch duration or submission form.** Check the latest organizer instructions for those details.

## Architecture and explanation

The HTML/CSS/JavaScript interface calls a Python backend. The backend combines a curated role/skill/resource catalogue with normalized, dated public source records. The catalogue constrains outputs so the system does not invent course names or jobs.

The baseline matching score uses three explainable parts: **65% skill coverage, 20% lexical TF-IDF relevance, and 15% trend evidence**. TF-IDF is a lightweight information-retrieval method: it compares words in the profile/interests with role descriptions, giving less-common words more weight. It does not understand a CV like a person, and it is not a generative language model. Inspect the implementation and displayed score components when explaining the exact calculation.

Trend and scenario inputs can affect role ranking and the weight given to skill coverage. For a fixed role, pathway order follows the same curated prerequisites; it is not automatically reordered by the scenario. A refresh can legitimately return identical records; the demo must not pretend every refresh produces a market change. A changed-data test is distinct from a real-world forecast validation.

The assistant's primary occupational AI evidence is the **ILO–NASK 2025 GenAI exposure mean**, with a date, exact source group and explicit mapping caveat. Six catalogue roles have broader proxies; BI and project management remain unavailable. A displayed 0–100 score is a rescaled technical-potential index, not a percentage of jobs or tasks replaced. Historical 2013 modelled computerisation probabilities appear separately for three catalogue roles, retaining both developer suboccupations. Editable task assumptions are a planning exercise and do not change source values. The downloadable JSON research report contains public evidence and methodology, not a personal resume. See [EVIDENCE.md](EVIDENCE.md) for attribution and provenance.

## Honest data scope and biggest risk

- **Jobs:** Coder Quad/Simplify's public new-graduate technology listings. The contributor guidance targets US, Canadian or remote roles. This is an international sample, not a representative Malaysian labour-market dataset. Titles/categories provide limited skill evidence; many required skills are not stated in a title.
- **AI advancement:** Hugging Face Transformers release notes, published through the project's official GitHub release feed. Software releases establish technical activity, not employment demand.
- **Occupational AI evidence:** ILO Working Paper 140 (May 2025), first-author dataset under CC BY 4.0, accessed 23 October 2026. Its technical exposure is separate from Frey–Osborne's historical 2013 probabilities; neither establishes actual job losses or a current personal replacement probability.
- **Resources:** linked public curricula, with provider attribution. Free reading does not guarantee free cloud/model exercises. Learning hours are planner estimates.
- **Trend labels:** limited samples and unequal publication patterns can mislead. Explain the comparison windows and sample counts. Missing terms alone do not establish skill obsolescence.
- **SDGs:** editorial mappings with a rationale. They are not UN endorsements or measured sustainability results.

**Biggest risk:** weak or geographically narrow signals producing convincing but misleading advice. Keep source citations and dates visible, disclose sparse evidence, and validate the skill taxonomy and pathways with a career adviser. The fallback is the last successfully fetched, timestamped snapshot, clearly labelled as cached. An unavailable live source must not be represented as successfully refreshed. A synthetic changed-signal example may support a controlled demo only when explicitly labelled synthetic.

## Suggested five-minute demo

1. Choose a synthetic graduate profile. Show the selected skills and interests; explain why this user needs guidance.
2. Open the radar. Search a relevant skill or role and show the source, source date, sample coverage and evidence links.
3. Generate matches. Explain the first role's three score components and identify an existing skill plus a concrete gap.
4. Compare moderate and fast scenarios. Describe which assumption changes; do not call the difference a proven prediction.
5. Open the pathway. Show the ordered missing skills, time estimates, a real learning link and the SDG contribution explanation.
6. Refresh the public feeds if connectivity permits. Show either updated evidence or an honest unchanged/cached result. Explain the data-change test separately.

If time permits after the six-feature core journey, open a cited occupational evidence panel, inspect its broader source group and download the public research report. Show BI or project management as an honest unavailable mapping. For the recruitment extension, use synthetic HR and moderator accounts to demonstrate a registry fixture, explicit domain-token simulation, separate authorization review and publishing gate. Do not call the synthetic badge real employer verification or claim a successful live GLEIF/SSM check.

The recruitment workflow, public-provider adapter, messages, calendars and research exports extend the team's concept. They are not additional mandatory Domain 1 features and must not displace the required trend-to-match-to-pathway demonstration. A working prototype does not perform the team's live pitch, grant judges repository access, establish original understanding or complete human review/adaptation.

## Submission checklist

- [ ] Team has reviewed, adapted and can explain the implementation and this proposal.
- [ ] GitHub link is public or accessible to judges and contains the code actually demonstrated.
- [ ] Setup instructions work on the demonstration machine; the UI can be opened and the journey completed.
- [ ] A live pitch and proposal cover all six features and the primary user problem.
- [ ] Latest organizer submission format, deadlines and length limits have been checked.
- [ ] Data, software and AI assistance are declared; synthetic profiles are used.
- [ ] Actual test/demo results are recorded by the team. This document does not claim tests were run.
- [ ] A fallback for source/network failure is prepared without presenting cached data as live.
