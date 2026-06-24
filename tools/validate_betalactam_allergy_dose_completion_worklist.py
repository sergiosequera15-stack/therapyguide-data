from __future__ import annotations

import json
from pathlib import Path
from typing import Any

WORKLIST_PATH = Path("docs/rules/betalactam_allergy_dose_completion_worklist.json")
MASTER_TABLE_PATH = Path("docs/rules/betalactam_allergy_options_master_table_draft.json")
DOSE_SUMMARY_PATH = Path("docs/rules/generated/betalactam_allergy_master_table_dose_completeness_summary.json")
REQUIRED_FALSE_METADATA_FLAGS = (
    "clinicalUseAllowed",
    "clinicalDecisionSupportAllowed",
    "therapeuticRecommendationAllowed",
    "readyForAppConsultant",
    "automaticUpdateAllowed",
)
ALLOWED_COMPLETION_STATUSES = {
    "pending_manual_completion",
    "completed_from_source",
    "accepted_unstructured_source_text",
    "not_applicable",
    "needs_discussion",
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


def validate_metadata(worklist: dict[str, Any], expected_count: int) -> None:
    metadata = worklist.get("metadata") or {}
    require(isinstance(metadata, dict), "metadata must be an object")
    require(metadata.get("status") == "manual_dose_completion_pending", "worklist status must remain manual_dose_completion_pending")
    require(metadata.get("rowCount") == expected_count, "metadata.rowCount must match expected incomplete row count")
    require(set(metadata.get("allowedCompletionStatuses") or []) == ALLOWED_COMPLETION_STATUSES, "allowedCompletionStatuses do not match expected values")
    for flag in REQUIRED_FALSE_METADATA_FLAGS:
        require(metadata.get(flag) is False, f"metadata.{flag} must remain false")


def validate_items(worklist: dict[str, Any], master_records: dict[int, dict[str, Any]], expected_row_numbers: set[int]) -> None:
    items = worklist.get("items") or []
    require(isinstance(items, list), "items must be a list")
    row_numbers = [item.get("rowNumber") for item in items if isinstance(item, dict)]
    require(len(row_numbers) == len(set(row_numbers)), "item rowNumber values must be unique")
    require(set(row_numbers) == expected_row_numbers, "worklist rowNumbers must match dose summary incompleteRows exactly")

    for index, item in enumerate(items):
        require(isinstance(item, dict), f"items[{index}] must be an object")
        prefix = f"items[{index}]"
        row_number = item.get("rowNumber")
        require(isinstance(row_number, int), f"{prefix}.rowNumber must be an integer")
        master = master_records.get(row_number)
        require(master is not None, f"{prefix}.rowNumber not found in master table")
        require(item.get("syndrome") == master.get("syndrome"), f"{prefix}.syndrome does not match master table")
        require(item.get("subsyndrome") == master.get("subsyndrome"), f"{prefix}.subsyndrome does not match master table")
        require(item.get("sourceTopicId") == master.get("sourceTopicId"), f"{prefix}.sourceTopicId does not match master table")
        require(item.get("sourceUrl") == master.get("sourceUrl"), f"{prefix}.sourceUrl does not match master table")
        require(item.get("currentOptionsText") == master.get("optionsText"), f"{prefix}.currentOptionsText does not match master table")
        require(item.get("completionStatus") in ALLOWED_COMPLETION_STATUSES, f"{prefix}.completionStatus is invalid")
        require(isinstance(item.get("completedOptionsText"), str), f"{prefix}.completedOptionsText must be a string")
        require(isinstance(item.get("reviewNote"), str), f"{prefix}.reviewNote must be a string")
        require(isinstance(item.get("qualityWarnings"), list), f"{prefix}.qualityWarnings must be a list")

        if item.get("completionStatus") == "completed_from_source":
            require(item.get("completedOptionsText"), f"{prefix} completed row lacks completedOptionsText")
            require(item.get("reviewer"), f"{prefix} completed row lacks reviewer")
            require(item.get("reviewedAt"), f"{prefix} completed row lacks reviewedAt")



def main() -> None:
    worklist = load_json(WORKLIST_PATH)
    master_table = load_json(MASTER_TABLE_PATH)
    dose_summary = load_json(DOSE_SUMMARY_PATH)
    require(isinstance(worklist, dict), f"{WORKLIST_PATH} must contain an object")
    require(isinstance(master_table, dict), f"{MASTER_TABLE_PATH} must contain an object")
    require(isinstance(dose_summary, dict), f"{DOSE_SUMMARY_PATH} must contain an object")

    master_records = {record["rowNumber"]: record for record in rows_to_records(master_table)}
    incomplete_rows = dose_summary.get("incompleteRows") or []
    require(isinstance(incomplete_rows, list), "dose summary incompleteRows must be a list")
    expected_row_numbers = {row.get("rowNumber") for row in incomplete_rows if isinstance(row, dict)}
    require(all(isinstance(row_number, int) for row_number in expected_row_numbers), "dose summary rowNumbers must be integers")
    validate_metadata(worklist, len(expected_row_numbers))
    validate_items(worklist, master_records, expected_row_numbers)
    print(f"Beta-lactam allergy dose completion worklist OK: {len(expected_row_numbers)} rows")


if __name__ == "__main__":
    main()
