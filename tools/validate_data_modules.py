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
    DOCS_DIR / "microbiology" / "scope_catalog.json",
    DOCS_DIR / "microbiology" / "extraction_status_2025.json",
    DOCS_DIR / "microbiology" / "qa_enterobacterias_pending_2025.json",
]
ALLOWED_QUERY_DATASET_STATUSES = {
    "draft_pending_manual_review",
    "published_annual_map",
}


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


def get_scope_metadata_values(scope_catalog: dict[str, Any]) -> set[str]:
    values: set[str] = set()
    for scope in scope_catalog.get("scopes") or []:
        values.add(str(scope.get("id")))
        for metadata_value in scope.get("metadataScopeValues") or []:
            values.add(str(metadata_value))
    return values


def validate_scope_catalog(scope_catalog: dict[str, Any]) -> set[str]:
    require(scope_catalog.get("status") == "draft_pending_manual_review", "scope_catalog.status must remain draft_pending_manual_review")
    require(scope_catalog.get("clinicalDecisionSupport") is False, "scope_catalog.clinicalDecisionSupport must be false")
    require(scope_catalog.get("interactiveUseAllowed") is False, "scope_catalog.interactiveUseAllowed must be false")
    require(scope_catalog.get("queryPreviewAllowed") is True, "scope_catalog.queryPreviewAllowed must be true")
    require(isinstance(scope_catalog.get("scopes"), list) and scope_catalog["scopes"], "scope_catalog.scopes must be a non-empty list")

    seen_ids: set[str] = set()
    available_count = 0

    for index, scope in enumerate(scope_catalog["scopes"]):
        prefix = f"scope_catalog.scopes[{index}]"
        scope_id = scope.get("id")
        require(scope_id, f"{prefix} lacks id")
        require(scope_id not in seen_ids, f"{prefix}.id is duplicated: {scope_id}")
        seen_ids.add(str(scope_id))
        require(scope.get("label"), f"{prefix} lacks label")
        require(scope.get("status") in {"available_pending_manual_review", "not_published"}, f"{prefix}.status is invalid")
        require(isinstance(scope.get("datasetUseAllowed"), bool), f"{prefix}.datasetUseAllowed must be boolean")
        require(isinstance(scope.get("metadataScopeValues"), list) and scope["metadataScopeValues"], f"{prefix}.metadataScopeValues must be a non-empty list")
        require(scope.get("description"), f"{prefix} lacks description")

        if scope.get("datasetUseAllowed"):
            available_count += 1
            require(
                scope.get("status") == "available_pending_manual_review",
                f"{prefix} allows dataset use but is not available_pending_manual_review",
            )
        else:
            require(scope.get("status") == "not_published", f"{prefix} blocks dataset use but is not not_published")

    require("huvn" in seen_ids, "scope_catalog must include huvn")
    require(available_count >= 1, "scope_catalog must expose at least one pending available scope")

    query_rules = scope_catalog.get("queryRules") or {}
    require(query_rules.get("scopeIsRequired") is True, "scope_catalog.queryRules.scopeIsRequired must be true")
    require(query_rules.get("microorganismFilterRequired") is False, "scope_catalog.queryRules.microorganismFilterRequired must be false")
    require(query_rules.get("antibioticFilterRequired") is False, "scope_catalog.queryRules.antibioticFilterRequired must be false")
    require(query_rules.get("allowEmptyOptionalFilters") is True, "scope_catalog.queryRules.allowEmptyOptionalFilters must be true")
    require(query_rules.get("forbidScopeFallback") is True, "scope_catalog.queryRules.forbidScopeFallback must be true")
    require(
        query_rules.get("forbidUsingGlobalHuvnAsSpecificCenter") is True,
        "scope_catalog.queryRules.forbidUsingGlobalHuvnAsSpecificCenter must be true",
    )

    return get_scope_metadata_values(scope_catalog)


def validate_extraction_status(extraction_status: dict[str, Any], microbiology_map: dict[str, Any]) -> None:
    require(
        extraction_status.get("status") == "partial_extraction_pending_manual_review",
        "extraction_status.status must remain partial_extraction_pending_manual_review",
    )
    require(extraction_status.get("source"), "extraction_status lacks source")

    summary = extraction_status.get("summary") or {}
    require(summary.get("fullInteractiveMapExtracted") is False, "extraction_status must not claim fullInteractiveMapExtracted")
    require(summary.get("fullInteractiveMapReviewed") is False, "extraction_status must not claim fullInteractiveMapReviewed")
    require(summary.get("globalMicrobiologyMapComplete") is False, "extraction_status must not claim globalMicrobiologyMapComplete")
    require(summary.get("enterobacteriaAnnualMapPublished") is True, "extraction_status must claim published annual enterobacteria map after publication")
    require(summary.get("enterobacteriaCandidatePipelineReady") is True, "extraction_status must claim candidate pipeline readiness")
    require(summary.get("enterobacteriaDryRunAnnualMapValidatedInCi") is True, "extraction_status must claim dry-run validation")
    require(summary.get("enterobacteriaConsolidated") is True, "extraction_status must claim enterobacteriaConsolidated after publication")
    require(summary.get("enterobacteriaQaDraft") is True, "extraction_status must claim enterobacteriaQaDraft only after QA draft exists")
    require(summary.get("enterobacteriaQaPublished") is False, "extraction_status must not claim enterobacteriaQaPublished")
    require(summary.get("sectionCatalogCount") == len(microbiology_map.get("sectionCatalog", [])), "extraction_status.sectionCatalogCount mismatch")
    require(
        summary.get("generalRecordsInMicrobiologyMap") == len(microbiology_map.get("records", [])),
        "extraction_status.generalRecordsInMicrobiologyMap mismatch",
    )
    require(
        summary.get("resistanceMechanismRecords") == len(microbiology_map.get("resistanceMechanismRecords", [])),
        "extraction_status.resistanceMechanismRecords mismatch",
    )

    safe_behavior = extraction_status.get("safeAppBehavior") or {}
    require(safe_behavior.get("mustBlockClinicalDecisionSupport") is True, "extraction_status.safeAppBehavior must block clinical decision support")
    require(safe_behavior.get("mustNotRankAntibiotics") is True, "extraction_status.safeAppBehavior must block ranking")
    require(
        safe_behavior.get("mustNotGenerateTherapeuticRecommendations") is True,
        "extraction_status.safeAppBehavior must block therapeutic recommendations",
    )
    require(
        safe_behavior.get("mustNotUseGlobalHuvnAsSpecificCenter") is True,
        "extraction_status.safeAppBehavior must block HUVN global fallback to specific centers",
    )
    require(
        safe_behavior.get("mustNotDescribeEnterobacteriaCandidateAsFullMicrobiologyMap") is True,
        "extraction_status.safeAppBehavior must block describing enterobacteria as full map",
    )

    not_completed = extraction_status.get("notCompletedItems") or []
    require(isinstance(not_completed, list) and not_completed, "extraction_status.notCompletedItems must be a non-empty list")


def validate_enterobacteria_qa(qa_data: dict[str, Any]) -> None:
    metadata = qa_data.get("metadata") or {}
    require(metadata.get("status") == "qa_draft_pending_manual_review", "enterobacteria QA must remain qa_draft_pending_manual_review")
    require(metadata.get("clinicalUseAllowed") is False, "enterobacteria QA clinicalUseAllowed must be false")
    require(metadata.get("interactiveUseAllowed") is False, "enterobacteria QA interactiveUseAllowed must be false")
    require(metadata.get("therapeuticRecommendationAllowed") is False, "enterobacteria QA therapeuticRecommendationAllowed must be false")

    input_datasets = qa_data.get("inputDatasets") or []
    require(isinstance(input_datasets, list) and len(input_datasets) == 3, "enterobacteria QA must reference exactly three input passes")
    for index, dataset in enumerate(input_datasets):
        prefix = f"enterobacteria_qa.inputDatasets[{index}]"
        require(dataset.get("id"), f"{prefix} lacks id")
        dataset_url = dataset.get("url")
        require(dataset_url, f"{prefix} lacks url")
        require(resolve_dataset_path(str(dataset_url)).exists(), f"{prefix} points to missing file")
        require(isinstance(dataset.get("recordCountEstimated"), int), f"{prefix}.recordCountEstimated must be integer")
        require(isinstance(dataset.get("microorganismGroupsWithRecords"), int), f"{prefix}.microorganismGroupsWithRecords must be integer")

    aggregate = qa_data.get("aggregateDraft") or {}
    require(aggregate.get("passesAreConsolidated") is False, "enterobacteria QA must not claim passes are consolidated")
    require(aggregate.get("readyForAppQueryAsConsolidatedDataset") is False, "enterobacteria QA must not be ready for app query as consolidated dataset")
    require(aggregate.get("readyForClinicalUse") is False, "enterobacteria QA must not be ready for clinical use")

    checklist = qa_data.get("manualReviewChecklist") or []
    require(isinstance(checklist, list) and checklist, "enterobacteria QA manualReviewChecklist must be non-empty")
    for index, item in enumerate(checklist):
        require(item.get("status") == "pending", f"enterobacteria_qa.manualReviewChecklist[{index}] must remain pending")

    safe_behavior = qa_data.get("safeAppBehavior") or {}
    require(safe_behavior.get("mustNotUseAsConsolidatedDataset") is True, "enterobacteria QA must block consolidated use")
    require(safe_behavior.get("mustNotRankAntibiotics") is True, "enterobacteria QA must block ranking")
    require(safe_behavior.get("mustNotGenerateTherapeuticRecommendations") is True, "enterobacteria QA must block therapeutic recommendations")
    require(safe_behavior.get("mustShowPendingReview") is True, "enterobacteria QA must show pending review")


def validate_microbiology(manifest: dict[str, Any], microbiology_map: dict[str, Any], declared_scope_values: set[str]) -> None:
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

    published_maps = manifest.get("publishedAnnualMaps") or []
    require(isinstance(published_maps, list), "microbiology_manifest.publishedAnnualMaps must be a list if present")
    for index, published_map in enumerate(published_maps):
        prefix = f"microbiology_manifest.publishedAnnualMaps[{index}]"
        map_path = published_map.get("path")
        require(published_map.get("id"), f"{prefix} lacks id")
        require(published_map.get("title"), f"{prefix} lacks title")
        require(isinstance(map_path, str) and map_path.endswith(".json"), f"{prefix}.path must point to JSON")
        require((DOCS_DIR / map_path).exists(), f"{prefix}.path points to missing file: {map_path}")
        require(published_map.get("isFullMicrobiologyMap") is False, f"{prefix} must not claim full map status")
        require(published_map.get("clinicalDecisionSupportAllowed") is False, f"{prefix} must block CDS")
        require(published_map.get("therapeuticRecommendationAllowed") is False, f"{prefix} must block therapeutic recommendations")

    section_catalog = microbiology_map.get("sectionCatalog") or []
    require(isinstance(section_catalog, list), "microbiology_map_2025.sectionCatalog must be a list")

    for index, section in enumerate(section_catalog):
        prefix = f"microbiology_map_2025.sectionCatalog[{index}]"
        require(section.get("id"), f"{prefix} lacks id")
        require(section.get("title"), f"{prefix} lacks title")
        require(section.get("printedPage"), f"{prefix} lacks printedPage")
        require(section.get("pdfPage"), f"{prefix} lacks pdfPage")
        section_scope = section.get("scope")
        require(section_scope, f"{prefix} lacks scope")
        require(str(section_scope) in declared_scope_values, f"{prefix}.scope is not declared in scope_catalog: {section_scope}")
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


def validate_query_dataset_metadata(dataset: dict[str, Any], dataset_data: Any, declared_scope_values: set[str]) -> None:
    dataset_id = str(dataset.get("id"))
    dataset_status = dataset.get("status")
    if not isinstance(dataset_data, dict):
        return

    if dataset_id == "antibiotic_abbreviations_2025":
        require(isinstance(dataset_data.get("abbreviations"), list), "antibiotic_abbreviations_2025 must contain abbreviations[]")
        return

    metadata = dataset_data.get("metadata") or {}
    if dataset_status == "published_annual_map":
        require(metadata.get("status") == "published_annual_map", f"{dataset_id}.metadata.status must be published_annual_map")
        require(metadata.get("appConsultationAllowed") is True, f"{dataset_id}.metadata.appConsultationAllowed must be true")
        require(metadata.get("clinicalUseAllowed") is False, f"{dataset_id}.metadata.clinicalUseAllowed must be false")
        require(metadata.get("clinicalDecisionSupportAllowed") is False, f"{dataset_id}.metadata.clinicalDecisionSupportAllowed must be false")
        require(metadata.get("therapeuticRecommendationAllowed") is False, f"{dataset_id}.metadata.therapeuticRecommendationAllowed must be false")
    else:
        require(metadata.get("interactiveUseAllowed") is False, f"{dataset_id}.metadata.interactiveUseAllowed must be false")

    scope = metadata.get("scope")
    if scope is not None:
        require(str(scope) in declared_scope_values, f"{dataset_id}.metadata.scope is not declared in scope_catalog: {scope}")


def validate_microbiology_query_manifest(data: dict[str, Any], declared_scope_values: set[str]) -> None:
    require(data.get("status") == "draft_pending_manual_review", "microbiology_query_manifest.status must remain draft_pending_manual_review")
    require(data.get("clinicalDecisionSupport") is False, "microbiology_query_manifest.clinicalDecisionSupport must be false")
    require(data.get("interactiveUseAllowed") is False, "microbiology_query_manifest.interactiveUseAllowed must be false")
    require(data.get("queryPreviewAllowed") is True, "microbiology_query_manifest.queryPreviewAllowed must be true")
    require(data.get("therapeuticRecommendationAllowed") is False, "microbiology_query_manifest.therapeuticRecommendationAllowed must be false")
    require(data.get("scopeCatalogUrl") == "microbiology/scope_catalog.json", "microbiology_query_manifest.scopeCatalogUrl must point to scope_catalog.json")
    require(
        data.get("extractionStatusUrl") == "microbiology/extraction_status_2025.json",
        "microbiology_query_manifest.extractionStatusUrl must point to extraction_status_2025.json",
    )
    require(isinstance(data.get("datasets"), list) and data["datasets"], "microbiology_query_manifest.datasets must be a non-empty list")
    require(isinstance(data.get("supportedFilters"), list) and data["supportedFilters"], "microbiology_query_manifest.supportedFilters must be a non-empty list")

    supported_filters = data.get("supportedFilters") or []
    scope_filter = next((item for item in supported_filters if item.get("id") == "scope"), None)
    require(scope_filter is not None, "microbiology_query_manifest.supportedFilters must include scope")
    require(scope_filter.get("type") == "single_select_required", "scope filter must be single_select_required")
    require(scope_filter.get("valuesFrom") == "scope_catalog.scopes", "scope filter must read from scope_catalog.scopes")

    for filter_id in ("microorganism", "antibiotic"):
        filter_item = next((item for item in supported_filters if item.get("id") == filter_id), None)
        require(filter_item is not None, f"microbiology_query_manifest.supportedFilters must include {filter_id}")
        require(str(filter_item.get("type", "")).endswith("_optional"), f"{filter_id} filter must be optional")

    query_behavior = data.get("queryBehavior") or {}
    require(query_behavior.get("scopeIsRequired") is True, "queryBehavior.scopeIsRequired must be true")
    require(query_behavior.get("microorganismFilterRequired") is False, "queryBehavior.microorganismFilterRequired must be false")
    require(query_behavior.get("antibioticFilterRequired") is False, "queryBehavior.antibioticFilterRequired must be false")
    require(query_behavior.get("allowEmptyOptionalFilters") is True, "queryBehavior.allowEmptyOptionalFilters must be true")
    require(query_behavior.get("forbidScopeFallback") is True, "queryBehavior.forbidScopeFallback must be true")
    require(query_behavior.get("forbidUsingGlobalHuvnAsSpecificCenter") is True, "queryBehavior.forbidUsingGlobalHuvnAsSpecificCenter must be true")

    for index, dataset in enumerate(data["datasets"]):
        prefix = f"microbiology_query_manifest.datasets[{index}]"
        dataset_url = dataset.get("url")
        require(dataset.get("id"), f"{prefix} lacks id")
        require(dataset.get("title"), f"{prefix} lacks title")
        require(dataset_url, f"{prefix} lacks url")
        require(dataset.get("status") in ALLOWED_QUERY_DATASET_STATUSES, f"{prefix} has invalid status")
        require(dataset.get("clinicalUseAllowed") is False, f"{prefix}.clinicalUseAllowed must be false")
        require(dataset.get("therapeuticRecommendationAllowed", False) is False, f"{prefix}.therapeuticRecommendationAllowed must be false")

        if dataset.get("status") == "published_annual_map":
            require(dataset.get("appConsultationAllowed") is True, f"{prefix}.appConsultationAllowed must be true")
            require(dataset.get("isFullMicrobiologyMap") is False, f"{prefix}.isFullMicrobiologyMap must be false")
            require(dataset.get("clinicalDecisionSupportAllowed") is False, f"{prefix}.clinicalDecisionSupportAllowed must be false")

        dataset_path = resolve_dataset_path(str(dataset_url))
        require(dataset_path.exists(), f"{prefix} points to missing file: {dataset_path}")
        dataset_data = load_json(dataset_path)
        validate_query_dataset_metadata(dataset, dataset_data, declared_scope_values)

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
    scope_catalog = load_json(DOCS_DIR / "microbiology" / "scope_catalog.json")
    extraction_status = load_json(DOCS_DIR / "microbiology" / "extraction_status_2025.json")
    enterobacteria_qa = load_json(DOCS_DIR / "microbiology" / "qa_enterobacterias_pending_2025.json")

    validate_recommendation_rules(recommendation_rules)
    validate_allergy_rules(allergy_rules)
    validate_dose_calculators(dose_calculators)
    validate_scores(scores)
    declared_scope_values = validate_scope_catalog(scope_catalog)
    validate_microbiology(microbiology_manifest, microbiology_map, declared_scope_values)
    validate_extraction_status(extraction_status, microbiology_map)
    validate_enterobacteria_qa(enterobacteria_qa)
    validate_microbiology_query_manifest(microbiology_query_manifest, declared_scope_values)

    print("Data modules OK")
    print(f"Recommendation rules: {len(recommendation_rules.get('rules', []))}")
    print(f"Allergy rules: {len(allergy_rules.get('rules', []))}")
    print(f"Dose calculators: {len(dose_calculators.get('calculators', []))}")
    print(f"Scores: {len(scores.get('scores', []))}")
    print(f"Microbiology records: {len(microbiology_map.get('records', []))}")
    print(f"Microbiology sections: {len(microbiology_map.get('sectionCatalog', []))}")
    print(f"Microbiology resistance mechanism records: {len(microbiology_map.get('resistanceMechanismRecords', []))}")
    print(f"Microbiology query datasets: {len(microbiology_query_manifest.get('datasets', []))}")
    print(f"Microbiology scopes: {len(scope_catalog.get('scopes', []))}")
    print(f"Microbiology extraction status: {extraction_status.get('status')}")
    print(f"Enterobacteria QA status: {enterobacteria_qa.get('metadata', {}).get('status')}")


if __name__ == "__main__":
    main()
