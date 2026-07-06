# CTE Agent

Clinical Trial Eligibility agent that helps a patient find possible recruiting clinical trial matches from ClinicalTrials.gov.

The app is intentionally small: a Streamlit chat UI collects the patient's situation, an agent extracts missing clinical details, searches ClinicalTrials.gov, filters obvious non-matches with code, and asks an LLM to reason over softer eligibility criteria.

## What It Does

1. Accepts a free-text patient description.
2. Extracts age, sex, condition, stage, prior treatments, biomarkers, country, and travel preference.
3. Asks a clarifying question when key information is missing.
4. Searches recruiting trials in ClinicalTrials.gov.
5. Cleans each trial into a smaller structure.
6. Applies deterministic filters for status, age, sex, and recruiting country.
7. Uses the LLM only for softer criteria such as stage, prior treatments, biomarkers, and uncertainty.
8. Returns a ranked shortlist with a safety disclaimer.

## Run Locally

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file:

```text
OPENAI_API_KEY=your_api_key_here
```

Run the app:

```bash
streamlit run app.py
```

Run tests:

```bash
pytest
```

## Architecture

- `app.py`: Streamlit chat interface and session state.
- `src/agent.py`: main agent loop: ask, search, filter, assess, return.
- `src/profile_extractor.py`: extracts a structured patient profile from free text.
- `src/message_guard.py`: keeps the chat focused on clinical-trial matching.
- `src/clinicaltrials_client.py`: ClinicalTrials.gov API integration.
- `src/trial_cleaner.py`: normalizes raw trial records and separates eligibility text into inclusion/exclusion sections.
- `src/eligibility.py`: deterministic hard filters before spending LLM calls.
- `src/semantic_matcher.py`: LLM-based soft eligibility assessment.
- `src/models.py`: shared Pydantic models for important result shapes.
- `tests/`: unit tests using mocks and local sample data.

## Key Design Decisions

- Hard constraints are checked in Python first: recruiting status, age range, sex, and country.
- The LLM is reserved for criteria that need interpretation, such as disease stage, prior therapies, and biomarkers.
- The ClinicalTrials.gov request uses a limited `fields` list to avoid carrying full records through the app.
- Results are framed as candidate matches only, never as medical advice or a definitive eligibility ruling.
- The UI is simple on purpose because the project is about data cleaning and agent behavior, not polished styling.

## Limitations

- Location matching is country-level, not true distance-to-site matching.
- Eligibility parsing is section-based and conservative; it does not fully understand every criteria sentence.
- The agent loop is focused on one patient at a time and one search pass.
- LLM JSON responses should be made stricter with structured outputs in a production version.

## With More Time

- Add structured OpenAI outputs with Pydantic validation.
- Fetch full trial details only for a smaller set selected by the agent.
- Add better ranking using location, phase, condition match, and eligibility confidence.
- Improve travel-distance handling and city-level matching.
