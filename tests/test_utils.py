from src.utils import parse_json_object


def test_parse_json_object_reads_plain_json() -> None:
    assert parse_json_object('{"label": "possibly_eligible"}') == {
        "label": "possibly_eligible"
    }


def test_parse_json_object_reads_json_from_markdown_fence() -> None:
    text = """
    ```json
    {"classification": "off_topic", "reply": "Please provide trial details."}
    ```
    """

    assert parse_json_object(text) == {
        "classification": "off_topic",
        "reply": "Please provide trial details.",
    }
