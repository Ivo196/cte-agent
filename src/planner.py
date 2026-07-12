"""LLM planner for the clinical-trial agent loop."""

import json
from typing import Any

from src.llm import ask_json


ACTIONS = {
    "ask_question",
    "search_trials",
    "refine_search",
    "select_trials",
    "fetch_trial_details",
    "assess_trials",
    "return_results",
}


class PlannerDecisionError(ValueError):
    """Raised when a planner decision cannot be executed safely."""


def decide_next_action(planner_view: dict) -> dict:
    """Ask the LLM to choose the next action from a compact state view."""
    state_text = json.dumps(planner_view, indent=2)

    prompt = f"""
You are the planner for a patient-facing clinical trial matching agent.
You genuinely control the next step. Do not assume a fixed workflow.

Choose exactly one action:
- ask_question: ask for one clinically important missing fact.
- search_trials: make the first ClinicalTrials.gov query.
- refine_search: make a broader or alternative query after a weak search.
- select_trials: explicitly choose promising NCT IDs from candidate summaries.
- fetch_trial_details: fetch full records only for already selected NCT IDs.
- assess_trials: evaluate soft eligibility criteria for fetched trials.
- return_results: stop when the agent has enough useful information, including
  when a completed search found no viable candidates.

Decision rules:
- Ask only eligibility-relevant questions. Do not require every possible field.
- You decide the search condition and optional country from the patient profile.
- Refine a search only when it is useful and the search limit allows it.
- Never invent NCT IDs. Select only IDs listed in candidate_summaries.
- Select at most the configured detailed-trial limit.
- Do not fetch details before selecting IDs.
- Do not assess before details are fetched.
- Do not claim definitive eligibility or provide medical advice.
- Stop within the supplied limits.

Return one JSON object only. Valid shapes are:
{{"action": "ask_question", "question": "..."}}
{{"action": "search_trials", "query": {{"condition": "...", "country": "..."}}}}
{{"action": "refine_search", "query": {{"condition": "...", "country": "..."}}}}
{{"action": "select_trials", "nct_ids": ["NCT..."]}}
{{"action": "fetch_trial_details"}}
{{"action": "assess_trials"}}
{{"action": "return_results"}}

Compact agent state:
{state_text}
"""

    return ask_json(prompt)


def validate_decision(decision: Any, state: dict) -> dict:
    """Validate and normalize an LLM decision before executing it."""
    if not isinstance(decision, dict):
        raise PlannerDecisionError("Planner response must be a JSON object.")

    action = decision.get("action")
    if action not in ACTIONS:
        raise PlannerDecisionError("Planner returned an unsupported action.")

    normalized = {"action": action}

    if action == "ask_question":
        question = decision.get("question")
        if not isinstance(question, str) or not question.strip():
            raise PlannerDecisionError("ask_question requires a question.")
        normalized["question"] = question.strip()

    if action in {"search_trials", "refine_search"}:
        if len(state["search_history"]) >= state["limits"]["max_searches"]:
            raise PlannerDecisionError("The search limit has been reached.")
        if action == "refine_search" and not state["search_history"]:
            raise PlannerDecisionError("A search must exist before refinement.")
        if action == "search_trials" and state["search_history"]:
            raise PlannerDecisionError("Use refine_search after the first search.")

        query = decision.get("query")
        if not isinstance(query, dict):
            raise PlannerDecisionError(f"{action} requires a query object.")

        condition = query.get("condition")
        if not isinstance(condition, str) or not condition.strip():
            raise PlannerDecisionError("A search query requires a condition.")

        country = query.get("country")
        if country is not None and not isinstance(country, str):
            raise PlannerDecisionError("Query country must be text or null.")

        normalized["query"] = {
            "condition": condition.strip(),
            "country": country.strip() if isinstance(country, str) else None,
        }

    if action == "select_trials":
        requested_ids = decision.get("nct_ids")
        if not isinstance(requested_ids, list):
            raise PlannerDecisionError("select_trials requires an NCT ID list.")

        allowed_ids = {
            trial.get("nct_id")
            for trial in state["candidate_trials"]
            if trial.get("nct_id")
        }
        selected_ids = []
        for nct_id in requested_ids:
            if (
                isinstance(nct_id, str)
                and nct_id in allowed_ids
                and nct_id not in selected_ids
            ):
                selected_ids.append(nct_id)

        selected_ids = selected_ids[: state["limits"]["max_detailed_trials"]]
        if not selected_ids:
            raise PlannerDecisionError("No selected NCT IDs are valid candidates.")
        normalized["nct_ids"] = selected_ids

    if action == "fetch_trial_details" and not state["selected_nct_ids"]:
        raise PlannerDecisionError("Trials must be selected before fetching details.")
    if action == "fetch_trial_details" and state["detailed_trials"]:
        raise PlannerDecisionError("Selected trial details are already available.")

    if action == "assess_trials" and not state["detailed_trials"]:
        raise PlannerDecisionError("Trial details must be fetched before assessment.")
    if action == "assess_trials" and state["assessed_results"]:
        raise PlannerDecisionError("The detailed trials are already assessed.")

    if (
        action == "return_results"
        and state["detailed_trials"]
        and not state["assessed_results"]
    ):
        raise PlannerDecisionError("Candidate trials must be assessed before return.")

    return normalized
