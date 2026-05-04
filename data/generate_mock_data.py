"""
Mock data generator -- "story-shaped" version
==============================================
Instead of random data, this generator produces a portfolio with deliberate
narrative arcs that make the demo land harder:

  Hero       : GenAI Advisor Co-Pilot (WM)        -- on-time, on-budget, exceeding KPIs
  Disaster   : RFQ Auto-Pricing (IS)              -- 185% over budget, 25% KPI, validator stuck 45 days
  Hidden risk: AI Code Review Assistant (TECH)    -- looks "Active" but milestone slipping & burn high
  Stuck      : Onboarding Doc Intelligence (WM)   -- validator pending 60+ days
  Stale      : Portfolio Manager Chatbot (IM)     -- 90 days no update, KPI 22%
  Quick win  : Internal Knowledge Search (TECH)   -- fully approved, ready to ship
  Bottleneck : person_005 assigned 5 pending reviews -- single point of failure

Each initiative is hand-crafted to support the story; only minor secondary
fields use randomization (seeded for reproducibility).
"""
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

random.seed(42)

DATA_DIR = Path(__file__).parent
DATA_DIR.mkdir(exist_ok=True)

SPONSORS = {
    "WM": "person_001 (Head of Wealth Management Technology)",
    "IB": "person_002 (Head of Investment Bank Technology)",
    "AM": "person_003 (Head of Asset Management Technology)",
    "GF": "person_004 (Head of Group Functions Technology)",
}


def days_ago(n):
    return datetime.now() - timedelta(days=n)


# ===========================================================================
# Narrative text per initiative
# ===========================================================================
# Free-text owner-style commentary -- this is what the Briefing Agent's LLM
# reads to surface story arcs. Putting story flavor in NOTES (not in a
# dedicated "story_type" field) is intentional: it forces the LLM to do the
# actual interpretive work, which is the whole point of putting AI in the loop.
#
NARRATIVES = {
    # ---- WM ---------------------------------------------------------------
    "WM-AI-1000": "Now production with 4,200 advisors using daily; advisor productivity gain measured at 28%, exceeding 20% target. Sponsor pushing to scale to remaining 8,000 advisors next quarter -- need additional API budget approved.",
    "WM-AI-1001": "Pilot scope: 200 advisors across two regions. Validator review re-opened after Q1 model update changed sentiment-classification thresholds.",
    "WM-AI-1002": "User feedback strong; pilot extending to additional research desks. No blockers.",
    "WM-AI-1003": "Build is functionally complete. Trying to reuse the Co-Pilot's already-approved LLM stack to shortcut model-risk review, but Risk has not yet ruled on whether the reuse argument is acceptable. Sitting in queue 62 days. Owner has escalated twice with no response.",
    "WM-AI-1004": "Joint WM + IB initiative for cross-border client tax-lot optimization. Governance friction: WM wants UK private-banker workflow; IB wants integration with structured-products desk. Legal review held pending alignment between the two BU heads on data-residency boundary. 142 comments on the ticket reflect this.",

    # ---- IB ---------------------------------------------------------------
    "IB-AI-1000": "Model showing significant drift in volatile rate environment. Vendor compute costs ran 3x estimate. Backtest results disputed by trading desk. Awaiting validator re-review of model risk documentation. $3.8M overspend with 25% KPI delivery -- this is a control failure, not a market failure.",
    "IB-AI-1001": "Compliance review extended timeline. Awaiting feedback on new alerting taxonomy. Burn rate manageable.",
    "IB-AI-1002": "Production deployment planned for next sprint. Latency holding under target across the Top 500 names.",
    "IB-AI-1003": "Model documentation iteration ongoing. Awaiting Risk validator's review of revised backtest methodology.",
    "IB-AI-1004": "Restructured 6 months ago after Q4 2025 review flagged scope creep. New ownership, 40% scope cut, biweekly validator cadence. Now 2 consecutive quarters Green and the firm's reference model for AI initiative remediation. Recommend other troubled initiatives study this template.",
    "IB-AI-1005": "Primary LLM vendor breached SLA twice in past 30 days (uptime <97% vs 99.5% contractual). Initiative paused pending evaluation of alternative provider; switching cost estimated at $300k + 6 weeks. Sponsor sign-off contingent on vendor decision.",

    # ---- AM ---------------------------------------------------------------
    "AM-AI-1000": "No status update in 87 days. Original PM rotated to a different desk in February; nominal owner has no domain context and no team. 22% complete with 14 open issues from 4 months ago. Realistically dead.",
    "AM-AI-1001": "Pilot showing measurable alpha lift on two strategies; expanding to fixed-income next quarter. On budget.",
    "AM-AI-1002": "UAT going well with portfolio managers; on track for Q3 2026 go-live.",
    "AM-AI-1003": "EU SFDR Level 2 climate-VaR disclosure has a hard regulatory deadline. Cannot slip without legal exposure -- different risk profile than 'we'd like this to ship'. Validator review with Legal pending 19 days; need to escalate this week.",

    # ---- GF ---------------------------------------------------------------
    "GF-AI-1000": "Source system reports 'Active' but milestone is 1+ month behind and spend is at 122% of $5.5M budget. Headcount expanded to 18 FTE without revised business case. The kind of slippage that's invisible in static reporting -- this is exactly what the prototype should catch.",
    "GF-AI-1001": "1-2 weeks behind on milestone but recoverable. PagerDuty integration cleared; awaiting sponsor review.",
    "GF-AI-1002": "Cleared all reviews ahead of schedule, under budget at 78%. Production rollout in flight to 12,000 engineers. Quietly the strongest delivery in the portfolio.",
    "GF-AI-1003": "Owner left the firm 6 months ago. No formal reassignment. Source system still shows 'Active' because no one has bothered to update it. Headcount on paper says 6 FTE but actually 0. $480k spent and stalled. This is organizational drift -- not a failed initiative, an abandoned one.",
    "GF-AI-1004": "Quietly delivering. Reduced contract-review turnaround from 12 days to 2 days. No drama, no headlines, no escalations. The kind of initiative that should be easy to fund more of next year.",

    # ---- WM scale stage --------------------------------------------------
    "WM-AI-1005": "Pilot with 150 advisors hit 94% of accuracy target on pre-trade compliance flagging. Compliance team comfortable -- moving into production rollout for Northeast region next month, then full WM by Q4.",

    # ---- AM standard delivery --------------------------------------------
    "AM-AI-1004": "Pilot with 6 portfolio managers running smoothly. Recommendations agree with PM votes 87% of the time; disagreements have been productive review conversations. Go-live in 60 days; no blockers.",
}


# ===========================================================================
# Budget overrides for source systems that don't natively track $ (WM Jira,
# AM SharePoint). Numbers are crafted to support each initiative's story:
#   - Hero/scaling = on or under budget
#   - Stuck/zombie/disaster = over budget
#   - Normal/healthy = mid-cycle, around 50-75% utilized
# Format: {initiative_id: (approved_USD, ytd_spent_USD)}
# ===========================================================================
BUDGETS = {
    # ---- WM ---------------------------------------------------------------
    "WM-AI-1000": (3_500_000, 2_450_000),    # Hero: under budget, scaling. 70% used.
    "WM-AI-1001": (1_200_000,   720_000),    # Sentiment: pilot phase, 60% used.
    "WM-AI-1002": (   900_000,  680_000),    # Research summarization: 75% used.
    "WM-AI-1003": (1_800_000, 1_650_000),    # STUCK: 92% spent, build done but stuck on approval.
    "WM-AI-1004": (2_400_000, 1_350_000),    # CROSS-BU: governance friction, 56% used. Slow burn.
    "WM-AI-1005": (1_400_000,   860_000),    # Compliance Co-Pilot: pilot to scale. 61% used.

    # ---- AM ---------------------------------------------------------------
    "AM-AI-1000": (1_600_000,   880_000),    # STALE: 55% spent then activity died. Money locked.
    "AM-AI-1001": (2_800_000, 1_960_000),    # Alpha Signals: on track. 70% used.
    "AM-AI-1002": (1_100_000,   910_000),    # ESG Classifier: near complete. 83% used.
    "AM-AI-1003": (3_200_000, 1_940_000),    # REGULATORY: deadline pressure. 61% used.
    "AM-AI-1004": (   850_000,  580_000),    # ESG Voting: pilot. 68% used.
}


# ===========================================================================
# Hand-crafted initiatives -- each tells a specific story
# ===========================================================================
INITIATIVES = [
    # -----------------------------------------------------------------------
    # HERO: WM GenAI Advisor Co-Pilot
    # -----------------------------------------------------------------------
    {
        "id": "WM-AI-1000", "bu": "WM",
        "name": "GenAI Advisor Co-Pilot",
        "description": "LLM-powered assistant for financial advisors to draft client communications and surface portfolio insights",
        "owner": "person_009",
        "story": "hero",
        "wm": {
            "status": "In Progress", "priority": "P0",
            "story_points_planned": 80, "story_points_completed": 78,
            "comments_count": 64, "last_updated_days_ago": 1,
            "labels": ["genai", "production", "scaling"],
        },
        "validator": "person_007 (Model Risk)",
        "validator_status": "approved", "validator_decision_days_ago": 18,
        "sponsor_status": "approved", "sponsor_decision_days_ago": 12,
    },

    # WM normal performer
    {
        "id": "WM-AI-1001", "bu": "WM",
        "name": "Client Sentiment Analytics",
        "description": "NLP on advisor call transcripts to detect at-risk client relationships",
        "owner": "person_010",
        "story": "normal",
        "wm": {
            "status": "In Progress", "priority": "P1",
            "story_points_planned": 50, "story_points_completed": 32,
            "comments_count": 22, "last_updated_days_ago": 6,
            "labels": ["nlp", "pilot"],
        },
        "validator": "person_005 (Risk)",
        "validator_status": "pending", "validator_decision_days_ago": None,
        "validator_pending_days": 18,
        "sponsor_status": "not_submitted", "sponsor_decision_days_ago": None,
    },

    # WM healthy
    {
        "id": "WM-AI-1002", "bu": "WM",
        "name": "Personalized Research Summarization",
        "description": "Auto-summarize equity research reports tailored to each client's holdings",
        "owner": "person_011",
        "story": "normal",
        "wm": {
            "status": "In Review", "priority": "P1",
            "story_points_planned": 40, "story_points_completed": 38,
            "comments_count": 31, "last_updated_days_ago": 4,
            "labels": ["genai", "pilot"],
        },
        "validator": "person_006 (Compliance)",
        "validator_status": "approved", "validator_decision_days_ago": 9,
        "sponsor_status": "approved", "sponsor_decision_days_ago": 4,
    },

    # -----------------------------------------------------------------------
    # STUCK: WM Onboarding Document Intelligence
    # -----------------------------------------------------------------------
    {
        "id": "WM-AI-1003", "bu": "WM",
        "name": "Onboarding Document Intelligence",
        "description": "OCR + LLM extraction for KYC/onboarding paperwork",
        "owner": "person_012",
        "story": "stuck",
        "wm": {
            "status": "Blocked", "priority": "P0",
            "story_points_planned": 60, "story_points_completed": 55,
            "comments_count": 89, "last_updated_days_ago": 12,
            "labels": ["genai", "production", "blocked-approval"],
        },
        "validator": "person_005 (Risk)",
        "validator_status": "pending", "validator_decision_days_ago": None,
        "validator_pending_days": 62,
        "sponsor_status": "not_submitted", "sponsor_decision_days_ago": None,
    },

    # -----------------------------------------------------------------------
    # DISASTER: IB Tech RFQ Auto-Pricing -- the headline failure
    # -----------------------------------------------------------------------
    {
        "id": "IB-AI-1000", "bu": "IB",
        "name": "RFQ Auto-Pricing",
        "description": "Reinforcement learning agent for fixed-income RFQ pricing",
        "owner": "person_013",
        "story": "disaster",
        "is": {
            "rag": "Red", "q_target": "Q2 2026",
            "budget_approved": 4_500_000,
            "budget_spent": 8_320_000,         # 185% -- catastrophic
            "kpi_target": "20bps pricing improvement on $2B daily flow",
            "kpi_actual_pct": 25,              # severely under
            "last_review_days_ago": 38,
            "notes": "Model showing significant drift in volatile rate environment. Vendor compute costs ran 3x estimate. Backtest results disputed by trading desk. Awaiting validator re-review of model risk documentation.",
        },
        "validator": "person_005 (Risk)",
        "validator_status": "pending", "validator_decision_days_ago": None,
        "validator_pending_days": 45,
        "sponsor_status": "not_submitted", "sponsor_decision_days_ago": None,
    },

    # IS amber -- mild overrun, sponsor pending
    {
        "id": "IB-AI-1001", "bu": "IB",
        "name": "Trade Surveillance ML",
        "description": "ML models flagging anomalous trading patterns for compliance review",
        "owner": "person_014",
        "story": "watch",
        "is": {
            "rag": "Amber", "q_target": "Q3 2026",
            "budget_approved": 2_500_000,
            "budget_spent": 2_640_000,
            "kpi_target": "30% reduction in false-positive alerts",
            "kpi_actual_pct": 58,
            "last_review_days_ago": 14,
            "notes": "Compliance review extended timeline. Awaiting feedback on new alerting taxonomy.",
        },
        "validator": "person_006 (Compliance)",
        "validator_status": "approved", "validator_decision_days_ago": 6,
        "sponsor_status": "pending", "sponsor_decision_days_ago": None,
    },

    # IS green
    {
        "id": "IB-AI-1002", "bu": "IB",
        "name": "Earnings Call NLP",
        "description": "Real-time NLP on earnings calls for sales & trading desk alerts",
        "owner": "person_015",
        "story": "normal",
        "is": {
            "rag": "Green", "q_target": "Q4 2026",
            "budget_approved": 1_200_000,
            "budget_spent": 720_000,
            "kpi_target": "Sub-2-second latency on Top 500 names",
            "kpi_actual_pct": 88,
            "last_review_days_ago": 7,
            "notes": "Production deployment planned for next sprint.",
        },
        "validator": "person_007 (Model Risk)",
        "validator_status": "approved", "validator_decision_days_ago": 11,
        "sponsor_status": "approved", "sponsor_decision_days_ago": 5,
    },

    # IS amber -- another stuck-on-Daniel-Park
    {
        "id": "IB-AI-1003", "bu": "IB",
        "name": "Counterparty Credit AI",
        "description": "Deep learning model for dynamic counterparty credit risk scoring",
        "owner": "person_016",
        "story": "watch",
        "is": {
            "rag": "Amber", "q_target": "Q2 2026",
            "budget_approved": 3_000_000,
            "budget_spent": 1_950_000,
            "kpi_target": "AUC > 0.85 on validation set",
            "kpi_actual_pct": 42,
            "last_review_days_ago": 21,
            "notes": "Model documentation iteration ongoing. Awaiting person_005's review of backtest methodology.",
        },
        "validator": "person_005 (Risk)",
        "validator_status": "pending", "validator_decision_days_ago": None,
        "validator_pending_days": 28,
        "sponsor_status": "not_submitted", "sponsor_decision_days_ago": None,
    },

    # -----------------------------------------------------------------------
    # STALE: AM Tech Portfolio Manager Chatbot
    # -----------------------------------------------------------------------
    {
        "id": "AM-AI-1000", "bu": "AM",
        "name": "Portfolio Manager Chatbot",
        "description": "Internal chatbot grounded on research library + holdings data",
        "owner": "person_017",
        "story": "stale",
        "im": {
            "health": "Off Track", "phase": "Build",
            "go_live_target_days_offset": -45,    # already missed
            "pct_complete": 22,
            "issues_open": 14,
            "last_status_update_days_ago": 87,    # nearly 3 months stale
        },
        "validator": "person_005 (Risk)",
        "validator_status": "not_submitted", "validator_decision_days_ago": None,
        "sponsor_status": "not_submitted", "sponsor_decision_days_ago": None,
    },

    # IM healthy
    {
        "id": "AM-AI-1001", "bu": "AM",
        "name": "Alt Data Alpha Signals",
        "description": "Generate alpha signals from alternative data using LLMs and ML",
        "owner": "person_018",
        "story": "normal",
        "im": {
            "health": "On Track", "phase": "Pilot",
            "go_live_target_days_offset": 90,
            "pct_complete": 72,
            "issues_open": 3,
            "last_status_update_days_ago": 5,
        },
        "validator": "person_007 (Model Risk)",
        "validator_status": "approved", "validator_decision_days_ago": 14,
        "sponsor_status": "approved", "sponsor_decision_days_ago": 8,
    },

    # IM healthy
    {
        "id": "AM-AI-1002", "bu": "AM",
        "name": "ESG Document Classifier",
        "description": "Classify and extract ESG metrics from corporate disclosures",
        "owner": "person_019",
        "story": "normal",
        "im": {
            "health": "On Track", "phase": "UAT",
            "go_live_target_days_offset": 45,
            "pct_complete": 85,
            "issues_open": 2,
            "last_status_update_days_ago": 3,
        },
        "validator": "person_008 (Legal)",
        "validator_status": "approved", "validator_decision_days_ago": 7,
        "sponsor_status": "approved", "sponsor_decision_days_ago": 2,
    },

    # -----------------------------------------------------------------------
    # HIDDEN RISK: GF Tech AI Code Review
    # -----------------------------------------------------------------------
    {
        "id": "GF-AI-1000", "bu": "GF",
        "name": "AI Code Review Assistant",
        "description": "LLM-based code review across the firm's ~12k engineers",
        "owner": "person_020",
        "story": "hidden_risk",
        "tech": {
            "fiscal_year": "FY2026",
            "approved_budget": 5_500_000,
            "ytd_spend": 6_710_000,            # 122% overrun
            "headcount_allocated": 18,
            "vendor_dependencies": "Anthropic, AWS, GitHub Enterprise",
            "current_state": "Active",          # source still says Active -- the trap
            "milestone_status": "1+ month behind",
        },
        "validator": "person_005 (Risk)",
        "validator_status": "pending", "validator_decision_days_ago": None,
        "validator_pending_days": 22,
        "sponsor_status": "not_submitted", "sponsor_decision_days_ago": None,
    },

    # TECH watch
    {
        "id": "GF-AI-1001", "bu": "GF",
        "name": "Incident Triage Agent",
        "description": "Agentic system that triages production incidents and drafts root-cause analyses",
        "owner": "person_021",
        "story": "watch",
        "tech": {
            "fiscal_year": "FY2026",
            "approved_budget": 1_500_000,
            "ytd_spend": 1_580_000,
            "headcount_allocated": 6,
            "vendor_dependencies": "Anthropic, PagerDuty",
            "current_state": "Active",
            "milestone_status": "1-2 weeks behind",
        },
        "validator": "person_008 (Legal)",
        "validator_status": "approved", "validator_decision_days_ago": 5,
        "sponsor_status": "pending", "sponsor_decision_days_ago": None,
    },

    # -----------------------------------------------------------------------
    # QUICK WIN: GF Tech Internal Knowledge Search
    # -----------------------------------------------------------------------
    {
        "id": "GF-AI-1002", "bu": "GF",
        "name": "Internal Knowledge Search",
        "description": "Enterprise search with RAG over Confluence, SharePoint, and ServiceNow",
        "owner": "person_022",
        "story": "quick_win",
        "tech": {
            "fiscal_year": "FY2026",
            "approved_budget": 800_000,
            "ytd_spend": 620_000,
            "headcount_allocated": 4,
            "vendor_dependencies": "Anthropic, Elastic",
            "current_state": "Active",
            "milestone_status": "Ahead of schedule",
        },
        "validator": "person_006 (Compliance)",
        "validator_status": "approved", "validator_decision_days_ago": 16,
        "sponsor_status": "approved", "sponsor_decision_days_ago": 9,
    },

    # =======================================================================
    # REFORMED: IB GenAI Earnings Translation -- the comeback story
    # =======================================================================
    # Was a "Red" disaster two quarters ago. After a hard restructure (new
    # owner, scope cut by 40%, tighter validator cadence) it's now a model
    # for how the firm should run AI initiatives. Worth highlighting in the
    # briefing as proof that remediation works.
    {
        "id": "IB-AI-1004", "bu": "IB",
        "name": "GenAI Earnings Translation",
        "description": "Real-time multilingual translation of earnings transcripts for cross-border S&T desks",
        "owner": "person_014",
        "story": "reformed",
        "is": {
            "rag": "Green", "q_target": "Q3 2026",
            "budget_approved": 1_800_000,
            "budget_spent": 1_120_000,
            "kpi_target": "Sub-500ms translation latency for 8 languages",
            "kpi_actual_pct": 92,
            "last_review_days_ago": 5,
            "notes": "Restructured 6 months ago after Q4 2025 review flagged scope creep; new ownership, 40% scope cut, biweekly validator cadence. Now 2 consecutive quarters Green. Cited as the firm's reference model for AI initiative remediation.",
        },
        "validator": "person_007 (Model Risk)",
        "validator_status": "approved", "validator_decision_days_ago": 8,
        "sponsor_status": "approved", "sponsor_decision_days_ago": 3,
    },

    # =======================================================================
    # REGULATORY-DRIVEN: AM Climate Risk Model -- external pressure, hard deadline
    # =======================================================================
    # EU SFDR Level 2 disclosure requirements have a fixed regulatory deadline.
    # This initiative cannot slip without legal exposure -- different risk
    # profile from "we'd like this to ship".
    {
        "id": "AM-AI-1003", "bu": "AM",
        "name": "Climate Risk ML Model",
        "description": "ML-based climate-VaR scoring across the AM equities and fixed-income book to satisfy EU SFDR Level 2 disclosures",
        "owner": "person_018",
        "story": "regulatory",
        "im": {
            "health": "At Risk", "phase": "Build",
            "go_live_target_days_offset": 75,
            "pct_complete": 48,
            "issues_open": 9,
            "last_status_update_days_ago": 4,
        },
        "validator": "person_008 (Legal)",
        "validator_status": "pending", "validator_decision_days_ago": None,
        "validator_pending_days": 19,
        "sponsor_status": "not_submitted", "sponsor_decision_days_ago": None,
    },

    # =======================================================================
    # ZOMBIE: GF Legacy COBOL Modernization Bot
    # =======================================================================
    # Owner left the firm 6 months ago. No one has formally been reassigned.
    # Source system still says "Active" because no one has bothered to update
    # it. This is the kind of organizational drift the prototype should catch.
    {
        "id": "GF-AI-1003", "bu": "GF",
        "name": "Legacy COBOL Modernization Bot",
        "description": "LLM-assisted refactoring of legacy COBOL/PL/I batch jobs into modern services",
        "owner": "person_020",
        "story": "zombie",
        "tech": {
            "fiscal_year": "FY2026",
            "approved_budget": 2_200_000,
            "ytd_spend": 480_000,
            "headcount_allocated": 0,
            "vendor_dependencies": "GitHub Copilot, internal CICS",
            "current_state": "Active",
            "milestone_status": "1+ month behind",
        },
        "validator": "person_007 (Model Risk)",
        "validator_status": "not_submitted", "validator_decision_days_ago": None,
        "sponsor_status": "not_submitted", "sponsor_decision_days_ago": None,
    },

    # =======================================================================
    # CROSS-BU: WM/IB Cross-Border Tax AI -- joint sponsorship, governance friction
    # =======================================================================
    {
        "id": "WM-AI-1004", "bu": "WM",
        "name": "Cross-Border Tax AI",
        "description": "LLM agent for cross-border client tax-lot optimization, jointly used by WM private bankers and IB structured products desk",
        "owner": "person_009",
        "story": "cross_bu",
        "wm": {
            "status": "In Progress", "priority": "P1",
            "story_points_planned": 90, "story_points_completed": 48,
            "comments_count": 142,
            "last_updated_days_ago": 8,
            "labels": ["genai", "cross-bu", "tax", "wm-ib-joint"],
        },
        "validator": "person_008 (Legal)",
        "validator_status": "pending", "validator_decision_days_ago": None,
        "validator_pending_days": 31,
        "sponsor_status": "not_submitted", "sponsor_decision_days_ago": None,
    },

    # =======================================================================
    # VENDOR RISK: IB Counterparty KYC Refresh AI
    # =======================================================================
    {
        "id": "IB-AI-1005", "bu": "IB",
        "name": "Counterparty KYC Refresh AI",
        "description": "Automated re-KYC document parsing for institutional counterparties using a primary LLM vendor",
        "owner": "person_016",
        "story": "vendor_risk",
        "is": {
            "rag": "Amber", "q_target": "Q4 2026",
            "budget_approved": 1_400_000,
            "budget_spent": 980_000,
            "kpi_target": "Process 500 counterparty re-KYCs / quarter at 95% accuracy",
            "kpi_actual_pct": 64,
            "last_review_days_ago": 9,
            "notes": "Primary vendor breached SLA twice in past 30 days (uptime <97% vs 99.5% contractual). Initiative paused pending evaluation of alternative provider; switching cost estimated at $300k + 6 weeks. Sponsor sign-off contingent on vendor decision.",
        },
        "validator": "person_007 (Model Risk)",
        "validator_status": "approved", "validator_decision_days_ago": 22,
        "sponsor_status": "pending", "sponsor_decision_days_ago": None,
    },

    # =======================================================================
    # NORMAL: WM Advisor Compliance Co-Pilot -- pilot succeeding, scaling
    # =======================================================================
    {
        "id": "WM-AI-1005", "bu": "WM",
        "name": "Advisor Compliance Co-Pilot",
        "description": "LLM-assisted pre-trade compliance checks for advisor-initiated transactions",
        "owner": "person_011",
        "wm": {
            "status": "In Review", "priority": "P1",
            "story_points_planned": 55, "story_points_completed": 50,
            "comments_count": 38, "last_updated_days_ago": 3,
            "labels": ["genai", "compliance", "pilot-to-scale"],
        },
        "validator": "person_006 (Compliance)",
        "validator_status": "approved", "validator_decision_days_ago": 11,
        "sponsor_status": "approved", "sponsor_decision_days_ago": 5,
    },

    # =======================================================================
    # NORMAL: AM ESG Voting Recommendation Engine -- on track, no drama
    # =======================================================================
    {
        "id": "AM-AI-1004", "bu": "AM",
        "name": "ESG Proxy Voting Recommendation Engine",
        "description": "ML-based recommendation engine for proxy voting decisions across the AM book",
        "owner": "person_019",
        "im": {
            "health": "On Track", "phase": "Pilot",
            "go_live_target_days_offset": 60,
            "pct_complete": 78,
            "issues_open": 4,
            "last_status_update_days_ago": 7,
        },
        "validator": "person_006 (Compliance)",
        "validator_status": "approved", "validator_decision_days_ago": 13,
        "sponsor_status": "approved", "sponsor_decision_days_ago": 4,
    },

    # =======================================================================
    # NORMAL: GF Procurement Contract Analyzer -- under-the-radar success
    # =======================================================================
    {
        "id": "GF-AI-1004", "bu": "GF",
        "name": "Procurement Contract Analyzer",
        "description": "LLM extraction of key terms (renewal date, auto-renew clauses, liability caps) from vendor contracts",
        "owner": "person_021",
        "tech": {
            "fiscal_year": "FY2026",
            "approved_budget": 600_000,
            "ytd_spend": 410_000,
            "headcount_allocated": 3,
            "vendor_dependencies": "Anthropic, Ironclad",
            "current_state": "Active",
            "milestone_status": "On schedule",
        },
        "validator": "person_008 (Legal)",
        "validator_status": "approved", "validator_decision_days_ago": 24,
        "sponsor_status": "approved", "sponsor_decision_days_ago": 17,
    },
]


# ===========================================================================
# Source-system writers
# ===========================================================================

def _narrative_for(init):
    """Per-initiative narrative -- explicit field takes priority, else NARRATIVES dict."""
    return init.get("narrative") or NARRATIVES.get(init["id"], "")


def _budget_for(init):
    """Per-initiative budget tuple (approved, spent) from BUDGETS dict; (0,0) if absent."""
    return BUDGETS.get(init["id"], (0, 0))


def write_wm_jira():
    wm = [i for i in INITIATIVES if i["bu"] == "WM"]
    out = []
    for init in wm:
        d = init["wm"]
        approved, spent = _budget_for(init)
        out.append({
            "ticket_id": init["id"],
            "summary": init["name"],
            "description": init["description"],
            "assignee": init["owner"],
            "status": d["status"],
            "priority": d["priority"],
            "created": days_ago(random.randint(120, 200)).isoformat(),
            "last_updated": days_ago(d["last_updated_days_ago"]).isoformat(),
            "story_points_planned": d["story_points_planned"],
            "story_points_completed": d["story_points_completed"],
            "labels": d["labels"],
            "epic": init["name"],
            "comments_count": d["comments_count"],
            "owner_notes": _narrative_for(init),
            "budget_approved_usd": approved,
            "budget_spent_usd": spent,
        })
    with open(DATA_DIR / "wm_jira_export.json", "w") as f:
        json.dump(out, f, indent=2)
    return len(out)


def write_is_excel():
    import csv
    rows = []
    for init in [i for i in INITIATIVES if i["bu"] == "IB"]:
        d = init["is"]
        # Prepend narrative if provided -- otherwise just use the source notes
        notes_combined = _narrative_for(init) or d.get("notes", "")
        rows.append({
            "Initiative_Code": init["id"],
            "Initiative_Name": init["name"],
            "Description": init["description"],
            "Owner": init["owner"],
            "RAG_Status": d["rag"],
            "Q_Target": d["q_target"],
            "Budget_Approved_USD": d["budget_approved"],
            "Budget_Spent_USD": d["budget_spent"],
            "KPI_Target": d["kpi_target"],
            "KPI_Actual_Pct": d["kpi_actual_pct"],
            "Last_Review_Date": days_ago(d["last_review_days_ago"]).strftime("%m/%d/%Y"),
            "Notes": notes_combined,
        })
    with open(DATA_DIR / "is_quarterly_tracker.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def write_im_sharepoint():
    import csv
    rows = []
    for init in [i for i in INITIATIVES if i["bu"] == "AM"]:
        d = init["im"]
        approved, spent = _budget_for(init)
        go_live = (datetime.now() + timedelta(days=d["go_live_target_days_offset"])).strftime("%Y-%m-%d")
        rows.append({
            "id": init["id"],
            "title": init["name"],
            "summary": init["description"],
            "project_lead": init["owner"],
            "health": d["health"],
            "phase": d["phase"],
            "go_live_target": go_live,
            "% Complete": d["pct_complete"],
            "issues_open": d["issues_open"],
            "last_status_update": days_ago(d["last_status_update_days_ago"]).strftime("%Y-%m-%d"),
            "budget_approved": approved,
            "budget_actual": spent,
            "lead_commentary": _narrative_for(init),
        })
    with open(DATA_DIR / "im_sharepoint_status.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def write_tech_budget():
    import csv
    rows = []
    for init in [i for i in INITIATIVES if i["bu"] == "GF"]:
        d = init["tech"]
        rows.append({
            "project_id": init["id"],
            "project_name": init["name"],
            "description": init["description"],
            "owner": init["owner"],
            "fiscal_year": d["fiscal_year"],
            "approved_budget": d["approved_budget"],
            "ytd_spend": d["ytd_spend"],
            "headcount_allocated": d["headcount_allocated"],
            "vendor_dependencies": d["vendor_dependencies"],
            "current_state": d["current_state"],
            "milestone_status": d["milestone_status"],
            "owner_commentary": _narrative_for(init),
        })
    with open(DATA_DIR / "tech_coo_budget.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def _validator_pending_note(init):
    notes_by_story = {
        "stuck":       "Awaiting updated model documentation from owner. Multiple follow-ups sent; no response.",
        "disaster":    "Backtest results disputed by trading desk; need full re-run on Q4 2025 data with revised methodology.",
        "hidden_risk": "Need clarification on data lineage and prompt-injection mitigations before proceeding.",
        "watch":       "In review queue.",
        "stale":       "Submission incomplete -- waiting on owner to provide model card.",
        "normal":      "In review queue.",
        "regulatory":  "EU SFDR Level 2 alignment review in progress with Legal -- regulatory deadline limits flexibility.",
        "zombie":      "No active owner contact; previous owner departed firm. Initiative needs re-staffing before review can proceed.",
        "cross_bu":    "Joint WM + IB sponsorship -- review held pending alignment between the two BU heads on data-residency boundary.",
        "vendor_risk": "Vendor SLA breach under investigation; validator review on hold until vendor decision is finalized.",
        "reformed":    "",  # Reformed initiatives are approved -- no pending note
    }
    return notes_by_story.get(init.get("story", ""), "")


def write_approvals_log():
    log = []
    for init in INITIATIVES:
        # Validator entry
        if init.get("validator_pending_days"):
            submitted = days_ago(init["validator_pending_days"])
        elif init["validator_status"] == "approved" and init["validator_decision_days_ago"] is not None:
            submitted = days_ago(init["validator_decision_days_ago"] + random.randint(3, 8))
        elif init["validator_status"] == "pending":
            submitted = days_ago(random.randint(8, 20))
        else:
            submitted = days_ago(random.randint(2, 6))

        decision = (
            days_ago(init["validator_decision_days_ago"])
            if init["validator_decision_days_ago"] is not None
            else None
        )

        log.append({
            "initiative_id": init["id"],
            "approval_type": "validator",
            "approver": init["validator"],
            "status": init["validator_status"],
            "submitted_date": submitted.isoformat() if submitted else None,
            "decision_date": decision.isoformat() if decision else None,
            "notes": "" if init["validator_status"] == "approved" else _validator_pending_note(init),
        })

        # Sponsor entry only if validator approved
        if init["validator_status"] == "approved":
            if init["sponsor_decision_days_ago"] is not None:
                sponsor_submitted = days_ago(init["sponsor_decision_days_ago"] + random.randint(1, 3))
            else:
                sponsor_submitted = days_ago(random.randint(2, 7))
            sponsor_decision = (
                days_ago(init["sponsor_decision_days_ago"])
                if init["sponsor_decision_days_ago"] is not None
                else None
            )
            log.append({
                "initiative_id": init["id"],
                "approval_type": "senior_sponsor",
                "approver": SPONSORS[init["bu"]],
                "status": init["sponsor_status"],
                "submitted_date": sponsor_submitted.isoformat(),
                "decision_date": sponsor_decision.isoformat() if sponsor_decision else None,
                "notes": "" if init["sponsor_status"] == "approved" else "In sponsor's review queue",
            })

    with open(DATA_DIR / "approvals_log.json", "w") as f:
        json.dump(log, f, indent=2)
    return len(log)


def main():
    n_wm = write_wm_jira()
    n_ib = write_is_excel()
    n_am = write_im_sharepoint()
    n_gf = write_tech_budget()
    n_approvals = write_approvals_log()

    total = n_wm + n_ib + n_am + n_gf
    print(f"Generated story-shaped mock data in {DATA_DIR}")
    print(f"  WM Tech (Jira JSON):           {n_wm} initiatives")
    print(f"  IB Tech (Quarterly CSV):       {n_ib} initiatives")
    print(f"  AM Tech (SharePoint CSV):      {n_am} initiatives")
    print(f"  GF Tech (Budget CSV):          {n_gf} initiatives")
    print(f"  Approvals log:                 {n_approvals} sign-off records")
    print(f"  Total initiatives:             {total}")
    print()
    print("Story arcs embedded (LLM should surface these from notes, not hardcoded):")
    print("  Hero          -- WM Co-Pilot (production at 4,200 advisors, scaling to 8,000)")
    print("  Disaster      -- IB RFQ Auto-Pricing (185% over budget, 25% KPI)")
    print("  Hidden risk   -- GF AI Code Review (looks Active but slipping; HC inflated)")
    print("  Stuck         -- WM Onboarding (62 days, blocked on LLM-stack reuse approval)")
    print("  Stale         -- AM PM Chatbot (87 days no update, owner rotated)")
    print("  Quick win     -- GF Knowledge Search (cleared early, under budget)")
    print("  Reformed      -- IB Earnings Translation (was red, now reference template)")
    print("  Regulatory    -- AM Climate Risk (EU SFDR Level 2 hard deadline)")
    print("  Zombie        -- GF Legacy COBOL Bot (owner departed 6 months ago)")
    print("  Cross-BU      -- WM Cross-Border Tax AI (WM+IB joint, 142 comments)")
    print("  Vendor risk   -- IB Counterparty KYC (primary vendor SLA breach)")
    print("  Quiet success -- GF Procurement Analyzer (under-radar delivery)")
    print("  Normal scaling-- WM Compliance Co-Pilot (pilot → prod), AM ESG Voting")
    print("  Bottleneck    -- person_005 holds majority of pending Risk reviews")


if __name__ == "__main__":
    main()
