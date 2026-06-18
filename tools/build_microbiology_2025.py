from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

DOCS_DIR = Path("docs")
MICROBIOLOGY_DIR = DOCS_DIR / "microbiology"
MAP_PATH = MICROBIOLOGY_DIR / "microbiology_map_2025.json"
MANIFEST_PATH = MICROBIOLOGY_DIR / "microbiology_manifest.json"

SOURCE_PDF = {
    "title": "Mapa Microbiológico 2025",
    "uploadedFileName": "Mapa Microbiologico 2025 (1).pdf",
    "sha256": "a3c338b169f5a54e807e003b07420494ce2e2f4803d202cf5414d67379b4825e",
    "sizeBytes": 45735934,
    "pageCount": 73,
    "dataRepositoryPath": None,
    "sourceUrl": None,
    "availableInData": False,
    "note": "PDF corregido aportado en conversación; pendiente de incorporar como binario al repositorio si se decide publicar el PDF desde DATA.",
}

# title, printedPage, scope, population, sampleType, service, contentType, organismGroup
SECTION_ROWS = [
    ("Aislamientos HUVN bacilos Gram Negativos", 5, "huvn", "all", None, None, "susceptibility_table", "gram_negative"),
    ("Aislamientos HUVN bacterias Gram positivas", 6, "huvn", "all", None, None, "susceptibility_table", "gram_positive"),
    ("Aislamientos HUVN bacterias crecimiento dificultoso y anaerobias", 7, "huvn", "all", None, None, "susceptibility_table", "difficult_growth_or_anaerobes"),
    ("Aislamientos HUVN sensibilidad antibióticos poco ensayados", 8, "huvn", "all", None, None, "susceptibility_table", "rarely_tested_antibiotics"),
    ("Aislamientos HUVN. Mecanismos de resistencia", 9, "huvn", "all", None, None, "resistance_mechanisms", "resistance_mechanisms"),
    ("Aislamientos hospital general bacilos Gram negativos", 10, "hospital_general", "all", None, None, "susceptibility_table", "gram_negative"),
    ("Aislamientos hospital General bacterias Gram positivas, crecimiento dificultoso y anaerobias", 11, "hospital_general", "all", None, None, "susceptibility_table", "gram_positive"),
    ("Aislamientos hospital neurotraumatología bacilos Gram negativos", 12, "neurotraumatologia", "all", None, None, "susceptibility_table", "gram_negative"),
    ("Aislamientos hospital neurotraumatología bacterias Gram positivas crecimiento dificultoso y anaerobias", 13, "neurotraumatologia", "all", None, None, "susceptibility_table", "gram_positive"),
    ("Aislamientos hospital materno-infantil bacilos Gram negativos", 14, "materno_infantil", "all", None, None, "susceptibility_table", "gram_negative"),
    ("Aislamientos hospital materno-infantil bacterias Gram positivas y crecimiento dificultoso", 15, "materno_infantil", "all", None, None, "susceptibility_table", "gram_positive"),
    ("Aislamientos de pacientes pediátricos HUVN bacilos Gram negativos, bacterias Gram positivas y de crecimiento dificultoso", 16, "huvn", "pediatric", None, None, "susceptibility_table", "mixed"),
    ("Aislamientos pacientes adultos bacilos Gram negativos", 17, "huvn", "adult", None, None, "susceptibility_table", "gram_negative"),
    ("Aislamientos pacientes adultos bacterias Gram positivas", 18, "huvn", "adult", None, None, "susceptibility_table", "gram_positive"),
    ("Aislamientos pacientes adultos bacterias de crecimiento dificultoso y anaerobias", 19, "huvn", "adult", None, None, "susceptibility_table", "difficult_growth_or_anaerobes"),
    ("Aislamientos extrahospitalarios bacilos Gram negativos", 20, "extrahospitalario", "adult", None, None, "susceptibility_table", "gram_negative"),
    ("Aislamientos extrahospitalarios bacterias Gram positivas", 21, "extrahospitalario", "adult", None, None, "susceptibility_table", "gram_positive"),
    ("Aislamientos extrahospitalarios bacterias de crecimiento dificultoso y anaerobias", 22, "extrahospitalario", "adult", None, None, "susceptibility_table", "difficult_growth_or_anaerobes"),
    ("Aislamientos HUVN de hemocultivos bacilos Gram negativos", 23, "huvn", "all", "hemocultivo", None, "susceptibility_table", "gram_negative"),
    ("Aislamientos HUVN de hemocultivos bacterias Gram positivas, crecimiento dificultoso y anaerobias", 24, "huvn", "all", "hemocultivo", None, "susceptibility_table", "gram_positive"),
    ("Aislamientos HUVN de exudados bacilos Gram negativos", 25, "huvn", "all", "exudado", None, "susceptibility_table", "gram_negative"),
    ("Aislamientos HUVN de exudados bacterias Gram positivas, crecimiento dificultoso y anaerobias", 26, "huvn", "all", "exudado", None, "susceptibility_table", "gram_positive"),
    ("Aislamientos HUVN de muestras respiratorias bacilos Gram negativos, positivas y de crecimiento dificultoso", 27, "huvn", "all", "respiratoria", None, "susceptibility_table", "gram_negative"),
    ("Aislamientos HUVN de orina bacilos Gram negativos y bacterias Gram positivas", 28, "huvn", "all", "orina", None, "susceptibility_table", "mixed"),
    ("Aislamientos S Cardiología bacilos Gram negativos y bacterias Gram positivas", 29, "service_specific", "all", None, "Cardiología", "susceptibility_table", "mixed"),
    ("Mecanismos de resistencia S. Cardiología", 30, "service_specific", "all", None, "Cardiología", "resistance_mechanisms", "resistance_mechanisms"),
    ("Aislamientos S Cirugía bacilos Gram negativos y bacterias Gram positivas", 31, "service_specific", "all", None, "Cirugía", "susceptibility_table", "mixed"),
    ("Mecanismos de resistencia S. Cirugía", 32, "service_specific", "all", None, "Cirugía", "resistance_mechanisms", "resistance_mechanisms"),
    ("Aislamientos S Cirugía Cardio-vascular bacilos Gram negativos y bacterias Gram positivas", 33, "service_specific", "all", None, "Cirugía Cardio-vascular", "susceptibility_table", "mixed"),
    ("Mecanismos de resistencia S. Cirugía Cardio-vascular", 34, "service_specific", "all", None, "Cirugía Cardio-vascular", "resistance_mechanisms", "resistance_mechanisms"),
    ("Aislamientos S Cirugía Maxilofacial bacilos Gram negativos y bacterias Gram positivas", 35, "service_specific", "all", None, "Cirugía Maxilofacial", "susceptibility_table", "mixed"),
    ("Aislamientos S Cirugía Plástica bacilos Gram negativos y bacterias Gram positivas", 36, "service_specific", "all", None, "Cirugía Plástica", "susceptibility_table", "mixed"),
    ("Mecanismos de resistencia S. Cirugía Plástica", 37, "service_specific", "all", None, "Cirugía Plástica", "resistance_mechanisms", "resistance_mechanisms"),
    ("Aislamientos S Cirugía Torácica bacilos Gram negativos y bacterias Gram positivas", 38, "service_specific", "all", None, "Cirugía Torácica", "susceptibility_table", "mixed"),
    ("Mecanismos de resistencia S. Cirugía Torácica", 39, "service_specific", "all", None, "Cirugía Torácica", "resistance_mechanisms", "resistance_mechanisms"),
    ("Aislamientos S. Cuidados Críticos hospital general", 40, "service_specific", "all", None, "Cuidados Críticos hospital general", "susceptibility_table", "mixed"),
    ("Mecanismos de resistencia S. Cuidados Críticos hospital general", 41, "service_specific", "all", None, "Cuidados Críticos hospital general", "resistance_mechanisms", "resistance_mechanisms"),
    ("Aislamientos S. Cuidados Críticos Neurotraumatología", 42, "service_specific", "all", None, "Cuidados Críticos Neurotraumatología", "susceptibility_table", "mixed"),
    ("Mecanismos de resistencia S. Cuidados Críticos Neurotraumatología", 43, "service_specific", "all", None, "Cuidados Críticos Neurotraumatología", "resistance_mechanisms", "resistance_mechanisms"),
    ("Aislamientos S. Ginecología y Obstetricia", 44, "service_specific", "all", None, "Ginecología y Obstetricia", "susceptibility_table", "mixed"),
    ("Mecanismos de resistencia S. Ginecología y Obstetricia", 45, "service_specific", "all", None, "Ginecología y Obstetricia", "resistance_mechanisms", "resistance_mechanisms"),
    ("Aislamientos S Hematología bacilos Gram negativos, bacterias Gram positivas y de crecimiento dificultoso", 46, "service_specific", "all", None, "Hematología", "susceptibility_table", "mixed"),
    ("Mecanismos S. Hematología", 47, "service_specific", "all", None, "Hematología", "resistance_mechanisms", "resistance_mechanisms"),
    ("Aislamientos S. Medicina Interna bacilos Gram negativos y bacterias Gram positivas", 48, "service_specific", "all", None, "Medicina Interna", "susceptibility_table", "mixed"),
    ("Mecanismos S. Medicina Interna", 49, "service_specific", "all", None, "Medicina Interna", "resistance_mechanisms", "resistance_mechanisms"),
    ("Aislamientos S. Nefrología", 50, "service_specific", "all", None, "Nefrología", "susceptibility_table", "mixed"),
    ("Mecanismos S. Nefrología", 51, "service_specific", "all", None, "Nefrología", "resistance_mechanisms", "resistance_mechanisms"),
    ("Aislamientos S. Neumología bacilos Gram negativos, bacterias Gram positivas y crecimiento dificultoso", 52, "service_specific", "all", None, "Neumología", "susceptibility_table", "mixed"),
    ("Mecanismos S. Neumología", 53, "service_specific", "all", None, "Neumología", "resistance_mechanisms", "resistance_mechanisms"),
    ("Aislamientos S. Neurología", 54, "service_specific", "all", None, "Neurología", "susceptibility_table", "mixed"),
    ("Mecanismos S. Neurología", 55, "service_specific", "all", None, "Neurología", "resistance_mechanisms", "resistance_mechanisms"),
    ("Aislamientos S. Oncología", 56, "service_specific", "all", None, "Oncología", "susceptibility_table", "mixed"),
    ("Mecanismos S. Oncología", 57, "service_specific", "all", None, "Oncología", "resistance_mechanisms", "resistance_mechanisms"),
    ("Aislamientos S. Reanimación", 58, "service_specific", "all", None, "Reanimación", "susceptibility_table", "mixed"),
    ("Mecanismos S. Reanimación", 59, "service_specific", "all", None, "Reanimación", "resistance_mechanisms", "resistance_mechanisms"),
    ("Aislamientos servicio Traumatología", 60, "service_specific", "all", None, "Traumatología", "susceptibility_table", "mixed"),
    ("Servicio Traumatología mecanismos de resistencia", 61, "service_specific", "all", None, "Traumatología", "resistance_mechanisms", "resistance_mechanisms"),
    ("Aislamientos S. Urología", 62, "service_specific", "all", None, "Urología", "susceptibility_table", "mixed"),
    ("Gráfico 1. Evolución de la sensibilidad a los antibióticos de Escherichia coli", 64, "huvn", "all", None, None, "trend_chart", "trend"),
    ("Gráfico 2. Evolución de la sensibilidad a los antibióticos de Klebsiella pneumoniae", 65, "huvn", "all", None, None, "trend_chart", "trend"),
    ("Gráfico 3. Evolución de la sensibilidad a los antibióticos de K. oxytoca y K. aerogenes", 66, "huvn", "all", None, None, "trend_chart", "trend"),
    ("Gráfico 4. Evolución de la sensibilidad a los antibióticos de Enterobacter cloacae complex", 67, "huvn", "all", None, None, "trend_chart", "trend"),
    ("Gráfico 5. Evolución de la sensibilidad a los antibióticos de P. mirabilis y M. morganii", 68, "huvn", "all", None, None, "trend_chart", "trend"),
    ("Gráfico 6. Evolución de la sensibilidad a los antibióticos P. aeruginosa", 69, "huvn", "all", None, None, "trend_chart", "trend"),
    ("Gráfico 7. Evolución sensibilidad a los antibióticos Staphylococcus aureus y S. aureus meticilin resistentes", 70, "huvn", "all", None, None, "trend_chart", "trend"),
    ("Gráfico 8. Evolución de la sensibilidad a los antibióticos Enterococcus faecalis y E. faecium", 71, "huvn", "all", None, None, "trend_chart", "trend"),
]

# microorganism, mechanism, count, percent
RESISTANCE_MECHANISM_ROWS = [
    ("Aci. baumanii cplx", "OXA", 4, 21.05),
    ("Aeromonas", "VIM", 1, 2.85),
    ("Cit freundii cplx", "OXA", 3, 2.97),
    ("Cit freundii cplx", "KPC", 1, 0.99),
    ("Cit freundii cplx", "VIM", 2, 1.98),
    ("Cit freundii cplx", "NDM", 1, 0.99),
    ("Cit freundii cplx", "AMPc", 4, 3.96),
    ("E. coli", "BLEE", 742, 13.35),
    ("E. coli", "OXA", 8, 0.14),
    ("E. coli", "VIM", 1, 0.01),
    ("E. coli", "NDM", 3, 0.05),
    ("E. coli", "AMPc", 19, 0.34),
    ("Ent. cloacae cplx", "BLEE", 1, 0.23),
    ("Ent. cloacae cplx", "OXA", 9, 2.53),
    ("Ent. cloacae cplx", "KPC", 9, 2.53),
    ("Ent. cloacae cplx", "VIM", 22, 6.19),
    ("Ent. cloacae cplx", "NDM", 1, 0.28),
    ("Ent. cloacae cplx", "AMPc", 18, 5.07),
    ("K. oxytoca", "BLEE", 18, 10.22),
    ("K. oxytoca", "OXA", 1, 0.56),
    ("K. oxytoca", "VIM", 1, 0.56),
    ("K. oxytoca", "NDM", 2, 1.13),
    ("K. pneumoniae", "BLEE", 279, 19.51),
    ("K. pneumoniae", "OXA", 119, 8.32),
    ("K. pneumoniae", "KPC", 3, 0.2),
    ("K. pneumoniae", "NDM", 39, 2.72),
    ("K. pneumoniae", "AMPc", 14, 0.97),
    ("Klebsiella", "BLEE", 1, 6.25),
    ("Klebsiella", "OXA", 1, 6.25),
    ("Proteus mirabilis", "BLEE", 17, 3.1),
    ("Proteus mirabilis", "AMPc", 2, 0.36),
    ("Pseudomonas", "VIM", 6, 22.22),
    ("Pseudomonas", "IMP", 1, 3.7),
    ("Pseudomonas aeruginosa", "KPC", 4, 0.35),
    ("Pseudomonas aeruginosa", "VIM", 67, 6.01),
    ("Pseudomonas aeruginosa", "IMP", 18, 1.61),
    ("Pseudomonas aeruginosa", "NDM", 5, 0.44),
    ("Pseudomonas aeruginosa", "MDR", 155, 14.67),
    ("Pseudomonas aeruginosa", "XDR", 94, 8.9),
    ("Pseudomonas aeruginosa", "PDR", 1, 0.09),
    ("Raoultella", "VIM", 1, 7.69),
    ("S. aureus", "SARM", 187, 14.82),
    ("Salmonella", "BLEE", 1, 2.08),
]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    ascii_value = re.sub(r"[^a-z0-9]+", "-", ascii_value)
    return re.sub(r"-+", "-", ascii_value).strip("-")


def build_section_catalog() -> list[dict]:
    sections = []
    for title, printed_page, scope, population, sample_type, service, content_type, organism_group in SECTION_ROWS:
        sections.append(
            {
                "id": slugify(title),
                "title": title,
                "printedPage": printed_page,
                "pdfPage": printed_page + 1,
                "scope": scope,
                "population": population,
                "sampleType": sample_type,
                "service": service,
                "contentType": content_type,
                "organismGroup": organism_group,
                "extractionStatus": (
                    "cataloged_pending_chart_extraction"
                    if content_type == "trend_chart"
                    else "cataloged_pending_table_extraction"
                ),
                "manualReviewStatus": "pending",
            }
        )
    return sections


def build_resistance_mechanism_records() -> list[dict]:
    return [
        {
            "scope": "huvn",
            "population": "all",
            "sampleType": None,
            "service": None,
            "microorganism": microorganism,
            "resistanceMechanism": mechanism,
            "count": count,
            "percent": percent,
            "source": {
                "pdfPage": 10,
                "printedPage": 9,
                "tableTitle": "Aislamientos HUVN. Mecanismos de resistencia",
                "sourceText": None,
            },
            "review": {
                "status": "pending",
                "reviewer": None,
                "reviewedAt": None,
            },
        }
        for microorganism, mechanism, count, percent in RESISTANCE_MECHANISM_ROWS
    ]


def unique(values):
    return sorted({value for value in values if value is not None})


def build_map() -> dict:
    section_catalog = build_section_catalog()
    mechanism_records = build_resistance_mechanism_records()

    return {
        "metadata": {
            "title": "Mapa Microbiológico 2025 HUVN",
            "version": "0.3.0",
            "yearLabel": 2025,
            "dataYear": 2025,
            "generatedAt": now_iso(),
            "sourcePdf": SOURCE_PDF,
            "extractionStatus": "full_section_catalog_and_huvn_resistance_mechanisms_extracted",
            "manualReviewStatus": "pending_table_extraction_review",
            "interactiveUseAllowed": False,
        },
        "methodology": {
            "sourcePages": [2, 3],
            "notes": [
                "Datos de sensibilidad correspondientes a microorganismos aislados en muestras clínicas de pacientes ingresados en HUVN durante el año 2025.",
                "Se excluyen aislamientos procedentes de estudios de vigilancia epidemiológica y ambientales.",
                "Se siguen recomendaciones SEIMC 2014 y COESANT marzo 2022 para informes acumulados de sensibilidad.",
                "Las categorías S e I se agrupan para calcular los porcentajes de sensibilidad.",
                "Los porcentajes proceden de informes archivados en el SIL Modulab.",
                "Se contabiliza solo el primer aislado de cada paciente y tipo de muestra en un periodo de 30 días; aislamientos posteriores repetidos pueden contabilizarse.",
                "Cuando el número de aislados es menor de 30 se agrupan por género o grupo; algunos grupos con 10 aislamientos carecen de valor estadístico.",
                "El informe aporta datos para HUVN, hospital general, materno-infantil, neurotraumatología, atención primaria/extrahospitalario, servicios PROA, adultos, pediatría y tipos de muestra.",
                "Incluye evolución de sensibilidad 2021-2025 para microorganismos seleccionados.",
            ],
            "susceptibilityCategoryRule": "S + I agrupadas como sensibilidad/sensible cuando se incrementa la exposición",
            "deduplicationRule": "Primer aislado de cada paciente y tipo de muestra en un periodo de 30 días",
            "lowCountRule": "n < 30: escaso valor estadístico; algunos grupos con n >= 10 se informan pero carecen de valor estadístico",
            "excludedSamples": ["vigilancia epidemiológica", "ambientales"],
        },
        "sectionCatalog": section_catalog,
        "dimensions": {
            "scopes": unique(row[2] for row in SECTION_ROWS),
            "populations": unique(row[3] for row in SECTION_ROWS),
            "sampleTypes": unique(row[4] for row in SECTION_ROWS),
            "services": unique(row[5] for row in SECTION_ROWS),
            "contentTypes": unique(row[6] for row in SECTION_ROWS),
            "organismGroups": unique(row[7] for row in SECTION_ROWS),
        },
        "records": [],
        "resistanceMechanismRecords": mechanism_records,
        "schema": {
            "susceptibilityRecord": {
                "scope": "huvn|hospital_general|materno_infantil|neurotraumatologia|extrahospitalario|service_specific",
                "population": "adult|pediatric|all|null",
                "sampleType": "hemocultivo|orina|exudado|respiratoria|other|null",
                "service": "string|null",
                "microorganism": "string",
                "antibiotic": "string",
                "isolatesTested": "number|null",
                "susceptibilityPercent": "number|null",
                "resistanceMechanisms": "array",
                "lowCountWarning": "boolean",
                "source": {
                    "pdfPage": "number|null",
                    "printedPage": "number|null",
                    "tableTitle": "string|null",
                    "sourceText": "string|null",
                },
                "review": {
                    "status": "pending|reviewed|rejected",
                    "reviewer": "string|null",
                    "reviewedAt": "string|null",
                },
            },
            "resistanceMechanismRecord": {
                "scope": "string",
                "population": "string",
                "sampleType": "string|null",
                "service": "string|null",
                "microorganism": "string",
                "resistanceMechanism": "BLEE|OXA|KPC|VIM|IMP|NDM|AMPc|MDR|XDR|PDR|SARM|other",
                "count": "number",
                "percent": "number",
                "source": "object",
                "review": "object",
            },
        },
        "warnings": [
            "Mapa microbiológico interactivo pendiente de extracción de tablas de sensibilidad y validación manual. Consultar el PDF original.",
            "Los registros de mecanismos de resistencia son una primera extracción manual asistida y siguen con review.status = pending.",
            "No hay registros de sensibilidad antimicrobiana estructurados activos en esta versión.",
            "No activar en la app como soporte decisional hasta revisión manual.",
        ],
    }


def build_manifest(microbiology_map: dict) -> dict:
    dimensions = microbiology_map["dimensions"]
    return {
        "version": "0.3.0",
        "generatedAt": now_iso(),
        "status": "draft_full_catalog_with_pending_mechanism_records",
        "title": "Mapa microbiológico HUVN",
        "currentMap": {
            "yearLabel": 2025,
            "dataYear": 2025,
            "path": "microbiology/microbiology_map_2025.json",
            "sourcePdf": SOURCE_PDF,
            "reviewStatus": "pending_table_extraction_review",
            "interactiveMapAvailable": False,
            "catalogAvailable": True,
            "catalogStatus": "complete_from_index",
            "catalogedSectionCount": len(microbiology_map["sectionCatalog"]),
            "expectedSectionCountFromIndex": len(SECTION_ROWS),
            "recordCount": len(microbiology_map["records"]),
            "resistanceMechanismRecordCount": len(microbiology_map["resistanceMechanismRecords"]),
        },
        "fallback": {
            "behavior": "show_notice_or_source_pdf_when_available",
            "message": "Mapa microbiológico interactivo pendiente de extracción y validación. Consultar el PDF original hasta revisión manual.",
        },
        "supportedDimensions": {
            "scope": dimensions["scopes"],
            "population": dimensions["populations"],
            "sampleType": dimensions["sampleTypes"],
            "service": dimensions["services"],
            "microorganism": [],
            "antibiotic": [],
            "resistanceMechanism": ["AMPc", "BLEE", "IMP", "KPC", "MDR", "NDM", "OXA", "PDR", "SARM", "VIM", "XDR"],
        },
        "warnings": [
            "No usar como mapa interactivo hasta completar extracción estructurada y revisión manual.",
            "El informe anual puede contener tablas con bajo número de aislados; debe conservarse advertencia si n < 30.",
            "El PDF corregido indica año de datos 2025.",
            "Catálogo completo desde índice; primera extracción de mecanismos HUVN pendiente de revisión manual.",
        ],
    }


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    MICROBIOLOGY_DIR.mkdir(parents=True, exist_ok=True)

    microbiology_map = build_map()
    manifest = build_manifest(microbiology_map)

    write_json(MAP_PATH, microbiology_map)
    write_json(MANIFEST_PATH, manifest)

    print(f"Microbiology sections: {len(microbiology_map['sectionCatalog'])}")
    print(f"Resistance mechanism records: {len(microbiology_map['resistanceMechanismRecords'])}")
    print(f"Written: {MAP_PATH}")
    print(f"Written: {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
