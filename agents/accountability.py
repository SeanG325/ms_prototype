"""
Accountability Agent
====================
Answers: "Who is accountable for what, and who is the blocker?"

Operates on the merged data and produces:
  - Per-initiative accountability state (who has signed, who hasn't)
  - Bottleneck detection (e.g., one validator with N pending reviews)
  - Auto-drafted escalation messages the COO can send with one click
"""
from collections import Counter, defaultdict
from datetime import datetime
from typing import List, Dict, Tuple
from .aggregator import Initiative
from .llm_client import get_client


class AccountabilityAgent:
    def __init__(self):
        from .logger import get_logger
        self._log = get_logger("Accountability")
        self.llm = get_client()

    # -----------------------------------------------------------------------
    # Aggregate views
    # -----------------------------------------------------------------------
    def signoff_summary(self, initiatives: List[Initiative]) -> Dict[str, int]:
        """Counts of each approval state."""
        s = Counter()
        for i in initiatives:
            s["validator_" + i.validator_status] += 1
            s["sponsor_" + i.sponsor_status] += 1
        # All-clear count
        s["fully_approved"] = sum(
            1 for i in initiatives
            if i.validator_status == "approved" and i.sponsor_status == "approved"
        )
        s["total"] = len(initiatives)
        return dict(s)

    def validator_workload(self, initiatives: List[Initiative]) -> List[Tuple[str, int, int]]:
        """
        Returns list of (validator_name, total_assigned, pending_count)
        sorted by pending desc -- this surfaces capacity bottlenecks.
        """
        load = defaultdict(lambda: [0, 0])  # [total, pending]
        for i in initiatives:
            if not i.validator:
                continue
            load[i.validator][0] += 1
            if i.validator_status == "pending":
                load[i.validator][1] += 1
        rows = [(name, t, p) for name, (t, p) in load.items()]
        rows.sort(key=lambda x: (-x[2], -x[1]))
        return rows

    def stuck_initiatives(self, initiatives: List[Initiative]) -> List[Initiative]:
        """Initiatives where the approval chain is stuck (validator pending or not started)."""
        return [
            i for i in initiatives
            if i.validator_status in ("pending", "not_submitted")
            or (i.validator_status == "approved" and i.sponsor_status == "pending")
        ]

    # -----------------------------------------------------------------------
    # Action generation -- one-click escalations
    # -----------------------------------------------------------------------
    def draft_escalations(self, initiatives: List[Initiative]) -> List[Dict]:
        """
        Auto-draft escalation messages for the COO to send. Each message
        identifies the recipient, the blocked items, and a specific ask.
        """
        self._log.info("Analyzing approval chains for bottlenecks")
        out = []

        # Bottleneck validators
        workload = self.validator_workload(initiatives)
        for validator, total, pending in workload:
            if pending >= 2:
                blocked = [i for i in initiatives if i.validator == validator and i.validator_status == "pending"]
                blocked_names = ", ".join(b.name for b in blocked)
                self._log.warning(
                    f"Bottleneck detected",
                    validator=validator,
                    pending=pending,
                    total_assigned=total,
                )
                out.append({
                    "to": validator,
                    "subject": f"Validator queue check-in: {pending} pending AI initiative reviews",
                    "body": (
                        f"Hi -- I'm seeing {pending} AI initiative validator reviews assigned to you "
                        f"that are currently pending: {blocked_names}.\n\n"
                        f"Two questions: (1) is this a capacity issue we can help resource, or (2) is "
                        f"there a content issue with one or more submissions that the owning teams should know about?\n\n"
                        f"This is becoming the longest pole in our monthly leadership reporting cycle, so any color helps."
                    ),
                    "priority": "High" if pending >= 3 else "Medium",
                    "blocked_initiatives": [b.id for b in blocked],
                })

        # Sponsor sign-offs pending
        sponsor_pending = [i for i in initiatives if i.sponsor_status == "pending"]
        by_sponsor = defaultdict(list)
        for i in sponsor_pending:
            by_sponsor[i.senior_sponsor].append(i)
        for sponsor, items in by_sponsor.items():
            names = ", ".join(i.name for i in items)
            out.append({
                "to": sponsor,
                "subject": f"Sponsor sign-off needed before next leadership review: {len(items)} item(s)",
                "body": (
                    f"The following initiatives have cleared validator review and need your sponsor sign-off "
                    f"before they can be included in the next monthly leadership update:\n\n"
                    f"  • {names}\n\n"
                    f"Decision needed by end of week. Reply 'approve' or flag any concerns."
                ),
                "priority": "High",
                "blocked_initiatives": [i.id for i in items],
            })

        self._log.info(
            f"Drafted {len(out)} escalation message(s) for COO review",
            high_priority=sum(1 for e in out if e["priority"] == "High"),
        )
        return out

    # -----------------------------------------------------------------------
    # Narrative
    # -----------------------------------------------------------------------
    def narrative(self, initiatives: List[Initiative]) -> str:
        """Free-form prose narrative -- kept for backward compatibility / export."""
        summary = self.signoff_summary(initiatives)
        workload = self.validator_workload(initiatives)
        prompt = f"""You are briefing the Technology COO on accountability and approval-chain health
across the AI initiative portfolio. Be specific, name names, and recommend exactly one action.

Approval state summary: {summary}

Validator workload (validator, total assigned, pending):
{chr(10).join(f'  - {v}: {t} assigned, {p} pending' for v, t, p in workload)}

Write 4-6 sentences: where is accountability working, where is it stuck, and what is the
one thing the COO should do this week to unblock it."""
        return self.llm.complete(prompt, max_tokens=500)

    def narrative_structured(self, initiatives: List[Initiative]) -> dict:
        """
        Returns a structured dict the UI can render as tables/cards:

        {
          "headline": "1-2 sentences summarizing approval-chain health",
          "what_is_working": [{"area": "...", "evidence": "..."}],
          "what_is_stuck":   [{"area": "...", "evidence": "...", "severity": "High|Medium|Low"}],
          "single_action":   {"action": "...", "owner": "...", "by_when": "..."}
        }
        """
        self._log.info("Generating structured accountability narrative (JSON)")
        summary = self.signoff_summary(initiatives)
        workload = self.validator_workload(initiatives)

        prompt = f"""You are briefing the Technology COO on accountability and approval-chain health
across the AI initiative portfolio. Output ONLY valid JSON (no prose, no markdown fences) matching
this exact schema:

{{
  "headline": "1-2 sentences -- the single most important takeaway about accountability health",
  "what_is_working": [
    {{"area": "short label", "evidence": "1 specific sentence with numbers"}}
  ],
  "what_is_stuck": [
    {{"area": "short label", "evidence": "1 specific sentence with names + numbers", "severity": "High|Medium|Low"}}
  ],
  "single_action": {{
    "action": "the ONE concrete action the COO should take this week",
    "owner": "who actually does it",
    "by_when": "specific deadline like 'EOW' or 'next leadership review'"
  }}
}}

Rules:
- 1-3 items in what_is_working; 1-3 items in what_is_stuck.
- Be specific: name validators, sponsors, and counts (e.g. "person_005 has 5 of 6 reviews pending").
- Be opinionated. Severity reflects the operational risk if not addressed.

Approval state summary: {summary}

Validator workload (validator, total assigned, pending):
{chr(10).join(f'  - {v}: {t} assigned, {p} pending' for v, t, p in workload)}
"""
        raw = self.llm.complete(
            prompt,
            system="You are a precise accountability analyst. You output only valid JSON.",
            max_tokens=900,
        )
        parsed = self._parse_json(raw)
        self._log.info(
            "Structured narrative generated",
            working_count=len(parsed.get("what_is_working", [])),
            stuck_count=len(parsed.get("what_is_stuck", [])),
        )
        return parsed

    def _parse_json(self, raw: str) -> dict:
        """Robust JSON parsing -- shared with BriefingAgent's pattern."""
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
                "Failed to parse accountability JSON -- using fallback",
                error=str(e)[:120],
            )
            return {
                "headline": "Accountability narrative unavailable -- LLM returned non-JSON content.",
                "what_is_working": [],
                "what_is_stuck": [],
                "single_action": {"action": "", "owner": "", "by_when": ""},
                "_raw_fallback": raw,
            }


if __name__ == "__main__":
    from .aggregator import DataAggregatorAgent
    inits = DataAggregatorAgent().run()
    agent = AccountabilityAgent()
    print("Sign-off summary:", agent.signoff_summary(inits))
    print("\nValidator workload:")
    for v, t, p in agent.validator_workload(inits):
        print(f"  {v}: {t} assigned, {p} pending")
    print(f"\nStuck initiatives: {len(agent.stuck_initiatives(inits))}")
    print("\nAuto-drafted escalations:")
    for e in agent.draft_escalations(inits):
        print(f"  → {e['to']} [{e['priority']}]: {e['subject']}")
