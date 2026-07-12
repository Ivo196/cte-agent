"""Readable planner/action loop for clinical-trial matching."""

from src.clinicaltrials_client import get_trial_details, search_trials
from src.eligibility import passes_hard_filters
from src.planner import (
    PlannerDecisionError,
    decide_next_action,
    get_missing_search_fields,
    validate_decision,
)
from src.profile_extractor import extract_patient_profile
from src.semantic_matcher import assess_trial_match
from src.trial_cleaner import (
    build_candidate_summary,
    clean_trial,
    select_nearest_recruiting_location,
)


MAX_AGENT_STEPS = 6
MAX_SEARCHES = 2
MAX_SEARCH_RESULTS = 20
MAX_DETAILED_TRIALS = 5

LABEL_ORDER = {
    "likely_eligible": 0,
    "possibly_eligible": 1,
    "likely_not_eligible": 2,
}

SAFETY_DISCLAIMER = (
    "These are possible candidate matches only, not medical advice or "
    "a definitive eligibility decision. Please discuss them with your "
    "doctor and the clinical trial team. If you need medical care, contact "
    "an appropriate healthcare professional."
)


def build_initial_state(conversation_context: str, patient_profile: dict) -> dict:
    """Create the compact, explicit state carried through one agent run."""
    return {
        "conversation_context": conversation_context,
        "patient_profile": patient_profile,
        "search_history": [],
        "candidate_trials": [],
        "selected_nct_ids": [],
        "detailed_trials": [],
        "assessed_results": [],
        "step": 0,
        "limits": {
            "max_agent_steps": MAX_AGENT_STEPS,
            "max_searches": MAX_SEARCHES,
            "max_search_results": MAX_SEARCH_RESULTS,
            "max_detailed_trials": MAX_DETAILED_TRIALS,
        },
    }


def build_planner_view(state: dict) -> dict:
    """Return only compact information that the planner needs."""
    missing_search_fields = get_missing_search_fields(state["patient_profile"])
    return {
        "patient_profile": state["patient_profile"],
        "search_ready": not missing_search_fields,
        "missing_search_fields": missing_search_fields,
        "search_history": state["search_history"],
        "candidate_summaries": [
            build_candidate_summary(trial) for trial in state["candidate_trials"]
        ],
        "selected_nct_ids": state["selected_nct_ids"],
        "details_fetched": bool(state["detailed_trials"]),
        "detailed_nct_ids": [
            trial["nct_id"] for trial in state["detailed_trials"]
        ],
        "trials_assessed": bool(state["assessed_results"]),
        "assessed_labels": [
            {
                "nct_id": result["nct_id"],
                "label": result["label"],
            }
            for result in state["assessed_results"]
        ],
        "step": state["step"],
        "limits": state["limits"],
    }


def _get_valid_planner_decision(state: dict) -> dict:
    """Give the planner one corrective retry after an invalid decision."""
    planner_view = build_planner_view(state)
    last_error: Exception | None = None

    for _ in range(2):
        if last_error is not None:
            planner_view["validation_feedback"] = str(last_error)

        try:
            decision = decide_next_action(planner_view)
            return validate_decision(decision, state)
        except (PlannerDecisionError, ValueError, TypeError, KeyError) as exc:
            last_error = exc

    raise PlannerDecisionError(str(last_error))


def _passes_initial_filters(patient: dict, trial: dict) -> bool:
    passed, _ = passes_hard_filters(
        patient=patient,
        trial=trial,
        country=patient.get("country"),
    )
    return passed


def _execute_search(state: dict, decision: dict) -> None:
    query = decision["query"]
    studies = search_trials(
        condition=query["condition"],
        country=query.get("country"),
        page_size=MAX_SEARCH_RESULTS,
    )

    existing_ids = {
        trial.get("nct_id")
        for trial in state["candidate_trials"]
        if trial.get("nct_id")
    }
    new_candidates = []

    for study in studies:
        trial = clean_trial(study)
        nct_id = trial.get("nct_id")
        if (
            nct_id
            and nct_id not in existing_ids
            and _passes_initial_filters(state["patient_profile"], trial)
        ):
            new_candidates.append(trial)
            existing_ids.add(nct_id)

    state["candidate_trials"].extend(new_candidates)
    state["selected_nct_ids"] = []
    state["detailed_trials"] = []
    state["assessed_results"] = []
    state["search_history"].append(
        {
            "action": decision["action"],
            "query": query,
            "records_returned": len(studies),
            "candidates_after_hard_filters": len(new_candidates),
        }
    )


def _fetch_selected_trials(state: dict) -> None:
    detailed_trials = []

    for nct_id in state["selected_nct_ids"][:MAX_DETAILED_TRIALS]:
        full_study = get_trial_details(nct_id)
        trial = clean_trial(full_study)

        # Recheck hard constraints because detailed records may contain newer data.
        if _passes_initial_filters(state["patient_profile"], trial):
            detailed_trials.append(trial)

    state["detailed_trials"] = detailed_trials


def _build_trial_result(patient: dict, trial: dict) -> dict:
    semantic_result = assess_trial_match(patient, trial)
    nearest_location = select_nearest_recruiting_location(trial, patient)

    return {
        "nct_id": trial["nct_id"],
        "title": trial["title"],
        "status": trial["status"],
        "phase": trial["phase"],
        "nearest_recruiting_location": nearest_location,
        "label": semantic_result["label"],
        "reason": semantic_result["reason"],
        "missing_information": semantic_result.get("missing_information", []),
        "trial_url": trial["trial_url"],
    }


def _assess_detailed_trials(state: dict) -> None:
    results = []
    patient = state["patient_profile"]

    for trial in state["detailed_trials"]:
        # Hard constraints always run before the semantic eligibility assessment.
        if _passes_initial_filters(patient, trial):
            results.append(_build_trial_result(patient, trial))

    state["assessed_results"] = _sort_results(results)


def _sort_results(results: list[dict]) -> list[dict]:
    return sorted(
        results,
        key=lambda result: LABEL_ORDER.get(result.get("label"), 3),
    )


def _results_reply(results: list[dict]) -> str:
    if results:
        return "I found these possible candidate matches:"

    return (
        "I could not find candidate trials that passed the available recruitment, "
        "study type, age, sex, and location checks. You can discuss other search "
        "options with your doctor or a clinical trial team."
    )


def _build_question_response(state: dict, question: str) -> dict:
    return {
        "action": "ask_question",
        "patient_profile": state["patient_profile"],
        "question": question,
        "disclaimer": SAFETY_DISCLAIMER,
    }


def _build_final_response(state: dict) -> dict:
    results = _sort_results(state["assessed_results"])
    return {
        "action": "show_results",
        "patient_profile": state["patient_profile"],
        "reply": _results_reply(results),
        "results": results,
        "disclaimer": SAFETY_DISCLAIMER,
        "search_history": state["search_history"],
        "selected_nct_ids": state["selected_nct_ids"],
    }


def _safe_fallback_response(state: dict, reason: str) -> dict:
    """Stop predictably when the planner is malformed or the step limit is hit."""
    if state["assessed_results"]:
        return _build_final_response(state)

    return {
        "action": "show_results",
        "patient_profile": state["patient_profile"],
        "reply": (
            "I could not safely complete the trial search in this turn. "
            "Please try again or discuss trial options with your doctor."
        ),
        "results": [],
        "disclaimer": SAFETY_DISCLAIMER,
        "error": reason,
        "search_history": state["search_history"],
        "selected_nct_ids": state["selected_nct_ids"],
    }


def run_agent(conversation_context: str) -> dict:
    """Run an LLM-directed planner/action loop with strict execution limits."""
    patient_profile = extract_patient_profile(conversation_context)
    state = build_initial_state(conversation_context, patient_profile)

    for step in range(MAX_AGENT_STEPS):
        state["step"] = step

        try:
            decision = _get_valid_planner_decision(state)
        except (PlannerDecisionError, ValueError, TypeError, KeyError) as exc:
            return _safe_fallback_response(state, str(exc))

        action = decision["action"]

        if action == "ask_question":
            return _build_question_response(state, decision["question"])

        if action in {"search_trials", "refine_search"}:
            _execute_search(state, decision)
            continue

        if action == "select_trials":
            state["selected_nct_ids"] = decision["nct_ids"]
            state["detailed_trials"] = []
            state["assessed_results"] = []
            continue

        if action == "fetch_trial_details":
            _fetch_selected_trials(state)
            continue

        if action == "assess_trials":
            _assess_detailed_trials(state)
            continue

        if action == "return_results":
            return _build_final_response(state)

    return _safe_fallback_response(state, "The agent reached its step limit.")
