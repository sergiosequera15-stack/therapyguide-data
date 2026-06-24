from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MASTER_TABLE_PATH = Path("docs/rules/betalactam_allergy_options_master_table_draft.json")
SOURCE_SUMMARY_PATH = Path("docs/rules/generated/betalactam_allergy_master_table_source_check_summary.json")
OUTPUT_PATH = Path("docs/rules/betalactam_allergy_master_table_manual_review_queue.json")


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
    source_summary = load_json(SOURCE_SUMMARY_PATH)
    master_metadata = master_table.get("metadata") or {}
    if master_metadata.get("schema") != "compact_rows_v2":
        raise SystemExit("ERROR: source review queue must be generated from compact_rows_v2 master table")
    master_records = {record["rowNumber"]: record for record in rows_to_records(master_table)}
    action_rows = source_summary.get("actionRequiredRows") or []
    if not isinstance(action_rows, list):
        raise SystemExit("ERROR: source summary actionRequiredRows must be a list")

    items: list[dict[str, Any]] = []
    for row in action_rows:
        if not isinstance(row, dict):
            raise SystemExit("ERROR: invalid action row in source summary")
        row_number = row.get("rowNumber")
        source_record = master_records.get(row_number)
        if source_record is None:
            raise SystemExit(f"ERROR: rowNumber {row_number} not found in master table")
        items.append(
            {
                "rowNumber": row_number,
                "syndrome": source_record.get("syndrome"),
                "subsyndrome": source_record.get("subsyndrome"),
                "population": source_record.get("population"),
                "allergyContext": source_record.get("allergyContext"),
                "sourceTopicId": source_record.get("sourceTopicId"),
                "sourceUrl": source_record.get("sourceUrl"),
                "currentOptionsText": source_record.get("optionsText"),
                "reviewNotes": source_record.get("reviewNotes"),
                "detectedIssue": row.get("status"),
                "missingDrugTokens": row.get("missingDrugTokens") or [],
                "qualityWarnings": source_record.get("qualityWarnings") or [],
                "manualReviewAction": "Verify current HUVN source text and decide whether to accept as source-reviewed, correct the master row, or keep as explicitly accepted exception.",
                "resolutionStatus": "pending_manual_review",
                "resolvedOptionsText": "",
                "resolutionNote": "",
                "reviewer": "",
                "reviewedAt": ""
            }
        )

    queue = {
        "metadata": {
            "title": "Beta-lactam allergy source review queue",
            "version": "0.3.0",
            "generatedAt": master_metadata.get("generatedAt", "2026-06-24T00:00:00Z"),
            "status": "manual_source_review_pending" if items else "manual_source_review_clear",
            "source": str(SOURCE_SUMMARY_PATH),
            "masterTable": str(MASTER_TABLE_PATH),
            "masterTableSchema": master_metadata.get("schema"),
            "rowCount": len(items),
            "allowedResolutionStatuses": [
                "pending_manual_review",
                "accepted_source_reviewed",
                "corrected_from_source",
                "accepted_explicit_exception",
                "needs_discussion",
                "not_applicable"
            ],
            "clinicalUseAllowed": False,
            "clinicalDecisionSupportAllowed": False,
            "therapeuticRecommendationAllowed": False,
            "readyForAppConsultant": False,
            "automaticUpdateAllowed": False,
            "notes": [
                "Generated from v2 source-check summary actionRequiredRows.",
                "This queue replaces the superseded compact_rows_v1 manual review queue.",
                "Rows must not be automatically corrected or promoted.",
                "This is source-review support only and must not be used as CDS."
            ]
        },
        "items": items
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(queue, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Generated {OUTPUT_PATH} with {len(items)} v2 source-review rows")


if __name__ == "__main__":
    main()
