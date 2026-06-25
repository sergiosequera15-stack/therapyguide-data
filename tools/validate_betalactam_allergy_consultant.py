from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CONSULTANT_PATH = Path("docs/rules/betalactam_allergy_consultant.json")
ALLOWED_STATUSES = {
    "draft_structure_pending_option_extraction",
    "draft_with_source_backed_options_pending_manual_review",
}
ALLOWED_SOURCES = {
    "guide_topics.json",
    "betalactam_allergy_options_master_table_draft.json",
}
FALSE_METADATA_FIELDS = (
    "clinicalUseAllowed",
    "clinicalDecisionSupportAllowed",
    "therapeuticRecommendationAllowed",
    "alternativeAntibioticRecommendationAllowed",
)
FALSE_RECORD_FIELDS = (
    "clinicalUseAllowed",
    "clinicalDecisionSupportAllowed",
    "therapeuticRecommendationAllowed",
    "alternativeAntibioticRecommendationAllowed",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"ERROR: {message}")


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(data, dict), f"{path} must contain an object")
    return data


def validate_metadata(data: dict[str, Any]) -> None:
    metadata = data.get("metadata") or {}
    require(metadata.get("status") in ALLOWED_STATUSES, "invalid metadata.status")
    require(metadata.get("consultationMode") == "syndrome_subsyndrome_allergy_options", "invalid consultationMode")
    require(metadata.get("source") in ALLOWED_SOURCES, "invalid metadata.source")
    require(metadata.get("manualReviewStatus") in {"pending", "accepted_for_draft_display_not_clinical_use"}, "invalid manualReviewStatus")
    for field in FALSE_METADATA_FIELDS:
        require(metadata.get(field) is False, f"metadata.{field} must be false")
    if metadata.get("source") == "betalactam_allergy_options_master_table_draft.json":
        require(metadata.get("masterTableSchema") == "compact_rows_v2", "invalid masterTableSchema")
        require(metadata.get("masterTableRowCount") == 76, "invalid masterTableRowCount")
        require(metadata.get("optionRecordCount") == 76, "invalid optionRecordCount")
        require(metadata.get("readyForAppConsultant") is False, "readyForAppConsultant must be false")
        require(metadata.get("doseDisplayMode") == "show_all_available_source_text_unstructured", "invalid doseDisplayMode")


def validate_selectors(data: dict[str, Any]) -> None:
    selectors = data.get("selectors") or []
    require(isinstance(selectors, list), "selectors must be a list")
    by_id = {selector.get("id"): selector for selector in selectors if isinstance(selector, dict)}
    require(by_id.get("syndrome", {}).get("type") == "single_select_required", "missing syndrome selector")
    require(by_id.get("subsyndrome", {}).get("dependsOn") == "syndrome", "invalid subsyndrome selector")


def validate_records(data: dict[str, Any]) -> None:
    records = data.get("optionRecords")
    require(isinstance(records, list), "optionRecords must be a list")
    if not records:
        empty_state = data.get("emptyState") or {}
        require(empty_state.get("title"), "emptyState.title is required")
        require(empty_state.get("message"), "emptyState.message is required")
        return
    row_numbers: list[int] = []
    for index, record in enumerate(records):
        require(isinstance(record, dict), f"optionRecords[{index}] must be object")
        for field in ("id", "rowNumber", "syndrome", "allergyContext", "options", "source"):
            require(field in record, f"optionRecords[{index}] lacks {field}")
        for field in FALSE_RECORD_FIELDS:
            require(record.get(field) is False, f"optionRecords[{index}].{field} must be false")
        row_numbers.append(record["rowNumber"])
        source = record.get("source") or {}
        require(source.get("sourceTopicId"), f"optionRecords[{index}] lacks sourceTopicId")
        require(source.get("sourceUrl"), f"optionRecords[{index}] lacks sourceUrl")
        options = record.get("options")
        require(isinstance(options, list) and len(options) == 1, f"optionRecords[{index}] must have one option")
        option = options[0]
        require(option.get("sourceText"), f"optionRecords[{index}] lacks sourceText")
        require(option.get("displayText") == option.get("sourceText"), f"optionRecords[{index}] displayText mismatch")
        require(option.get("isTherapeuticRecommendation") is False, f"optionRecords[{index}] invalid option flag")
        require(option.get("isRanked") is False, f"optionRecords[{index}] ranked option")
        require(option.get("isDoseCalculator") is False, f"optionRecords[{index}] calculator option")
        require(option.get("structuredDoseAvailable") is False, f"optionRecords[{index}] structured dose exposed")
    require(sorted(row_numbers) == list(range(1, 77)), "rowNumber values must be 1..76")


def validate_safety(data: dict[str, Any]) -> None:
    hard_safety = data.get("hardSafetyRules") or {}
    app_behavior = data.get("appBehavior") or {}
    for field in (
        "mustNotRankOptions",
        "mustNotGenerateTherapeuticRecommendations",
        "mustNotInferOptionsFromAllergySeverity",
        "mustOnlyShowSourceBackedOptions",
        "mustShowClinicalUseBlockedBanner",
        "mustPreserveSyndromeAndSubsyndromeContext",
    ):
        require(hard_safety.get(field) is True, f"hardSafetyRules.{field} must be true")
    require(app_behavior.get("mayRenderInResourcesConsultantsSection") is True, "section render flag must be true")
    require(app_behavior.get("mayRenderAsSyndromeSubsyndromeLookup") is True, "lookup render flag must be true")
    for field in ("mayStoreAnswersLocally", "mayUseAnswersToFilterTherapeuticRules", "mayUseAnswersToGenerateAntibioticAlternatives"):
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
