from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

TOPICS_PATH = Path("docs/guide_topics.json")
OUTPUT_PATH = Path("docs/rules/betalactam_allergy_options_candidate.json")
SUMMARY_PATH = Path("docs/rules/betalactam_allergy_options_candidate_summary.json")
KEYWORD_RE = re.compile(
    r"(alergi[ao]s?|al[ée]rgic[ao]s?|betalact[áa]mic[oa]s?|beta[- ]?lact[áa]mic[oa]s?|b[- ]?lact[áa]mic[oa]s?)",
    re.IGNORECASE,
)
HEADING_RE = re.compile(r"(\d+(?:\.\d+)*\.-?[^:.]{3,140}|[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s]{6,140})")


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"ERROR: invalid JSON in {path}: {exc}") from exc


def normalize_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def split_sentences(text: str) -> list[str]:
    normalized = normalize_spaces(text)
    if not normalized:
        return []
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+|\s+(?=\d+(?:\.\d+)*\.-)", normalized) if part.strip()]


def find_context_heading(sentences: list[str], index: int) -> str | None:
    for previous in reversed(sentences[max(0, index - 8):index + 1]):
        match = HEADING_RE.search(previous)
        if match:
            return normalize_spaces(match.group(1))[:180]
    return None


def build_snippet(sentences: list[str], index: int) -> str:
    start = max(0, index - 1)
    end = min(len(sentences), index + 3)
    return normalize_spaces(" ".join(sentences[start:end]))[:1200]


def extract_candidates(topics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []

    for topic in topics:
        topic_id = str(topic.get("id") or "").strip()
        title = str(topic.get("title") or "").strip()
        source_url = str(topic.get("sourceUrl") or "").strip()
        content_text = str(topic.get("contentText") or "")
        sentences = split_sentences(content_text)

        for index, sentence in enumerate(sentences):
            if not KEYWORD_RE.search(sentence):
                continue

            snippet = build_snippet(sentences, index)
            if not snippet:
                continue

            candidate_id = f"{topic_id or 'topic'}__allergy_candidate_{len(candidates) + 1:03d}"
            candidates.append(
                {
                    "id": candidate_id,
                    "topicId": topic_id,
                    "topicTitle": title,
                    "sourceUrl": source_url,
                    "candidateContext": find_context_heading(sentences, index),
                    "matchedSentence": normalize_spaces(sentence)[:500],
                    "sourceText": snippet,
                    "status": "candidate_pending_manual_curation",
                    "readyForConsultant": False,
                    "isTherapeuticRecommendation": False,
                }
            )

    return candidates


def build_summary(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    by_topic: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        by_topic[str(candidate.get("topicId") or "unknown")].append(candidate)

    topic_summaries = []
    for topic_id, topic_candidates in sorted(by_topic.items(), key=lambda item: (-len(item[1]), item[0])):
        first = topic_candidates[0]
        context_counts = Counter(
            str(candidate.get("candidateContext") or "sin_contexto") for candidate in topic_candidates
        )
        topic_summaries.append(
            {
                "topicId": topic_id,
                "topicTitle": first.get("topicTitle"),
                "sourceUrl": first.get("sourceUrl"),
                "candidateCount": len(topic_candidates),
                "topContexts": [
                    {"context": context, "count": count}
                    for context, count in context_counts.most_common(8)
                ],
                "sampleCandidateIds": [candidate.get("id") for candidate in topic_candidates[:5]],
                "sampleMatchedSentences": [
                    candidate.get("matchedSentence") for candidate in topic_candidates[:3]
                ],
                "curationStatus": "pending_manual_review",
            }
        )

    return {
        "metadata": {
            "title": "Resumen de candidatos de opciones para alergia a betalactámicos",
            "version": "0.1.0",
            "generatedAt": "2026-06-24T00:00:00Z",
            "status": "summary_pending_manual_curation",
            "source": "betalactam_allergy_options_candidate.json",
            "topicCount": len(topic_summaries),
            "candidateCount": len(candidates),
            "clinicalUseAllowed": False,
            "clinicalDecisionSupportAllowed": False,
            "therapeuticRecommendationAllowed": False,
            "readyForAppConsultant": False,
        },
        "topics": topic_summaries,
        "manualCurationRequired": [
            "Priorizar temas con más candidatos y contextos claros.",
            "Fusionar duplicados por síndrome y subsíndrome.",
            "Descartar menciones generales que no sean opciones para alérgicos.",
            "Mantener sourceUrl, sourceText y trazabilidad antes de crear optionRecords.",
        ],
    }


def main() -> None:
    topics = load_json(TOPICS_PATH)
    if not isinstance(topics, list):
        raise SystemExit("ERROR: docs/guide_topics.json must contain a list")

    typed_topics = [topic for topic in topics if isinstance(topic, dict)]
    candidates = extract_candidates(typed_topics)
    output = {
        "metadata": {
            "title": "Candidatos de opciones para alergia a betalactámicos",
            "version": "0.1.0",
            "generatedAt": "2026-06-24T00:00:00Z",
            "status": "candidate_pending_manual_curation",
            "source": "guide_topics.json",
            "recordCount": len(candidates),
            "clinicalUseAllowed": False,
            "clinicalDecisionSupportAllowed": False,
            "therapeuticRecommendationAllowed": False,
            "readyForAppConsultant": False,
        },
        "candidates": candidates,
        "manualCurationRequired": [
            "Asignar syndrome y subsyndrome a cada candidato útil.",
            "Extraer solo opciones explícitas respaldadas por el texto fuente.",
            "Descartar menciones no relacionadas con opciones para alérgicos.",
            "No convertir candidatos en recomendaciones ni rankings.",
        ],
    }
    summary = build_summary(candidates)
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH} with {len(candidates)} candidates")
    print(f"Wrote {SUMMARY_PATH} with {len(summary['topics'])} topic summaries")


if __name__ == "__main__":
    main()
