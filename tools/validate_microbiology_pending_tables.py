from __future__ import annotations

import json
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


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"ERROR: {message}")


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"ERROR: invalid JSON in {path}: {exc}") from exc


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

    print("Pending microbiology table extractions OK")
    print(f"Antibiotic dictionary entries: {len(allowed_antibiotics)}")
    print(f"Susceptibility files: {len(REQUIRED_SUSCEPTIBILITY_FILES)}")
    print(f"Susceptibility records: {len(all_records)}")
    print(f"Enterobacteria QA: validated against source passes")


if __name__ == "__main__":
    main()
