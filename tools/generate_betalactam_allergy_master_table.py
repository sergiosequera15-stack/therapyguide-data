from __future__ import annotations

import json
from pathlib import Path
from typing import Any

OUTPUT_PATH = Path("docs/rules/betalactam_allergy_options_master_table_draft.json")
EXPECTED_SCHEMA = "compact_rows_v2"
EXPECTED_ROW_COUNT = 76


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"ERROR: missing {path}; reviewed v2 master table must be committed before normalization") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"ERROR: invalid JSON in {path}: {exc}") from exc


def main() -> None:
    data = load_json(OUTPUT_PATH)
    if not isinstance(data, dict):
        raise SystemExit(f"ERROR: {OUTPUT_PATH} must contain a JSON object")
    metadata = data.get("metadata") or {}
    rows = data.get("rows") or []
    if metadata.get("schema") != EXPECTED_SCHEMA:
        raise SystemExit(f"ERROR: expected {EXPECTED_SCHEMA}, found {metadata.get('schema')!r}")
    if metadata.get("rowCount") != EXPECTED_ROW_COUNT or len(rows) != EXPECTED_ROW_COUNT:
        raise SystemExit(f"ERROR: expected {EXPECTED_ROW_COUNT} v2 rows, found metadata={metadata.get('rowCount')!r}, rows={len(rows)}")
    OUTPUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Normalized {OUTPUT_PATH} with {metadata.get('rowCount')} reviewed v2 draft rows ({metadata.get('schema')})")


if __name__ == "__main__":
    main()
