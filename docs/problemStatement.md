# Weekly Review Pulse — Problem Statement

## Overview

We are building an automated weekly **pulse** that turns public **Google Play** reviews for **Groww** into a one-page insight report and delivers it to stakeholders through Google Workspace.

All external integrations go through **MCP (Model Context Protocol)** servers—not ad hoc API calls inside the agent:

- **Play Store Reviews MCP** — fetches public Play Store reviews (built and provided in this project).
- **Google Docs MCP** — appends weekly report sections to a running document.
- **Gmail MCP** — sends stakeholder notification emails with a link to the report.

### Current Scope

| Dimension | In scope (now) | Deferred |
|-----------|----------------|----------|
| **Product** | Groww only | INDMoney, PowerUp Money, Wealth Monitor, Kuvera |
| **Review source** | Google Play only | Apple App Store |

The design should remain extensible so additional products and sources can be added later without rewriting the core pipeline.

---

## Objective

Give product, support, and leadership teams a repeatable, weekly snapshot of what Groww customers are saying in **Play Store** reviews: **themes**, **representative quotes**, and **actionable ideas**—without manual copy-paste or one-off spreadsheets.

---

## What the System Does

### 1. Ingest (via Play Store Reviews MCP)

Pull public Google Play reviews for Groww from the last **8–12 weeks** (configurable window) by calling tools on the **Play Store Reviews MCP server** included in this project.

| Source | Method |
|--------|--------|
| Google Play | Play Store Reviews MCP (this project) |

The agent does not scrape Play Store directly or embed review-fetch logic in application code—it invokes the MCP server’s tools (e.g. fetch reviews for a package ID / app, with date or count filters as defined in the server).

### 2. Analyze

- Cluster and rank feedback using embeddings and density-based clustering (e.g. **UMAP + HDBSCAN**).
- Use an LLM to name themes, pull verbatim quotes, and propose action ideas.
- **Validation:** quotes must appear in real review text.

### 3. Render

Produce a concise one-page narrative:

- Top themes
- Quotes
- Action ideas
- Short “who this helps” section

### 4. Deliver (MCP Only)

Outputs go **only** through Google Workspace MCP servers:

| MCP Server | Behavior |
|------------|----------|
| **Google Docs MCP** | Append each week’s report as a new dated section to a single running document (*Weekly Review Pulse — Groww*). The Doc is the system of record and preserves history. |
| **Gmail MCP** | Send a short stakeholder email with a deep link to the new section in that Doc (heading link)—not a duplicate full report in email alone. |

### Architecture: Separation of Concerns

| Concern | Where It Lives |
|---------|----------------|
| Data retrieval | **Play Store Reviews MCP** (provided in this project) |
| Reasoning | Clustering + LLM summarization (themes, quotes, actions) |
| Output generation | Report + email rendering (structured for Docs; HTML/text for Gmail) |
| Human-visible delivery | MCP tools only → Google Docs MCP + Gmail MCP |

> The agent is an **MCP host/client**. It does not embed Google credentials, scrape Play Store directly, or call Docs/Gmail REST APIs for delivery. Review ingestion is exclusively through the Play Store Reviews MCP server shipped with this project.

### MCP Servers in This Project

| Server | Role |
|--------|------|
| **Play Store Reviews MCP** | Exposes tools to fetch and return public Google Play reviews for Groww (and, later, other apps). Implemented and configured as part of this repository. |
| **Google Docs MCP** | External / separate server — append dated sections to the pulse Doc. |
| **Gmail MCP** | External / separate server — draft or send stakeholder emails. |

---

## Key Requirements

| Requirement | Detail |
|-------------|--------|
| **MCP-based ingestion** | Fetch Play Store reviews only via the Play Store Reviews MCP server in this project—not inline scrapers or direct HTTP calls from the agent. |
| **MCP-based delivery** | Append to the shared Google Doc and send Gmail only via the respective MCP servers’ tools (e.g. document batch update, draft/create/send flows as defined in architecture). |
| **Weekly cadence** | Designed to run once per week for Groww (e.g. scheduled job Monday morning IST), with a CLI for backfill of any ISO week. |
| **Idempotent runs** | Re-running the same ISO week must not create duplicate Doc sections or duplicate sends. Enforced with a stable section anchor in the Doc and a run-scoped idempotency check on email (see architecture). |
| **Auditable** | Each run records delivery identifiers (e.g. doc heading / message ids) and enough metadata to answer “what was sent when, for which week?” |
| **Safety and quality** | PII scrubbing on review text before LLM and before publishing; reviews treated as data, not instructions; cost/token limits per run. |

---

## Non-Goals (Explicit)

- **Additional products** (INDMoney, PowerUp Money, Wealth Monitor, Kuvera) in the initial build—Groww only.
- **Apple App Store** reviews or iTunes RSS ingestion in the initial build—Google Play only.
- A generic Google Workspace product beyond what the pulse needs (Docs append + Gmail send/draft).
- Real-time streaming analytics or a BI dashboard (the running Google Doc is the living artifact).
- Social sources (Twitter, Reddit, etc.) in the initial scope.
- Storing Google OAuth secrets in the agent codebase—they belong in the MCP servers’ configuration, per architecture.
- Embedding Play Store scraping logic in the agent—the Play Store Reviews MCP server owns that concern.

---

## Who This Helps

| Audience | Value |
|----------|-------|
| **Product** | Prioritize roadmap from recurring themes in Groww Play Store feedback |
| **Support** | Spot repeating complaints and quality issues |
| **Leadership** | Fast health snapshot tied to customer voice |

---

## Sample Output (Illustrative)

### Groww — Weekly Review Pulse

**Period:** Last 8–12 weeks (rolling window)  
**Source:** Google Play reviews only

#### Top Themes

1. **App performance & bugs** — Lag, crashes during trading hours; login/session timeouts.
2. **Customer support friction** — Slow responses; unresolved tickets.
3. **UX & feature gaps** — Confusing navigation for portfolio insights; missing advanced analytics.

#### Real User Quotes

- “The app freezes exactly when the market opens, very frustrating.”
- “Support takes days to reply and doesn’t solve the issue.”
- “Good for beginners but lacks detailed analysis tools.”

#### Action Ideas

- **Stabilize peak-time performance** — Scale infra during market hours; improve crash visibility.
- **Improve support SLA visibility** — Expected response time in-app; ticket status tracking.
- **Enhance power-user features** — Advanced portfolio analytics; clearer investments navigation.

---

## What This Solves

Roadmap alignment for product, issue clustering for support, and a leadership-friendly snapshot—now **automated** from **Groww Play Store reviews**, **archived in Google Docs**, and **announced by email** with a link back to the canonical section.

---

## Delivery Expectations (Stakeholder-Facing)

1. Each run adds **one clearly labeled section** to the Groww pulse Google Doc (dated / week-labeled).
2. The email is a **brief teaser** (e.g. top themes as bullets) plus a “Read full report” link to that section.
3. Development/staging may default to **draft-only email** until explicit confirmation to send, per implementation plan.
