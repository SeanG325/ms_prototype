# PITCH — How to present this prototype

A **6-8 minute** walkthrough script for the Morgan Stanley interview. The goal is **not** to demo features. The goal is to show you **understood the problem**, made **deliberate design choices**, and can **defend them**.

> Built by **Sean Guan**. Mock data is fully anonymized (`person_NNN` placeholders) and uses MS-internal Tech division terminology (WM Tech, IB Tech, AM Tech, GF Tech).

---

## Quick reference card

| Beat | Tab to open | Key data to point at | Minutes |
|---|---|---|---|
| Frame the problem | (no demo yet) | — | 0:00–1:00 |
| Source landscape + initialization | Sidebar + boot screen | 5 sources · 2 parallel LLM calls · ~3-5s | 1:00–2:00 |
| Agent pipeline | 🔍 Agent Activity | 5 specialized agents | 2:00–3:00 |
| Executive Briefing | 📝 Executive Briefing | 1 Critical · 4 At Risk · $45.8M | 3:00–4:30 |
| Drill-down (structured) | 📋 Initiatives | RFQ Auto-Pricing risk score 100 | 4:30–5:15 |
| Accountability | ✅ Accountability | person_005: 6 assigned, 5 pending | 5:15–6:15 |
| Q&A with clickable citations | 💬 Ask the Portfolio | Live demo · click [WM-AI-1003] → drill-down | 6:15–7:15 |
| Observability | 📜 Logs | LLM call count, fallback count | 7:15–7:45 |
| Land design principles | (any tab) | — | 7:45–8:00 |

---

## 1. Frame the problem first (60 seconds — do NOT open the demo yet)

> "Before I show anything, let me tell you how I read this brief. The transformation team is being asked to do something they fundamentally can't do well manually: produce a *coherent, accountable, decision-ready* view of the firm's AI portfolio every month. The data is fragmented across systems. Status vocabularies don't match. Approval chains live in email. And the output — static slides — is a snapshot that's already stale by the time leadership sees it.
>
> So the prototype isn't a dashboard. A dashboard would just digitize the existing slides. The prototype is an **agentic pipeline** that does the work the team is currently doing by hand, and then produces something better than slides on the other side: a live, queryable, *opinionated* briefing that ends in concrete decisions for leadership to make."

**Why this opening works:** You're showing you read "agentic" and "intelligence" as design constraints, not buzzwords. You also reframe the deliverable from "report" to "decision support."

---

## 2. Show the source landscape AND initialization (60 seconds)

Refresh the page so the interviewer sees the **boot screen with the detailed step-by-step progress**.

> "Notice the initialization isn't just a spinner. Each step shows what's actually happening: loading WM Tech's Jira export, IB Tech's Excel tracker, AM Tech's SharePoint, GF Tech's budget CSV. Then status normalization across three different vocabularies. Then deterministic risk scoring. Then accountability mapping. Then the LLM-driven steps run in parallel — structured briefing and accountability narrative concurrently, with the markdown export derived directly from the structured JSON instead of asking the LLM to write it twice. Total: about three to five seconds with the live API.
>
> This is intentional. The interview brief mentioned the team currently spends days stitching this together. The point of leading with the boot screen is showing what's been automated, end-to-end, by the agentic pipeline."

Then point at the sidebar source pills.

> "Five fragmented sources because that's the actual problem. Each uses a different schema, a different status vocabulary — Green/Amber/Red versus On-Track/At-Risk versus In-Progress/Blocked — and even different date formats. This is exactly what the transformation team stitches together by hand today."

**Why:** Shows you understand the problem isn't 'we need a chart', it's 'we need normalization.' The boot screen also doubles as proof the system actually works deterministically. **The "parallel LLM calls" detail is interview gold** — it shows you think about cost and latency, not just functionality.

---

## 3. Walk through the agent pipeline (60 seconds)

Click **🔍 Agent Activity** tab. Let them see the trace.

> "Five specialized agents, composed by an orchestrator. Specialist over generalist is deliberate — one big prompt would be impossible to test, debug, or swap out. Each agent does one thing well:
>
> - **Data Aggregator** pulls from the five sources and produces a canonical schema. This is *not* AI — it's deterministic ETL.
> - **Risk Analyst** is the most important design decision. Risk *scoring* is rule-based — a 7-factor weighted model, completely auditable. The LLM only narrates *why*. In a regulated firm you cannot have a black-box scoring function deciding which initiative is at risk; Compliance and Model Risk would shut it down on day one.
> - **Accountability Agent** maps the validator → sponsor chain, finds bottlenecks, drafts escalation emails.
> - **Briefing Agent** synthesizes everything into the executive narrative. It generates structured JSON for the UI, and the markdown for export is derived from that same JSON — single source of truth, no double-spend on LLM calls.
> - **Q&A Agent** answers ad-hoc questions on demand, with clickable inline citations."

**Why:** This is where you separate yourself from someone who just plugged GPT into a CSV. You can articulate *what* you let the LLM do and *what you didn't* — and why.

---

## 4. Show the Executive Briefing (90 seconds)

Click **📝 Executive Briefing** tab.

> "This replaces the static slide deck. Same underlying information, but it has properties slides don't have. First, it's regenerated every time the underlying data changes — it can't be stale. Second, it's structured as decision-ready content, not prose to read."

**Walk through the sections top to bottom:**

1. **Headline** (gradient blue card) — what's the one thing to know
2. **Portfolio health strip** — 4 colored counters: Critical / At Risk / Watch / Healthy
3. **What's Working / What's Not Working** (side-by-side tables) — names and numbers, not vibes
4. **Who's Accountable for the Gaps** (table) — owners, sponsors, and validators by role
5. **Recommended Decisions** (numbered cards with Approve/Decline buttons)

**Concrete data to point at:**

> "The portfolio has **22 active initiatives**, **1 Critical, 4 At Risk**, total budget exposure **$45.8M FY26 with $39.5M consumed YTD — 86% utilization**. The headline failure is **RFQ Auto-Pricing in IB Tech — $4.5M approved, $8.3M spent (185% overrun), KPI delivering at 25%**. Owner is `person_013`; sponsor is `person_002` — Head of IB Tech. Validator sign-off has been pending **45 days**.
>
> But the briefing also tells a positive story: **GenAI Earnings Translation**, also IB Tech, was a Red disaster two quarters ago. After a hard restructure — new ownership, scope cut by 40%, biweekly validator cadence — it's now Green for two consecutive quarters. The briefing recommends explicitly: 'apply the Earnings Translation remediation template to RFQ.' That kind of cross-initiative learning is exactly what static slides can't do."

**The Approve / Decline buttons:**

> "Notice the decision cards have approve/decline buttons. The point of replacing slides is to convert the meeting from a status review into a decision forum. If leadership is reading instead of deciding, we haven't actually solved their problem."

**Export bar at the bottom:**

> "Same content, four formats: Markdown, HTML, Word, PDF. The Markdown goes into the audit trail. The HTML gets emailed inline. The Word doc goes to leadership for pre-read. The PDF goes to Compliance for archival. Zero manual labor — and the markdown export shares the same source-of-truth JSON as the on-screen cards, so they never drift."

---

## 5. Drill into an initiative — structured Risk Analyst (75 seconds)

Click **📋 Initiatives** tab. Filter to risk bucket "Critical" + "At Risk". Pick **RFQ Auto-Pricing** from the dropdown.

> "Three things to notice up here:
>
> 1. The **details table** flattens information from the source into a unified view. Source vocabulary is preserved — 'Status: Off Track (source: Red)' — so we can prove the normalization is faithful.
> 2. The **three colored metric cards** use independent color logic — Risk score by bucket, KPI by performance band, Budget by overrun severity. Not all-green checkmarks. The colors mean something.
> 3. The **Risk flags table** shows the deterministic factors that drove the score, each tagged with a category — Financial / Approval chain / Performance / Status / Freshness — and severity. This is the audit trail Compliance would need."

Then click **🤖 Ask Risk Analyst Agent**.

> "The deterministic flags are facts. The LLM-generated narrative is interpretation. They're presented separately. Notice the Risk Analyst's output is **structured into four sections**, not a paragraph: an Assessment, a side-by-side Strengths/Risks table with severity tags, and a single Recommended Next Step with owner and deadline.
>
> This shape is deliberate — it forces balance. The LLM is told explicitly: don't manufacture risks for healthy initiatives. If you click into one of the healthy ones, you'll see the Risks array can be empty, and the assessment leads with strengths. The agent's tone is calibrated to the actual risk bucket — measured language for healthy projects, direct language for critical ones — but it's never gratuitously alarmist. That's a defendable design choice in front of senior sponsors who get mad when their projects are misrepresented."

---

## 6. Accountability + escalations (75 seconds)

Click **✅ Accountability** tab. Point at the validator workload table.

> "**`person_005` (Risk) has 6 reviews assigned, 5 pending**. That's a single point of failure for the entire portfolio's reporting cycle, and it would have been buried in five different spreadsheets last month. There's also a secondary bottleneck — `person_008` (Legal) has 2 pending, including the **AM Climate Risk Model**, which has an EU SFDR regulatory deadline. That's not an inconvenience — that's legal exposure."

Scroll to the **Accountability Agent narrative card**.

> "The Accountability Agent gives you a structured assessment in the same shape as the briefing: headline, what's working, what's stuck with severity tags, and one specific action to take this week. That last card — 'The one action this week' — is intentionally singular. The agent doesn't dump 12 recommendations. It picks one."

Scroll to the **auto-drafted escalation messages**.

> "This is where 'agentic' pays off. The agent has already drafted 4 escalation messages — to the bottleneck validator, to the sponsors who need to sign off. Specific blocked initiatives listed. Specific two-question ask in each. The COO clicks Send. We've taken what's currently a 30-minute task — figuring out who's blocking what and writing the email — and made it a one-click action.
>
> Critically: the agent **drafts**, it does not **send**. Human-in-the-loop on every external action. That's the line between agentic and autonomous, and where I'd want any production system to be in a regulated firm."

---

## 7. Q&A with clickable citations — the killer demo (75 seconds)

Click **💬 Ask the Portfolio** tab.

> "Leadership doesn't just get the briefing — they get the data behind it. Anyone in the meeting can ask a follow-up live."

Click one of the sample questions, e.g. **"Which initiatives are at risk in our portfolio?"**.

> "Three things I want to highlight here:
>
> First, notice the **two-stage rendering** — my question appears in chat instantly, then there's a 'reasoning' bubble while the agent thinks. That's not fluff. In a real demo with senior leadership, dead air kills credibility — they need to see the system is working.
>
> Second, every factual claim has a **citation chip** inline — the blue `[WM-AI-1003]` pills you see scattered through the answer, and the `[SOURCE:...]` chips that point to which source system supplied the aggregate. At the bottom of the answer there's a sources-cited panel with full names. **This is non-negotiable in a regulated firm**: leadership cannot act on agent output without provenance, and Compliance will not approve a system that hallucinates without traceability."

**Now the killer move — click one of the citation chips, e.g. `[WM-AI-1003 ↗]`:**

> "Watch this. Each citation chip is a real hyperlink. Click it..."

*[Click — page jumps to Initiatives tab, drill-down auto-selects WM-AI-1003 Onboarding Document Intelligence, page smooth-scrolls to that section]*

> "...and we land directly on the drill-down for that initiative. The selectbox is pre-set, the page scrolls to the relevant section, and we have the full deterministic risk flags, the Risk Analyst's structured assessment, the budget breakdown — everything. **This converts the Q&A from information retrieval into investigation.** Leadership reads a claim, clicks to verify, sees the underlying data row, makes a decision. No 'let me get back to you with that detail.'
>
> Third, the input box stays pinned at the bottom even when history grows long. ChatGPT-style scroll behavior is what people expect."

---

## 8. Observability (30 seconds)

Click **📜 Logs** tab.

> "Every agent action, every LLM call, token counts, elapsed time, fallbacks if the API fails. In a regulated firm, the first question Compliance asks about an agentic system is *'how do you audit it'*, and the second is *'how do you know when the LLM is wrong'*. This panel is the answer. Logs are also written to file for post-mortem. Three sinks — console, file, in-memory — zero overhead each."

---

## 9. Land the design principles (45 seconds)

Stay on Logs tab or go to Agent Activity.

> "Five constraints I imposed on myself:
>
> 1. **Deterministic core, LLM at the edges.** Risk scores are rule-based and auditable. The LLM narrates; it doesn't decide.
> 2. **Specialist agents, not mega-prompts.** Each agent does one thing. Testable, swappable, composable.
> 3. **Source-of-truth preservation.** Owners keep their existing tools. The aggregator builds a unified view *on top* — adoption friction zero. Inside the system itself, the structured JSON is the single source of truth for the briefing UI, the markdown export, and the chat citations — they cannot drift.
> 4. **Decision-shaped output, not status-shaped.** The briefing ends in numbered, approvable items. The chat citations are clickable links, not just labels. The meeting becomes a decision forum.
> 5. **Graceful degradation.** Demo runs with or without an API key. If the API fails mid-demo, the LLM client silently falls back to a deterministic mock so the demo never breaks.
>
> These came directly from imagining the real conversation with Compliance, with Model Risk, with the BU Tech heads who don't want to migrate to a new system. The prototype could have been twice as flashy if I'd ignored them, but it would not have been deployable inside Morgan Stanley."

---

## 10. What you'd build next (30 seconds)

> "If I had two real weeks instead of 48 hours: real connectors for Jira, ServiceNow, SharePoint, and the firm's data lakes. Drift detection on the briefing itself, so leadership sees what *changed* this month, not just current state. Source-row provenance on every LLM-generated claim, with click-through to the data row. Validator-side workflow — same agent platform, surfaced to validators as their own queue with auto-drafted RFI when a submission is incomplete. And meta-monitoring on the agent pipeline itself, to prove this system is cheaper than the manual process it replaces."

---

## Likely interview questions and how to answer them

### Q: "How would you handle hallucinations in the executive briefing?"

> "Three layers. First, the deterministic risk scores are non-negotiable ground truth — the LLM is given them and explicitly told the score itself is fixed. The portfolio health counter on the briefing is computed from data, not produced by the LLM. Second, the LLM is given structured facts only, never raw unstructured text from the source systems. Third, every factual claim in the Q&A response has an inline citation marker that the UI renders as a clickable chip — and clicking it takes you to the underlying drill-down. So a hallucinated claim about an initiative is visibly suspicious because the chip would lead to data that doesn't support it. We don't ship a briefing system to senior leadership without that level of traceability."

### Q: "Why agents instead of just one big prompt?"

> "Three reasons. **Testability** — I can unit-test the risk scorer independently of the LLM. **Cost** — the deterministic agents don't call the LLM at all; only the narrative steps do. The pipeline now uses just two parallel LLM calls per init, with the markdown export derived from the structured JSON instead of asking the LLM to write it twice. And **vendor flexibility** — if Anthropic goes down, the Q&A agent can be swapped to OpenAI without touching the aggregator or risk scorer. The 5-agent architecture lets each piece be evaluated, replaced, or improved independently."

### Q: "How does this scale to 200 initiatives instead of 22?"

> "The deterministic pipeline scales linearly and cheaply — at 200 initiatives, scoring still finishes in under a second. The LLM cost scales with how much narrative we generate, which is why the briefing is portfolio-level rather than per-initiative. Per-initiative narrative is generated on demand from the drill-down — you don't pay for it unless someone clicks. At 200 initiatives the bigger problem isn't compute, it's that the briefing becomes a wall of text. That's where I'd add hierarchical summarization — by BU first, then drill into individual initiatives only on click."

### Q: "What if a business unit doesn't want to share their data?"

> "Two answers. First, this is a read-only system — we're not asking them to change their workflow or expose anything they don't already share with the transformation team. Second, the canonical schema is intentionally minimal — we only need status, owner, KPI, and approval state. We don't need to see anyone's underlying source code or proprietary models. That's a much easier conversation than 'give us all your data.'"

### Q: "What's actually 'agentic' here vs just an LLM-powered dashboard?"

> "Three things distinguish this from a dashboard with an LLM bolted on. **First, the agents act on data** — the Accountability Agent doesn't just describe a problem, it drafts the email to fix it. **Second, they compose** — the orchestrator runs them in sequence and each one's output becomes the next one's input. **Third, they have specialization and division of labor** — that's the architectural pattern, and it's what lets the system scale to more capabilities without becoming a single fragile prompt."

### Q: "You said 'human in the loop' — what's the boundary between draft and send?"

> "Right now: the agent never sends. Every external-facing action — escalation emails, sponsor pings, decision logging — is **drafted** with the recipient, subject, body, and reasoning all visible to the COO. The COO clicks Send. In production, I'd want this to be a configurable boundary per action type. Routine 'reminder to update status' nudges might be safe to send autonomously after a 24-hour review window. But anything that touches a senior sponsor or makes a budget claim stays human-approved indefinitely. The architecture supports either; it's a policy choice, not a technical one."

### Q: "What did you specifically not do that you wish you had?"

> "Four things. **Real connectors** — everything is mock data. The schemas are realistic but it's not actually wired to live systems. **Drift / change detection** — the briefing is a snapshot, not a delta. The most valuable thing in a monthly review is what changed, not the current state. **Validator-side workflow** — I built the COO view but not the validator view. Validators need their own queue, auto-drafted RFIs when a submission is incomplete, and a way to push back without sending email. **Cost telemetry on the pipeline itself** — to prove the system is cheaper than the manual process it replaces, I'd need a $-per-briefing metric tracked over time."

### Q: "Show me where the LLM could go wrong, and how you'd catch it."

> "Three scenarios I designed against:
>
> **(1) JSON parsing failure.** The Briefing Agent, Risk Analyst, and Accountability Agent all ask the LLM for valid JSON. If it returns something else, my `_parse_json` helper returns a fallback structure with the raw text exposed under `_raw_fallback`, and the UI shows a warning expander instead of crashing.
>
> **(2) API failure mid-demo.** The LLM client wraps every Anthropic call in try/except. On exception, it logs the error type and falls back to a deterministic mock. The Logs tab surfaces fallback count as a top-level metric — leadership can see when something went wrong.
>
> **(3) Confident hallucination.** Hardest to catch. My current defense is putting structured facts in the prompt, not free text, and explicitly listing the valid initiative IDs the LLM is allowed to cite. The next layer is the inline citation requirement: every factual claim in the Q&A must have a citation marker, which means an unsupported claim is visibly missing its evidence chip — and clicking the chip takes you to the underlying data, so a misleading narrative would be exposed. The most important defense is that the **deterministic risk scores never come from the LLM** — so the worst-case hallucination is a misleading narrative attached to a correct risk classification."

### Q: "Why does the Risk Analyst output have such different tone for healthy vs critical projects?"

> "I built that in deliberately because the first version was too aggressive — it would manufacture risks even for projects with clean signals, which is exactly the kind of behavior that gets a system shut down by sponsors who feel their projects are being unfairly characterized. So I added explicit tone guidance in the prompt that varies by risk bucket: for Healthy projects, lead with strengths and only flag risks that are clearly evidenced; risks array can legitimately be empty. For Critical projects, be direct about the issues but still acknowledge any genuine strengths visible in the data. The structured JSON schema with separate Strengths and Risks arrays *forces* balance — the agent can't just produce a one-sided takedown anymore."

### Q: "Walk me through how you optimized the initialization latency."

> "Original implementation made four sequential LLM calls — structured briefing JSON, markdown briefing, structured accountability JSON, accountability narrative text. About 12-20 seconds on the live API.
>
> First optimization: I noticed the markdown briefing was just a different rendering of the same underlying content as the structured JSON. So I wrote a deterministic helper that takes the structured JSON and produces markdown — saves one LLM call entirely, and as a bonus the markdown export now shares the same source of truth as the on-screen cards, so they can never drift apart.
>
> Second optimization: the accountability narrative-as-prose was actually never displayed in the UI — it was a vestigial output kept for backward compat. I removed it. Saves another LLM call.
>
> Third optimization: the two remaining calls — briefing structured + accountability structured — are independent. They don't depend on each other's outputs. So I wrapped them in a `ThreadPoolExecutor` and ran them in parallel. LLM API calls are I/O bound so the GIL releases, threading works fine.
>
> Net result: 4 sequential calls became 2 parallel calls. Roughly 4x faster. About three to five seconds end-to-end."

---

## Demo gotchas (the boring stuff that breaks demos)

- **Test the API key the morning of**. Console.anthropic.com sometimes requires re-confirming billing. The mock fallback covers you, but the live LLM gives a much more impressive briefing.
- **Don't share your terminal screen if the API key is exported there**. Either use the `.env` file or close the terminal before screen-sharing.
- **Don't open the Initiatives table first if you're rushed for time**. It's a wall of data; the briefing tab tells the story faster.
- **The Approve / Decline buttons are placeholders**. If asked, say "in production these would write to the decision log and notify the owner — I scoped that out for the 48-hour timeline."
- **The Q&A chat works best on the sample questions**. They're tested. If you ad-lib a question and the answer is weak, lean on "this is the mock LLM giving a deterministic response — with the live API the answer would be much richer."
- **Practice the citation-chip click**. The first time you click a chip during the demo, hold for a beat — the page will jump tabs, auto-select the initiative, and smooth-scroll to the drill-down. Don't keep talking through the transition; let the interviewer SEE it work. That moment is the most impressive UX in the prototype.
- **If the boot screen flashes too fast on a refresh**, that's the cache hit path — Streamlit's `@st.cache_resource` is keeping the pipeline result alive across reloads, so the second-time-around boot is intentionally instant.

---

## What NOT to do in the demo

- **Don't** apologize for using mock data. The whole point is showing you understand the *real* data landscape; mock data is the right call for a 48h prototype.
- **Don't** demo every feature. Pick the 5 tabs that tell the story (Briefing, Initiatives drill-down, Accountability, Chat, Logs). Skip Overview if time-pressed — its content is a subset of the Briefing.
- **Don't** bury the design principles. They're what separates this from a college project. Land them explicitly at the end.
- **Don't** oversell the LLM. Be precise about what it does and doesn't do.
- **Don't** read the screen. Look at the interviewer. Use the screen as your annotation, not your script.
