from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MICROBIOLOGY_DIR = Path("docs") / "microbiology"
REQUIRED_SUSCEPTIBILITY_FILES = [
    MICROBIOLOGY_DIR / "susceptibility_huvn_bgn_non_enterobacterias_2025.json",
    MICROBIOLOGY_DIR / "susceptibility_huvn_bgn_enterobacterias_2025.json",
    MICROBIOLOGY_DIR / "susceptibility_huvn_bgn_enterobacterias_second_pass_2025.json",
    MICROBIOLOGY_DIR / "susceptibility_huvn_bgn_enterobacterias_third_pass_2025.json",
]
REQUIRED_DICTIONARY_FILES = [
    MICROBIOLOGY_DIR / "antibiotic_abbreviations_2025.json",
]
ENTEROBACTERIA_QA_FILE = MICROBIOLOGY_DIR / "qa_enterobacterias_pending_2025.json"
ENTEROBACTERIA_PRECONSOLIDATION_FILE = MICROBIOLOGY_DIR / "preconsolidation_enterobacterias_draft_2025.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"ERROR: {message}")


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"ERROR: invalid JSON in {path}: {exc}") from exc


def validate_utc_timestamp(value: Any, label: str) -> None:
    require(isinstance(value, str) and value.strip(), f"{label} must be a non-empty string")
    require(value.endswith("Z"), f"{label} must be UTC and end with Z")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SystemExit(f"ERROR: {label} is not valid ISO 8601: {value}") from exc
    offset = parsed.utcoffset()
    require(offset is not None and offset.total_seconds() == 0, f"{label} must be UTC")


def validate_dictionary_file(path: Path) -> set[str]:
    data = load_json(path)
    metadata = data.get("metadata") or {}
    abbreviations = data.get("abbreviations") or []
    review = data.get("review") or {}

    require(metadata.get("sourcePdf"), f"{path} lacks metadata.sourcePdf")
    require(metadata.get("manualReviewStatus") == "pending", f"{path} must remain pending before clinical use")
    require(isinstance(abbreviations, list) and abbreviations, f"{path} must contain abbreviations[]")
    require(review.get("status") == "pending", f"{path} review.status must be pending")

    codes: set[str] = set()
    for index, item in enumerate(abbreviations):
        prefix = f"{path.name}.abbreviations[{index}]"
        code = item.get("code")
        name = item.get("name")
        require(isinstance(code, str) and code.strip(), f"{prefix} lacks code")
        require(isinstance(name, str) and name.strip(), f"{prefix} lacks name")
        require(code not in codes, f"{path.name} duplicate abbreviation code: {code}")
        codes.add(code)

    return codes


def validate_susceptibility_file(path: Path, allowed_antibiotics: set[str]) -> list[dict[str, Any]]:
    data = load_json(path)
    metadata = data.get("metadata") or {}
    records = data.get("records") or []
    review = data.get("review") or {}

    require(metadata.get("sourcePdf"), f"{path} lacks metadata.sourcePdf")
    require(metadata.get("manualReviewStatus") == "pending", f"{path} must remain pending before clinical use")
    require(metadata.get("interactiveUseAllowed") is False, f"{path} must not be interactively enabled")
    require(isinstance(records, list) and records, f"{path} must contain records[]")
    require(review.get("status") == "pending", f"{path} review.status must be pending")

    normalized_records: list[dict[str, Any]] = []

    for index, record in enumerate(records):
        prefix = f"{path.name}.records[{index}]"
        microorganism = record.get("microorganism")
        require(isinstance(microorganism, str) and microorganism.strip(), f"{prefix} lacks microorganism")
        require(isinstance(record.get("isolatesTested"), int), f"{prefix} lacks integer isolatesTested")
        antibiotic = record.get("antibiotic")
        require(isinstance(antibiotic, str) and antibiotic, f"{prefix} lacks antibiotic")
        require(antibiotic in allowed_antibiotics, f"{prefix} antibiotic {antibiotic} missing from abbreviation dictionary")
        percent = record.get("susceptibilityPercent")
        require(isinstance(percent, (int, float)), f"{prefix} lacks numeric susceptibilityPercent")
        require(0 <= percent <= 100, f"{prefix} susceptibilityPercent out of range")

        normalized_records.append(
            {
                "sourceFile": path.name,
                "microorganism": microorganism.strip(),
                "isolatesTested": record["isolatesTested"],
                "antibiotic": antibiotic,
                "susceptibilityPercent": percent,
            }
        )

    return normalized_records


def validate_no_conflicting_duplicate_records(records: list[dict[str, Any]]) -> None:
    seen: dict[tuple[str, str], dict[str, Any]] = {}

    for record in records:
        key = (record["microorganism"], record["antibiotic"])
        previous = seen.get(key)

        if previous is None:
            seen[key] = record
            continue

        require(
            previous["isolatesTested"] == record["isolatesTested"]
            and previous["susceptibilityPercent"] == record["susceptibilityPercent"],
            "conflicting duplicate microbiology record: "
            f"{key[0]} / {key[1]} in {previous['sourceFile']} and {record['sourceFile']}",
        )


def group_records_by_key(records: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[(record["microorganism"], record["antibiotic"])].append(record)
    return grouped


def calculate_key_classes(records: list[dict[str, Any]]) -> tuple[set[tuple[str, str]], set[tuple[str, str]], set[tuple[str, str]]]:
    grouped = group_records_by_key(records)
    single_record_keys: set[tuple[str, str]] = set()
    duplicate_identical_keys: set[tuple[str, str]] = set()
    conflicting_keys: set[tuple[str, str]] = set()

    for key, key_records in grouped.items():
        value_pairs = {(record["isolatesTested"], record["susceptibilityPercent"]) for record in key_records}
        if len(key_records) == 1:
            single_record_keys.add(key)
        elif len(value_pairs) == 1:
            duplicate_identical_keys.add(key)
        else:
            conflicting_keys.add(key)

    return single_record_keys, duplicate_identical_keys, conflicting_keys


def validate_enterobacteria_qa_against_records(
    qa_path: Path,
    records: list[dict[str, Any]],
) -> None:
    require(qa_path.exists(), f"missing enterobacteria QA file: {qa_path}")
    qa_data = load_json(qa_path)
    metadata = qa_data.get("metadata") or {}
    input_datasets = qa_data.get("inputDatasets") or []
    aggregate = qa_data.get("aggregateDraft") or {}
    low_count_groups = qa_data.get("knownLowCountGroupsInExtractedRecords") or []

    require(metadata.get("status") == "qa_draft_pending_manual_review", "enterobacteria QA must remain draft pending manual review")
    require(metadata.get("clinicalUseAllowed") is False, "enterobacteria QA must not allow clinical use")
    require(metadata.get("interactiveUseAllowed") is False, "enterobacteria QA must not allow interactive use")
    require(metadata.get("therapeuticRecommendationAllowed") is False, "enterobacteria QA must not allow therapeutic recommendations")
    require(isinstance(input_datasets, list) and len(input_datasets) == 3, "enterobacteria QA must reference exactly three extraction passes")

    records_by_source: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        records_by_source.setdefault(str(record["sourceFile"]), []).append(record)

    qa_total_records = 0
    qa_total_organism_groups = 0
    source_files_from_qa: set[str] = set()

    for index, dataset in enumerate(input_datasets):
        prefix = f"enterobacteria_qa.inputDatasets[{index}]"
        dataset_url = dataset.get("url")
        require(isinstance(dataset_url, str) and dataset_url.endswith(".json"), f"{prefix}.url must point to json")
        source_file = Path(dataset_url).name
        source_files_from_qa.add(source_file)
        source_records = records_by_source.get(source_file) or []
        require(source_records, f"{prefix} points to a file with no validated records: {source_file}")

        source_organisms = {record["microorganism"] for record in source_records}
        require(dataset.get("recordCountEstimated") == len(source_records), f"{prefix}.recordCountEstimated does not match source record count")
        require(
            dataset.get("microorganismGroupsWithRecords") == len(source_organisms),
            f"{prefix}.microorganismGroupsWithRecords does not match source organism count",
        )

        qa_total_records += len(source_records)
        qa_total_organism_groups += len(source_organisms)

    require(aggregate.get("totalRecordCountEstimated") == qa_total_records, "enterobacteria QA totalRecordCountEstimated mismatch")
    require(
        aggregate.get("microorganismGroupsWithRecordsEstimated") == qa_total_organism_groups,
        "enterobacteria QA microorganismGroupsWithRecordsEstimated mismatch",
    )
    require(aggregate.get("passesAreConsolidated") is False, "enterobacteria QA must not claim passes are consolidated")
    require(
        aggregate.get("readyForAppQueryAsConsolidatedDataset") is False,
        "enterobacteria QA must not claim app-ready consolidated dataset status",
    )
    require(aggregate.get("readyForClinicalUse") is False, "enterobacteria QA must not claim clinical-use readiness")

    expected_low_count_groups = {
        (record["microorganism"], record["isolatesTested"])
        for record in records
        if record["sourceFile"] in source_files_from_qa and int(record["isolatesTested"]) < 30
    }
    observed_low_count_groups = {
        (item.get("microorganism"), item.get("isolatesTested"))
        for item in low_count_groups
        if isinstance(item, dict)
    }
    require(
        expected_low_count_groups == observed_low_count_groups,
        "enterobacteria QA knownLowCountGroupsInExtractedRecords does not match source records",
    )


def validate_enterobacteria_preconsolidation_against_records(
    preconsolidation_path: Path,
    records: list[dict[str, Any]],
) -> None:
    require(preconsolidation_path.exists(), f"missing enterobacteria preconsolidation file: {preconsolidation_path}")
    data = load_json(preconsolidation_path)
    metadata = data.get("metadata") or {}
    input_datasets = data.get("inputDatasets") or []
    method = data.get("preconsolidationMethod") or {}
    summary = data.get("summary") or {}
    duplicate_identical_keys = data.get("duplicateIdenticalKeys") or []
    conflicting_keys = data.get("conflictingKeys") or []
    low_count_groups = data.get("lowCountGroups") or []

    require(
        metadata.get("status") == "preconsolidation_draft_pending_manual_review",
        "enterobacteria preconsolidation must remain draft pending manual review",
    )
    validate_utc_timestamp(metadata.get("generatedAt"), "enterobacteria preconsolidation generatedAt")
    require(metadata.get("clinicalUseAllowed") is False, "enterobacteria preconsolidation must not allow clinical use")
    require(metadata.get("interactiveUseAllowed") is False, "enterobacteria preconsolidation must not allow interactive use")
    require(
        metadata.get("therapeuticRecommendationAllowed") is False,
        "enterobacteria preconsolidation must not allow therapeutic recommendations",
    )
    require(isinstance(input_datasets, list) and len(input_datasets) == 3, "enterobacteria preconsolidation must reference exactly three passes")

    require(method.get("keyFields") == ["microorganism", "antibiotic"], "preconsolidation method keyFields must stay fixed")
    require(isinstance(method.get("duplicateIdenticalDefinition"), str) and method.get("duplicateIdenticalDefinition"), "preconsolidation method must define identical duplicates")
    require(isinstance(method.get("conflictDefinition"), str) and method.get("conflictDefinition"), "preconsolidation method must define conflicts")
    require(isinstance(method.get("lowCountDefinition"), str) and method.get("lowCountDefinition"), "preconsolidation method must define low-count groups")
    require(method.get("automaticConsolidationPerformed") is False, "preconsolidation must not claim automatic consolidation")
    require(method.get("conflictResolutionPerformed") is False, "preconsolidation must not claim conflict resolution")
    require(method.get("clinicalInterpretationPerformed") is False, "preconsolidation must not claim clinical interpretation")

    source_files = {str(item.get("file")) for item in input_datasets if item.get("file")}
    source_records = [record for record in records if record["sourceFile"] in source_files]
    require(source_records, "enterobacteria preconsolidation references no source records")

    records_by_source: dict[str, list[dict[str, Any]]] = {}
    for record in source_records:
        records_by_source.setdefault(str(record["sourceFile"]), []).append(record)

    for index, item in enumerate(input_datasets):
        prefix = f"enterobacteria_preconsolidation.inputDatasets[{index}]"
        source_file = item.get("file")
        require(isinstance(source_file, str) and source_file.endswith(".json"), f"{prefix}.file must be a JSON filename")
        current_records = records_by_source.get(source_file) or []
        require(current_records, f"{prefix}.file has no matching source records: {source_file}")
        source_organisms = {record["microorganism"] for record in current_records}
        source_antibiotics = {record["antibiotic"] for record in current_records}
        require(item.get("recordCount") == len(current_records), f"{prefix}.recordCount mismatch")
        require(item.get("microorganismGroupCount") == len(source_organisms), f"{prefix}.microorganismGroupCount mismatch")
        require(item.get("antibioticCount") == len(source_antibiotics), f"{prefix}.antibioticCount mismatch")

    grouped = group_records_by_key(source_records)
    single_record_keys, expected_duplicate_identical_keys, expected_conflicting_keys = calculate_key_classes(source_records)

    require(summary.get("sourceRecordCount") == len(source_records), "preconsolidation.sourceRecordCount mismatch")
    require(summary.get("uniqueKeyCount") == len(grouped), "preconsolidation.uniqueKeyCount mismatch")
    require(summary.get("singleRecordKeyCount") == len(single_record_keys), "preconsolidation.singleRecordKeyCount mismatch")
    require(
        summary.get("duplicateIdenticalKeyCount") == len(expected_duplicate_identical_keys),
        "preconsolidation.duplicateIdenticalKeyCount mismatch",
    )
    require(summary.get("conflictingKeyCount") == len(expected_conflicting_keys), "preconsolidation.conflictingKeyCount mismatch")
    require(summary.get("readyForConsolidatedPublication") is False, "preconsolidation must not be publication-ready")
    require(
        summary.get("readyForAppQueryAsConsolidatedDataset") is False,
        "preconsolidation must not be APP-ready as a consolidated dataset",
    )
    require(summary.get("readyForClinicalUse") is False, "preconsolidation must not be clinical-use ready")

    observed_duplicate_identical_keys = {
        (item.get("microorganism"), item.get("antibiotic"))
        for item in duplicate_identical_keys
        if isinstance(item, dict)
    }
    observed_conflicting_keys = {
        (item.get("microorganism"), item.get("antibiotic"))
        for item in conflicting_keys
        if isinstance(item, dict)
    }
    expected_low_count_groups = {
        (record["microorganism"], record["isolatesTested"])
        for record in source_records
        if int(record["isolatesTested"]) < 30
    }
    observed_low_count_groups = {
        (item.get("microorganism"), item.get("isolatesTested"))
        for item in low_count_groups
        if isinstance(item, dict)
    }

    require(
        observed_duplicate_identical_keys == expected_duplicate_identical_keys,
        "preconsolidation.duplicateIdenticalKeys does not match source records",
    )
    require(observed_conflicting_keys == expected_conflicting_keys, "preconsolidation.conflictingKeys does not match source records")
    require(observed_low_count_groups == expected_low_count_groups, "preconsolidation.lowCountGroups does not match source records")

    safe_behavior = data.get("safeAppBehavior") or {}
    require(safe_behavior.get("mustNotUseAsConsolidatedDataset") is True, "preconsolidation must block consolidated use")
    require(safe_behavior.get("mustNotRankAntibiotics") is True, "preconsolidation must block ranking")
    require(
        safe_behavior.get("mustNotGenerateTherapeuticRecommendations") is True,
        "preconsolidation must block therapeutic recommendations",
    )
    require(safe_behavior.get("mustShowPendingReview") is True, "preconsolidation must show pending review")


def main() -> None:
    allowed_antibiotics: set[str] = set()

    for path in REQUIRED_DICTIONARY_FILES:
        require(path.exists(), f"missing microbiology dictionary file: {path}")
        allowed_antibiotics.update(validate_dictionary_file(path))

    all_records: list[dict[str, Any]] = []
    for path in REQUIRED_SUSCEPTIBILITY_FILES:
        require(path.exists(), f"missing microbiology pending table file: {path}")
        all_records.extend(validate_susceptibility_file(path, allowed_antibiotics))

    validate_no_conflicting_duplicate_records(all_records)
    validate_enterobacteria_qa_against_records(ENTEROBACTERIA_QA_FILE, all_records)
    validate_enterobacteria_preconsolidation_against_records(ENTEROBACTERIA_PRECONSOLIDATION_FILE, all_records)

    print("Pending microbiology table extractions OK")
    print(f"Antibiotic dictionary entries: {len(allowed_antibiotics)}")
    print(f"Susceptibility files: {len(REQUIRED_SUSCEPTIBILITY_FILES)}")
    print(f"Susceptibility records: {len(all_records)}")
    print("Enterobacteria QA: validated against source passes")
    print("Enterobacteria preconsolidation: validated against source passes")


if __name__ == "__main__":
    main()
