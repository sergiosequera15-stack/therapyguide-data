from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MICROBIOLOGY_DIR = Path("docs") / "microbiology"
INPUT_FILES = [
    MICROBIOLOGY_DIR / "susceptibility_huvn_bgn_enterobacterias_2025.json",
    MICROBIOLOGY_DIR / "susceptibility_huvn_bgn_enterobacterias_second_pass_2025.json",
    MICROBIOLOGY_DIR / "susceptibility_huvn_bgn_enterobacterias_third_pass_2025.json",
]
OUTPUT_FILE = MICROBIOLOGY_DIR / "preconsolidation_enterobacterias_draft_2025.json"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_record(path: Path, record: dict[str, Any]) -> dict[str, Any]:
    return {
        "sourceFile": path.name,
        "microorganism": str(record["microorganism"]).strip(),
        "isolatesTested": int(record["isolatesTested"]),
        "antibiotic": str(record["antibiotic"]).strip(),
        "susceptibilityPercent": record["susceptibilityPercent"],
    }


def main() -> None:
    all_records: list[dict[str, Any]] = []
    input_summaries: list[dict[str, Any]] = []

    for path in INPUT_FILES:
        data = load_json(path)
        metadata = data.get("metadata") or {}
        records = [normalize_record(path, record) for record in data.get("records") or []]
        organisms = sorted({record["microorganism"] for record in records})
        antibiotics = sorted({record["antibiotic"] for record in records})

        input_summaries.append(
            {
                "file": path.name,
                "title": metadata.get("title"),
                "extractionStatus": metadata.get("extractionStatus"),
                "manualReviewStatus": metadata.get("manualReviewStatus"),
                "recordCount": len(records),
                "microorganismGroupCount": len(organisms),
                "antibioticCount": len(antibiotics),
            }
        )
        all_records.extend(records)

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in all_records:
        grouped[(record["microorganism"], record["antibiotic"])].append(record)

    duplicate_identical_keys: list[dict[str, Any]] = []
    conflicting_keys: list[dict[str, Any]] = []
    unique_records: list[dict[str, Any]] = []

    for (microorganism, antibiotic), records in sorted(grouped.items()):
        value_pairs = {(record["isolatesTested"], record["susceptibilityPercent"]) for record in records}
        sources = sorted({record["sourceFile"] for record in records})

        if len(records) == 1:
            unique_records.append(records[0])
            continue

        if len(value_pairs) == 1:
            duplicate_identical_keys.append(
                {
                    "microorganism": microorganism,
                    "antibiotic": antibiotic,
                    "sources": sources,
                    "recordCount": len(records),
                    "isolatesTested": records[0]["isolatesTested"],
                    "susceptibilityPercent": records[0]["susceptibilityPercent"],
                }
            )
        else:
            conflicting_keys.append(
                {
                    "microorganism": microorganism,
                    "antibiotic": antibiotic,
                    "sources": sources,
                    "values": [
                        {
                            "sourceFile": record["sourceFile"],
                            "isolatesTested": record["isolatesTested"],
                            "susceptibilityPercent": record["susceptibilityPercent"],
                        }
                        for record in records
                    ],
                }
            )

    low_count_groups = sorted(
        {
            (record["microorganism"], record["isolatesTested"])
            for record in all_records
            if record["isolatesTested"] < 30
        }
    )

    report = {
        "metadata": {
            "title": "Preconsolidación auditada pendiente de enterobacterias HUVN 2025",
            "version": "0.1.0",
            "generatedAt": utc_now_iso(),
            "status": "preconsolidation_draft_pending_manual_review",
            "clinicalUseAllowed": False,
            "interactiveUseAllowed": False,
            "therapeuticRecommendationAllowed": False,
            "notes": [
                "Informe generado de forma reproducible desde las tres pasadas de enterobacterias.",
                "No publica un dataset consolidado para consulta APP.",
                "No resuelve conflictos manualmente ni debe usarse para recomendaciones terapéuticas.",
            ],
        },
        "inputDatasets": input_summaries,
        "preconsolidationMethod": {
            "keyFields": ["microorganism", "antibiotic"],
            "duplicateIdenticalDefinition": "Same microorganism and antibiotic with identical isolatesTested and susceptibilityPercent values across more than one source pass.",
            "conflictDefinition": "Same microorganism and antibiotic with different isolatesTested or susceptibilityPercent values across source passes.",
            "lowCountDefinition": "Any microorganism group with isolatesTested lower than 30.",
            "automaticConsolidationPerformed": False,
            "conflictResolutionPerformed": False,
            "clinicalInterpretationPerformed": False,
        },
        "summary": {
            "sourceRecordCount": len(all_records),
            "uniqueKeyCount": len(grouped),
            "singleRecordKeyCount": len(unique_records),
            "duplicateIdenticalKeyCount": len(duplicate_identical_keys),
            "conflictingKeyCount": len(conflicting_keys),
            "lowCountGroupCount": len(low_count_groups),
            "readyForConsolidatedPublication": False,
            "readyForAppQueryAsConsolidatedDataset": False,
            "readyForClinicalUse": False,
        },
        "duplicateIdenticalKeys": duplicate_identical_keys,
        "conflictingKeys": conflicting_keys,
        "lowCountGroups": [
            {
                "microorganism": microorganism,
                "isolatesTested": isolates_tested,
                "warning": "n < 30; estimates should be flagged as unstable.",
            }
            for microorganism, isolates_tested in low_count_groups
        ],
        "safeAppBehavior": {
            "mayShowPreconsolidationStatus": True,
            "mustNotUseAsConsolidatedDataset": True,
            "mustNotRankAntibiotics": True,
            "mustNotGenerateTherapeuticRecommendations": True,
            "mustShowPendingReview": True,
        },
        "review": {
            "status": "pending",
            "reviewer": None,
            "reviewedAt": None,
        },
    }

    write_json(OUTPUT_FILE, report)
    print(f"Wrote {OUTPUT_FILE}")
    print(f"Generated at: {report['metadata']['generatedAt']}")
    print(f"Source records: {len(all_records)}")
    print(f"Unique keys: {len(grouped)}")
    print(f"Conflicts: {len(conflicting_keys)}")


if __name__ == "__main__":
    main()
