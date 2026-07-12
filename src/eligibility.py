from typing import Optional


def normalize_sex(value: Optional[str]) -> Optional[str]:
    """
    Converts possible patient values into the ClinicalTrials format.
    """
    if not value:
        return None

    value = value.upper().strip()

    mapping = {
        "MALE": "MALE",
        "MAN": "MALE",
        "M": "MALE",
        "FEMALE": "FEMALE",
        "WOMAN": "FEMALE",
        "F": "FEMALE",
    }

    return mapping.get(value)


def passes_hard_filters(
    patient: dict,
    trial: dict,
    country: Optional[str],
) -> tuple[bool, list[str]]:
    """
    Checks objective criteria before using an LLM:
    - trial is recruiting
    - trial is interventional
    - patient age fits
    - patient sex fits
    - trial has a recruiting site in the requested country
    """

    reasons = []

    # 1. Global trial status
    if trial.get("status") != "RECRUITING":
        reasons.append("Trial is not globally recruiting.")

    # 2. Study type
    if trial.get("study_type") != "INTERVENTIONAL":
        reasons.append("Trial is not an interventional study.")

    # 3. Age
    patient_age = patient.get("age")
    min_age = trial.get("min_age")
    max_age = trial.get("max_age")

    if patient_age is not None:
        if min_age is not None and patient_age < min_age:
            reasons.append(f"Patient is younger than the minimum age ({min_age}).")

        if max_age is not None and patient_age > max_age:
            reasons.append(f"Patient is older than the maximum age ({max_age}).")

    # 4. Sex
    patient_sex = normalize_sex(patient.get("sex"))
    trial_sex = trial.get("sex")

    if (
        patient_sex is not None
        and trial_sex not in (None, "ALL")
        and patient_sex != trial_sex
    ):
        reasons.append(f"Trial is restricted to {trial_sex.lower()} participants.")

    # 5. Recruiting location in requested country, when supplied
    if country:
        recruiting_locations_in_country = [
            location
            for location in trial.get("locations", [])
            if location.get("country", "").casefold() == country.casefold()
        ]

        if not recruiting_locations_in_country:
            reasons.append(f"No recruiting location found in {country}.")

    return len(reasons) == 0, reasons
