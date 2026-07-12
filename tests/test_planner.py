import pytest

from src import planner


def planner_state() -> dict:
    return {
        "patient_profile": {
            "age": 60,
            "sex": "female",
            "condition": "breast cancer",
            "country": "Denmark",
        },
        "search_history": [],
        "candidate_trials": [],
        "selected_nct_ids": [],
        "detailed_trials": [],
        "assessed_results": [],
        "limits": {
            "max_searches": 2,
            "max_detailed_trials": 5,
        },
    }


def test_llm_planner_receives_state_and_chooses_query(monkeypatch) -> None:
    captured = {}

    def fake_ask_json(prompt: str) -> dict:
        captured["prompt"] = prompt
        return {
            "action": "search_trials",
            "query": {"condition": "breast cancer", "country": "Denmark"},
        }

    monkeypatch.setattr(planner, "ask_json", fake_ask_json)

    decision = planner.decide_next_action(
        {
            "patient_profile": {
                "age": 60,
                "sex": "female",
                "condition": "breast cancer",
                "country": "Denmark",
            },
            "search_ready": True,
            "missing_search_fields": [],
            "candidate_summaries": [],
            "search_history": [],
            "step": 0,
            "limits": {"max_searches": 2},
        }
    )

    assert decision["query"]["condition"] == "breast cancer"
    assert "refine_search" in captured["prompt"]
    assert '"patient_profile"' in captured["prompt"]
    assert "When search_ready is true" in captured["prompt"]


def test_optional_details_cannot_block_a_search_ready_profile() -> None:
    state = planner_state()

    with pytest.raises(planner.PlannerDecisionError, match="ready to search"):
        planner.validate_decision(
            {
                "action": "ask_question",
                "question": "What is the HER2 status?",
            },
            state,
        )


def test_refined_search_is_valid_only_after_first_search() -> None:
    state = planner_state()
    decision = {
        "action": "refine_search",
        "query": {"condition": "breast cancer", "country": "Denmark"},
    }

    with pytest.raises(planner.PlannerDecisionError):
        planner.validate_decision(decision, state)

    state["search_history"].append({"query": {"condition": "HER2 breast cancer"}})
    assert planner.validate_decision(decision, state) == decision


def test_planner_explicitly_selects_only_known_nct_ids() -> None:
    state = planner_state()
    state["candidate_trials"] = [
        {"nct_id": "NCT001"},
        {"nct_id": "NCT002"},
    ]

    decision = planner.validate_decision(
        {
            "action": "select_trials",
            "nct_ids": ["NCT999", "NCT002"],
        },
        state,
    )

    assert decision["nct_ids"] == ["NCT002"]


def test_invalid_planner_action_is_rejected() -> None:
    with pytest.raises(planner.PlannerDecisionError):
        planner.validate_decision({"action": "run_fixed_pipeline"}, planner_state())
