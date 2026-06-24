from __future__ import annotations

import json
from pathlib import Path
from typing import Any

OUTPUT_PATH = Path("docs/rules/betalactam_allergy_options_master_table_draft.json")
EXPECTED_SCHEMA = "compact_rows_v2"
EXPECTED_ROW_COUNT = 76
SOURCE_TOPIC_ALIASES = {
    "tratamiento_de_infecciones_urinarias": "infeccion_del_tracto_urinario",
    "infeccion_intraabdominal_complicada": "infeccion_intraabdominal_complicada_en_pacientes_adultos",
    "infeccion_intrabdominal_complicada_infantil": "infeccion_intraabdominal_en_pacientes_pediatricos",
}
SOURCE_URL_ALIASES = {
    "https://www.huvn.es/profesionales/de_interes_sanitario/proa_programa_de_optimizacion_de_la_antibioterapia/guia_de_antibioterapia/tratamiento_de_infecciones_urinarias": "https://www.huvn.es/profesionales/de_interes_sanitario/proa_programa_de_optimizacion_de_la_antibioterapia/guia_de_antibioterapia/infeccion_del_tracto_urinario",
    "https://www.huvn.es/profesionales/de_interes_sanitario/proa_programa_de_optimizacion_de_la_antibioterapia/guia_de_antibioterapia/infeccion_intraabdominal_complicada": "https://www.huvn.es/profesionales/de_interes_sanitario/proa_programa_de_optimizacion_de_la_antibioterapia/guia_de_antibioterapia/infeccion_intraabdominal_complicada_en_pacientes_adultos",
    "https://www.huvn.es/profesionales/de_interes_sanitario/proa_programa_de_optimizacion_de_la_antibioterapia/guia_de_antibioterapia/infeccion_intrabdominal_complicada_infantil": "https://www.huvn.es/profesionales/de_interes_sanitario/proa_programa_de_optimizacion_de_la_antibioterapia/guia_de_antibioterapia/infeccion_intraabdominal_complicada_en_pacientes_adultos/infeccion_intraabdominal_en_pacientes_pediatricos",
}
KNOWN_SOURCE_TOPICS_NOT_IN_CURRENT_GUIDE_SNAPSHOT = {
    "infeccion_intraabdominal_en_pacientes_pediatricos",
}


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"ERROR: missing {path}; reviewed v2 master table must be committed before normalization") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"ERROR: invalid JSON in {path}: {exc}") from exc


def normalize_rows(data: dict[str, Any]) -> int:
    columns = data.get("columns") or []
    rows = data.get("rows") or []
    if not isinstance(columns, list) or not isinstance(rows, list):
        raise SystemExit("ERROR: master table must contain columns and rows lists")
    try:
        topic_idx = columns.index("sourceTopicId")
        url_idx = columns.index("sourceUrl")
        warning_idx = columns.index("qualityWarnings")
    except ValueError as exc:
        raise SystemExit("ERROR: compact_rows_v2 source columns are missing") from exc

    changed = 0
    for row_number, row in enumerate(rows, start=1):
        if not isinstance(row, list) or len(row) != len(columns):
            raise SystemExit(f"ERROR: invalid row {row_number}")
        old_topic = row[topic_idx]
        old_url = row[url_idx]
        new_topic = SOURCE_TOPIC_ALIASES.get(old_topic, old_topic)
        new_url = SOURCE_URL_ALIASES.get(old_url, old_url)
        if new_topic != old_topic:
            row[topic_idx] = new_topic
            changed += 1
        if new_url != old_url:
            row[url_idx] = new_url
            changed += 1
        warnings = row[warning_idx]
        if not isinstance(warnings, list):
            raise SystemExit(f"ERROR: row {row_number} qualityWarnings must be a list")
        if row[topic_idx] in KNOWN_SOURCE_TOPICS_NOT_IN_CURRENT_GUIDE_SNAPSHOT and "source_topic_not_in_current_guide_topics" not in warnings:
            warnings.append("source_topic_not_in_current_guide_topics")
            changed += 1
    return changed


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
    changed = normalize_rows(data)
    OUTPUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Normalized {OUTPUT_PATH} with {metadata.get('rowCount')} reviewed v2 draft rows ({metadata.get('schema')}); normalized fields={changed}")


if __name__ == "__main__":
    main()
