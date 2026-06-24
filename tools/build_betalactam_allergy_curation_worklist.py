from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CANDIDATE_PATH = Path("docs/rules/betalactam_allergy_options_candidate.json")
WORKLIST_PATH = Path("docs/rules/betalactam_allergy_options_curation_worklist.json")
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


def existing_entries_by_candidate_id(worklist: dict[str, Any]) -> dict[str, dict[str, Any]]:
    entries = worklist.get("entries") or []
    if not isinstance(entries, list):
        return {}
    return {
        str(entry.get("candidateId")): entry
        for entry in entries
        if isinstance(entry, dict) and entry.get("candidateId")
    }


def preserve_curation_fields(candidate_id: str, existing_entries: dict[str, dict[str, Any]]) -> dict[str, Any]:
    existing = existing_entries.get(candidate_id) or {}
    preserved = {field: existing.get(field) for field in CURATION_FIELDS if field in existing}

    return {
        "curationDecision": preserved.get("curationDecision") or "pending",
        "proposedSyndrome": preserved.get("proposedSyndrome"),
        "proposedSubsyndrome": preserved.get("proposedSubsyndrome"),
        "extractedOptions": preserved.get("extractedOptions") or [],
        "excludeReason": preserved.get("excludeReason"),
        "curatorNotes": preserved.get("curatorNotes"),
    }


def build_entry(candidate: dict[str, Any], existing_entries: dict[str, dict[str, Any]]) -> dict[str, Any]:
    candidate_id = str(candidate.get("id") or "")
    entry = {
        "candidateId": candidate_id,
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
    entry.update(preserve_curation_fields(candidate_id, existing_entries))
    return entry


def build_worklist(candidate_payload: dict[str, Any], existing: dict[str, Any]) -> dict[str, Any]:
    candidates = candidate_payload.get("candidates") or []
    if not isinstance(candidates, list):
        raise SystemExit("ERROR: candidates must be a list")

    existing_entries = existing_entries_by_candidate_id(existing)
    entries = [
        build_entry(candidate, existing_entries)
        for candidate in candidates
        if isinstance(candidate, dict) and candidate.get("id")
    ]
    pending_count = sum(1 for entry in entries if entry.get("curationDecision") == "pending")
    included_count = sum(1 for entry in entries if entry.get("curationDecision") == "include")
    excluded_count = sum(1 for entry in entries if entry.get("curationDecision") == "exclude")

    return {
        "metadata": {
            "title": "Lista de curación de candidatos de opciones para alergia a betalactámicos",
            "version": "0.1.0",
            "generatedAt": "2026-06-24T00:00:00Z",
            "status": "manual_curation_pending",
            "source": "betalactam_allergy_options_candidate.json",
            "candidateCount": len(entries),
            "pendingCount": pending_count,
            "includedCount": included_count,
            "excludedCount": excluded_count,
            "clinicalUseAllowed": False,
            "clinicalDecisionSupportAllowed": False,
            "therapeuticRecommendationAllowed": False,
            "readyForAppConsultant": False,
        },
        "allowedCurationDecisions": ["pending", "include", "exclude", "needs_discussion"],
        "instructions": [
            "Use include solo si el fragmento contiene una opción explícita y trazable para pacientes alérgicos.",
            "Asigne proposedSyndrome y proposedSubsyndrome antes de pasar a optionRecords.",
            "Use exclude para ruido, duplicados o menciones generales no útiles.",
            "No marque ningún registro como recomendación terapéutica ni ranking.",
        ],
        "entries": entries,
    }


def main() -> None:
    candidate_payload = load_json(CANDIDATE_PATH)
    existing_worklist = load_json(WORKLIST_PATH)
    worklist = build_worklist(candidate_payload, existing_worklist)
    WORKLIST_PATH.write_text(json.dumps(worklist, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {WORKLIST_PATH} with {worklist['metadata']['candidateCount']} entries")


if __name__ == "__main__":
    main()
