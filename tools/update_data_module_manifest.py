from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

DOCS_DIR = Path("docs")
MANIFEST_PATH = DOCS_DIR / "manifest.json"

DATA_MODULES = {
    "rules": {
        "manifestUrl": "rules/rule_manifest.json",
        "recommendationRulesUrl": "rules/recommendation_rules.json",
        "allergyRulesUrl": "rules/allergy_rules.json",
        "validationReportUrl": "rules/rule_validation_report.json",
        "status": "draft",
    },
    "tools": {
        "scoresUrl": "tools/scores.json",
        "doseCalculatorsUrl": "tools/dose_calculators.json",
        "validationReportUrl": "tools/tool_validation_report.json",
        "status": "draft",
    },
    "microbiology": {
        "manifestUrl": "microbiology/microbiology_manifest.json",
        "currentMapUrl": "microbiology/microbiology_map_2025.json",
        "status": "draft_pending_extraction",
    },
}


def main() -> None:
    if not MANIFEST_PATH.exists():
        raise SystemExit(f"ERROR: {MANIFEST_PATH} does not exist")

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest["dataModules"] = DATA_MODULES
    manifest["dataModulesUpdatedAt"] = datetime.now(timezone.utc).isoformat()

    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("Updated manifest dataModules")


if __name__ == "__main__":
    main()
