from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

DOCS_DIR = Path("docs")

REQUIRED_FILES = [
    DOCS_DIR / "rules" / "recommendation_rules.json",
    DOCS_DIR / "rules" / "allergy_rules.json",
    DOCS_DIR / "rules" / "rule_manifest.json",
    DOCS_DIR / "rules" / "rule_validation_report.json",
    DOCS_DIR / "tools" / "scores.json",
    DOCS_DIR / "tools" / "dose_calculators.json",
    DOCS_DIR / "tools" / "tool_validation_report.json",
    DOCS_DIR / "microbiology" / "microbiology_manifest.json",
    DOCS_DIR / "microbiology" / "microbiology_map_2025.json",
    DOCS_DIR / "microbiology" / "microbiology_query_manifest.json",
]


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"ERROR: invalid JSON in {path}: {exc}") from exc


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"ERROR: {message}")


def resolve_dataset_path(dataset_url: str) -> Path:
    relative_path = dataset_url.split("#", 1)[0]
    require(relative_path.endswith(".json"), f"dataset url must point to a JSON file: {dataset_url}")
    return DOCS_DIR / relative_path


def validate_recommendation_rules(data: dict[str, Any]) -> None:
    require(isinstance(data.get("rules"), list), "recommendation_rules.json must contain rules[]")

    for index, rule in enumerate(data["rules"]):
        prefix = f"recommendation_rules[{index}]"
        require(rule.get("id"), f"{prefix} lacks id")
        require(rule.get("title"), f"{prefix} lacks title")
        require(rule.get("population"), f"{prefix} lacks population")
        require(rule.get("syndrome"), f"{prefix} lacks syndrome")
        source = rule.get("source") or {}
        require(source.get("sourceUrl"), f"{prefix} lacks source.sourceUrl")
        require(source.get("sourceTopicId"), f"{prefix} lacks source.sourceTopicId")

        allergy_alternatives = rule.get("betalactamAllergyAlternative") or []
        require(
            isinstance(allergy_alternatives, list),
            f"{prefix}.betalactamAllergyAlternative must be a list",
        )

        for allergy_index, alternative in enumerate(allergy_alternatives):
            require(
                alternative.get("source") or source.get("sourceUrl"),
                f"{prefix}.betalactamAllergyAlternative[{allergy_index}] lacks source context",
            )


def validate_allergy_rules(data: dict[str, Any]) -> None:
    question = data.get("allergyQuestion") or {}
    options = question.get("options") or []
    option_ids = {option.get("id") for option in options}

    require(question.get("id") == "betalactam_allergy", "allergyQuestion.id must be betalactam_allergy")
    require("no" in option_ids, "allergy options must include no")
    require("unknown" in option_ids, "allergy options must include unknown")
    require(isinstance(data.get("rules"), list), "allergy_rules.json must contain rules[]")


def validate_dose_calculators(data: dict[str, Any]) -> None:
    calculators = data.get("calculators") or []
    require(isinstance(calculators, list), "dose_calculators.json calculators must be a list")

    for index, calculator in enumerate(calculators):
        prefix = f"dose_calculators[{index}]"
        require(calculator.get("id"), f"{prefix} lacks id")
        require(calculator.get("title"), f"{prefix} lacks title")
        require(calculator.get("type"), f"{prefix} lacks type")
        require(isinstance(calculator.get("inputs"), list), f"{prefix} lacks inputs[]")
        require(isinstance(calculator.get("formula"), dict), f"{prefix} lacks formula")
        require(isinstance(calculator.get("output"), dict), f"{prefix} lacks output")

        source = calculator.get("source") or {}
        validation = calculator.get("validation") or {}
        status = validation.get("status")
        test_cases = validation.get("testCases") or []
        enabled = bool(calculator.get("enabled"))

        if enabled:
            require(source.get("sourceUrl"), f"{prefix} is enabled but lacks source.sourceUrl")
            require(source.get("sourceText"), f"{prefix} is enabled but lacks source.sourceText")

        if status == "validated":
            require(test_cases, f"{prefix} is validated without testCases")


def validate_scores(data: dict[str, Any]) -> None:
    scores = data.get("scores") or []
    require(isinstance(scores, list), "scores.json scores must be a list")

    for index, score in enumerate(scores):
        prefix = f"scores[{index}]"
        require(score.get("id"), f"{prefix} lacks id")
        require(score.get("title"), f"{prefix} lacks title")
        validation = score.get("validation") or {}
        if validation.get("status") == "validated":
            require(validation.get("testCases"), f"{prefix} is validated without testCases")


def validate_microbiology(manifest: dict[str, Any], microbiology_map: dict[str, Any]) -> None:
    current_map = manifest.get("currentMap") or {}
    require(current_map.get("path"), "microbiology_manifest.currentMap lacks path")
    require(current_map.get("reviewStatus"), "microbiology_manifest.currentMap lacks reviewStatus")

    metadata = microbiology_map.get("metadata") or {}
    require(metadata.get("sourcePdf"), "microbiology_map_2025.metadata lacks sourcePdf")
    require(metadata.get("manualReviewStatus"), "microbiology_map_2025.metadata lacks manualReviewStatus")
    require(isinstance(microbiology_map.get("records"), list), "microbiology_map_2025.records must be a list")

    if microbiology_map.get("records"):
        require(
            metadata.get("manualReviewStatus") == "reviewed",
            "microbiology map has records but manualReviewStatus is not reviewed",
        )

    section_catalog = microbiology_map.get("sectionCatalog") or []
    require(isinstance(section_catalog, list), "microbiology_map_2025.sectionCatalog must be a list")

    for index, section in enumerate(section_catalog):
        prefix = f"microbiology_map_2025.sectionCatalog[{index}]"
        require(section.get("id"), f"{prefix} lacks id")
        require(section.get("title"), f"{prefix} lacks title")
        require(section.get("printedPage"), f"{prefix} lacks printedPage")
        require(section.get("pdfPage"), f"{prefix} lacks pdfPage")
        require(section.get("scope"), f"{prefix} lacks scope")
        require(section.get("contentType"), f"{prefix} lacks contentType")

    mechanism_records = microbiology_map.get("resistanceMechanismRecords") or []
    require(
        isinstance(mechanism_records, list),
        "microbiology_map_2025.resistanceMechanismRecords must be a list",
    )

    for index, record in enumerate(mechanism_records):
        prefix = f"microbiology_map_2025.resistanceMechanismRecords[{index}]"
        require(record.get("microorganism"), f"{prefix} lacks microorganism")
        require(record.get("resistanceMechanism"), f"{prefix} lacks resistanceMechanism")
        require(isinstance(record.get("count"), (int, float)), f"{prefix} lacks numeric count")
        require(isinstance(record.get("percent"), (int, float)), f"{prefix} lacks numeric percent")
        require(record.get("source"), f"{prefix} lacks source")
        review = record.get("review") or {}
        require(review.get("status"), f"{prefix} lacks review.status")

        if review.get("status") == "reviewed":
            require(review.get("reviewedAt"), f"{prefix} reviewed record lacks reviewedAt")


def validate_microbiology_query_manifest(data: dict[str, Any]) -> None:
    require(data.get("status") == "draft_pending_manual_review", "microbiology_query_manifest.status must remain draft_pending_manual_review")
    require(data.get("clinicalDecisionSupport") is False, "microbiology_query_manifest.clinicalDecisionSupport must be false")
    require(data.get("interactiveUseAllowed") is False, "microbiology_query_manifest.interactiveUseAllowed must be false")
    require(data.get("queryPreviewAllowed") is True, "microbiology_query_manifest.queryPreviewAllowed must be true")
    require(data.get("therapeuticRecommendationAllowed") is False, "microbiology_query_manifest.therapeuticRecommendationAllowed must be false")
    require(isinstance(data.get("datasets"), list) and data["datasets"], "microbiology_query_manifest.datasets must be a non-empty list")
    require(isinstance(data.get("supportedFilters"), list) and data["supportedFilters"], "microbiology_query_manifest.supportedFilters must be a non-empty list")

    for index, dataset in enumerate(data["datasets"]):
        prefix = f"microbiology_query_manifest.datasets[{index}]"
        dataset_url = dataset.get("url")
        require(dataset.get("id"), f"{prefix} lacks id")
        require(dataset.get("title"), f"{prefix} lacks title")
        require(dataset_url, f"{prefix} lacks url")
        require(dataset.get("status") == "draft_pending_manual_review", f"{prefix} must remain draft_pending_manual_review")
        require(dataset.get("clinicalUseAllowed") is False, f"{prefix}.clinicalUseAllowed must be false")

        dataset_path = resolve_dataset_path(str(dataset_url))
        require(dataset_path.exists(), f"{prefix} points to missing file: {dataset_path}")
        load_json(dataset_path)

    output_policy = data.get("queryOutputPolicy") or {}
    require(output_policy.get("mustNotGenerateTherapeuticRecommendations") is True, "queryOutputPolicy must block therapeutic recommendations")
    require(output_policy.get("mustWarnWhenNBelow") == 30, "queryOutputPolicy.mustWarnWhenNBelow must be 30")


def main() -> None:
    for path in REQUIRED_FILES:
        require(path.exists(), f"missing required data module file: {path}")

    recommendation_rules = load_json(DOCS_DIR / "rules" / "recommendation_rules.json")
    allergy_rules = load_json(DOCS_DIR / "rules" / "allergy_rules.json")
    dose_calculators = load_json(DOCS_DIR / "tools" / "dose_calculators.json")
    scores = load_json(DOCS_DIR / "tools" / "scores.json")
    microbiology_manifest = load_json(DOCS_DIR / "microbiology" / "microbiology_manifest.json")
    microbiology_map = load_json(DOCS_DIR / "microbiology" / "microbiology_map_2025.json")
    microbiology_query_manifest = load_json(DOCS_DIR / "microbiology" / "microbiology_query_manifest.json")

    validate_recommendation_rules(recommendation_rules)
    validate_allergy_rules(allergy_rules)
    validate_dose_calculators(dose_calculators)
    validate_scores(scores)
    validate_microbiology(microbiology_manifest, microbiology_map)
    validate_microbiology_query_manifest(microbiology_query_manifest)

    print("Data modules OK")
    print(f"Recommendation rules: {len(recommendation_rules.get('rules', []))}")
    print(f"Allergy rules: {len(allergy_rules.get('rules', []))}")
    print(f"Dose calculators: {len(dose_calculators.get('calculators', []))}")
    print(f"Scores: {len(scores.get('scores', []))}")
    print(f"Microbiology records: {len(microbiology_map.get('records', []))}")
    print(f"Microbiology sections: {len(microbiology_map.get('sectionCatalog', []))}")
    print(f"Microbiology resistance mechanism records: {len(microbiology_map.get('resistanceMechanismRecords', []))}")
    print(f"Microbiology query datasets: {len(microbiology_query_manifest.get('datasets', []))}")


if __name__ == "__main__":
    main()
