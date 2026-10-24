"""Cited occupational GenAI exposure, separate from editable planning assumptions.

Only the six published ISCO-08 records used by this catalogue are distributed.
Their means are descriptive technical-potential indices, not job-loss forecasts.
The O*NET-to-ISCO mappings are our explicit editorial proxies. Neither scenarios
nor user-authored task assumptions enter this adapter.
"""

from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import json
import math
from pathlib import Path
import re
from urllib.parse import urlsplit

from .catalog import ROLES


EVIDENCE_PATH = Path(__file__).resolve().parent.parent / "data" / "exposure_evidence.json"
ROLE_MAP = {role["id"]: role for role in ROLES}


def _https_url(value):
    if not isinstance(value, str):
        return False
    try:
        parsed = urlsplit(value)
        return parsed.scheme == "https" and bool(parsed.hostname) and not parsed.username and not parsed.password
    except ValueError:
        return False


def _unit_interval(value):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and 0 <= value <= 1 and math.isfinite(value)


def validate_exposure_data(data):
    """Reject incomplete or contradictory source snapshots before serving numbers."""
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValueError("Unsupported occupational exposure evidence schema.")
    try:
        source = data["source"]
        provenance = data["provenance"]
        methodology = data["methodology"]
        if not all(source.get(key) for key in ("title", "authors", "publisher", "year", "citation", "accessed_at")):
            raise ValueError("Exposure citation is incomplete.")
        if not all(_https_url(source.get(key)) for key in ("url", "dataset_url")):
            raise ValueError("Exposure source URLs must be public HTTPS URLs.")
        if not re.fullmatch(r"[0-9a-f]{40}", provenance.get("repository_commit", "")):
            raise ValueError("Exposure source must identify an immutable repository commit.")
        if not re.fullmatch(r"[0-9a-f]{64}", provenance.get("source_file_sha256", "")):
            raise ValueError("Exposure source must identify the original workbook checksum.")
        if provenance["repository_commit"] not in provenance.get("download_url", "") or not _https_url(provenance.get("download_url")):
            raise ValueError("Exposure workbook download must be pinned to its cited commit.")
        if not all(data["scope"].get(key) for key in ("geography", "population", "time_horizon")):
            raise ValueError("Exposure geography, population and horizon are required.")
        if methodology["source_field"] != "mean_score_2025" or methodology["is_probability"] is not False:
            raise ValueError("This adapter serves the published mean exposure index, never a probability.")
        if not methodology["limitations"] or not methodology["licence"]["adaptation_disclaimer"]:
            raise ValueError("Exposure limitations and reuse attribution are required.")
        occupations = data["occupations"]
        mappings = data["mappings"]
        if not isinstance(occupations, dict) or not isinstance(mappings, dict):
            raise ValueError("Exposure occupations and mappings must be objects.")
        for code, row in occupations.items():
            if not re.fullmatch(r"\d{4}", code) or row["code"] != code or not row["title"]:
                raise ValueError("Exposure occupation code or title is invalid.")
            if not _unit_interval(row["mean_score_2025"]) or not _unit_interval(row["SD_2025"]):
                raise ValueError("Published exposure mean and task standard deviation must be bounded numbers.")
            if not row["potential25"] or not row["source_rows"]:
                raise ValueError("Exposure category and source row locators are required.")
            if any(type(number) is not int or number < 2 for number in row["source_rows"]):
                raise ValueError("Exposure workbook row locators are invalid.")
            if row["task_count"] != len(row["source_rows"]):
                raise ValueError("Exposure task counts must match source row locators.")
        for role_id, mapping in mappings.items():
            if role_id not in ROLE_MAP or not mapping["rationale"] or not mapping["caveat"]:
                raise ValueError("Exposure mapping must name a known catalogue role and explain its limits.")
            code = mapping["source_code"]
            if code is None:
                if mapping["relation"] != "unavailable":
                    raise ValueError("Missing source occupations must be marked unavailable.")
            elif code not in occupations or mapping["relation"] not in {"exact", "broader_proxy"}:
                raise ValueError("Exposure mappings must refer to a published occupation.")
        historical = data["historical"]
        if historical["source"]["year"] != 2013 or not _https_url(historical["source"]["url"]):
            raise ValueError("Historical probabilities must identify their 2013 source.")
        if not historical["source"]["citation"] or not historical["provenance"]["limitation"]:
            raise ValueError("Historical source attribution and mirror limitations are required.")
        if not all(historical["scope"].get(key) for key in ("geography", "population", "time_horizon")):
            raise ValueError("Historical probability scope must be stated.")
        if not re.fullmatch(r"[0-9a-f]{64}", historical["provenance"].get("source_file_sha256", "")):
            raise ValueError("Historical paper checksum is required.")
        historical_commit = historical["provenance"].get("repository_commit", "")
        if not re.fullmatch(r"[0-9a-f]{40}", historical_commit) or historical_commit not in historical["provenance"]["download_url"]:
            raise ValueError("Historical paper mirror must be pinned to an immutable commit.")
        historical_keys = set()
        for estimate in historical["estimates"]:
            key = (estimate["catalog_role_id"], estimate["source_code"])
            if key in historical_keys or key[0] not in ROLE_MAP or not re.fullmatch(r"\d{2}-\d{4}", key[1]):
                raise ValueError("Historical source occupations must be distinct, valid mappings.")
            historical_keys.add(key)
            if not _unit_interval(estimate["probability"]) or not estimate["source_title"]:
                raise ValueError("Historical source probability is invalid.")
            if type(estimate["page"]) is not int or estimate["page"] < 1 or not estimate["rationale"] or not estimate["caveat"]:
                raise ValueError("Historical page locators and mapping caveats are required.")
            if estimate["relation"] not in {"historical_counterpart", "historical_suboccupation"}:
                raise ValueError("Historical mappings must distinguish counterpart and subgroup estimates.")
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError("Occupational exposure evidence is incomplete.") from error
    return True


@lru_cache(maxsize=1)
def _snapshot():
    data = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    validate_exposure_data(data)
    return data


def _historical_estimates(data, role):
    historical = data["historical"]
    results = []
    for row in historical["estimates"]:
        if row["catalog_role_id"] != role["id"]:
            continue
        percent = round(row["probability"] * 100, 4)
        provenance = deepcopy(historical["provenance"])
        provenance.update(page=row["page"], rank=row["rank"])
        results.append({
            "metric": {
                "name": historical["methodology"]["metric_name"],
                "value": row["probability"],
                "percent": percent,
                "display_value": f"{percent:g}%",
                "unit": "percent (historical source-model probability)",
                "is_probability": True,
                "is_current_genai_risk": False,
                "interpretation": historical["methodology"]["interpretation"],
            },
            "source": deepcopy(historical["source"]),
            "mapping": {
                "catalog_role_id": role["id"],
                "catalog_role_title": role["title"],
                "catalog_onet_code": role["source_url"].rsplit("/", 1)[-1],
                "source_classification": "2010 US SOC",
                "source_code": row["source_code"],
                "source_title": row["source_title"],
                "relation": row["relation"],
                "rationale": row["rationale"],
                "caveat": row["caveat"],
            },
            "scope": deepcopy(historical["scope"]),
            "uncertainty": {"text": historical["methodology"]["uncertainty"], "confidence_interval": None},
            "limitations": deepcopy(historical["methodology"]["limitations"]),
            "provenance": provenance,
            "licence": deepcopy(historical["methodology"]["licence"]),
        })
    return results


def build_exposure_evidence(role_id):
    """Return a published occupational index or an explicit mapping coverage gap.

    A result contains a metric only when a cited source occupation is mapped.
    A broader proxy's metric remains attributed to that source occupation; it
    does not become a measured estimate for the catalogue role or its workers.
    """
    if not isinstance(role_id, str) or role_id not in ROLE_MAP:
        raise ValueError("Choose a known catalogue role.")
    data = _snapshot()
    role = ROLE_MAP[role_id]
    original_mapping = data["mappings"].get(role_id, {
        "source_code": None,
        "relation": "unavailable",
        "rationale": "No reviewed source occupation mapping is available for this catalogue role.",
        "caveat": "A neighbouring occupation's score must not be presented as this role's estimate.",
    })
    source_code = original_mapping["source_code"]
    row = data["occupations"].get(source_code)
    mapping = {
        "catalog_role_id": role_id,
        "catalog_role_title": role["title"],
        "catalog_onet_code": role["source_url"].rsplit("/", 1)[-1],
        "catalog_source_url": role["source_url"],
        "source_classification": "ISCO-08 (four-digit unit group)",
        "source_code": source_code,
        "source_title": row["title"] if row else None,
        "relation": original_mapping["relation"],
        "label": "Broader occupation proxy" if original_mapping["relation"] == "broader_proxy" else ("Exact occupation mapping" if row else "No reviewed occupation mapping"),
        "rationale": original_mapping["rationale"],
        "caveat": original_mapping["caveat"],
        "authorship": "Application authors' editorial mapping; not an official O*NET–ISCO crosswalk or an ILO endorsement.",
    }
    result = {
        "schema_version": data["schema_version"],
        "dataset_id": data["dataset_id"],
        "status": "available" if row else "unavailable",
        "role_id": role_id,
        "metric": None,
        "source": deepcopy(data["source"]),
        "mapping": mapping,
        "scope": deepcopy(data["scope"]),
        "uncertainty": {
            "type": "unquantified_method_and_mapping_uncertainty",
            "text": data["methodology"]["uncertainty"],
            "mapping": original_mapping["caveat"],
            "task_score_sd": row["SD_2025"] if row else None,
            "task_score_sd_interpretation": "Published dispersion across the source occupation's task scores, not a confidence interval or prediction error.",
            "confidence_interval": None,
        },
        "limitations": deepcopy(data["methodology"]["limitations"]),
        "provenance": deepcopy(data["provenance"]),
        "licence": deepcopy(data["methodology"]["licence"]),
        "unavailable_reason": None if row else original_mapping["rationale"],
    }
    result["historical_estimates"] = _historical_estimates(data, role)
    result["historical_coverage"] = {
        "status": "available" if result["historical_estimates"] else "unavailable",
        "unavailable_reason": None if result["historical_estimates"] else data["historical"]["unavailable_reason"],
    }
    if row:
        result["metric"] = {
            "name": data["methodology"]["metric_name"],
            "source_field": data["methodology"]["source_field"],
            "value": row["mean_score_2025"],
            "minimum": 0,
            "maximum": 1,
            "percent": round(row["mean_score_2025"] * 100, 2),
            "display_value": f"{row['mean_score_2025'] * 100:g} / 100",
            "unit": "index points on a 0–100 scale",
            "interpretation": data["methodology"]["interpretation"],
            "is_probability": False,
            "is_share_of_tasks_or_jobs": False,
            "source_occupation_code": source_code,
            "source_occupation_title": row["title"],
            "category": row["potential25"],
            "task_count": row["task_count"],
        }
        result["provenance"]["source_rows"] = deepcopy(row["source_rows"])
    else:
        result["provenance"]["source_rows"] = []
    return result


def exposure_methodology():
    """Return the reviewable, redistributable citation, method and coverage report."""
    data = _snapshot()
    return {
        "schema_version": data["schema_version"],
        "dataset_id": data["dataset_id"],
        "source": deepcopy(data["source"]),
        "scope": deepcopy(data["scope"]),
        "methodology": deepcopy(data["methodology"]),
        "provenance": deepcopy(data["provenance"]),
        "historical": deepcopy(data["historical"]),
        "coverage": [build_exposure_evidence(role["id"]) for role in ROLES],
    }
