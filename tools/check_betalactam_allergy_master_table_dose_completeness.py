from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

TABLE_PATH = Path("docs/rules/betalactam_allergy_options_master_table_draft.json")
DEFAULT_REPORT_PATH = Path("docs/rules/generated/betalactam_allergy_master_table_dose_completeness_report.json")
DEFAULT_SUMMARY_PATH = Path("docs/rules/generated/betalactam_allergy_master_table_dose_completeness_summary.json")

DOSE_RE = re.compile(
    r"(?ix)"
    r"("
    r"\b\d+(?:[,.]\d+)?\s*(?:mg|g|mcg|µg|ui)\b"
    r"|\b\d+(?:[,.]\d+)?\s*(?:mg|g)\s*/\s*kg\b"
    r"|\b\d+(?:[,.]\d+)?\s*(?:mg|g)\s*/\s*(?:kg\s*/\s*)?(?:24\s*h|día|dia)\b"
    r"|\b\d+(?:[,.]\d+)?\s*(?:comp|comprimido|comprimidos)\b"
    r"|\bdosis\s+única\b"
    r"|\bdosis\s+unica\b"
    r")"
)
ROUTE_RE = re.compile(
    r"(?ix)"
    r"("
    r"\biv\b|\bi\.v\.\b|\bintravenos[ao]\b|"
    r"\bvo\b|\bv\.o\.\b|\boral\b|"
    r"\bim\b|\bi\.m\.\b|\bintramuscular\b|"
    r"\bintraperitoneal\b|\bintrav[ií]tre[ao]\b|\binhalad[ao]\b"
    r")"
)
FREQUENCY_RE = re.compile(
    r"(?ix)"
    r"("
    r"/\s*(?:6|8|12|24)\s*h\b"
    r"|cada\s+\d+\s*(?:h|horas|d[ií]as?)\b"
    r"|\b\d+\s*/\s*(?:6|8|12|24)\s*h\b"
    r"|\b\d+\s*(?:d[ií]as?)\b"
    r"|\bdosis\s+única\b"
    r"|\bdosis\s+unica\b"
    r")"
)
CLASS_OR_CONTEXT_RE = re.compile(
    r"(?i)\b(igual que|misma alternativa|macr[oó]lido|seg[uú]n edad|seg[uú]n situaci[oó]n|opcional|alternativa)\b"
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def rows_to_records(table: dict[str, Any]) -> list[dict[str, Any]]:
    columns = table.get("columns") or []
    rows = table.get("rows") or []
    if not isinstance(columns, list) or not isinstance(rows, list):
        raise SystemExit("ERROR: compact master table must contain columns and rows lists")
    records = []
    for index, row in enumerate(rows):
        if not isinstance(row, list) or len(row) != len(columns):
            raise SystemExit(f"ERROR: invalid row at index {index}")
        records.append(dict(zip(columns, row, strict=True)))
    return records


def match_values(regex: re.Pattern[str], text: str) -> list[str]:
    return sorted({match.group(0).strip() for match in regex.finditer(text)})


def assess_record(record: dict[str, Any]) -> dict[str, Any]:
    text = str(record.get("optionsText") or "")
    dose_matches = match_values(DOSE_RE, text)
    route_matches = match_values(ROUTE_RE, text)
    frequency_matches = match_values(FREQUENCY_RE, text)
    class_or_context = bool(CLASS_OR_CONTEXT_RE.search(text))

    has_dose = bool(dose_matches)
    has_route = bool(route_matches)
    has_frequency = bool(frequency_matches)

    if has_dose and has_route and has_frequency:
        status = "explicit_dose_route_frequency"
    elif has_dose and has_frequency:
        status = "explicit_dose_frequency_route_unspecified"
    elif has_dose:
        status = "partial_dose_information"
    elif class_or_context:
        status = "class_or_context_shorthand_without_explicit_dose"
    else:
        status = "missing_explicit_dose_information"

    return {
        "rowNumber": record.get("rowNumber"),
        "syndrome": record.get("syndrome"),
        "subsyndrome": record.get("subsyndrome"),
        "sourceTopicId": record.get("sourceTopicId"),
        "status": status,
        "hasDose": has_dose,
        "hasRoute": has_route,
        "hasFrequencyOrDuration": has_frequency,
        "doseMatches": dose_matches,
        "routeMatches": route_matches,
        "frequencyOrDurationMatches": frequency_matches,
        "qualityWarnings": record.get("qualityWarnings") or [],
        "optionsText": text,
    }


def compact_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "rowNumber": row.get("rowNumber"),
        "syndrome": row.get("syndrome"),
        "subsyndrome": row.get("subsyndrome"),
        "sourceTopicId": row.get("sourceTopicId"),
        "status": row.get("status"),
        "hasDose": row.get("hasDose"),
        "hasRoute": row.get("hasRoute"),
        "hasFrequencyOrDuration": row.get("hasFrequencyOrDuration"),
        "doseMatches": row.get("doseMatches") or [],
        "routeMatches": row.get("routeMatches") or [],
        "frequencyOrDurationMatches": row.get("frequencyOrDurationMatches") or [],
        "qualityWarnings": row.get("qualityWarnings") or [],
    }


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    table = load_json(TABLE_PATH)
    records = rows_to_records(table)
    rows = [assess_record(record) for record in records]
    status_counts = Counter(row["status"] for row in rows)
    incomplete_statuses = {
        "explicit_dose_frequency_route_unspecified",
        "partial_dose_information",
        "class_or_context_shorthand_without_explicit_dose",
        "missing_explicit_dose_information",
    }
    incomplete_rows = [row for row in rows if row["status"] in incomplete_statuses]
    no_explicit_dose_rows = [row for row in rows if not row["hasDose"]]

    report = {
        "metadata": {
            "title": "Beta-lactam allergy master table dose completeness report",
            "generatedAt": table.get("metadata", {}).get("generatedAt", "2026-06-24T00:00:00Z"),
            "status": "draft_dose_completeness_audit_only",
            "table": str(TABLE_PATH),
            "rowCount": len(rows),
            "statusCounts": dict(sorted(status_counts.items())),
            "incompleteDoseInfoRowCount": len(incomplete_rows),
            "noExplicitDoseRowCount": len(no_explicit_dose_rows),
            "clinicalUseAllowed": False,
            "clinicalDecisionSupportAllowed": False,
            "therapeuticRecommendationAllowed": False,
            "readyForAppConsultant": False,
            "notes": [
                "This report audits whether optionsText contains explicit dose, route, and frequency/duration patterns.",
                "It does not validate dose correctness or clinical appropriateness.",
                "Rows without explicit dose information require source-level review before structured APP display."
            ]
        },
        "rows": rows,
    }
    summary = {
        "metadata": {
            "title": "Beta-lactam allergy master table dose completeness summary",
            "generatedAt": report["metadata"]["generatedAt"],
            "status": "draft_dose_completeness_summary_only",
            "rowCount": len(rows),
            "statusCounts": report["metadata"]["statusCounts"],
            "incompleteDoseInfoRowCount": len(incomplete_rows),
            "noExplicitDoseRowCount": len(no_explicit_dose_rows),
            "clinicalUseAllowed": False,
            "clinicalDecisionSupportAllowed": False,
            "therapeuticRecommendationAllowed": False,
            "readyForAppConsultant": False,
            "notes": [
                "Compact deterministic summary for dose-completeness review.",
                "Not a clinical validation report.",
                "Incomplete rows are not wrong by default; some are shorthand rows inherited from the source table."
            ]
        },
        "incompleteRows": [compact_row(row) for row in incomplete_rows],
        "noExplicitDoseRows": [compact_row(row) for row in no_explicit_dose_rows],
    }

    write_json(DEFAULT_REPORT_PATH, report)
    write_json(DEFAULT_SUMMARY_PATH, summary)
    print(f"Beta-lactam allergy dose completeness report written to {DEFAULT_REPORT_PATH}")
    print(f"Beta-lactam allergy dose completeness summary written to {DEFAULT_SUMMARY_PATH}")
    print(json.dumps(report["metadata"]["statusCounts"], ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
