from src.eligibility import normalize_sex, passes_hard_filters


def valid_trial() -> dict:
    return {
        "status": "RECRUITING",
        "study_type": "INTERVENTIONAL",
        "min_age": 18,
        "max_age": 80,
        "sex": "ALL",
        "locations": [{"country": "Denmark"}],
    }


def test_normalize_sex_handles_common_patient_values() -> None:
    assert normalize_sex("woman") == "FEMALE"
    assert normalize_sex("M") == "MALE"
    assert normalize_sex(None) is None


def test_hard_filters_cover_status_type_age_sex_and_country() -> None:
    patient = {"age": 60, "sex": "female"}
    trial = valid_trial()
    trial.update(
        {
            "status": "COMPLETED",
            "study_type": "OBSERVATIONAL",
            "min_age": 65,
            "sex": "MALE",
            "locations": [{"country": "Sweden"}],
        }
    )

    passed, reasons = passes_hard_filters(patient, trial, "Denmark")

    assert passed is False
    assert len(reasons) == 5


def test_hard_filters_accept_matching_interventional_trial() -> None:
    passed, reasons = passes_hard_filters(
        {"age": 60, "sex": "female"},
        valid_trial(),
        "Denmark",
    )

    assert passed is True
    assert reasons == []
