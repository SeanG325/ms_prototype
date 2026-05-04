"""
Meta-monitoring on the agent pipeline itself.

Proves that the automated system is cheaper than the manual process it replaces.
Tracks: pipeline latency, LLM token consumption, $ cost per briefing, vs the
estimated $ cost of the manual process. Surfaces the result on a dedicated UI
tab so leadership can see the ROI argument with audit-trail data, not vibes.

Design principle: every assumption surfaced in the UI gets a "(?)" tooltip or
caveat — we don't hide the math. ROI claims that survive Compliance scrutiny
are claims that show their work.
"""
from dataclasses import dataclass
from typing import Dict, Optional


# ===========================================================================
# Pricing constants (Anthropic Claude Sonnet 4 — public pricing as of 2025)
# These are intentionally hardcoded so the UI is honest about which model
# was assumed. In production this should read from the model selection.
# ===========================================================================
USD_PER_INPUT_TOKEN  = 3.00 / 1_000_000     # $3.00 per million input tokens
USD_PER_OUTPUT_TOKEN = 15.00 / 1_000_000    # $15.00 per million output tokens
CHARS_PER_TOKEN      = 4.0                  # rough approximation for English text


# ===========================================================================
# Manual process baseline (clearly labelled assumptions in the UI)
# ===========================================================================
@dataclass
class ManualBaseline:
    """
    The manual process this system replaces. Numbers are conservative
    estimates based on what the brief and follow-up conversations described.
    Every number is editable in production via a config screen.
    """
    bu_lead_hours_per_month: float = 4.0      # × 4 BU Tech leads collecting data
    bu_lead_count: int             = 4
    analyst_hours_per_month: float = 8.0      # transformation team analyst stitching + writing
    analyst_count: int             = 1
    reviewer_hours_per_month: float = 2.0     # senior reviewer QA pass
    reviewer_count: int            = 1
    blended_hourly_rate_usd: float = 200.0    # blended fully-loaded cost incl. benefits/overhead
    monthly_briefings: int         = 1        # one briefing produced per month

    @property
    def total_hours_per_month(self) -> float:
        return (
            self.bu_lead_hours_per_month * self.bu_lead_count
            + self.analyst_hours_per_month * self.analyst_count
            + self.reviewer_hours_per_month * self.reviewer_count
        )

    @property
    def cost_per_briefing(self) -> float:
        return self.total_hours_per_month * self.blended_hourly_rate_usd / self.monthly_briefings

    @property
    def annual_cost(self) -> float:
        return self.cost_per_briefing * 12 * self.monthly_briefings


# ===========================================================================
# Automated pipeline cost
# ===========================================================================
@dataclass
class PipelineRunMetrics:
    """A single pipeline run's resource consumption."""
    pipeline_elapsed_s: float
    llm_calls: int
    llm_fallback_count: int
    input_chars: int
    output_chars: int
    initiatives: int
    escalations: int

    @property
    def estimated_input_tokens(self) -> int:
        return int(self.input_chars / CHARS_PER_TOKEN)

    @property
    def estimated_output_tokens(self) -> int:
        return int(self.output_chars / CHARS_PER_TOKEN)

    @property
    def estimated_llm_cost_usd(self) -> float:
        return (
            self.estimated_input_tokens * USD_PER_INPUT_TOKEN
            + self.estimated_output_tokens * USD_PER_OUTPUT_TOKEN
        )

    @property
    def estimated_infra_cost_usd(self) -> float:
        # Tiny — 1 vCPU * 5s of compute. Calculated at AWS Fargate spot rate.
        # Numbers chosen conservatively so total cost claim is defensible.
        return 0.005

    @property
    def total_cost_per_run_usd(self) -> float:
        return self.estimated_llm_cost_usd + self.estimated_infra_cost_usd


# ===========================================================================
# ROI computation
# ===========================================================================
@dataclass
class ROIReport:
    automated: PipelineRunMetrics
    baseline: ManualBaseline

    @property
    def cost_reduction_per_briefing(self) -> float:
        return self.baseline.cost_per_briefing - self.automated.total_cost_per_run_usd

    @property
    def cost_reduction_pct(self) -> float:
        if self.baseline.cost_per_briefing == 0:
            return 0.0
        pct = self.cost_reduction_per_briefing / self.baseline.cost_per_briefing * 100
        # Cap display at 99.9% — claiming 100% reads as marketing not engineering
        return min(pct, 99.9)

    @property
    def annual_savings(self) -> float:
        return self.cost_reduction_per_briefing * 12 * self.baseline.monthly_briefings

    @property
    def hours_saved_per_briefing(self) -> float:
        return self.baseline.total_hours_per_month / self.baseline.monthly_briefings

    @property
    def hours_saved_annually(self) -> float:
        return self.hours_saved_per_briefing * 12 * self.baseline.monthly_briefings

    @property
    def speedup_factor(self) -> float:
        """How many times faster (wall clock) the automated pipeline is."""
        manual_seconds = self.baseline.total_hours_per_month * 3600 / self.baseline.monthly_briefings
        if self.automated.pipeline_elapsed_s == 0:
            return float("inf")
        return manual_seconds / self.automated.pipeline_elapsed_s


# ===========================================================================
# Helper to build a report from current LLM client state
# ===========================================================================
def build_roi_report(
    pipeline_elapsed_s: float,
    initiatives_count: int,
    escalations_count: int,
    baseline: Optional[ManualBaseline] = None,
) -> ROIReport:
    """Convenience: pulls live stats from the LLM client + assembles a report."""
    from .llm_client import get_client
    client = get_client()
    metrics = PipelineRunMetrics(
        pipeline_elapsed_s=pipeline_elapsed_s,
        llm_calls=client.total_calls,
        llm_fallback_count=client.fallback_count,
        input_chars=client.total_input_chars,
        output_chars=client.total_output_chars,
        initiatives=initiatives_count,
        escalations=escalations_count,
    )
    return ROIReport(automated=metrics, baseline=baseline or ManualBaseline())
