from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MICROBIOLOGY_DIR = Path("docs") / "microbiology"
REQUIRED_FILES = [
    MICROBIOLOGY_DIR / "susceptibility_huvn_bgn_non_enterobacterias_2025.json",
]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"ERROR: {message}")


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"ERROR: invalid JSON in {path}: {exc}") from exc


def validate_susceptibility_file(path: Path) -> None:
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
        require(record.get("antibiotic"), f"{prefix} lacks antibiotic")
        percent = record.get("susceptibilityPercent")
        require(isinstance(percent, (int, float)), f"{prefix} lacks numeric susceptibilityPercent")
        require(0 <= percent <= 100, f"{prefix} susceptibilityPercent out of range")


def main() -> None:
    for path in REQUIRED_FILES:
        require(path.exists(), f"missing microbiology pending table file: {path}")
        validate_susceptibility_file(path)

    print("Pending microbiology table extractions OK")


if __name__ == "__main__":
    main()
