import json
import os

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()


def get_client() -> OpenAI:
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


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
            "inclusion_criteria": trial.get("inclusion_criteria", []),
            "exclusion_criteria": trial.get("exclusion_criteria", []),
            "other_criteria": trial.get("other_criteria", []),
            "raw_eligibility_criteria": trial["eligibility_criteria"],
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

    response = get_client().responses.create(
        model="gpt-5-mini",
        input=prompt,
    )

    return json.loads(response.output_text)
