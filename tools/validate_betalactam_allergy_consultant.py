from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CONSULTANT_PATH = Path("docs/rules/betalactam_allergy_consultant.json")
ALLOWED_STATUSES = {
    "draft_structure_pending_option_extraction",
    "draft_with_source_backed_options_pending_manual_review",
}


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"ERROR: invalid JSON in {path}: {exc}") from exc

    require(isinstance(data, dict), f"{path} must contain an object")
    return data


def validate_metadata(data: dict[str, Any]) -> None:
    metadata = data.get("metadata") or {}
    require(metadata.get("status") in ALLOWED_STATUSES, "metadata.status is invalid")
    require(metadata.get("consultationMode") == "syndrome_subsyndrome_allergy_options", "metadata.consultationMode is invalid")
    require(metadata.get("source") == "guide_topics.json", "metadata.source is invalid")
    require(metadata.get("manualReviewStatus") == "pending", "metadata.manualReviewStatus must remain pending")

    for field in (
        "clinicalUseAllowed",
        "clinicalDecisionSupportAllowed",
        "therapeuticRecommendationAllowed",
        "alternativeAntibioticRecommendationAllowed",
    ):
        require(metadata.get(field) is False, f"metadata.{field} must be false")


def validate_selectors(data: dict[str, Any]) -> None:
    selectors = data.get("selectors") or []
    require(isinstance(selectors, list), "selectors must be a list")
    by_id = {selector.get("id"): selector for selector in selectors if isinstance(selector, dict)}
    require("syndrome" in by_id, "missing syndrome selector")
    require("subsyndrome" in by_id, "missing subsyndrome selector")
    require(by_id["syndrome"].get("type") == "single_select_required", "syndrome selector type is invalid")
    require(by_id["subsyndrome"].get("type") == "single_select_optional", "subsyndrome selector type is invalid")
    require(by_id["subsyndrome"].get("dependsOn") == "syndrome", "subsyndrome must depend on syndrome")


def validate_records(data: dict[str, Any]) -> None:
    records = data.get("optionRecords")
    require(isinstance(records, list), "optionRecords must be a list")

    if not records:
        empty_state = data.get("emptyState") or {}
        require(empty_state.get("title"), "emptyState.title is required when optionRecords is empty")
        require(empty_state.get("message"), "emptyState.message is required when optionRecords is empty")
        return

    for index, record in enumerate(records):
        require(isinstance(record, dict), f"optionRecords[{index}] must be an object")
        for field in ("id", "syndrome", "allergyContext", "options", "source"):
            require(field in record, f"optionRecords[{index}] lacks {field}")
        require(isinstance(record["options"], list) and record["options"], f"optionRecords[{index}].options must be non-empty")
        for option_index, option in enumerate(record["options"]):
            require(isinstance(option, dict), f"optionRecords[{index}].options[{option_index}] must be an object")
            require(option.get("label"), f"optionRecords[{index}].options[{option_index}] lacks label")
            require(option.get("isTherapeuticRecommendation") is False, f"optionRecords[{index}].options[{option_index}] is not allowed")


def validate_safety(data: dict[str, Any]) -> None:
    hard_safety = data.get("hardSafetyRules") or {}
    app_behavior = data.get("appBehavior") or {}

    for field in (
        "mustNotRankOptions",
        "mustNotGenerateTherapeuticRecommendations",
        "mustNotInferOptionsFromAllergySeverity",
        "mustOnlyShowSourceBackedOptions",
        "mustShowPendingExtractionWhenNoRecords",
        "mustShowClinicalUseBlockedBanner",
        "mustPreserveSyndromeAndSubsyndromeContext",
    ):
        require(hard_safety.get(field) is True, f"hardSafetyRules.{field} must be true")

    require(app_behavior.get("mayRenderInResourcesConsultantsSection") is True, "appBehavior section flag must be true")
    require(app_behavior.get("mayRenderAsSyndromeSubsyndromeLookup") is True, "appBehavior lookup flag must be true")
    require(app_behavior.get("mayShowEmptyDraftState") is True, "appBehavior empty-state flag must be true")

    for field in (
        "mayStoreAnswersLocally",
        "mayUseAnswersToFilterTherapeuticRules",
        "mayUseAnswersToGenerateAntibioticAlternatives",
    ):
        require(app_behavior.get(field) is False, f"appBehavior.{field} must be false")


def main() -> None:
    require(CONSULTANT_PATH.exists(), f"missing {CONSULTANT_PATH}")
    data = load_json(CONSULTANT_PATH)
    validate_metadata(data)
    validate_selectors(data)
    validate_records(data)
    validate_safety(data)
    print("Beta-lactam allergy options contract OK")


if __name__ == "__main__":
    main()
