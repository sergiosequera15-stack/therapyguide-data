from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DOCS_DIR = Path("docs")
DATA_MODULES_PATH = DOCS_DIR / "data_modules.json"
ALLOWED_MICROBIOLOGY_STATUSES = {
    "draft_pending_manual_review",
    "partial_published_annual_map_available",
}


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"ERROR: invalid JSON in {path}: {exc}") from exc


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"ERROR: {message}")


def require_json_url(relative_url: str, field_name: str) -> None:
    require(relative_url.endswith(".json"), f"{field_name} must point to a JSON file")
    path = DOCS_DIR / relative_url
    require(path.exists(), f"{field_name} points to missing file: {path}")
    load_json(path)


def main() -> None:
    require(DATA_MODULES_PATH.exists(), f"missing {DATA_MODULES_PATH}")
    data_modules = load_json(DATA_MODULES_PATH)

    modules = data_modules.get("modules") or {}
    require(isinstance(modules, dict), "data_modules.modules must be an object")

    microbiology = modules.get("microbiology") or {}
    require(isinstance(microbiology, dict), "data_modules.modules.microbiology must be an object")

    require(microbiology.get("status") in ALLOWED_MICROBIOLOGY_STATUSES, "microbiology.status is invalid")
    require(microbiology.get("queryPreviewAllowed") is True, "microbiology.queryPreviewAllowed must be true")
    require(microbiology.get("interactiveUseAllowed") is False, "microbiology.interactiveUseAllowed must be false")
    require(microbiology.get("clinicalDecisionSupport") is False, "microbiology.clinicalDecisionSupport must be false")
    require(microbiology.get("therapeuticRecommendationAllowed", False) is False, "microbiology.therapeuticRecommendationAllowed must be false")

    required_urls = {
        "manifestUrl": "microbiology/microbiology_manifest.json",
        "queryManifestUrl": "microbiology/microbiology_query_manifest.json",
        "scopeCatalogUrl": "microbiology/scope_catalog.json",
        "extractionStatusUrl": "microbiology/extraction_status_2025.json",
        "currentMapUrl": "microbiology/microbiology_map_2025.json",
        "updatePolicyUrl": "microbiology/update_policy.json",
        "antibioticAbbreviationsUrl": "microbiology/antibiotic_abbreviations_2025.json",
    }

    for field_name, expected_url in required_urls.items():
        actual_url = microbiology.get(field_name)
        require(actual_url == expected_url, f"microbiology.{field_name} must be {expected_url}, got {actual_url}")
        require_json_url(str(actual_url), f"microbiology.{field_name}")

    published_annual_maps = microbiology.get("publishedAnnualMaps") or {}
    require(isinstance(published_annual_maps, dict), "microbiology.publishedAnnualMaps must be an object")
    published_enterobacteria_url = published_annual_maps.get("huvnEnterobacteria2025Url")
    require(
        published_enterobacteria_url == "microbiology/published/huvn_enterobacterias_2025.json",
        "microbiology.publishedAnnualMaps.huvnEnterobacteria2025Url is invalid",
    )
    require_json_url(str(published_enterobacteria_url), "microbiology.publishedAnnualMaps.huvnEnterobacteria2025Url")

    susceptibility_tables = microbiology.get("susceptibilityTables") or {}
    require(isinstance(susceptibility_tables, dict), "microbiology.susceptibilityTables must be an object")

    required_susceptibility_urls = {
        "huvnGramNegativeNonEnterobacteriaUrl": "microbiology/susceptibility_huvn_bgn_non_enterobacterias_2025.json",
        "huvnGramNegativeEnterobacteriaFirstPassUrl": "microbiology/susceptibility_huvn_bgn_enterobacterias_2025.json",
        "huvnGramNegativeEnterobacteriaSecondPassUrl": "microbiology/susceptibility_huvn_bgn_enterobacterias_second_pass_2025.json",
        "huvnGramNegativeEnterobacteriaThirdPassUrl": "microbiology/susceptibility_huvn_bgn_enterobacterias_third_pass_2025.json",
    }

    for field_name, expected_url in required_susceptibility_urls.items():
        actual_url = susceptibility_tables.get(field_name)
        require(actual_url == expected_url, f"microbiology.susceptibilityTables.{field_name} must be {expected_url}, got {actual_url}")
        require_json_url(str(actual_url), f"microbiology.susceptibilityTables.{field_name}")

    print("Data module index OK")
    print(f"Data modules version: {data_modules.get('version')}")
    print("Microbiology scope catalog, extraction status and partial annual maps exposed")


if __name__ == "__main__":
    main()
