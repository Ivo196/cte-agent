from src.llm import ask_json


def classify_message(message: str, conversation_context: str) -> dict:
    """
    Keeps casual or unrelated messages out of the patient profile.
    """

    prompt = f"""
You are a small input guard for a clinical trial eligibility chat.

The app should stay focused on collecting patient details and finding possible
clinical trial matches.

Conversation context:
{conversation_context}

New user message:
{message}

Classify the new message as exactly one of:
- relevant
- off_topic

Return valid JSON only:

{{
  "classification": "relevant | off_topic",
  "reply": "A short reply only if off_topic, otherwise an empty string."
}}

Relevant messages include patient age, sex, diagnosis, disease stage, cancer
subtype, biomarkers, prior treatments, current treatment status, location,
travel ability, or an answer to a clarification question.

If the message is off topic, politely say that this tool is only for finding
possible clinical trial matches and ask the user to describe the patient case.
Do not provide medical advice.
"""

    return ask_json(prompt)
