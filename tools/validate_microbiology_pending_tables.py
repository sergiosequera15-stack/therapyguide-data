from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MICROBIOLOGY_DIR = Path("docs") / "microbiology"
REQUIRED_SUSCEPTIBILITY_FILES = [
    MICROBIOLOGY_DIR / "susceptibility_huvn_bgn_non_enterobacterias_2025.json",
    MICROBIOLOGY_DIR / "susceptibility_huvn_bgn_enterobacterias_2025.json",
    MICROBIOLOGY_DIR / "susceptibility_huvn_bgn_enterobacterias_second_pass_2025.json",
]
REQUIRED_DICTIONARY_FILES = [
    MICROBIOLOGY_DIR / "antibiotic_abbreviations_2025.json",
]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"ERROR: {message}")


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"ERROR: invalid JSON in {path}: {exc}") from exc


def validate_dictionary_file(path: Path) -> set[str]:
    data = load_json(path)
    metadata = data.get("metadata") or {}
    abbreviations = data.get("abbreviations") or []
    review = data.get("review") or {}

    require(metadata.get("sourcePdf"), f"{path} lacks metadata.sourcePdf")
    require(metadata.get("manualReviewStatus") == "pending", f"{path} must remain pending before clinical use")
    require(isinstance(abbreviations, list) and abbreviations, f"{path} must contain abbreviations[]")
    require(review.get("status") == "pending", f"{path} review.status must be pending")

    codes: set[str] = set()
    for index, item in enumerate(abbreviations):
        prefix = f"{path.name}.abbreviations[{index}]"
        code = item.get("code")
        name = item.get("name")
        require(isinstance(code, str) and code.strip(), f"{prefix} lacks code")
        require(isinstance(name, str) and name.strip(), f"{prefix} lacks name")
        require(code not in codes, f"{path.name} duplicate abbreviation code: {code}")
        codes.add(code)

    return codes


def validate_susceptibility_file(path: Path, allowed_antibiotics: set[str]) -> None:
    data = load_json(path)
    metadata = data.get("metadata") or {}
    records = data.get("records") or []
    review = data.get("review") or {}

    require(metadata.get("sourcePdf"), f"{path} lacks metadata.sourcePdf")
    require(metadata.get("manualReviewStatus") == "pending", f"{path} must remain pending before clinical use")
    require(metadata.get("interactiveUseAllowed") is False, f"{path} must not be interactively enabled")
    require(isinstance(records, list) and records, f"{path} must contain records[]")
    require(review.get("status") == "pending", f"{path} review.status must be pending")

    for index, record in enumerate(records):
        prefix = f"{path.name}.records[{index}]"
        require(record.get("microorganism"), f"{prefix} lacks microorganism")
        require(isinstance(record.get("isolatesTested"), int), f"{prefix} lacks integer isolatesTested")
        antibiotic = record.get("antibiotic")
        require(isinstance(antibiotic, str) and antibiotic, f"{prefix} lacks antibiotic")
        require(antibiotic in allowed_antibiotics, f"{prefix} antibiotic {antibiotic} missing from abbreviation dictionary")
        percent = record.get("susceptibilityPercent")
        require(isinstance(percent, (int, float)), f"{prefix} lacks numeric susceptibilityPercent")
        require(0 <= percent <= 100, f"{prefix} susceptibilityPercent out of range")


def main() -> None:
    allowed_antibiotics: set[str] = set()

    for path in REQUIRED_DICTIONARY_FILES:
        require(path.exists(), f"missing microbiology dictionary file: {path}")
        allowed_antibiotics.update(validate_dictionary_file(path))

    for path in REQUIRED_SUSCEPTIBILITY_FILES:
        require(path.exists(), f"missing microbiology pending table file: {path}")
        validate_susceptibility_file(path, allowed_antibiotics)

    print("Pending microbiology table extractions OK")
    print(f"Antibiotic dictionary entries: {len(allowed_antibiotics)}")
    print(f"Susceptibility files: {len(REQUIRED_SUSCEPTIBILITY_FILES)}")


if __name__ == "__main__":
    main()
