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

PAGE_MAX_WIDTH = "1040px"

STYLES = f"""
<style>
/* ---- page shell: light neutral background, centred responsive container ---- */
[data-testid="stAppViewContainer"] {{ background-color: #f6f7f9; }}
[data-testid="stHeader"] {{ background: transparent; }}

.block-container,
[data-testid="stMainBlockContainer"] {{
    max-width: {PAGE_MAX_WIDTH};
    margin-left: auto;
    margin-right: auto;
    padding-top: 2.25rem;
    padding-bottom: 3rem;
    padding-left: 1.5rem;
    padding-right: 1.5rem;
}}

/* ---- typography and hierarchy ---- */
h1 {{ font-size: 2.1rem; font-weight: 700; letter-spacing: -0.02em; margin-bottom: 0.35rem; }}
h2 {{ font-size: 1.35rem; font-weight: 650; margin-top: 0.25rem; }}
h3 {{ font-size: 1.1rem; font-weight: 650; }}
[data-testid="stCaptionContainer"] p {{ color: #6b7280; font-size: 0.82rem; margin-bottom: 0; }}

/* ---- the form card ---- */
[data-testid="stForm"] {{
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 14px;
    padding: 1.6rem 1.75rem 1.35rem;
    box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04), 0 1px 3px rgba(16, 24, 40, 0.06);
}}

/* uniform label styling and spacing */
[data-testid="stWidgetLabel"] p {{
    font-weight: 600;
    font-size: 0.92rem;
    color: #111827;
    margin-bottom: 0.3rem;
}}

/* consistent full-width inputs, heights and radii */
.stTextInput input,
.stTextArea textarea,
[data-baseweb="select"] > div {{
    border-radius: 10px !important;
    border-color: #d7dbe0 !important;
    background-color: #ffffff !important;
    font-size: 0.95rem !important;
    box-shadow: none !important;
}}
.stTextInput input {{ min-height: 2.6rem; }}
[data-baseweb="select"] > div {{ min-height: 2.6rem; }}
.stTextArea textarea {{ line-height: 1.55; padding: 0.7rem 0.8rem; }}
.stTextInput, .stTextArea, .stSelectbox {{ width: 100% !important; }}

/* placeholders clearly distinct from typed text */
input::placeholder, textarea::placeholder {{
    color: #9aa1ac !important;
    opacity: 1 !important;
    font-style: italic;
}}

/* ---- buttons ---- */
.stButton > button,
[data-testid="stFormSubmitButton"] button {{
    border-radius: 10px;
    font-weight: 600;
    font-size: 0.93rem;
    min-height: 2.6rem;
    padding: 0.5rem 1.25rem;
    box-shadow: none;
}}
[data-testid="stFormSubmitButton"] button {{ margin-top: 0.35rem; }}
.stButton > button:hover {{ border-color: #2563eb; color: #2563eb; }}

/* ---- notices, errors and results ---- */
[data-testid="stAlert"] {{
    border-radius: 10px;
    padding: 0.85rem 1rem;
    font-size: 0.92rem;
}}
[data-testid="stExpander"] {{
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    margin-bottom: 0.6rem;
}}
[data-testid="stExpander"] summary {{ font-weight: 600; font-size: 0.94rem; }}
[data-testid="stVerticalBlockBorderWrapper"] {{
    background: #ffffff;
    border-radius: 14px;
}}
hr {{ margin: 2rem 0 1.5rem; border-color: #e5e7eb; }}

/* ---- responsive behaviour ---- */
@media (max-width: 1120px) {{
    .block-container, [data-testid="stMainBlockContainer"] {{ max-width: 100%; }}
}}
@media (max-width: 640px) {{
    .block-container, [data-testid="stMainBlockContainer"] {{
        padding-left: 1rem;
        padding-right: 1rem;
        padding-top: 1.5rem;
    }}
    [data-testid="stForm"] {{ padding: 1.1rem 1.1rem 0.9rem; }}
    h1 {{ font-size: 1.7rem; }}
    .stButton > button, [data-testid="stFormSubmitButton"] button {{ width: 100%; }}
}}
</style>
"""

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
    st.set_page_config(page_title="Startup Idea Validator", page_icon="🚀", layout="wide")
    st.markdown(STYLES, unsafe_allow_html=True)
    st.title("Startup Idea Validator")
    st.write(
        "Describe your startup idea in two or three lines. We structure it, then search the web "
        "for market size, competitors, customer demand and recent funding news."
    )

    values, submitted = read_form()
    st.button("Clear form", type="secondary", on_click=clear_form)

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
        st.divider()
        with st.container(border=True):
            show_result(result)
    elif not errors:
        st.info(
            "Fill in the form above and press **Validate my idea**. "
            f"The results appear here. The server must be running at {backend_url()}.",
            icon=ICON_INFO,
        )


main()
