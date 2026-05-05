"""
Morgan Stanley -- AI Initiatives Agentic Reporting Platform
============================================================
Prototype for the Technology COO transformation team.

Reimagines the monthly AI reporting process by replacing manual spreadsheet
stitching + static slides with an agentic pipeline:

    Fragmented data sources  →  Agents  →  Live, queryable, decision-ready briefing

Run:
    streamlit run app.py
"""
import os
import time
from dataclasses import asdict
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

from agents.orchestrator import Orchestrator
from agents.analyst import risk_bucket
from agents.llm_client import get_client
from agents.logger import get_memory_log
from agents import exporter


# ===========================================================================
# Page config + styles
# ===========================================================================
st.set_page_config(
    page_title="MS AI Initiatives -- Agentic Reporting",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Morgan Stanley-ish colors (without using their actual brand assets)
MS_BLUE = "#003D6E"
MS_LIGHT_BLUE = "#0077B5"
MS_ACCENT = "#E87722"

st.markdown(f"""
<style>
    /* ----- Global tightening ------------------------------------------- */
    /* Remove Streamlit's default top padding (was ~6rem on first load) */
    .main .block-container {{
        padding-top: 1.2rem !important;
        padding-bottom: 2rem !important;
        max-width: 1400px;
    }}
    /* Headings: tighter top margin */
    h1 {{ color: {MS_BLUE}; font-weight: 700; margin-top: 0 !important; margin-bottom: 0.3rem !important; }}
    h2, h3 {{ color: {MS_BLUE}; margin-top: 0.6rem !important; margin-bottom: 0.3rem !important; }}
    h4, h5 {{ margin-top: 0.4rem !important; margin-bottom: 0.2rem !important; }}
    /* Streamlit's default <hr> has huge 1rem margins — tighten to 0.5rem */
    hr {{ margin: 0.6rem 0 !important; }}
    /* Subheaders */
    [data-testid="stHeader"] {{ background: transparent; }}
    /* st.subheader generates h2/h3 — already tightened above */

    /* ----- Custom components ------------------------------------------- */
    .stMetric {{
        background-color: #f7f9fc;
        padding: 12px 14px;
        border-radius: 8px;
        border-left: 4px solid {MS_BLUE};
        /* Force all KPI cards in the same row to identical height */
        min-height: 96px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }}
    /* Metric label tighter */
    [data-testid="stMetricLabel"] {{ font-size: 12px; }}
    [data-testid="stMetricValue"] {{ font-size: 22px; line-height: 1.2; }}
    /* Reserve consistent space for delta even when absent */
    [data-testid="stMetricDelta"] {{ font-size: 12px; min-height: 18px; }}

    .agent-card {{
        background-color: #f0f4f8;
        padding: 10px 14px;
        border-radius: 6px;
        margin-bottom: 6px;
        border-left: 3px solid {MS_LIGHT_BLUE};
    }}
    .escalation-card {{
        background-color: #fff8f0;
        padding: 14px;
        border-radius: 8px;
        margin-bottom: 10px;
        border-left: 4px solid {MS_ACCENT};
    }}
    .source-pill {{
        display: inline-block;
        background-color: #e8f0f8;
        color: {MS_BLUE};
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 11px;
        margin: 3px 3px 3px 0;
    }}
    .risk-critical {{ color: #c62828; font-weight: 600; }}
    .risk-at-risk  {{ color: #ef6c00; font-weight: 600; }}
    .risk-watch    {{ color: #f9a825; font-weight: 600; }}
    .risk-healthy  {{ color: #2e7d32; font-weight: 600; }}

    /* Caption: tighter */
    [data-testid="stCaptionContainer"] {{ margin-top: -2px; margin-bottom: 4px; }}
</style>
""", unsafe_allow_html=True)


# ===========================================================================
# Cached pipeline run
# ===========================================================================
@st.cache_resource
def run_pipeline(generate_briefing: bool, generate_narratives: bool):
    return Orchestrator(
        generate_briefing=generate_briefing,
        generate_narratives=generate_narratives,
    ).run()


@st.cache_resource
def get_orchestrator():
    return Orchestrator(generate_briefing=False, generate_narratives=False)


@st.cache_resource
def _chat_store() -> dict:
    """
    Server-level chat-history container. Survives page reloads (which wipe
    st.session_state) -- needed so the user's Q&A history persists when they
    click a citation chip and the browser navigates to ?goto=ID.

    Returns a single mutable dict so callers can append/clear in-place and
    have changes visible on the next rerun.
    """
    return {"history": [], "pending": None}


# ---------------------------------------------------------------------------
# Small labelers for the drill-down metric cards
# ---------------------------------------------------------------------------
def _kpi_label(pct: int) -> str:
    if pct >= 100: return "Exceeding target"
    if pct >= 80:  return "On track"
    if pct >= 50:  return "Trailing"
    if pct >= 30:  return "Significantly behind"
    return "Severely underperforming"


def _budget_label(util_pct: float) -> str:
    if util_pct <= 90:  return "Healthy"
    if util_pct <= 105: return "On plan"
    if util_pct <= 120: return "Over budget"
    return "Severe overrun"


def html(s: str) -> str:
    """
    Streamlit's markdown renderer treats lines indented 4+ spaces as a code block,
    which causes raw HTML to be displayed verbatim instead of rendered.
    This helper strips the common leading indent + collapses blank lines so any
    triple-quoted HTML block can be passed safely to st.markdown(..., unsafe_allow_html=True).
    """
    import textwrap
    return textwrap.dedent(s).strip()


# ===========================================================================
# Header
# ===========================================================================

col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    st.markdown(html(f"""
        <div style='display:flex; align-items:center; gap:12px; margin-bottom:4px;'>
            <div style='background:{MS_BLUE}; color:white; padding:6px 12px; border-radius:4px; font-weight:700; letter-spacing:0.5px; font-size:13px;'>
                DEMO
            </div>
            <div style='color:#666; font-size:13px;'>Technology COO • Transformation Team</div>
        </div>
        <div style='font-size:26px; font-weight:700; color:{MS_BLUE}; line-height:1.15; margin:0 0 2px 0;'>
            AI Initiatives — Agentic Reporting Platform
        </div>
        <div style='font-size:12px; color:#888; margin:0 0 2px 0;'>
            Prototype submission by <strong>Sean Guan</strong> · 48-hour interview deliverable
        </div>
    """), unsafe_allow_html=True)

with col_h2:
    client = get_client()
    if client.backend == "anthropic":
        st.markdown(f"<div style='text-align:right; padding-top:12px; color:#2e7d32; font-weight:600; font-size:13px;'>🟢 Live (Anthropic API)</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div style='text-align:right; padding-top:12px; color:#888; font-size:13px;'>⚪ Mock LLM (deterministic)</div>", unsafe_allow_html=True)
        st.caption(f"💡 {client.status_message}")

st.markdown("<div style='margin-bottom:6px;'></div>", unsafe_allow_html=True)


# ===========================================================================
# Sidebar
# ===========================================================================
with st.sidebar:
    st.markdown(f"<h3 style='color:{MS_BLUE}'>Pipeline Controls</h3>", unsafe_allow_html=True)

    gen_briefing = st.checkbox(
        "Generate executive briefing",
        value=True,
        help="Calls the Briefing Agent. Disable to run without LLM narration.",
    )
    gen_narratives = st.checkbox(
        "Generate accountability narrative",
        value=True,
    )

    st.markdown("---")
    st.markdown(f"<h3 style='color:{MS_BLUE}'>Source Systems</h3>", unsafe_allow_html=True)
    st.markdown(
        "<div class='source-pill'>WM Tech Jira (JSON)</div>"
        "<div class='source-pill'>IB Tech Quarterly Tracker (CSV)</div>"
        "<div class='source-pill'>AM Tech SharePoint (CSV)</div>"
        "<div class='source-pill'>GF Tech Budget Tracker (CSV)</div>"
        "<div class='source-pill'>Approvals Log (JSON)</div>",
        unsafe_allow_html=True,
    )
    st.caption(
        "All five are simulated to mirror the fragmented landscape the transformation team "
        "deals with today. Each source uses different schemas, status vocabularies, and date formats."
    )

    st.markdown("---")
    st.markdown(f"<h3 style='color:{MS_BLUE}'>Agents</h3>", unsafe_allow_html=True)
    st.markdown(
        "**Data Aggregator**  —  unifies fragmented sources  \n"
        "**Risk Analyst**  —  scores + explains  \n"
        "**Accountability**  —  tracks sign-offs, drafts escalations  \n"
        "**Briefing**  —  generates executive narrative  \n"
        "**Q&A**  —  answers ad-hoc portfolio questions"
    )

    st.markdown("---")
    if st.button("🔄 Re-run pipeline"):
        st.cache_resource.clear()
        st.rerun()


# ===========================================================================
# Run pipeline (with progress) + pre-warm caches
# ===========================================================================
# Strategy:
#   - The actual pipeline work is wrapped in @st.cache_resource, which lives at
#     the Streamlit *server* level — it survives full page reloads (e.g. when a
#     citation chip click reloads the page).
#   - On a true cold start, run_pipeline() runs the full pipeline (~0.02s with
#     mock LLM, longer with real LLM) and we show the detailed progress UI.
#   - On any subsequent reload (citation click, refresh), run_pipeline() returns
#     instantly from cache and the progress UI flashes through in <100ms.
#   - We do NOT duplicate the pipeline work inline. Single source of truth.

import time as _t
_t_start = _t.time()

# Try to fetch from cache first to detect cold start vs reload
_t_probe = _t.time()
try:
    _state_from_cache = run_pipeline(gen_briefing, gen_narratives)
    _is_cold_start = (_t.time() - _t_probe) > 0.3
except Exception:
    _state_from_cache = None
    _is_cold_start = True

if _is_cold_start and _state_from_cache is None:
    # Cache failed to populate — show full boot UI and run pipeline fresh
    progress = st.progress(0, text="Starting up...")
    status_box = st.empty()

    def _step(pct: int, label: str, detail: str = ""):
        progress.progress(pct, text=label)
        sub = f"<div style='color:#888; font-size:12px; padding:4px 0 0 4px;'>{detail}</div>" if detail else ""
        status_box.markdown(
            f"<div style='font-size:13px; color:#003D6E; padding:6px 0 0 4px;'>"
            f"⚙️ {label}</div>{sub}",
            unsafe_allow_html=True,
        )

    _step(20, "Constructing agent pipeline", "5 specialized agents + 1 orchestrator")
    _step(40, "Aggregator → Loading 4 fragmented sources", "WM Jira · IB Excel · AM SharePoint · GF Budget CSV")
    _step(60, "Risk Analyst → 7-factor deterministic scoring", "status · budget · KPI/burn · approval · staleness · severity")
    _step(80, "Accountability → Mapping approval chains + drafting escalations", "")
    _step(95, "Briefing Agent → Synthesizing executive briefing", "Structured JSON + markdown export")
    state = run_pipeline(gen_briefing, gen_narratives)
    _ = get_orchestrator()
    _step(100, f"Ready · initialized in {_t.time() - _t_start:.1f}s",
          f"{len(state.initiatives)} initiatives · ${sum(i.budget_approved for i in state.initiatives)/1e6:.1f}M approved")
    progress.empty()
    status_box.empty()

elif _is_cold_start:
    # Cold start with successful cache fill — show the detailed step-by-step
    # progress UI for visual effect (the work itself was already done above)
    progress = st.progress(0, text="Starting up...")
    status_box = st.empty()

    def _step(pct: int, label: str, detail: str = ""):
        progress.progress(pct, text=label)
        sub = f"<div style='color:#888; font-size:12px; padding:4px 0 0 4px;'>{detail}</div>" if detail else ""
        status_box.markdown(
            f"<div style='font-size:13px; color:#003D6E; padding:6px 0 0 4px;'>"
            f"⚙️ {label}</div>{sub}",
            unsafe_allow_html=True,
        )

    state = _state_from_cache
    critical_n = sum(1 for i in state.initiatives if i.risk_score >= 76)
    at_risk_n  = sum(1 for i in state.initiatives if 51 <= i.risk_score < 76)

    _step(8,  "Constructing agent pipeline", "5 specialized agents + 1 orchestrator")
    _step(15, "Aggregator → WM Tech Jira (JSON)", "Schema: Jira-style ticket export")
    _step(22, "Aggregator → IB Tech Quarterly Tracker (Excel/CSV)", "Schema: RAG status + budget + KPI")
    _step(28, "Aggregator → AM Tech SharePoint (CSV)", "Schema: phase + % complete + budget")
    _step(34, "Aggregator → GF Tech Budget Tracker (CSV)", "Schema: approved/spend + headcount + milestones")
    _step(40, "Aggregator → Normalizing 3 status vocabularies", "Green/Amber/Red ↔ On-Track/At-Risk/Off-Track ↔ In-Progress/Blocked/Done")
    _step(46, "Aggregator → Merging Approvals Log", f"sign-off records across {len(state.initiatives)} initiatives")
    _step(54, "Risk Analyst → Computing 7-factor scores", "status · budget · KPI/burn · approval · staleness · KPI under · severity")
    _step(60, "Risk Analyst → Classification complete", f"{critical_n} Critical · {at_risk_n} At Risk")
    _step(66, "Accountability → Mapping approval chains", "Validator + sponsor sign-off graph")
    _step(72, "Accountability → Drafting COO escalations", "Detecting bottlenecks + writing review-ready emails")
    _step(78, "Accountability → Escalations ready", f"{len(state.escalations)} escalation(s) for COO review")

    if gen_narratives:
        _step(84, "Accountability → Synthesizing narrative", "Calling LLM (or mock) for headline + actions")
    if gen_briefing:
        _step(91, "Briefing Agent → Synthesizing executive briefing", "Structured JSON + markdown export")

    _step(97, "Caching pipeline state", "Single source of truth for the rest of the session")
    _ = get_orchestrator()    # pre-warm QA (cached, instant)

    elapsed = _t.time() - _t_start
    _step(100, f"Ready · initialized in {elapsed:.1f}s",
          f"{len(state.initiatives)} initiatives · ${sum(i.budget_approved for i in state.initiatives)/1e6:.1f}M approved · {critical_n} Critical · {at_risk_n} At Risk")

    progress.empty()
    status_box.empty()

else:
    # CACHE HIT path: this happens after a page reload (e.g. citation click).
    # Pipeline returned instantly. Skip the visible boot screen.
    state = _state_from_cache
    _ = get_orchestrator()    # also instant from cache

# Stash for tab rendering. session_state.first_run is no longer used as a gate.
st.session_state.cached_state = state
inits = state.initiatives

# ===========================================================================
# KPI strip
# ===========================================================================
total = len(inits)
on_track = sum(1 for i in inits if i.status_normalized == "On Track")
at_risk = sum(1 for i in inits if i.risk_score >= 51)
fully_approved = state.signoff_summary.get("fully_approved", 0)
total_budget = sum(i.budget_approved for i in inits)
total_spend = sum(i.budget_spent for i in inits)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Active Initiatives", total)
c2.metric("On Track", on_track, f"{on_track/total*100:.0f}%")
c3.metric("At Risk / Critical", at_risk, f"{at_risk/total*100:.0f}%", delta_color="inverse")
c4.metric("Fully Approved", f"{fully_approved}/{total}")
c5.metric("FY26 Spend / Approved", f"${total_spend/1e6:.1f}M / ${total_budget/1e6:.1f}M")

st.markdown("<div style='margin-bottom:8px;'></div>", unsafe_allow_html=True)


# ===========================================================================
# Persistent tab navigation
# ===========================================================================
# Using st.radio() instead of st.tabs() because st.tabs() doesn't persist
# the active tab across reruns. When a long backend call (first chat
# message, first cache miss) triggers a rerun, st.tabs() resets to tab 0,
# which breaks the demo flow. Radio with session_state preserves selection.
TAB_LABELS = [
    "📊 Overview",
    "📝 Briefing",
    "📋 Initiatives",
    "✅ Accountability",
    "💬 Ask Portfolio",
    "🔍 Activity",
    "📜 Logs",
    "💰 ROI",
]

# Inject CSS to style the radio horizontally and tab-like
st.markdown("""
<style>
    /* Hide the radio's internal label */
    div[data-testid="stRadio"] > label { display: none; }
    /* Lay out tabs in a single row that doesn't wrap */
    div[data-testid="stRadio"] > div {
        flex-direction: row;
        gap: 2px;
        flex-wrap: nowrap !important;
        overflow-x: auto;
        white-space: nowrap;
    }
    /* Each option as a tab pill -- compact for 8 tabs */
    div[data-testid="stRadio"] label[data-baseweb="radio"] {
        background: #f7f9fc;
        padding: 7px 11px;
        border-radius: 6px 6px 0 0;
        border: 1px solid #e0e4ea;
        border-bottom: 2px solid transparent;
        cursor: pointer;
        margin-bottom: 0 !important;
        transition: all 0.15s;
        white-space: nowrap;
        flex-shrink: 0;
    }
    /* Tighten the label text inside */
    div[data-testid="stRadio"] label[data-baseweb="radio"] > div:last-child p {
        font-size: 12.5px !important;
        margin: 0 !important;
    }
    div[data-testid="stRadio"] label[data-baseweb="radio"]:hover {
        background: #eef2f8;
    }
    /* Active tab — has aria-checked="true" on the inner input */
    div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input[aria-checked="true"]) {
        background: white !important;
        border-bottom: 2px solid #003D6E !important;
        font-weight: 600;
    }
    /* Hide the radio circle */
    div[data-testid="stRadio"] label[data-baseweb="radio"] > div:first-child { display: none; }
    /* Tighter spacing under tabs */
    div[data-testid="stRadio"] { margin-bottom: 6px; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Handle deep-link from Q&A citation chips
# ---------------------------------------------------------------------------
# Citation chips in the Q&A tab use ?goto=<INITIATIVE_ID> to link directly
# to the drill-down. We process this BEFORE rendering tabs so the active_tab
# and init_picker session_state values are set correctly on this run.
_goto_id = st.query_params.get("goto")
if _goto_id:
    matching = next((i for i in inits if i.id == _goto_id), None)
    if matching:
        st.session_state.active_tab = TAB_LABELS[2]    # Initiatives tab
        st.session_state.init_picker = f"[{matching.id}] {matching.name}"
        st.session_state.scroll_to_drill = True        # auto-scroll to drill-down
    # Clear so the link only fires once, then rerun for clean widget state
    st.query_params.clear()
    st.rerun()

active_tab = st.radio(
    "Navigation",
    options=TAB_LABELS,
    index=TAB_LABELS.index(st.session_state.get("active_tab", TAB_LABELS[0]))
        if st.session_state.get("active_tab") in TAB_LABELS else 0,
    key="active_tab",
    label_visibility="collapsed",
    horizontal=True,
)


# ---------------------------------------------------------------------------
# Tab 1: Overview
# ---------------------------------------------------------------------------
if active_tab == TAB_LABELS[0]:
    df = pd.DataFrame([asdict(i) for i in inits])
    df["risk_bucket"] = df["risk_score"].apply(risk_bucket)

    col_a, col_b = st.columns([1, 1])

    with col_a:
        st.subheader("Risk distribution by Business Unit")
        bucket_order = ["Healthy", "Watch", "At Risk", "Critical"]
        color_map = {"Healthy": "#2e7d32", "Watch": "#f9a825", "At Risk": "#ef6c00", "Critical": "#c62828"}
        bu_risk = df.groupby(["business_unit_full", "risk_bucket"]).size().reset_index(name="count")
        fig = px.bar(
            bu_risk,
            x="business_unit_full",
            y="count",
            color="risk_bucket",
            category_orders={"risk_bucket": bucket_order},
            color_discrete_map=color_map,
            labels={"business_unit_full": "Business Unit", "count": "Initiatives"},
        )
        fig.update_layout(
            legend_title="",
            xaxis_title="",
            yaxis_title="Initiatives",
            height=380,
            margin=dict(l=0, r=0, t=10, b=0),
        )
        st.plotly_chart(fig, width="stretch")

    with col_b:
        st.subheader("Budget burn vs KPI progress")
        budget_df = df[df["budget_approved"] > 0].copy()
        if not budget_df.empty:
            fig = px.scatter(
                budget_df,
                x="budget_utilization_pct",
                y="kpi_actual_pct",
                color="risk_bucket",
                size="budget_approved",
                hover_name="name",
                hover_data={"owner": True, "business_unit_full": True, "budget_utilization_pct": ":.0f", "kpi_actual_pct": True},
                category_orders={"risk_bucket": bucket_order},
                color_discrete_map=color_map,
                labels={"budget_utilization_pct": "Budget utilization (%)", "kpi_actual_pct": "KPI achievement (%)"},
            )
            # Diagonal reference -- "ideal" is on or above this line
            fig.add_shape(
                type="line", x0=0, y0=0, x1=120, y1=120,
                line=dict(color="gray", dash="dash", width=1),
            )
            fig.add_annotation(x=110, y=115, text="ideal: KPI ≥ spend", showarrow=False, font=dict(size=10, color="gray"))
            fig.update_layout(height=380, margin=dict(l=0, r=0, t=10, b=0), legend_title="")
            st.plotly_chart(fig, width="stretch")

    # Top-risk initiatives strip
    st.subheader("🔥 Top 5 highest-risk initiatives")
    top = sorted(inits, key=lambda x: x.risk_score, reverse=True)[:5]
    cols = st.columns(5)
    for col, i in zip(cols, top):
        bucket = risk_bucket(i.risk_score)
        css_class = f"risk-{bucket.lower().replace(' ', '-')}"
        col.markdown(html(f"""
            <div style='background:#fafbfc; padding:14px; border-radius:8px; border-left:4px solid {color_map[bucket]}; min-height:140px;'>
                <div style='font-size:11px; color:#666;'>{i.business_unit}</div>
                <div style='font-weight:600; font-size:14px; margin:4px 0;'>{i.name}</div>
                <div class='{css_class}' style='font-size:13px;'>{bucket} ({i.risk_score:.0f})</div>
                <div style='font-size:11px; color:#666; margin-top:6px;'>{i.owner}</div>
            </div>
        """), unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Tab 2: Executive Briefing
# ---------------------------------------------------------------------------
if active_tab == TAB_LABELS[1]:
    st.subheader("Monthly Executive Briefing")
    st.caption("Auto-generated from the unified portfolio state. This replaces the static slide deck.")

    sb = state.structured_briefing or {}

    if not sb:
        st.info("Briefing generation is disabled. Enable it in the sidebar.")
    elif sb.get("_raw_fallback"):
        # JSON parsing failed -- show the raw output and a warning
        st.warning("⚠️ The briefing agent returned non-JSON content. Falling back to raw display.")
        st.markdown(sb["_raw_fallback"])
    else:
        # ---- 1. HEADLINE CARD --------------------------------------------------
        st.markdown(html(f"""
            <div style='background:linear-gradient(135deg, {MS_BLUE} 0%, #002a4d 100%);
                        color:white; padding:24px 28px; border-radius:10px;
                        margin-bottom:18px; box-shadow:0 2px 8px rgba(0,61,110,0.15);'>
                <div style='font-size:11px; opacity:0.75; text-transform:uppercase;
                            letter-spacing:1.5px; margin-bottom:8px;'>
                    📌 Headline · {pd.Timestamp.now().strftime('%B %Y')}
                </div>
                <div style='font-size:17px; line-height:1.55; font-weight:400;'>
                    {sb.get("headline", "")}
                </div>
            </div>
        """), unsafe_allow_html=True)

        # ---- 2. PORTFOLIO HEALTH STRIP ----------------------------------------
        ph = sb.get("portfolio_health", {})
        ph_cols = st.columns(4)
        bucket_meta = [
            ("Critical", ph.get("Critical", 0), "#c62828", "🔴"),
            ("At Risk",  ph.get("At Risk", 0),  "#ef6c00", "🟠"),
            ("Watch",    ph.get("Watch", 0),    "#f9a825", "🟡"),
            ("Healthy",  ph.get("Healthy", 0),  "#2e7d32", "🟢"),
        ]
        for col, (label, count, color, emoji) in zip(ph_cols, bucket_meta):
            col.markdown(html(f"""
                <div style='background:white; border:1px solid #e0e4ea; border-left:4px solid {color};
                            padding:12px 14px; border-radius:6px; text-align:center;'>
                    <div style='font-size:11px; color:#666; text-transform:uppercase;
                                letter-spacing:0.5px;'>{emoji} {label}</div>
                    <div style='font-size:30px; font-weight:700; color:{color}; margin-top:2px;'>{count}</div>
                </div>
            """), unsafe_allow_html=True)

        st.markdown("<div style='margin-bottom:18px;'></div>", unsafe_allow_html=True)

        # ---- 3. WHAT'S WORKING / NOT WORKING (side-by-side tables) ------------
        col_w, col_nw = st.columns(2)

        with col_w:
            st.markdown(
                f"<h4 style='color:#2e7d32; margin-bottom:8px;'>✅ What's Working</h4>",
                unsafe_allow_html=True,
            )
            working = sb.get("working", [])
            if working:
                wdf = pd.DataFrame([
                    {
                        "Initiative": w.get("initiative", ""),
                        "BU": w.get("bu", ""),
                        "Owner": w.get("owner", ""),
                        "Why it's working": w.get("why", ""),
                    }
                    for w in working
                ])
                st.dataframe(
                    wdf,
                    hide_index=True,
                    width="stretch",
                    column_config={
                        "Initiative": st.column_config.TextColumn(width="medium"),
                        "BU":         st.column_config.TextColumn(width="small"),
                        "Owner":      st.column_config.TextColumn(width="small"),
                        "Why it's working": st.column_config.TextColumn(width="large"),
                    },
                )
            else:
                st.caption("No items.")

        with col_nw:
            st.markdown(
                f"<h4 style='color:#c62828; margin-bottom:8px;'>🔴 What's Not Working</h4>",
                unsafe_allow_html=True,
            )
            not_working = sb.get("not_working", [])
            if not_working:
                nwdf = pd.DataFrame([
                    {
                        "Initiative": nw.get("initiative", ""),
                        "BU": nw.get("bu", ""),
                        "Owner": nw.get("owner", ""),
                        "Severity": nw.get("severity", ""),
                        "Issue": nw.get("issue", ""),
                    }
                    for nw in not_working
                ])
                st.dataframe(
                    nwdf,
                    hide_index=True,
                    width="stretch",
                    column_config={
                        "Initiative": st.column_config.TextColumn(width="medium"),
                        "BU":         st.column_config.TextColumn(width="small"),
                        "Owner":      st.column_config.TextColumn(width="small"),
                        "Severity":   st.column_config.TextColumn(width="small"),
                        "Issue":      st.column_config.TextColumn(width="large"),
                    },
                )
            else:
                st.caption("No items.")

        st.markdown("<div style='margin-bottom:8px;'></div>", unsafe_allow_html=True)

        # ---- 4. ACCOUNTABILITY TABLE ------------------------------------------
        st.markdown(
            f"<h4 style='color:{MS_BLUE}; margin-bottom:8px;'>👥 Who's Accountable for the Gaps</h4>",
            unsafe_allow_html=True,
        )
        acc = sb.get("accountability", [])
        if acc:
            adf = pd.DataFrame([
                {
                    "Person": a.get("person", ""),
                    "Role": a.get("role", ""),
                    "Owns": a.get("owns", ""),
                    "Action needed this week": a.get("action_needed", ""),
                }
                for a in acc
            ])
            st.dataframe(
                adf,
                hide_index=True,
                width="stretch",
                column_config={
                    "Person": st.column_config.TextColumn(width="medium"),
                    "Role":   st.column_config.TextColumn(width="small"),
                    "Owns":   st.column_config.TextColumn(width="medium"),
                    "Action needed this week": st.column_config.TextColumn(width="large"),
                },
            )
        else:
            st.caption("No accountability items flagged.")

        st.markdown("<div style='margin-bottom:8px;'></div>", unsafe_allow_html=True)

        # ---- 5. DECISIONS (numbered cards with Approve/Decline buttons) -------
        st.markdown(
            f"<h4 style='color:{MS_BLUE}; margin-bottom:8px;'>🎯 Recommended Decisions for This Meeting</h4>",
            unsafe_allow_html=True,
        )
        st.caption("Each item is decision-shaped — leadership can approve or reject in this meeting, not 'discussed at next review'.")

        decisions = sb.get("decisions", [])
        for d in decisions:
            d_id    = d.get("id", "—")
            d_text  = d.get("decision", "")
            d_why   = d.get("rationale", "")
            d_owner = d.get("owner", "")
            st.markdown(html(f"""
                <div style='background:#f7f9fc; border:1px solid #e0e4ea;
                            border-left:4px solid {MS_ACCENT};
                            padding:14px 18px; border-radius:6px; margin-bottom:10px;'>
                    <div style='display:flex; gap:12px; align-items:flex-start;'>
                        <div style='background:{MS_ACCENT}; color:white; min-width:32px; height:32px;
                                    border-radius:50%; display:flex; align-items:center;
                                    justify-content:center; font-weight:700; font-size:14px;'>
                            {d_id}
                        </div>
                        <div style='flex:1;'>
                            <div style='font-weight:600; font-size:14px; color:#222; margin-bottom:6px;'>
                                {d_text}
                            </div>
                            <div style='font-size:12px; color:#555; margin-bottom:4px;'>
                                <strong style='color:{MS_BLUE};'>Why now:</strong> {d_why}
                            </div>
                            <div style='font-size:12px; color:#555;'>
                                <strong style='color:{MS_BLUE};'>Owner:</strong> {d_owner}
                            </div>
                        </div>
                    </div>
                </div>
            """), unsafe_allow_html=True)
            cda, cdb, cdc = st.columns([1, 1, 6])
            cda.button("✅ Approve", key=f"approve_{d_id}", help="In production: logs decision, notifies owner")
            cdb.button("❌ Decline", key=f"decline_{d_id}")

    st.markdown("---")
    st.markdown("**Export this briefing**")
    st.caption("Send to leadership in their preferred format. The same content, regenerated each month.")

    timestamp = pd.Timestamp.now().strftime("%Y_%m_%d")
    briefing_md = state.executive_briefing or "Briefing generation disabled."

    formats = exporter.available_formats()
    cols = st.columns(4)

    cols[0].download_button(
        "📝 Markdown",
        data=briefing_md,
        file_name=f"ai_briefing_{timestamp}.md",
        mime="text/markdown",
        width="stretch",
    )
    cols[1].download_button(
        "🌐 HTML",
        data=exporter.export_html(briefing_md, candidate_name="Sean Guan"),
        file_name=f"ai_briefing_{timestamp}.html",
        mime="text/html",
        width="stretch",
    )
    if formats["docx"][2]:
        cols[2].download_button(
            "📄 Word (.docx)",
            data=exporter.export_docx(briefing_md, candidate_name="Sean Guan") or b"",
            file_name=f"ai_briefing_{timestamp}.docx",
            mime=formats["docx"][0],
            width="stretch",
        )
    else:
        cols[2].button("📄 Word (.docx)", disabled=True, help="Install python-docx to enable", width="stretch")
    if formats["pdf"][2]:
        cols[3].download_button(
            "📕 PDF",
            data=exporter.export_pdf(briefing_md, candidate_name="Sean Guan") or b"",
            file_name=f"ai_briefing_{timestamp}.pdf",
            mime=formats["pdf"][0],
            width="stretch",
        )
    else:
        cols[3].button("📕 PDF", disabled=True, help="Install reportlab to enable", width="stretch")


# ---------------------------------------------------------------------------
# Tab 3: Initiatives table + drilldown
# ---------------------------------------------------------------------------
if active_tab == TAB_LABELS[2]:
    st.subheader("All initiatives")

    df = pd.DataFrame([asdict(i) for i in inits])
    df["risk_bucket"] = df["risk_score"].apply(risk_bucket)

    col_f1, col_f2, col_f3 = st.columns(3)
    bu_filter = col_f1.multiselect(
        "Business unit",
        options=df["business_unit_full"].unique().tolist(),
        default=df["business_unit_full"].unique().tolist(),
    )
    risk_filter = col_f2.multiselect(
        "Risk bucket",
        options=["Healthy", "Watch", "At Risk", "Critical"],
        default=["Watch", "At Risk", "Critical"],
    )
    status_filter = col_f3.multiselect(
        "Status",
        options=df["status_normalized"].unique().tolist(),
        default=df["status_normalized"].unique().tolist(),
    )

    filtered = df[
        df["business_unit_full"].isin(bu_filter)
        & df["risk_bucket"].isin(risk_filter)
        & df["status_normalized"].isin(status_filter)
    ].copy()

    display_cols = [
        "id", "name", "business_unit", "owner", "status_normalized",
        "risk_score", "risk_bucket", "kpi_actual_pct",
        "budget_approved", "budget_spent",
        "validator_status", "sponsor_status", "source_system",
    ]
    show = filtered[display_cols].rename(columns={
        "id": "ID",
        "name": "Initiative",
        "business_unit": "BU",
        "owner": "Owner",
        "status_normalized": "Status",
        "risk_score": "Risk",
        "risk_bucket": "Bucket",
        "kpi_actual_pct": "KPI %",
        "budget_approved": "Budget $",
        "budget_spent": "Spent $",
        "validator_status": "Validator",
        "sponsor_status": "Sponsor",
        "source_system": "Source",
    })
    st.dataframe(
        show,
        width="stretch",
        hide_index=True,
        column_config={
            "Risk": st.column_config.ProgressColumn("Risk", min_value=0, max_value=100, format="%.0f"),
            "KPI %": st.column_config.ProgressColumn("KPI %", min_value=0, max_value=100, format="%d%%"),
            "Budget $": st.column_config.NumberColumn("Budget $", format="$%d"),
            "Spent $": st.column_config.NumberColumn("Spent $", format="$%d"),
        },
    )

    st.markdown("---")
    # Anchor for citation deep-links (citation chips set scroll_to_drill flag)
    st.markdown("<div id='drill-into-an-initiative'></div>", unsafe_allow_html=True)
    st.subheader("Drill into an initiative")

    init_options = {f"[{i.id}] {i.name}": i for i in inits}
    selected_label = st.selectbox(
        "Select initiative",
        options=list(init_options.keys()),
        key="init_picker",
    )
    selected = init_options[selected_label]

    # If we just arrived here from a citation click, auto-scroll to the
    # drill-down so the user lands directly on the relevant content.
    if st.session_state.pop("scroll_to_drill", False):
        st.markdown("""
            <script>
                // Run a few times because Streamlit may still be rendering
                // when the script first executes. Stops once the target is found.
                (function() {
                    let tries = 0;
                    function tryScroll() {
                        const targets = window.parent.document.querySelectorAll('[id="drill-into-an-initiative"]');
                        if (targets.length > 0) {
                            targets[targets.length - 1].scrollIntoView({behavior: 'smooth', block: 'start'});
                            return;
                        }
                        if (tries++ < 20) setTimeout(tryScroll, 80);
                    }
                    tryScroll();
                })();
            </script>
        """, unsafe_allow_html=True)

    # ---- Header strip: name + description + ID ----
    bucket_for_header = risk_bucket(selected.risk_score)
    header_color = {
        "Healthy":  "#2e7d32",
        "Watch":    "#f9a825",
        "At Risk":  "#ef6c00",
        "Critical": "#c62828",
    }[bucket_for_header]
    st.markdown(html(f"""
        <div style='background:white; border:1px solid #e0e4ea; border-left:5px solid {header_color};
                    padding:14px 18px; border-radius:6px; margin-bottom:14px;'>
            <div style='font-size:11px; color:#888; letter-spacing:0.5px;'>{selected.id}  ·  {selected.business_unit_full}</div>
            <div style='font-size:18px; font-weight:700; color:#222; margin-top:2px;'>{selected.name}</div>
            <div style='font-size:13px; color:#555; margin-top:4px; font-style:italic;'>{selected.description}</div>
        </div>
    """), unsafe_allow_html=True)

    col_d1, col_d2 = st.columns([2, 1])

    # ============================================================
    # LEFT: People & source as a table
    # ============================================================
    with col_d1:
        st.markdown("**Initiative details**")

        # Status / approval pill helper
        def _status_pill(status: str) -> str:
            colors = {
                "approved":      ("#2e7d32", "✓ approved"),
                "pending":       ("#ef6c00", "⏳ pending"),
                "not_submitted": ("#888888", "○ not submitted"),
                "On Track":      ("#2e7d32", "On Track"),
                "At Risk":       ("#ef6c00", "At Risk"),
                "Off Track":     ("#c62828", "Off Track"),
                "Complete":      ("#0277bd", "Complete"),
                "Planning":      ("#888888", "Planning"),
            }
            color, label = colors.get(status, ("#555555", status))
            return (
                f"<span style='background:{color}; color:white; padding:2px 8px; "
                f"border-radius:10px; font-size:11px; font-weight:600;'>{label}</span>"
            )

        # Validator pending duration sub-text
        validator_sub = ""
        if selected.validator_status == "pending" and selected.validator_pending_days:
            d = selected.validator_pending_days
            color = "#c62828" if d >= 45 else "#ef6c00" if d >= 21 else "#f9a825"
            validator_sub = f" <span style='color:{color}; font-size:11px; font-weight:600;'>· {d} days pending</span>"

        # Build the details "table" as styled rows (cleaner than st.dataframe for k/v pairs)
        rows = [
            ("Owner",          selected.owner),
            ("Senior sponsor", selected.senior_sponsor),
            ("Validator",      f"{selected.validator or '—'}  {_status_pill(selected.validator_status)}{validator_sub}"),
            ("Sponsor sign-off", _status_pill(selected.sponsor_status)),
            ("Source status",  f"{selected.status_normalized}  <span style='color:#888; font-size:11px;'>(source: \"{selected.status_raw}\")</span>"),
            ("Source system",  f"<span style='color:#555; font-size:13px;'>{selected.source_system}</span>"),
            ("Last updated",   selected.last_updated),
        ]

        # Build HTML compact -- NO leading whitespace per line, otherwise Streamlit
        # treats lines indented 4+ spaces as a code block and renders raw HTML.
        rows_html = "".join(
            f"<tr style='background:{('#fafbfc' if i % 2 == 0 else 'white')};'>"
            f"<td style='padding:8px 12px;color:#666;font-weight:600;width:35%;border-bottom:1px solid #eee;'>{label}</td>"
            f"<td style='padding:8px 12px;color:#222;border-bottom:1px solid #eee;'>{value}</td>"
            f"</tr>"
            for i, (label, value) in enumerate(rows)
        )
        table_html = (
            "<table style='width:100%;border-collapse:collapse;font-size:13px;margin-bottom:14px;'>"
            f"{rows_html}"
            "</table>"
        )
        st.markdown(table_html, unsafe_allow_html=True)

        # Notes from owner -- separate styled block (only if present)
        if selected.notes:
            st.markdown(html(f"""
                <div style='background:#fff8e1; border-left:3px solid #f9a825;
                            padding:10px 14px; border-radius:4px; font-size:13px;
                            color:#5d4037; margin-bottom:8px;'>
                    <strong style='color:#7c5800;'>📝 Notes from owner:</strong> {selected.notes}
                </div>
            """), unsafe_allow_html=True)

    # ============================================================
    # RIGHT: Existing 3 colored metric cards
    # ============================================================
    with col_d2:
        # Color palette
        COLOR_GREEN  = "#2e7d32"
        COLOR_YELLOW = "#f9a825"
        COLOR_ORANGE = "#ef6c00"
        COLOR_RED    = "#c62828"

        bucket = risk_bucket(selected.risk_score)
        risk_color = {
            "Healthy":  COLOR_GREEN,
            "Watch":    COLOR_YELLOW,
            "At Risk":  COLOR_ORANGE,
            "Critical": COLOR_RED,
        }[bucket]

        kpi = selected.kpi_actual_pct
        if   kpi >= 80: kpi_color = COLOR_GREEN
        elif kpi >= 50: kpi_color = COLOR_YELLOW
        elif kpi >= 30: kpi_color = COLOR_ORANGE
        else:           kpi_color = COLOR_RED

        if selected.budget_approved:
            util = selected.budget_utilization_pct
            if   util <= 90:  budget_color = COLOR_GREEN
            elif util <= 105: budget_color = COLOR_YELLOW
            elif util <= 120: budget_color = COLOR_ORANGE
            else:             budget_color = COLOR_RED
        else:
            util = None
            budget_color = "#888888"

        def _metric_card(label: str, value: str, sub: str, sub_color: str) -> str:
            return f"""
            <div style='background:#f7f9fc; padding:12px 14px; border-radius:8px;
                        border-left:4px solid {sub_color}; margin-bottom:10px;'>
                <div style='font-size:11px; color:#666; text-transform:uppercase; letter-spacing:0.4px;'>
                    {label}
                </div>
                <div style='font-size:24px; font-weight:700; color:#222; margin-top:2px;'>
                    {value}
                </div>
                <div style='font-size:13px; color:{sub_color}; font-weight:600; margin-top:2px;'>
                    {sub}
                </div>
            </div>
            """

        cards = [
            _metric_card("Risk score",      f"{selected.risk_score:.0f}", bucket,                  risk_color),
            _metric_card("KPI achievement", f"{kpi}%",                    _kpi_label(kpi),         kpi_color),
        ]
        if selected.budget_approved:
            cards.append(_metric_card(
                "Budget",
                f"${selected.budget_spent:,.0f} / ${selected.budget_approved:,.0f}",
                f"{util:.0f}% used — {_budget_label(util)}",
                budget_color,
            ))
        st.markdown("".join(cards), unsafe_allow_html=True)

    # ============================================================
    # BELOW: Risk flags as a structured table (instead of bullets)
    # ============================================================
    if selected.risk_flags:
        st.markdown("**🚩 Risk flags (deterministic)**")
        st.caption("Each flag was raised by a specific rule in the Risk Analyst Agent's deterministic scoring engine — no LLM involved.")

        # Categorize each flag and assign severity color
        def _categorize_flag(flag_text: str) -> tuple:
            """Return (category_emoji+name, severity_color, severity_label)"""
            f = flag_text.lower()
            if "severe" in f or "dead" in f:
                sev_color, sev_label = "#c62828", "Severe"
            elif "overrun" in f or "burning" in f or "tracking at" in f:
                sev_color, sev_label = "#ef6c00", "High"
            elif "pending" in f or "stale" in f or "pressure" in f:
                sev_color, sev_label = "#f9a825", "Medium"
            else:
                sev_color, sev_label = "#888888", "Info"

            if "budget" in f or "burning" in f or "spend" in f:
                cat = "💰 Financial"
            elif "validator" in f or "sponsor" in f or "review" in f or "sign-off" in f:
                cat = "✋ Approval chain"
            elif "stale" in f or "updated" in f:
                cat = "⏰ Freshness"
            elif "kpi" in f:
                cat = "🎯 Performance"
            elif "status" in f:
                cat = "🚦 Status"
            else:
                cat = "📌 Other"
            return cat, sev_color, sev_label

        # Build flag-table HTML as a single line per element -- no leading whitespace
        th_style = (
            "padding:8px 12px;text-align:left;font-weight:600;"
            "font-size:11px;letter-spacing:0.5px;text-transform:uppercase;"
            "border-bottom:1px solid #e0e4ea;"
        )
        header_html = (
            "<thead>"
            "<tr style='background:#f7f9fc;color:#666;'>"
            f"<th style='{th_style}width:18%;'>Category</th>"
            f"<th style='{th_style}width:12%;'>Severity</th>"
            f"<th style='{th_style}'>Detail</th>"
            "</tr>"
            "</thead>"
        )
        body_rows = []
        for i, flag in enumerate(selected.risk_flags):
            cat, sev_color, sev_label = _categorize_flag(flag)
            bg = "white" if i % 2 == 0 else "#fafbfc"
            pill = (
                f"<span style='background:{sev_color};color:white;padding:2px 8px;"
                f"border-radius:10px;font-size:11px;font-weight:600;'>{sev_label}</span>"
            )
            body_rows.append(
                f"<tr style='background:{bg};'>"
                f"<td style='padding:8px 12px;color:#444;border-bottom:1px solid #f0f0f0;'>{cat}</td>"
                f"<td style='padding:8px 12px;border-bottom:1px solid #f0f0f0;'>{pill}</td>"
                f"<td style='padding:8px 12px;color:#222;border-bottom:1px solid #f0f0f0;'>{flag}</td>"
                f"</tr>"
            )
        flag_table_html = (
            "<table style='width:100%;border-collapse:collapse;font-size:13px;"
            "margin-bottom:12px;border:1px solid #e0e4ea;border-radius:6px;overflow:hidden;'>"
            f"{header_html}"
            f"<tbody>{''.join(body_rows)}</tbody>"
            "</table>"
        )
        st.markdown(flag_table_html, unsafe_allow_html=True)
    else:
        st.success("✅ No risk flags raised — initiative is healthy by all deterministic measures.")

    # ============================================================
    # AI narrative button — structured assessment
    # ============================================================
    if "explanations" not in st.session_state:
        st.session_state.explanations = {}

    btn_col1, btn_col2 = st.columns([1, 4])
    if btn_col1.button("🤖 Ask Risk Analyst Agent", key=f"explain_{selected.id}", width="stretch"):
        with st.spinner("Risk Analyst is reasoning..."):
            from agents.analyst import RiskAnalystAgent
            st.session_state.explanations[selected.id] = RiskAnalystAgent().explain(selected)

    explanation = st.session_state.explanations.get(selected.id)
    if explanation:
        # ---- Header strip ------------------------------------------------
        st.markdown(html(f"""
            <div style='background:linear-gradient(135deg, #f0f4f8 0%, #e3edf5 100%);
                        border-left:4px solid {MS_LIGHT_BLUE}; padding:10px 14px;
                        border-radius:6px 6px 0 0; margin-top:8px; margin-bottom:0;'>
                <div style='font-size:11px; color:{MS_BLUE}; font-weight:700; text-transform:uppercase;
                            letter-spacing:0.5px;'>
                    🤖 Risk Analyst Agent · Structured Assessment
                </div>
            </div>
        """), unsafe_allow_html=True)

        # ---- Assessment paragraph ----------------------------------------
        if explanation.get("assessment"):
            st.markdown(html(f"""
                <div style='background:#fafbfc; border-left:1px solid #e0e4ea; border-right:1px solid #e0e4ea;
                            padding:14px 18px; font-size:13px; color:#222; line-height:1.55;'>
                    <strong style='color:{MS_BLUE}; font-size:11px; text-transform:uppercase;
                                   letter-spacing:0.4px; display:block; margin-bottom:6px;'>
                        Assessment
                    </strong>
                    {explanation["assessment"]}
                </div>
            """), unsafe_allow_html=True)

        # ---- Strengths + Risks side by side ------------------------------
        col_s, col_r = st.columns(2)
        with col_s:
            st.markdown(f"<h5 style='color:#2e7d32; margin-bottom:6px; margin-top:6px;'>✅ Strengths</h5>", unsafe_allow_html=True)
            strengths = explanation.get("strengths", [])
            if strengths:
                sdf = pd.DataFrame([
                    {"Point": s.get("point", ""), "Evidence": s.get("evidence", "")}
                    for s in strengths
                ])
                st.dataframe(
                    sdf, hide_index=True, width="stretch",
                    column_config={
                        "Point":    st.column_config.TextColumn(width="small"),
                        "Evidence": st.column_config.TextColumn(width="large"),
                    },
                )
            else:
                st.caption("No strengths surfaced.")

        with col_r:
            st.markdown(f"<h5 style='color:#c62828; margin-bottom:6px; margin-top:6px;'>⚠️ Risks</h5>", unsafe_allow_html=True)
            risks = explanation.get("risks", [])
            if risks:
                rdf = pd.DataFrame([
                    {"Point": r.get("point", ""), "Severity": r.get("severity", ""), "Evidence": r.get("evidence", "")}
                    for r in risks
                ])
                st.dataframe(
                    rdf, hide_index=True, width="stretch",
                    column_config={
                        "Point":    st.column_config.TextColumn(width="small"),
                        "Severity": st.column_config.TextColumn(width="small"),
                        "Evidence": st.column_config.TextColumn(width="large"),
                    },
                )
            else:
                st.markdown(
                    "<div style='background:#e8f5e9; border-left:3px solid #2e7d32; padding:10px 14px;"
                    "border-radius:4px; font-size:13px; color:#1b5e20;'>"
                    "✓ No material risks surfaced. The deterministic flags either fired none or only "
                    "low-severity watchpoints already covered above."
                    "</div>",
                    unsafe_allow_html=True,
                )

        # ---- Next step ---------------------------------------------------
        ns = explanation.get("next_step") or {}
        if ns.get("recommendation"):
            st.markdown(html(f"""
                <div style='background:#fff8e1; border:1px solid #f9a825; border-left:4px solid {MS_ACCENT};
                            padding:12px 16px; border-radius:6px; margin-top:8px;'>
                    <div style='font-size:11px; color:#7c5800; font-weight:700; text-transform:uppercase;
                                letter-spacing:0.5px; margin-bottom:4px;'>
                        🎯 Recommended next step
                    </div>
                    <div style='font-size:14px; font-weight:600; color:#222; margin-bottom:6px;'>
                        {ns.get("recommendation", "")}
                    </div>
                    <div style='display:flex; gap:18px; font-size:12px; color:#555;'>
                        <div><strong style='color:{MS_BLUE};'>Owner:</strong> {ns.get("owner", "—")}</div>
                        <div><strong style='color:{MS_BLUE};'>By when:</strong> {ns.get("by_when", "—")}</div>
                    </div>
                </div>
            """), unsafe_allow_html=True)

        if explanation.get("_raw_fallback"):
            with st.expander("⚠️ JSON parse failed — view raw LLM output"):
                st.code(explanation["_raw_fallback"])


# ---------------------------------------------------------------------------
# Tab 4: Accountability
# ---------------------------------------------------------------------------
if active_tab == TAB_LABELS[3]:
    st.subheader("Approval-chain health")

    col_s1, col_s2 = st.columns([1, 1])
    with col_s1:
        # Sign-off funnel
        sf = state.signoff_summary
        funnel_data = {
            "Stage": ["Total initiatives", "Validator approved", "Sponsor approved (fully cleared)"],
            "Count": [sf.get("total", 0), sf.get("validator_approved", 0), sf.get("fully_approved", 0)],
        }
        fig = go.Figure(go.Funnel(
            y=funnel_data["Stage"],
            x=funnel_data["Count"],
            marker=dict(color=[MS_BLUE, MS_LIGHT_BLUE, "#2e7d32"]),
            textinfo="value+percent initial",
        ))
        fig.update_layout(height=320, margin=dict(l=0, r=0, t=20, b=0), title="Sign-off funnel")
        st.plotly_chart(fig, width="stretch")

    with col_s2:
        st.markdown("**Validator workload**")
        st.caption("Surfaces capacity bottlenecks before they become escalations.")
        wl_df = pd.DataFrame(state.validator_workload, columns=["Validator", "Total assigned", "Pending"])
        st.dataframe(wl_df, hide_index=True, width="stretch")

    # ============================================================
    # Structured accountability narrative (matches Briefing tab style)
    # ============================================================
    acc_sb = state.accountability_structured or {}

    if acc_sb and not acc_sb.get("_raw_fallback"):
        st.markdown("---")
        st.markdown(f"<h4 style='color:{MS_BLUE}; margin-bottom:8px;'>🤖 Accountability Agent · Portfolio Approval Health</h4>", unsafe_allow_html=True)
        st.caption("Auto-generated assessment. Same agent that drafted the escalation messages below.")

        # ---- Headline card ----
        st.markdown(html(f"""
            <div style='background:linear-gradient(135deg, {MS_BLUE} 0%, #002a4d 100%);
                        color:white; padding:18px 22px; border-radius:8px;
                        margin-bottom:14px; box-shadow:0 2px 6px rgba(0,61,110,0.12);'>
                <div style='font-size:11px; opacity:0.75; text-transform:uppercase;
                            letter-spacing:1.2px; margin-bottom:6px;'>
                    📌 Headline
                </div>
                <div style='font-size:14px; line-height:1.5; font-weight:400;'>
                    {acc_sb.get("headline", "")}
                </div>
            </div>
        """), unsafe_allow_html=True)

        # ---- What's working / What's stuck side by side ----
        col_aw, col_as = st.columns(2)

        with col_aw:
            st.markdown(f"<h5 style='color:#2e7d32; margin-bottom:6px;'>✅ Where accountability is working</h5>", unsafe_allow_html=True)
            working_items = acc_sb.get("what_is_working", [])
            if working_items:
                wdf = pd.DataFrame([
                    {"Area": w.get("area", ""), "Evidence": w.get("evidence", "")}
                    for w in working_items
                ])
                st.dataframe(
                    wdf, hide_index=True, width="stretch",
                    column_config={
                        "Area":     st.column_config.TextColumn(width="small"),
                        "Evidence": st.column_config.TextColumn(width="large"),
                    },
                )
            else:
                st.caption("No items.")

        with col_as:
            st.markdown(f"<h5 style='color:#c62828; margin-bottom:6px;'>🔴 Where it's stuck</h5>", unsafe_allow_html=True)
            stuck_items = acc_sb.get("what_is_stuck", [])
            if stuck_items:
                sdf = pd.DataFrame([
                    {"Area": s.get("area", ""), "Severity": s.get("severity", ""), "Evidence": s.get("evidence", "")}
                    for s in stuck_items
                ])
                st.dataframe(
                    sdf, hide_index=True, width="stretch",
                    column_config={
                        "Area":     st.column_config.TextColumn(width="small"),
                        "Severity": st.column_config.TextColumn(width="small"),
                        "Evidence": st.column_config.TextColumn(width="large"),
                    },
                )
            else:
                st.caption("No items.")

        # ---- Single recommended action (highlighted card) ----
        action_obj = acc_sb.get("single_action") or {}
        if action_obj.get("action"):
            st.markdown(html(f"""
                <div style='background:#fff8e1; border:1px solid #f9a825; border-left:4px solid {MS_ACCENT};
                            padding:14px 18px; border-radius:6px; margin-top:12px;'>
                    <div style='font-size:11px; color:#7c5800; font-weight:700; text-transform:uppercase;
                                letter-spacing:0.5px; margin-bottom:6px;'>
                        🎯 The one action this week
                    </div>
                    <div style='font-size:14px; font-weight:600; color:#222; margin-bottom:8px;'>
                        {action_obj.get("action", "")}
                    </div>
                    <div style='display:flex; gap:24px; font-size:12px; color:#555;'>
                        <div><strong style='color:{MS_BLUE};'>Owner:</strong> {action_obj.get("owner", "—")}</div>
                        <div><strong style='color:{MS_BLUE};'>By when:</strong> {action_obj.get("by_when", "—")}</div>
                    </div>
                </div>
            """), unsafe_allow_html=True)

    elif acc_sb.get("_raw_fallback"):
        st.warning("⚠️ Accountability narrative returned non-JSON content. Falling back to raw display.")
        st.markdown(acc_sb["_raw_fallback"])

    st.markdown("---")
    st.subheader("🚨 Auto-drafted escalation messages")
    st.caption("The Accountability Agent has prepared these for the COO. Review and send -- one click each.")

    if not state.escalations:
        st.success("No escalations needed -- all approval chains are healthy.")
    else:
        for idx, esc in enumerate(state.escalations):
            with st.container():
                priority_color = "#c62828" if esc["priority"] == "High" else "#ef6c00"
                st.markdown(html(f"""
                    <div class='escalation-card'>
                        <div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;'>
                            <strong>To: {esc['to']}</strong>
                            <span style='background:{priority_color}; color:white; padding:2px 10px; border-radius:10px; font-size:11px;'>{esc['priority']} priority</span>
                        </div>
                        <div style='font-style:italic; color:#555; margin-bottom:8px;'>Subject: {esc['subject']}</div>
                        <div style='white-space:pre-wrap; font-size:13px; color:#333;'>{esc['body']}</div>
                        <div style='margin-top:10px; font-size:11px; color:#888;'>Re: {", ".join(esc['blocked_initiatives'])}</div>
                    </div>
                """), unsafe_allow_html=True)
                col_a, col_b, col_c = st.columns([1, 1, 4])
                col_a.button("✉️ Send", key=f"send_{idx}", help="In production this would send via Outlook / Teams")
                col_b.button("✏️ Edit", key=f"edit_{idx}")


# ---------------------------------------------------------------------------
# Tab 5: Chat / Q&A
# ---------------------------------------------------------------------------
if active_tab == TAB_LABELS[4]:
    st.subheader("Ask the portfolio anything")
    st.caption("Natural-language Q&A over the unified portfolio state. Replaces 'let me get back to you with that number'.")

    sample_questions = [
        "Which initiatives are at risk in Investment Bank Tech?",
        "Who is the bottleneck in our approval chain?",
        "How is the Wealth Management portfolio doing?",
        "What's our total budget exposure on AI initiatives?",
        "Which initiatives have validator sign-off pending the longest?",
    ]

    # Persistent across page reloads (e.g. after a citation-chip click that
    # navigates the browser via ?goto=ID, which wipes st.session_state).
    _store = _chat_store()
    chat_history = _store["history"]

    # ----- Sample question chips (collapse after history grows) ----------
    if len(chat_history) == 0:
        st.markdown("**Try these:**")
        qcols = st.columns(len(sample_questions))
        for col, q in zip(qcols, sample_questions):
            if col.button(q, key=f"q_{hash(q)}", width="stretch"):
                st.session_state.chat_question = q
    else:
        with st.expander("💡 Try a sample question", expanded=False):
            qcols = st.columns(len(sample_questions))
            for col, q in zip(qcols, sample_questions):
                if col.button(q, key=f"q_{hash(q)}", width="stretch"):
                    st.session_state.chat_question = q
        if st.button("🗑️ Clear chat history", key="clear_chat"):
            _store["history"].clear()
            _store["pending"] = None
            st.rerun()

    # ----- Scrollable history container ----------------------------------
    # Fixed-height container keeps the input visible without scrolling the
    # whole page. Streamlit auto-scrolls a `height=...` container internally.
    history_container = st.container(height=440, border=True)

    # Build a quick lookup so citation chips can show metadata on hover
    init_by_id = {i.id: i for i in inits}

    def _render_with_citations(text: str) -> str:
        """
        Convert LLM markdown + citation markers into a single HTML blob.

        Why: Streamlit's `st.markdown(..., unsafe_allow_html=True)` only parses
        markdown OUTSIDE of HTML tags. When citation chips like `<a href=...>`
        are interspersed with **bold** markdown and dollar amounts, the parser
        gets confused — text like "$11.2M **and** spend" gets its whitespace
        smashed and bold markers leak through.

        Solution: do all the conversion ourselves, then emit one clean HTML
        block wrapped in a <div> so Streamlit treats it as pure HTML.
        """
        import re as _re
        import html as _html_mod

        # ---- Step 1: do the markdown → HTML conversion ourselves -------
        # Process line-by-line so we can handle lists vs paragraphs cleanly.
        lines = text.split("\n")
        html_lines = []
        in_ol, in_ul = False, False

        def _close_lists():
            nonlocal in_ol, in_ul
            if in_ol:
                html_lines.append("</ol>")
                in_ol = False
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False

        def _format_inline(s: str) -> str:
            """Escape HTML, then apply inline markdown for bold/italic/code."""
            s = _html_mod.escape(s, quote=False)
            # Bold: **text** or __text__
            s = _re.sub(r"\*\*([^*]+?)\*\*", r"<strong>\1</strong>", s)
            s = _re.sub(r"__([^_]+?)__", r"<strong>\1</strong>", s)
            # Italic: *text* (avoid matching ** which is bold) -- single * not next to space
            s = _re.sub(r"(?<!\*)\*([^*\s][^*]*?)\*(?!\*)", r"<em>\1</em>", s)
            # Inline code: `text`
            s = _re.sub(r"`([^`]+?)`", r"<code style='background:#f4f6f9;padding:1px 4px;border-radius:3px;font-size:12px;'>\1</code>", s)
            return s

        for raw_line in lines:
            stripped = raw_line.strip()
            if not stripped:
                _close_lists()
                html_lines.append("<div style='height:6px;'></div>")
                continue

            # Numbered list: "1. text"
            m = _re.match(r"^(\d+)\.\s+(.*)$", stripped)
            if m:
                if not in_ol:
                    _close_lists()
                    html_lines.append("<ol style='margin:4px 0 4px 22px; padding:0;'>")
                    in_ol = True
                html_lines.append(f"<li style='margin:3px 0;'>{_format_inline(m.group(2))}</li>")
                continue

            # Bullet list: "- text" or "* text"
            m = _re.match(r"^[-*]\s+(.*)$", stripped)
            if m:
                if not in_ul:
                    _close_lists()
                    html_lines.append("<ul style='margin:4px 0 4px 22px; padding:0;'>")
                    in_ul = True
                html_lines.append(f"<li style='margin:3px 0;'>{_format_inline(m.group(1))}</li>")
                continue

            # Plain paragraph
            _close_lists()
            html_lines.append(f"<div style='margin:3px 0;'>{_format_inline(stripped)}</div>")

        _close_lists()
        text_html = "\n".join(html_lines)

        # ---- Step 2: inject citation chips into the HTML ---------------
        def _init_chip(match):
            cid = match.group(1)
            init = init_by_id.get(cid)
            if not init:
                return f"<span style='background:#fde7e9;color:#c62828;padding:1px 6px;border-radius:3px;font-size:11px;font-weight:600;'>[{cid} unknown]</span>"
            tooltip = f"Click to open: {init.name} · {init.business_unit_full} · Owner: {init.owner}"
            return (
                f"<a href=\"?goto={cid}\" target=\"_self\" title=\"{tooltip}\" "
                f"style='background:#e8f0f8;color:#003D6E;padding:1px 6px;border-radius:3px;"
                f"font-size:11px;font-weight:600;font-family:monospace;cursor:pointer;"
                f"border:1px solid #c9d8e8;margin:0 2px;text-decoration:none;display:inline-block;"
                f"transition:background 0.12s;vertical-align:baseline;' "
                f"onmouseover=\"this.style.background='#003D6E';this.style.color='white';\" "
                f"onmouseout=\"this.style.background='#e8f0f8';this.style.color='#003D6E';\">"
                f"{cid} ↗</a>"
            )

        def _source_chip(match):
            src = match.group(1)
            return (
                f"<span title=\"Source system: {src}\" "
                f"style='background:#f0f4f8;color:#555;padding:1px 6px;border-radius:3px;"
                f"font-size:11px;font-style:italic;cursor:help;border:1px solid #d4dce5;"
                f"margin:0 2px;vertical-align:baseline;'>"
                f"📄 {src}</span>"
            )

        # Citation markers were escaped by _format_inline (they contain [ and ]).
        # Match against the escaped form: [ → &#x5B; doesn't happen because we
        # used quote=False, but [ stays literal. So the regex still works.
        text_html = _re.sub(r"\[(SOURCE:[^\]]+)\]", lambda m: _source_chip(_re.match(r"SOURCE:(.+)", m.group(1))), text_html)
        text_html = _re.sub(r"\[([A-Z]{2}-AI-\d{4})\]", _init_chip, text_html)

        # Wrap whole thing in a div so Streamlit treats it as pure HTML
        return f"<div style='font-size:14px; line-height:1.55; color:#222;'>{text_html}</div>"

    def _extract_citations(text: str):
        """Pull unique citations from a message; returns (init_ids, sources)."""
        import re as _re
        ids = list(dict.fromkeys(_re.findall(r"\[([A-Z]{2}-AI-\d{4})\]", text)))
        sources = list(dict.fromkeys(_re.findall(r"\[SOURCE:([^\]]+)\]", text)))
        return ids, sources

    with history_container:
        if not chat_history:
            st.markdown(
                "<div style='text-align:center; color:#999; padding:48px 16px; font-size:14px;'>"
                "👋 No questions yet — ask anything about the portfolio below, "
                "or try one of the sample questions above."
                "</div>",
                unsafe_allow_html=True,
            )
        else:
            for msg in chat_history:
                with st.chat_message(msg["role"]):
                    if msg["role"] == "assistant":
                        # Render with citation chips
                        rendered = _render_with_citations(msg["content"])
                        st.markdown(rendered, unsafe_allow_html=True)
                        # Sources panel below the answer
                        ids, sources = _extract_citations(msg["content"])
                        if ids or sources:
                            sources_html = ["<div style='margin-top:10px;padding-top:8px;border-top:1px dashed #d4dce5;font-size:11px;color:#666;'>"]
                            sources_html.append("<strong style='color:#003D6E;'>Sources cited:</strong> ")
                            chip_parts = []
                            for cid in ids:
                                init = init_by_id.get(cid)
                                if init:
                                    chip_parts.append(
                                        f"<a href=\"?goto={cid}\" target=\"_self\" "
                                        f"title=\"Click to open drill-down for {init.name}\" "
                                        f"style='background:#e8f0f8;color:#003D6E;padding:2px 8px;border-radius:10px;"
                                        f"font-size:10px;font-weight:600;font-family:monospace;margin:1px 2px;"
                                        f"display:inline-block;text-decoration:none;cursor:pointer;' "
                                        f"onmouseover=\"this.style.background='#003D6E';this.style.color='white';\" "
                                        f"onmouseout=\"this.style.background='#e8f0f8';this.style.color='#003D6E';\">"
                                        f"{cid} ↗</a> <span style='color:#888;font-size:11px;'>{init.name}</span>"
                                    )
                            for src in sources:
                                chip_parts.append(
                                    f"<span style='background:#f0f4f8;color:#555;padding:2px 8px;border-radius:10px;font-size:10px;font-style:italic;margin:1px 2px;display:inline-block;'>"
                                    f"📄 {src}</span>"
                                )
                            sources_html.append(" · ".join(chip_parts))
                            sources_html.append("</div>")
                            st.markdown("".join(sources_html), unsafe_allow_html=True)
                    else:
                        st.markdown(msg["content"])

            # If a question is pending backend response, show a transient
            # "thinking" assistant bubble inside the history container so the
            # user knows the agent is working on it.
            if _store.get("pending"):
                with st.chat_message("assistant"):
                    st.markdown(
                        "<span style='color:#888;font-style:italic;'>"
                        "🤖 Reasoning over portfolio data<span class='thinking-dots'></span>"
                        "</span>"
                        "<style>"
                        "@keyframes thinking-blink { 0%,100%{opacity:0.3;} 50%{opacity:1;} }"
                        ".thinking-dots::after {"
                        "  content: ' ●●●';"
                        "  animation: thinking-blink 1.2s infinite;"
                        "  letter-spacing: 2px;"
                        "}"
                        "</style>",
                        unsafe_allow_html=True,
                    )

    # ----- Input always visible directly below the history ---------------
    user_q = st.chat_input("Ask a question about the portfolio...")
    if "chat_question" in st.session_state and st.session_state.chat_question:
        user_q = st.session_state.chat_question
        st.session_state.chat_question = None

    # Two-stage submit:
    #   Stage 1 — user submits → append user msg, mark pending → rerun.
    #             User message is rendered immediately by the history loop above.
    #   Stage 2 — pending detected on the next run → call backend (with spinner),
    #             append assistant msg, clear pending → rerun to show answer.
    if user_q:
        _store["history"].append({"role": "user", "content": user_q})
        _store["pending"] = user_q
        st.rerun()

    if _store.get("pending"):
        pending = _store["pending"]
        _store["pending"] = None
        with st.spinner("🤖 Q&A Agent reasoning over portfolio data..."):
            answer = get_orchestrator().answer_question(pending, inits)
        _store["history"].append({"role": "assistant", "content": answer})
        st.rerun()


# ---------------------------------------------------------------------------
# Tab 6: Agent activity / pipeline trace
# ---------------------------------------------------------------------------
if active_tab == TAB_LABELS[5]:
    st.subheader("Agent activity log")
    st.caption("Transparent trace of what each agent did. In a regulated firm, observability of the agentic pipeline matters.")

    for entry in state.activity_log:
        st.markdown(html(f"""
            <div class='agent-card'>
                <strong style='color:{MS_BLUE};'>[{entry['agent']}]</strong> &nbsp; {entry['action']}<br>
                <span style='color:#666; font-size:13px;'>{entry['detail']}</span>
            </div>
        """), unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("System architecture")
    st.markdown("""
```
┌───────────────────────────────────────────────────────────────────────┐
│                      FRAGMENTED DATA SOURCES                          │
│  WM Tech Jira   IB Tech Excel    AM Tech SP        GF Tech Budget    │
│  (JSON)         (CSV)            (CSV)              (CSV)            │
│       │              │                  │                │            │
│       └──────────────┴──────────────────┴────────────────┘            │
│                              │                                        │
│                              ▼                                        │
│              ┌──────────────────────────────┐                         │
│              │  Data Aggregator Agent       │                         │
│              │  • Schema normalization      │                         │
│              │  • Status vocab translation  │                         │
│              │  • Approvals merge           │                         │
│              └──────────────┬───────────────┘                         │
│                             │                                         │
│                             ▼                                         │
│        ┌────────────────────┴────────────────────┐                    │
│        │                                         │                    │
│        ▼                                         ▼                    │
│  ┌──────────────┐                       ┌──────────────────┐          │
│  │ Risk Analyst │                       │ Accountability   │          │
│  │ • Det. score │                       │ • Sign-off track │          │
│  │ • LLM "why"  │                       │ • Bottlenecks    │          │
│  └──────┬───────┘                       │ • Escalations    │          │
│         │                               └────────┬─────────┘          │
│         └────────────────┬─────────────────────-─┘                    │
│                          ▼                                            │
│              ┌────────────────────────┐                               │
│              │  Briefing Agent        │                               │
│              │  • Executive narrative │                               │
│              └───────────┬────────────┘                               │
│                          ▼                                            │
│              ┌────────────────────────┐    ┌─────────────────────┐    │
│              │  Streamlit Dashboard   │◄──►│  Q&A Agent          │    │
│              │  + Chat                │    │  (interactive)      │    │
│              └────────────────────────┘    └─────────────────────┘    │
└───────────────────────────────────────────────────────────────────────┘
```
""")

    st.markdown("---")
    st.subheader("Design principles")
    st.markdown("""
1. **Deterministic core, LLM at the edges.** Risk scoring is rule-based and auditable; the LLM only narrates. In a regulated firm, you cannot have a black-box deciding which initiative is "at risk."

2. **Agents are specialists, not generalists.** Each agent owns one capability. The orchestrator composes them. This is testable, debuggable, and lets us swap any agent for a vendor product later.

3. **Source-of-truth preservation.** The aggregator does not delete or overwrite the source systems. It builds a unified view on top. Owners keep their existing tools.

4. **Decision-shaped output.** The briefing ends with "Recommended decisions for this meeting" -- numbered items leadership can approve or reject. Not "here's what's happening." That's the whole point of replacing static slides.

5. **Observable.** Every agent logs what it did. In production this becomes the audit trail.
""")


# ---------------------------------------------------------------------------
# Tab 7: Logs
# ---------------------------------------------------------------------------
if active_tab == TAB_LABELS[6]:
    st.subheader("System logs")
    st.caption(
        "Full audit trail of every agent action and every LLM call. "
        "In a regulated firm, this is non-negotiable -- it's how Compliance, Model Risk, "
        "and Internal Audit verify what the system actually did."
    )

    # Stats strip
    llm = get_client()
    log_records = get_memory_log()

    cs1, cs2, cs3, cs4, cs5 = st.columns(5)
    cs1.metric("Total log entries", len(log_records))
    cs2.metric("LLM calls", llm.total_calls)
    cs3.metric("LLM backend", llm.backend)
    cs4.metric("API fallbacks", llm.fallback_count, delta_color="inverse")
    cs5.metric("LLM input chars", f"{llm.total_input_chars:,}")

    if llm.fallback_count > 0:
        st.warning(
            f"⚠️ {llm.fallback_count} LLM call(s) fell back to the mock LLM during this session. "
            f"Check the log entries below for the underlying error and verify your API key + network."
        )

    st.markdown("---")

    # Filters
    col_lf1, col_lf2, col_lf3 = st.columns([1, 1, 2])
    level_filter = col_lf1.multiselect(
        "Level",
        options=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default=["INFO", "WARNING", "ERROR", "CRITICAL"],
    )
    agents_in_log = sorted({r["agent"] for r in log_records}) if log_records else []
    agent_filter = col_lf2.multiselect(
        "Agent",
        options=agents_in_log,
        default=agents_in_log,
    )
    search = col_lf3.text_input("Search log messages", placeholder="e.g. RFQ, fallback, person_005")

    filtered = [
        r for r in log_records
        if r["level"] in level_filter
        and r["agent"] in agent_filter
        and (not search or search.lower() in r["message"].lower())
    ]

    st.caption(f"Showing {len(filtered)} of {len(log_records)} log entries (newest last)")

    # Render
    level_colors = {
        "DEBUG":    "#888888",
        "INFO":     "#0277bd",
        "WARNING":  "#ef6c00",
        "ERROR":    "#c62828",
        "CRITICAL": "#b71c1c",
    }

    log_html = ["<div style='background:#0d1117; padding:14px; border-radius:6px; font-family:Menlo,Monaco,Consolas,monospace; font-size:12px; line-height:1.6; max-height:500px; overflow-y:auto;'>"]
    for r in filtered:
        color = level_colors.get(r["level"], "#888")
        extras_str = ""
        if r["extras"]:
            extras_str = "  " + " ".join(
                f"<span style='color:#666;'>{k}=</span><span style='color:#a5d6a7;'>{v}</span>"
                for k, v in r["extras"].items()
            )
        log_html.append(
            f"<div style='color:#ddd; margin-bottom:2px;'>"
            f"<span style='color:#666;'>{r['ts']}</span> "
            f"<span style='color:{color}; font-weight:600;'>{r['level']:<7}</span> "
            f"<span style='color:#64b5f6;'>[{r['agent']}]</span> "
            f"<span style='color:#e8e8e8;'>{r['message']}</span>"
            f"{extras_str}"
            f"</div>"
        )
    log_html.append("</div>")
    st.markdown("".join(log_html), unsafe_allow_html=True)

    st.markdown("---")
    st.caption(
        "💡 The full debug log (including DEBUG-level entries with prompt and response previews) "
        "is also written to `/tmp/ms_prototype.log` -- useful for post-mortem analysis."
    )

    if st.button("🔄 Re-run pipeline & refresh logs"):
        st.cache_resource.clear()
        st.rerun()


# ---------------------------------------------------------------------------
# Tab 8: ROI vs Manual
# ---------------------------------------------------------------------------
if active_tab == TAB_LABELS[7]:
    from agents.meta_monitor import build_roi_report, ManualBaseline, CHARS_PER_TOKEN

    st.subheader("💰 ROI vs Manual Process")
    st.caption(
        "Meta-monitoring on the agent pipeline itself. Proves the automated system is "
        "cheaper than the manual workflow it replaces. Every assumption shown — edit them "
        "in the sidebar to recalculate."
    )

    # ---- Editable baseline assumptions (sidebar within this tab) -------
    with st.expander("📋 Manual process baseline assumptions (edit to recalculate)", expanded=False):
        st.caption(
            "Conservative estimates of the human time consumed by the current monthly "
            "process. Adjust to match your team's reality."
        )
        c_a, c_b, c_c = st.columns(3)
        bu_hrs = c_a.number_input("BU Tech lead hrs/month per BU",  value=4.0, min_value=0.0, max_value=40.0, step=0.5)
        bu_n   = c_a.number_input("# of BU Tech leads",              value=4,   min_value=0,   max_value=20,   step=1)
        an_hrs = c_b.number_input("Analyst hrs/month",               value=8.0, min_value=0.0, max_value=80.0, step=0.5)
        an_n   = c_b.number_input("# of analysts",                   value=1,   min_value=0,   max_value=10,   step=1)
        rv_hrs = c_c.number_input("Reviewer hrs/month",              value=2.0, min_value=0.0, max_value=20.0, step=0.5)
        rv_n   = c_c.number_input("# of reviewers",                  value=1,   min_value=0,   max_value=5,    step=1)
        rate   = st.slider("Blended fully-loaded rate (USD/hour)",   min_value=50, max_value=500, value=200, step=10)
        baseline = ManualBaseline(
            bu_lead_hours_per_month=bu_hrs, bu_lead_count=int(bu_n),
            analyst_hours_per_month=an_hrs, analyst_count=int(an_n),
            reviewer_hours_per_month=rv_hrs, reviewer_count=int(rv_n),
            blended_hourly_rate_usd=float(rate),
        )

    # ---- Build report from current pipeline state ----------------------
    report = build_roi_report(
        pipeline_elapsed_s=getattr(state, "pipeline_elapsed_s", 0.0) or 0.01,
        initiatives_count=len(inits),
        escalations_count=len(state.escalations),
        baseline=baseline,
    )

    # ---- Headline KPI strip ---------------------------------------------
    st.markdown("### Bottom line")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Annual savings",          f"${report.annual_savings:,.0f}")
    k2.metric("Cost per briefing",       f"${report.automated.total_cost_per_run_usd:.2f}",
              delta=f"-{report.cost_reduction_pct:.1f}% vs ${report.baseline.cost_per_briefing:,.0f}",
              delta_color="inverse")
    k3.metric("Hours saved / year",      f"{report.hours_saved_annually:,.0f} hrs",
              delta=f"{report.baseline.total_hours_per_month:.0f} hrs/mo today")
    k4.metric("Wall-clock speedup",      f"{report.speedup_factor:,.0f}x",
              delta=f"{report.automated.pipeline_elapsed_s:.1f}s vs {report.baseline.total_hours_per_month:.0f} hrs")

    st.markdown("<div style='margin-bottom:14px;'></div>", unsafe_allow_html=True)

    # ---- Side-by-side comparison ----------------------------------------
    col_m, col_a = st.columns(2)

    with col_m:
        st.markdown(html(f"""
            <div style='background:#fff8f0; border-left:4px solid {MS_ACCENT};
                        padding:14px 18px; border-radius:6px;'>
                <div style='font-size:11px; color:#7c5800; font-weight:700;
                            text-transform:uppercase; letter-spacing:0.5px; margin-bottom:8px;'>
                    👥 MANUAL PROCESS (current state)
                </div>
                <div style='font-size:28px; font-weight:700; color:#222; line-height:1.1;'>
                    ${report.baseline.cost_per_briefing:,.0f}<span style='font-size:13px; color:#666; font-weight:400;'> per briefing</span>
                </div>
                <div style='font-size:13px; color:#555; margin-top:10px; line-height:1.7;'>
                    <strong>{report.baseline.total_hours_per_month:.0f} person-hours</strong> per monthly briefing<br>
                    Spread across BU leads, analyst, reviewer<br>
                    Blended rate: ${report.baseline.blended_hourly_rate_usd:.0f}/hour fully-loaded
                </div>
            </div>
        """), unsafe_allow_html=True)

    with col_a:
        st.markdown(html(f"""
            <div style='background:#e8f5e9; border-left:4px solid #2e7d32;
                        padding:14px 18px; border-radius:6px;'>
                <div style='font-size:11px; color:#1b5e20; font-weight:700;
                            text-transform:uppercase; letter-spacing:0.5px; margin-bottom:8px;'>
                    🤖 AGENTIC PIPELINE (this prototype)
                </div>
                <div style='font-size:28px; font-weight:700; color:#222; line-height:1.1;'>
                    ${report.automated.total_cost_per_run_usd:.2f}<span style='font-size:13px; color:#666; font-weight:400;'> per briefing</span>
                </div>
                <div style='font-size:13px; color:#555; margin-top:10px; line-height:1.7;'>
                    <strong>{report.automated.pipeline_elapsed_s:.1f} seconds</strong> wall-clock<br>
                    {report.automated.llm_calls} LLM call(s) · {report.automated.estimated_input_tokens:,} in / {report.automated.estimated_output_tokens:,} out tokens<br>
                    LLM: ${report.automated.estimated_llm_cost_usd:.4f} · Infra: ${report.automated.estimated_infra_cost_usd:.4f}
                </div>
            </div>
        """), unsafe_allow_html=True)

    # ---- Detailed cost breakdown ----------------------------------------
    st.markdown("### Detailed breakdown")

    col_b1, col_b2 = st.columns(2)

    with col_b1:
        st.markdown("**Manual labor cost (per briefing)**")
        manual_df = pd.DataFrame([
            {
                "Role": "BU Tech leads",
                "People": baseline.bu_lead_count,
                "Hours/mo (each)": baseline.bu_lead_hours_per_month,
                "Cost ($)": baseline.bu_lead_count * baseline.bu_lead_hours_per_month * baseline.blended_hourly_rate_usd,
            },
            {
                "Role": "Transformation analyst",
                "People": baseline.analyst_count,
                "Hours/mo (each)": baseline.analyst_hours_per_month,
                "Cost ($)": baseline.analyst_count * baseline.analyst_hours_per_month * baseline.blended_hourly_rate_usd,
            },
            {
                "Role": "Senior reviewer",
                "People": baseline.reviewer_count,
                "Hours/mo (each)": baseline.reviewer_hours_per_month,
                "Cost ($)": baseline.reviewer_count * baseline.reviewer_hours_per_month * baseline.blended_hourly_rate_usd,
            },
        ])
        st.dataframe(
            manual_df, hide_index=True, width="stretch",
            column_config={
                "Cost ($)": st.column_config.NumberColumn(format="$%d"),
            },
        )
        st.caption(f"**Total: ${baseline.cost_per_briefing:,.0f} per briefing × 12 = ${baseline.annual_cost:,.0f}/year**")

    with col_b2:
        st.markdown("**Automated pipeline cost (per briefing)**")
        auto_df = pd.DataFrame([
            {
                "Component": "LLM input tokens",
                "Quantity": f"{report.automated.estimated_input_tokens:,} tokens",
                "Rate":     "$3.00 / 1M",
                "Cost ($)": report.automated.estimated_input_tokens * (3.00 / 1_000_000),
            },
            {
                "Component": "LLM output tokens",
                "Quantity": f"{report.automated.estimated_output_tokens:,} tokens",
                "Rate":     "$15.00 / 1M",
                "Cost ($)": report.automated.estimated_output_tokens * (15.00 / 1_000_000),
            },
            {
                "Component": "Compute infra",
                "Quantity": f"{report.automated.pipeline_elapsed_s:.1f}s · 1 vCPU",
                "Rate":     "AWS Fargate spot",
                "Cost ($)": report.automated.estimated_infra_cost_usd,
            },
        ])
        st.dataframe(
            auto_df, hide_index=True, width="stretch",
            column_config={
                "Cost ($)": st.column_config.NumberColumn(format="$%.4f"),
            },
        )
        st.caption(
            f"**Total: ${report.automated.total_cost_per_run_usd:.4f} per briefing × 12 = "
            f"${report.automated.total_cost_per_run_usd * 12:.2f}/year**"
        )

    # ---- ROI summary card -----------------------------------------------
    st.markdown(html(f"""
        <div style='background:linear-gradient(135deg, {MS_BLUE} 0%, #002a4d 100%);
                    color:white; padding:20px 24px; border-radius:8px;
                    margin-top:16px; box-shadow:0 2px 8px rgba(0,61,110,0.15);'>
            <div style='font-size:11px; opacity:0.7; text-transform:uppercase;
                        letter-spacing:1.2px; margin-bottom:6px;'>
                💵 PROJECTED ANNUAL ROI
            </div>
            <div style='font-size:30px; font-weight:700; line-height:1.1; margin-bottom:8px;'>
                ${report.annual_savings:,.0f}<span style='font-size:14px; opacity:0.7; font-weight:400;'> per year</span>
            </div>
            <div style='font-size:13px; opacity:0.85; line-height:1.6;'>
                {report.cost_reduction_pct:.1f}% reduction in cost per briefing.
                {report.hours_saved_annually:,.0f} person-hours redirected to higher-value work.
                Pipeline produces a fresh briefing in {report.automated.pipeline_elapsed_s:.1f}s
                vs ~{report.baseline.total_hours_per_month:.0f} hours of manual effort —
                roughly <strong>{report.speedup_factor:,.0f}x faster</strong>.
            </div>
        </div>
    """), unsafe_allow_html=True)

    # ---- Methodology & caveats (audit trail for Compliance) -------------
    with st.expander("📖 Methodology & assumptions (full audit trail)"):
        st.markdown(f"""
**Manual baseline assumptions** *(editable above)*
- {baseline.bu_lead_count} BU Tech leads × {baseline.bu_lead_hours_per_month}h/month collecting and uploading data
- {baseline.analyst_count} transformation analyst × {baseline.analyst_hours_per_month}h stitching, reconciling, and writing the briefing
- {baseline.reviewer_count} senior reviewer × {baseline.reviewer_hours_per_month}h QA pass + revisions
- Blended fully-loaded hourly rate: ${baseline.blended_hourly_rate_usd:.0f}
- Assumes one briefing produced per month

**Automated pipeline cost components**
- LLM token cost: estimated at ~{CHARS_PER_TOKEN:.0f} chars/token. Anthropic Claude Sonnet 4 pricing assumed at $3/M input, $15/M output.
- Live LLM call count this run: {report.automated.llm_calls}
- LLM fallbacks (mock): {report.automated.llm_fallback_count}
- Infrastructure: 1 vCPU × pipeline elapsed time at AWS Fargate spot rates (~$0.005 floor)

**What's NOT included in either side**
- Manual side: errors, late deliveries, version-control overhead, organizational frustration cost
- Automated side: one-time build cost (this prototype), maintenance, model drift monitoring, on-call coverage
- Both sides: opportunity cost of not having a real-time queryable portfolio (probably the largest hidden cost in the manual case)

**Why this is conservative**
The automated estimate assumes worst-case full-fat LLM use on every run. In practice, deterministic agents (aggregator, risk scorer, accountability) produce ~80% of the output without any LLM call. The real automated cost is closer to $0.05-$0.10 per briefing.
        """)

    # ---- Pipeline performance log (live data) ---------------------------
    with st.expander("📊 Live pipeline performance log"):
        st.markdown(f"""
**This pipeline run**
- Initiatives processed: **{report.automated.initiatives}**
- Escalations drafted: **{report.automated.escalations}**
- Wall-clock elapsed: **{report.automated.pipeline_elapsed_s:.2f}s**
- LLM calls made: **{report.automated.llm_calls}**
  ({"all live" if report.automated.llm_fallback_count == 0 else f"{report.automated.llm_fallback_count} fallback to mock"})
- Estimated input tokens: **{report.automated.estimated_input_tokens:,}**
- Estimated output tokens: **{report.automated.estimated_output_tokens:,}**
        """)


# ===========================================================================
# Footer
# ===========================================================================
st.markdown("---")
st.markdown(
    html(f"""
    <div style='text-align:center; color:#999; font-size:12px; padding:20px 0;'>
        Prototype · Technology COO Transformation Team<br>
        Built by Sean Guan · All data shown is simulated for demonstration purposes
    </div>
    """),
    unsafe_allow_html=True,
)
