from __future__ import annotations

import json
from pathlib import Path
from typing import Any

WORKLIST_PATH = Path("docs/rules/betalactam_allergy_options_curation_worklist.json")
CANDIDATE_PATH = Path("docs/rules/betalactam_allergy_options_candidate.json")
ALLOWED_DECISIONS = {"pending", "include", "exclude", "needs_discussion"}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"ERROR: {message}")


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"ERROR: invalid JSON in {path}: {exc}") from exc

    require(isinstance(data, dict), f"{path} must contain an object")
    return data


def validate_metadata(worklist: dict[str, Any]) -> None:
    metadata = worklist.get("metadata") or {}
    require(metadata.get("status") == "manual_curation_pending", "worklist status must remain manual_curation_pending")
    require(metadata.get("source") == "betalactam_allergy_options_candidate.json", "worklist source is invalid")
    require(metadata.get("clinicalUseAllowed") is False, "clinicalUseAllowed must be false")
    require(metadata.get("clinicalDecisionSupportAllowed") is False, "clinicalDecisionSupportAllowed must be false")
    require(metadata.get("therapeuticRecommendationAllowed") is False, "therapeuticRecommendationAllowed must be false")
    require(metadata.get("readyForAppConsultant") is False, "readyForAppConsultant must be false")


def validate_entries(worklist: dict[str, Any], candidates: dict[str, Any]) -> None:
    entries = worklist.get("entries") or []
    candidate_items = candidates.get("candidates") or []
    require(isinstance(entries, list), "worklist entries must be a list")
    require(isinstance(candidate_items, list), "candidate items must be a list")

    candidate_ids = {candidate.get("id") for candidate in candidate_items if isinstance(candidate, dict)}
    entry_ids = [entry.get("candidateId") for entry in entries if isinstance(entry, dict)]
    require(set(entry_ids) == candidate_ids, "worklist entries must match candidate ids exactly")
    require(len(entry_ids) == len(set(entry_ids)), "worklist candidateId values must be unique")

    for index, entry in enumerate(entries):
        require(isinstance(entry, dict), f"entries[{index}] must be an object")
        prefix = f"entries[{index}]"
        decision = entry.get("curationDecision")
        require(decision in ALLOWED_DECISIONS, f"{prefix}.curationDecision is invalid")
        require(entry.get("candidateId"), f"{prefix} lacks candidateId")
        require(entry.get("topicId"), f"{prefix} lacks topicId")
        require(entry.get("sourceText"), f"{prefix} lacks sourceText")
        require(entry.get("readyForConsultant") is False, f"{prefix}.readyForConsultant must be false")
        require(entry.get("isTherapeuticRecommendation") is False, f"{prefix}.isTherapeuticRecommendation must be false")

        if decision == "include":
            require(entry.get("proposedSyndrome"), f"{prefix} included entry lacks proposedSyndrome")
            extracted_options = entry.get("extractedOptions") or []
            require(isinstance(extracted_options, list) and extracted_options, f"{prefix} included entry lacks extractedOptions")
            for option_index, option in enumerate(extracted_options):
                require(isinstance(option, dict), f"{prefix}.extractedOptions[{option_index}] must be an object")
                require(option.get("label"), f"{prefix}.extractedOptions[{option_index}] lacks label")
                require(option.get("sourceText"), f"{prefix}.extractedOptions[{option_index}] lacks sourceText")
                require(option.get("isTherapeuticRecommendation") is False, f"{prefix}.extractedOptions[{option_index}] must not be a recommendation")

        if decision == "exclude":
            require(entry.get("excludeReason"), f"{prefix} excluded entry lacks excludeReason")


def main() -> None:
    require(WORKLIST_PATH.exists(), f"missing {WORKLIST_PATH}")
    require(CANDIDATE_PATH.exists(), f"missing {CANDIDATE_PATH}")
    worklist = load_json(WORKLIST_PATH)
    candidates = load_json(CANDIDATE_PATH)
    validate_metadata(worklist)
    validate_entries(worklist, candidates)
    print("Beta-lactam allergy curation worklist OK")


if __name__ == "__main__":
    main()
