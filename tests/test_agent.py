from src import agent


def test_run_agent_asks_for_missing_required_information(monkeypatch) -> None:
    monkeypatch.setattr(
        agent,
        "extract_patient_profile",
        lambda _: {
            "age": None,
            "sex": "female",
            "condition": "breast cancer",
            "country": "Denmark",
            "disease_stage": "stage 2",
        },
    )

    result = agent.run_agent("I have breast cancer.")

    assert result["action"] == "ask_question"
    assert result["question"] == "What is your age?"


def test_run_agent_returns_ranked_candidate_results(monkeypatch) -> None:
    patient = {
        "age": 60,
        "sex": "female",
        "condition": "breast cancer",
        "country": "Denmark",
        "disease_stage": "stage 2",
    }

    trial = {
        "nct_id": "NCT123",
        "title": "Breast Cancer Treatment Study",
        "status": "RECRUITING",
        "phase": ["PHASE2"],
        "study_type": "INTERVENTIONAL",
        "brief_summary": "Testing a treatment option.",
        "locations": [
            {
                "facility": "Rigshospitalet",
                "city": "Copenhagen",
                "country": "Denmark",
                "status": "RECRUITING",
            }
        ],
        "trial_url": "https://clinicaltrials.gov/study/NCT123",
    }

    monkeypatch.setattr(agent, "extract_patient_profile", lambda _: patient)
    monkeypatch.setattr(agent, "search_trials", lambda **_: [{"raw": "study"}])
    monkeypatch.setattr(agent, "clean_trial", lambda _: trial)
    monkeypatch.setattr(agent, "passes_hard_filters", lambda **_: (True, []))
    monkeypatch.setattr(
        agent,
        "assess_trial_match",
        lambda *_: {
            "label": "possibly_eligible",
            "reason": "Matches the basic profile, but criteria need confirmation.",
            "missing_information": ["biomarker status"],
        },
    )

    result = agent.run_agent("complete profile")

    assert result["action"] == "show_results"
    assert result["reply"] == "I found these possible candidate matches:"
    assert result["results"][0]["nct_id"] == "NCT123"
    assert result["results"][0]["label"] == "possibly_eligible"
    assert result["results"][0]["location"]["city"] == "Copenhagen"
