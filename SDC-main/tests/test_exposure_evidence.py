"""Published figures keep their definition, occupation and provenance attached."""

from copy import deepcopy
import json

import pytest

from career import exposure
from career.catalog import ROLES


EXPECTED_ILO = {
    "data-scientist": ("2120", "Mathematicians, Actuaries and Statisticians", .56, .09, 336, 345),
    "sustainability-specialist": ("2133", "Environmental Protection Professionals", .38, .04, 366, 372),
    "learning-development-specialist": ("2424", "Training and Staff Development Professionals", .41, .09, 804, 811),
    "computer-systems-analyst": ("2511", "Systems Analysts", .49, .05, 848, 854),
    "software-developer": ("2512", "Software Developers", .53, .07, 855, 862),
    "information-security-analyst": ("2529", "Database and Network Professionals Not Elsewhere Classified", .49, .06, 896, 903),
}


def source_snapshot():
    return json.loads(exposure.EVIDENCE_PATH.read_text(encoding="utf-8"))


def test_source_snapshot_has_attribution_immutable_provenance_and_full_catalog_coverage():
    data = source_snapshot()
    assert exposure.validate_exposure_data(data)
    assert set(data["mappings"]) == {role["id"] for role in ROLES}
    assert len(data["occupations"]) == 6
    assert data["source"]["year"] == 2025
    assert data["source"]["url"] == "https://doi.org/10.54394/HETP0387"
    assert data["provenance"]["repository_commit"] == "ce5fc25c2a0db2757c5bfa797c4cfc8b408431ea"
    assert data["provenance"]["source_file_sha256"] == "c1940b87e7293b1eb95b530b6d3da7cd806b61d217c4bff1e69372b2cff5c90a"
    assert data["methodology"]["licence"]["url"] == "https://creativecommons.org/licenses/by/4.0/"
    assert "has not been prepared, reviewed or endorsed" in data["methodology"]["licence"]["adaptation_disclaimer"]


@pytest.mark.parametrize("role_id,expected", EXPECTED_ILO.items())
def test_ilo_values_preserve_published_means_exact_source_rows_and_proxy_labels(role_id, expected):
    code, title, mean, sd, first_row, last_row = expected
    evidence = exposure.build_exposure_evidence(role_id)
    assert evidence["status"] == "available"
    assert evidence["mapping"]["source_code"] == code
    assert evidence["mapping"]["source_title"] == title
    assert evidence["mapping"]["relation"] == "broader_proxy"
    assert "editorial mapping" in evidence["mapping"]["authorship"]
    assert evidence["mapping"]["caveat"]
    assert evidence["metric"]["value"] == mean
    assert evidence["metric"]["percent"] == pytest.approx(mean * 100)
    assert evidence["metric"]["unit"] == "index points on a 0–100 scale"
    assert evidence["metric"]["is_probability"] is False
    assert evidence["metric"]["is_share_of_tasks_or_jobs"] is False
    assert evidence["uncertainty"]["task_score_sd"] == sd
    assert evidence["uncertainty"]["confidence_interval"] is None
    assert "not a confidence interval" in evidence["uncertainty"]["task_score_sd_interpretation"]
    assert evidence["provenance"]["source_rows"] == list(range(first_row, last_row + 1))
    assert evidence["metric"]["task_count"] == last_row - first_row + 1


@pytest.mark.parametrize("role_id", ["business-intelligence-analyst", "project-management-specialist"])
def test_ambiguous_occupation_mapping_returns_coverage_gap_never_an_inferred_percent(role_id):
    evidence = exposure.build_exposure_evidence(role_id)
    assert evidence["status"] == "unavailable"
    assert evidence["metric"] is None
    assert evidence["mapping"]["source_code"] is None
    assert evidence["mapping"]["relation"] == "unavailable"
    assert "No unambiguous" in evidence["unavailable_reason"]
    assert evidence["provenance"]["source_rows"] == []
    assert evidence["historical_estimates"] == []


def test_missing_reviewed_mapping_also_fails_closed(monkeypatch):
    data = source_snapshot()
    del data["mappings"]["software-developer"]
    monkeypatch.setattr(exposure, "_snapshot", lambda: data)
    result = exposure.build_exposure_evidence("software-developer")
    assert result["metric"] is None
    assert result["status"] == "unavailable"
    assert "No reviewed" in result["unavailable_reason"]


@pytest.mark.parametrize("role_id,entries", [
    ("computer-systems-analyst", [("15-1121", .0065, .65, 57)]),
    ("learning-development-specialist", [("13-1151", .014, 1.4, 58)]),
    ("software-developer", [("15-1132", .042, 4.2, 59), ("15-1133", .13, 13, 60)]),
])
def test_historical_probabilities_keep_the_2013_definition_and_exact_old_soc(role_id, entries):
    estimates = exposure.build_exposure_evidence(role_id)["historical_estimates"]
    assert len(estimates) == len(entries)
    for estimate, (code, probability, percent, page) in zip(estimates, entries):
        assert estimate["mapping"]["source_code"] == code
        assert estimate["mapping"]["source_classification"] == "2010 US SOC"
        assert estimate["metric"]["value"] == probability
        assert estimate["metric"]["percent"] == percent
        assert estimate["metric"]["is_probability"] is True
        assert estimate["metric"]["is_current_genai_risk"] is False
        assert estimate["source"]["year"] == 2013
        assert estimate["source"]["publication_date"] == "2013-09-17"
        assert estimate["provenance"]["page"] == page
        assert estimate["provenance"]["source_file_sha256"] == "1d0ef561ebef9ececda63403a40860aa172be953fe2b050d27de8987c9e852fc"
        assert "unspecified" in estimate["scope"]["time_horizon"]
        assert "third-party mirror" in " ".join(estimate["limitations"])
        assert estimate["uncertainty"]["confidence_interval"] is None


def test_historical_software_subgroups_are_separate_and_composite_security_group_is_not_substituted():
    software = exposure.build_exposure_evidence("software-developer")
    assert {row["mapping"]["relation"] for row in software["historical_estimates"]} == {"historical_suboccupation"}
    assert len(software["historical_estimates"]) == 2
    security = exposure.build_exposure_evidence("information-security-analyst")
    assert security["historical_estimates"] == []
    assert security["historical_coverage"]["status"] == "unavailable"
    assert security["historical_coverage"]["unavailable_reason"]


@pytest.mark.parametrize("change", [
    lambda data: data["occupations"]["2512"].update(mean_score_2025=1.1),
    lambda data: data["occupations"]["2512"].update(mean_score_2025=True),
    lambda data: data["occupations"]["2512"].update(mean_score_2025=float("nan")),
    lambda data: data["occupations"]["2512"].update(mean_score_2025=10 ** 500),
    lambda data: data["occupations"]["2512"].update(SD_2025=-.1),
    lambda data: data["occupations"]["2512"].update(task_count=1000),
    lambda data: data["source"].update(url="javascript:alert(1)"),
    lambda data: data["source"].update(citation=""),
    lambda data: data["provenance"].update(source_file_sha256=""),
    lambda data: data["provenance"].update(repository_commit="moving-branch-name"),
    lambda data: data["mappings"]["software-developer"].update(source_code="9999"),
    lambda data: data["methodology"].update(is_probability=True),
    lambda data: data["historical"]["source"].update(year=2025),
    lambda data: data["historical"]["estimates"][0].update(probability=-.1),
])
def test_incomplete_or_contradictory_source_data_is_rejected(change):
    data = source_snapshot()
    change(data)
    with pytest.raises(ValueError):
        exposure.validate_exposure_data(data)


def test_evidence_reports_are_json_serializable_independent_copies():
    result = exposure.build_exposure_evidence("software-developer")
    original = deepcopy(result)
    result["source"]["title"] = "Changed outside adapter"
    result["mapping"]["caveat"] = "Changed outside adapter"
    result["provenance"]["source_rows"].clear()
    result["historical_estimates"][0]["metric"]["percent"] = 100
    assert exposure.build_exposure_evidence("software-developer") == original
    report = exposure.exposure_methodology()
    assert len(report["coverage"]) == len(ROLES)
    assert len(report["historical"]["estimates"]) == 4
    json.dumps(report, allow_nan=False)


@pytest.mark.parametrize("role_id", ["missing-role", None, [], 1])
def test_unknown_role_never_yields_a_source_estimate(role_id):
    with pytest.raises(ValueError):
        exposure.build_exposure_evidence(role_id)


def test_planning_scenarios_and_editable_tasks_do_not_change_either_published_evidence_series():
    from career.assistant import role_exposure

    initial = role_exposure("software-developer", "moderate")
    fast = role_exposure("software-developer", "fast")
    assumptions = {task["id"]: 0 for task in initial["task_assessment"]["tasks"]}
    edited = role_exposure("software-developer", "fast", assumptions)
    assert initial["research_evidence"] == fast["research_evidence"] == edited["research_evidence"]
    assert edited["task_assessment"]["percentage"] == 0
    assert initial["task_assessment"]["percentage"] != edited["task_assessment"]["percentage"]
