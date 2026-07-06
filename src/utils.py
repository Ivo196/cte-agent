"""Small shared utilities."""

import json
import re


def parse_json_object(text: str) -> dict:
    """
    Parses a JSON object from model output.

    The prompts ask for JSON only, but this keeps the app from crashing if the
    model wraps the object in a short explanation or markdown code fence.
    """
    cleaned = text.strip()

    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.I)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.S)

        if not match:
            raise

        return json.loads(match.group())
