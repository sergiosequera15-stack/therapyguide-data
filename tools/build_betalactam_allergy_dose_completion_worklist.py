from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MASTER_TABLE_PATH = Path("docs/rules/betalactam_allergy_options_master_table_draft.json")
DOSE_SUMMARY_PATH = Path("docs/rules/generated/betalactam_allergy_master_table_dose_completeness_summary.json")
OUTPUT_PATH = Path("docs/rules/betalactam_allergy_dose_completion_worklist.json")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def rows_to_records(table: dict[str, Any]) -> list[dict[str, Any]]:
    columns = table.get("columns") or []
    rows = table.get("rows") or []
    if not isinstance(columns, list) or not isinstance(rows, list):
        raise SystemExit("ERROR: compact master table must contain columns and rows lists")
    records: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, list) or len(row) != len(columns):
            raise SystemExit(f"ERROR: invalid row at index {index}")
        records.append(dict(zip(columns, row, strict=True)))
    return records


def main() -> None:
    master_table = load_json(MASTER_TABLE_PATH)
    dose_summary = load_json(DOSE_SUMMARY_PATH)
    master_records = {record["rowNumber"]: record for record in rows_to_records(master_table)}
    incomplete_rows = dose_summary.get("incompleteRows") or []
    if not isinstance(incomplete_rows, list):
        raise SystemExit("ERROR: dose summary incompleteRows must be a list")

    items: list[dict[str, Any]] = []
    for row in incomplete_rows:
        if not isinstance(row, dict):
            raise SystemExit("ERROR: invalid incomplete row in dose summary")
        row_number = row.get("rowNumber")
        source_record = master_records.get(row_number)
        if source_record is None:
            raise SystemExit(f"ERROR: rowNumber {row_number} not found in master table")
        items.append(
            {
                "rowNumber": row_number,
                "syndrome": source_record.get("syndrome"),
                "subsyndrome": source_record.get("subsyndrome"),
                "sourceTopicId": source_record.get("sourceTopicId"),
                "sourceUrl": source_record.get("sourceUrl"),
                "currentOptionsText": source_record.get("optionsText"),
                "doseAuditStatus": row.get("status"),
                "hasDose": row.get("hasDose"),
                "hasRoute": row.get("hasRoute"),
                "hasFrequencyOrDuration": row.get("hasFrequencyOrDuration"),
                "doseMatches": row.get("doseMatches") or [],
                "routeMatches": row.get("routeMatches") or [],
                "frequencyOrDurationMatches": row.get("frequencyOrDurationMatches") or [],
                "qualityWarnings": source_record.get("qualityWarnings") or [],
                "completionStatus": "pending_manual_completion",
                "completedOptionsText": "",
                "reviewNote": "",
                "reviewer": "",
                "reviewedAt": ""
            }
        )

    worklist = {
        "metadata": {
            "title": "Beta-lactam allergy dose completion worklist",
            "version": "0.1.0",
            "generatedAt": master_table.get("metadata", {}).get("generatedAt", "2026-06-24T00:00:00Z"),
            "status": "manual_dose_completion_pending",
            "source": str(DOSE_SUMMARY_PATH),
            "masterTable": str(MASTER_TABLE_PATH),
            "rowCount": len(items),
            "allowedCompletionStatuses": [
                "pending_manual_completion",
                "completed_from_source",
                "accepted_unstructured_source_text",
                "not_applicable",
                "needs_discussion"
            ],
            "clinicalUseAllowed": False,
            "clinicalDecisionSupportAllowed": False,
            "therapeuticRecommendationAllowed": False,
            "readyForAppConsultant": False,
            "automaticUpdateAllowed": False,
            "notes": [
                "Worklist generated from dose completeness audit.",
                "Rows should be completed from the HUVN source, not inferred.",
                "completedOptionsText should preserve dose, route and frequency/duration where the source provides them.",
                "This is not clinical validation and must not be used as CDS."
            ]
        },
        "items": items
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(worklist, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Generated {OUTPUT_PATH} with {len(items)} dose-completion rows")


if __name__ == "__main__":
    main()
