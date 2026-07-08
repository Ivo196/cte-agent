from typing import Optional

import streamlit as st

from src.agent import run_agent
from src.input_guard import classify_message


CHAT_PLACEHOLDER = (
    "Describe your condition, age, location, prior treatments, and travel preferences..."
)
THINKING_LABEL = "Thinking..."


def init_page() -> None:
    st.set_page_config(
        page_title="Clinical Trial Eligibility Agent",
        page_icon=":material/local_hospital:",
    )

    st.title("Clinical Trial Eligibility Agent")
    st.caption(
        "Describe your condition, age, location, prior treatments, and travel "
        "preferences. This tool identifies possible clinical trial matches only."
    )
    st.warning(
        "This is not medical advice and does not determine eligibility. "
        "Always discuss possible trials with your doctor and the clinical trial team."
    )


def init_state() -> None:
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("latest_results", None)


def add_message(role: str, content: str, relevant: bool = True) -> None:
    st.session_state.messages.append(
        {
            "role": role,
            "content": content,
            "relevant": relevant,
        }
    )


def get_user_context() -> str:
    return "\n".join(
        message["content"]
        for message in st.session_state.messages
        if message["role"] == "user" and message.get("relevant", True)
    )


def render_history() -> None:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])


def render_trial_result(trial: dict) -> None:
    location = trial.get("location") or {}
    phase = ", ".join(trial["phase"]) if trial["phase"] else "Not listed"

    st.subheader(f'{trial["nct_id"]} - {trial["title"]}')
    st.write(f'**Assessment:** {trial["label"].replace("_", " ").title()}')
    st.write(f'**Reason:** {trial["reason"]}')
    st.write(f'**Status:** {trial["status"]}')
    st.write(f"**Phase:** {phase}")

    if location:
        st.write(
            f"**Recruiting location:** "
            f'{location.get("facility", "Unknown site")} - '
            f'{location.get("city", "Unknown city")}, '
            f'{location.get("country", "Unknown country")}'
        )

    if trial.get("missing_information"):
        st.write(
            "**Information to confirm:** "
            + "; ".join(trial["missing_information"][:4])
        )

    st.link_button("View trial on ClinicalTrials.gov", trial["trial_url"])
    st.divider()


def render_results(result: dict) -> None:
    results = result.get("results", [])

    if not results:
        st.info(result.get("reply", "No candidate trials found."))
        return

    for trial in results:
        render_trial_result(trial)

    st.info(result["disclaimer"])


def handle_agent_turn(user_input: str) -> tuple[str, Optional[dict]]:
    guard_result = classify_message(
        message=user_input,
        conversation_context=get_user_context(),
    )

    if guard_result["classification"] == "off_topic":
        add_message("user", user_input, relevant=False)
        reply = guard_result["reply"]
        add_message("assistant", reply, relevant=False)
        return reply, None

    add_message("user", user_input)
    result = run_agent(get_user_context())

    if result["action"] == "ask_question":
        reply = result["question"]
        add_message("assistant", reply)
        st.session_state.latest_results = None
        return reply, None

    reply = result.get("reply", "I found these possible candidate matches:")
    add_message("assistant", reply)
    st.session_state.latest_results = result
    return reply, result


def handle_user_input(user_input: str) -> None:
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner(THINKING_LABEL):
            reply, result = handle_agent_turn(user_input)

        st.markdown(reply)

        if result:
            render_results(result)


def main() -> None:
    init_page()
    init_state()
    render_history()

    if st.session_state.latest_results:
        render_results(st.session_state.latest_results)

    user_input = st.chat_input(CHAT_PLACEHOLDER)

    if user_input:
        handle_user_input(user_input)


if __name__ == "__main__":
    main()
