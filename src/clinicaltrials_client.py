from typing import Optional

import requests

BASE_URL = "https://clinicaltrials.gov/api/v2/studies"

TRIAL_FIELDS = [
    "NCTId",
    "BriefTitle",
    "OverallStatus",
    "Phase",
    "StudyType",
    "Condition",
    "BriefSummary",
    "MinimumAge",
    "MaximumAge",
    "Sex",
    "HealthyVolunteers",
    "EligibilityCriteria",
    "LocationFacility",
    "LocationCity",
    "LocationCountry",
    "LocationStatus",
]


def search_trials(
    condition: str,
    country: Optional[str] = None,
    page_size: int = 20,
) -> list[dict]:
    """
    Searches for recruiting clinical trials matching a condition.
    Optionally filters by country.
    """

    page_size = max(1, min(page_size, 100))

    params = {
        "query.cond": condition,
        "filter.overallStatus": "RECRUITING",
        "pageSize": page_size,
        "fields": ",".join(TRIAL_FIELDS),
    }

    if country:
        params["filter.advanced"] = f'AREA[LocationCountry]"{country}"'

    response = requests.get(BASE_URL, params=params, timeout=20)
    response.raise_for_status()

    return response.json().get("studies", [])


def get_trial_details(nct_id: str) -> dict:
    """
    Fetches one full trial record using its NCT identifier.
    Example: NCT05921279
    """

    response = requests.get(f"{BASE_URL}/{nct_id}", timeout=20)
    response.raise_for_status()

    return response.json()
