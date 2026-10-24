"""Source-grounded guidance and reviewable task-assistance scenarios.

No generative model or employment-risk model is used. Advice is assembled from
the same curated catalogue and dated evidence as the career matching page.
"""

from __future__ import annotations

import math
import re

from .catalog import ROLES, SKILLS
from .exposure import build_exposure_evidence
from .recommendations import match_profile
from .sources import safe_url

ROLE_BY_ID = {role["id"]: role for role in ROLES}
SKILL_BY_ID = {skill["id"]: skill for skill in SKILLS}
METHOD = "Guided, source-grounded responses using catalogue retrieval and the existing matching baseline; no language model."
DISCLAIMER = (
    "Career exploration only. Match scores are not hiring probabilities. "
    "Published occupational exposure evidence and the editable task-assistance "
    "index measure different things. Neither is a validated personal job-loss "
    "probability. People make career and hiring decisions."
)

# These examples are authored, reviewable descriptions of task assistance.
# O*NET links establish the occupation context, not the validity of our labels.
_TASKS = {
    "business-intelligence-analyst": {
        "levels": ("moderate", "high"),
        "tasks": ["Draft SQL queries for review", "Create initial dashboard summaries", "Prepare routine report drafts"],
        "strengths": ["Check data quality and business meaning", "Choose useful measures", "Explain trade-offs to stakeholders"],
    },
    "data-scientist": {
        "levels": ("moderate", "high"),
        "tasks": ["Draft analysis code", "Suggest candidate features", "Summarise documented experiment results"],
        "strengths": ["Design valid experiments", "Evaluate bias, leakage and uncertainty", "Decide whether a model is appropriate"],
    },
    "software-developer": {
        "levels": ("moderate", "high"),
        "tasks": ["Draft routine code and tests", "Summarise code changes", "Suggest debugging hypotheses"],
        "strengths": ["Understand user needs", "Review security and system design", "Verify behaviour and maintainability"],
    },
    "information-security-analyst": {
        "levels": ("moderate", "moderate"),
        "tasks": ["Summarise security logs", "Group alerts for analyst review", "Draft incident documentation"],
        "strengths": ["Investigate ambiguous threats", "Validate evidence before escalation", "Make accountable incident-response decisions"],
    },
    "sustainability-specialist": {
        "levels": ("low", "moderate"),
        "tasks": ["Organise sustainability disclosures", "Draft resource-use summaries", "Search reference material for review"],
        "strengths": ["Validate environmental evidence", "Understand local operational constraints", "Coordinate measurable changes with people"],
    },
    "learning-development-specialist": {
        "levels": ("low", "moderate"),
        "tasks": ["Draft introductory lesson outlines", "Suggest practice questions", "Summarise non-sensitive training feedback"],
        "strengths": ["Understand learner needs", "Teach and coach with empathy", "Evaluate genuine understanding and inclusion"],
    },
    "project-management-specialist": {
        "levels": ("moderate", "moderate"),
        "tasks": ["Draft meeting summaries", "Organise task updates", "Prepare initial schedule and risk-register drafts"],
        "strengths": ["Negotiate priorities", "Resolve team conflicts", "Own delivery and risk decisions"],
    },
    "computer-systems-analyst": {
        "levels": ("moderate", "high"),
        "tasks": ["Draft requirements summaries", "Outline routine workflow changes", "Generate initial documentation"],
        "strengths": ["Understand organisational context", "Validate requirements with users", "Assess integration and change-management risks"],
    },
}


def role_exposure(role_id, scenario="moderate", task_assumptions=None):
    """Describe selected tasks and an editable index, never replacement risk.

    The numeric index averages authored/user-selected assumptions for six
    equally weighted example tasks. It is not observed occupational exposure,
    work-hour coverage, an empirical forecast or a probability.
    """
    if role_id not in ROLE_BY_ID:
        raise ValueError("Choose a role from the career catalogue.")
    if scenario not in ("moderate", "fast"):
        raise ValueError("Choose the moderate or fast scenario.")
    role = ROLE_BY_ID[role_id]
    tasks = _TASKS[role_id]
    level = tasks["levels"][1 if scenario == "fast" else 0]
    defaults = {"low": (25, 0), "moderate": (50, 10), "high": (80, 20)}[level]
    examples = [
        {"id": f"routine-{index + 1}", "label": label, "assistance_percent": defaults[0]}
        for index, label in enumerate(tasks["tasks"])
    ] + [
        {"id": f"judgement-{index + 1}", "label": label, "assistance_percent": defaults[1]}
        for index, label in enumerate(tasks["strengths"])
    ]
    if task_assumptions is not None:
        if not isinstance(task_assumptions, dict) or set(task_assumptions) - {task["id"] for task in examples}:
            raise ValueError("Edit only the supplied example-task assumptions.")
        for task in examples:
            if task["id"] in task_assumptions:
                value = task_assumptions[task["id"]]
                if isinstance(value, bool) or not isinstance(value, (float, int)) or not 0 <= value <= 100 or not math.isfinite(value):
                    raise ValueError("Task-assistance assumptions must be numbers from 0 to 100.")
                task["assistance_percent"] = round(value, 1)
    percentage = round(sum(task["assistance_percent"] for task in examples) / len(examples), 1)
    lower = round(sum(max(0, task["assistance_percent"] - 15) for task in examples) / len(examples), 1)
    upper = round(sum(min(100, task["assistance_percent"] + 15) for task in examples) / len(examples), 1)
    adoption = "Faster adoption assumes broader access to capable AI tools" if scenario == "fast" else "Moderate adoption assumes selective use with human review"
    return {
        "level": level,
        "scenario": scenario,
        "summary": (
            f"Illustrative {level} AI-assistance exposure for selected routine tasks in {role['title']}. "
            f"{adoption}. This is not the probability that this job or person will be replaced."
        ),
        "task_examples": list(tasks["tasks"]),
        "human_strengths": list(tasks["strengths"]),
        "role_id": role_id,
        "role_title": role["title"],
        "research_evidence": build_exposure_evidence(role_id),
        "task_assessment": {
            "label": "Illustrative task-assistance index",
            "percentage": percentage,
            "tasks": examples,
            "customised": task_assumptions is not None,
            "formula": "Sum of the six assumed assistance percentages divided by six (equal example-task weights).",
            "sensitivity_band": {"lower": lower, "upper": upper, "assumption_shift_points": 15},
            "uncertainty": "The band shifts each task assumption by 15 percentage points, clipped to 0–100. It is a sensitivity example, not a confidence interval.",
            "scope": "Six authored task examples, not a representative task survey or share of work hours. Defaults are editorial scenario assumptions; edit them to explore alternatives. This is not a job-replacement probability.",
        },
        "source_url": role["source_url"],
        "method": (
            "Editorial qualitative task assessment with an O*NET occupation reference. "
            "O*NET supports the occupation context; it does not endorse these exposure labels. "
            "Labels are sensitivity assumptions and have not been validated against employment outcomes."
        ),
    }


def _reply(answer, sources=(), actions=(), research_evidence=None):
    seen, citations = set(), []
    for source in sources:
        url = safe_url(source.get("url"))
        if url and url not in seen:
            citations.append({"title": str(source.get("title", "Source"))[:240], "url": url, "date": str(source.get("date", ""))[:32]})
            seen.add(url)
    response = {"answer": answer, "sources": citations[:7], "actions": list(actions), "method": METHOD, "disclaimer": DISCLAIMER}
    if research_evidence is not None:
        response["research_evidence"] = research_evidence
    return response


def _named_role(query):
    """Resolve only catalogue names/aliases, with word boundaries.

    Longest matches win so a specific occupation is not displaced by a short
    alias. Substrings such as "software developerish" are not occupations.
    """
    candidates = [
        (len(name), role["id"])
        for role in ROLES
        for name in [role["title"], *role.get("aliases", [])]
        if re.search(
            r"(?<!\w)" + re.escape(name.lower())
            + (r"s?" if name.lower().endswith(("analyst", "scientist", "developer", "specialist", "manager", "engineer", "designer", "coordinator")) else "")
            + r"(?!\w)", query,
        )
    ]
    return max(candidates)[1] if candidates else None


def _research_summary(evidence):
    """Describe a published measure without converting it into replacement risk."""
    source = evidence.get("source", {})
    mapping = evidence.get("mapping", {})
    scope = evidence.get("scope", {})
    if evidence.get("status") != "available":
        reason = evidence.get("unavailable_reason") or evidence.get("reason") or "No defensible published occupation mapping is available in the curated evidence."
        return f"Published exposure measure: unavailable. {reason} No percentage is inferred from another occupation."
    metric = evidence["metric"]
    value = metric.get("percent")
    score = f"{value:g}" if isinstance(value, (float, int)) else str(value)
    relation = "exact occupation match" if mapping.get("relation") == "exact" else "broader occupation proxy"
    uncertainty = evidence.get("uncertainty", {})
    uncertainty_text = uncertainty.get("text", "") if isinstance(uncertainty, dict) else str(uncertainty)
    return (
        f"Published measure: {score}/100 {metric.get('name', 'exposure index')} "
        f"({source.get('publisher', '')}, {source.get('year', '')}). "
        f"{metric.get('interpretation', '')}\n"
        f"Scope: {scope.get('geography', 'not specified')}; {scope.get('population', 'not specified')}. "
        f"Time horizon: {scope.get('time_horizon', 'not specified')}.\n"
        f"Mapping: {relation} — {mapping.get('source_classification', '')} "
        f"{mapping.get('source_code', '')}, {mapping.get('source_title', '')}. "
        f"{mapping.get('rationale', '')}\n"
        f"Uncertainty: {uncertainty_text}"
    )


def _historical_summary(evidence):
    """Keep 2013 source-model probabilities separate by source occupation."""
    estimates = evidence.get("historical_estimates", [])
    if not estimates:
        return "Historical computerisation estimate: unavailable for this catalogue role in the curated evidence."
    records = []
    for estimate in estimates:
        metric = estimate["metric"]
        mapping = estimate["mapping"]
        scope = estimate["scope"]
        records.append(
            f"{mapping['source_title']} ({mapping['source_classification']} {mapping['source_code']}): "
            f"{metric['display_value']} — {metric['name']}. "
            f"{mapping['rationale']} {mapping['caveat']} "
            f"Scope: {scope['geography']}. Time horizon: {scope['time_horizon']}."
        )
    return (
        "Historical 2013 computerisation model, shown separately from 2025 GenAI research:\n"
        + "\n".join(records)
        + "\nThese are older US occupation-level model estimates for broad computerisation, "
        "not current GenAI replacement percentages, observed job losses or validated personal forecasts. "
        "Distinct source suboccupations are not averaged or compared directly with the 2025 exposure index."
    )


def _signal_context(snapshot):
    status = snapshot.get("signal_status", {})
    timestamp = status.get("fetched_at") or "not available"
    availability = status.get("status", "offline")
    return (
        f"Evidence snapshot: {timestamp} ({availability}). Job evidence is a limited international "
        "graduate-role sample, not Malaysian labour-market statistics."
    )


def _snapshot_source(snapshot):
    status = snapshot.get("signal_status", {})
    return {"title": status.get("source_name", "Public job sample"), "url": status.get("source_url", ""), "date": status.get("fetched_at", "")}


def build_reply(message, profile, snapshot, actor_role="guest", role_id=None):
    """Return a bounded, explainable response for supported career/workflow intents.

    The caller validates the incoming profile and obtains actor_role from the
    authenticated session. This function neither reads applicant records nor
    performs hiring actions.
    """
    if not isinstance(message, str) or not message.strip() or len(message) > 1000:
        raise ValueError("Ask a question of 1 to 1,000 characters.")
    if role_id is not None and role_id not in ROLE_BY_ID:
        raise ValueError("Choose a role from the career catalogue.")
    query = message.lower().strip()
    # A known occupation explicitly named by the user takes priority over the
    # selected pathway or default top match. No occupation is created from text.
    named_role = _named_role(query)
    if named_role:
        role_id = named_role
    exposure_intent = bool(
        re.search(r"\b(exposure|replace|replacement|replaced|automation|automate|automated|automating|computerisation|computerization|risk|risks)\b", query)
        or re.search(r"\b(job[- ]loss|lose (?:my|our|their|the) job|take (?:my|our|their|the) job)\b", query)
    )
    if re.search(r"\b(salary|salaries|pay|compensation|wage|wages)\b", query):
        return _reply(
            "Job cards show the employer's stated base salary range, currency and pay period. "
            "Salary bounds are required before a vacancy can be published; compare the same currency and pay period. "
            "Demo salaries are illustrative, not labour-market salary estimates. HR can edit salary details in the company profile.",
            actions=[{"label": "Company profile" if actor_role == "hr" else "Find a job", "view": "profile" if actor_role == "hr" else "jobs"}],
        )
    if re.search(r"\b(verify|verified|verification|moderator|scam|scams|trust)\b", query):
        return _reply(
            "Check the company's verification status and review notes on its vacancy. HR submits synthetic company-registration "
            "and recruiter evidence from the company profile; an authorised moderator reviews it and records a reason. "
            "This prototype simulates that review. A demo verification badge is not a real company-registry or identity check.",
            actions=[{"label": "Company profile" if actor_role == "hr" else "Inspect employers", "view": "profile" if actor_role == "hr" else "jobs"}],
        )
    if re.search(r"\b(message|messages|messaging|chat|contact|employer|recruiter)\b", query):
        if actor_role == "guest":
            return _reply("Sign in as a job seeker to contact an employer from a vacancy. Your in-app conversations are separate from this career assistant.", actions=[{"label": "Explore jobs", "view": "jobs"}, {"label": "Sign in", "view": "profile"}])
        return _reply("Use Message employer on a vacancy, or Message applicant in the HR inbox. The Messages page holds your private, role-scoped conversations. Replies stay inside this demo; no email is sent.", actions=[{"label": "Open messages", "view": "messages"}])
    if re.search(r"\b(sla|overdue|deadline|deadlines|reason|reasons|feedback|ghosting|tracker|tracking|notification|notifications)\b", query):
        return _reply(
            "The application tracker shows submission, employer viewing, review, interview and decision events. "
            "Accepting or rejecting requires a reason. The response deadline and overdue flag make pending decisions visible; "
            "in-app notifications refresh while the workspace is open. Employers still make every hiring decision.",
            actions=[{"label": "Review applications", "view": "applicants" if actor_role == "hr" else "applications"}, {"label": "Open calendar", "view": "calendar"}],
        )
    if actor_role == "hr" and re.search(r"\b(applicant|applicants|accept|reject|shortlist|candidate|candidates|review)\b", query):
        return _reply(
            "Open your Applicant inbox to inspect each submitted resume, skills coverage and application status. "
            "Compare the stated job requirements with the submitted evidence, then make your own review, shortlist, "
            "accept or reject decision, with a reason for either final decision. I do not assess personal worth or make hiring decisions.",
            actions=[{"label": "Review applicants", "view": "applicants"}],
        )
    if actor_role == "hr" and re.search(r"\b(interview|interviews|schedule|meeting|calendar)\b", query):
        return _reply(
            "Choose an applicant in your inbox and use Schedule interview. Enter a future date/time, duration "
            "and an HTTPS meeting link, or choose the generated Jitsi room-link option. The saved session appears in your calendar "
            "and the applicant's calendar with an in-app notification. Scheduling does not create a video room or send an email invitation; "
            "the external provider handles the room when participants open its link.",
            actions=[{"label": "Choose an applicant", "view": "applicants"}, {"label": "Open calendar", "view": "calendar"}],
        )
    if re.search(r"\b(application|applications|applied|calendar|interview|interviews)\b", query):
        if actor_role == "guest":
            return _reply("Guests can explore jobs and learning plans directly. Sign in as a job seeker to save a resume, submit demo applications and track interviews.", actions=[{"label": "Explore demo jobs", "view": "jobs"}, {"label": "Open my profile", "view": "profile"}])
        return _reply("Your applications page tracks submitted demo applications and their status. Interview sessions and relevant deadlines appear in your calendar. A scheduled interview can be confirmed or cancelled from that workflow.", actions=[{"label": "My applications", "view": "applications"}, {"label": "My calendar", "view": "calendar"}])

    supported = role_id is not None or exposure_intent or re.search(r"\b(skill|skills|gap|gaps|lacking|lack|missing|job|jobs|role|roles|career|careers|plan|planning|learn|learning|future|reskill|reskilling|survive|sdg|sdgs)\b", query)
    if not supported:
        return _reply(
            "I can explain your skill gaps, suggest catalogue roles, outline your learning plan, discuss "
            "AI task exposure and show relevant sources. I am a guided catalogue assistant, not a general-purpose "
            "language model. Try one of the suggested questions below.",
            actions=[{"label": "Explore roles", "view": "matches"}, {"label": "Inspect sources", "view": "sources"}],
        )

    # Do not quietly answer for the selected/top role when a different, unknown
    # occupation is explicitly requested. This is a catalogue coverage gap, not
    # a claim that research on that occupation does not exist anywhere.
    requested = re.search(r"\b(?:for|as)\s+(?:(?:a|an|the)\s+)?([a-z][a-z -]{1,75})[?.!]*$", query)
    generic_targets = {"me", "myself", "my role", "my job", "my career", "my future", "this role", "this job", "my selected role", "selected role", "all jobs", "workers"}
    if not named_role and requested and requested[1].strip() not in generic_targets and exposure_intent:
        return _reply(
            f"Published occupation-specific exposure data for {requested[1].strip()} is unavailable in this curated catalogue. "
            "I cannot give a validated job-replacement percentage or a personal job-loss probability, "
            "and I will not substitute a different catalogue occupation's score. Choose a supported role to inspect its research mapping and a reskilling plan.",
            actions=[{"label": "Explore supported roles", "view": "matches"}, {"label": "Inspect sources", "view": "sources"}],
        )

    safe_profile = {"skills": [], "interests": "", "weekly_hours": 6, "scenario": "moderate", **(profile or {})}
    result = match_profile(safe_profile, snapshot)
    matches = result["matches"]
    chosen = next((match for match in matches if match["id"] == role_id), matches[0])
    evidence = [*chosen["evidence"], _snapshot_source(snapshot)]
    role_action = {"label": f"Explore {chosen['title']}", "view": "matches", "role_id": chosen["id"]}
    context = _signal_context(snapshot)

    if exposure_intent:
        exposure = role_exposure(chosen["id"], safe_profile["scenario"])
        research = exposure["research_evidence"]
        source = research.get("source", {})
        research_citation = {"title": source.get("title", "Published exposure research"), "url": source.get("url", ""), "date": str(source.get("year", ""))}
        historical_requested = bool(re.search(r"\b(historical|history|2013|frey|osborne|computerisation|computerization)\b", query))
        historical_citations = [
            {"title": estimate["source"]["title"], "url": estimate["source"].get("mirror_url") or estimate["source"].get("url"), "date": str(estimate["source"]["year"])}
            for estimate in research.get("historical_estimates", [])
        ] if historical_requested else []
        steps = chosen["pathway"]["steps"][:2]
        resources = [resource for step in steps for resource in step["resources"][:1]]
        learning_citations = [{"title": f"{resource['title']} · {resource['provider']}", "url": resource["url"], "date": ""} for resource in resources]
        next_step = (
            "Next reskilling steps: " + "; ".join(f"{step['name']} ({step['hours']} introductory study hours)" for step in steps) + "."
            if steps else "Next step: practise the role's human strengths in a small project and seek feedback from a career adviser."
        )
        selection = "" if named_role else ("Your selected role. " if role_id else "Using your current top catalogue match. ")
        historical_context = f"{_historical_summary(research)}\n\n" if historical_requested else ""
        answer = (
            f"{chosen['title']}: {selection}I cannot give a validated job-replacement percentage or a personal job-loss probability.\n\n"
            f"{_research_summary(research)}\n\n"
            f"{historical_context}"
            "The moderate/fast scenario and editable six-task index are authored what-if assumptions. "
            "Changing them does not change the published study measure.\n\n"
            f"Authored task examples AI could assist with: {'; '.join(exposure['task_examples'])}.\n\n"
            f"Human strengths to develop: {'; '.join(exposure['human_strengths'])}.\n\n"
            f"{next_step} Study budgets are planning estimates, not a proficiency guarantee. "
            "O*NET supplies occupation context; it does not validate our authored task assumptions."
        )
        return _reply(answer, [research_citation, *historical_citations, *learning_citations, *evidence], [role_action, {"label": "Build a learning plan", "view": "pathway", "role_id": chosen["id"]}, {"label": "Inspect sources", "view": "sources"}], research_evidence=research)

    if re.search(r"\b(plan|planning|learn|learning|future|reskill|reskilling|survive)\b", query):
        plan = chosen["pathway"]
        steps = plan["steps"][:4]
        if not steps:
            answer = f"You cover the curated skill requirements for {chosen['title']}. Practise with a small project and seek feedback from a career adviser; catalogue coverage does not establish job readiness."
        else:
            answer = (
                f"For {chosen['title']}, start with this prerequisite-aware path at {safe_profile['weekly_hours']} hours/week:\n"
                + "\n".join(f"{index + 1}. {step['name']} — {step['hours']} introductory study hours, week {step['week_start']}–{step['week_end']}." for index, step in enumerate(steps))
                + (f"\nThe full plan has {len(plan['steps'])} steps." if len(plan["steps"]) > len(steps) else "")
                + f"\nEstimated full plan: {plan['total_hours']} hours over {plan['weeks']} weeks. "
                "These are study budgets, not a promise of professional proficiency."
            )
        resources = [resource for step in steps for resource in step["resources"][:1]]
        citations = [{"title": f"{resource['title']} · {resource['provider']}", "url": resource["url"], "date": ""} for resource in resources]
        return _reply(answer + f"\n\n{chosen['sdg_impact']}\n\n{context}", [*citations, *evidence], [{"label": "Open the full learning plan", "view": "pathway", "role_id": chosen["id"]}])

    if re.search(r"\b(skill|skills|gap|gaps|lacking|lack|missing)\b", query):
        missing = chosen["missing_skills"]
        covered = ", ".join(skill["name"] for skill in chosen["matched_skills"]) or "no selected skills from this role's curated requirements yet"
        gaps = ", ".join(skill["name"] for skill in missing)
        answer = (
            f"For {chosen['title']}, your selected strengths are: {covered}.\n\n"
            + (f"Catalogue skill gaps: {gaps}." if missing else "You cover all the curated skill requirements for this role.")
            + " These gaps compare a self-reported profile with our curated role requirements; they are not an assessment of your ability. "
            + f"Your weighted skills-coverage component is {chosen['components']['skill_coverage']} out of 100.\n\n{context}"
        )
        return _reply(answer, evidence, [role_action, {"label": "Learn the missing skills", "view": "pathway", "role_id": chosen["id"]}])

    if re.search(r"\b(sdg|sdgs)\b", query):
        return _reply(
            f"{chosen['title']} connects to SDGs {', '.join(str(value) for value in chosen['sdgs'])}. "
            f"{chosen['sdg_impact']} These are editorial links describing potential contribution through the work; "
            "they do not measure impact or imply UN endorsement.",
            [*evidence, *[{"title": f"UN Sustainable Development Goal {goal}", "url": f"https://sdgs.un.org/goals/goal{goal}", "date": ""} for goal in chosen["sdgs"]]],
            [{"label": "Explore this pathway's SDGs", "view": "pathway", "role_id": chosen["id"]}],
        )

    if named_role:
        return _reply(
            f"{chosen['title']}: {chosen['summary']} Your current catalogue fit score is {chosen['score']} out of 100, "
            f"with {len(chosen['missing_skills'])} curated skill gaps. {chosen['sdg_impact']} "
            "Ask about the role's skill gaps, learning plan or AI task exposure to explore further. " + context,
            evidence,
            [role_action, {"label": "Open this learning plan", "view": "pathway", "role_id": chosen["id"]}],
        )

    suggestions = matches[:3]
    answer = "Your strongest catalogue matches in this snapshot are:\n" + "\n".join(
        f"{index + 1}. {match['title']} — fit score {match['score']} out of 100; {len(match['missing_skills'])} curated skill gaps."
        for index, match in enumerate(suggestions)
    )
    answer += "\n\nScores combine skills coverage (65%), lexical interest relevance (20%) and observed source-sample support (15%). They are not hiring probabilities. " + context
    return _reply(answer, [source for match in suggestions for source in match["evidence"][:2]] + [_snapshot_source(snapshot)], [{"label": "Compare career matches", "view": "matches"}, {"label": "Find demo vacancies", "view": "jobs"}])
