# CTE Agent

CTE means **Clinical Trial Eligibility**.

This project is a small patient-facing agent that helps patients find possible
recruiting clinical trial matches from
[ClinicalTrials.gov](https://clinicaltrials.gov/).

The app keeps the workflow simple and safety-focused:

1. Collect a patient description in plain language.
2. Turn that description into a structured patient profile.
3. Ask a clarification question if important information is missing.
4. Search ClinicalTrials.gov for recruiting trials.
5. Clean the messy trial records into a smaller structure.
6. Filter obvious non-matches with normal Python code.
7. Use the LLM only for the softer eligibility reasoning.
8. Return a ranked shortlist with links and a safety disclaimer.

## Quick Start

Create a virtual environment:

```bash
python3 -m venv .venv
```

Install dependencies:

```bash
.venv/bin/python -m pip install -r requirements.txt
```

Create a `.env` file:

```text
OPENAI_API_KEY=your_api_key_here
```

Run the app:

```bash
.venv/bin/streamlit run app.py
```

Run tests:

```bash
.venv/bin/python -m pytest -q
```

## The Simple Architecture

The app is intentionally split into small files so each part has one job.

```text
Patient message
    |
    v
app.py
    |
    v
src/agent.py
    |
    +--> src/profile_extractor.py
    |       Extracts age, sex, condition, stage, treatments, biomarkers,
    |       country, city, and travel preference from free text.
    |
    +--> src/clinicaltrials_client.py
    |       Searches ClinicalTrials.gov and fetches full trial details.
    |
    +--> src/trial_cleaner.py
    |       Keeps only the fields the agent needs and splits eligibility
    |       criteria into inclusion, exclusion, and other sections.
    |
    +--> src/eligibility.py
    |       Applies hard filters in code: recruiting status, age, sex,
    |       country, and interventional study type.
    |
    +--> src/semantic_matcher.py
            Uses the LLM for soft criteria like disease stage, prior
            treatments, biomarkers, and missing information.
```

`src/input_guard.py` is a small support module used by the UI. It keeps casual
or unrelated messages out of the patient profile, so the agent does not treat a
joke or random question as medical context.

## File Guide

- `app.py`: Streamlit chat UI. It stores the conversation and displays results.
- `src/input_guard.py`: Keeps unrelated chat messages out of the patient profile.
- `src/agent.py`: Main control flow. This is the best file to read first.
- `src/profile_extractor.py`: LLM prompt that converts patient text into JSON.
- `src/clinicaltrials_client.py`: ClinicalTrials.gov API calls.
- `src/trial_cleaner.py`: Data cleaning for trial records and eligibility text.
- `src/eligibility.py`: Deterministic filters before spending LLM calls.
- `src/semantic_matcher.py`: LLM-based eligibility assessment for candidate trials.
- `src/llm.py`: Shared OpenAI client helper.
- `src/utils.py`: Small JSON parsing helper for model output.
- `tests/`: Unit tests with mocked API and LLM behavior.

## Main Agent Flow

The main flow is in `src/agent.py`.

1. `run_agent()` receives all patient messages so far.
2. `extract_patient_profile()` converts the text into structured JSON.
3. If age, sex, condition, country, or disease stage is missing, the agent asks
   one clarifying question and stops.
4. If the profile is complete enough, `search_trials()` queries recruiting
   trials from ClinicalTrials.gov.
5. Each search result is passed through `clean_trial()`.
6. `passes_hard_filters()` removes trials that clearly do not match.
7. The agent fetches full details for only the best small shortlist.
8. `assess_trial_match()` asks the LLM to classify each candidate trial.
9. Results are sorted as:
   - `likely_eligible`
   - `possibly_eligible`
   - `likely_not_eligible`
10. The UI shows the shortlist with NCT ID, title, phase, location, reason,
    missing information, and a ClinicalTrials.gov link.

## Important Design Choices

### 1. The LLM does not do everything

Hard constraints are checked with Python first:

- Trial must be recruiting.
- Patient age must fit the trial age range.
- Patient sex must match the trial sex rule.
- Trial must have a recruiting location in the requested country.
- Trial must be interventional.

This keeps the system cheaper, easier to test, and easier to explain.

### 2. The LLM is used where text interpretation matters

Clinical trial eligibility criteria are often written as messy free text. The
LLM is used after filtering to reason about softer criteria:

- Disease stage
- Prior treatments
- Biomarkers
- Uncertainty or missing information

### 3. The app carries only useful trial fields

ClinicalTrials.gov records are large. The client requests a limited field list,
and the cleaner converts each trial into a smaller dictionary that the agent can
reason over.

### 4. The output is careful

The app never says a patient is definitely eligible. It returns possible
candidate matches and tells the patient to confirm with their doctor and the
clinical trial team.

## Limitations

- Location matching is country-level, not city-level distance matching.
- The eligibility parser is conservative and section-based.
- LLM responses are parsed as JSON, but production code should use stricter
  structured outputs and validation.

## Future Work

- Improve ranking with distance, phase, condition match, and confidence.
- Add better error handling for API or LLM failures.
- Add city-level or radius-based location matching.
