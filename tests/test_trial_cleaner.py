from src.trial_cleaner import clean_trial, parse_age, split_criteria


def test_parse_age_reads_clinicaltrials_age_text() -> None:
    assert parse_age("18 Years") == 18
    assert parse_age("65 Years") == 65
    assert parse_age("N/A") is None
    assert parse_age(None) is None


def test_split_criteria_separates_inclusion_and_exclusion() -> None:
    text = """
    Inclusion Criteria:
    - Female participants
    - Stage II breast cancer

    Exclusion Criteria:
    - Prior treatment with investigational drug
    - Severe heart disease
    """

    criteria = split_criteria(text)

    assert criteria["inclusion"] == [
        "Female participants",
        "Stage II breast cancer",
    ]
    assert criteria["exclusion"] == [
        "Prior treatment with investigational drug",
        "Severe heart disease",
    ]


def test_split_criteria_accepts_key_criteria_headings() -> None:
    text = """
    Key inclusion criteria for both phases:
    1. Adult females and adult males.

    Key exclusion criteria for both phases:
    1. History of another primary malignancy.
    """

    criteria = split_criteria(text)

    assert criteria["inclusion"] == ["Adult females and adult males."]
    assert criteria["exclusion"] == ["History of another primary malignancy."]


def test_clean_trial_keeps_only_useful_fields() -> None:
    study = {
        "protocolSection": {
            "identificationModule": {
                "nctId": "NCT123",
                "briefTitle": "Breast Cancer Study",
            },
            "statusModule": {"overallStatus": "RECRUITING"},
            "designModule": {
                "phases": ["PHASE2"],
                "studyType": "INTERVENTIONAL",
            },
            "conditionsModule": {"conditions": ["Breast Cancer"]},
            "descriptionModule": {"briefSummary": "A short summary."},
            "eligibilityModule": {
                "minimumAge": "18 Years",
                "maximumAge": "80 Years",
                "sex": "FEMALE",
                "healthyVolunteers": False,
                "eligibilityCriteria": """
                Inclusion Criteria:
                - Breast cancer
                Exclusion Criteria:
                - Active infection
                """,
            },
            "contactsLocationsModule": {
                "locations": [
                    {
                        "facility": "Rigshospitalet",
                        "city": "Copenhagen",
                        "country": "Denmark",
                        "status": "RECRUITING",
                    },
                    {
                        "facility": "Closed Site",
                        "city": "Aarhus",
                        "country": "Denmark",
                        "status": "COMPLETED",
                    },
                ]
            },
        }
    }

    trial = clean_trial(study)

    assert trial["nct_id"] == "NCT123"
    assert trial["min_age"] == 18
    assert trial["max_age"] == 80
    assert trial["locations"] == [
        {
            "facility": "Rigshospitalet",
            "city": "Copenhagen",
            "country": "Denmark",
            "status": "RECRUITING",
        }
    ]
    assert trial["inclusion_criteria"] == ["Breast cancer"]
    assert trial["exclusion_criteria"] == ["Active infection"]
