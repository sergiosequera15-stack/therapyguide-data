from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CANDIDATE_PATH = Path("docs/rules/betalactam_allergy_options_candidate.json")
WORKLIST_PATH = Path("docs/rules/betalactam_allergy_options_curation_worklist.json")
OVERLAY_PATH = Path("docs/rules/betalactam_allergy_options_manual_curation.json")
OVERLAY_DIR = Path("docs/rules/curation_overlays")
CURATION_FIELDS = (
    "curationDecision",
    "proposedSyndrome",
    "proposedSubsyndrome",
    "extractedOptions",
    "excludeReason",
    "curatorNotes",
)


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as exc:
        raise SystemExit(f"ERROR: invalid JSON in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise SystemExit(f"ERROR: {path} must contain an object")
    return data


def entries_by_id(payload: dict[str, Any], key: str = "entries") -> dict[str, dict[str, Any]]:
    entries = payload.get(key) or []
    if not isinstance(entries, list):
        return {}
    return {
        str(entry.get("candidateId")): entry
        for entry in entries
        if isinstance(entry, dict) and entry.get("candidateId")
    }


def load_overlay_entries() -> dict[str, dict[str, Any]]:
    merged = entries_by_id(load_json(OVERLAY_PATH))
    if OVERLAY_DIR.exists():
        for path in sorted(OVERLAY_DIR.glob("*.json")):
            merged.update(entries_by_id(load_json(path)))
    return merged


def expand_options(options: Any, candidate: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(options, list):
        return []

    expanded: list[dict[str, Any]] = []
    for option in options:
        if not isinstance(option, dict):
            continue
        next_option = dict(option)
        source_field = next_option.pop("sourceTextField", None)
        if not next_option.get("sourceText") and isinstance(source_field, str):
            next_option["sourceText"] = candidate.get(source_field)
        next_option["isTherapeuticRecommendation"] = False
        expanded.append(next_option)
    return expanded


def curation_fields(candidate: dict[str, Any], existing: dict[str, dict[str, Any]], overlay: dict[str, dict[str, Any]]) -> dict[str, Any]:
    candidate_id = str(candidate.get("id") or "")
    source = overlay.get(candidate_id) or existing.get(candidate_id) or {}
    preserved = {field: source.get(field) for field in CURATION_FIELDS if field in source}

    return {
        "curationDecision": preserved.get("curationDecision") or "pending",
        "proposedSyndrome": preserved.get("proposedSyndrome"),
        "proposedSubsyndrome": preserved.get("proposedSubsyndrome"),
        "extractedOptions": expand_options(preserved.get("extractedOptions") or [], candidate),
        "excludeReason": preserved.get("excludeReason"),
        "curatorNotes": preserved.get("curatorNotes"),
    }


def build_entry(candidate: dict[str, Any], existing: dict[str, dict[str, Any]], overlay: dict[str, dict[str, Any]]) -> dict[str, Any]:
    entry = {
        "candidateId": candidate.get("id"),
        "topicId": candidate.get("topicId"),
        "topicTitle": candidate.get("topicTitle"),
        "candidateContext": candidate.get("candidateContext"),
        "matchedSentence": candidate.get("matchedSentence"),
        "sourceUrl": candidate.get("sourceUrl"),
        "sourceText": candidate.get("sourceText"),
        "sourceStatus": candidate.get("status"),
        "readyForConsultant": False,
        "isTherapeuticRecommendation": False,
    }
    entry.update(curation_fields(candidate, existing, overlay))
    return entry


def validate_overlay(overlay: dict[str, dict[str, Any]], candidate_ids: set[str]) -> None:
    unknown = sorted(set(overlay) - candidate_ids)
    if unknown:
        raise SystemExit(f"ERROR: overlay references unknown candidates: {', '.join(unknown)}")


def build_worklist(candidate_payload: dict[str, Any], existing_payload: dict[str, Any], overlay: dict[str, dict[str, Any]]) -> dict[str, Any]:
    candidates = candidate_payload.get("candidates") or []
    if not isinstance(candidates, list):
        raise SystemExit("ERROR: candidates must be a list")

    candidate_ids = {
        str(candidate.get("id"))
        for candidate in candidates
        if isinstance(candidate, dict) and candidate.get("id")
    }
    validate_overlay(overlay, candidate_ids)
    existing = entries_by_id(existing_payload)
    entries = [
        build_entry(candidate, existing, overlay)
        for candidate in candidates
        if isinstance(candidate, dict) and candidate.get("id")
    ]

    return {
        "metadata": {
            "title": "Lista de curación de candidatos de opciones para alergia a betalactámicos",
            "version": "0.1.0",
            "generatedAt": "2026-06-24T00:00:00Z",
            "status": "manual_curation_pending",
            "source": "betalactam_allergy_options_candidate.json",
            "manualCurationSource": "betalactam_allergy_options_manual_curation.json plus docs/rules/curation_overlays/*.json",
            "candidateCount": len(entries),
            "pendingCount": sum(1 for entry in entries if entry.get("curationDecision") == "pending"),
            "includedCount": sum(1 for entry in entries if entry.get("curationDecision") == "include"),
            "excludedCount": sum(1 for entry in entries if entry.get("curationDecision") == "exclude"),
            "needsDiscussionCount": sum(1 for entry in entries if entry.get("curationDecision") == "needs_discussion"),
            "clinicalUseAllowed": False,
            "clinicalDecisionSupportAllowed": False,
            "therapeuticRecommendationAllowed": False,
            "readyForAppConsultant": False,
        },
        "allowedCurationDecisions": ["pending", "include", "exclude", "needs_discussion"],
        "instructions": [
            "Use include only for explicit source-backed records.",
            "Set proposedSyndrome and proposedSubsyndrome before promoting records.",
            "Use exclude for noise or duplicates.",
            "Do not mark records as recommendations or rankings.",
        ],
        "entries": entries,
    }


def main() -> None:
    candidate_payload = load_json(CANDIDATE_PATH)
    existing_payload = load_json(WORKLIST_PATH)
    overlay = load_overlay_entries()
    worklist = build_worklist(candidate_payload, existing_payload, overlay)
    WORKLIST_PATH.write_text(json.dumps(worklist, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {WORKLIST_PATH} with {worklist['metadata']['candidateCount']} entries")


if __name__ == "__main__":
    main()
