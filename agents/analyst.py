"""
Risk Analyst Agent
==================
Layered analysis:
  1. Deterministic scoring (no LLM)  -- transparent, auditable, reproducible
  2. LLM narrative explanation       -- the "why" leadership wants to read

The deterministic layer is critical: in a regulated firm like Morgan Stanley,
the risk score itself cannot come from a black-box LLM. The LLM only narrates.
"""
from typing import List, Tuple
from datetime import datetime, timedelta
from .aggregator import Initiative
from .llm_client import get_client


# ---------------------------------------------------------------------------
# Scoring rules -- transparent, weighted
# ---------------------------------------------------------------------------
def score_initiative(init: Initiative) -> Tuple[float, List[str]]:
    """
    Returns (risk_score 0..100, list_of_human_readable_flags).

    Higher score = higher risk. Score buckets:
        0-25   Healthy
        26-50  Watch
        51-75  At Risk
        76-100 Critical
    """
    score = 0.0
    flags: List[str] = []

    # --- Status signal (heavy weight) ----------------------------------------
    if init.status_normalized == "Off Track":
        score += 35
        flags.append("Status: Off Track in source system")
    elif init.status_normalized == "At Risk":
        score += 20
        flags.append("Status: At Risk in source system")

    # --- Budget overrun (graduated severity) ---------------------------------
    if init.budget_approved > 0:
        util = init.budget_utilization_pct
        if util > 150:
            score += 35
            flags.append(f"SEVERE budget overrun: {util:.0f}% of approved spent (${init.budget_spent - init.budget_approved:,.0f} over)")
        elif util > 110:
            score += 22
            flags.append(f"Budget overrun: {util:.0f}% of approved spent")
        elif util > 95:
            score += 10
            flags.append(f"Budget pressure: {util:.0f}% of approved spent")

    # --- KPI vs budget gap (the "burning money for nothing" signal) ---------
    if init.budget_approved > 0 and init.budget_utilization_pct > 100 and init.kpi_actual_pct < 40:
        score += 25
        flags.append(f"Spending past budget while KPI tracks at {init.kpi_actual_pct}% -- burning money without delivery")
    elif init.budget_approved > 0 and init.budget_utilization_pct > 80 and init.kpi_actual_pct < 50:
        score += 15
        flags.append("Burn rate exceeds delivery rate")

    # --- Approval chain stuck (graduated by how long it's been stuck) -------
    if init.validator_status == "pending":
        days = init.validator_pending_days or 0
        if days >= 45:
            score += 22
            flags.append(f"Validator sign-off pending {days} days -- chain is dead ({init.validator})")
        elif days >= 21:
            score += 14
            flags.append(f"Validator sign-off pending {days} days ({init.validator})")
        else:
            score += 7
            flags.append(f"Validator sign-off pending ({init.validator})")
    if init.validator_status == "approved" and init.sponsor_status == "pending":
        score += 8
        flags.append("Senior sponsor sign-off pending")
    if init.validator_status == "not_submitted":
        score += 8
        flags.append("Validator review not yet initiated")

    # --- Stale data ----------------------------------------------------------
    try:
        last = datetime.strptime(init.last_updated, "%Y-%m-%d")
        days = (datetime.now() - last).days
        if days > 60:
            score += 18
            flags.append(f"Severely stale: last updated {days} days ago")
        elif days > 30:
            score += 8
            flags.append(f"Stale: last updated {days} days ago")
    except (ValueError, TypeError):
        pass

    # --- KPI underperformance -----------------------------------------------
    if init.kpi_actual_pct < 30:
        score += 12
        flags.append(f"KPI tracking at {init.kpi_actual_pct}% of target")

    return min(100.0, score), flags


def risk_bucket(score: float) -> str:
    if score >= 76: return "Critical"
    if score >= 51: return "At Risk"
    if score >= 26: return "Watch"
    return "Healthy"


# ---------------------------------------------------------------------------
# Public agent
# ---------------------------------------------------------------------------
class RiskAnalystAgent:
    def __init__(self):
        from .logger import get_logger
        self._log = get_logger("RiskAnalyst")
        self.llm = get_client()

    def score_all(self, initiatives: List[Initiative]) -> List[Initiative]:
        """Mutate-in-place: assign risk_score and risk_flags."""
        self._log.info(
            f"Scoring {len(initiatives)} initiatives with deterministic 7-factor model",
            factors="status, budget_overrun, kpi_burn_gap, validator_pending_duration, sponsor_delay, staleness, kpi_under",
        )
        bucket_counts = {"Healthy": 0, "Watch": 0, "At Risk": 0, "Critical": 0}
        for init in initiatives:
            score, flags = score_initiative(init)
            init.risk_score = score
            init.risk_flags = flags
            bucket = risk_bucket(score)
            bucket_counts[bucket] += 1
            # Log only the high-risk ones to avoid noise
            if score >= 51:
                self._log.warning(
                    f"  {bucket}: {init.name} ({init.business_unit})",
                    score=f"{score:.0f}",
                    flag_count=len(flags),
                )
            else:
                self._log.debug(f"  {bucket}: {init.name} = {score:.0f}")
        self._log.info(
            f"Risk classification complete",
            critical=bucket_counts["Critical"],
            at_risk=bucket_counts["At Risk"],
            watch=bucket_counts["Watch"],
            healthy=bucket_counts["Healthy"],
        )
        return initiatives

    def explain(self, init: Initiative) -> dict:
        """
        Structured LLM narrative -- returns dict with:
          {
            "assessment": "1-2 sentence overall read",
            "strengths": [{"point": "...", "evidence": "..."}],
            "risks":     [{"point": "...", "evidence": "...", "severity": "Low|Medium|High"}],
            "next_step": {"recommendation": "...", "owner": "...", "by_when": "..."}
          }
        Tone is intentionally measured -- a healthy initiative should not have
        manufactured concerns. The bar for adding a risk is real evidence in
        the data, not speculation.
        """
        self._log.info(f"Generating LLM narrative", initiative=init.name, score=f"{init.risk_score:.0f}")

        # Determine tone guidance based on actual risk bucket
        bucket = risk_bucket(init.risk_score)
        if bucket == "Healthy":
            tone_guidance = (
                "This initiative is performing well. Lead with what's working. "
                "Only flag risks that are clearly evidenced in the data -- if there are no "
                "real risk signals, the risks array can be empty or contain a single 'no material concerns' note. "
                "Do NOT manufacture concerns to seem rigorous."
            )
        elif bucket == "Watch":
            tone_guidance = (
                "This initiative is mostly on track with mild watchpoints. Acknowledge what's working "
                "before discussing concerns. Risks should be specific and evidenced, not speculative."
            )
        elif bucket == "At Risk":
            tone_guidance = (
                "This initiative has real concerns that need attention. Be direct about the issues "
                "but professional -- the goal is to help the team recover, not to assign blame. "
                "Still acknowledge any genuine strengths if present."
            )
        else:  # Critical
            tone_guidance = (
                "This initiative has serious problems requiring immediate action. Be direct and clear "
                "about the issues. Even here, acknowledge any genuine strengths (e.g. owner responsiveness) "
                "if visible in the data. The recommendation should be a single concrete action."
            )

        prompt = f"""You are a senior risk analyst preparing a structured assessment for the Technology COO.
Output ONLY valid JSON (no prose, no markdown fences) matching this exact schema:

{{
  "assessment": "1-2 sentences -- the overall read on this initiative, balanced and professional",
  "strengths": [
    {{"point": "short label", "evidence": "specific evidence from the data"}}
  ],
  "risks": [
    {{"point": "short label", "evidence": "specific evidence from the data", "severity": "Low|Medium|High"}}
  ],
  "next_step": {{
    "recommendation": "one specific action to take this week",
    "owner": "who should do it",
    "by_when": "specific deadline like 'EOW' or 'next sprint review'"
  }}
}}

TONE GUIDANCE FOR THIS SPECIFIC INITIATIVE:
{tone_guidance}

Rules for the strengths/risks arrays:
- Strengths: 1-3 items. Cite specific evidence (KPI %, budget number, validator status).
- Risks: 0-3 items. Each risk MUST be backed by evidence from the data below -- not
  speculation, not generic LLM-project concerns. If there are no material risks, return
  an empty array or a single item with severity "Low" noting "no material concerns".
- Severity: "High" only when there's clear material impact; "Medium" for things needing
  attention; "Low" for minor watchpoints.

Initiative data:
- Name: {init.name}
- Business unit: {init.business_unit_full}
- Owner: {init.owner}
- Senior sponsor: {init.senior_sponsor}
- Description: {init.description}
- Risk score: {init.risk_score:.0f}/100 ({bucket})
- Normalized status: {init.status_normalized}
- KPI target: {init.kpi_target}
- KPI actual: {init.kpi_actual_pct}% of target
- Budget approved: ${init.budget_approved:,.0f}
- Budget spent: ${init.budget_spent:,.0f} ({init.budget_utilization_pct:.0f}% utilization)
- Validator: {init.validator or "unassigned"} ({init.validator_status})
- Sponsor sign-off: {init.sponsor_status}
- Owner's notes: {init.notes}

Deterministic risk flags (from automated scoring -- these are the ONLY factual risk signals):
{chr(10).join('  - ' + f for f in init.risk_flags) if init.risk_flags else '  (none)'}
"""
        raw = self.llm.complete(
            prompt,
            system="You are a measured, balanced risk analyst. You output only valid JSON.",
            max_tokens=900,
        )
        return self._parse_json(raw, fallback_assessment=f"Assessment unavailable for {init.name}.")

    def _parse_json(self, raw: str, fallback_assessment: str = "") -> dict:
        """Robust JSON parse -- same pattern as Briefing/Accountability."""
        import json, re
        s = raw.strip()
        if s.startswith("```"):
            s = re.sub(r"^```(?:json)?\s*", "", s)
            s = re.sub(r"\s*```$", "", s)
        first = s.find("{")
        last = s.rfind("}")
        if first != -1 and last != -1 and last > first:
            s = s[first : last + 1]
        try:
            return json.loads(s)
        except json.JSONDecodeError as e:
            self._log.warning(
                "Failed to parse risk-explain JSON -- using fallback",
                error=str(e)[:120],
            )
            return {
                "assessment": fallback_assessment,
                "strengths": [],
                "risks": [],
                "next_step": {"recommendation": "", "owner": "", "by_when": ""},
                "_raw_fallback": raw,
            }


if __name__ == "__main__":
    from .aggregator import DataAggregatorAgent
    inits = DataAggregatorAgent().run()
    analyst = RiskAnalystAgent()
    analyst.score_all(inits)
    inits.sort(key=lambda x: x.risk_score, reverse=True)
    print("Top 5 highest-risk initiatives:\n")
    for i in inits[:5]:
        print(f"  [{i.id}] {i.name}")
        print(f"    Score: {i.risk_score:.0f} ({risk_bucket(i.risk_score)})")
        for f in i.risk_flags:
            print(f"      - {f}")
        print()
