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
from frontend import analysis_views as views  # noqa: E402
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
from models.schemas import (  # noqa: E402
    INDUSTRIES,
    Competitor,
    CompetitorAnalysisResult,
    LabeledItem,
    MarketOpportunityResult,
    PipelineResult,
    SourceRef,
)

RESULT_KEY = "pipeline_result"
ERRORS_KEY = "field_errors"
FORM_KEYS = ("idea_description", "industry", "industry_other", "target_customers", "details")

PLACEHOLDER = (
    "A mobile app that detects crop diseases from a photo of a leaf.\n"
    "Small farmers get an instant diagnosis and a treatment suggestion in their own language.\n"
    "We want to start in Maharashtra with two farming cooperatives."
)

SPINNER_TEXT = "Validating your idea. The market and competitor analysis can take a few minutes..."

ICON_OK = "✅"
ICON_WARN = "⚠️"
ICON_FAIL = "❌"
ICON_INFO = "ℹ️"

PAGE_MAX_WIDTH = "1080px"

# Presentation only: a dark "research console" look on top of the dark theme in
# .streamlit/config.toml. Selectors use Streamlit's data-testid attributes; if one stops
# matching after a Streamlit update, that element simply falls back to the theme.
STYLES = f"""
<style>
/* ---- page shell: layered dark background with a faint grid, centred container ---- */
[data-testid="stAppViewContainer"] {{
    background:
        radial-gradient(1100px 520px at 12% -8%, rgba(56, 189, 248, 0.10), transparent 62%),
        radial-gradient(900px 480px at 100% 0%, rgba(129, 140, 248, 0.08), transparent 58%),
        linear-gradient(rgba(148, 163, 184, 0.035) 1px, transparent 1px) 0 0 / 44px 44px,
        linear-gradient(90deg, rgba(148, 163, 184, 0.035) 1px, transparent 1px) 0 0 / 44px 44px,
        #0a0e1a;
}}
[data-testid="stHeader"] {{ background: transparent; }}
::selection {{ background: rgba(56, 189, 248, 0.32); }}

[data-testid="stMainBlockContainer"] {{
    max-width: {PAGE_MAX_WIDTH};
    margin-left: auto;
    margin-right: auto;
    padding: 2.5rem 1.5rem 3.5rem;
}}
/* the element holding this <style> block takes no space */
[data-testid="stElementContainer"]:has(> [data-testid="stMarkdown"] style) {{ display: none; }}

/* ---- typography ---- */
[data-testid="stHeading"] h1 {{
    font-size: 2.4rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    line-height: 1.15;
    color: #f8fafc;
    text-shadow: 0 0 28px rgba(56, 189, 248, 0.22);
    padding-bottom: 0.25rem;
}}
[data-testid="stHeading"] h1::after {{
    content: "";
    display: block;
    width: 84px;
    height: 2px;
    margin-top: 0.8rem;
    border-radius: 2px;
    background: linear-gradient(90deg, #38bdf8, #818cf8);
    box-shadow: 0 0 12px rgba(56, 189, 248, 0.55);
}}

/* section headings: console-style labels with a status dot and a hairline */
[data-testid="stHeading"] h3 {{
    display: flex;
    align-items: center;
    gap: 0.6rem;
    font-family: "Source Code Pro", ui-monospace, "Cascadia Mono", Consolas, monospace;
    font-size: 0.9rem;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #bae6fd;
    margin-top: 1rem;
    padding-bottom: 0.6rem;
    border-bottom: 1px solid #1e2a42;
}}
[data-testid="stHeading"] h3::before {{
    content: "";
    flex: none;
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #38bdf8;
    box-shadow: 0 0 10px rgba(56, 189, 248, 0.85);
}}

/* body markdown: spacing and colours; text fills its panel so it lines up with the tables */
[data-testid="stMarkdownContainer"] {{ overflow-wrap: break-word; }}
[data-testid="stMarkdown"] [data-testid="stMarkdownContainer"] :is(p, li) {{
    color: #cbd5e1;
    line-height: 1.62;
}}
[data-testid="stMarkdownContainer"] code {{
    color: #a5f3fc;
    background: rgba(56, 189, 248, 0.08);
    border-radius: 4px;
}}
[data-testid="stMarkdown"] [data-testid="stMarkdownContainer"] h3 {{
    font-size: 1.45rem;
    font-weight: 650;
    letter-spacing: -0.01em;
    color: #f8fafc;
    padding-top: 0.2rem;
}}
[data-testid="stMarkdownContainer"] strong {{ color: #e2e8f0; font-weight: 650; }}
[data-testid="stMarkdownContainer"] :is(ul, ol) {{ margin-bottom: 1rem; }}
[data-testid="stMarkdownContainer"] li {{ margin-top: 0.2rem; margin-bottom: 0.2rem; }}
[data-testid="stMarkdownContainer"] li::marker {{ color: #38bdf8; }}
[data-testid="stMarkdownContainer"] a {{
    color: #7dd3fc;
    text-decoration-color: rgba(125, 211, 252, 0.4);
    text-underline-offset: 2px;
}}
[data-testid="stMarkdownContainer"] a:hover {{ color: #bae6fd; text-decoration-color: currentColor; }}

/* captions, including any headings that came inside a search snippet */
[data-testid="stCaptionContainer"],
[data-testid="stCaptionContainer"] p {{
    color: #a7b3c7;
    font-size: 0.84rem;
    line-height: 1.5;
}}
[data-testid="stCaptionContainer"] p {{ margin-bottom: 0; }}
[data-testid="stCaptionContainer"] :is(h1, h2, h3, h4, h5, h6) {{
    font-size: inherit;
    font-weight: 600;
    line-height: inherit;
    letter-spacing: 0;
    color: inherit;
    margin: 0;
    padding: 0;
}}

/* the intro line directly under the title */
[data-testid="stElementContainer"]:has(> [data-testid="stHeading"] h1)
    + [data-testid="stElementContainer"] [data-testid="stMarkdown"] [data-testid="stMarkdownContainer"] > p {{
    max-width: 82ch;
    color: #a7b3c7;
    font-size: 1.02rem;
}}

/* ---- the idea form: an elevated console panel ---- */
[data-testid="stForm"] {{
    position: relative;
    background: linear-gradient(180deg, rgba(23, 32, 51, 0.94), rgba(17, 24, 39, 0.94));
    border: 1px solid #24324a;
    border-radius: 16px;
    padding: 1.75rem 1.9rem 1.5rem;
    box-shadow: 0 0 0 1px rgba(56, 189, 248, 0.04), 0 24px 48px -28px rgba(0, 0, 0, 0.75);
}}
[data-testid="stForm"]::before {{
    content: "";
    position: absolute;
    top: -1px;
    left: 28px;
    right: 28px;
    height: 1px;
    pointer-events: none;
    background: linear-gradient(90deg, transparent, rgba(56, 189, 248, 0.7), rgba(129, 140, 248, 0.6), transparent);
}}
/* the form's own heading line ("Tell us about your idea") as a console label */
[data-testid="stForm"] [data-testid="stVerticalBlock"] > [data-testid="stElementContainer"]:first-child p {{
    font-family: "Source Code Pro", ui-monospace, "Cascadia Mono", Consolas, monospace;
    font-size: 0.82rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #7dd3fc;
}}
[data-testid="stForm"] [data-testid="stVerticalBlock"] > [data-testid="stElementContainer"]:first-child strong {{
    color: inherit;
    font-weight: 600;
}}

/* labels, help icons and inputs */
[data-testid="stWidgetLabel"] p {{
    font-weight: 600;
    font-size: 0.92rem;
    color: #e2e8f0;
    margin-bottom: 0.15rem;
}}
[data-testid="stTooltipIcon"] svg {{ color: #64748b; }}
[data-testid="stTextAreaRootElement"],
[data-testid="stTextInputRootElement"] {{
    border-color: #2a3954;
    transition: border-color 120ms ease, box-shadow 120ms ease;
}}
[data-testid="stTextAreaRootElement"]:focus-within,
[data-testid="stTextInputRootElement"]:focus-within {{
    border-color: #38bdf8;
    box-shadow: 0 0 0 3px rgba(56, 189, 248, 0.16);
}}
[data-testid="stTextAreaRootElement"] textarea {{ line-height: 1.55; }}
[data-testid="stTextArea"] textarea,
[data-testid="stTextInput"] input {{ color: #f1f5f9; font-size: 0.95rem; }}
textarea::placeholder,
input::placeholder {{
    color: #7c8aa5 !important;
    opacity: 1 !important;
    font-style: italic;
}}

/* ---- buttons ---- */
[data-testid="stBaseButton-primaryFormSubmit"],
[data-testid="stBaseButton-secondary"] {{
    min-height: 2.6rem;
    padding: 0.5rem 1.35rem;
    font-weight: 600;
    transition: border-color 120ms ease, box-shadow 120ms ease, color 120ms ease, filter 120ms ease;
}}
[data-testid="stBaseButton-primaryFormSubmit"] {{
    margin-top: 0.4rem;
    color: #04111f;
    background-color: #38bdf8;
    background-image: linear-gradient(135deg, #38bdf8, #818cf8);
    border: 1px solid rgba(186, 230, 253, 0.35);
    box-shadow: 0 10px 26px -12px rgba(56, 189, 248, 0.7);
}}
[data-testid="stBaseButton-primaryFormSubmit"] p {{ color: #04111f; font-weight: 700; letter-spacing: 0.01em; }}
[data-testid="stBaseButton-primaryFormSubmit"]:hover {{
    color: #04111f;
    filter: brightness(1.08);
    border-color: rgba(224, 242, 254, 0.6);
    box-shadow: 0 0 0 1px rgba(56, 189, 248, 0.45), 0 12px 30px -10px rgba(56, 189, 248, 0.75);
}}
[data-testid="stBaseButton-secondary"] {{
    color: #e2e8f0;
    background-color: rgba(15, 23, 42, 0.7);
    border: 1px solid #2a3954;
}}
[data-testid="stBaseButton-secondary"]:hover {{
    color: #7dd3fc;
    border-color: #38bdf8;
    box-shadow: 0 0 0 1px rgba(56, 189, 248, 0.2);
}}
[data-testid="stBaseButton-secondary"]:hover p {{ color: #7dd3fc; }}

/* ---- status, warnings and errors: compact rows with a coloured edge ---- */
[data-testid="stAlert"] {{ padding: 0; }}
[data-testid="stAlertContainer"] {{
    border-radius: 10px;
    border: 1px solid transparent;
    border-left-width: 3px;
    padding: 0.7rem 1rem;
    font-size: 0.93rem;
    line-height: 1.5;
}}
[data-testid="stAlertContainer"] [data-testid="stMarkdownContainer"] p {{ color: inherit; margin-bottom: 0; }}
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentSuccess"]) {{
    background-color: rgba(34, 197, 94, 0.10);
    border-color: rgba(34, 197, 94, 0.28);
    border-left-color: #22c55e;
    color: #bbf7d0;
}}
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]) {{
    background-color: rgba(245, 158, 11, 0.08);
    border-color: rgba(245, 158, 11, 0.22);
    border-left-color: #f59e0b;
    color: #fde68a;
}}
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]) {{
    background-color: rgba(239, 68, 68, 0.10);
    border-color: rgba(239, 68, 68, 0.30);
    border-left-color: #ef4444;
    color: #fecaca;
}}
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentInfo"]) {{
    background-color: rgba(56, 189, 248, 0.08);
    border-color: rgba(56, 189, 248, 0.22);
    border-left-color: #38bdf8;
    color: #bae6fd;
}}
[data-testid="stAlertContainer"] [data-testid="stMarkdownContainer"] a {{ color: inherit; }}
/* consecutive notices read as one list rather than separate blocks */
[data-testid="stElementContainer"]:has(> [data-testid="stAlert"])
    + [data-testid="stElementContainer"]:has(> [data-testid="stAlert"]) {{ margin-top: -0.5rem; }}

/* ---- the result panel (st.container(border=True)) ---- */
[data-testid="stLayoutWrapper"] > [data-testid="stVerticalBlock"] {{
    position: relative;
    background: linear-gradient(180deg, rgba(17, 24, 39, 0.92), rgba(13, 19, 33, 0.92));
    border: 1px solid #22304a;
    border-radius: 16px;
    padding: 1.6rem 1.75rem 1.5rem;
    box-shadow: 0 0 0 1px rgba(56, 189, 248, 0.03), 0 24px 48px -30px rgba(0, 0, 0, 0.8);
}}
[data-testid="stLayoutWrapper"] > [data-testid="stVerticalBlock"]::before {{
    content: "";
    position: absolute;
    top: -1px;
    left: 28px;
    right: 28px;
    height: 1px;
    pointer-events: none;
    background: linear-gradient(90deg, transparent, rgba(56, 189, 248, 0.55), rgba(129, 140, 248, 0.45), transparent);
}}

/* ---- expandable research sections ---- */
[data-testid="stExpander"] {{ background: transparent; border: none; }}
[data-testid="stExpander"] details {{
    background: rgba(15, 23, 42, 0.62);
    border: 1px solid #22304a;
    border-radius: 12px;
    overflow: hidden;
}}
[data-testid="stExpander"] details[open] {{ border-color: #2a3a58; }}
[data-testid="stExpander"] summary {{
    font-weight: 600;
    font-size: 0.95rem;
    color: #e2e8f0;
    padding-top: 0.75rem;
    padding-bottom: 0.75rem;
}}
[data-testid="stExpander"] summary:hover {{ color: #7dd3fc; }}
[data-testid="stExpander"] summary p {{ color: inherit; }}
[data-testid="stExpander"] details[open] > summary {{
    border-bottom: 1px solid #1e2a42;
    background: rgba(23, 32, 51, 0.55);
}}
[data-testid="stExpander"] [data-testid="stIconMaterial"] {{ color: #38bdf8; }}
[data-testid="stExpanderDetails"] {{ padding-top: 0.9rem; }}
/* a run of expanders sits as one group */
[data-testid="stLayoutWrapper"]:has(> [data-testid="stExpander"])
    + [data-testid="stLayoutWrapper"]:has(> [data-testid="stExpander"]) {{ margin-top: -0.4rem; }}

/* tables and the raw JSON view */
[data-testid="stDataFrame"] {{ border-radius: 10px; }}
[data-testid="stJson"] {{
    border: 1px solid #22304a;
    border-radius: 10px;
    padding: 0.6rem 0.8rem;
    background: rgba(10, 14, 26, 0.6);
}}

/* divider above the results */
hr {{
    margin: 2rem 0 1.5rem;
    border: none;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(56, 189, 248, 0.35), rgba(129, 140, 248, 0.35), transparent);
}}

/* ---- responsive behaviour ---- */
@media (max-width: 1160px) {{
    [data-testid="stMainBlockContainer"] {{ max-width: 100%; }}
}}
@media (max-width: 640px) {{
    [data-testid="stMainBlockContainer"] {{ padding: 1.5rem 1rem 2.5rem; }}
    [data-testid="stForm"],
    [data-testid="stLayoutWrapper"] > [data-testid="stVerticalBlock"] {{ padding: 1.1rem 1.1rem 1rem; }}
    [data-testid="stHeading"] h1 {{ font-size: 1.8rem; }}
    [data-testid="stBaseButton-primaryFormSubmit"],
    [data-testid="stBaseButton-secondary"] {{ width: 100%; }}
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


def show_items(title: str, items: list[LabeledItem]) -> None:
    st.markdown(f"**{title}**")
    if not items:
        st.caption(views.MSG_NONE_FOUND)
        return
    for item in items:
        st.markdown(f"- {views.item_line(item)}")


def show_sources(sources: list[SourceRef]) -> None:
    if not sources:
        st.caption(views.MSG_NO_SOURCES)
        return
    for line in views.source_lines(sources):
        st.markdown(line)


def show_notes(analysis: MarketOpportunityResult | CompetitorAnalysisResult) -> None:
    st.caption(views.quality_text(analysis.data_quality))
    for note in analysis.data_quality.notes:
        st.caption(note)


def show_market_size(market: MarketOpportunityResult) -> None:
    st.dataframe(views.market_size_rows(market), hide_index=True)
    broader = views.broader_market_rows(market)
    if broader:
        st.caption(views.MSG_BROADER_MARKETS)
        st.dataframe(broader, hide_index=True)


def show_segments(market: MarketOpportunityResult) -> None:
    for segment in market.segments:
        st.markdown(f"**{views.segment_heading(segment)}**")
        st.markdown(segment.description)
        if segment.needs:
            st.markdown(f"Needs: {'; '.join(segment.needs)}")
        show_items("Pain points", segment.pain_points)
    priority = market.priority_segment
    if priority is None:
        st.caption(views.MSG_NO_PRIORITY)
        return
    st.markdown(f"**Priority segment: {priority.segment_name}.** {priority.rationale}")
    for risk in priority.risks:
        st.markdown(f"- Risk: {risk}")


def show_market(result: PipelineResult) -> None:
    st.subheader("Market opportunity")
    market = result.market
    if market is None:
        st.info(views.MSG_NO_MARKET, icon=ICON_INFO)
        return
    show_notes(market)
    overview, demand = market.industry_overview, market.market_demand
    with st.expander("Industry overview", expanded=True):
        st.markdown(f"**Market category:** {overview.market_category}")
        st.markdown(overview.summary)
        show_items("Developments", overview.developments)
    with st.expander("Customer demand"):
        st.markdown(demand.summary)
        show_items("Demand evidence", demand.demand_evidence)
        show_items("Customer problems", demand.customer_problems)
        show_items("Interest signals", demand.interest_signals)
    with st.expander("Market size"):
        show_market_size(market)
    with st.expander("Trends"):
        for trend in market.trends:
            st.markdown(f"- {views.trend_line(trend)}")
        if not market.trends:
            st.caption(views.MSG_NONE_FOUND)
    with st.expander("Customer segments"):
        show_segments(market)
    with st.expander("Opportunities and limitations"):
        show_items("Opportunities", market.opportunities)
        show_items("Limitations", market.limitations)
    with st.expander(f"Sources ({len(market.sources)})"):
        show_sources(market.sources)
    for caveat in market.caveats:
        st.caption(caveat)


def show_competitor(competitor: Competitor) -> None:
    heading = f"**{competitor.name}**"
    if competitor.website:
        heading += f" ([website]({competitor.website}))"
    st.markdown(heading)
    for label, text in views.competitor_facts(competitor):
        st.markdown(f"- {label}: {text}")
    show_items("Strengths", competitor.strengths)
    show_items("Weaknesses", competitor.weaknesses)


def show_comparison(analysis: CompetitorAnalysisResult) -> None:
    rows = views.comparison_rows(analysis)
    if not rows:
        st.caption(views.MSG_NO_COMPARISON)
        return
    st.dataframe(rows, hide_index=True)
    st.dataframe(views.coverage_rows(analysis), hide_index=True)


def show_gaps(analysis: CompetitorAnalysisResult) -> None:
    st.markdown("**Possible market gaps**")
    for gap in analysis.market_gaps:
        st.markdown(f"- {views.gap_line(gap)}")
        st.caption(gap.caveat)
    if not analysis.market_gaps:
        st.caption(views.MSG_NONE_FOUND)
    show_items("Differentiation opportunities", analysis.differentiation_opportunities)


def show_competitors(result: PipelineResult) -> None:
    st.subheader("Competitors")
    analysis = result.competitors
    if analysis is None:
        st.info(views.MSG_NO_COMPETITORS, icon=ICON_INFO)
        return
    show_notes(analysis)
    for position, (heading, group) in enumerate(views.competitor_groups(analysis)):
        with st.expander(f"{heading} ({len(group)})", expanded=position == 0):
            for competitor in group:
                show_competitor(competitor)
    with st.expander("Feature comparison"):
        show_comparison(analysis)
    with st.expander("Market gaps and differentiation"):
        show_gaps(analysis)
    with st.expander(f"Searches run for this analysis ({len(analysis.queries_used)})"):
        for query in analysis.queries_used:
            st.markdown(f"- {query}")
    with st.expander(f"Sources ({len(analysis.sources)})"):
        show_sources(analysis.sources)
    for caveat in analysis.caveats:
        st.caption(caveat)


def show_downloads(result: PipelineResult) -> None:
    with st.expander("Raw result and downloads"):
        st.json(result.model_dump(mode="json"))
        st.download_button(
            "Download JSON",
            data=result.model_dump_json(indent=2),
            file_name="validation_result.json",
            mime="application/json",
        )
        report = views.report_markdown(result)
        if report:
            st.download_button(
                "Download Markdown report",
                data=report,
                file_name=views.report_file_name(result),
                mime="text/markdown",
            )


def show_result(result: PipelineResult) -> None:
    icon, label, explanation, banner = STATUS_BANNERS[result.status]
    banner(f"**Status: {label}.** {explanation}", icon=icon)

    for warning in result.warnings:
        st.warning(warning, icon=ICON_WARN)
    for failure in result.errors:
        st.error(f"The {views.stage_label(failure.stage)} step failed: {failure.message}", icon=ICON_FAIL)

    show_idea(result)
    if result.idea is not None:
        show_research(result)
        show_market(result)
        show_competitors(result)
    show_downloads(result)
    if result.timings:
        spent = ", ".join(
            f"{views.stage_label(stage)} {seconds:.1f}s" for stage, seconds in result.timings.items()
        )
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
        "for market size, competitors, customer demand and recent funding news, and analyse the "
        "market opportunity and the competitors from what the search found."
    )

    values, submitted = read_form()
    st.button("Clear form", type="secondary", on_click=clear_form)

    if submitted:
        st.session_state.pop(RESULT_KEY, None)
        submission, errors = validate_submission(values)
        st.session_state[ERRORS_KEY] = errors
        if submission is not None:
            with st.spinner(SPINNER_TEXT):
                try:
                    st.session_state[RESULT_KEY] = validate_idea(submission, include_analysis=True)
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
