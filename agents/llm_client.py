"""
LLM client with graceful fallback.

If ANTHROPIC_API_KEY is set in the environment, uses the real Claude API.
Otherwise, uses a deterministic Mock LLM so the demo runs anywhere with zero
external dependencies. The mock is "smart" -- it inspects the prompt and
returns realistic responses, so the demo flow is identical either way.
"""
import json
import os
import re
from pathlib import Path
from typing import Optional


def _load_dotenv():
    """Tiny dotenv loader -- no extra dependency. Reads .env from project root."""
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        # Don't overwrite if already set in real environment
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv()


class LLMClient:
    """Single interface, two backends."""

    def __init__(self, model: str = "claude-sonnet-4-5"):
        from .logger import get_logger
        self._log = get_logger("LLMClient")
        self.model = model
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        self.backend = "anthropic" if self.api_key else "mock"
        self.status_message = ""
        self._anthropic_client = None
        # Stats
        self.total_calls = 0
        self.total_input_chars = 0
        self.total_output_chars = 0
        self.total_elapsed_ms = 0.0
        self.fallback_count = 0

        if self.backend == "anthropic":
            try:
                import anthropic
                self._anthropic_client = anthropic.Anthropic(api_key=self.api_key)
                self.status_message = "Connected to Anthropic API"
                self._log.info("Initialized LLM client", backend="anthropic", model=self.model)
            except ImportError:
                # Library not installed -- fall back to mock
                self.backend = "mock"
                self.status_message = "API key found but `anthropic` package not installed -- run: pip install anthropic"
                self._log.warning(
                    "ANTHROPIC_API_KEY is set but `anthropic` package is not installed -- falling back to mock",
                    fix="pip install anthropic",
                )
        else:
            self.status_message = "No ANTHROPIC_API_KEY set -- using mock LLM (set the key in .env or environment)"
            self._log.warning(
                "No API key found -- using mock LLM",
                hint="Set ANTHROPIC_API_KEY in .env or environment to use real Claude",
            )

    def complete(self, prompt: str, system: Optional[str] = None, max_tokens: int = 1024) -> str:
        self.total_calls += 1
        self.total_input_chars += len(prompt) + (len(system) if system else 0)

        # Estimate tokens (rough: ~4 chars/token for English)
        input_tokens_est = (len(prompt) + (len(system) if system else 0)) // 4

        self._log.info(
            f"LLM call #{self.total_calls}",
            backend=self.backend,
            prompt_chars=len(prompt),
            system_chars=len(system) if system else 0,
            est_input_tokens=input_tokens_est,
            max_tokens=max_tokens,
        )
        # Log a preview of the prompt at DEBUG level (file only)
        self._log.debug(f"Prompt preview: {prompt[:200]!r}{'...' if len(prompt) > 200 else ''}")

        if self.backend == "anthropic":
            return self._anthropic_complete(prompt, system, max_tokens)
        return self._mock_complete(prompt, system)

    # -----------------------------------------------------------------------
    # Real backend
    # -----------------------------------------------------------------------
    def _anthropic_complete(self, prompt: str, system: Optional[str], max_tokens: int) -> str:
        import time as _time
        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        t0 = _time.time()
        try:
            resp = self._anthropic_client.messages.create(**kwargs)
            elapsed_ms = (_time.time() - t0) * 1000
            self.total_elapsed_ms += elapsed_ms
            text = resp.content[0].text
            self.total_output_chars += len(text)
            # Try to read real usage if available
            usage = getattr(resp, "usage", None)
            if usage:
                self._log.info(
                    "✓ Anthropic API call succeeded",
                    elapsed_ms=f"{elapsed_ms:.0f}",
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                    output_chars=len(text),
                )
            else:
                self._log.info(
                    "✓ Anthropic API call succeeded",
                    elapsed_ms=f"{elapsed_ms:.0f}",
                    output_chars=len(text),
                )
            self._log.debug(f"Response preview: {text[:200]!r}{'...' if len(text) > 200 else ''}")
            return text
        except Exception as e:
            elapsed_ms = (_time.time() - t0) * 1000
            self.fallback_count += 1
            self._log.error(
                f"✗ Anthropic API call failed -- falling back to mock",
                error_type=type(e).__name__,
                error=str(e)[:200],
                elapsed_ms=f"{elapsed_ms:.0f}",
            )
            return self._mock_complete(prompt, system, error_note=f"(fallback after API error: {type(e).__name__})")

    # -----------------------------------------------------------------------
    # Mock backend -- deterministic, prompt-aware, "smart enough" for demo
    # -----------------------------------------------------------------------
    def _mock_complete(self, prompt: str, system: Optional[str], error_note: str = "") -> str:
        p = prompt.lower()

        # Highest priority: caller explicitly asked for JSON
        if "valid json" in p or ("output only" in p and "json" in p):
            if "what_is_working" in p or "what_is_stuck" in p or "single_action" in p:
                template = "structured_accountability_json"
                response = self._mock_structured_accountability_json()
            elif "strengths" in p and "risks" in p and "next_step" in p:
                template = "structured_risk_explain_json"
                response = self._mock_structured_risk_explain_json(prompt)
            else:
                template = "structured_briefing_json"
                response = self._mock_structured_briefing_json()
        # Q&A prompt has a unique signature: "Question:" + "Answer:" + citation rules
        elif "question:" in p and "answer:" in p and "citation" in p:
            template = "qa"
            response = self._mock_qa(prompt)
        # Per-initiative risk-analyst narrative
        elif "senior risk analyst" in p or ("analyze why" in p):
            template = "risk_analysis"
            response = self._mock_risk_analysis(prompt)
        # Markdown executive briefing
        elif "executive briefing" in p or ("section headers" in p and "headline" in p):
            template = "executive_briefing"
            response = self._mock_executive_briefing(prompt)
        # Accountability narrative (free-form)
        elif "approval-chain health" in p or ("validator workload" in p and "where is it stuck" in p):
            template = "accountability"
            response = self._mock_accountability(prompt)
        # Generic Q&A fallback for any other question-like prompt
        elif prompt.strip().endswith("?") or "which" in p or "who" in p or "how is" in p:
            template = "qa"
            response = self._mock_qa(prompt)
        else:
            template = "generic"
            response = f"[Mock LLM] I would analyze the provided context and respond. {error_note}"

        self._log.info(
            f"✓ Mock LLM response generated",
            template=template,
            output_chars=len(response),
        )
        self.total_output_chars += len(response)
        return response

    def _mock_structured_briefing_json(self) -> str:
        """Returns a hand-crafted JSON briefing matching the expected schema."""
        import json
        return json.dumps({
            "headline": "Portfolio shows mixed health with one critical failure (RFQ Auto-Pricing, $3.8M overspend) and a single-validator bottleneck blocking five high-priority initiatives. Two genuine wins are ready to scale; the rest of the portfolio is treading water on approval-chain delays.",
            "working": [
                {
                    "initiative": "GenAI Advisor Co-Pilot",
                    "bu": "WM",
                    "owner": "person_009",
                    "why": "On-time, on-budget, and exceeding the productivity-gain KPI -- ready to expand to the full advisor base."
                },
                {
                    "initiative": "Internal Knowledge Search",
                    "bu": "GF",
                    "owner": "person_022",
                    "why": "Fully approved and ahead of schedule; under budget at 78% spend with sponsor sign-off complete."
                },
                {
                    "initiative": "ESG Document Classifier",
                    "bu": "AM",
                    "owner": "person_019",
                    "why": "85% complete and moving smoothly through UAT with 2 open issues -- on track for go-live in 45 days."
                }
            ],
            "not_working": [
                {
                    "initiative": "RFQ Auto-Pricing",
                    "bu": "IB",
                    "owner": "person_013",
                    "severity": "Critical",
                    "issue": "$8.3M spent against $4.5M approved (185% overrun) while delivering only 25% of the pricing-improvement KPI. Validator review pending 45 days; trading desk disputes backtest results."
                },
                {
                    "initiative": "Portfolio Manager Chatbot",
                    "bu": "AM",
                    "owner": "person_017",
                    "severity": "At Risk",
                    "issue": "No status update in 87 days, only 22% complete, and 14 open issues. Already missed the original go-live by 45 days. Validator review never even initiated."
                },
                {
                    "initiative": "AI Code Review Assistant",
                    "bu": "GF",
                    "owner": "person_020",
                    "severity": "At Risk",
                    "issue": "Source system reports 'Active' but milestone is 1+ month behind and spend is at 122% of $5.5M budget -- the kind of slippage that's invisible in static reporting."
                }
            ],
            "accountability": [
                {
                    "person": "person_005 (Risk)",
                    "role": "Validator",
                    "owns": "Validator review for RFQ Auto-Pricing, Onboarding Doc Intelligence, and 3 others",
                    "action_needed": "Capacity check this week -- 5 of 6 reviews pending, including the critical RFQ item. Single point of failure for portfolio reporting cycle."
                },
                {
                    "person": "person_002",
                    "role": "Sponsor",
                    "owns": "Head of IS Tech -- ultimate owner of RFQ Auto-Pricing and Trade Surveillance ML",
                    "action_needed": "Decision required this week: kill, restructure, or refund RFQ Auto-Pricing. $3.8M overspend cannot continue."
                },
                {
                    "person": "person_003",
                    "role": "Sponsor",
                    "owns": "Head of IM Tech -- sponsor of Portfolio Manager Chatbot",
                    "action_needed": "87-day silence on this initiative needs explanation. Either reassign or cancel."
                }
            ],
            "decisions": [
                {
                    "id": 1,
                    "decision": "Approve a 30-day remediation window for RFQ Auto-Pricing with weekly check-ins, or formally pause the initiative pending revised business case.",
                    "rationale": "$3.8M overspend with 25% KPI delivery is unsustainable; status quo means continued burn.",
                    "owner": "person_002 (Sponsor) + person_013 (Owner)"
                },
                {
                    "id": 2,
                    "decision": "Reallocate $1.2M from Portfolio Manager Chatbot (stalled) to scale GenAI Advisor Co-Pilot rollout firm-wide.",
                    "rationale": "Move capital from a stalled initiative to the highest-performing one; the Co-Pilot is ready to absorb additional investment.",
                    "owner": "person_004 (COO Technology)"
                },
                {
                    "id": 3,
                    "decision": "Stand up a validator-capacity working group, chaired by person_005, to address the model-risk review bottleneck.",
                    "rationale": "person_005 holds 5 of 6 pending validator reviews -- this is becoming the longest pole in the monthly leadership reporting cycle.",
                    "owner": "person_005 (Risk) + COO Technology Office"
                }
            ]
        }, indent=2)

    def _mock_structured_accountability_json(self) -> str:
        """Returns hand-crafted JSON for the accountability narrative."""
        import json
        return json.dumps({
            "headline": "Approval-chain health is mixed: 9 of 14 initiatives are fully cleared, but the remaining 5 are concentrated under a single validator (person_005), making them the long pole in the monthly reporting cycle.",
            "what_is_working": [
                {
                    "area": "Sponsor-tier sign-offs",
                    "evidence": "9 of 14 initiatives have full sponsor approval; sponsor-tier latency is averaging under 5 days when items reach them."
                },
                {
                    "area": "Compliance & Legal review",
                    "evidence": "person_006 (Compliance) and person_008 (Legal) have zero pending items -- no capacity issue at those review functions."
                }
            ],
            "what_is_stuck": [
                {
                    "area": "Risk-tier validator bottleneck",
                    "severity": "High",
                    "evidence": "person_005 (Risk) is named validator on 6 of 14 initiatives and has 5 of those pending. This is a single point of failure for the entire portfolio."
                },
                {
                    "area": "Stalled submissions",
                    "severity": "Medium",
                    "evidence": "1 initiative (Portfolio Manager Chatbot, AM Tech) has not even initiated validator review despite being 87 days stale -- ownership ambiguity."
                }
            ],
            "single_action": {
                "action": "Schedule a 30-minute capacity review with person_005 to triage the 5 pending Risk-tier items: which need re-submission vs which can be approved as-is.",
                "owner": "person_004 (Head of Group Functions Technology) — as portfolio-wide owner",
                "by_when": "End of this week, before the next monthly leadership review"
            }
        }, indent=2)

    def _mock_structured_risk_explain_json(self, prompt: str) -> str:
        """
        Tone-aware structured risk assessment. Reads the prompt to determine
        the risk bucket and which initiative is being analyzed, then returns
        a balanced JSON response. Critically: does NOT manufacture risks for
        healthy initiatives.
        """
        import json, re as _re

        # Detect bucket from prompt
        m = _re.search(r"\(([\w ]+)\)\s*\nNormalized status", prompt)
        bucket_match = _re.search(r"Risk score:\s*\d+/100\s*\(([\w ]+)\)", prompt)
        bucket = bucket_match.group(1) if bucket_match else "Watch"

        # Extract initiative name + a few facts
        name_match = _re.search(r"Name:\s*([^\n]+)", prompt)
        initiative_name = name_match.group(1).strip() if name_match else "this initiative"
        bu_match = _re.search(r"Business unit:\s*([^\n]+)", prompt)
        bu = bu_match.group(1).strip() if bu_match else ""
        kpi_match = _re.search(r"KPI actual:\s*(\d+)%", prompt)
        kpi = int(kpi_match.group(1)) if kpi_match else 50
        util_match = _re.search(r"\((\d+)% utilization\)", prompt)
        util = int(util_match.group(1)) if util_match else 0
        validator_pending = "pending" in prompt.lower() and "validator" in prompt.lower()

        # Build response based on bucket
        if bucket == "Healthy":
            return json.dumps({
                "assessment": f"{initiative_name} is performing well across all measured dimensions. The deterministic scoring engine raised no material flags, and the team is meeting its commitments.",
                "strengths": [
                    {"point": "On-target KPI delivery", "evidence": f"KPI achievement at {kpi}% of target."},
                    {"point": "Disciplined budget execution", "evidence": f"Budget utilization at {util}% with no overrun signals."},
                    {"point": "Approval chain healthy", "evidence": "Validator and sponsor sign-offs both complete."},
                ],
                "risks": [],
                "next_step": {
                    "recommendation": "Continue current cadence. Consider whether learnings from this initiative can be templated for other teams.",
                    "owner": "Initiative owner",
                    "by_when": "Next quarterly portfolio review"
                }
            }, indent=2)

        if bucket == "Watch":
            return json.dumps({
                "assessment": f"{initiative_name} is broadly on track with one or two watchpoints worth monitoring. Nothing requires escalation at this point.",
                "strengths": [
                    {"point": "Initiative is making measurable progress", "evidence": f"KPI at {kpi}% of target."},
                    {"point": "Team is engaged", "evidence": "Owner notes show active iteration on outstanding items."},
                ],
                "risks": [
                    {"point": "Mild approval-cycle delay", "evidence": "Validator review is in queue but not yet stale.", "severity": "Low"},
                ] if validator_pending else [],
                "next_step": {
                    "recommendation": "Confirm validator review timeline at next standup; no escalation needed yet.",
                    "owner": f"Initiative owner",
                    "by_when": "Next standup / weekly review"
                }
            }, indent=2)

        if bucket == "At Risk":
            return json.dumps({
                "assessment": f"{initiative_name} has clear indicators that need attention. The issues are addressable but require deliberate intervention this cycle.",
                "strengths": [
                    {"point": "Owner accountability is intact", "evidence": "Notes show the owner has identified and is engaging with the issues."},
                ],
                "risks": [
                    {"point": "KPI underperformance", "evidence": f"Tracking at {kpi}% of target.", "severity": "Medium"},
                    {"point": "Approval-chain delay", "evidence": "Validator review pending beyond typical SLA.", "severity": "Medium"},
                ] + ([
                    {"point": "Budget pressure", "evidence": f"Utilization at {util}% — diminishing remediation runway.", "severity": "Medium"},
                ] if util > 90 else []),
                "next_step": {
                    "recommendation": "Schedule a focused 30-minute review with the validator and owner to clarify what's blocking sign-off.",
                    "owner": f"Senior sponsor for {bu}",
                    "by_when": "End of this week"
                }
            }, indent=2)

        # Critical
        return json.dumps({
            "assessment": f"{initiative_name} has serious concerns requiring immediate sponsor-level intervention. Multiple risk signals are firing simultaneously, and the trajectory is unfavorable without action.",
            "strengths": [
                {"point": "Issues are visible in the data", "evidence": "Source-system commentary surfaces the problems candidly — there is no information gap."},
            ],
            "risks": [
                {"point": "Material budget overrun", "evidence": f"Spend at {util}% of approved envelope.", "severity": "High"},
                {"point": "KPI severely under target", "evidence": f"Tracking at {kpi}% — the spend-to-delivery gap is the dominant signal.", "severity": "High"},
                {"point": "Stalled approval chain", "evidence": "Validator review pending beyond reasonable SLA, suggesting unresolved substantive concerns.", "severity": "High"},
            ],
            "next_step": {
                "recommendation": f"Bring this to the next leadership review with a concrete remediation proposal: kill, restructure, or refund. Apply the lessons from successful remediations (e.g. scope reduction, owner reassignment, tighter validator cadence).",
                "owner": f"Senior sponsor for {bu}",
                "by_when": "Next leadership review"
            }
        }, indent=2)

    def _mock_risk_analysis(self, prompt: str) -> str:
        # Extract initiative names mentioned in prompt for slightly more dynamic mock
        names = re.findall(r"([A-Z][A-Za-z ]+(?:Co-Pilot|Analytics|Summarization|Intelligence|ML|Pricing|NLP|AI|Signals|Classifier|Chatbot|Assistant|Agent|Search))", prompt)
        focal = names[0] if names else "this initiative"
        return (
            f"**Risk assessment**: {focal} shows multiple concurrent stress signals. "
            f"The primary concern is the gap between budget consumption and KPI achievement -- "
            f"spend is tracking ahead of plan while measurable outcomes lag. "
            f"Secondary concern is approval-chain latency: validator sign-off has been pending "
            f"for an extended window, which historically correlates with scope or model-risk issues "
            f"that the owning team has not yet escalated.\n\n"
            f"**Recommended action**: Escalate to the senior sponsor with a focused two-question agenda -- "
            f"(1) is the KPI definition still the right one, and (2) what specifically is blocking validator approval. "
            f"Avoid a generic 'status update' meeting; ask for a written decision."
        )

    def _mock_executive_briefing(self, prompt: str) -> str:
        return (
            "**Executive Briefing -- AI Initiatives Portfolio**\n\n"
            "**Headline**: 14 active AI initiatives across four business units, "
            "$32.4M committed FY26 budget. Portfolio health is mixed: roughly 40% of initiatives "
            "are tracking to plan, 35% need attention, and 25% are at material risk of missing FY26 commitments.\n\n"
            "**What's working**\n"
            "- Wealth Management's GenAI Advisor Co-Pilot is the strongest performer -- on-time, "
            "on-budget, and showing measurable advisor productivity gains.\n"
            "- Technology's Internal Knowledge Search has cleared validator review and is in production rollout.\n\n"
            "**What's not working**\n"
            "- Investment Bank Tech's RFQ Auto-Pricing is over-budget and showing model drift; "
            "no clear remediation owner.\n"
            "- Two initiatives have validator sign-offs pending more than 30 days -- a leading "
            "indicator of model-risk concerns the owning teams haven't surfaced.\n\n"
            "**Who's accountable for the gaps**\n"
            "- person_002 (Head of IS Tech) owns the two highest-risk items.\n"
            "- Validator queue is concentrated with person_005 (Risk) -- worth a capacity check.\n\n"
            "**Recommended decisions for this meeting**\n"
            "1. Approve a 30-day remediation window for the two red initiatives, with weekly check-ins.\n"
            "2. Reallocate budget from one paused initiative ($1.2M) to scale the Co-Pilot rollout.\n"
            "3. Stand up a validator-capacity working group -- this is becoming a portfolio-wide bottleneck."
        )

    def _mock_qa(self, prompt: str) -> str:
        # Extract just the question text (after "Question:" marker), not the
        # full prompt -- otherwise the citation-instruction text triggers
        # false matches (e.g. "Valid initiative IDs: WM-AI-..." → "wm" match).
        import re as _re
        m = _re.search(r"Question:\s*(.+?)\s*Answer:", prompt, _re.DOTALL)
        q = m.group(1).lower() if m else prompt.lower()

        if "wealth" in q or " wm" in q or "wm tech" in q or q.startswith("wm"):
            return (
                "Across Wealth Management Tech, you have 6 active AI initiatives [SOURCE:WM Jira (JSON)]. "
                "The standout is **GenAI Advisor Co-Pilot** [WM-AI-1000] -- now in production with "
                "4,200 advisors and exceeding the 20% productivity-gain target [WM-AI-1000]. "
                "**Onboarding Document Intelligence** [WM-AI-1003] is the one to watch -- "
                "validator sign-off pending 62 days [WM-AI-1003]. **Cross-Border Tax AI** [WM-AI-1004] "
                "is also stuck at 31 days pending due to WM/IB joint-governance friction [WM-AI-1004]. "
                "Senior sponsor for WM is person_001."
            )
        if "behind" in q or "delay" in q or "at risk" in q or "red" in q or "highest risk" in q:
            return (
                "The initiatives I would flag as at-risk right now:\n\n"
                "1. **RFQ Auto-Pricing** [IB-AI-1000] -- $8.3M spent against $4.5M approved (185% overrun) "
                "with KPI at 25% [IB-AI-1000].\n"
                "2. **Portfolio Manager Chatbot** [AM-AI-1000] -- 87 days no update, 22% complete [AM-AI-1000].\n"
                "3. **AI Code Review Assistant** [GF-AI-1000] -- spend at 122% of $5.5M with milestone 1+ month behind [GF-AI-1000].\n"
                "4. **Legacy COBOL Modernization Bot** [GF-AI-1003] -- abandoned: owner left 6 months ago, source still says Active [GF-AI-1003].\n\n"
                "Common thread: all four have validator approval pending or never initiated [SOURCE:Approvals Log (JSON)]. "
                "Validator latency is your earliest leading indicator of trouble."
            )
        if "investment bank" in q or " ib " in q or q.startswith("ib") or "ib tech" in q:
            return (
                "Investment Bank Tech has 6 active AI initiatives [SOURCE:IB Tech Quarterly Tracker (Excel/CSV)]. "
                "The most concerning is **RFQ Auto-Pricing** [IB-AI-1000] -- 185% over a $4.5M budget at 25% KPI delivery [IB-AI-1000]. "
                "**Counterparty Credit AI** [IB-AI-1003] and **Counterparty KYC Refresh AI** [IB-AI-1005] are also flagged. "
                "On the positive side, **GenAI Earnings Translation** [IB-AI-1004] is the firm's reference template for AI initiative remediation -- "
                "was Red two quarters ago, now Green for two consecutive quarters after restructure [IB-AI-1004]. "
                "Senior sponsor across IB Tech is person_002."
            )
        if "budget" in q or "spend" in q or "money" in q or "exposure" in q:
            return (
                "Total approved FY26 budget across the portfolio is approximately $32.4M, "
                "with $24.1M consumed YTD (74%) [SOURCE:IB Tech Quarterly Tracker (Excel/CSV)]"
                "[SOURCE:GF Tech Budget Tracker (CSV)]. Three initiatives are running over their approved "
                "envelope: **RFQ Auto-Pricing** [IB-AI-1000] at 185%, **AI Code Review Assistant** [GF-AI-1000] "
                "at 122%, and **Trade Surveillance ML** [IB-AI-1001] at 106%. Group Functions Tech is the "
                "most disciplined on spend overall [SOURCE:GF Tech Budget Tracker (CSV)]."
            )
        if "accountab" in q or "owner" in q or "responsible" in q or "bottleneck" in q:
            return (
                "Accountability is structured in three tiers per initiative: a working-level owner, "
                "an independent validator (Risk / Compliance / Model Risk / Legal), and a senior sponsor "
                "[SOURCE:Approvals Log (JSON)]. The most concentrated accountability gap right now sits with "
                "**person_005 (Risk)** -- named validator on 6 of 22 initiatives, with 5 of those pending "
                "[SOURCE:Approvals Log (JSON)]. The pending items include the highest-risk one in the portfolio: "
                "**RFQ Auto-Pricing** [IB-AI-1000]. There is also a secondary bottleneck at **person_008 (Legal)** "
                "with 2 pending, including the regulatory-deadline **Climate Risk ML Model** [AM-AI-1003]. "
                "Single point of failure worth raising at the next leadership review."
            )
        if "validator" in q and ("longest" in q or "pending" in q):
            return (
                "Validator sign-off pending durations (longest first) [SOURCE:Approvals Log (JSON)]:\n\n"
                "1. **Onboarding Document Intelligence** [WM-AI-1003] -- 62 days pending with person_005 (Risk).\n"
                "2. **RFQ Auto-Pricing** [IB-AI-1000] -- 45 days pending with person_005 (Risk).\n"
                "3. **Cross-Border Tax AI** [WM-AI-1004] -- 31 days pending with person_008 (Legal).\n"
                "4. **Counterparty Credit AI** [IB-AI-1003] -- 28 days pending with person_005 (Risk).\n"
                "5. **AI Code Review Assistant** [GF-AI-1000] -- 22 days pending with person_005 (Risk).\n\n"
                "Three of the top five are with the same validator -- person_005 -- which is the bottleneck pattern."
            )
        return (
            "Based on the current portfolio data: 22 active initiatives across 4 BU Tech divisions "
            "[SOURCE:WM Jira (JSON)][SOURCE:IB Tech Quarterly Tracker (Excel/CSV)]"
            "[SOURCE:AM Tech SharePoint (CSV)][SOURCE:GF Tech Budget Tracker (CSV)]. "
            "Ask me about specific business units, at-risk initiatives, budget, validator pending durations, "
            "or accountability -- I can pull the underlying data for any of those."
        )

    def _mock_accountability(self, prompt: str) -> str:
        return (
            "**Accountability snapshot**\n\n"
            "- 5 initiatives have all required sign-offs complete and are clear to report.\n"
            "- 6 initiatives have validator approval pending; median wait is 18 days.\n"
            "- 3 initiatives have validator approved but senior sponsor sign-off pending.\n\n"
            "**Suggested escalations** (auto-drafted -- review before sending):\n"
            "1. To person_005: 3 model-risk reviews in queue >14 days. Capacity issue or content issue?\n"
            "2. To person_001: Onboarding Document Intelligence sponsor sign-off pending 9 days.\n"
            "3. To person_002: RFQ Auto-Pricing requires sponsor decision before next leadership review."
        )


# Module-level singleton
_client = None

def get_client() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
