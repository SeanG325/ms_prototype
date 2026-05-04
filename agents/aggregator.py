"""
Data Aggregator Agent
=====================
Pulls from 4 fragmented sources (Jira-like JSON, Excel-like CSV, SharePoint-like
CSV, budget tracker CSV) plus the approvals log, and produces a single canonical
Initiative dataset.

This is the "stop manually stitching spreadsheets together" agent.
"""
import csv
import json
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

DATA_DIR = Path(__file__).parent.parent / "data"


# ---------------------------------------------------------------------------
# Canonical model -- the unified schema leadership actually wants
# ---------------------------------------------------------------------------
@dataclass
class Initiative:
    id: str
    name: str
    description: str
    business_unit: str           # WM, IB, AM, GF
    business_unit_full: str
    owner: str
    senior_sponsor: str
    status_normalized: str       # On Track | At Risk | Off Track | Complete | Planning
    status_raw: str              # original status from source system
    source_system: str
    budget_approved: float
    budget_spent: float
    budget_utilization_pct: float
    kpi_target: str
    kpi_actual_pct: int          # 0-100+ (>100 means exceeding target)
    last_updated: str
    notes: str
    # Approval chain
    validator: Optional[str] = None
    validator_status: str = "not_submitted"
    validator_decision_date: Optional[str] = None
    validator_pending_days: Optional[int] = None  # how long validator review has been pending
    sponsor_status: str = "not_submitted"
    sponsor_decision_date: Optional[str] = None
    sponsor_pending_days: Optional[int] = None
    # Computed risk fields (filled by analyst agent)
    risk_score: float = 0.0
    risk_flags: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Status normalization -- the "translation layer" across vocabularies
# ---------------------------------------------------------------------------
STATUS_MAP = {
    # Jira-like
    "in progress": "On Track",
    "blocked": "Off Track",
    "done": "Complete",
    "backlog": "Planning",
    "in review": "On Track",
    # Excel RAG
    "green": "On Track",
    "amber": "At Risk",
    "red": "Off Track",
    "complete": "Complete",
    "not started": "Planning",
    # SharePoint
    "on track": "On Track",
    "at risk": "At Risk",
    "off track": "Off Track",
    "delivered": "Complete",
    "planning": "Planning",
    # Tech budget tracker
    "active": "On Track",
    "paused": "Off Track",
    "under review": "At Risk",
}

BU_FULL_NAMES = {
    "WM": "Wealth Management Technology",
    "IB": "Investment Bank Technology",
    "AM": "Asset Management Technology",
    "GF": "Group Functions Technology",
}

SPONSORS = {
    "WM": "person_001 (Head of Wealth Management Technology)",
    "IB": "person_002 (Head of Investment Bank Technology)",
    "AM": "person_003 (Head of Asset Management Technology)",
    "GF": "person_004 (Head of Group Functions Technology)",
}


def normalize_status(raw: str) -> str:
    return STATUS_MAP.get(raw.strip().lower(), "On Track")


# ---------------------------------------------------------------------------
# Per-source loaders
# ---------------------------------------------------------------------------
def load_wm() -> List[Initiative]:
    with open(DATA_DIR / "wm_jira_export.json") as f:
        data = json.load(f)
    out = []
    for r in data:
        sp_pct = (r["story_points_completed"] / r["story_points_planned"] * 100) if r["story_points_planned"] else 0
        notes_parts = [f"Priority {r['priority']}, {r['comments_count']} comments"]
        if r.get("owner_notes"):
            notes_parts.append(r["owner_notes"])
        approved = float(r.get("budget_approved_usd") or 0)
        spent = float(r.get("budget_spent_usd") or 0)
        out.append(Initiative(
            id=r["ticket_id"],
            name=r["summary"],
            description=r["description"],
            business_unit="WM",
            business_unit_full=BU_FULL_NAMES["WM"],
            owner=r["assignee"],
            senior_sponsor=SPONSORS["WM"],
            status_normalized=normalize_status(r["status"]),
            status_raw=r["status"],
            source_system="WM Jira (JSON)",
            budget_approved=approved,
            budget_spent=spent,
            budget_utilization_pct=(spent / approved * 100) if approved else 0,
            kpi_target=f"Complete {r['story_points_planned']} story points",
            kpi_actual_pct=int(sp_pct),
            last_updated=r["last_updated"][:10],
            notes=" | ".join(notes_parts),
        ))
    return out


def load_ib() -> List[Initiative]:
    out = []
    with open(DATA_DIR / "is_quarterly_tracker.csv") as f:
        for r in csv.DictReader(f):
            approved = float(r["Budget_Approved_USD"])
            spent = float(r["Budget_Spent_USD"])
            out.append(Initiative(
                id=r["Initiative_Code"],
                name=r["Initiative_Name"],
                description=r["Description"],
                business_unit="IB",
                business_unit_full=BU_FULL_NAMES["IB"],
                owner=r["Owner"],
                senior_sponsor=SPONSORS["IB"],
                status_normalized=normalize_status(r["RAG_Status"]),
                status_raw=r["RAG_Status"],
                source_system="IB Tech Quarterly Tracker (Excel/CSV)",
                budget_approved=approved,
                budget_spent=spent,
                budget_utilization_pct=(spent / approved * 100) if approved else 0,
                kpi_target=r["KPI_Target"],
                kpi_actual_pct=int(r["KPI_Actual_Pct"]),
                last_updated=datetime.strptime(r["Last_Review_Date"], "%m/%d/%Y").strftime("%Y-%m-%d"),
                notes=r["Notes"],
            ))
    return out


def load_am() -> List[Initiative]:
    out = []
    with open(DATA_DIR / "im_sharepoint_status.csv") as f:
        for r in csv.DictReader(f):
            notes_parts = [f"Phase: {r['phase']}, {r['issues_open']} open issues"]
            if r.get("lead_commentary"):
                notes_parts.append(r["lead_commentary"])
            approved = float(r.get("budget_approved") or 0)
            spent = float(r.get("budget_actual") or 0)
            out.append(Initiative(
                id=r["id"],
                name=r["title"],
                description=r["summary"],
                business_unit="AM",
                business_unit_full=BU_FULL_NAMES["AM"],
                owner=r["project_lead"],
                senior_sponsor=SPONSORS["AM"],
                status_normalized=normalize_status(r["health"]),
                status_raw=r["health"],
                source_system="AM Tech SharePoint (CSV)",
                budget_approved=approved,
                budget_spent=spent,
                budget_utilization_pct=(spent / approved * 100) if approved else 0,
                kpi_target=f"Reach {r['phase']} phase by {r['go_live_target']}",
                kpi_actual_pct=int(r["% Complete"]),
                last_updated=r["last_status_update"],
                notes=" | ".join(notes_parts),
            ))
    return out


def load_gf() -> List[Initiative]:
    out = []
    with open(DATA_DIR / "tech_coo_budget.csv") as f:
        for r in csv.DictReader(f):
            approved = float(r["approved_budget"])
            spent = float(r["ytd_spend"])
            # Combine state + milestone for richer status
            status_raw = r["current_state"]
            normalized = normalize_status(status_raw)
            if "behind" in r["milestone_status"]:
                normalized = "At Risk" if "1-2 weeks" in r["milestone_status"] else "Off Track"
            notes_parts = [f"{r['headcount_allocated']} FTE, vendors: {r['vendor_dependencies']}"]
            if r.get("owner_commentary"):
                notes_parts.append(r["owner_commentary"])
            out.append(Initiative(
                id=r["project_id"],
                name=r["project_name"],
                description=r["description"],
                business_unit="GF",
                business_unit_full=BU_FULL_NAMES["GF"],
                owner=r["owner"],
                senior_sponsor=SPONSORS["GF"],
                status_normalized=normalized,
                status_raw=f"{r['current_state']} / {r['milestone_status']}",
                source_system="GF Tech Budget Tracker (CSV)",
                budget_approved=approved,
                budget_spent=spent,
                budget_utilization_pct=(spent / approved * 100) if approved else 0,
                kpi_target=r["milestone_status"],
                kpi_actual_pct=int(min(100, (spent / approved * 100))) if approved else 0,
                last_updated=datetime.now().strftime("%Y-%m-%d"),
                notes=" | ".join(notes_parts),
            ))
    return out


def merge_approvals(initiatives: List[Initiative]) -> List[Initiative]:
    with open(DATA_DIR / "approvals_log.json") as f:
        approvals = json.load(f)
    by_id: Dict[str, List[dict]] = {}
    for a in approvals:
        by_id.setdefault(a["initiative_id"], []).append(a)

    now = datetime.now()
    for init in initiatives:
        records = by_id.get(init.id, [])
        for rec in records:
            # Compute pending duration from submitted_date for any "pending" record
            pending_days = None
            if rec["status"] == "pending" and rec.get("submitted_date"):
                try:
                    submitted = datetime.fromisoformat(rec["submitted_date"])
                    pending_days = (now - submitted).days
                except (ValueError, TypeError):
                    pass

            if rec["approval_type"] == "validator":
                init.validator = rec["approver"]
                init.validator_status = rec["status"]
                init.validator_decision_date = rec["decision_date"]
                init.validator_pending_days = pending_days
            elif rec["approval_type"] == "senior_sponsor":
                init.sponsor_status = rec["status"]
                init.sponsor_decision_date = rec["decision_date"]
                init.sponsor_pending_days = pending_days
    return initiatives


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
class DataAggregatorAgent:
    """Run all loaders, normalize, merge approvals."""

    def __init__(self):
        from .logger import get_logger
        self._log = get_logger("DataAggregator")

    def run(self) -> List[Initiative]:
        self._log.info("Starting aggregation of fragmented data sources")

        with self._log.timed("Loading WM Tech Jira (JSON)"):
            wm = load_wm()
            self._log.info(f"  WM (Wealth Management) source loaded", initiatives=len(wm))

        with self._log.timed("Loading IB Tech Quarterly Tracker (CSV)"):
            ib = load_ib()
            self._log.info(f"  IB (Investment Bank) source loaded", initiatives=len(ib))

        with self._log.timed("Loading AM Tech SharePoint (CSV)"):
            am = load_am()
            self._log.info(f"  AM (Asset Management) source loaded", initiatives=len(am))

        with self._log.timed("Loading GF Tech Budget Tracker (CSV)"):
            gf = load_gf()
            self._log.info(f"  GF (Group Functions) source loaded", initiatives=len(gf))

        all_initiatives = wm + ib + am + gf
        self._log.info(
            f"Normalized to canonical schema",
            total=len(all_initiatives),
            sources=4,
            status_vocabularies_unified=3,
        )

        with self._log.timed("Merging approvals log"):
            all_initiatives = merge_approvals(all_initiatives)

        # Sanity-check warnings
        no_validator = [i.id for i in all_initiatives if not i.validator]
        if no_validator:
            self._log.warning(
                f"{len(no_validator)} initiative(s) have no assigned validator",
                ids=", ".join(no_validator[:5]),
            )

        return all_initiatives

    def run_as_dicts(self) -> List[dict]:
        return [asdict(i) for i in self.run()]


if __name__ == "__main__":
    agent = DataAggregatorAgent()
    inits = agent.run()
    print(f"Aggregated {len(inits)} initiatives from 4 source systems\n")
    for i in inits[:3]:
        print(f"  [{i.id}] {i.name}")
        print(f"    BU: {i.business_unit_full} | Status: {i.status_normalized} (raw: {i.status_raw})")
        print(f"    Owner: {i.owner} | Validator: {i.validator_status} | Sponsor: {i.sponsor_status}")
        print()
