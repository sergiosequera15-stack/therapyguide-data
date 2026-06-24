from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TABLE_PATH = Path("docs/rules/betalactam_allergy_options_master_table_draft.json")
GUIDE_TOPICS_PATH = Path("docs/guide_topics.json")
DEFAULT_REPORT_PATH = Path("docs/rules/generated/betalactam_allergy_master_table_source_check_report.json")

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
    "fosfomicina": ["fosfomicina"],
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


def extract_drug_tokens(text: str) -> list[str]:
    return sorted({normalize_text(match.group(1)) for match in DRUG_RE.finditer(text)})


def token_present(token: str, haystack: str) -> bool:
    aliases = DRUG_ALIASES.get(token, [token])
    return any(normalize_text(alias) in haystack for alias in aliases)


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
        result["status"] = "source_not_found"
        result["notes"].append("No matching topic found by sourceTopicId or sourceUrl.")
        return result

    content_text = normalize_text(topic.get("contentText") or topic.get("summary") or "")
    drug_tokens = extract_drug_tokens(str(record.get("optionsText") or ""))
    missing = [token for token in drug_tokens if not token_present(token, content_text)]
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Check draft beta-lactam allergy master table against current guide_topics text.")
    parser.add_argument("--table", default=str(TABLE_PATH))
    parser.add_argument("--guide-topics", default=str(GUIDE_TOPICS_PATH))
    parser.add_argument("--output", default=str(DEFAULT_REPORT_PATH))
    parser.add_argument("--fail-on-possible-change", action="store_true", help="Exit with non-zero status if possible changes/source mismatches are detected.")
    args = parser.parse_args()

    table = load_json(Path(args.table))
    topics = load_json(Path(args.guide_topics))
    records = rows_to_records(table)
    if not isinstance(topics, list):
        raise SystemExit("ERROR: guide_topics must be a list")

    by_id, by_url = build_topic_index(topics)
    rows = [check_record(record, by_id, by_url) for record in records]
    status_counts = Counter(row["status"] for row in rows)
    report = {
        "metadata": {
            "title": "Beta-lactam allergy master table source check report",
            "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "status": "draft_source_change_detection_only",
            "table": str(args.table),
            "guideTopics": str(args.guide_topics),
            "rowCount": len(rows),
            "statusCounts": dict(sorted(status_counts.items())),
            "clinicalUseAllowed": False,
            "clinicalDecisionSupportAllowed": False,
            "therapeuticRecommendationAllowed": False,
            "readyForAppConsultant": False,
            "notes": [
                "This report is a change-detection aid only.",
                "It checks presence of drug tokens in the current source topic text; it does not validate clinical correctness.",
                "Rows flagged as possible changes require manual review before any table update."
            ]
        },
        "rows": rows,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Beta-lactam allergy master table source check report written to {output_path}")
    print(json.dumps(report["metadata"]["statusCounts"], ensure_ascii=False, sort_keys=True))

    risky_statuses = {"source_not_found", "possible_option_change_or_table_source_mismatch"}
    if args.fail_on_possible_change and any(status_counts.get(status, 0) for status in risky_statuses):
        raise SystemExit("ERROR: possible source/table changes detected")


if __name__ == "__main__":
    main()
