from app import build_relevant_user_context


def test_off_topic_messages_do_not_enter_patient_context() -> None:
    messages = [
        {"role": "user", "content": "I am 60 years old.", "relevant": True},
        {"role": "assistant", "content": "What is your diagnosis?"},
        {"role": "user", "content": "Tell me a joke.", "relevant": False},
        {"role": "user", "content": "Breast cancer.", "relevant": True},
    ]

    context = build_relevant_user_context(messages)

    assert context == "I am 60 years old.\nBreast cancer."
    assert "joke" not in context
