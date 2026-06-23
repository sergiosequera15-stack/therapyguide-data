from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

PUBLISHED_DIR = Path("docs/microbiology/published")
POLICY_PATH = Path("docs/microbiology/ANNUAL_MAP_PUBLICATION_POLICY.md")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"ERROR: {message}")


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"ERROR: invalid JSON in {path}: {exc}") from exc


def validate_iso_datetime_or_date(value: Any, label: str) -> None:
    require(isinstance(value, str) and value.strip(), f"{label} must be a non-empty string")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SystemExit(f"ERROR: {label} is not valid ISO date/datetime: {value}") from exc


def validate_record(path: Path, record: dict[str, Any], index: int) -> None:
    prefix = f"{path.name}.records[{index}]"
    require(isinstance(record.get("microorganism"), str) and record.get("microorganism"), f"{prefix}.microorganism is required")
    require(isinstance(record.get("isolatesTested"), int) and record.get("isolatesTested") > 0, f"{prefix}.isolatesTested must be positive integer")
    require(isinstance(record.get("antibiotic"), str) and record.get("antibiotic"), f"{prefix}.antibiotic is required")
    percent = record.get("susceptibilityPercent")
    require(isinstance(percent, (int, float)) and 0 <= percent <= 100, f"{prefix}.susceptibilityPercent must be 0-100")

    candidate_source = record.get("candidateSource") or {}
    require(isinstance(candidate_source, dict), f"{prefix}.candidateSource must be an object")
    require(
        candidate_source.get("type") in {"singleRecordKey", "duplicateIdenticalCollapsed"},
        f"{prefix}.candidateSource.type is invalid",
    )
    source_files = candidate_source.get("sourceFiles")
    require(isinstance(source_files, list) and source_files, f"{prefix}.candidateSource.sourceFiles is required")
    require(
        isinstance(candidate_source.get("sourceRecordCount"), int) and candidate_source.get("sourceRecordCount") > 0,
        f"{prefix}.candidateSource.sourceRecordCount must be positive integer",
    )


def validate_published_map(path: Path) -> None:
    data = load_json(path)
    metadata = data.get("metadata") or {}
    summary = data.get("summary") or {}
    records = data.get("records") or []
    excluded_conflicts = data.get("excludedConflicts") or []
    low_count_groups = data.get("lowCountGroupsToFlag") or []
    safe_behavior = data.get("safeAppBehavior") or {}
    review = data.get("review") or {}

    require(metadata.get("status") == "published_annual_map", f"{path.name} metadata.status must be published_annual_map")
    require(isinstance(metadata.get("scope"), str) and metadata.get("scope"), f"{path.name} metadata.scope is required")
    require(isinstance(metadata.get("dataYear"), int), f"{path.name} metadata.dataYear must be integer")
    require(metadata.get("manualReviewStatus") == "reviewed", f"{path.name} manualReviewStatus must be reviewed")
    require(isinstance(metadata.get("reviewer"), str) and metadata.get("reviewer"), f"{path.name} reviewer is required")
    validate_iso_datetime_or_date(metadata.get("reviewedAt"), f"{path.name} reviewedAt")
    validate_iso_datetime_or_date(metadata.get("publishedAt"), f"{path.name} publishedAt")
    require(metadata.get("publicationPolicy") == POLICY_PATH.name, f"{path.name} publicationPolicy mismatch")

    annual_validity = metadata.get("annualValidity") or {}
    require(annual_validity.get("validUntilReplacedByNextAnnualSource") is True, f"{path.name} annual validity must persist until replacement")
    require(annual_validity.get("regenerateOnEveryCiRun") is False, f"{path.name} must not regenerate on every CI run")

    require(metadata.get("appConsultationAllowed") is True, f"{path.name} must explicitly allow APP consultation")
    require(metadata.get("clinicalUseAllowed") is False, f"{path.name} must not allow clinical use")
    require(metadata.get("clinicalDecisionSupportAllowed") is False, f"{path.name} must not allow CDS")
    require(metadata.get("therapeuticRecommendationAllowed") is False, f"{path.name} must not allow therapeutic recommendations")

    require(isinstance(records, list) and records, f"{path.name} records must be a non-empty list")
    require(summary.get("recordCount") == len(records), f"{path.name} summary.recordCount mismatch")
    require(summary.get("excludedConflictKeyCount") == len(excluded_conflicts), f"{path.name} excludedConflictKeyCount mismatch")
    require(summary.get("lowCountGroupCount") == len(low_count_groups), f"{path.name} lowCountGroupCount mismatch")
    require(summary.get("readyForManifestPublication") is True, f"{path.name} must be manifest-ready if published")
    require(summary.get("readyForAppQueryAsConsolidatedDataset") is True, f"{path.name} must be APP-query-ready if published")
    require(summary.get("readyForClinicalUse") is False, f"{path.name} must not be clinical-use ready")

    seen_keys: set[tuple[str, str]] = set()
    for index, record in enumerate(records):
        require(isinstance(record, dict), f"{path.name}.records[{index}] must be an object")
        validate_record(path, record, index)
        key = (record["microorganism"], record["antibiotic"])
        require(key not in seen_keys, f"{path.name} duplicate published key: {key[0]} / {key[1]}")
        seen_keys.add(key)

    require(safe_behavior.get("mayUseAsAnnualConsultationMap") is True, f"{path.name} must allow annual consultation map use")
    require(safe_behavior.get("mustShowScope") is True, f"{path.name} must show scope")
    require(safe_behavior.get("mustShowDataYear") is True, f"{path.name} must show dataYear")
    require(safe_behavior.get("mustShowLowCountWarnings") is bool(low_count_groups), f"{path.name} low-count warning flag mismatch")
    require(safe_behavior.get("mustNotRankAntibiotics") is True, f"{path.name} must block antibiotic ranking")
    require(safe_behavior.get("mustNotGenerateTherapeuticRecommendations") is True, f"{path.name} must block therapeutic recommendations")
    require(safe_behavior.get("mustNotFallbackToDifferentScope") is True, f"{path.name} must block scope fallback")

    require(review.get("status") == "reviewed", f"{path.name} review.status must be reviewed")
    require(review.get("reviewer") == metadata.get("reviewer"), f"{path.name} review.reviewer mismatch")
    require(review.get("reviewedAt") == metadata.get("reviewedAt"), f"{path.name} review.reviewedAt mismatch")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate permanent or dry-run published microbiology maps.")
    parser.add_argument(
        "--map-file",
        type=Path,
        action="append",
        default=[],
        help="Specific published-map JSON to validate. Can be supplied more than once.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    require(POLICY_PATH.exists(), "annual microbiology map publication policy is missing")

    if args.map_file:
        for path in args.map_file:
            require(path.exists(), f"published microbiology map file not found: {path}")
            validate_published_map(path)
            print(f"Published microbiology map OK: {path}")
        print(f"Published microbiology maps validated: {len(args.map_file)}")
        return

    if not PUBLISHED_DIR.exists():
        print("No published microbiology map directory found; skipping published map validation")
        return

    map_files = sorted(path for path in PUBLISHED_DIR.glob("*.json") if path.is_file())
    if not map_files:
        print("No published microbiology maps found; skipping published map validation")
        return

    for path in map_files:
        validate_published_map(path)
        print(f"Published microbiology map OK: {path}")

    print(f"Published microbiology maps validated: {len(map_files)}")


if __name__ == "__main__":
    main()
