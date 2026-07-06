from src.llm import ask_json


def classify_message(message: str, conversation_context: str) -> dict:
    """
    Checks whether a new message is relevant to the clinical-trial matching flow.
    """

    prompt = f"""
You are a message guard for a clinical trial eligibility chat.

The user should only provide information relevant to finding possible clinical trial matches.

Relevant information includes:
- age
- sex
- diagnosis or condition
- disease stage
- cancer subtype
- biomarkers
- prior treatments
- current treatment status
- location or country
- travel ability
- symptoms or side effects only if relevant to trial matching
- answers to a previous clarification question

Conversation context:
{conversation_context}

New user message:
{message}

Classify the new message as exactly one of:
- relevant
- clarification_answer
- off_topic

Return valid JSON only:

{{
  "classification": "relevant | clarification_answer | off_topic",
  "reply": "A short reply only if off_topic, otherwise an empty string."
}}

Rules:
- If the message is unrelated, greeting-only, a command, a joke, casual chat, or does not add patient/trial information, classify it as off_topic.
- For off_topic, politely say that this tool can only help collect clinical information and find possible clinical trial matches.
- Do not provide medical advice.
"""

    return ask_json(prompt)
