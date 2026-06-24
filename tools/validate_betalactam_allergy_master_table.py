from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TABLE_PATH = Path("docs/rules/betalactam_allergy_options_master_table_draft.json")
GUIDE_TOPICS_PATH = Path("docs/guide_topics.json")
REQUIRED_COLUMNS = [
    "rowNumber",
    "syndrome",
    "subsyndrome",
    "population",
    "allergyContext",
    "optionsText",
    "reviewNotes",
    "sourceRefId",
    "sourceUrl",
    "sourceTopicId",
    "qualityWarnings",
]
REQUIRED_FALSE_METADATA_FLAGS = (
    "clinicalUseAllowed",
    "clinicalDecisionSupportAllowed",
    "therapeuticRecommendationAllowed",
    "readyForAppConsultant",
    "automaticUpdateAllowed",
)
MISSING_SOURCE_TOPIC_WARNING = "source_topic_not_in_current_guide_topics"


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


def canonicalize_url(url: str | None) -> str | None:
    if not url:
        return None
    parts = urlsplit(str(url).strip())
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not k.lower().startswith("utm_")]
    return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), urlencode(query), parts.fragment))


def row_to_record(columns: list[str], row: list[Any], index: int) -> dict[str, Any]:
    require(len(row) == len(columns), f"rows[{index}] length must match columns length")
    return dict(zip(columns, row, strict=True))


def validate_metadata(table: dict[str, Any], rows: list[list[Any]]) -> None:
    metadata = table.get("metadata") or {}
    require(isinstance(metadata, dict), "metadata must be an object")
    require(metadata.get("schema") == "compact_rows_v2", "metadata.schema must be compact_rows_v2")
    require(metadata.get("status") == "draft_pending_source_verification_and_manual_review", "metadata.status must remain draft_pending_source_verification_and_manual_review")
    require(metadata.get("manualReviewStatus") == "draft_pending_manual_review", "metadata.manualReviewStatus must remain draft_pending_manual_review")
    require(metadata.get("rowCount") == len(rows), "metadata.rowCount must match rows length")
    require(metadata.get("rowCount") == 76, "metadata.rowCount must be 76 for reviewed spreadsheet v2")
    require(metadata.get("source") == "proa_huvn_alergia_betalactamicos_y_calculadoras_v2(1).xlsx::Alergia betalactamicos", "metadata.source must identify reviewed spreadsheet v2 source sheet")
    require(metadata.get("inputSheet") == "Alergia betalactamicos", "metadata.inputSheet must be Alergia betalactamicos")
    require(metadata.get("ignoredSheets") == ["Calculadoras PROA", "Correcciones"], "metadata.ignoredSheets must document ignored sheets")
    require(metadata.get("changeDetectionOnly") is True, "metadata.changeDetectionOnly must be true")
    require(metadata.get("requiresManualReviewBeforeClinicalUse") is True, "metadata.requiresManualReviewBeforeClinicalUse must be true")
    for flag in REQUIRED_FALSE_METADATA_FLAGS:
        require(metadata.get(flag) is False, f"metadata.{flag} must remain false")


def validate_against_guide_topics(records: list[dict[str, Any]]) -> None:
    if not GUIDE_TOPICS_PATH.exists():
        print(f"WARNING: {GUIDE_TOPICS_PATH} not found; source topic validation skipped")
        return
    topics = load_json(GUIDE_TOPICS_PATH)
    require(isinstance(topics, list), f"{GUIDE_TOPICS_PATH} must contain a list")
    topic_ids = {topic.get("id") for topic in topics if isinstance(topic, dict)}
    urls = {canonicalize_url(topic.get("sourceUrl")) for topic in topics if isinstance(topic, dict)}
    urls.discard(None)

    missing_topic_ids: list[str] = []
    explicitly_marked_missing_topic_ids: list[str] = []
    missing_urls: list[str] = []
    for record in records:
        topic_id = record.get("sourceTopicId")
        source_url = canonicalize_url(record.get("sourceUrl"))
        warnings = record.get("qualityWarnings") or []
        if topic_id and topic_id not in topic_ids:
            label = f"row {record.get('rowNumber')} -> {topic_id}"
            if MISSING_SOURCE_TOPIC_WARNING in warnings:
                explicitly_marked_missing_topic_ids.append(label)
            else:
                missing_topic_ids.append(label)
        if source_url and source_url not in urls:
            missing_urls.append(f"row {record.get('rowNumber')} -> {source_url}")
    require(not missing_topic_ids, "sourceTopicId values not present in guide_topics.json and not explicitly marked: " + "; ".join(missing_topic_ids[:10]))
    if explicitly_marked_missing_topic_ids:
        print("WARNING: sourceTopicId values absent from current guide_topics.json but explicitly marked for review: " + "; ".join(explicitly_marked_missing_topic_ids[:10]))
    if missing_urls:
        print("WARNING: sourceUrl values not present verbatim in guide_topics.json; sourceTopicId validation passed or row is explicitly marked. First examples: " + "; ".join(missing_urls[:10]))


def validate_records(columns: list[str], rows: list[list[Any]]) -> list[dict[str, Any]]:
    require(columns == REQUIRED_COLUMNS, "columns do not match compact_rows_v2 schema")
    require(rows, "rows must not be empty")
    records = [row_to_record(columns, row, index) for index, row in enumerate(rows)]
    row_numbers = [record.get("rowNumber") for record in records]
    require(len(row_numbers) == len(set(row_numbers)), "rowNumber values must be unique")
    require(row_numbers == list(range(1, len(rows) + 1)), "rowNumber values must be consecutive starting at 1")

    for index, record in enumerate(records):
        prefix = f"rows[{index}]"
        require(record.get("syndrome"), f"{prefix}.syndrome is required")
        require(record.get("subsyndrome"), f"{prefix}.subsyndrome is required")
        require(record.get("population"), f"{prefix}.population is required")
        require(record.get("allergyContext"), f"{prefix}.allergyContext is required")
        require(record.get("optionsText"), f"{prefix}.optionsText is required")
        require(isinstance(record.get("reviewNotes"), str), f"{prefix}.reviewNotes must be a string")
        require(record.get("sourceRefId"), f"{prefix}.sourceRefId is required")
        source_url = str(record.get("sourceUrl") or "")
        require(source_url.startswith("https://www.huvn.es/"), f"{prefix}.sourceUrl must be a HUVN URL")
        require("utm_" not in source_url, f"{prefix}.sourceUrl must not contain tracking parameters")
        require(record.get("sourceTopicId"), f"{prefix}.sourceTopicId is required")
        warnings = record.get("qualityWarnings")
        require(isinstance(warnings, list), f"{prefix}.qualityWarnings must be a list")
    return records


def main() -> None:
    table = load_json(TABLE_PATH)
    require(isinstance(table, dict), f"{TABLE_PATH} must contain an object")
    columns = table.get("columns") or []
    rows = table.get("rows") or []
    require(isinstance(columns, list), "columns must be a list")
    require(isinstance(rows, list), "rows must be a list")
    validate_metadata(table, rows)
    records = validate_records(columns, rows)
    validate_against_guide_topics(records)
    print(f"Beta-lactam allergy master table OK: {len(records)} reviewed v2 draft rows")


if __name__ == "__main__":
    main()
