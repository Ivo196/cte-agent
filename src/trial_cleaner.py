import re
from typing import Optional


SECTION_HEADINGS = {
    "inclusion": re.compile(r"^\s*(key\s+)?inclusion criteria\b.*:?\s*$", re.I),
    "exclusion": re.compile(r"^\s*(key\s+)?exclusion criteria\b.*:?\s*$", re.I),
}


def parse_age(age_text: Optional[str]) -> Optional[int]:
    """
    Converts text like '18 Years' into 18.
    Returns None when the value is missing or cannot be parsed.
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
    line = re.sub(r"^[-*\u2022]\s*", "", line)
    line = re.sub(r"^\d+[\.)]\s*", "", line)
    return re.sub(r"\s+", " ", line).strip()


def split_criteria(eligibility_text: Optional[str]) -> dict[str, list[str]]:
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
    Converts a large ClinicalTrials.gov JSON record into a small dictionary
    with only the fields the agent needs.
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
        "inclusion_criteria": structured_criteria["inclusion"],
        "exclusion_criteria": structured_criteria["exclusion"],
        "other_criteria": structured_criteria["other"],
        "locations": recruiting_locations,
        "trial_url": f"https://clinicaltrials.gov/study/{nct_id}",
    }


def build_candidate_summary(trial: dict) -> dict:
    """Build a small planner-safe view without raw API or eligibility records."""
    locations = [
        {
            "city": location.get("city"),
            "country": location.get("country"),
        }
        for location in trial.get("locations", [])[:8]
    ]
    brief_summary = trial.get("brief_summary") or ""

    return {
        "nct_id": trial.get("nct_id"),
        "title": trial.get("title"),
        "phase": trial.get("phase", []),
        "study_type": trial.get("study_type"),
        "conditions": trial.get("conditions", []),
        "age_range": {
            "minimum": trial.get("min_age"),
            "maximum": trial.get("max_age"),
        },
        "sex": trial.get("sex"),
        "locations": locations,
        "brief_summary": brief_summary[:500],
    }


def select_nearest_recruiting_location(
    trial: dict,
    patient: dict,
) -> Optional[dict]:
    """Prefer the patient's city, otherwise the first site in their country."""
    locations = trial.get("locations", [])
    country = patient.get("country")
    city = patient.get("city")

    country_locations = locations
    if country:
        country_locations = [
            location
            for location in locations
            if location.get("country", "").casefold() == country.casefold()
        ]

    if city:
        for location in country_locations:
            if location.get("city", "").casefold() == city.casefold():
                return location

    return country_locations[0] if country_locations else None
