from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DOCS_DIR = Path("docs")
CONSULTANT_PATH = DOCS_DIR / "rules" / "betalactam_allergy_consultant.json"
ALLERGY_RULES_PATH = DOCS_DIR / "rules" / "allergy_rules.json"
REQUIRED_ENTRY_OPTION_IDS = {
    "no",
    "penicillin_non_severe",
    "immediate_severe",
    "severe_cutaneous",
    "unknown",
}
REPORTED_ALLERGY_BUCKETS = {
    "reported_non_severe_history",
    "high_risk_immediate_reaction",
    "very_high_risk_severe_cutaneous_reaction",
    "uncertain_history",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"ERROR: {message}")


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"ERROR: invalid JSON in {path}: {exc}") from exc

    require(isinstance(data, dict), f"{path} must contain a JSON object")
    return data


def validate_metadata(data: dict[str, Any]) -> None:
    metadata = data.get("metadata") or {}
    require(metadata.get("status") == "draft_structure_only", "consultant metadata.status must be draft_structure_only")
    require(metadata.get("source") == "allergy_rules.json", "consultant metadata.source must be allergy_rules.json")
    require(metadata.get("clinicalUseAllowed") is False, "consultant must block clinicalUseAllowed")
    require(metadata.get("clinicalDecisionSupportAllowed") is False, "consultant must block clinicalDecisionSupportAllowed")
    require(metadata.get("therapeuticRecommendationAllowed") is False, "consultant must block therapeuticRecommendationAllowed")
    require(metadata.get("alternativeAntibioticRecommendationAllowed") is False, "consultant must block alternativeAntibioticRecommendationAllowed")
    require(metadata.get("manualReviewStatus") == "pending", "consultant manualReviewStatus must remain pending")


def validate_entry_question(data: dict[str, Any], allergy_rules: dict[str, Any]) -> None:
    question = data.get("entryQuestion") or {}
    allergy_question = allergy_rules.get("allergyQuestion") or {}

    require(question.get("id") == "betalactam_allergy", "entryQuestion.id must be betalactam_allergy")
    require(question.get("type") == "single_select", "entryQuestion.type must be single_select")
    require(question.get("required") is True, "entryQuestion.required must be true")
    require(allergy_question.get("id") == question.get("id"), "entryQuestion must reuse allergy_rules allergyQuestion id")

    options = question.get("options") or []
    require(isinstance(options, list) and options, "entryQuestion.options must be a non-empty list")
    option_ids = {option.get("id") for option in options if isinstance(option, dict)}
    require(option_ids == REQUIRED_ENTRY_OPTION_IDS, f"entryQuestion.options mismatch: {sorted(option_ids)}")

    source_option_ids = {option.get("id") for option in allergy_question.get("options") or [] if isinstance(option, dict)}
    require(option_ids == source_option_ids, "consultant entry options must match allergy_rules options by id")

    for option in options:
        require(isinstance(option, dict), "each entry option must be an object")
        prefix = f"entryQuestion.options[{option.get('id')}]"
        require(option.get("label"), f"{prefix} lacks label")
        require(option.get("riskBucket"), f"{prefix} lacks riskBucket")
        require(option.get("nextStep"), f"{prefix} lacks nextStep")
        require(isinstance(option.get("mayContinueStandardGuide"), bool), f"{prefix}.mayContinueStandardGuide must be boolean")


def validate_follow_up_questions(data: dict[str, Any]) -> None:
    questions = data.get("followUpQuestions") or []
    require(isinstance(questions, list) and questions, "followUpQuestions must be a non-empty list")

    question_ids = {question.get("id") for question in questions if isinstance(question, dict)}
    required_ids = {"culpritDrug", "reactionType", "reactionTiming", "reactionDate", "subsequentTolerance"}
    require(required_ids.issubset(question_ids), "followUpQuestions missing required allergy documentation fields")

    for question in questions:
        require(isinstance(question, dict), "each follow-up question must be an object")
        prefix = f"followUpQuestions[{question.get('id')}]"
        require(question.get("label"), f"{prefix} lacks label")
        require(question.get("type") in {"free_text", "single_select", "multi_select"}, f"{prefix}.type is invalid")
        required_for = question.get("requiredForBuckets") or []
        require(set(required_for) == REPORTED_ALLERGY_BUCKETS, f"{prefix}.requiredForBuckets must cover all reported allergy buckets")


def validate_result_messages(data: dict[str, Any]) -> None:
    messages = data.get("resultMessages") or {}
    require(isinstance(messages, dict) and messages, "resultMessages must be a non-empty object")

    entry_buckets = {option.get("riskBucket") for option in data.get("entryQuestion", {}).get("options") or [] if isinstance(option, dict)}
    require(set(messages.keys()) == entry_buckets, "resultMessages must cover every riskBucket exactly")

    for bucket, message in messages.items():
        require(isinstance(message, dict), f"resultMessages[{bucket}] must be an object")
        require(message.get("severity") in {"info", "caution", "high_risk", "very_high_risk"}, f"resultMessages[{bucket}].severity is invalid")
        require(message.get("title"), f"resultMessages[{bucket}] lacks title")
        require(message.get("message"), f"resultMessages[{bucket}] lacks message")


def validate_safety(data: dict[str, Any]) -> None:
    hard_safety = data.get("hardSafetyRules") or {}
    app_behavior = data.get("appBehavior") or {}

    require(hard_safety.get("mustNotRecommendAlternativeAntibiotics") is True, "consultant must block alternative antibiotic recommendation")
    require(hard_safety.get("mustNotOverrideDocumentedSevereAllergy") is True, "consultant must not override severe allergy")
    require(hard_safety.get("mustNotInferToleranceWithoutDocumentation") is True, "consultant must not infer tolerance")
    require(hard_safety.get("mustAlwaysAskReactionTypeForReportedAllergy") is True, "consultant must ask reaction type")
    require(hard_safety.get("mustAlwaysShowClinicalUseBlockedBanner") is True, "consultant must show clinical-use blocked banner")
    require(hard_safety.get("mustAdviseExpertReviewForSevereOrUnclearHistory") is True, "consultant must advise expert review")

    require(app_behavior.get("mayRenderAsQuestionnaire") is True, "app may render questionnaire")
    require(app_behavior.get("mayStoreAnswersLocally") is False, "app must not store answers locally")
    require(app_behavior.get("mayUseAnswersToFilterTherapeuticRules") is False, "app must not filter therapeutic rules")
    require(app_behavior.get("mayUseAnswersToGenerateWarnings") is True, "app may generate warnings")
    require(app_behavior.get("mayUseAnswersToGenerateAntibioticAlternatives") is False, "app must not generate alternatives")


def main() -> None:
    require(CONSULTANT_PATH.exists(), f"missing {CONSULTANT_PATH}")
    require(ALLERGY_RULES_PATH.exists(), f"missing {ALLERGY_RULES_PATH}")

    consultant = load_json(CONSULTANT_PATH)
    allergy_rules = load_json(ALLERGY_RULES_PATH)

    validate_metadata(consultant)
    validate_entry_question(consultant, allergy_rules)
    validate_follow_up_questions(consultant)
    validate_result_messages(consultant)
    validate_safety(consultant)

    print("Beta-lactam allergy consultant OK")


if __name__ == "__main__":
    main()
