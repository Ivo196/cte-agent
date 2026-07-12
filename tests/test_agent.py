from src import agent


def patient_profile(**overrides) -> dict:
    profile = {
        "age": 60,
        "sex": "female",
        "condition": "breast cancer",
        "country": "Denmark",
        "city": "Copenhagen",
        "disease_stage": "stage 2",
        "prior_treatments": ["chemotherapy"],
        "biomarkers": [],
    }
    profile.update(overrides)
    return profile


def candidate_trial(nct_id: str, **overrides) -> dict:
    trial = {
        "nct_id": nct_id,
        "title": f"Trial {nct_id}",
        "status": "RECRUITING",
        "phase": ["PHASE2"],
        "study_type": "INTERVENTIONAL",
        "conditions": ["Breast Cancer"],
        "brief_summary": "Testing a treatment option.",
        "min_age": 18,
        "max_age": 80,
        "sex": "ALL",
        "healthy_volunteers": False,
        "inclusion_criteria": ["Stage II breast cancer"],
        "exclusion_criteria": [],
        "other_criteria": [],
        "locations": [
            {
                "facility": "Rigshospitalet",
                "city": "Copenhagen",
                "country": "Denmark",
                "status": "RECRUITING",
            }
        ],
        "trial_url": f"https://clinicaltrials.gov/study/{nct_id}",
    }
    trial.update(overrides)
    return trial


def decision_sequence(*decisions):
    iterator = iter(decisions)

    def decide(_planner_view: dict) -> dict:
        return next(iterator)

    return decide


def configure_profile(monkeypatch, **overrides) -> None:
    monkeypatch.setattr(
        agent,
        "extract_patient_profile",
        lambda _: patient_profile(**overrides),
    )


def test_planner_asks_a_clarification_question(monkeypatch) -> None:
    configure_profile(monkeypatch, age=None)
    monkeypatch.setattr(
        agent,
        "decide_next_action",
        lambda _: {"action": "ask_question", "question": "What is your age?"},
    )

    result = agent.run_agent("I have breast cancer.")

    assert result["action"] == "ask_question"
    assert result["question"] == "What is your age?"
    assert "not medical advice" in result["disclaimer"]


def test_planner_generated_search_query_is_executed(monkeypatch) -> None:
    configure_profile(monkeypatch)
    captured_queries = []
    monkeypatch.setattr(
        agent,
        "decide_next_action",
        decision_sequence(
            {
                "action": "search_trials",
                "query": {"condition": "breast neoplasm", "country": "Denmark"},
            },
            {"action": "return_results"},
        ),
    )
    monkeypatch.setattr(
        agent,
        "search_trials",
        lambda **query: captured_queries.append(query) or [],
    )

    result = agent.run_agent("complete profile")

    assert captured_queries == [
        {
            "condition": "breast neoplasm",
            "country": "Denmark",
            "page_size": agent.MAX_SEARCH_RESULTS,
        }
    ]
    assert result["search_history"][0]["query"]["condition"] == "breast neoplasm"


def test_planner_can_refine_search_but_never_exceeds_limit(monkeypatch) -> None:
    configure_profile(monkeypatch)
    search_calls = []
    monkeypatch.setattr(
        agent,
        "decide_next_action",
        decision_sequence(
            {
                "action": "search_trials",
                "query": {"condition": "stage 2 HER2 breast cancer", "country": "Denmark"},
            },
            {
                "action": "refine_search",
                "query": {"condition": "breast cancer", "country": "Denmark"},
            },
            {
                "action": "refine_search",
                "query": {"condition": "breast neoplasm", "country": "Denmark"},
            },
            {
                "action": "refine_search",
                "query": {"condition": "breast neoplasm", "country": "Denmark"},
            },
        ),
    )
    monkeypatch.setattr(
        agent,
        "search_trials",
        lambda **query: search_calls.append(query) or [],
    )

    result = agent.run_agent("complete profile")

    assert len(search_calls) == agent.MAX_SEARCHES
    assert [item["action"] for item in result["search_history"]] == [
        "search_trials",
        "refine_search",
    ]
    assert "search limit" in result["error"].lower()


def test_only_planner_selected_trials_get_full_details(monkeypatch) -> None:
    configure_profile(monkeypatch)
    trials = [candidate_trial("NCT001"), candidate_trial("NCT002")]
    detail_calls = []
    monkeypatch.setattr(agent, "clean_trial", lambda study: study)
    monkeypatch.setattr(agent, "search_trials", lambda **_: trials)
    monkeypatch.setattr(
        agent,
        "get_trial_details",
        lambda nct_id: detail_calls.append(nct_id)
        or next(trial for trial in trials if trial["nct_id"] == nct_id),
    )
    monkeypatch.setattr(
        agent,
        "assess_trial_match",
        lambda *_: {
            "label": "possibly_eligible",
            "reason": "Needs confirmation.",
            "missing_information": [],
        },
    )
    monkeypatch.setattr(
        agent,
        "decide_next_action",
        decision_sequence(
            {
                "action": "search_trials",
                "query": {"condition": "breast cancer", "country": "Denmark"},
            },
            {"action": "select_trials", "nct_ids": ["NCT002"]},
            {"action": "fetch_trial_details"},
            {"action": "assess_trials"},
            {"action": "return_results"},
        ),
    )

    result = agent.run_agent("complete profile")

    assert detail_calls == ["NCT002"]
    assert result["selected_nct_ids"] == ["NCT002"]
    assert result["results"][0]["nct_id"] == "NCT002"


def test_invalid_selected_ids_are_ignored_when_valid_ids_remain(monkeypatch) -> None:
    configure_profile(monkeypatch)
    trial = candidate_trial("NCT001")
    detail_calls = []
    monkeypatch.setattr(agent, "clean_trial", lambda study: study)
    monkeypatch.setattr(agent, "search_trials", lambda **_: [trial])
    monkeypatch.setattr(
        agent,
        "get_trial_details",
        lambda nct_id: detail_calls.append(nct_id) or trial,
    )
    monkeypatch.setattr(
        agent,
        "assess_trial_match",
        lambda *_: {
            "label": "likely_eligible",
            "reason": "The available criteria match.",
            "missing_information": [],
        },
    )
    monkeypatch.setattr(
        agent,
        "decide_next_action",
        decision_sequence(
            {
                "action": "search_trials",
                "query": {"condition": "breast cancer", "country": "Denmark"},
            },
            {"action": "select_trials", "nct_ids": ["NCT999", "NCT001"]},
            {"action": "fetch_trial_details"},
            {"action": "assess_trials"},
            {"action": "return_results"},
        ),
    )

    result = agent.run_agent("complete profile")

    assert detail_calls == ["NCT001"]
    assert result["selected_nct_ids"] == ["NCT001"]


def test_full_details_are_capped_at_maximum(monkeypatch) -> None:
    configure_profile(monkeypatch)
    trials = [candidate_trial(f"NCT{i:03}") for i in range(7)]
    detail_calls = []
    monkeypatch.setattr(agent, "clean_trial", lambda study: study)
    monkeypatch.setattr(agent, "search_trials", lambda **_: trials)
    monkeypatch.setattr(
        agent,
        "get_trial_details",
        lambda nct_id: detail_calls.append(nct_id)
        or next(trial for trial in trials if trial["nct_id"] == nct_id),
    )
    monkeypatch.setattr(
        agent,
        "decide_next_action",
        decision_sequence(
            {
                "action": "search_trials",
                "query": {"condition": "breast cancer", "country": "Denmark"},
            },
            {
                "action": "select_trials",
                "nct_ids": [trial["nct_id"] for trial in trials],
            },
            {"action": "fetch_trial_details"},
            {"action": "return_results"},
            {"action": "return_results"},
        ),
    )

    result = agent.run_agent("complete profile")

    assert len(detail_calls) == agent.MAX_DETAILED_TRIALS
    assert "must be assessed" in result["error"].lower()


def test_hard_mismatch_is_filtered_before_semantic_assessment(monkeypatch) -> None:
    configure_profile(monkeypatch)
    shallow = candidate_trial("NCT001")
    full_mismatch = candidate_trial("NCT001", min_age=70)
    semantic_calls = []
    monkeypatch.setattr(agent, "clean_trial", lambda study: study)
    monkeypatch.setattr(agent, "search_trials", lambda **_: [shallow])
    monkeypatch.setattr(agent, "get_trial_details", lambda _: full_mismatch)
    monkeypatch.setattr(
        agent,
        "assess_trial_match",
        lambda *_: semantic_calls.append(True),
    )
    monkeypatch.setattr(
        agent,
        "decide_next_action",
        decision_sequence(
            {
                "action": "search_trials",
                "query": {"condition": "breast cancer", "country": "Denmark"},
            },
            {"action": "select_trials", "nct_ids": ["NCT001"]},
            {"action": "fetch_trial_details"},
            {"action": "return_results"},
        ),
    )

    result = agent.run_agent("complete profile")

    assert semantic_calls == []
    assert result["results"] == []


def test_agent_returns_ranked_results_and_city_preference(monkeypatch) -> None:
    configure_profile(monkeypatch)
    first = candidate_trial(
        "NCT001",
        locations=[
            {
                "facility": "Aarhus Site",
                "city": "Aarhus",
                "country": "Denmark",
                "status": "RECRUITING",
            },
            {
                "facility": "Copenhagen Site",
                "city": "Copenhagen",
                "country": "Denmark",
                "status": "RECRUITING",
            },
        ],
    )
    second = candidate_trial("NCT002")
    trials = [first, second]
    labels = {
        "NCT001": "possibly_eligible",
        "NCT002": "likely_eligible",
    }
    monkeypatch.setattr(agent, "clean_trial", lambda study: study)
    monkeypatch.setattr(agent, "search_trials", lambda **_: trials)
    monkeypatch.setattr(
        agent,
        "get_trial_details",
        lambda nct_id: next(trial for trial in trials if trial["nct_id"] == nct_id),
    )
    monkeypatch.setattr(
        agent,
        "assess_trial_match",
        lambda _, trial: {
            "label": labels[trial["nct_id"]],
            "reason": "Plain-language reason.",
            "missing_information": ["HER2 status"],
        },
    )
    monkeypatch.setattr(
        agent,
        "decide_next_action",
        decision_sequence(
            {
                "action": "search_trials",
                "query": {"condition": "breast cancer", "country": "Denmark"},
            },
            {"action": "select_trials", "nct_ids": ["NCT001", "NCT002"]},
            {"action": "fetch_trial_details"},
            {"action": "assess_trials"},
            {"action": "return_results"},
        ),
    )

    result = agent.run_agent("complete profile")

    assert [item["nct_id"] for item in result["results"]] == ["NCT002", "NCT001"]
    nct001 = next(item for item in result["results"] if item["nct_id"] == "NCT001")
    assert nct001["nearest_recruiting_location"]["city"] == "Copenhagen"
    assert "candidate matches" in result["disclaimer"]


def test_agent_loop_cannot_run_forever(monkeypatch) -> None:
    configure_profile(monkeypatch)
    trial = candidate_trial("NCT001")
    decisions = [
        {
            "action": "search_trials",
            "query": {"condition": "breast cancer", "country": "Denmark"},
        },
        *[
            {"action": "select_trials", "nct_ids": ["NCT001"]}
            for _ in range(agent.MAX_AGENT_STEPS - 1)
        ],
    ]
    monkeypatch.setattr(agent, "clean_trial", lambda study: study)
    monkeypatch.setattr(agent, "search_trials", lambda **_: [trial])
    monkeypatch.setattr(
        agent,
        "decide_next_action",
        decision_sequence(*decisions),
    )

    result = agent.run_agent("complete profile")

    assert result["error"] == "The agent reached its step limit."


def test_malformed_planner_response_fails_safely(monkeypatch) -> None:
    configure_profile(monkeypatch)
    monkeypatch.setattr(agent, "decide_next_action", lambda _: "not a JSON object")

    result = agent.run_agent("complete profile")

    assert result["action"] == "show_results"
    assert result["results"] == []
    assert "JSON object" in result["error"]
    assert "not medical advice" in result["disclaimer"]


def test_search_ready_profile_retries_after_optional_question(monkeypatch) -> None:
    configure_profile(monkeypatch)
    search_calls = []
    monkeypatch.setattr(
        agent,
        "decide_next_action",
        decision_sequence(
            {
                "action": "ask_question",
                "question": "What is the HER2 status?",
            },
            {
                "action": "search_trials",
                "query": {"condition": "breast cancer", "country": "Denmark"},
            },
            {"action": "return_results"},
        ),
    )
    monkeypatch.setattr(
        agent,
        "search_trials",
        lambda **query: search_calls.append(query) or [],
    )

    result = agent.run_agent("complete profile")

    assert result["action"] == "show_results"
    assert len(search_calls) == 1
    assert result["search_history"][0]["query"]["condition"] == "breast cancer"
