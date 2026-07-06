from src.llm import ask_json


def extract_patient_profile(user_message: str) -> dict:
    """
    Converts a patient's free-text description into structured information.
    Missing information must be returned as null or an empty list.
    """

    prompt = f"""
Extract a structured patient profile from this message.

Patient message:
{user_message}

Return valid JSON only with exactly these fields:

{{
  "age": null,
  "sex": null,
  "condition": null,
  "disease_stage": null,
  "prior_treatments": [],
  "biomarkers": [],
  "country": null,
  "city": null,
  "travel_preference": null
}}

Rules:
- Do not invent information.
- Use null when a single value is unknown.
- Use [] when a list is unknown.
- Normalize country names in English, for example "Denmark".
- Normalize sex to "male" or "female" when known.
- Keep treatments concise, for example "chemotherapy", "tamoxifen".
"""

    return ask_json(prompt)
