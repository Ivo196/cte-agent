from src import semantic_matcher


def test_semantic_matcher_receives_structured_criteria_not_raw_blob(monkeypatch) -> None:
    captured = {}

    def fake_ask_json(prompt: str) -> dict:
        captured["prompt"] = prompt
        return {
            "label": "possibly_eligible",
            "reason": "Prior treatment timing needs confirmation.",
            "missing_information": ["treatment date"],
        }

    monkeypatch.setattr(semantic_matcher, "ask_json", fake_ask_json)
    trial = {
        "nct_id": "NCT123",
        "title": "Study",
        "conditions": ["Breast Cancer"],
        "study_type": "INTERVENTIONAL",
        "brief_summary": "Summary",
        "min_age": 18,
        "max_age": 80,
        "sex": "ALL",
        "healthy_volunteers": False,
        "inclusion_criteria": ["Stage II breast cancer"],
        "exclusion_criteria": ["Treatment within 14 days"],
        "other_criteria": [],
    }

    result = semantic_matcher.assess_trial_match(
        {"disease_stage": "stage 2", "prior_treatments": ["chemotherapy"]},
        trial,
    )

    assert result["label"] == "possibly_eligible"
    assert "Stage II breast cancer" in captured["prompt"]
    assert "raw_eligibility_criteria" not in captured["prompt"]
