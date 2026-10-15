"""Streamlit UI for submitting a startup idea and reading the validation result.

Run from the project root:  streamlit run frontend/app.py
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import streamlit as st  # noqa: E402

from agents.web_search_agent import render_markdown  # noqa: E402
from frontend.api_client import (  # noqa: E402
    FIELD_LABELS,
    OTHER_INDUSTRY,
    BackendError,
    FormValues,
    backend_url,
    character_hint,
    validate_idea,
    validate_submission,
)
from models.schemas import INDUSTRIES, PipelineResult  # noqa: E402

RESULT_KEY = "pipeline_result"
ERRORS_KEY = "field_errors"
FORM_KEYS = ("idea_description", "industry", "industry_other", "target_customers", "details")

PLACEHOLDER = (
    "A mobile app that detects crop diseases from a photo of a leaf.\n"
    "Small farmers get an instant diagnosis and a treatment suggestion in their own language.\n"
    "We want to start in Maharashtra with two farming cooperatives."
)

ICON_OK = "✅"
ICON_WARN = "⚠️"
ICON_FAIL = "❌"
ICON_INFO = "ℹ️"

STATUS_BANNERS = {
    "complete": (ICON_OK, "Complete", "Your idea was structured and researched.", st.success),
    "partial": (ICON_WARN, "Partial", "Part of the run did not finish. Everything we found is below.", st.warning),
    "failed": (ICON_FAIL, "Failed", "We could not process your idea. Details are below.", st.error),
}


def show_field_errors(errors: dict[str, str]) -> None:
    st.error("Please fix these before submitting:", icon=ICON_FAIL)
    for field, message in errors.items():
        st.markdown(f"- **{FIELD_LABELS.get(field, field).capitalize()}**: {message}")


def show_idea(result: PipelineResult) -> None:
    idea = result.idea
    if idea is None:
        return
    st.subheader("What the system understood")
    st.markdown(f"### {idea.idea_title}")
    st.markdown(f"**Industry:** {idea.industry}")
    st.markdown(f"**Problem**\n\n{idea.problem}")
    st.markdown(f"**Solution**\n\n{idea.solution}")
    st.markdown("**Target customers**")
    for customer in idea.target_customers:
        st.markdown(f"- {customer}")
    st.markdown("**Key features**")
    for feature in idea.key_features:
        st.markdown(f"- {feature}")


def show_research(result: PipelineResult) -> None:
    bundle = result.search
    if bundle is None:
        st.info("No market research was collected for this run.")
        return

    st.subheader("Market and competitor research")
    st.caption(f"{bundle.total_results} results from {len(bundle.sections)} searches")
    for position, section in enumerate(bundle.sections):
        with st.expander(f"{section.label} ({len(section.results)} results)", expanded=position == 0):
            st.caption(f"Search: {section.query}")
            if section.error:
                st.warning(section.error, icon=ICON_WARN)
            if section.answer:
                st.markdown(f"**Summary:** {section.answer}")
            for number, item in enumerate(section.results, 1):
                st.markdown(f"{number}. [{item.title}]({item.url})")
                st.caption(item.snippet)


def show_downloads(result: PipelineResult) -> None:
    with st.expander("Raw result and downloads"):
        st.json(result.model_dump(mode="json"))
        st.download_button(
            "Download JSON",
            data=result.model_dump_json(indent=2),
            file_name="validation_result.json",
            mime="application/json",
        )
        if result.search is not None:
            st.download_button(
                "Download Markdown report",
                data=render_markdown(result.search),
                file_name="market_research.md",
                mime="text/markdown",
            )


def show_result(result: PipelineResult) -> None:
    icon, label, explanation, banner = STATUS_BANNERS[result.status]
    banner(f"**Status: {label}.** {explanation}", icon=icon)

    for warning in result.warnings:
        st.warning(warning, icon=ICON_WARN)
    for failure in result.errors:
        st.error(f"The {failure.stage} step failed: {failure.message}", icon=ICON_FAIL)

    show_idea(result)
    if result.idea is not None:
        show_research(result)
    show_downloads(result)
    if result.timings:
        spent = ", ".join(f"{stage} {seconds:.1f}s" for stage, seconds in result.timings.items())
        st.caption(f"Time taken: {spent}")


def read_form() -> tuple[FormValues, bool]:
    with st.form("idea_form"):
        st.markdown("**Tell us about your idea**")
        description = st.text_area(
            "Your startup idea *",
            key="idea_description",
            height=150,
            placeholder=PLACEHOLDER,
            help=character_hint("idea_description"),
        )
        st.caption(character_hint("idea_description"))

        industry = st.selectbox("Industry *", INDUSTRIES, key="industry")
        industry_other = st.text_input(
            f"If {OTHER_INDUSTRY}, specify",
            key="industry_other",
            placeholder="For example: Sports and fitness",
            help=f"Only needed when you pick {OTHER_INDUSTRY} above.",
        )

        customers = st.text_input(
            "Who are your target customers? *",
            key="target_customers",
            placeholder="Small farmers in Maharashtra",
            help=character_hint("target_customers"),
        )
        details = st.text_area(
            "Anything else we should know?",
            key="details",
            height=100,
            placeholder="Location, stage, budget, competitors you already know about.",
            help=character_hint("relevant_details"),
        )
        st.caption(character_hint("relevant_details"))

        submitted = st.form_submit_button("Validate my idea", type="primary")

    values = FormValues(
        idea_description=description,
        industry=industry,
        industry_other=industry_other,
        target_customers=customers,
        relevant_details=details,
    )
    return values, submitted


def clear_form() -> None:
    for key in (*FORM_KEYS, RESULT_KEY, ERRORS_KEY):
        st.session_state.pop(key, None)


def main() -> None:
    st.set_page_config(page_title="Startup Idea Validator", page_icon="🚀", layout="centered")
    st.title("Startup Idea Validator")
    st.write(
        "Describe your startup idea in two or three lines. We structure it, then search the web "
        "for market size, competitors, customer demand and recent funding news."
    )

    values, submitted = read_form()
    st.button("Clear form", on_click=clear_form)

    if submitted:
        st.session_state.pop(RESULT_KEY, None)
        submission, errors = validate_submission(values)
        st.session_state[ERRORS_KEY] = errors
        if submission is not None:
            with st.spinner("Validating your idea..."):
                try:
                    st.session_state[RESULT_KEY] = validate_idea(submission)
                except BackendError as exc:
                    st.session_state[ERRORS_KEY] = {}
                    st.error(exc.message, icon=ICON_FAIL)

    errors = st.session_state.get(ERRORS_KEY) or {}
    if errors:
        show_field_errors(errors)

    result = st.session_state.get(RESULT_KEY)
    if result is not None:
        show_result(result)
    elif not errors:
        st.info(
            "Fill in the form above and press **Validate my idea**. "
            f"The results appear here. The server must be running at {backend_url()}.",
            icon=ICON_INFO,
        )


main()
