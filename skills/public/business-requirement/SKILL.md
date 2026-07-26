---
name: business-requirement
description: Structure business objectives, stakeholder needs, and process flows with quantified ROI. Use when the user asks for "business requirements", "BRD", "business case", "stakeholder needs", "process improvement", "business analysis", or "requirements gathering". Covers current/future state analysis, feasibility, risk, and cost-benefit.
---

# Business Requirement Skill

## Purpose

Produce a complete Business Requirements Document (BRD) that aligns stakeholders, defines business objectives, maps current and future processes, quantifies costs and benefits, and identifies risks. This is not a technical spec — it describes what the business needs and why.

---

## Phase 1: Business Context

**Gate: Must complete before any detailed analysis.**

### What to Establish

Ask with `ask_clarification` if not provided:

| Question | Why |
|---|---|
| What is the business problem or opportunity? | Defines the reason for the project |
| Who requested this? Who pays? | Identifies the sponsor |
| What happens if we do nothing? | Establishes urgency |
| What is the business goal? (revenue / cost / compliance / retention / growth) | Aligns measurement |
| Who are the stakeholders? | Identifies who needs to approve |
| What is the timeline? | Defines scope boundaries |
| What is the budget? | Defines feasibility |

### Output

```
## Business Context

### Problem / Opportunity Statement
{One paragraph describing the business problem or opportunity}

### Business Objectives

| Objective | KPI | Current Value | Target Value | Timeline |
|---|---|---|---|---|
| Increase revenue | Monthly recurring revenue | $50K | $75K | 6 months |
| Reduce cost | Support tickets closed manually | 500/month | 200/month | 3 months |
| Improve retention | 90-day churn rate | 8% | 4% | 12 months |

### Stakeholders

| Name/Role | Interest | Influence (H/M/L) | Concerns | Approval Needed? |
|---|---|---|---|---|
| Head of Sales | Pipeline growth | High | Team training time | Yes |
| CFO | Budget impact | High | ROI | Yes |
| IT Director | Technical feasibility | Medium | Integration effort | No |
| End users | Usability | Low | Learning curve | No |
```

---

## Phase 2: Current State Analysis

**Gate: Business context defined.**

### What to Map

```
## Current State — "As-Is"

### Process Flow
{Describe or diagram the current process step by step}

### Pain Points

| Pain Point | Impact (Frequency × Severity) | Who Feels It |
|---|---|---|
| Manual data entry | Daily × High | Operations team |
| No visibility into pipeline | Weekly × Medium | Sales team |
| Approval takes 3 days | Per request × High | All stakeholders |

### Current Costs

| Cost Item | Monthly Cost | Annual Cost |
|---|---|---|
| Manual labor (hours) | $X | $Y |
| Tooling/licenses | $X | $Y |
| Error correction (waste) | $X | $Y |
| **Total** | **$X** | **$Y** |

### Constraints
| Constraint | Source | Impact |
|---|---|---|
| Existing system must remain during migration | IT policy | Phased rollout required |
| Budget capped at $50K | Finance | Must scope to MVP |
| 3-month deadline | Executive | Start ASAP, no perfect solution |
```
---

## Phase 3: Future State — Requirements

**Gate: Current state documented.**

### Requirements Categories

```
## Future State — "To-Be"

### Business Requirements (WHAT the business needs)

| ID | Requirement | Priority (MoSCoW) | Stakeholder Source |
|---|---|---|---|
| BR-01 | Sales team can view real-time pipeline dashboard | Must-have | Head of Sales |
| BR-02 | Approval workflow completes within 4 hours | Must-have | All stakeholders |
| BR-03 | Data entry reduced by 80% | Should-have | Operations |
| BR-04 | Mobile access for field agents | Could-have | Field team |

### Functional Requirements (WHAT the system must do)

| ID | Requirement | Maps To (BR) |
|---|---|---|
| FR-01 | Dashboard auto-refreshes every 60s | BR-01 |
| FR-02 | Notifications sent via email + in-app | BR-02 |
| FR-03 | CSV/API import from current system | BR-03 |
| FR-04 | Responsive web interface down to 320px | BR-04 |

### Non-Functional Requirements

| ID | Requirement | Target | Maps To (BR) |
|---|---|---|---|
| NFR-01 | System available 99.5% uptime | Monthly | BR-01 |
| NFR-02 | Dashboard loads in < 3s | p95 | BR-01 |
| NFR-03 | Support 50 concurrent users | MVP | BR-03 |
| NFR-04 | Data encrypted at rest and in transit | Compliance | All |
```

---

## Phase 4: Process Design

**Gate: Requirements defined.**

### Future Process Flow

```
## Proposed Process — "To-Be"

1. Sales rep enters customer data → auto-saved (no save button)
2. System checks for duplicates → if found, suggest merge
3. Approval request sent → manager notified via app + email
4. Manager approves/declines from phone → < 4 hours
5. System notifies sales rep → proceeds to next step

### Changes from Current Process

| Step | Before | After | Benefit |
|---|---|---|---|
| Data entry | Manual, 10 min per record | Auto-import + validation, 2 min | 80% time reduction |
| Approval | Email chain, 3 days avg | In-app approval, 4 hours max | 96% faster |
| Visibility | Weekly email report | Real-time dashboard | Always current |
```

---

## Phase 5: Feasibility & Risk

**Gate: Requirements and process design complete.**

### Feasibility Assessment

| Dimension | Assessment | Evidence |
|---|---|---|
| Technical | Feasible | Similar integrations done before |
| Operational | Requires 2 new hires | Training plan needed |
| Timeline | Tight but achievable | MVP in 2 months, full in 4 |
| Budget | $45K of $50K allocated | Contingency cushion available |

### Risk Register

| Risk | Likelihood | Impact | Mitigation | Owner |
|---|---|---|---|---|
| Integration delays | Medium | High | Start integration first, buffer 2 weeks | Dev lead |
| User adoption low | Medium | Medium | Training sessions, phased rollout | Ops lead |
| Scope creep | High | Medium | Strict MoSCoW, change control board | PM |
| Key person leaves | Low | High | Cross-training, documentation | HR |

### Assumptions

1. {assumption} — if wrong, impact is {impact}
2. {assumption} — if wrong, impact is {impact}

---

## Phase 6: Cost-Benefit Analysis

**Gate: Feasibility accepted.**

### Costs

| Cost Category | Year 1 | Year 2 | Year 3 |
|---|---|---|---|
| Development | $X | $0 | $0 |
| Licensing | $X | $X | $X |
| Operations | $X | $X | $X |
| Training | $X | $0 | $0 |
| **Total** | **$X** | **$X** | **$X** |

### Benefits

| Benefit Category | Year 1 | Year 2 | Year 3 |
|---|---|---|---|
| Labor savings | $X | $X | $X |
| Revenue increase | $X | $X | $X |
| Error reduction | $X | $X | $X |
| **Total** | **$X** | **$X** | **$X** |

### ROI Summary

| Metric | Value |
|---|---|
| Total investment (3 years) | $X |
| Total benefit (3 years) | $X |
| Net benefit | $X |
| ROI | X% |
| Payback period | X months |
```

---

## Phase 7: Deliver

### Final Document

```
# Business Requirements Document: {Project Name}

## 1. Executive Summary
{One-page summary of the entire BRD}

## 2. Business Context
{Phase 1}

## 3. Current State Analysis
{Phase 2}

## 4. Requirements
{Phase 3}

## 5. Process Design
{Phase 4}

## 6. Feasibility & Risk
{Phase 5}

## 7. Cost-Benefit Analysis
{Phase 6}

## 8. Recommendations
{Specific recommended action with justification}
```

### Bare Minimum

| Phase | Minimum deliverable |
|---|---|
| Context | Problem statement + 3 business objectives with KPIs |
| Current state | Pain points table + current costs |
| Requirements | 5 requirements (mix of BR/FR/NFR) |
| Feasibility | Risk register with 3 risks |
| Cost-benefit | Simple 1-year cost vs benefit estimate |
| Recommendation | Clear "do this / don't do this" with one-sentence justification |

### Quality Gates

- [ ] Every requirement is traceable to a business objective
- [ ] Costs and benefits are quantified (not "save money" but "save $X/year")
- [ ] Stakeholders are identified with their interests
- [ ] Risks have both mitigation AND an owner
- [ ] The deliverable ends with an actionable recommendation
