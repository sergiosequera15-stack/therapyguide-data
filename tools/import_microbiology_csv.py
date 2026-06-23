from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REQUIRED_DATA_FIELDS = [
    "microorganism",
    "isolatesTested",
    "antibiotic",
    "susceptibilityPercent",
]
OPTIONAL_CONTEXT_FIELDS = ["scope", "year"]

COLUMN_ALIASES = {
    "scope": ["scope", "ambito", "ámbito", "centro", "hospital_scope"],
    "year": ["year", "año", "ano", "anio"],
    "microorganism": ["microorganism", "microorganismo", "organism", "organismo"],
    "isolatesTested": ["isolatestested", "isolates_tested", "n", "n_aislamientos", "aislamientos", "numero_aislamientos"],
    "antibiotic": ["antibiotic", "antibiotico", "antibiótico", "codigo_antibiotico", "código_antibiótico"],
    "susceptibilityPercent": [
        "susceptibilitypercent",
        "susceptibility_percent",
        "percent_susceptible",
        "porcentaje_sensible",
        "porcentaje_sensibilidad",
        "sensibilidad_porcentaje",
    ],
}

OUTPUT_STATUS = "csv_import_draft_pending_manual_review"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_header(value: str) -> str:
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def build_header_map(fieldnames: list[str]) -> dict[str, str]:
    normalized_to_original = {normalize_header(name): name for name in fieldnames if name is not None}
    header_map: dict[str, str] = {}

    for canonical_field, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            normalized_alias = normalize_header(alias)
            if normalized_alias in normalized_to_original:
                header_map[canonical_field] = normalized_to_original[normalized_alias]
                break

    return header_map


def detect_dialect(path: Path) -> csv.Dialect:
    sample = path.read_text(encoding="utf-8-sig")[:4096]
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        return csv.excel


def parse_int(value: Any, label: str, row_number: int) -> int:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise SystemExit(f"ERROR: row {row_number}: {label} must be an integer") from exc
    if parsed < 0:
        raise SystemExit(f"ERROR: row {row_number}: {label} must be non-negative")
    return parsed


def parse_percent(value: Any, label: str, row_number: int) -> float:
    raw = str(value).strip().replace(",", ".")
    try:
        parsed = float(raw)
    except ValueError as exc:
        raise SystemExit(f"ERROR: row {row_number}: {label} must be numeric") from exc
    if not 0 <= parsed <= 100:
        raise SystemExit(f"ERROR: row {row_number}: {label} must be between 0 and 100")
    return parsed


def get_text(row: dict[str, Any], column: str, label: str, row_number: int) -> str:
    value = str(row.get(column, "")).strip()
    if not value:
        raise SystemExit(f"ERROR: row {row_number}: {label} must not be empty")
    return value


def source_value(
    row: dict[str, Any],
    header_map: dict[str, str],
    canonical_field: str,
    fallback: str | int | None,
    row_number: int,
) -> str | int:
    column = header_map.get(canonical_field)
    if column:
        return get_text(row, column, canonical_field, row_number)
    if fallback is not None:
        return fallback
    raise SystemExit(f"ERROR: missing {canonical_field}; provide CSV column or CLI fallback")


def build_record(
    row: dict[str, Any],
    header_map: dict[str, str],
    source_file: str,
    row_number: int,
    default_scope: str | None,
    default_year: int | None,
) -> dict[str, Any]:
    scope = str(source_value(row, header_map, "scope", default_scope, row_number)).strip().lower()
    year = parse_int(source_value(row, header_map, "year", default_year, row_number), "year", row_number)
    microorganism = get_text(row, header_map["microorganism"], "microorganism", row_number)
    antibiotic = get_text(row, header_map["antibiotic"], "antibiotic", row_number).upper()
    isolates_tested = parse_int(row.get(header_map["isolatesTested"]), "isolatesTested", row_number)
    susceptibility_percent = parse_percent(row.get(header_map["susceptibilityPercent"]), "susceptibilityPercent", row_number)

    return {
        "scope": scope,
        "year": year,
        "microorganism": microorganism,
        "isolatesTested": isolates_tested,
        "antibiotic": antibiotic,
        "susceptibilityPercent": susceptibility_percent,
        "source": {
            "type": "csv",
            "file": source_file,
            "rowNumber": row_number,
        },
        "manualReviewStatus": "pending",
        "clinicalUseAllowed": False,
        "interactiveUseAllowed": False,
        "therapeuticRecommendationAllowed": False,
    }


def audit_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[tuple[str, int, str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        key = (record["scope"], record["year"], record["microorganism"], record["antibiotic"])
        grouped[key].append(record)

    duplicate_identical_keys: list[dict[str, Any]] = []
    conflicting_keys: list[dict[str, Any]] = []

    for (scope, year, microorganism, antibiotic), key_records in sorted(grouped.items()):
        value_pairs = {(record["isolatesTested"], record["susceptibilityPercent"]) for record in key_records}
        if len(key_records) <= 1:
            continue
        if len(value_pairs) == 1:
            duplicate_identical_keys.append(
                {
                    "scope": scope,
                    "year": year,
                    "microorganism": microorganism,
                    "antibiotic": antibiotic,
                    "recordCount": len(key_records),
                    "rows": [record["source"]["rowNumber"] for record in key_records],
                }
            )
        else:
            conflicting_keys.append(
                {
                    "scope": scope,
                    "year": year,
                    "microorganism": microorganism,
                    "antibiotic": antibiotic,
                    "values": [
                        {
                            "rowNumber": record["source"]["rowNumber"],
                            "isolatesTested": record["isolatesTested"],
                            "susceptibilityPercent": record["susceptibilityPercent"],
                        }
                        for record in key_records
                    ],
                }
            )

    return {
        "recordCount": len(records),
        "uniqueKeyCount": len(grouped),
        "duplicateIdenticalKeyCount": len(duplicate_identical_keys),
        "conflictingKeyCount": len(conflicting_keys),
        "duplicateIdenticalKeys": duplicate_identical_keys,
        "conflictingKeys": conflicting_keys,
    }


def read_csv_records(
    input_path: Path,
    default_scope: str | None,
    default_year: int | None,
    delimiter: str | None,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    dialect = detect_dialect(input_path)
    if delimiter is not None:
        dialect.delimiter = delimiter

    with input_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, dialect=dialect)
        if not reader.fieldnames:
            raise SystemExit("ERROR: CSV has no header row")
        header_map = build_header_map(reader.fieldnames)

        missing = [field for field in REQUIRED_DATA_FIELDS if field not in header_map]
        if missing:
            raise SystemExit(f"ERROR: missing required CSV columns or aliases: {', '.join(missing)}")
        if "scope" not in header_map and not default_scope:
            raise SystemExit("ERROR: missing scope column; pass --scope if source CSV has a single known scope")
        if "year" not in header_map and default_year is None:
            raise SystemExit("ERROR: missing year column; pass --year if source CSV has a single known year")

        records = [
            build_record(row, header_map, input_path.name, index, default_scope, default_year)
            for index, row in enumerate(reader, start=2)
        ]

    if not records:
        raise SystemExit("ERROR: CSV contains no data rows")

    return records, header_map


def write_json(path: Path, data: dict[str, Any], overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise SystemExit(f"ERROR: output file already exists: {path}; pass --overwrite to replace it")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_output(input_path: Path, records: list[dict[str, Any]], header_map: dict[str, str]) -> dict[str, Any]:
    audit = audit_records(records)
    return {
        "metadata": {
            "title": "Borrador importado desde CSV microbiológico",
            "version": "0.1.0",
            "generatedAt": utc_now_iso(),
            "status": OUTPUT_STATUS,
            "sourceCsv": input_path.name,
            "clinicalUseAllowed": False,
            "interactiveUseAllowed": False,
            "therapeuticRecommendationAllowed": False,
            "manualReviewStatus": "pending",
            "notes": [
                "CSV importado como fuente de entrada, no como contrato estable para la APP.",
                "Salida pendiente de validación y revisión manual antes de cualquier publicación en manifiestos.",
                "No se realiza interpretación clínica ni recomendación terapéutica.",
            ],
        },
        "csvImportContract": {
            "appMayConsumeSourceCsvDirectly": False,
            "canonicalJsonRequiredBeforeAppConsumption": True,
            "manifestPublicationRequiredBeforeAppConsumption": True,
            "scopeFallbackAllowed": False,
        },
        "columnMapping": header_map,
        "audit": audit,
        "records": records,
    }


def print_schema() -> None:
    schema = {
        "requiredDataFields": REQUIRED_DATA_FIELDS,
        "contextFields": OPTIONAL_CONTEXT_FIELDS,
        "acceptedAliases": COLUMN_ALIASES,
        "cliFallbacks": {
            "scope": "Allowed when the CSV has a single known scope and no scope column.",
            "year": "Allowed when the CSV has a single known year and no year column.",
        },
    }
    print(json.dumps(schema, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import an official microbiology CSV into a non-clinical canonical DATA JSON draft.")
    parser.add_argument("--input", type=Path, help="Official source CSV file.")
    parser.add_argument("--output", type=Path, help="Output JSON draft path.")
    parser.add_argument("--scope", help="Fallback scope when the CSV has no scope column, e.g. 'huvn'.")
    parser.add_argument("--year", type=int, help="Fallback year when the CSV has no year column, e.g. 2025.")
    parser.add_argument("--delimiter", help="Optional CSV delimiter override, e.g. ';'.")
    parser.add_argument("--overwrite", action="store_true", help="Allow replacing an existing output file.")
    parser.add_argument("--print-schema", action="store_true", help="Print accepted columns and aliases, then exit.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.print_schema:
        print_schema()
        return

    if args.input is None or args.output is None:
        raise SystemExit("ERROR: --input and --output are required unless --print-schema is used")
    if not args.input.exists():
        raise SystemExit(f"ERROR: input CSV does not exist: {args.input}")

    records, header_map = read_csv_records(args.input, args.scope, args.year, args.delimiter)
    output = build_output(args.input, records, header_map)
    write_json(args.output, output, overwrite=args.overwrite)

    print(f"Wrote {args.output}")
    print(f"Imported records: {len(records)}")
    print(f"Conflicting keys: {output['audit']['conflictingKeyCount']}")
    print("Status: draft pending manual review; not clinical; not APP-published")


if __name__ == "__main__":
    main()
