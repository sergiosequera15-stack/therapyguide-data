from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TABLE_PATH = Path("docs/rules/betalactam_allergy_options_master_table_draft.json")
GUIDE_TOPICS_PATH = Path("docs/guide_topics.json")
DEFAULT_REPORT_PATH = Path("docs/rules/generated/betalactam_allergy_master_table_source_check_report.json")
DEFAULT_SUMMARY_PATH = Path("docs/rules/generated/betalactam_allergy_master_table_source_check_summary.json")

DRUG_ALIASES: dict[str, list[str]] = {
    "septrim": ["septrim", "tmp", "smx", "cotrimoxazol"],
    "cotrimoxazol": ["cotrimoxazol", "septrim", "tmp", "smx"],
    "aztreonam": ["aztreonam"],
    "metronidazol": ["metronidazol"],
    "amikacina": ["amikacina"],
    "gentamicina": ["gentamicina"],
    "daptomicina": ["daptomicina"],
    "linezolid": ["linezolid"],
    "tigeciclina": ["tigeciclina"],
    "moxifloxacino": ["moxifloxacino"],
    "levofloxacino": ["levofloxacino"],
    "ciprofloxacino": ["ciprofloxacino"],
    "ceftriaxona": ["ceftriaxona"],
    "cefotaxima": ["cefotaxima"],
    "cefuroxima": ["cefuroxima"],
    "ceftibuteno": ["ceftibuteno"],
    "cefditoreno": ["cefditoreno"],
    "cefixima": ["cefixima"],
    "ceftarolina": ["ceftarolina"],
    "ceftobiprol": ["ceftobiprol"],
    "ceftazidima": ["ceftazidima"],
    "ceftolozano": ["ceftolozano"],
    "meropenem": ["meropenem"],
    "ertapenem": ["ertapenem"],
    "imipenem": ["imipenem"],
    "vaborbactam": ["vaborbactam"],
    "relebactam": ["relebactam"],
    "fosfomicina": ["fosfomicina", "fosfomcina"],
    "vancomicina": ["vancomicina"],
    "rifampicina": ["rifampicina"],
    "dexametasona": ["dexametasona"],
    "azitromicina": ["azitromicina"],
    "claritromicina": ["claritromicina"],
    "josamicina": ["josamicina"],
    "midecamicina": ["midecamicina"],
    "clindamicina": ["clindamicina"],
    "doxiciclina": ["doxiciclina"],
    "caspofungina": ["caspofungina"],
    "dalbavancina": ["dalbavancina"],
    "oritavancina": ["oritavancina"],
    "oseltamivir": ["oseltamivir"],
    "probenecid": ["probenecid"],
    "penicilina": ["penicilina"],
}
DRUG_RE = re.compile(r"\b(" + "|".join(sorted(map(re.escape, DRUG_ALIASES), key=len, reverse=True)) + r")\b", re.IGNORECASE)
RISKY_STATUSES = {"source_not_found", "possible_option_change_or_table_source_mismatch", "needs_manual_review_no_drug_tokens_detected"}
SOURCE_TEXT_FIELDS = ("contentText", "summary", "contentHtml")
SOURCE_CONFIRMED_BY_USER_WARNING = "source_confirmed_by_user"
SOURCE_TOPIC_NOT_IN_SNAPSHOT_WARNING = "source_topic_not_in_current_guide_topics"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def canonicalize_url(url: str | None) -> str | None:
    if not url:
        return None
    parts = urlsplit(str(url).strip())
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not k.lower().startswith("utm_")]
    return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), urlencode(query), parts.fragment))


def normalize_text(text: str | None) -> str:
    text = str(text or "").lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def compact_text(text: str | None) -> str:
    return normalize_text(text).replace(" ", "")


def combined_topic_text(topic: dict[str, Any]) -> str:
    # Use all committed source text fields. Some source tokens may survive in HTML while
    # being absent from the extracted text summary, so checking only one field can create
    # false-positive mismatch rows. This is still deterministic source-token checking;
    # it is not clinical validation.
    return normalize_text("\n".join(str(topic.get(field) or "") for field in SOURCE_TEXT_FIELDS))


def extract_drug_tokens(text: str) -> list[str]:
    return sorted({normalize_text(match.group(1)) for match in DRUG_RE.finditer(text)})


def token_present(token: str, haystack: str) -> bool:
    aliases = DRUG_ALIASES.get(token, [token])
    compact_haystack = compact_text(haystack)
    for alias in aliases:
        normalized_alias = normalize_text(alias)
        if normalized_alias in haystack:
            return True
        if compact_text(alias) in compact_haystack:
            return True
    return False


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


def build_topic_index(topics: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_id: dict[str, dict[str, Any]] = {}
    by_url: dict[str, dict[str, Any]] = {}
    for topic in topics:
        if not isinstance(topic, dict):
            continue
        topic_id = topic.get("id")
        url = canonicalize_url(topic.get("sourceUrl"))
        if topic_id:
            by_id[str(topic_id)] = topic
        if url:
            by_url[url] = topic
    return by_id, by_url


def check_record(record: dict[str, Any], by_id: dict[str, dict[str, Any]], by_url: dict[str, dict[str, Any]]) -> dict[str, Any]:
    source_topic_id = record.get("sourceTopicId")
    source_url = canonicalize_url(record.get("sourceUrl"))
    topic = by_id.get(str(source_topic_id)) if source_topic_id else None
    if topic is None and source_url:
        topic = by_url.get(source_url)

    result: dict[str, Any] = {
        "rowNumber": record.get("rowNumber"),
        "syndrome": record.get("syndrome"),
        "subsyndrome": record.get("subsyndrome"),
        "sourceTopicId": source_topic_id,
        "sourceUrl": source_url,
        "status": "unchecked",
        "drugTokens": [],
        "missingDrugTokens": [],
        "qualityWarnings": record.get("qualityWarnings") or [],
        "notes": [],
    }
    if topic is None:
        warnings = set(result["qualityWarnings"])
        if SOURCE_CONFIRMED_BY_USER_WARNING in warnings and SOURCE_TOPIC_NOT_IN_SNAPSHOT_WARNING in warnings:
            result["status"] = "source_confirmed_outside_current_snapshot"
            result["notes"].append("Source chapter was confirmed by user but is not present in the committed guide_topics.json snapshot.")
            return result
        result["status"] = "source_not_found"
        result["notes"].append("No matching topic found by sourceTopicId or sourceUrl.")
        return result

    source_text = combined_topic_text(topic)
    drug_tokens = extract_drug_tokens(str(record.get("optionsText") or ""))
    missing = [token for token in drug_tokens if not token_present(token, source_text)]
    result["drugTokens"] = drug_tokens
    result["missingDrugTokens"] = missing

    if not drug_tokens:
        result["status"] = "needs_manual_review_no_drug_tokens_detected"
        result["notes"].append("No recognized drug tokens were extracted from optionsText.")
    elif missing:
        result["status"] = "possible_option_change_or_table_source_mismatch"
        result["notes"].append("One or more drug tokens from the table were not found in the current source topic text.")
    else:
        result["status"] = "source_contains_table_drug_tokens"
    return result


def compact_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "rowNumber": row.get("rowNumber"),
        "syndrome": row.get("syndrome"),
        "subsyndrome": row.get("subsyndrome"),
        "sourceTopicId": row.get("sourceTopicId"),
        "status": row.get("status"),
        "missingDrugTokens": row.get("missingDrugTokens") or [],
        "qualityWarnings": row.get("qualityWarnings") or [],
    }


def build_report(table: dict[str, Any], table_path: str, guide_topics_path: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts = Counter(row["status"] for row in rows)
    return {
        "metadata": {
            "title": "Beta-lactam allergy master table source check report",
            "generatedAt": table.get("metadata", {}).get("generatedAt", "2026-06-24T00:00:00Z"),
            "status": "draft_source_change_detection_only",
            "reportMode": "deterministic_committed_snapshot",
            "sourceTextFields": list(SOURCE_TEXT_FIELDS),
            "table": table_path,
            "guideTopics": guide_topics_path,
            "rowCount": len(rows),
            "statusCounts": dict(sorted(status_counts.items())),
            "clinicalUseAllowed": False,
            "clinicalDecisionSupportAllowed": False,
            "therapeuticRecommendationAllowed": False,
            "readyForAppConsultant": False,
            "notes": [
                "This report is a change-detection aid only.",
                "It checks presence of drug tokens in the current source topic text fields; it does not validate clinical correctness.",
                "Rows flagged as possible changes require manual review before any table update."
            ]
        },
        "rows": rows,
    }


def build_summary(report: dict[str, Any]) -> dict[str, Any]:
    rows = report.get("rows") or []
    risky_rows = [row for row in rows if row.get("status") in RISKY_STATUSES]
    warning_rows = [row for row in rows if row.get("qualityWarnings")]
    return {
        "metadata": {
            "title": "Beta-lactam allergy master table source check summary",
            "generatedAt": report.get("metadata", {}).get("generatedAt"),
            "status": "draft_source_change_detection_summary_only",
            "sourceTextFields": report.get("metadata", {}).get("sourceTextFields"),
            "rowCount": report.get("metadata", {}).get("rowCount"),
            "statusCounts": report.get("metadata", {}).get("statusCounts", {}),
            "actionRequiredRowCount": len(risky_rows),
            "qualityWarningRowCount": len(warning_rows),
            "clinicalUseAllowed": False,
            "clinicalDecisionSupportAllowed": False,
            "therapeuticRecommendationAllowed": False,
            "readyForAppConsultant": False,
            "notes": [
                "Compact deterministic summary for quick review in GitHub.",
                "Not a clinical validation report.",
                "Rows listed here require manual review before promotion."
            ]
        },
        "actionRequiredRows": [compact_row(row) for row in risky_rows],
        "qualityWarningRows": [compact_row(row) for row in warning_rows],
    }


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Check draft beta-lactam allergy master table against current guide_topics text.")
    parser.add_argument("--table", default=str(TABLE_PATH))
    parser.add_argument("--guide-topics", default=str(GUIDE_TOPICS_PATH))
    parser.add_argument("--output", default=str(DEFAULT_REPORT_PATH))
    parser.add_argument("--summary-output", default=str(DEFAULT_SUMMARY_PATH))
    parser.add_argument("--fail-on-possible-change", action="store_true", help="Exit with non-zero status if possible changes/source mismatches are detected.")
    args = parser.parse_args()

    table = load_json(Path(args.table))
    topics = load_json(Path(args.guide_topics))
    records = rows_to_records(table)
    if not isinstance(topics, list):
        raise SystemExit("ERROR: guide_topics must be a list")

    by_id, by_url = build_topic_index(topics)
    checked_rows = [check_record(record, by_id, by_url) for record in records]
    report = build_report(table, args.table, args.guide_topics, checked_rows)
    summary = build_summary(report)

    write_json(Path(args.output), report)
    write_json(Path(args.summary_output), summary)

    print(f"Beta-lactam allergy master table source check report written to {args.output}")
    print(f"Beta-lactam allergy master table source check summary written to {args.summary_output}")
    print(json.dumps(report["metadata"]["statusCounts"], ensure_ascii=False, sort_keys=True))

    if args.fail_on_possible_change and any(row.get("status") in RISKY_STATUSES for row in checked_rows):
        raise SystemExit("ERROR: possible source changes or unresolved source mismatches detected")


if __name__ == "__main__":
    main()
