"""Deterministic fakes for the three Task 4 domains (KIRO_PROMPT_M2.md Section 10.1 and 10.2).

Each `Domain` carries everything one integrated pipeline run needs: the real sample submission
from `data/test_ideas/`, the extraction reply, the standard search bundle, the agent's own
targeted bundles, and the three LLM replies. Nothing here touches the network.

The AgriTech domain reuses the bundles already proven in `tests/pipeline_fakes.py`; only its
competitor replies are rebuilt, because `agritech.json` names no competitor of its own.

Evidence ids are **computed, not hard-coded**: the module runs the real evidence builders over
each bundle and maps every URL to the id it will carry, then writes the replies from that map.
A change to a bundle therefore cannot silently leave a reply citing the wrong source.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from agents.competitor_analysis_agent import competitor_evidence
from agents.competitor_checks import check_candidates, founder_text
from agents.evidence import build_evidence
from agents.market_size import market_evidence
from models.schemas import CandidateList, ExtractedIdea, IdeaSubmission, SearchBundle, SearchSection
from tests.fakes import VALID_EXTRACTION
from tests.m2_fakes import COMPETITOR_TARGETED, NO_MARKET_SIZE_RESULTS, bundle, result, section
from tests.pipeline_fakes import PIPELINE_MARKET_REPLY, PIPELINE_SEARCH

IDEAS_DIR = Path(__file__).resolve().parent.parent / "data" / "test_ideas"

LABEL_MARKET = "Market size and trends"
LABEL_COMPETITORS = "Competitors"
LABEL_DEMAND = "Customer demand and pain points"
LABEL_NEWS = "Recent news and funding"
LABEL_IDEA_MARKET = "Market size for this idea"
LABEL_CUSTOMER_MARKET = "Market size for the target customers"
LABEL_ALTERNATIVES = "Alternatives and substitutes"
LABEL_EMERGING = "Emerging approaches"


def submission_from(file_name: str) -> IdeaSubmission:
    """The real sample idea, so the fakes and `data/test_ideas/` cannot drift apart."""
    return IdeaSubmission(**json.loads((IDEAS_DIR / file_name).read_text(encoding="utf-8")))


def _targeted(*sections: SearchSection) -> SearchBundle:
    """A bundle from the agent's own searches. A search that found nothing is not a failure,
    so `queries_failed` stays 0, as `run_queries` would report it."""
    return SearchBundle(
        sections=list(sections),
        total_results=sum(len(item.results) for item in sections),
        queries_failed=0,
    )


def _url_ids(items) -> dict[str, str]:
    return {item.url: item.id for item in items if item.url}


def _item(text: str, basis: str, *ids: str) -> dict:
    return {"text": text, "basis": basis, "source_ids": list(ids)}


def _price(value: str | None, status: str, *ids: str) -> dict:
    return {"value": value, "status": status, "source_ids": list(ids), "note": None}


def _unavailable(note: str | None = None) -> dict:
    return {"value": None, "status": "unavailable", "source_ids": [], "note": note}


# --- AgriTech: reuses the bundles from tests/pipeline_fakes.py -------------------------------

AGRI_PLANTIX_ABOUT = "https://plantix.example/about"
AGRI_DIRECTORY = "https://directory.example/agrio/alternatives"
AGRI_CROPSENSE = "https://news.example/cropsense-launch"
AGRI_LEAFDOC_PRICING = "https://leafdoc.example/pricing"
AGRI_PLANTIX_PRICING = "https://plantix.example/pricing"
AGRI_KISAN = "https://helpline.example/kisan"
AGRI_DRONE = "https://research.example/drone-scouting"


def agri_candidates(std: dict[str, str]) -> dict:
    return {
        "candidates": [
            {"name": "Plantix", "type": "direct", "source_ids": [std[AGRI_PLANTIX_ABOUT], std[AGRI_DIRECTORY]],
             "basis": "sourced"},
            {"name": "Fasal", "type": "indirect", "source_ids": [std[AGRI_DIRECTORY]], "basis": "sourced"},
            {"name": "Map My Crop", "type": "indirect", "source_ids": [std[AGRI_DIRECTORY]], "basis": "sourced"},
            {"name": "CropSense", "type": "emerging", "source_ids": [std[AGRI_CROPSENSE]], "basis": "sourced"},
        ]
    }


def agri_analysis(ids: dict[str, str]) -> dict:
    plantix, directory, cropsense = ids[AGRI_PLANTIX_ABOUT], ids[AGRI_DIRECTORY], ids[AGRI_CROPSENSE]
    leafdoc_price, plantix_price = ids[AGRI_LEAFDOC_PRICING], ids[AGRI_PLANTIX_PRICING]
    kisan, drone = ids[AGRI_KISAN], ids[AGRI_DRONE]
    return {
        "competitors": [
            {
                "name": "Plantix", "type": "direct",
                "relevance_note": "A photo-based crop disease diagnosis app for farmers, the same job as this idea.",
                "website": "https://plantix.example", "source_ids": [plantix, plantix_price],
                "offering": "Photo-based crop disease diagnosis app", "target_segment": "Farmers in India",
                "key_features": ["Photo-based diagnosis", "Local language support", "Expert chat"],
                "value_proposition": "Free diagnosis in 18 languages",
                "pricing_model": _price("Free; Pro INR 499 a year", "sourced", plantix_price),
                "strengths": [_item("Diagnosis in 18 languages", "sourced", plantix)],
                "weaknesses": [_item("Expert chat needs the paid Pro plan", "sourced", plantix_price)],
                "positioning": "Free mass-market crop doctor",
                "differentiation_vs_startup": "This idea must beat a free incumbent on accuracy or advice.",
                "basis": "sourced",
            },
            {
                "name": "LeafDoc", "type": "direct",
                "relevance_note": "Sells paid photo diagnosis with expert chat to the same farmers.",
                "website": "https://leafdoc.example", "source_ids": [leafdoc_price],
                "offering": "Paid photo diagnosis with expert chat", "target_segment": None,
                "key_features": ["Photo-based diagnosis", "Expert chat"], "value_proposition": None,
                "pricing_model": _price("5 USD a month", "sourced", leafdoc_price),
                "strengths": [], "weaknesses": [], "positioning": None,
                "differentiation_vs_startup": None, "basis": "sourced",
            },
            {
                "name": "Fasal", "type": "indirect",
                "relevance_note": "A crop monitoring and advisory platform listed beside Plantix.",
                "website": None, "source_ids": [directory], "offering": "Crop monitoring and advisory",
                "target_segment": None, "key_features": ["Crop monitoring"], "value_proposition": None,
                "pricing_model": _unavailable(), "strengths": [], "weaknesses": [], "positioning": None,
                "differentiation_vs_startup": None, "basis": "sourced",
            },
            {
                "name": "Kisan call centres", "type": "indirect",
                "relevance_note": "A free phone helpline is a substitute for a diagnosis app.",
                "website": None, "source_ids": [kisan],
                "offering": "Free phone advice on crop diseases in local languages", "target_segment": "Farmers",
                "key_features": ["Local language support"], "value_proposition": "Free advice by phone",
                "pricing_model": _price("Free", "sourced", kisan),
                "strengths": [_item("Advice in local languages", "sourced", kisan)], "weaknesses": [],
                "positioning": None,
                "differentiation_vs_startup": "This idea gives instant photo diagnosis without a phone call.",
                "basis": "sourced",
            },
            {
                "name": "CropSense", "type": "emerging",
                "relevance_note": "A new drone-based disease scouting service for cooperatives.",
                "website": None, "source_ids": [cropsense, drone], "offering": "Drone-based disease scouting",
                "target_segment": "Farming cooperatives", "key_features": ["Drone scouting"],
                "value_proposition": None, "pricing_model": _unavailable(), "strengths": [], "weaknesses": [],
                "positioning": None, "differentiation_vs_startup": None, "basis": "sourced",
            },
        ],
        "comparison": {
            "features": ["Photo-based diagnosis", "Treatment advice", "Local language support", "Expert chat"],
            "rows": [
                {"competitor": "Plantix", "cells": [
                    {"feature": "Photo-based diagnosis", "status": "evidence_found", "source_ids": [plantix]},
                    {"feature": "Local language support", "status": "evidence_found", "source_ids": [plantix]},
                    {"feature": "Expert chat", "status": "evidence_found", "source_ids": [plantix_price]},
                ]},
                {"competitor": "LeafDoc", "cells": [
                    {"feature": "Photo-based diagnosis", "status": "evidence_found", "source_ids": [leafdoc_price]},
                    {"feature": "Expert chat", "status": "evidence_found", "source_ids": [leafdoc_price]},
                ]},
                {"competitor": "Fasal", "cells": [
                    {"feature": "Photo-based diagnosis", "status": "unclear", "source_ids": []},
                ]},
                {"competitor": "Kisan call centres", "cells": [
                    {"feature": "Local language support", "status": "evidence_found", "source_ids": [kisan]},
                    {"feature": "Treatment advice", "status": "evidence_found", "source_ids": [kisan]},
                ]},
                {"competitor": "CropSense", "cells": [
                    # Cites the launch article, which names CropSense; the drone research page
                    # does not, and a cell citing it would be demoted to unclear.
                    {"feature": "Drone scouting", "status": "evidence_found", "source_ids": [cropsense]},
                ]},
            ],
        },
        "market_gaps": [
            {"description": "Few competitors show treatment advice tied to the diagnosed disease.",
             "related_features": ["Treatment advice"], "basis": "ai_interpretation", "source_ids": [],
             "confidence": "medium"},
        ],
        "differentiation_opportunities": [
            _item("Combine photo diagnosis with treatment advice in local languages.", "ai_interpretation", plantix, kisan),
        ],
        "data_quality": {"evidence_level": "limited", "notes": ["Pricing for Fasal and CropSense was not found."]},
    }


# --- FinTech: cash-flow and expense management -----------------------------------------------

FIN_MARKET_REPORT = "https://reports.example/cash-flow-software-market"
FIN_LEDGERLITE_ABOUT = "https://ledgerlite.example/about"
FIN_DIRECTORY = "https://directory.example/cashradar-alternatives"
FIN_SURVEY = "https://smallbiz.example/cash-survey"
FIN_NEWS = "https://news.example/fintech-funding"
FIN_INDIA_MARKET = "https://research.example/expense-management-india"
FIN_GLOBAL_FINTECH = "https://insights.example/global-fintech-market"
FIN_LEDGERLITE_PRICING = "https://ledgerlite.example/pricing"
FIN_CASHRADAR_PRICING = "https://cashradar.example/pricing"
FIN_TEMPLATES = "https://spreadsheets.example/cash-flow-templates"
FIN_FLOWCAST = "https://news.example/flowcast-launch"

FIN_EXTRACTION = {
    "idea_title": "Cash Flow and Expense Management for Small Businesses",
    "problem": "Small business owners track expenses in spreadsheets and cannot see how much cash is left before bills fall due.",
    "solution": "A platform that reads bank and UPI statements with consent, sorts expenses into categories, and forecasts cash flow for the week ahead.",
    "target_customers": ["Small business owners in Indian cities", "Shop accountants"],
    "industry": "Finance / FinTech",
    "key_features": ["Expense categorisation", "Cash-flow forecast", "Bill due reminders", "Bank statement import"],
}

FIN_SEARCH = bundle(
    section(
        LABEL_MARKET,
        result(FIN_MARKET_REPORT,
               "The global cash flow management software market was valued at USD 1.4 billion in 2024 as small firms moved off spreadsheets.",
               "Cash flow management software market report", 0.9),
        answer="Cash flow management software is growing among small businesses.",
    ),
    section(
        LABEL_COMPETITORS,
        result(FIN_LEDGERLITE_ABOUT,
               "LedgerLite is an expense tracking app used by small shops to record daily sales and expenses.",
               "LedgerLite", 0.9),
        result(FIN_DIRECTORY,
               "Top CashRadar alternatives include LedgerLite and BookKeeper Pro for small business accounting.",
               "CashRadar alternatives and competitors", 0.8),
    ),
    section(
        LABEL_DEMAND,
        result(FIN_SURVEY,
               "Most small business owners say they track expenses in spreadsheets and cannot forecast cash flow.",
               "Small business cash survey", 0.7),
    ),
    section(
        LABEL_NEWS,
        result(FIN_NEWS, "Investors backed several small-business accounting startups in 2025.",
               "FinTech funding roundup", 0.6),
    ),
)

FIN_MARKET_SEARCH = _targeted(
    section(
        LABEL_IDEA_MARKET,
        result(FIN_INDIA_MARKET,
               "The expense management software market in India reached USD 180 million in 2024.",
               "Expense management software market in India", 0.9),
    ),
    section(
        LABEL_CUSTOMER_MARKET,
        result(FIN_GLOBAL_FINTECH, "The global fintech market was valued at USD 312 billion in 2024.",
               "Global fintech market outlook", 0.8),
    ),
)

FIN_COMPETITOR_SEARCH = _targeted(
    section("Competitor: Khatabook", error="No live results found for this query."),
    section(
        "Competitor: LedgerLite",
        result(FIN_LEDGERLITE_PRICING,
               "LedgerLite is free for one user and the Plus plan costs INR 299 a month for unlimited invoices.",
               "LedgerLite pricing", 0.9),
    ),
    section(
        "Competitor: CashRadar",
        result(FIN_CASHRADAR_PRICING,
               "CashRadar charges INR 499 a month for cash-flow forecasting and bill reminders.",
               "CashRadar pricing", 0.9),
    ),
    section(
        LABEL_ALTERNATIVES,
        result(FIN_TEMPLATES,
               "Free spreadsheet templates let owners track expenses manually without any subscription.",
               "Free cash flow spreadsheet templates", 0.8),
    ),
    section(
        LABEL_EMERGING,
        result(FIN_FLOWCAST,
               "FlowCast, a new startup, launched automated cash-flow forecasting for small firms in 2026.",
               "FlowCast launches cash-flow forecasting", 0.7),
    ),
)


def fin_market(ids: dict[str, str]) -> dict:
    report, india, global_fintech = ids[FIN_MARKET_REPORT], ids[FIN_INDIA_MARKET], ids[FIN_GLOBAL_FINTECH]
    survey, news = ids[FIN_SURVEY], ids[FIN_NEWS]
    return {
        "industry_overview": {
            "summary": "Small firms are moving from spreadsheets to software that tracks expenses and forecasts cash.",
            "market_category": "Cash flow and expense management software",
            "developments": [
                _item("Small firms are moving off spreadsheets towards cash flow management software.", "sourced", report),
                _item("Investors backed several small-business accounting startups in 2025.", "sourced", news),
            ],
        },
        "market_demand": {
            "summary": "Owners cannot forecast cash because expenses sit in spreadsheets.",
            "demand_evidence": [
                _item("Most small business owners say they track expenses in spreadsheets and cannot forecast cash flow.",
                      "sourced", survey),
            ],
            "customer_problems": [
                _item("Expenses are tracked in spreadsheets, so cash flow cannot be forecast.", "sourced", survey),
            ],
            "interest_signals": [
                _item("Spending on cash flow management software is rising as small firms leave spreadsheets.",
                      "ai_interpretation", report),
            ],
        },
        "market_size": {
            "tam": {"value": "USD 1.4 billion", "status": "sourced", "source_ids": [report],
                    "note": "Global cash flow management software market, 2024", "scope": "idea_market"},
            "sam": {"value": "USD 180 million", "status": "sourced", "source_ids": [india],
                    "note": "Expense management software market in India, 2024", "scope": "idea_market"},
            "som": _unavailable("No figure for the share a new entrant could win was found"),
        },
        "broader_markets": [
            {"value": "USD 312 billion", "status": "sourced", "source_ids": [global_fintech],
             "note": "Global fintech market, 2024", "scope": "broader_market"},
        ],
        "trends": [
            {"trend": "Small firms replacing spreadsheets with accounting software", "category": "business",
             "basis": "sourced", "source_ids": [report]},
        ],
        "segments": [
            {
                "name": "Owner-run shops",
                "description": "Single-owner shops that record sales and expenses by hand.",
                "segmentation_basis": "business_type",
                "needs": ["A weekly cash forecast", "Expense categorisation"],
                "pain_points": [_item("Expenses are tracked in spreadsheets, so cash flow is unclear.", "sourced", survey)],
                "source_ids": [survey],
            },
            {
                "name": "Shop accountants",
                "description": "Part-time accountants who close the books for several small shops.",
                "segmentation_basis": "needs",
                "needs": ["Bank statement import"],
                "pain_points": [_item("Statements are reconciled by hand for every shop.", "assumption")],
                "source_ids": [],
            },
        ],
        "priority_segment": {
            "segment_name": "Owner-run shops",
            "rationale": "They feel the cash flow problem directly and have no accountant to absorb it.",
            "risks": ["Free ledger apps already serve them"],
        },
        "opportunities": [
            _item("Turn imported statements into a weekly cash forecast.", "ai_interpretation", survey),
        ],
        "limitations": [
            _item("Expense tracking apps already record daily sales and expenses.", "sourced", ids[FIN_LEDGERLITE_ABOUT]),
        ],
        "data_quality": {
            "evidence_level": "limited",
            "notes": ["No figure for the share a new entrant could win was found."],
        },
    }


def fin_candidates(std: dict[str, str]) -> dict:
    return {
        "candidates": [
            {"name": "LedgerLite", "type": "direct", "source_ids": [std[FIN_LEDGERLITE_ABOUT], std[FIN_DIRECTORY]],
             "basis": "sourced"},
            {"name": "CashRadar", "type": "direct", "source_ids": [std[FIN_DIRECTORY]], "basis": "sourced"},
            {"name": "BookKeeper Pro", "type": "indirect", "source_ids": [std[FIN_DIRECTORY]], "basis": "sourced"},
            {"name": "Khatabook", "type": "direct", "source_ids": [], "basis": "user_provided"},
        ]
    }


def fin_analysis(ids: dict[str, str]) -> dict:
    about, directory = ids[FIN_LEDGERLITE_ABOUT], ids[FIN_DIRECTORY]
    ledger_price, cash_price = ids[FIN_LEDGERLITE_PRICING], ids[FIN_CASHRADAR_PRICING]
    templates, flowcast = ids[FIN_TEMPLATES], ids[FIN_FLOWCAST]
    return {
        "competitors": [
            {
                "name": "LedgerLite", "type": "direct",
                "relevance_note": "An expense tracking app for the same small shops.",
                "website": "https://ledgerlite.example", "source_ids": [about, ledger_price],
                "offering": "Expense tracking app for small shops", "target_segment": "Small shops",
                "key_features": ["Expense categorisation", "Daily sales record"],
                "value_proposition": "Free for a single user",
                "pricing_model": _price("Free for one user; Plus INR 299 a month", "sourced", ledger_price),
                "strengths": [_item("Free for one user", "sourced", ledger_price)],
                "weaknesses": [_item("Unlimited invoices need the paid Plus plan", "sourced", ledger_price)],
                "positioning": "Free entry-level expense tracker",
                "differentiation_vs_startup": "This idea adds a forecast rather than only a record of expenses.",
                "basis": "sourced",
            },
            {
                "name": "CashRadar", "type": "direct",
                "relevance_note": "Sells cash-flow forecasting and bill reminders, the same job as this idea.",
                "website": "https://cashradar.example", "source_ids": [directory, cash_price],
                "offering": "Cash-flow forecasting and bill reminders", "target_segment": "Small businesses",
                "key_features": ["Cash-flow forecast", "Bill due reminders"], "value_proposition": None,
                "pricing_model": _price("INR 499 a month", "sourced", cash_price),
                "strengths": [], "weaknesses": [], "positioning": None,
                "differentiation_vs_startup": "This idea imports statements automatically.", "basis": "sourced",
            },
            {
                "name": "BookKeeper Pro", "type": "indirect",
                "relevance_note": "General small business accounting listed beside the direct rivals.",
                "website": None, "source_ids": [directory], "offering": "Small business accounting",
                "target_segment": None, "key_features": ["Bookkeeping"], "value_proposition": None,
                "pricing_model": _unavailable(), "strengths": [], "weaknesses": [], "positioning": None,
                "differentiation_vs_startup": None, "basis": "sourced",
            },
            {
                "name": "Khatabook", "type": "direct",
                "relevance_note": "Named by the founder as a ledger app small shops already use.",
                "website": None, "source_ids": [], "offering": None, "target_segment": None,
                "key_features": [], "value_proposition": None, "pricing_model": _unavailable(),
                "strengths": [], "weaknesses": [], "positioning": None,
                "differentiation_vs_startup": None, "basis": "user_provided",
            },
            {
                "name": "Free spreadsheet templates", "type": "indirect",
                "relevance_note": "The manual habit this idea has to replace.",
                "website": None, "source_ids": [templates],
                "offering": "Spreadsheet templates for tracking expenses by hand", "target_segment": "Owners",
                "key_features": ["Expense categorisation"], "value_proposition": "No subscription",
                "pricing_model": _price("Free", "sourced", templates),
                "strengths": [_item("No subscription is needed", "sourced", templates)], "weaknesses": [],
                "positioning": None,
                "differentiation_vs_startup": "This idea removes the manual entry a template still needs.",
                "basis": "sourced",
            },
            {
                "name": "FlowCast", "type": "emerging",
                "relevance_note": "A new startup selling automated cash-flow forecasting.",
                "website": None, "source_ids": [flowcast], "offering": "Automated cash-flow forecasting",
                "target_segment": "Small firms", "key_features": ["Cash-flow forecast"], "value_proposition": None,
                "pricing_model": _unavailable(), "strengths": [], "weaknesses": [], "positioning": None,
                "differentiation_vs_startup": None, "basis": "sourced",
            },
        ],
        "comparison": {
            "features": ["Expense categorisation", "Cash-flow forecast", "Bill due reminders", "Bank statement import"],
            "rows": [
                {"competitor": "LedgerLite", "cells": [
                    {"feature": "Expense categorisation", "status": "evidence_found", "source_ids": [about]},
                    {"feature": "Cash-flow forecast", "status": "no_evidence_found", "source_ids": [about]},
                    {"feature": "Bank statement import", "status": "unclear", "source_ids": []},
                ]},
                {"competitor": "CashRadar", "cells": [
                    {"feature": "Cash-flow forecast", "status": "evidence_found", "source_ids": [cash_price]},
                    {"feature": "Bill due reminders", "status": "evidence_found", "source_ids": [cash_price]},
                ]},
                {"competitor": "BookKeeper Pro", "cells": [
                    {"feature": "Expense categorisation", "status": "unclear", "source_ids": []},
                ]},
                {"competitor": "Khatabook", "cells": []},
                {"competitor": "Free spreadsheet templates", "cells": [
                    {"feature": "Expense categorisation", "status": "evidence_found", "source_ids": [templates]},
                ]},
                {"competitor": "FlowCast", "cells": [
                    {"feature": "Cash-flow forecast", "status": "evidence_found", "source_ids": [flowcast]},
                ]},
            ],
        },
        "market_gaps": [
            {"description": "No competitor in the results imports bank and UPI statements automatically.",
             "related_features": ["Bank statement import"], "basis": "ai_interpretation", "source_ids": [],
             "confidence": "medium"},
        ],
        "differentiation_opportunities": [
            _item("Import statements automatically instead of asking owners to type entries.", "ai_interpretation", templates),
        ],
        "data_quality": {
            "evidence_level": "limited",
            "notes": ["Pricing for BookKeeper Pro and FlowCast was not found."],
        },
    }


# --- FoodTech: surplus food marketplace -------------------------------------------------------

FOOD_MARKET_REPORT = "https://reports.example/surplus-food-market"
FOOD_SURPLUSHUB_ABOUT = "https://surplushub.example/about"
FOOD_DIRECTORY = "https://directory.example/freshrescue-alternatives"
FOOD_SURVEY = "https://retail.example/waste-survey"
FOOD_NEWS = "https://news.example/foodtech-funding"
FOOD_INDIA_MARKET = "https://research.example/india-surplus-food"
FOOD_WASTE_MARKET = "https://insights.example/food-waste-market"
FOOD_SURPLUSHUB_PRICING = "https://surplushub.example/pricing"
FOOD_FRESHRESCUE_PRICING = "https://freshrescue.example/pricing"
FOOD_DONATION = "https://ngo.example/food-donation"
FOOD_BINLESS = "https://news.example/binless-launch"

FOOD_EXTRACTION = {
    "idea_title": "Surplus Food Marketplace",
    "problem": "Restaurants and grocery stores discard unsold food every night because there is no quick way to sell it before closing.",
    "solution": "A marketplace where shops list surplus food at a discount each evening and nearby shoppers collect it before closing time.",
    "target_customers": ["Restaurants and grocery stores in Indian cities", "Shoppers who want discounted food"],
    "industry": "Food & Beverage",
    "key_features": ["Evening surplus listings", "Automatic listing expiry", "Waste avoided dashboard"],
}

FOOD_SEARCH = bundle(
    section(
        LABEL_MARKET,
        result(FOOD_MARKET_REPORT,
               "The global surplus food marketplace was valued at USD 2.1 billion in 2024 as retailers cut waste.",
               "Surplus food marketplace market report", 0.9),
        answer="Surplus food marketplaces are growing as retailers cut waste.",
    ),
    section(
        LABEL_COMPETITORS,
        result(FOOD_SURPLUSHUB_ABOUT,
               "SurplusHub lets restaurants list unsold meals at a discount for collection before closing.",
               "SurplusHub", 0.9),
        result(FOOD_DIRECTORY,
               "FreshRescue alternatives include SurplusHub and WasteWise for surplus food collection.",
               "FreshRescue alternatives and competitors", 0.8),
    ),
    section(
        LABEL_DEMAND,
        result(FOOD_SURVEY,
               "Most grocery stores discard unsold food each night and want a faster way to sell it.",
               "Retail food waste survey", 0.7),
    ),
    section(
        LABEL_NEWS,
        result(FOOD_NEWS, "Investors backed surplus food startups in 2025.", "FoodTech funding roundup", 0.6),
    ),
)

FOOD_MARKET_SEARCH = _targeted(
    section(
        LABEL_IDEA_MARKET,
        result(FOOD_INDIA_MARKET,
               "The surplus food marketplace in India reached USD 95 million in 2024.",
               "Surplus food marketplace in India", 0.9),
    ),
    section(
        LABEL_CUSTOMER_MARKET,
        result(FOOD_WASTE_MARKET,
               "The global food waste management market was valued at USD 48 billion in 2024.",
               "Food waste management market", 0.8),
    ),
)

FOOD_COMPETITOR_SEARCH = _targeted(
    section(
        "Competitor: SurplusHub",
        result(FOOD_SURPLUSHUB_PRICING,
               "SurplusHub takes a 15 percent commission on each surplus order and charges shops no monthly fee.",
               "SurplusHub pricing", 0.9),
    ),
    section(
        "Competitor: FreshRescue",
        result(FOOD_FRESHRESCUE_PRICING,
               "FreshRescue charges shops INR 999 a month for unlimited surplus listings.",
               "FreshRescue pricing", 0.9),
    ),
    section("Competitor: WasteWise", error="No live results found for this query."),
    section(
        LABEL_ALTERNATIVES,
        result(FOOD_DONATION,
               "Food donation networks collect unsold food from shops and give it to shelters at no charge.",
               "Food donation networks", 0.8),
    ),
    section(
        LABEL_EMERGING,
        result(FOOD_BINLESS,
               "Binless, a new startup, launched dynamic evening discounting for grocery stores in 2026.",
               "Binless launches dynamic discounting", 0.7),
    ),
)


def food_market(ids: dict[str, str]) -> dict:
    report, india, waste = ids[FOOD_MARKET_REPORT], ids[FOOD_INDIA_MARKET], ids[FOOD_WASTE_MARKET]
    survey, hub = ids[FOOD_SURVEY], ids[FOOD_SURPLUSHUB_ABOUT]
    return {
        "industry_overview": {
            "summary": "Retailers are turning unsold stock into discounted evening sales instead of waste.",
            "market_category": "Surplus food marketplace",
            "developments": [
                _item("Retailers are cutting waste through surplus food marketplaces.", "sourced", report),
            ],
        },
        "market_demand": {
            "summary": "Shops discard unsold food nightly and want a faster way to sell it.",
            "demand_evidence": [
                _item("Most grocery stores discard unsold food each night and want a faster way to sell it.",
                      "sourced", survey),
            ],
            "customer_problems": [
                _item("Unsold food is discarded each night with no quick way to sell it.", "sourced", survey),
            ],
            "interest_signals": [
                _item("Shops already accept discounted collection before closing.", "ai_interpretation", hub),
            ],
        },
        "market_size": {
            "tam": {"value": "USD 2.1 billion", "status": "sourced", "source_ids": [report],
                    "note": "Global surplus food marketplace, 2024", "scope": "idea_market"},
            "sam": {"value": "USD 95 million", "status": "sourced", "source_ids": [india],
                    "note": "Surplus food marketplace in India, 2024", "scope": "idea_market"},
            "som": _unavailable("No figure for a single city was found"),
        },
        "broader_markets": [
            {"value": "USD 48 billion", "status": "sourced", "source_ids": [waste],
             "note": "Global food waste management market, 2024", "scope": "broader_market"},
        ],
        "trends": [
            {"trend": "Discounted evening collection of unsold stock", "category": "consumer", "basis": "sourced",
             "source_ids": [hub]},
        ],
        "segments": [
            {
                "name": "Neighbourhood grocery stores",
                "description": "Small grocers that throw away unsold stock at closing time.",
                "segmentation_basis": "business_type",
                "needs": ["Evening surplus listings"],
                "pain_points": [_item("Unsold food is discarded each night.", "sourced", survey)],
                "source_ids": [survey],
            },
            {
                "name": "Restaurants",
                "description": "Kitchens with prepared meals left at the end of service.",
                "segmentation_basis": "business_type",
                "needs": ["Automatic listing expiry"],
                "pain_points": [_item("Prepared meals cannot be held overnight.", "assumption")],
                "source_ids": [],
            },
        ],
        "priority_segment": {
            "segment_name": "Neighbourhood grocery stores",
            "rationale": "They discard unsold stock nightly and already want a faster way to sell it.",
            "risks": ["Donation networks collect the same stock at no charge"],
        },
        "opportunities": [
            _item("Show each shop how much waste it avoided.", "ai_interpretation", survey),
        ],
        "limitations": [
            _item("Surplus collection services already operate before closing.", "sourced", hub),
        ],
        "data_quality": {"evidence_level": "limited", "notes": ["No figure for a single city was found."]},
    }


def food_candidates(std: dict[str, str]) -> dict:
    return {
        "candidates": [
            {"name": "SurplusHub", "type": "direct", "source_ids": [std[FOOD_SURPLUSHUB_ABOUT], std[FOOD_DIRECTORY]],
             "basis": "sourced"},
            {"name": "FreshRescue", "type": "direct", "source_ids": [std[FOOD_DIRECTORY]], "basis": "sourced"},
            {"name": "WasteWise", "type": "indirect", "source_ids": [std[FOOD_DIRECTORY]], "basis": "sourced"},
        ]
    }


def food_analysis(ids: dict[str, str]) -> dict:
    about, directory = ids[FOOD_SURPLUSHUB_ABOUT], ids[FOOD_DIRECTORY]
    hub_price, fresh_price = ids[FOOD_SURPLUSHUB_PRICING], ids[FOOD_FRESHRESCUE_PRICING]
    donation, binless = ids[FOOD_DONATION], ids[FOOD_BINLESS]
    return {
        "competitors": [
            {
                "name": "SurplusHub", "type": "direct",
                "relevance_note": "Lists unsold meals at a discount for collection, the same job as this idea.",
                "website": "https://surplushub.example", "source_ids": [about, hub_price],
                "offering": "Surplus meal listings for collection before closing", "target_segment": "Restaurants",
                "key_features": ["Evening surplus listings", "Discounted collection"],
                "value_proposition": "No monthly fee for shops",
                "pricing_model": _price("15 percent commission per order", "sourced", hub_price),
                "strengths": [_item("Shops pay no monthly fee", "sourced", hub_price)],
                "weaknesses": [], "positioning": "Commission-only marketplace",
                "differentiation_vs_startup": "This idea adds automatic expiry and a waste dashboard.",
                "basis": "sourced",
            },
            {
                "name": "FreshRescue", "type": "direct",
                "relevance_note": "Sells unlimited surplus listings to the same shops.",
                "website": "https://freshrescue.example", "source_ids": [directory, fresh_price],
                "offering": "Unlimited surplus listings on subscription", "target_segment": "Shops",
                "key_features": ["Evening surplus listings"], "value_proposition": None,
                "pricing_model": _price("INR 999 a month", "sourced", fresh_price),
                "strengths": [], "weaknesses": [], "positioning": None,
                "differentiation_vs_startup": "This idea charges no monthly fee.", "basis": "sourced",
            },
            {
                "name": "WasteWise", "type": "indirect",
                "relevance_note": "Listed beside the direct rivals for surplus food collection.",
                "website": None, "source_ids": [directory], "offering": "Surplus food collection",
                "target_segment": None, "key_features": ["Waste avoided dashboard"], "value_proposition": None,
                "pricing_model": _unavailable(), "strengths": [], "weaknesses": [], "positioning": None,
                "differentiation_vs_startup": None, "basis": "sourced",
            },
            {
                "name": "Food donation networks", "type": "indirect",
                "relevance_note": "Collect the same unsold stock at no charge, so they are a substitute.",
                "website": None, "source_ids": [donation],
                "offering": "Collection of unsold food for shelters", "target_segment": "Shelters",
                "key_features": ["Discounted collection"], "value_proposition": "No charge to shops",
                # Worded as the cited snippet words it, so the price check finds it.
                "pricing_model": _price("No charge to shops", "sourced", donation),
                "strengths": [_item("Shops pay nothing", "sourced", donation)], "weaknesses": [],
                "positioning": None,
                "differentiation_vs_startup": "This idea returns revenue to the shop instead of donating stock.",
                "basis": "sourced",
            },
            {
                "name": "Binless", "type": "emerging",
                "relevance_note": "A new startup discounting grocery stock in the evening.",
                "website": None, "source_ids": [binless], "offering": "Dynamic evening discounting",
                "target_segment": "Grocery stores", "key_features": ["Evening surplus listings"],
                "value_proposition": None, "pricing_model": _unavailable(), "strengths": [], "weaknesses": [],
                "positioning": None, "differentiation_vs_startup": None, "basis": "sourced",
            },
        ],
        "comparison": {
            "features": ["Evening surplus listings", "Automatic listing expiry", "Waste avoided dashboard"],
            "rows": [
                {"competitor": "SurplusHub", "cells": [
                    {"feature": "Evening surplus listings", "status": "evidence_found", "source_ids": [about]},
                    {"feature": "Automatic listing expiry", "status": "unclear", "source_ids": []},
                ]},
                {"competitor": "FreshRescue", "cells": [
                    {"feature": "Evening surplus listings", "status": "evidence_found", "source_ids": [fresh_price]},
                ]},
                {"competitor": "WasteWise", "cells": [
                    {"feature": "Waste avoided dashboard", "status": "unclear", "source_ids": []},
                ]},
                {"competitor": "Food donation networks", "cells": [
                    {"feature": "Evening surplus listings", "status": "no_evidence_found", "source_ids": [donation]},
                ]},
                {"competitor": "Binless", "cells": [
                    {"feature": "Evening surplus listings", "status": "evidence_found", "source_ids": [binless]},
                ]},
            ],
        },
        "market_gaps": [
            {"description": "No competitor in the results expires a listing automatically when the food is no longer safe.",
             "related_features": ["Automatic listing expiry"], "basis": "ai_interpretation", "source_ids": [],
             "confidence": "medium"},
        ],
        "differentiation_opportunities": [
            _item("Expire listings automatically so nothing unsafe is offered.", "ai_interpretation", about),
        ],
        "data_quality": {"evidence_level": "limited", "notes": ["Pricing for WasteWise and Binless was not found."]},
    }


# --- assembling the domains -------------------------------------------------------------------


@dataclass(frozen=True)
class Domain:
    """One domain's complete fake pipeline input, plus the ids its replies cite."""

    name: str
    idea_file: str
    industry: str
    market_category: str
    submission: IdeaSubmission
    idea: ExtractedIdea
    extraction_reply: str
    search: SearchBundle
    market_search: SearchBundle
    competitor_search: SearchBundle
    market_reply: str
    candidate_reply: str
    analysis_reply: str
    market_ids: dict[str, str]
    competitor_ids: dict[str, str]

    @property
    def llm_replies(self) -> tuple[str, str, str]:
        return self.extraction_reply, self.market_reply, self.analysis_reply


def _build(name, idea_file, extraction, search, market_search, competitor_search, market, candidates, analysis) -> Domain:
    submission = submission_from(idea_file)
    idea = ExtractedIdea(**extraction)
    standard = build_evidence(search)
    std_ids = _url_ids(standard)

    candidate_payload = candidates(std_ids)
    kept, _ = check_candidates(
        CandidateList(**candidate_payload).candidates, standard, founder_text(submission)
    )
    competitor_items = competitor_evidence(search, competitor_search, kept)
    market_items = market_evidence(search, market_search, idea)
    market_ids, competitor_ids = _url_ids(market_items), _url_ids(competitor_items)

    return Domain(
        name=name,
        idea_file=idea_file,
        industry=submission.industry,
        market_category=market(market_ids)["industry_overview"]["market_category"],
        submission=submission,
        idea=idea,
        extraction_reply=json.dumps(extraction),
        search=search,
        market_search=market_search,
        competitor_search=competitor_search,
        market_reply=json.dumps(market(market_ids)),
        candidate_reply=json.dumps(candidate_payload),
        analysis_reply=json.dumps(analysis(competitor_ids)),
        market_ids=market_ids,
        competitor_ids=competitor_ids,
    )


AGRITECH = _build(
    "agritech", "agritech.json", VALID_EXTRACTION, PIPELINE_SEARCH, NO_MARKET_SIZE_RESULTS, COMPETITOR_TARGETED,
    lambda ids: PIPELINE_MARKET_REPLY, agri_candidates, agri_analysis,
)
FINTECH = _build(
    "fintech_cashflow", "fintech_cashflow.json", FIN_EXTRACTION, FIN_SEARCH, FIN_MARKET_SEARCH,
    FIN_COMPETITOR_SEARCH, fin_market, fin_candidates, fin_analysis,
)
FOODTECH = _build(
    "foodtech_surplus", "foodtech_surplus.json", FOOD_EXTRACTION, FOOD_SEARCH, FOOD_MARKET_SEARCH,
    FOOD_COMPETITOR_SEARCH, food_market, food_candidates, food_analysis,
)

DOMAINS = (AGRITECH, FINTECH, FOODTECH)
DOMAIN_IDS = [domain.name for domain in DOMAINS]
# Section 10.1's three Task 4 domains, by industry.
REQUIRED_INDUSTRIES = {"Agriculture / AgriTech", "Finance / FinTech", "Food & Beverage"}


def all_urls(domain: Domain) -> set[str]:
    """Every URL the domain's searches returned, for checking that no other URL appears."""
    return {
        item.url
        for search in (domain.search, domain.market_search, domain.competitor_search)
        for section_item in search.sections
        for item in section_item.results
    }
