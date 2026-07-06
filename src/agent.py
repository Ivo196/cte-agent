from src.clinicaltrials_client import get_trial_details, search_trials
from src.eligibility import passes_hard_filters
from src.profile_extractor import extract_patient_profile
from src.semantic_matcher import assess_trial_match
from src.trial_cleaner import clean_trial, get_recruiting_locations_in_country


MAX_SEARCH_RESULTS = 20
MAX_DETAILED_TRIALS = 6

REQUIRED_FIELDS = [
    "age",
    "sex",
    "condition",
    "country",
    "disease_stage",
]

CLARIFYING_QUESTIONS = {
    "age": "What is your age?",
    "sex": "What sex were you assigned at birth?",
    "condition": "What condition or diagnosis are you looking for a trial for?",
    "country": "Which country can you travel within?",
    "disease_stage": (
        "What stage is your cancer? For example, stage 1, 2, 3, "
        "or stage 4/metastatic. If you do not know, please say so."
    ),
}

LABEL_ORDER = {
    "likely_eligible": 0,
    "possibly_eligible": 1,
    "likely_not_eligible": 2,
}

SUPPORTIVE_TRIAL_KEYWORDS = [
    "acupuncture",
    "nausea",
    "quality of life",
    "decision making",
    "supportive care",
    "brown fat",
    "metabolic rate",
]

SAFETY_DISCLAIMER = (
    "These are possible candidate matches only, not medical advice or "
    "a definitive eligibility decision. Please discuss them with your "
    "doctor and the clinical trial team."
)


def get_missing_required_fields(profile: dict) -> list[str]:
    return [
        field
        for field in REQUIRED_FIELDS
        if profile.get(field) is None or profile.get(field) == ""
    ]


def build_clarifying_question(missing_fields: list[str]) -> str:
    return CLARIFYING_QUESTIONS[missing_fields[0]]


def is_supportive_or_non_treatment_trial(trial: dict) -> bool:
    title = (trial.get("title") or "").lower()
    summary = (trial.get("brief_summary") or "").lower()

    return any(
        keyword in title or keyword in summary
        for keyword in SUPPORTIVE_TRIAL_KEYWORDS
    )


def _passes_initial_filters(patient: dict, trial: dict) -> bool:
    passed, _ = passes_hard_filters(
        patient=patient,
        trial=trial,
        country=patient["country"],
    )

    if not passed:
        return False

    if trial.get("study_type") != "INTERVENTIONAL":
        return False

    return not is_supportive_or_non_treatment_trial(trial)


def _search_shallow_candidates(patient: dict) -> list[dict]:
    studies = search_trials(
        condition=patient["condition"],
        country=patient["country"],
        page_size=MAX_SEARCH_RESULTS,
    )

    candidates = []

    for study in studies:
        trial = clean_trial(study)

        if _passes_initial_filters(patient, trial):
            candidates.append(trial)

    return candidates


def _fetch_detailed_trials(shallow_trials: list[dict]) -> list[dict]:
    detailed_trials = []

    for trial in shallow_trials[:MAX_DETAILED_TRIALS]:
        full_study = get_trial_details(trial["nct_id"])
        detailed_trials.append(clean_trial(full_study))

    return detailed_trials


def _build_trial_result(patient: dict, trial: dict) -> dict:
    semantic_result = assess_trial_match(patient, trial)
    local_locations = get_recruiting_locations_in_country(
        trial,
        patient["country"],
    )

    return {
        "nct_id": trial["nct_id"],
        "title": trial["title"],
        "status": trial["status"],
        "phase": trial["phase"],
        "location": local_locations[0] if local_locations else None,
        "label": semantic_result["label"],
        "reason": semantic_result["reason"],
        "missing_information": semantic_result["missing_information"],
        "trial_url": trial["trial_url"],
    }


def _sort_results(results: list[dict]) -> list[dict]:
    return sorted(
        results,
        key=lambda result: LABEL_ORDER.get(result["label"], 3),
    )


def _results_reply(results: list[dict]) -> str:
    if results:
        return "I found these possible candidate matches:"

    return (
        "I could not find candidate trials that match the basic "
        "age, sex, recruitment, and location filters."
    )


def run_agent(user_message: str) -> dict:
    """
    Runs one agent turn: extract profile, ask if needed, search, inspect, rank.
    """
    patient = extract_patient_profile(user_message)
    missing_fields = get_missing_required_fields(patient)

    if missing_fields:
        return {
            "action": "ask_question",
            "patient_profile": patient,
            "question": build_clarifying_question(missing_fields),
        }

    shallow_candidates = _search_shallow_candidates(patient)
    detailed_trials = _fetch_detailed_trials(shallow_candidates)
    results = _sort_results(
        [_build_trial_result(patient, trial) for trial in detailed_trials]
    )

    return {
        "action": "show_results",
        "patient_profile": patient,
        "reply": _results_reply(results),
        "results": results,
        "disclaimer": SAFETY_DISCLAIMER,
    }
