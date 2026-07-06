import streamlit as st

from src.agent import run_agent
from src.message_guard import classify_message


st.set_page_config(
    page_title="Clinical Trial Eligibility Agent",
    page_icon=":material/local_hospital:",
)

st.title("Clinical Trial Eligibility Agent")

st.caption(
    "Describe your condition, age, location, prior treatments, and travel preferences. "
    "This tool identifies possible clinical trial matches only."
)

st.warning(
    "This is not medical advice and does not determine eligibility. "
    "Always discuss possible trials with your doctor and the clinical trial team."
)


# ----------------------------
# Session state
# ----------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

if "latest_results" not in st.session_state:
    st.session_state.latest_results = None


def add_message(role: str, content: str, relevant: bool = True) -> None:
    st.session_state.messages.append(
        {
            "role": role,
            "content": content,
            "relevant": relevant,
        }
    )


def get_user_context() -> str:
    """
    Returns only relevant user messages.
    Off-topic messages remain visible in the chat,
    but are excluded from the medical context.
    """
    return "\n".join(
        message["content"]
        for message in st.session_state.messages
        if message["role"] == "user" and message.get("relevant", True)
    )


def render_results(result: dict) -> None:
    results = result.get("results", [])

    if not results:
        st.info(
            "I could not find candidate trials that match the basic "
            "age, sex, recruitment, and location filters."
        )
        return

    st.markdown("I found these possible candidate matches:")

    label_order = {
        "likely_eligible": 0,
        "possibly_eligible": 1,
        "likely_not_eligible": 2,
    }

    sorted_results = sorted(
        results,
        key=lambda item: label_order.get(item["label"], 3),
    )

    for trial in sorted_results:
        location = trial.get("location") or {}

        st.subheader(f'{trial["nct_id"]} - {trial["title"]}')

        st.write(f'**Assessment:** {trial["label"].replace("_", " ").title()}')
        st.write(f'**Reason:** {trial["reason"]}')
        st.write(f'**Status:** {trial["status"]}')

        phase = ", ".join(trial["phase"]) if trial["phase"] else "Not listed"
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

        st.link_button(
            "View trial on ClinicalTrials.gov",
            trial["trial_url"],
        )

        st.divider()

    st.info(result["disclaimer"])


# ----------------------------
# Render previous history
# ----------------------------
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


# ----------------------------
# Render latest trial results
# ----------------------------
if st.session_state.latest_results:
    render_results(st.session_state.latest_results)


# ----------------------------
# New message
# ----------------------------
user_input = st.chat_input(
    "Describe your condition, age, location, prior treatments, and travel preferences..."
)

if user_input:
    # Context before the new message is added.
    previous_context = get_user_context()

    # Show the user message immediately.
    with st.chat_message("user"):
        st.markdown(user_input)

    guard_result = classify_message(
        message=user_input,
        conversation_context=previous_context,
    )

    # ----------------------------
    # Off-topic message
    # ----------------------------
    if guard_result["classification"] == "off_topic":
        add_message(
            role="user",
            content=user_input,
            relevant=False,
        )

        reply = guard_result["reply"]

        with st.chat_message("assistant"):
            st.markdown(reply)

        add_message(
            role="assistant",
            content=reply,
            relevant=False,
        )

    # ----------------------------
    # Relevant medical message
    # ----------------------------
    else:
        add_message(
            role="user",
            content=user_input,
            relevant=True,
        )

        full_context = get_user_context()

        with st.chat_message("assistant"):
            with st.spinner("Reviewing your information..."):
                result = run_agent(full_context)

            if result["action"] == "ask_question":
                reply = result["question"]

                st.markdown(reply)

                add_message(
                    role="assistant",
                    content=reply,
                    relevant=True,
                )

            else:
                reply = result.get(
                    "reply",
                    "I found these possible candidate matches:",
                )

                st.markdown(reply)

                add_message(
                    role="assistant",
                    content=reply,
                    relevant=True,
                )

                st.session_state.latest_results = result

                render_results(result)
