from __future__ import annotations

import json
from pathlib import Path
from typing import Any

QUEUE_PATH = Path("docs/rules/betalactam_allergy_master_table_manual_review_queue.json")
MASTER_TABLE_PATH = Path("docs/rules/betalactam_allergy_options_master_table_draft.json")
SOURCE_SUMMARY_PATH = Path("docs/rules/generated/betalactam_allergy_master_table_source_check_summary.json")
REQUIRED_FALSE_METADATA_FLAGS = (
    "clinicalUseAllowed",
    "clinicalDecisionSupportAllowed",
    "therapeuticRecommendationAllowed",
    "readyForAppConsultant",
    "automaticUpdateAllowed",
)
ALLOWED_RESOLUTION_STATUSES = {
    "pending_manual_review",
    "accepted_source_reviewed",
    "corrected_from_source",
    "accepted_explicit_exception",
    "needs_discussion",
    "not_applicable",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"ERROR: {message}")


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"ERROR: missing {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"ERROR: invalid JSON in {path}: {exc}") from exc


def rows_to_records(table: dict[str, Any]) -> list[dict[str, Any]]:
    columns = table.get("columns") or []
    rows = table.get("rows") or []
    require(isinstance(columns, list), "master table columns must be a list")
    require(isinstance(rows, list), "master table rows must be a list")
    records: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        require(isinstance(row, list), f"master rows[{index}] must be a list")
        require(len(row) == len(columns), f"master rows[{index}] length must match columns")
        records.append(dict(zip(columns, row, strict=True)))
    return records


def validate_metadata(queue: dict[str, Any], expected_count: int) -> None:
    metadata = queue.get("metadata") or {}
    require(isinstance(metadata, dict), "metadata must be an object")
    expected_status = "manual_source_review_pending" if expected_count else "manual_source_review_clear"
    require(metadata.get("status") == expected_status, f"metadata.status must be {expected_status}")
    require(metadata.get("masterTableSchema") == "compact_rows_v2", "metadata.masterTableSchema must be compact_rows_v2")
    require(metadata.get("rowCount") == expected_count, "metadata.rowCount must match source summary actionRequiredRows count")
    require(set(metadata.get("allowedResolutionStatuses") or []) == ALLOWED_RESOLUTION_STATUSES, "allowedResolutionStatuses do not match expected values")
    for flag in REQUIRED_FALSE_METADATA_FLAGS:
        require(metadata.get(flag) is False, f"metadata.{flag} must remain false")


def validate_items(queue: dict[str, Any], master_records: dict[int, dict[str, Any]], expected_row_numbers: set[int]) -> None:
    items = queue.get("items") or []
    require(isinstance(items, list), "items must be a list")
    row_numbers = [item.get("rowNumber") for item in items if isinstance(item, dict)]
    require(len(row_numbers) == len(set(row_numbers)), "item rowNumber values must be unique")
    require(set(row_numbers) == expected_row_numbers, "queue rowNumbers must match source summary actionRequiredRows exactly")

    for index, item in enumerate(items):
        require(isinstance(item, dict), f"items[{index}] must be an object")
        prefix = f"items[{index}]"
        row_number = item.get("rowNumber")
        require(isinstance(row_number, int), f"{prefix}.rowNumber must be an integer")
        master = master_records.get(row_number)
        require(master is not None, f"{prefix}.rowNumber not found in master table")
        for key in ("syndrome", "subsyndrome", "population", "allergyContext", "sourceTopicId", "sourceUrl"):
            require(item.get(key) == master.get(key), f"{prefix}.{key} does not match master table")
        require(item.get("currentOptionsText") == master.get("optionsText"), f"{prefix}.currentOptionsText does not match master table")
        require(item.get("reviewNotes") == master.get("reviewNotes"), f"{prefix}.reviewNotes does not match master table")
        require(isinstance(item.get("missingDrugTokens"), list), f"{prefix}.missingDrugTokens must be a list")
        require(isinstance(item.get("qualityWarnings"), list), f"{prefix}.qualityWarnings must be a list")
        require(item.get("resolutionStatus") in ALLOWED_RESOLUTION_STATUSES, f"{prefix}.resolutionStatus is invalid")
        require(isinstance(item.get("resolvedOptionsText"), str), f"{prefix}.resolvedOptionsText must be a string")
        require(isinstance(item.get("resolutionNote"), str), f"{prefix}.resolutionNote must be a string")
        if item.get("resolutionStatus") in {"accepted_source_reviewed", "corrected_from_source", "accepted_explicit_exception"}:
            require(item.get("reviewer"), f"{prefix} resolved row lacks reviewer")
            require(item.get("reviewedAt"), f"{prefix} resolved row lacks reviewedAt")
            require(item.get("resolutionNote"), f"{prefix} resolved row lacks resolutionNote")


def main() -> None:
    queue = load_json(QUEUE_PATH)
    master_table = load_json(MASTER_TABLE_PATH)
    source_summary = load_json(SOURCE_SUMMARY_PATH)
    require(isinstance(queue, dict), f"{QUEUE_PATH} must contain an object")
    require(isinstance(master_table, dict), f"{MASTER_TABLE_PATH} must contain an object")
    require(isinstance(source_summary, dict), f"{SOURCE_SUMMARY_PATH} must contain an object")
    require((master_table.get("metadata") or {}).get("schema") == "compact_rows_v2", "master table must be compact_rows_v2")

    master_records = {record["rowNumber"]: record for record in rows_to_records(master_table)}
    action_rows = source_summary.get("actionRequiredRows") or []
    require(isinstance(action_rows, list), "source summary actionRequiredRows must be a list")
    expected_row_numbers = {row.get("rowNumber") for row in action_rows if isinstance(row, dict)}
    require(all(isinstance(row_number, int) for row_number in expected_row_numbers), "source summary rowNumbers must be integers")
    validate_metadata(queue, len(expected_row_numbers))
    validate_items(queue, master_records, expected_row_numbers)
    print(f"Beta-lactam allergy source review queue OK: {len(expected_row_numbers)} rows")


if __name__ == "__main__":
    main()
