# AI Initiatives — Agentic Reporting Platform

**Prototype for Morgan Stanley Technology COO transformation team.**

Reimagines the monthly AI initiatives reporting process by replacing manual spreadsheet stitching and static slide decks with an agentic pipeline that produces live, queryable, decision-ready briefings.

---

## The problem (as stated)

> Every month, our transformation team reports to senior leadership on how AI initiatives across the firm are performing. Today, the data lives in fragmented systems and spreadsheets, gets stitched together manually, and arrives as static slides. Leadership wants to know which initiatives are working, which aren't, and who's accountable. Multiple business units run their own initiatives. Each has owners, validators, and senior supporters who sign off before anything reaches leadership.

## What this prototype does

1. **Pulls** AI initiative data from 4 simulated fragmented sources (Jira-like JSON, Excel-style CSV, SharePoint-style CSV, budget tracker CSV) plus an approvals log
2. **Normalizes** the chaos — different schemas, different status vocabularies (`Green/Amber/Red` vs `On Track/At Risk/Off Track` vs `In Progress/Blocked/Done`), different date formats — into one canonical view
3. **Scores** each initiative for risk using a deterministic, auditable, 6-factor model (status, budget overrun, KPI/burn gap, approval-chain stalls, staleness, KPI underperformance)
4. **Tracks** the validator → senior sponsor approval chain and surfaces bottlenecks (e.g., "person_005 has 3 model-risk reviews pending — that's a capacity problem")
5. **Auto-drafts** escalation messages the COO can send with one click
6. **Generates** a decision-shaped executive briefing that replaces the static slide deck
7. **Answers** ad-hoc natural-language questions about the portfolio in chat — no more "let me get back to you with that number"

## Architecture

```
4 fragmented sources  →  Data Aggregator  →  unified canonical schema
                                ↓
                  ┌─────────────┼─────────────┐
                  ↓             ↓             ↓
           Risk Analyst   Accountability   Briefing
                  ↓             ↓             ↓
                  └─────────────┼─────────────┘
                                ↓
                     Streamlit dashboard + Q&A chat
```

5 specialized agents, composed by an Orchestrator. Each agent owns one capability and is independently testable.

## Quick start

```bash
pip install -r requirements.txt

# Optional: use the real Claude API for LLM narrative.
# If unset, the prototype uses a deterministic mock LLM.
export ANTHROPIC_API_KEY="..."

# Generate mock data (already committed, but you can regenerate)
python data/generate_mock_data.py

# Run the dashboard
streamlit run app.py
```

Visit `http://localhost:8501`.

## Design principles

1. **Deterministic core, LLM at the edges.** Risk *scores* are rule-based and auditable. The LLM *narrates* the score; it does not produce it. In a regulated firm you can't have a black-box deciding which initiative is at risk.

2. **Specialist agents, not one mega-prompt.** Each agent does one thing — aggregate, score, track approvals, narrate, answer questions. The orchestrator composes them. Testable, debuggable, swappable.

3. **Source-of-truth preservation.** The aggregator builds a unified view *on top* of existing systems. It doesn't replace them, doesn't overwrite them, doesn't ask owners to migrate. Adoption friction = zero.

4. **Decision-shaped output.** The briefing ends with "Recommended decisions for this meeting" — numbered, approvable items. Not "here's what's happening." That's the whole point of replacing static slides: the meeting becomes a decision forum, not a status update.

5. **Graceful degradation.** Demo runs with or without an API key. If the API fails mid-demo, the LLM client silently falls back to a deterministic mock so the demo never breaks.

6. **Observable.** Every agent logs what it did to a trace visible in the "Agent Activity" tab. In production this becomes the audit trail.

## Project structure

```
ms_prototype/
├── app.py                          # Streamlit dashboard
├── requirements.txt
├── README.md
├── PITCH.md                        # The story for the interview
├── data/
│   ├── generate_mock_data.py       # Generates the 5 mock data sources
│   ├── wm_jira_export.json         # Wealth Management
│   ├── is_quarterly_tracker.csv    # Investment Bank
│   ├── im_sharepoint_status.csv    # Asset Management
│   ├── tech_coo_budget.csv         # Technology / COO
│   └── approvals_log.json          # Validator + sponsor sign-offs
└── agents/
    ├── llm_client.py               # Anthropic API + mock fallback
    ├── aggregator.py               # Data Aggregator Agent
    ├── analyst.py                  # Risk Analyst Agent
    ├── accountability.py           # Accountability Agent
    ├── briefing.py                 # Briefing + Q&A Agents
    └── orchestrator.py             # Wires the pipeline together
```

## What I would build next (if I had more than 48 hours)

- **Real connectors** — replace the mock data files with read-only adapters for Jira, ServiceNow, SharePoint, internal data lakes
- **Drift detection on the briefing itself** — flag when this month's narrative diverges materially from last month's, so leadership sees the *change*, not just the state
- **Validator-side workflow** — same agent platform, surfaced to validators as their own queue with auto-drafted requests-for-information when a submission is incomplete
- **Confidence + provenance on every LLM claim** — every sentence in the briefing should link back to the underlying data row that produced it
- **Human-in-the-loop on escalations** — current prototype lets the COO send drafted escalations; the next step is letting them be edited inline with a diff view, plus an audit log of what was sent
- **Cost & performance tracking on the agent pipeline itself** — meta-monitoring so we can show that this system is cheaper than the manual process it replaces
