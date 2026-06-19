from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MICROBIOLOGY_DIR = Path("docs") / "microbiology"
SOURCE_FILES = [
    MICROBIOLOGY_DIR / "susceptibility_huvn_bgn_enterobacterias_2025.json",
    MICROBIOLOGY_DIR / "susceptibility_huvn_bgn_enterobacterias_second_pass_2025.json",
    MICROBIOLOGY_DIR / "susceptibility_huvn_bgn_enterobacterias_third_pass_2025.json",
]
CONSOLIDATED_PATH = MICROBIOLOGY_DIR / "susceptibility_huvn_bgn_enterobacterias_consolidated_pending_2025.json"
QA_REPORT_PATH = MICROBIOLOGY_DIR / "qa_enterobacterias_2025.json"

LOW_COUNT_THRESHOLD = 30
ROUNDING_TOLERANCE_PERCENT_POINTS = 0.51


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def key_for(record: dict[str, Any]) -> tuple[str, str]:
    return record["microorganism"], record["antibiotic"]


def infer_susceptible_count(isolates_tested: int, percent: float) -> dict[str, Any]:
    raw = isolates_tested * percent / 100
    nearest_count = int(round(raw))
    nearest_count = max(0, min(nearest_count, isolates_tested))
    reconstructed_percent = 100 * nearest_count / isolates_tested if isolates_tested else 0
    residual = abs(reconstructed_percent - percent)

    return {
        "inferredSusceptibleIsolates": nearest_count,
        "reconstructedPercent": round(reconstructed_percent, 4),
        "roundingResidualPercentPoints": round(residual, 4),
        "roundingCheck": "pass" if residual <= ROUNDING_TOLERANCE_PERCENT_POINTS else "review",
    }


def normalize_record(record: dict[str, Any], source_file: str) -> dict[str, Any]:
    isolates_tested = int(record["isolatesTested"])
    percent = float(record["susceptibilityPercent"])
    numeric_check = infer_susceptible_count(isolates_tested, percent)

    flags: list[str] = []
    if isolates_tested < LOW_COUNT_THRESHOLD:
        flags.append("low_count_n_below_30")
    if numeric_check["roundingCheck"] != "pass":
        flags.append("percentage_rounding_requires_review")

    return {
        "scope": "huvn",
        "population": "all",
        "sampleType": None,
        "organismGroup": "gram_negative_enterobacteria",
        "microorganism": record["microorganism"],
        "isolatesTested": isolates_tested,
        "antibiotic": record["antibiotic"],
        "susceptibilityPercent": percent if not percent.is_integer() else int(percent),
        **numeric_check,
        "flags": flags,
        "source": {
            "sourceFile": source_file,
            "pdfPage": 6,
            "printedPage": 5,
            "tableTitle": "Bacilos Gram negativos Enterobacterias",
        },
        "review": {
            "status": "pending",
            "reviewer": None,
            "reviewedAt": None,
        },
    }


def load_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    for path in SOURCE_FILES:
        data = load_json(path)
        for record in data.get("records", []):
            records.append(normalize_record(record, path.name))

    return records


def consolidate(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    duplicate_conflicts: list[dict[str, Any]] = []

    for record in records:
        key = key_for(record)
        previous = by_key.get(key)

        if previous is None:
            by_key[key] = record
            continue

        same_value = (
            previous["isolatesTested"] == record["isolatesTested"]
            and previous["susceptibilityPercent"] == record["susceptibilityPercent"]
        )

        if not same_value:
            duplicate_conflicts.append(
                {
                    "microorganism": key[0],
                    "antibiotic": key[1],
                    "first": {
                        "sourceFile": previous["source"]["sourceFile"],
                        "isolatesTested": previous["isolatesTested"],
                        "susceptibilityPercent": previous["susceptibilityPercent"],
                    },
                    "second": {
                        "sourceFile": record["source"]["sourceFile"],
                        "isolatesTested": record["isolatesTested"],
                        "susceptibilityPercent": record["susceptibilityPercent"],
                    },
                }
            )

    consolidated = sorted(by_key.values(), key=lambda item: (item["microorganism"], item["antibiotic"]))
    return consolidated, duplicate_conflicts


def build_qa_report(records: list[dict[str, Any]], consolidated: list[dict[str, Any]], duplicate_conflicts: list[dict[str, Any]]) -> dict[str, Any]:
    organism_counts = Counter(record["microorganism"] for record in consolidated)
    antibiotic_counts = Counter(record["antibiotic"] for record in consolidated)
    low_count_records = [record for record in consolidated if "low_count_n_below_30" in record["flags"]]
    rounding_review_records = [record for record in consolidated if "percentage_rounding_requires_review" in record["flags"]]

    coverage_by_organism = [
        {
            "microorganism": microorganism,
            "antibioticRecordCount": count,
            "isolatesTested": next(record["isolatesTested"] for record in consolidated if record["microorganism"] == microorganism),
            "lowCountWarning": next(record["isolatesTested"] for record in consolidated if record["microorganism"] == microorganism) < LOW_COUNT_THRESHOLD,
        }
        for microorganism, count in sorted(organism_counts.items())
    ]

    return {
        "metadata": {
            "title": "QA Enterobacterias HUVN 2025",
            "generatedAt": now_iso(),
            "status": "pending_manual_review",
            "sourceFiles": [path.name for path in SOURCE_FILES],
            "consolidatedFile": CONSOLIDATED_PATH.name,
        },
        "summary": {
            "rawRecordCount": len(records),
            "consolidatedRecordCount": len(consolidated),
            "organismCount": len(organism_counts),
            "antibioticCount": len(antibiotic_counts),
            "duplicateConflictCount": len(duplicate_conflicts),
            "lowCountRecordCount": len(low_count_records),
            "roundingReviewRecordCount": len(rounding_review_records),
        },
        "coverageByOrganism": coverage_by_organism,
        "coverageByAntibiotic": [
            {"antibiotic": antibiotic, "recordCount": count}
            for antibiotic, count in sorted(antibiotic_counts.items())
        ],
        "duplicateConflicts": duplicate_conflicts,
        "roundingReviewRecords": [
            {
                "microorganism": record["microorganism"],
                "antibiotic": record["antibiotic"],
                "isolatesTested": record["isolatesTested"],
                "susceptibilityPercent": record["susceptibilityPercent"],
                "inferredSusceptibleIsolates": record["inferredSusceptibleIsolates"],
                "reconstructedPercent": record["reconstructedPercent"],
                "roundingResidualPercentPoints": record["roundingResidualPercentPoints"],
                "sourceFile": record["source"]["sourceFile"],
            }
            for record in rounding_review_records
        ],
        "lowCountOrganisms": [
            item for item in coverage_by_organism if item["lowCountWarning"]
        ],
        "reviewNotes": [
            "Este informe no valida clínicamente los datos: solo detecta inconsistencias estructurales y numéricas internas.",
            "La validación clínica requiere cotejo visual/manual contra el PDF original.",
            "Los registros con n < 30 deben conservar advertencia estadística.",
        ],
    }


def build_consolidated_file(consolidated: list[dict[str, Any]], qa_report: dict[str, Any]) -> dict[str, Any]:
    return {
        "metadata": {
            "title": "Aislamientos HUVN bacilos Gram negativos enterobacterias - consolidado pendiente",
            "version": "0.1.0",
            "yearLabel": 2025,
            "dataYear": 2025,
            "scope": "huvn",
            "population": "all",
            "sampleType": None,
            "organismGroup": "gram_negative_enterobacteria",
            "generatedAt": now_iso(),
            "sourcePdf": {
                "title": "Mapa Microbiológico 2025",
                "uploadedFileName": "Mapa Microbiologico 2025 (1).pdf",
                "sha256": "a3c338b169f5a54e807e003b07420494ce2e2f4803d202cf5414d67379b4825e",
                "printedPage": 5,
                "pdfPage": 6,
                "tableTitle": "Bacilos Gram negativos Enterobacterias",
            },
            "sourceFiles": [path.name for path in SOURCE_FILES],
            "qaReport": QA_REPORT_PATH.name,
            "extractionStatus": "multi_pass_consolidated_pending",
            "manualReviewStatus": "pending",
            "interactiveUseAllowed": False,
            "duplicateConflictCount": qa_report["summary"]["duplicateConflictCount"],
            "roundingReviewRecordCount": qa_report["summary"]["roundingReviewRecordCount"],
            "lowCountRecordCount": qa_report["summary"]["lowCountRecordCount"],
        },
        "records": consolidated,
        "review": {
            "status": "pending",
            "reviewer": None,
            "reviewedAt": None,
        },
    }


def main() -> None:
    records = load_records()
    consolidated, duplicate_conflicts = consolidate(records)
    qa_report = build_qa_report(records, consolidated, duplicate_conflicts)
    consolidated_file = build_consolidated_file(consolidated, qa_report)

    write_json(CONSOLIDATED_PATH, consolidated_file)
    write_json(QA_REPORT_PATH, qa_report)

    if duplicate_conflicts:
        raise SystemExit(f"ERROR: conflicting duplicate records detected: {len(duplicate_conflicts)}")

    print(f"Raw records: {len(records)}")
    print(f"Consolidated records: {len(consolidated)}")
    print(f"Organisms: {qa_report['summary']['organismCount']}")
    print(f"Antibiotics: {qa_report['summary']['antibioticCount']}")
    print(f"Low-count records: {qa_report['summary']['lowCountRecordCount']}")
    print(f"Rounding review records: {qa_report['summary']['roundingReviewRecordCount']}")
    print(f"Written: {CONSOLIDATED_PATH}")
    print(f"Written: {QA_REPORT_PATH}")


if __name__ == "__main__":
    main()
