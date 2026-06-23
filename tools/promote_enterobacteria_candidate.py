from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_CANDIDATE_PATH = Path("docs/microbiology/consolidated_enterobacterias_candidate_2025.json")
DEFAULT_OUTPUT_PATH = Path("docs/microbiology/published/huvn_enterobacterias_2025.json")
POLICY_PATH = Path("docs/microbiology/ANNUAL_MAP_PUBLICATION_POLICY.md")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"ERROR: {message}")


def validate_reviewed_at(value: str) -> str:
    try:
        datetime.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("reviewed-at must be an ISO date or datetime, e.g. 2026-06-23") from exc
    return value


def build_published_map(
    candidate: dict[str, Any],
    reviewer: str,
    reviewed_at: str,
    review_notes: str | None,
    accepted_low_count_warnings: bool,
    accepted_excluded_conflicts: bool,
) -> dict[str, Any]:
    candidate_metadata = candidate.get("metadata") or {}
    candidate_summary = candidate.get("summary") or {}
    records = candidate.get("records") or []
    excluded_conflicts = candidate.get("excludedConflicts") or []
    low_count_groups = candidate.get("lowCountGroupsToFlag") or []

    require(candidate_metadata.get("status") == "consolidated_candidate_pending_manual_review", "candidate status is not valid for promotion")
    require(candidate_metadata.get("manualReviewStatus") == "pending", "candidate manualReviewStatus must be pending before promotion")
    require(candidate_metadata.get("scope") == "huvn", "candidate scope must be huv n".replace("huv n", "huvn"))
    require(candidate_metadata.get("clinicalUseAllowed") is False, "candidate must not claim clinical use")
    require(candidate_metadata.get("therapeuticRecommendationAllowed") is False, "candidate must not allow recommendations")
    require(candidate_summary.get("readyForManifestPublication") is False, "candidate unexpectedly claims manifest-ready status")
    require(candidate_summary.get("readyForClinicalUse") is False, "candidate unexpectedly claims clinical-use readiness")
    require(isinstance(records, list) and records, "candidate has no records")

    if excluded_conflicts:
        require(
            accepted_excluded_conflicts,
            "candidate has excluded conflicts; rerun with --accept-excluded-conflicts only after manual review",
        )

    if low_count_groups:
        require(
            accepted_low_count_warnings,
            "candidate has low-count groups; rerun with --accept-low-count-warnings only after confirming warnings are visible",
        )

    published_at = utc_now_iso()

    return {
        "metadata": {
            "title": "Mapa anual publicado de enterobacterias HUVN 2025",
            "version": "1.0.0",
            "status": "published_annual_map",
            "scope": "huvn",
            "dataYear": 2025,
            "organismGroup": candidate_metadata.get("organismGroup"),
            "sourceCandidateArtifact": DEFAULT_CANDIDATE_PATH.name,
            "sourcePreconsolidationArtifact": candidate_metadata.get("sourcePreconsolidationArtifact"),
            "publicationPolicy": POLICY_PATH.name,
            "publishedAt": published_at,
            "reviewedAt": reviewed_at,
            "reviewer": reviewer,
            "manualReviewStatus": "reviewed",
            "annualValidity": {
                "validFrom": reviewed_at,
                "validUntilReplacedByNextAnnualSource": True,
                "regenerateOnEveryCiRun": False,
            },
            "appConsultationAllowed": True,
            "clinicalUseAllowed": False,
            "clinicalDecisionSupportAllowed": False,
            "therapeuticRecommendationAllowed": False,
            "notes": [
                "Mapa anual permanente generado mediante promoción manual controlada.",
                "Permite consulta por APP como mapa microbiológico anual, no recomendación terapéutica.",
                "No debe extrapolarse fuera del scope declarado.",
            ],
        },
        "inputDatasets": candidate.get("inputDatasets") or [],
        "summary": {
            "recordCount": len(records),
            "excludedConflictKeyCount": len(excluded_conflicts),
            "lowCountGroupCount": len(low_count_groups),
            "readyForManifestPublication": True,
            "readyForAppQueryAsConsolidatedDataset": True,
            "readyForClinicalUse": False,
        },
        "records": records,
        "excludedConflicts": excluded_conflicts,
        "lowCountGroupsToFlag": low_count_groups,
        "safeAppBehavior": {
            "mayUseAsAnnualConsultationMap": True,
            "mustShowScope": True,
            "mustShowDataYear": True,
            "mustShowLowCountWarnings": bool(low_count_groups),
            "mustNotRankAntibiotics": True,
            "mustNotGenerateTherapeuticRecommendations": True,
            "mustNotFallbackToDifferentScope": True,
        },
        "review": {
            "status": "reviewed",
            "reviewer": reviewer,
            "reviewedAt": reviewed_at,
            "acceptedLowCountWarnings": accepted_low_count_warnings,
            "acceptedExcludedConflicts": accepted_excluded_conflicts,
            "notes": review_notes,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Promote the reviewed enterobacteria candidate artifact to a permanent annual DATA map."
    )
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--reviewer", required=True, help="Manual reviewer name or identifier.")
    parser.add_argument("--reviewed-at", required=True, type=validate_reviewed_at, help="ISO date/datetime of manual review.")
    parser.add_argument("--review-notes", default=None)
    parser.add_argument("--accept-low-count-warnings", action="store_true")
    parser.add_argument("--accept-excluded-conflicts", action="store_true")
    parser.add_argument("--approve-publication", action="store_true", help="Required safety switch to write the permanent map.")
    parser.add_argument("--overwrite", action="store_true", help="Allow replacing an existing output map.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    require(args.approve_publication, "--approve-publication is required")
    require(args.candidate.exists(), f"candidate file not found: {args.candidate}")
    require(POLICY_PATH.exists(), f"publication policy not found: {POLICY_PATH}")
    require(args.overwrite or not args.output.exists(), f"output already exists: {args.output}; use --overwrite only for a documented correction")

    candidate = load_json(args.candidate)
    published_map = build_published_map(
        candidate=candidate,
        reviewer=args.reviewer,
        reviewed_at=args.reviewed_at,
        review_notes=args.review_notes,
        accepted_low_count_warnings=args.accept_low_count_warnings,
        accepted_excluded_conflicts=args.accept_excluded_conflicts,
    )

    write_json(args.output, published_map)
    print(f"Wrote permanent annual microbiology map: {args.output}")
    print(f"Records: {published_map['summary']['recordCount']}")
    print(f"Low-count groups flagged: {published_map['summary']['lowCountGroupCount']}")
    print(f"Excluded conflict keys: {published_map['summary']['excludedConflictKeyCount']}")
    print("Clinical decision support: disabled")
    print("Therapeutic recommendations: disabled")


if __name__ == "__main__":
    main()
