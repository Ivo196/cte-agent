import os

from dotenv import load_dotenv
from openai import OpenAI
from src.utils import parse_json_object


MODEL = "gpt-5-mini"

load_dotenv()


def get_client() -> OpenAI:
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def ask_json(prompt: str) -> dict:
    response = get_client().responses.create(
        model=MODEL,
        input=prompt,
    )

    return parse_json_object(response.output_text)
