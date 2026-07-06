from src.clinicaltrials_client import search_trials
from src.profile_extractor import extract_patient_profile
from src.trial_cleaner import clean_trial, get_recruiting_locations_in_country
from src.eligibility import passes_hard_filters
from src.semantic_matcher import assess_trial_match


REQUIRED_FIELDS = [
    "age",
    "sex",
    "condition",
    "country",
    "disease_stage",
]


def get_missing_required_fields(profile: dict) -> list[str]:
    """
    Returns the important profile fields that are still missing.
    """
    missing = []

    for field in REQUIRED_FIELDS:
        value = profile.get(field)

        if value is None or value == "":
            missing.append(field)

    return missing


def build_clarifying_question(missing_fields: list[str]) -> str:
    """
    Asks one simple question at a time.
    """
    questions = {
        "age": "What is your age?",
        "sex": "What sex were you assigned at birth?",
        "condition": "What condition or diagnosis are you looking for a trial for?",
        "country": "Which country can you travel within?",
        "disease_stage": (
            "What stage is your cancer? For example, stage 1, 2, 3, "
            "or stage 4/metastatic. If you do not know, please say so."
        ),
    }

    return questions[missing_fields[0]]


def is_supportive_or_non_treatment_trial(trial: dict) -> bool:
    """
    Removes trials that are technically relevant to cancer patients,
    but are not mainly about cancer treatment options.
    """
    title = (trial.get("title") or "").lower()
    summary = (trial.get("brief_summary") or "").lower()

    supportive_keywords = [
        "acupuncture",
        "nausea",
        "quality of life",
        "decision making",
        "supportive care",
        "brown fat",
        "metabolic rate",
    ]

    return any(
        keyword in title or keyword in summary for keyword in supportive_keywords
    )


def run_agent(user_message: str) -> dict:
    """
    Main agent flow.

    1. Extract patient profile from free text.
    2. Ask for missing information when needed.
    3. Search recruiting trials.
    4. Apply deterministic hard filters.
    5. Remove non-treatment/supportive trials.
    6. Use the LLM to evaluate soft medical criteria.
    7. Return a ranked shortlist.
    """

    patient = extract_patient_profile(user_message)

    missing_fields = get_missing_required_fields(patient)

    if missing_fields:
        return {
            "action": "ask_question",
            "patient_profile": patient,
            "question": build_clarifying_question(missing_fields),
        }

    studies = search_trials(
        condition=patient["condition"],
        country=patient["country"],
        page_size=20,
    )

    candidate_trials = []

    for study in studies:
        trial = clean_trial(study)

        passed, _ = passes_hard_filters(
            patient=patient,
            trial=trial,
            country=patient["country"],
        )

        if not passed:
            continue

        # Keep only treatment/intervention studies.
        if trial.get("study_type") != "INTERVENTIONAL":
            continue

        # Remove supportive-care or unrelated intervention studies.
        if is_supportive_or_non_treatment_trial(trial):
            continue

        candidate_trials.append(trial)

    # We only deeply assess a small shortlist with the LLM.
    candidate_trials = candidate_trials[:6]

    results = []

    for trial in candidate_trials:
        semantic_result = assess_trial_match(patient, trial)

        local_locations = get_recruiting_locations_in_country(
            trial,
            patient["country"],
        )

        nearest_location = local_locations[0] if local_locations else None

        results.append(
            {
                "nct_id": trial["nct_id"],
                "title": trial["title"],
                "status": trial["status"],
                "phase": trial["phase"],
                "location": nearest_location,
                "label": semantic_result["label"],
                "reason": semantic_result["reason"],
                "missing_information": semantic_result["missing_information"],
                "trial_url": trial["trial_url"],
            }
        )

    label_order = {
        "likely_eligible": 0,
        "possibly_eligible": 1,
        "likely_not_eligible": 2,
    }

    results.sort(key=lambda result: label_order.get(result["label"], 3))

    return {
        "action": "show_results",
        "patient_profile": patient,
        "reply": (
            "I found these possible candidate matches:"
            if results
            else (
                "I could not find candidate trials that match the basic "
                "age, sex, recruitment, and location filters."
            )
        ),
        "results": results,
        "disclaimer": (
            "These are possible candidate matches only, not medical advice or "
            "a definitive eligibility decision. Please discuss them with your "
            "doctor and the clinical trial team."
        ),
    }
