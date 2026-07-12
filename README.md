# Clinical Trial Eligibility Agent

CTE means **Clinical Trial Eligibility**. This repository contains a focused,
patient-facing agent that helps identify possible recruiting clinical-trial
matches from [ClinicalTrials.gov](https://clinicaltrials.gov/).

The tool is decision support, not medical advice. It never determines final
eligibility. A doctor and the clinical trial team must confirm every candidate.

## Run locally

The project requires Python 3.10 or newer.

```bash
python -m venv .venv
```

Activate the environment:

```text
# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS or Linux
source .venv/bin/activate
```

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Create `.env` from `.env.example` and add an OpenAI API key:

```text
OPENAI_API_KEY=your_api_key_here
```

Start the Streamlit application:

```bash
python -m streamlit run app.py
```

Run the tests:

```bash
python -m pytest -q
```

All external API and LLM calls are mocked in the test suite.

## What the application does

1. The patient describes their situation in plain language.
2. The Streamlit chat preserves relevant messages across turns.
3. An input guard keeps off-topic messages out of the clinical context.
4. The patient profile extractor turns relevant conversation into structured
   fields such as age, diagnosis, stage, treatments, biomarkers, and location.
5. An LLM planner chooses the next action from the current agent state.
6. Python executes and validates that action.
7. The loop continues until the planner asks a question, returns results, or a
   safety limit stops the run.

This is intentionally not a fixed search pipeline. The planner can ask a
question before searching, refine an unhelpful query, choose a subset of NCT
IDs for deeper review, or stop when it has enough information.

## Architecture

```text
Streamlit conversation
        |
        +--> input_guard.py -------- excludes off-topic messages
        |
        +--> profile_extractor.py -- conversation -> patient profile
        |
        v
agent.py custom planner/action loop
        |
        +--> planner.py ---------------- chooses the next action with an LLM
        +--> clinicaltrials_client.py -- runs planner-generated API queries
        +--> trial_cleaner.py ---------- structures and compacts trial records
        +--> eligibility.py ------------ deterministic hard filters
        +--> semantic_matcher.py ------- LLM assessment of soft criteria
        |
        v
ranked candidate matches + source links + safety disclaimer
```

The project uses a small custom loop instead of LangGraph or another agent
framework. Given the focused scope, the explicit loop is easier to read, test,
and maintain. The LLM decides what happens next; Python owns validation,
limits, deterministic rules, and side effects.

## Planner actions

`src/planner.py` exposes seven possible actions:

- `ask_question`: request one clinically important missing fact.
- `search_trials`: choose and execute the first search query.
- `refine_search`: broaden or replace a weak query.
- `select_trials`: explicitly choose candidate NCT IDs for deep review.
- `fetch_trial_details`: retrieve full records only for selected IDs.
- `assess_trials`: evaluate soft eligibility criteria after hard filtering.
- `return_results`: stop and return the current ranked shortlist.

The planner returns JSON. `validate_decision()` rejects unsupported actions,
malformed queries, premature detail or assessment actions, unknown NCT IDs,
and attempts to exceed the configured limits. A malformed planner response
produces a controlled, patient-safe fallback instead of executing guessed work.

## Agent state

Each call to `run_agent()` starts with an explicit state dictionary:

```python
{
    "conversation_context": str,
    "patient_profile": dict,
    "search_history": list,
    "candidate_trials": list,
    "selected_nct_ids": list,
    "detailed_trials": list,
    "assessed_results": list,
    "step": int,
}
```

Execution limits are stored alongside the state. The planner receives a compact
view rather than full raw records: patient fields, search counts and queries,
candidate summaries, selected IDs, progress flags, result labels, and limits.

Candidate summaries contain only the NCT ID, title, phase, study type,
conditions, age range, sex, a small location list, and a truncated brief
summary. Full API records and full eligibility text are never sent to the
planner.

## Query planning and refinement

The planner constructs the ClinicalTrials.gov query from the patient profile.
It chooses a condition term and can include the patient's country. The API
client always adds the recruiting-status filter and requests only the initial
selection fields through the `fields` parameter.

An initial search requires age, sex, condition, and country. Once those fields
are available, optional details such as biomarkers, receptor status, residual
disease, surgery status, or treatment timing do not block the search. Any
missing optional information is reported with the assessed results for the
patient and study team to confirm.

If a query is too restrictive or returns weak candidates, the planner can use
`refine_search` to try a broader or alternative condition term. For example,
it can change `stage 2 HER2-positive breast cancer` to `breast cancer`. Search
history is included in the next planner view so it can avoid repeating a query.
The executor permits at most two searches.

## Trial selection and detailed retrieval

Search results are cleaned and passed through deterministic hard filters before
the planner sees compact summaries. The planner must explicitly return the NCT
IDs it wants to inspect. The executor validates those IDs against the current
candidates and ignores unknown IDs when valid choices remain.

There is no `candidates[:5]` selection. Full detail requests are made only for
validated planner-selected IDs, with a maximum of five trials. Full records are
hard-filtered again before semantic assessment.

## Data cleaning

`src/trial_cleaner.py` converts ClinicalTrials.gov records into a small internal
representation. It handles:

- minimum and maximum age parsing;
- sex and healthy-volunteer fields;
- recruiting locations only;
- condition names, phase, study type, and brief summary;
- conservative separation of inclusion, exclusion, and other criteria;
- a compact summary specifically for planner selection.

The initial search does not request the eligibility blob. Eligibility text is
obtained only for selected detailed records, split into structured sections,
and then passed to the semantic matcher. The model is not given one undifferentiated
raw eligibility blob.

## Hard versus soft eligibility

Deterministic Python checks run before every semantic assessment.

Hard filters in `src/eligibility.py` cover:

- recruiting status;
- interventional study type;
- minimum age;
- maximum age;
- sex;
- a recruiting location in the requested country.

The LLM in `src/semantic_matcher.py` is reserved for softer criteria:

- disease stage and cancer subtype;
- prior treatments and treatment timing;
- biomarkers;
- unclear inclusion or exclusion language;
- uncertainty and missing information.

This separation reduces cost and prevents obvious mismatches from consuming an
LLM eligibility call.

## Ranking and location

Assessed trials are ranked in this order:

1. `likely_eligible`
2. `possibly_eligible`
3. `likely_not_eligible`

For location, the prototype prefers a recruiting site in the patient's city.
If there is no exact city match, it returns the first recruiting site in the
requested country. This is a deterministic fallback, not a geographic distance
calculation.

Every returned trial includes its NCT ID, title, status, phase, nearest
reasonable recruiting location, label, one-line reason, missing information,
and ClinicalTrials.gov link.

## Safety decisions

- Results are always described as possible candidate matches.
- The agent never claims definitive eligibility.
- Prompts prohibit medical advice and require honest uncertainty.
- Every agent response includes the safety disclaimer, including clarification
  and controlled fallback responses.
- The patient is directed to a doctor and the clinical trial team for
  confirmation and is never discouraged from seeking care.

## Stopping limits

The custom loop has explicit safeguards:

```python
MAX_AGENT_STEPS = 6
MAX_SEARCHES = 2
MAX_SEARCH_RESULTS = 20
MAX_DETAILED_TRIALS = 5
```

The planner decides when to stop within those limits. Python enforces the hard
ceiling so malformed or repetitive decisions cannot create an infinite loop or
unbounded API/LLM usage.

## File guide

- `app.py`: Streamlit chat UI and relevant-message conversation handling.
- `src/agent.py`: state construction, action execution, ranking, and loop.
- `src/planner.py`: LLM next-action prompt and decision validation.
- `src/input_guard.py`: relevant versus off-topic message classification.
- `src/profile_extractor.py`: patient narrative to structured JSON.
- `src/clinicaltrials_client.py`: recruiting search and selected detail calls.
- `src/trial_cleaner.py`: record normalization and eligibility structuring.
- `src/eligibility.py`: deterministic hard constraints.
- `src/semantic_matcher.py`: soft eligibility reasoning.
- `src/llm.py`: shared OpenAI Responses API helper.
- `tests/`: mocked unit and agent-loop tests.

## Current limitations and next steps

- City matching is exact text matching; real distance calculation is future
  work.
- Eligibility section parsing is conservative and depends on recognizable
  inclusion and exclusion headings.
- Planner and matcher JSON is validated in Python, but production code should
  also use strict API-level structured outputs and schemas.
- API retry behavior, observability, and richer user-facing error states are
  limited.
- Ranking is based on semantic labels, not clinical outcome quality.
- The prototype needs evaluation against clinician-reviewed patient cases
  before any real-world use.

With more time, the next priorities would be schema-enforced model outputs,
geographic distance ranking, retry and monitoring support, and a small
clinician-reviewed evaluation set.
