from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

MASTER_TABLE_PATH = Path("docs/rules/betalactam_allergy_options_master_table_draft.json")
CONSULTANT_PATH = Path("docs/rules/betalactam_allergy_consultant.json")
EXPECTED_SCHEMA = "compact_rows_v2"
EXPECTED_ROW_COUNT = 76


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_value = ascii_value.lower()
    ascii_value = re.sub(r"[^a-z0-9]+", "-", ascii_value)
    ascii_value = re.sub(r"-+", "-", ascii_value).strip("-")
    return ascii_value or "record"


def rows_to_records(table: dict[str, Any]) -> list[dict[str, Any]]:
    columns = table.get("columns") or []
    rows = table.get("rows") or []
    if not isinstance(columns, list) or not isinstance(rows, list):
        raise SystemExit("ERROR: compact master table must contain columns and rows lists")
    records: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, list) or len(row) != len(columns):
            raise SystemExit(f"ERROR: invalid row at index {index}")
        records.append(dict(zip(columns, row, strict=True)))
    return records


def build_option_record(record: dict[str, Any]) -> dict[str, Any]:
    row_number = record["rowNumber"]
    syndrome = record.get("syndrome") or ""
    subsyndrome = record.get("subsyndrome") or ""
    options_text = record.get("optionsText") or ""
    source_topic_id = record.get("sourceTopicId") or ""
    source_url = record.get("sourceUrl") or ""
    warnings = record.get("qualityWarnings") or []

    option_record = {
        "id": f"allergy-option-row-{row_number:03d}-{slugify(syndrome)}-{slugify(subsyndrome)[:48]}",
        "rowNumber": row_number,
        "syndrome": syndrome,
        "subsyndrome": subsyndrome,
        "population": record.get("population") or "",
        "allergyContext": record.get("allergyContext") or "",
        "options": [
            {
                "label": "Opciones recogidas en la fuente",
                "description": "Texto fuente disponible para consulta; no es recomendación automática ni ranking.",
                "sourceText": options_text,
                "displayText": options_text,
                "isTherapeuticRecommendation": False,
                "isRanked": False,
                "isDoseCalculator": False,
                "structuredDoseAvailable": False,
            }
        ],
        "source": {
            "sourceTopicId": source_topic_id,
            "sourceUrl": source_url,
            "sourceRefId": record.get("sourceRefId") or "",
            "sourceConfirmedByUser": "source_confirmed_by_user" in warnings,
            "sourceTopicNotInCurrentSnapshot": "source_topic_not_in_current_guide_topics" in warnings,
        },
        "notes": record.get("reviewNotes") or "",
        "warnings": warnings,
        "clinicalUseAllowed": False,
        "clinicalDecisionSupportAllowed": False,
        "therapeuticRecommendationAllowed": False,
        "alternativeAntibioticRecommendationAllowed": False,
    }
    return option_record


def build_consultant(table: dict[str, Any]) -> dict[str, Any]:
    metadata = table.get("metadata") or {}
    if metadata.get("schema") != EXPECTED_SCHEMA:
        raise SystemExit(f"ERROR: expected master table schema {EXPECTED_SCHEMA}")
    records = rows_to_records(table)
    if len(records) != EXPECTED_ROW_COUNT:
        raise SystemExit(f"ERROR: expected {EXPECTED_ROW_COUNT} records, found {len(records)}")

    option_records = [build_option_record(record) for record in records]
    syndromes = sorted({record["syndrome"] for record in option_records})

    return {
        "metadata": {
            "title": "Opciones en alergia a betalactámicos por síndrome",
            "version": "0.3.0",
            "generatedAt": metadata.get("generatedAt", "2026-06-25T00:00:00Z"),
            "status": "draft_with_source_backed_options_pending_manual_review",
            "consultationMode": "syndrome_subsyndrome_allergy_options",
            "source": "betalactam_allergy_options_master_table_draft.json",
            "masterTableSchema": metadata.get("schema"),
            "masterTableRowCount": len(records),
            "optionRecordCount": len(option_records),
            "syndromeCount": len(syndromes),
            "clinicalUseAllowed": False,
            "clinicalDecisionSupportAllowed": False,
            "therapeuticRecommendationAllowed": False,
            "alternativeAntibioticRecommendationAllowed": False,
            "readyForAppConsultant": False,
            "manualReviewStatus": "accepted_for_draft_display_not_clinical_use",
            "doseDisplayMode": "show_all_available_source_text_unstructured",
            "notes": [
                "Opciones generadas desde la tabla maestra v2 revisada.",
                "Mostrar todas las dosis disponibles como texto fuente no estructurado.",
                "No clasifica gravedad de alergia, no ordena opciones y no genera recomendaciones terapéuticas automáticas.",
                "No usar como calculadora de dosis ni como CDS."
            ]
        },
        "selectors": [
            {
                "id": "syndrome",
                "label": "Síndrome",
                "type": "single_select_required",
                "valuesFrom": "optionRecords.syndrome"
            },
            {
                "id": "subsyndrome",
                "label": "Subsíndrome",
                "type": "single_select_optional",
                "valuesFrom": "optionRecords.subsyndrome",
                "dependsOn": "syndrome"
            }
        ],
        "optionRecords": option_records,
        "emptyState": {
            "title": "Sin opciones para el filtro seleccionado",
            "message": "No hay opciones publicadas en DATA para esta combinación de síndrome/subsíndrome."
        },
        "recordSchema": {
            "requiredFields": ["id", "syndrome", "allergyContext", "options", "source"],
            "optionalFields": ["subsyndrome", "population", "notes", "warnings", "rowNumber"],
            "optionFields": ["label", "description", "sourceText", "displayText", "isTherapeuticRecommendation", "isRanked", "isDoseCalculator"]
        },
        "hardSafetyRules": {
            "mustNotRankOptions": True,
            "mustNotGenerateTherapeuticRecommendations": True,
            "mustNotInferOptionsFromAllergySeverity": True,
            "mustOnlyShowSourceBackedOptions": True,
            "mustShowPendingExtractionWhenNoRecords": True,
            "mustShowClinicalUseBlockedBanner": True,
            "mustPreserveSyndromeAndSubsyndromeContext": True,
        },
        "appBehavior": {
            "mayRenderInResourcesConsultantsSection": True,
            "mayRenderAsSyndromeSubsyndromeLookup": True,
            "mayStoreAnswersLocally": False,
            "mayUseAnswersToFilterTherapeuticRules": False,
            "mayUseAnswersToGenerateAntibioticAlternatives": False,
            "mayShowEmptyDraftState": True,
            "mustShowNonClinicalDraftBanner": True,
            "mustShowSourceTextVerbatim": True,
        },
        "nextExtractionTasks": [
            "Mantener consulta por síndrome/subsíndrome sin ranking ni recomendación.",
            "Si se crean calculadoras futuras, deben salir de módulo separado y validado, no de este texto fuente.",
            "Actualizar automáticamente desde tabla maestra v2 cuando cambie DATA."
        ]
    }


def main() -> None:
    table = load_json(MASTER_TABLE_PATH)
    consultant = build_consultant(table)
    CONSULTANT_PATH.write_text(json.dumps(consultant, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Generated {CONSULTANT_PATH} with {consultant['metadata']['optionRecordCount']} draft option records")


if __name__ == "__main__":
    main()
