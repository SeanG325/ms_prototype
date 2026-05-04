"""
Briefing Agent + Q&A Agent
==========================
- BriefingAgent: produces the monthly executive briefing (replaces static slides)
- QAAgent: answers ad-hoc questions over the portfolio (replaces "let me get back to you")
"""
from typing import List
from .aggregator import Initiative
from .analyst import risk_bucket
from .llm_client import get_client


def _portfolio_facts(initiatives: List[Initiative]) -> str:
    """Compact, factual summary of the portfolio used as LLM context."""
    by_bu = {}
    for i in initiatives:
        by_bu.setdefault(i.business_unit_full, []).append(i)

    lines = []
    total_approved = sum(i.budget_approved for i in initiatives)
    total_spent = sum(i.budget_spent for i in initiatives)
    lines.append(f"Total initiatives: {len(initiatives)}")
    lines.append(f"Total approved budget (where tracked): ${total_approved:,.0f}")
    lines.append(f"Total spend YTD: ${total_spent:,.0f}")
    lines.append("")

    for bu, items in by_bu.items():
        lines.append(f"## {bu} ({len(items)} initiatives)")
        for i in items:
            line = (
                f"  - [{i.id}] {i.name} | Status: {i.status_normalized} | "
                f"Risk: {i.risk_score:.0f} ({risk_bucket(i.risk_score)}) | "
                f"KPI: {i.kpi_actual_pct}% | Owner: {i.owner} | "
                f"Validator: {i.validator_status} | Sponsor: {i.sponsor_status}"
            )
            if i.budget_approved:
                line += f" | Budget: ${i.budget_spent:,.0f}/${i.budget_approved:,.0f}"
            lines.append(line)
            if i.risk_flags:
                lines.append(f"      flags: {'; '.join(i.risk_flags)}")
        lines.append("")
    return "\n".join(lines)


class BriefingAgent:
    """Generates the executive briefing that replaces static monthly slides."""

    def __init__(self):
        from .logger import get_logger
        self._log = get_logger("BriefingAgent")
        self.llm = get_client()

    def generate(self, initiatives: List[Initiative]) -> str:
        """
        Free-form markdown briefing for export. Derived from the same structured
        briefing data — no separate LLM call. Saves one round-trip and ensures
        the markdown export and the UI cards stay in sync.
        """
        sb = self.generate_structured(initiatives)
        return self._structured_to_markdown(sb)

    def generate_markdown_from_structured(self, structured: dict) -> str:
        """
        Public helper -- given an already-computed structured briefing dict,
        produce the markdown export. Use this when the orchestrator has
        already generated structured output and wants to avoid a duplicate.
        """
        return self._structured_to_markdown(structured)

    def _structured_to_markdown(self, sb: dict) -> str:
        """Render the structured briefing JSON as the same markdown shape used historically."""
        if not sb or sb.get("_raw_fallback"):
            return sb.get("_raw_fallback", "Briefing generation failed.")

        out = []
        if sb.get("headline"):
            out.append("**Headline**")
            out.append(sb["headline"])
            out.append("")

        if sb.get("working"):
            out.append("**What's working**")
            for w in sb["working"]:
                bu = w.get("bu", "")
                init = w.get("initiative", "")
                why = w.get("why", "")
                out.append(f"- **{init}** ({bu}, owner: {w.get('owner', '—')}) — {why}")
            out.append("")

        if sb.get("not_working"):
            out.append("**What's not working**")
            for nw in sb["not_working"]:
                bu = nw.get("bu", "")
                init = nw.get("initiative", "")
                sev = nw.get("severity", "")
                issue = nw.get("issue", "")
                out.append(f"- **{init}** ({bu}, owner: {nw.get('owner', '—')}) — *{sev}* — {issue}")
            out.append("")

        if sb.get("accountability"):
            out.append("**Who's accountable for the gaps**")
            for a in sb["accountability"]:
                out.append(f"- {a.get('initiative', '')}: owner {a.get('owner', '—')}, sponsor {a.get('sponsor', '—')}, validator {a.get('validator', '—')}")
            out.append("")

        if sb.get("decisions"):
            out.append("**Recommended decisions for this meeting**")
            for i, d in enumerate(sb["decisions"], 1):
                decision = d.get("decision", "")
                rationale = d.get("rationale", "")
                owner = d.get("owner", "")
                out.append(f"{i}. **{decision}**")
                if rationale:
                    out.append(f"   - *Rationale:* {rationale}")
                if owner:
                    out.append(f"   - *Owner:* {owner}")
            out.append("")

        return "\n".join(out)

    def generate_structured(self, initiatives: List[Initiative]) -> dict:
        """
        Returns a structured dict the UI can render as tables/cards:

        {
          "headline": "...",
          "portfolio_health": {"critical": N, "at_risk": N, "watch": N, "healthy": N},
          "working": [{"initiative": "...", "bu": "WM", "owner": "...", "why": "..."}],
          "not_working": [{"initiative": "...", "bu": "...", "owner": "...", "issue": "...",
                           "severity": "Critical|At Risk"}],
          "accountability": [{"person": "...", "role": "Owner|Sponsor|Validator", "owns": "...",
                              "action_needed": "..."}],
          "decisions": [{"id": 1, "decision": "...", "rationale": "...", "owner": "..."}]
        }
        """
        self._log.info(f"Generating structured briefing (JSON)", initiative_count=len(initiatives))
        facts = _portfolio_facts(initiatives)

        # Pre-compute portfolio_health from the data so it's never wrong even if LLM
        # hallucinates. The LLM populates the qualitative fields only.
        from .analyst import risk_bucket
        bucket_counts = {"Critical": 0, "At Risk": 0, "Watch": 0, "Healthy": 0}
        for i in initiatives:
            bucket_counts[risk_bucket(i.risk_score)] += 1

        prompt = f"""You are preparing the monthly AI Initiatives Briefing for Morgan Stanley's
Technology COO. Output ONLY valid JSON (no prose, no markdown fences) matching this exact schema:

{{
  "headline": "2 sentences, the single most important thing for leaders to know",
  "working": [
    {{"initiative": "name", "bu": "WM|IB|AM|GF", "owner": "name", "why": "1 specific sentence why this is succeeding"}}
  ],
  "not_working": [
    {{"initiative": "name", "bu": "WM|IB|AM|GF", "owner": "name", "severity": "Critical|At Risk", "issue": "1 specific sentence describing the actual problem with numbers"}}
  ],
  "accountability": [
    {{"person": "name", "role": "Owner|Sponsor|Validator", "owns": "what they're responsible for", "action_needed": "specific action this week"}}
  ],
  "decisions": [
    {{"id": 1, "decision": "decision-shaped item leaders can approve or reject", "rationale": "1 sentence why now", "owner": "who would execute"}}
  ]
}}

Rules:
- 2-3 items in working, 2-3 in not_working, 2-3 in accountability, exactly 3 decisions.
- Be specific: name initiatives, names of people, and numbers ($, %, days).
- Be opinionated: if a budget should be reallocated, say so. If a person is the bottleneck, say so by name.
- Do NOT include the portfolio_health field -- it will be added programmatically.

Portfolio facts:
{facts}
"""
        raw = self.llm.complete(
            prompt,
            system="You are a precise, opinionated executive briefer. You output only valid JSON.",
            max_tokens=2000,
        )
        parsed = self._parse_json(raw)
        # Always inject the deterministic portfolio_health
        parsed["portfolio_health"] = bucket_counts
        self._log.info(
            f"Structured briefing generated",
            working=len(parsed.get("working", [])),
            not_working=len(parsed.get("not_working", [])),
            decisions=len(parsed.get("decisions", [])),
        )
        return parsed

    def _parse_json(self, raw: str) -> dict:
        """
        Robust JSON parsing -- handles common LLM quirks:
          - markdown fences (```json ... ```)
          - leading/trailing prose
          - missing top-level braces
        Falls back to a minimal structure if parsing fails so the UI never crashes.
        """
        import json, re
        s = raw.strip()
        # Strip ```json fences if present
        if s.startswith("```"):
            s = re.sub(r"^```(?:json)?\s*", "", s)
            s = re.sub(r"\s*```$", "", s)
        # Find first { ... last }
        first = s.find("{")
        last = s.rfind("}")
        if first != -1 and last != -1 and last > first:
            s = s[first : last + 1]
        try:
            return json.loads(s)
        except json.JSONDecodeError as e:
            self._log.warning(
                "Failed to parse LLM JSON briefing -- using fallback structure",
                error=str(e)[:120],
                raw_preview=raw[:200],
            )
            return self._fallback_structure(raw)

    def _fallback_structure(self, raw_text: str) -> dict:
        """If JSON parsing fails, surface the raw text so demo doesn't crash."""
        return {
            "headline": "Briefing generation returned non-JSON content. See raw output below.",
            "working": [],
            "not_working": [],
            "accountability": [],
            "decisions": [],
            "_raw_fallback": raw_text,
        }


class QAAgent:
    """Answers ad-hoc natural-language questions over the portfolio."""

    def __init__(self):
        from .logger import get_logger
        self._log = get_logger("QAAgent")
        self.llm = get_client()

    def answer(self, question: str, initiatives: List[Initiative]) -> str:
        """
        Returns answer text with inline citation markers like [WM-AI-1000] or
        [SOURCE:IB Tech Quarterly Tracker]. The UI parses these markers and
        renders them as clickable chips with hover-tooltips.
        """
        self._log.info(f"Answering ad-hoc question", question_preview=question[:80])
        facts = _portfolio_facts(initiatives)

        # Build a list of valid citation IDs the LLM is allowed to use
        valid_ids = sorted({i.id for i in initiatives})
        valid_sources = sorted({i.source_system for i in initiatives})

        prompt = f"""You are a portfolio analytics assistant for Morgan Stanley's transformation team.
Answer the question using ONLY the portfolio facts below. Be specific -- name initiatives,
business units, owners, and numbers. If the data does not contain the answer, say so directly.

CITATION REQUIREMENTS:
After EVERY factual claim, add an inline citation in square brackets pointing to the
source(s) that support it. Two formats are valid:

  - Initiative IDs:      [WM-AI-1000]   (use these whenever you reference a specific initiative)
  - Source systems:      [SOURCE:WM Jira (JSON)]   (use when you cite portfolio-wide aggregates)

You may chain multiple citations: [WM-AI-1000][IB-AI-1004]. Place citations IMMEDIATELY after
the claim they support, not at the end of the sentence. Every numeric figure must be cited.

Valid initiative IDs: {", ".join(valid_ids)}
Valid source systems: {"; ".join(valid_sources)}

Portfolio facts:
{facts}

Question: {question}

Answer:"""
        result = self.llm.complete(prompt, max_tokens=900)
        self._log.info(f"Q&A response generated", chars=len(result))
        return result


if __name__ == "__main__":
    from .aggregator import DataAggregatorAgent
    from .analyst import RiskAnalystAgent
    inits = DataAggregatorAgent().run()
    RiskAnalystAgent().score_all(inits)
    print("=" * 70)
    print("EXECUTIVE BRIEFING")
    print("=" * 70)
    print(BriefingAgent().generate(inits))
    print()
    print("=" * 70)
    print("Q: Which initiatives are at risk in Institutional Securities?")
    print("=" * 70)
    print(QAAgent().answer("Which initiatives are at risk in Institutional Securities?", inits))
