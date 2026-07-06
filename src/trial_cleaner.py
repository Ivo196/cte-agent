import re


SECTION_HEADINGS = {
    "inclusion": re.compile(r"^\s*(key\s+)?inclusion criteria\s*:?\s*$", re.I),
    "exclusion": re.compile(r"^\s*(key\s+)?exclusion criteria\s*:?\s*$", re.I),
}


def parse_age(age_text: str | None) -> int | None:
    """
    Convierte textos como '18 Years' en 18.
    Si no hay edad o no se puede leer, devuelve None.
    """
    if not age_text:
        return None

    match = re.search(r"\d+", age_text)

    if not match:
        return None

    return int(match.group())


def _clean_criterion_line(line: str) -> str:
    """
    Removes common bullets and extra whitespace from one criterion line.
    """
    line = line.strip()
    line = re.sub(r"^[-*•\u2022]\s*", "", line)
    line = re.sub(r"^\d+[\.)]\s*", "", line)
    return re.sub(r"\s+", " ", line).strip()


def split_criteria(eligibility_text: str | None) -> dict[str, list[str]]:
    """
    Splits a ClinicalTrials.gov eligibility blob into inclusion and exclusion lists.

    The source text is messy, so this intentionally uses conservative section
    headings instead of trying to infer medical meaning from every sentence.
    """
    criteria = {
        "inclusion": [],
        "exclusion": [],
        "other": [],
    }

    if not eligibility_text:
        return criteria

    current_section = "other"

    for raw_line in eligibility_text.splitlines():
        line = raw_line.strip()

        if not line:
            continue

        if SECTION_HEADINGS["inclusion"].match(line):
            current_section = "inclusion"
            continue

        if SECTION_HEADINGS["exclusion"].match(line):
            current_section = "exclusion"
            continue

        cleaned_line = _clean_criterion_line(line)

        if cleaned_line:
            criteria[current_section].append(cleaned_line)

    return criteria


def clean_trial(study: dict) -> dict:
    """
    Convierte el JSON grande de ClinicalTrials.gov
    en un diccionario pequeño y útil para nuestro agente.
    """

    protocol = study.get("protocolSection", {})

    identification = protocol.get("identificationModule", {})
    status_module = protocol.get("statusModule", {})
    design_module = protocol.get("designModule", {})
    eligibility_module = protocol.get("eligibilityModule", {})
    locations_module = protocol.get("contactsLocationsModule", {})
    conditions_module = protocol.get("conditionsModule", {})
    description_module = protocol.get("descriptionModule", {})

    recruiting_locations = []

    for location in locations_module.get("locations", []):
        if location.get("status") == "RECRUITING":
            recruiting_locations.append(
                {
                    "facility": location.get("facility"),
                    "city": location.get("city"),
                    "country": location.get("country"),
                    "status": location.get("status"),
                }
            )

    nct_id = identification.get("nctId")
    eligibility_criteria = eligibility_module.get("eligibilityCriteria")
    structured_criteria = split_criteria(eligibility_criteria)

    return {
        "nct_id": nct_id,
        "title": identification.get("briefTitle"),
        "status": status_module.get("overallStatus"),
        "phase": design_module.get("phases", []),
        "study_type": design_module.get("studyType"),
        "conditions": conditions_module.get("conditions", []),
        "brief_summary": description_module.get("briefSummary"),
        "min_age": parse_age(eligibility_module.get("minimumAge")),
        "max_age": parse_age(eligibility_module.get("maximumAge")),
        "sex": eligibility_module.get("sex"),
        "healthy_volunteers": eligibility_module.get("healthyVolunteers"),
        "eligibility_criteria": eligibility_criteria,
        "inclusion_criteria": structured_criteria["inclusion"],
        "exclusion_criteria": structured_criteria["exclusion"],
        "other_criteria": structured_criteria["other"],
        "locations": recruiting_locations,
        "trial_url": f"https://clinicaltrials.gov/study/{nct_id}",
    }


def get_recruiting_locations_in_country(
    trial: dict,
    country: str,
) -> list[dict]:
    """
    Devuelve solo sedes recruiting del país pedido.
    """
    return [
        location
        for location in trial["locations"]
        if location.get("country", "").lower() == country.lower()
    ]
