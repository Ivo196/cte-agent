import json

from src.llm import ask_json


def assess_trial_match(patient: dict, trial: dict) -> dict:
    """
    Compares a patient profile with a trial using the LLM.

    Python has already filtered age, sex, and location.
    This function analyzes harder criteria:
    stage, metastatic disease, HER2, prior treatments, and similar details.
    """

    patient_text = json.dumps(patient, indent=2)

    trial_text = json.dumps(
        {
            "nct_id": trial["nct_id"],
            "title": trial["title"],
            "conditions": trial["conditions"],
            "study_type": trial["study_type"],
            "brief_summary": trial["brief_summary"],
            "minimum_age": trial.get("min_age"),
            "maximum_age": trial.get("max_age"),
            "sex": trial.get("sex"),
            "healthy_volunteers": trial.get("healthy_volunteers"),
            "inclusion_criteria": trial.get("inclusion_criteria", []),
            "exclusion_criteria": trial.get("exclusion_criteria", []),
            "other_criteria": trial.get("other_criteria", []),
        },
        indent=2,
    )

    prompt = f"""
You are helping identify possible clinical trial candidate matches.

Important rules:
- Do not give medical advice.
- Do not say the patient is definitely eligible.
- The final decision belongs to the clinical trial team and treating clinician.
- Be honest when information is missing.
- Use only the information provided.
- Python has already checked recruitment status, study type, age, sex, and
  recruiting country. Focus on disease stage, subtype, prior treatments,
  treatment timing, biomarkers, unclear exclusions, and uncertainty.

Patient profile:
{patient_text}

Clinical trial:
{trial_text}

Classify this trial as exactly one of:
- likely_eligible
- possibly_eligible
- likely_not_eligible

Return valid JSON only with this exact structure:

{{
  "label": "likely_eligible",
  "reason": "One short plain-language sentence.",
  "missing_information": []
}}
"""

    result = ask_json(prompt)
    valid_labels = {
        "likely_eligible",
        "possibly_eligible",
        "likely_not_eligible",
    }
    if not isinstance(result, dict) or result.get("label") not in valid_labels:
        return {
            "label": "possibly_eligible",
            "reason": "The soft eligibility criteria could not be assessed reliably.",
            "missing_information": ["Clinical review of the eligibility criteria"],
        }

    reason = result.get("reason")
    missing_information = result.get("missing_information")
    if not isinstance(reason, str) or not reason.strip():
        reason = "The available information is not enough for a confident match."
    if not isinstance(missing_information, list):
        missing_information = []

    return {
        "label": result["label"],
        "reason": reason.strip(),
        "missing_information": missing_information,
    }
