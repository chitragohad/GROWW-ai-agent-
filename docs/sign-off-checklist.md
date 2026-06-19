# Stakeholder Sign-Off — Groww Weekly Review Pulse

Complete this checklist before enabling production `mode=send` on the weekly scheduler.

| Field | Value |
|-------|-------|
| Product | Groww |
| Reviewer | |
| Date | |
| ISO week reviewed | e.g. 2026-W24 |

---

## Report quality

- [ ] **Themes** — Top themes reflect real user pain points and praise (not generic)
- [ ] **Quotes** — Quotes are verbatim excerpts from Play Store reviews (no hallucinations)
- [ ] **Action ideas** — Suggestions are specific and actionable for product/support teams
- [ ] **Volume** — Review count and window (10 weeks) are reasonable for the report

## Delivery

- [ ] **Google Doc** — Section appended with correct heading and anchor `groww-{iso_week}`
- [ ] **Doc URL** — Link opens the right section in *Weekly Review Pulse — Groww*
- [ ] **Email** — Subject `Groww Weekly Review Pulse — {iso_week}`; deep link works
- [ ] **Recipients** — Stakeholder list in `PULSE_EMAIL_RECIPIENTS` is correct

## Operations

- [ ] **Idempotency** — Re-run same week produces no duplicate Doc section or email
- [ ] **Dry-run tested** — `pulse dry-run --product groww` completes locally
- [ ] **Staging draft tested** — `pulse run --email-mode draft` verified in Gmail drafts
- [ ] **Alerts** — Failure webhook tested (optional) or `pulse check-failures` reviewed

## Approval

- [ ] **Sign-off** — Product lead approves weekly pulse for production send

**Approver signature / name:** ___________________________

**Notes:**
