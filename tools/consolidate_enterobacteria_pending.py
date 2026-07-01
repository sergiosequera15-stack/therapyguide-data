from __future__ import annotations

import json
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
PRECONSOLIDATION_PATH = MICROBIOLOGY_DIR / "preconsolidation_enterobacterias_draft_2025.json"
CONSOLIDATED_CANDIDATE_PATH = MICROBIOLOGY_DIR / "consolidated_enterobacterias_candidate_2025.json"
LEGACY_CONSOLIDATED_PATH = MICROBIOLOGY_DIR / "susceptibility_huvn_bgn_enterobacterias_consolidated_pending_2025.json"
LEGACY_QA_REPORT_PATH = MICROBIOLOGY_DIR / "qa_enterobacterias_2025.json"
PUBLICATION_POLICY_FILE = MICROBIOLOGY_DIR / "ANNUAL_MAP_PUBLICATION_POLICY.md"
INTENDED_PUBLISHED_PATH = "docs/microbiology/published/huvn_enterobacterias_2025.json"

LOW_COUNT_THRESHOLD = 30
ROUNDING_TOLERANCE_PERCENT_POINTS = 0.51


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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


def normalize_percent(value: float) -> int | float:
    return int(value) if float(value).is_integer() else value


def load_source_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    for path in SOURCE_FILES:
        data = load_json(path)
        for raw_record in data.get("records", []):
            isolates_tested = int(raw_record["isolatesTested"])
            susceptibility_percent = normalize_percent(float(raw_record["susceptibilityPercent"]))
            numeric_check = infer_susceptible_count(isolates_tested, float(susceptibility_percent))
            records.append(
                {
                    "sourceFile": path.name,
                    "microorganism": str(raw_record["microorganism"]).strip(),
                    "isolatesTested": isolates_tested,
                    "antibiotic": str(raw_record["antibiotic"]).strip(),
                    "susceptibilityPercent": susceptibility_percent,
                    **numeric_check,
                }
            )

    return records


def group_records(records: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[(record["microorganism"], record["antibiotic"])].append(record)
    return grouped


def classify_keys(grouped: dict[tuple[str, str], list[dict[str, Any]]]) -> tuple[set[tuple[str, str]], set[tuple[str, str]], set[tuple[str, str]]]:
    single_record_keys: set[tuple[str, str]] = set()
    duplicate_identical_keys: set[tuple[str, str]] = set()
    conflicting_keys: set[tuple[str, str]] = set()

    for key, key_records in grouped.items():
        value_pairs = {(record["isolatesTested"], record["susceptibilityPercent"]) for record in key_records}
        if len(key_records) == 1:
            single_record_keys.add(key)
        elif len(value_pairs) == 1:
            duplicate_identical_keys.add(key)
        else:
            conflicting_keys.add(key)

    return single_record_keys, duplicate_identical_keys, conflicting_keys


def build_input_datasets(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records_by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        records_by_source[record["sourceFile"]].append(record)

    input_datasets: list[dict[str, Any]] = []
    for path in SOURCE_FILES:
        source_records = records_by_source[path.name]
        input_datasets.append(
            {
                "file": path.name,
                "recordCount": len(source_records),
                "microorganismGroupCount": len({record["microorganism"] for record in source_records}),
                "antibioticCount": len({record["antibiotic"] for record in source_records}),
            }
        )

    return input_datasets


def build_candidate_records(
    grouped: dict[tuple[str, str], list[dict[str, Any]]],
    single_record_keys: set[tuple[str, str]],
    duplicate_identical_keys: set[tuple[str, str]],
) -> list[dict[str, Any]]:
    candidate_records: list[dict[str, Any]] = []

    for key in sorted(single_record_keys | duplicate_identical_keys):
        source_records = grouped[key]
        first_record = source_records[0]
        candidate_records.append(
            {
                "microorganism": key[0],
                "antibiotic": key[1],
                "isolatesTested": first_record["isolatesTested"],
                "susceptibilityPercent": first_record["susceptibilityPercent"],
                "candidateSource": {
                    "type": "singleRecordKey" if key in single_record_keys else "duplicateIdenticalCollapsed",
                    "sourceFiles": sorted({record["sourceFile"] for record in source_records}),
                    "sourceRecordCount": len(source_records),
                },
            }
        )

    return candidate_records


def key_records_to_objects(keys: set[tuple[str, str]], grouped: dict[tuple[str, str], list[dict[str, Any]]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for microorganism, antibiotic in sorted(keys):
        source_records = grouped[(microorganism, antibiotic)]
        output.append(
            {
                "microorganism": microorganism,
                "antibiotic": antibiotic,
                "sources": sorted({record["sourceFile"] for record in source_records}),
                "sourceRecordCount": len(source_records),
            }
        )
    return output


def low_count_group_objects(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups = {
        (record["microorganism"], record["isolatesTested"])
        for record in records
        if int(record["isolatesTested"]) < LOW_COUNT_THRESHOLD
    }
    return [
        {
            "microorganism": microorganism,
            "isolatesTested": isolates_tested,
        }
        for microorganism, isolates_tested in sorted(groups)
    ]


def build_manual_review_worklist(
    grouped: dict[tuple[str, str], list[dict[str, Any]]],
    conflicting_keys: set[tuple[str, str]],
    low_count_groups: list[dict[str, Any]],
    candidate_record_count: int,
) -> dict[str, Any]:
    blockers = [
        {
            "code": "manual_review_pending",
            "blocksPublication": True,
            "message": "Manual review is required before publication or APP query as consolidated dataset.",
        }
    ]

    if conflicting_keys:
        blockers.append(
            {
                "code": "unresolved_conflicts",
                "blocksPublication": True,
                "message": "Conflicting duplicate microorganism/antibiotic keys require manual resolution.",
            }
        )

    if low_count_groups:
        blockers.append(
            {
                "code": "low_count_groups_need_flagging",
                "blocksPublication": True,
                "message": "Groups with n < 30 require explicit warning acceptance before publication.",
            }
        )

    return {
        "status": "pending",
        "conflictsToResolve": [
            {
                "microorganism": microorganism,
                "antibiotic": antibiotic,
                "sources": sorted({record["sourceFile"] for record in grouped[(microorganism, antibiotic)]}),
                "blocksPublication": True,
                "actionRequired": "Resolve conflicting duplicate values manually before promotion.",
            }
            for microorganism, antibiotic in sorted(conflicting_keys)
        ],
        "lowCountGroupsToFlag": [
            {
                **item,
                "blocksPublication": True,
                "actionRequired": "Keep visible low-count warning and accept it explicitly before publication.",
            }
            for item in low_count_groups
        ],
        "candidateRecordsToReview": [
            {
                "recordCount": candidate_record_count,
                "blocksPublication": True,
                "actionRequired": "Review all deduplicated candidate records against source PDF/table before promotion.",
            }
        ],
        "publicationBlockers": blockers,
    }


def build_preconsolidation(records: list[dict[str, Any]], generated_at: str) -> dict[str, Any]:
    grouped = group_records(records)
    single_record_keys, duplicate_identical_keys, conflicting_keys = classify_keys(grouped)
    candidate_records = build_candidate_records(grouped, single_record_keys, duplicate_identical_keys)
    low_count_groups = low_count_group_objects(records)
    input_datasets = build_input_datasets(records)

    return {
        "metadata": {
            "title": "Preconsolidación enterobacterias HUVN 2025",
            "status": "preconsolidation_draft_pending_manual_review",
            "generatedAt": generated_at,
            "scope": "huvn",
            "dataYear": 2025,
            "clinicalUseAllowed": False,
            "interactiveUseAllowed": False,
            "therapeuticRecommendationAllowed": False,
            "manualReviewStatus": "pending",
        },
        "inputDatasets": input_datasets,
        "preconsolidationMethod": {
            "keyFields": ["microorganism", "antibiotic"],
            "duplicateIdenticalDefinition": "Same microorganism and antibiotic with identical isolatesTested and susceptibilityPercent across passes.",
            "conflictDefinition": "Same microorganism and antibiotic with different isolatesTested or susceptibilityPercent across passes.",
            "lowCountDefinition": f"Any microorganism group with isolatesTested < {LOW_COUNT_THRESHOLD}.",
            "candidateRecordRule": "Only single-record keys and duplicate-identical keys are emitted as deduplicated candidates; conflicts are excluded.",
            "automaticConsolidationPerformed": False,
            "conflictResolutionPerformed": False,
            "clinicalInterpretationPerformed": False,
            "candidateRecordsArePublished": False,
        },
        "summary": {
            "sourceRecordCount": len(records),
            "uniqueKeyCount": len(grouped),
            "singleRecordKeyCount": len(single_record_keys),
            "duplicateIdenticalKeyCount": len(duplicate_identical_keys),
            "conflictingKeyCount": len(conflicting_keys),
            "candidateDeduplicatedRecordCount": len(candidate_records),
            "candidateExcludedConflictKeyCount": len(conflicting_keys),
            "candidateReadyForPublication": False,
            "readyForConsolidatedPublication": False,
            "readyForAppQueryAsConsolidatedDataset": False,
            "readyForClinicalUse": False,
        },
        "deduplicatedCandidateRecords": candidate_records,
        "duplicateIdenticalKeys": key_records_to_objects(duplicate_identical_keys, grouped),
        "conflictingKeys": key_records_to_objects(conflicting_keys, grouped),
        "lowCountGroups": low_count_groups,
        "manualReviewWorklist": build_manual_review_worklist(
            grouped=grouped,
            conflicting_keys=conflicting_keys,
            low_count_groups=low_count_groups,
            candidate_record_count=len(candidate_records),
        ),
        "safeAppBehavior": {
            "mustNotUseAsConsolidatedDataset": True,
            "mustNotRankAntibiotics": True,
            "mustNotGenerateTherapeuticRecommendations": True,
            "mustShowPendingReview": True,
        },
    }


def build_candidate(preconsolidation: dict[str, Any]) -> dict[str, Any]:
    input_datasets = preconsolidation["inputDatasets"]
    records = preconsolidation["deduplicatedCandidateRecords"]
    excluded_conflicts = [
        {
            "microorganism": item["microorganism"],
            "antibiotic": item["antibiotic"],
            "sources": item.get("sources", []),
            "blocksPublication": True,
        }
        for item in preconsolidation.get("conflictingKeys", [])
    ]
    low_count_groups = [
        {
            "microorganism": item["microorganism"],
            "isolatesTested": item["isolatesTested"],
            "blocksPublication": True,
        }
        for item in preconsolidation.get("lowCountGroups", [])
    ]

    return {
        "metadata": {
            "title": "Candidata consolidada enterobacterias HUVN 2025",
            "status": "consolidated_candidate_pending_manual_review",
            "sourcePreconsolidationArtifact": PRECONSOLIDATION_PATH.name,
            "publicationPolicy": PUBLICATION_POLICY_FILE.name,
            "intendedPermanentPathAfterReview": INTENDED_PUBLISHED_PATH,
            "generatedAt": preconsolidation["metadata"]["generatedAt"],
            "scope": "huvn",
            "dataYear": 2025,
            "clinicalUseAllowed": False,
            "interactiveUseAllowed": False,
            "therapeuticRecommendationAllowed": False,
            "manualReviewStatus": "pending",
        },
        "inputDatasets": input_datasets,
        "records": records,
        "excludedConflicts": excluded_conflicts,
        "lowCountGroupsToFlag": low_count_groups,
        "summary": {
            "recordCount": len(records),
            "excludedConflictKeyCount": len(excluded_conflicts),
            "lowCountGroupCount": len(low_count_groups),
            "readyForManifestPublication": False,
            "readyForAppQueryAsConsolidatedDataset": False,
            "readyForClinicalUse": False,
        },
        "safeAppBehavior": {
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


def build_legacy_outputs(records: list[dict[str, Any]], preconsolidation: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    candidate_records = preconsolidation["deduplicatedCandidateRecords"]
    low_count_groups = preconsolidation["lowCountGroups"]
    antibiotic_counts = Counter(record["antibiotic"] for record in candidate_records)
    organism_counts = Counter(record["microorganism"] for record in candidate_records)

    legacy_records = [
        {
            "scope": "huvn",
            "population": "all",
            "sampleType": None,
            "organismGroup": "gram_negative_enterobacteria",
            "microorganism": record["microorganism"],
            "isolatesTested": record["isolatesTested"],
            "antibiotic": record["antibiotic"],
            "susceptibilityPercent": record["susceptibilityPercent"],
            "flags": ["low_count_n_below_30"] if int(record["isolatesTested"]) < LOW_COUNT_THRESHOLD else [],
            "source": {
                "sourceFiles": record.get("candidateSource", {}).get("sourceFiles", []),
                "tableTitle": "Bacilos Gram negativos Enterobacterias",
            },
            "review": {"status": "pending", "reviewer": None, "reviewedAt": None},
        }
        for record in candidate_records
    ]

    legacy_consolidated = {
        "metadata": {
            "title": "Aislamientos HUVN bacilos Gram negativos enterobacterias - consolidado pendiente",
            "version": "0.2.0",
            "yearLabel": 2025,
            "dataYear": 2025,
            "scope": "huvn",
            "organismGroup": "gram_negative_enterobacteria",
            "generatedAt": preconsolidation["metadata"]["generatedAt"],
            "extractionStatus": "preconsolidated_candidate_pending_manual_review",
            "manualReviewStatus": "pending",
            "interactiveUseAllowed": False,
            "clinicalUseAllowed": False,
            "therapeuticRecommendationAllowed": False,
        },
        "records": legacy_records,
        "review": {"status": "pending", "reviewer": None, "reviewedAt": None},
    }

    legacy_qa = {
        "metadata": {
            "title": "QA Enterobacterias HUVN 2025",
            "generatedAt": preconsolidation["metadata"]["generatedAt"],
            "status": "pending_manual_review",
            "sourceFiles": [path.name for path in SOURCE_FILES],
            "preconsolidationArtifact": PRECONSOLIDATION_PATH.name,
            "consolidatedCandidateArtifact": CONSOLIDATED_CANDIDATE_PATH.name,
        },
        "summary": {
            "rawRecordCount": len(records),
            "candidateRecordCount": len(candidate_records),
            "organismCount": len(organism_counts),
            "antibioticCount": len(antibiotic_counts),
            "conflictingKeyCount": preconsolidation["summary"]["conflictingKeyCount"],
            "lowCountGroupCount": len(low_count_groups),
        },
        "coverageByAntibiotic": [
            {"antibiotic": antibiotic, "recordCount": count}
            for antibiotic, count in sorted(antibiotic_counts.items())
        ],
        "reviewNotes": [
            "Legacy QA mirror; canonical safety artifacts are preconsolidation_enterobacterias_draft_2025.json and consolidated_enterobacterias_candidate_2025.json.",
            "No clinical validation or therapeutic recommendation is performed.",
        ],
    }

    return legacy_consolidated, legacy_qa


def main() -> None:
    records = load_source_records()
    generated_at = now_iso()
    preconsolidation = build_preconsolidation(records, generated_at)
    candidate = build_candidate(preconsolidation)
    legacy_consolidated, legacy_qa = build_legacy_outputs(records, preconsolidation)

    write_json(PRECONSOLIDATION_PATH, preconsolidation)
    write_json(CONSOLIDATED_CANDIDATE_PATH, candidate)
    write_json(LEGACY_CONSOLIDATED_PATH, legacy_consolidated)
    write_json(LEGACY_QA_REPORT_PATH, legacy_qa)

    print(f"Raw records: {len(records)}")
    print(f"Candidate records: {len(preconsolidation['deduplicatedCandidateRecords'])}")
    print(f"Conflicting keys: {preconsolidation['summary']['conflictingKeyCount']}")
    print(f"Low-count groups: {len(preconsolidation['lowCountGroups'])}")
    print(f"Written: {PRECONSOLIDATION_PATH}")
    print(f"Written: {CONSOLIDATED_CANDIDATE_PATH}")
    print(f"Written: {LEGACY_CONSOLIDATED_PATH}")
    print(f"Written: {LEGACY_QA_REPORT_PATH}")


if __name__ == "__main__":
    main()
