"""
Orchestrator
============
The agentic glue. One call, full pipeline:

    1. Data Aggregator  →  pull from 4 fragmented systems, normalize
    2. Risk Analyst     →  deterministic scoring + LLM narrative
    3. Accountability   →  detect bottlenecks, draft escalations
    4. Briefing         →  generate executive narrative
    5. Q&A              →  available on demand for chat

Streamlit UI calls this once on load and caches the result.
"""
from dataclasses import dataclass
from typing import List, Dict
from .aggregator import DataAggregatorAgent, Initiative
from .analyst import RiskAnalystAgent
from .accountability import AccountabilityAgent
from .briefing import BriefingAgent, QAAgent


@dataclass
class PortfolioState:
    initiatives: List[Initiative]
    signoff_summary: Dict
    validator_workload: List
    escalations: List[Dict]
    accountability_narrative: str
    accountability_structured: Dict     # JSON-shaped accountability narrative for table/card UI
    executive_briefing: str
    structured_briefing: Dict           # JSON-shaped briefing for table/card UI
    source_systems: List[str]
    # Trace of agent activity for the "Agent Activity" panel
    activity_log: List[Dict]
    # Wall-clock time of this pipeline run (for meta-monitoring / ROI tab)
    pipeline_elapsed_s: float = 0.0


class Orchestrator:
    def __init__(self, generate_briefing: bool = True, generate_narratives: bool = True):
        from .logger import get_logger
        self._log = get_logger("Orchestrator")
        self.aggregator = DataAggregatorAgent()
        self.analyst = RiskAnalystAgent()
        self.accountability = AccountabilityAgent()
        self.briefing = BriefingAgent()
        self.qa = QAAgent()
        self.generate_briefing = generate_briefing
        self.generate_narratives = generate_narratives

    def run(self) -> PortfolioState:
        import time as _time
        t_start = _time.time()
        self._log.info(
            "═══ Pipeline run started",
            generate_briefing=self.generate_briefing,
            generate_narratives=self.generate_narratives,
        )
        log = []

        # Step 1: aggregate
        log.append({
            "agent": "Data Aggregator",
            "action": "Pulling from fragmented sources",
            "detail": "WM Tech Jira (JSON), IB Tech Quarterly Tracker (CSV), AM Tech SharePoint (CSV), GF Tech Budget Tracker (CSV), Approvals Log (JSON)",
        })
        initiatives = self.aggregator.run()
        log.append({
            "agent": "Data Aggregator",
            "action": "Normalized to canonical schema",
            "detail": f"{len(initiatives)} initiatives unified across 4 source systems with 3 different status vocabularies",
        })

        # Step 2: score risk
        log.append({
            "agent": "Risk Analyst",
            "action": "Computing deterministic risk scores",
            "detail": "7-factor weighted model: status, budget overrun severity, KPI/burn gap, validator pending duration, sponsor delay, staleness, KPI underperformance",
        })
        self.analyst.score_all(initiatives)
        critical_count = sum(1 for i in initiatives if i.risk_score >= 76)
        at_risk_count = sum(1 for i in initiatives if 51 <= i.risk_score < 76)
        log.append({
            "agent": "Risk Analyst",
            "action": "Risk classification complete",
            "detail": f"{critical_count} Critical, {at_risk_count} At Risk",
        })

        # Step 3: accountability
        log.append({
            "agent": "Accountability",
            "action": "Mapping approval chain status",
            "detail": "Tracking validator + sponsor sign-offs per initiative",
        })
        signoff_summary = self.accountability.signoff_summary(initiatives)
        validator_workload = self.accountability.validator_workload(initiatives)
        escalations = self.accountability.draft_escalations(initiatives)
        log.append({
            "agent": "Accountability",
            "action": "Drafted escalation messages",
            "detail": f"{len(escalations)} escalation(s) drafted, awaiting COO review",
        })

        # Step 3 & 4 (parallelized): accountability narrative + structured briefing.
        # Both are I/O bound LLM calls, run concurrently. Markdown briefing is
        # derived from the structured JSON — no separate LLM call needed.
        # Sequential before: ~12-15s on real LLM. Parallel + derived: ~3-5s.
        from concurrent.futures import ThreadPoolExecutor

        def _run_acc_narrative():
            return self.accountability.narrative_structured(initiatives) if self.generate_narratives else {}

        def _run_briefing_structured():
            return self.briefing.generate_structured(initiatives) if self.generate_briefing else {}

        if self.generate_narratives or self.generate_briefing:
            log.append({
                "agent": "Briefing + Accountability",
                "action": "Generating narratives in parallel",
                "detail": "2 concurrent LLM calls (structured briefing + accountability)",
            })
            with ThreadPoolExecutor(max_workers=2) as pool:
                f_acc      = pool.submit(_run_acc_narrative)
                f_brief_s  = pool.submit(_run_briefing_structured)
                accountability_structured = f_acc.result()
                structured_briefing       = f_brief_s.result()
            # Markdown export is derived from the structured JSON — no LLM call
            executive_briefing = self.briefing.generate_markdown_from_structured(structured_briefing) if self.generate_briefing else ""
        else:
            accountability_structured = {}
            structured_briefing = {}
            executive_briefing = ""

        # Free-form accountability text is no longer used in the UI; dropped to
        # save one LLM call. Kept as empty string for backward-compat in
        # PortfolioState consumers.
        accountability_narrative = ""

        # Log pipeline summary
        from .llm_client import get_client as _gc
        llm = _gc()
        elapsed = _time.time() - t_start
        self._log.info(
            "═══ Pipeline run complete",
            elapsed_s=f"{elapsed:.2f}",
            initiatives=len(initiatives),
            escalations=len(escalations),
            llm_calls=llm.total_calls,
            llm_fallbacks=llm.fallback_count,
        )
        if llm.fallback_count > 0:
            self._log.warning(
                f"{llm.fallback_count} LLM call(s) fell back to mock during this run",
                hint="Check API key and network connectivity",
            )

        return PortfolioState(
            initiatives=initiatives,
            signoff_summary=signoff_summary,
            validator_workload=validator_workload,
            escalations=escalations,
            accountability_narrative=accountability_narrative,
            accountability_structured=accountability_structured,
            executive_briefing=executive_briefing,
            structured_briefing=structured_briefing,
            source_systems=[
                "WM Tech Jira (JSON)",
                "IB Tech Quarterly Tracker (Excel/CSV)",
                "AM Tech SharePoint (CSV)",
                "GF Tech Budget Tracker (CSV)",
                "Approvals Log (JSON)",
            ],
            activity_log=log,
            pipeline_elapsed_s=elapsed,
        )

    def answer_question(self, question: str, initiatives: List[Initiative]) -> str:
        return self.qa.answer(question, initiatives)


if __name__ == "__main__":
    state = Orchestrator(generate_briefing=False, generate_narratives=False).run()
    print(f"Initiatives: {len(state.initiatives)}")
    print(f"Escalations drafted: {len(state.escalations)}")
    print(f"Activity log entries: {len(state.activity_log)}")
    for e in state.activity_log:
        print(f"  [{e['agent']}] {e['action']}: {e['detail']}")
