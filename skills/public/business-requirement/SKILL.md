---
name: business-requirement
description: Elicit and document complete business requirements through continuous dialogue, end-to-end process mapping with Mermaid diagrams, scope management, feasibility assessment, and polished BRD output. Use when the user asks for "business requirements", "BRD", "business case", "stakeholder needs", "process improvement", "business analysis", or "requirements gathering".
---

# Business Requirement Skill

## Purpose

Elaborate a complete Business Requirements Document through **continuous dialogue**, not assumption. The AI asks questions at every stage, maps end-to-end flows with Mermaid diagrams, maintains scope boundaries, assesses feasibility, and produces a polished, professional BRD that stakeholders can act on.

---

## Phase 0: Continuous Context Discovery

**Gate: NEVER complete. Keep asking through every phase.**

### Rules of Engagement

1. **No guessing** — if something is unclear, ask. Do not assume.
2. **One question at a time** — do not batch. Each answer informs the next question.
3. **Ask why** — when the user states a requirement, ask: "Why is this needed? What problem does it solve?"
4. **Ask who** — for every process step: "Who does this? Who approves? Who is blocked?"
5. **Ask when** — "When does this happen? Daily? Monthly? On trigger?"
6. **Ask what if** — "What happens if this step fails? What is the backup today?"

### Initial Discovery Questions

Ask in this order, one at a time:

1. "What is the core business problem or opportunity? One sentence."
2. "What happens if nothing changes? Who feels the pain most?"
3. "Who are the people involved? (roles, not names)"
4. "What is the current budget and timeline constraint?"
5. "What does success look like in measurable terms?"
6. "Are there existing systems or processes this must integrate with?"
7. "Who has final approval authority?"

### Output Template (filled as you learn)

```
## Discovery Notes

### Core Problem
{single sentence}

### Business Impact
{what happens if nothing changes}

### Stakeholders (discovered continuously)
| Role | Interest | Pain Level | Authority |
|---|---|---|---|

### Constraints
| Constraint | Source | Impact |
|---|---|---|

### Success Criteria
{how the user will know it worked — with numbers}
```

---

## Phase 1: End-to-End Process Mapping

**Gate: Full context gathered before mapping flows.**

### Map the Current State (As-Is)

Walk through the current process step by step with the user. Ask for EVERY step:

```
"Walk me through what happens from start to finish.

Start: {trigger event}
  → What happens next? Who does it?
  → Then what? Who approves?
  → How long does each step take?
  → What tools or systems are used at each step?
  → Where do handoffs happen? What information is passed?
  → What breaks? What are the common failure points?
End: {final outcome}"
```

### Required Mermaid Diagram — Current State

Every process MUST be visualized as a Mermaid flowchart:

```mermaid
flowchart TD
    A[Trigger: {event}] --> B[Role: {action}]
    B --> C{Decision point?}
    C -->|Yes| D[Role: {action}\nTool: {tool}\nTime: {duration}]
    C -->|No| E[Role: {action}]
    D --> F[End: {outcome}]
    E --> F

    style D fill:#ffcccc
    style E fill:#ffffcc
```

- Red nodes = pain points, bottlenecks
- Yellow nodes = manual steps that could be automated
- Green nodes = working well

### Required Mermaid Diagram — Future State (To-Be)

Propose and validate the future flow:

```mermaid
flowchart TD
    A[Trigger] --> B[Automated: {action}\nBenefit: {improvement}]
    B --> C[Role: {action}]
    C --> D[End: {outcome}\nMetric: {KPI}]
```

### Real-World Alternatives

For each key decision, present alternatives with tradeoffs:

```
### Decision: {what to decide}

| Option | Pros | Cons | Cost | Timeline | Risk |
|---|---|---|---|---|---|
| A: {approach} | {benefits} | {drawbacks} | $X | X weeks | {risk} |
| B: {approach} | {benefits} | {drawbacks} | $X | X weeks | {risk} |
| C: Do nothing | {benefits} | {drawbacks} | $0 | N/A | {risk} |

**Recommended**: Option {X} because {rationale}. Confirmed by user: Yes / No
```

---

## Phase 2: Scope Management

**Gate: Processes mapped before scoping.**

### Define Boundaries Explicitly

```
### In Scope
- {item 1} — because {reason}
- {item 2} — because {reason}

### Out of Scope (Explicitly Excluded)
- {item 1} — because {reason}. Will revisit in {Phase 2 / Never}
- {item 2} — because {reason}

### Gray Area (Needs Decision)
- {item} — unclear if in scope. Ask: {question for stakeholder}
```

### Scope Creep Detection

Periodically (after every 3-4 requirements), check:

```
"Let me pause and check alignment.

Original intention: {restate the core problem from Phase 0}
Current discussion: {what we are talking about now}

Are we still on track? Has anything changed since we started?"
```

If the user adds requirements beyond the original scope:
- Flag it immediately: "This is new. It was not part of the original scope. Should we add it to the BRD as Phase 2, or include it now?"
- Update the scope section.

---

## Phase 3: Intention Anchoring

**Goal**: Prevent drift. Every requirement must trace back to the original business objective.

### Intention Chain

For each requirement, ask:

```
"I understand you want {requirement}. This addresses {business objective from Phase 0}.

How critical is this? Must-have, should-have, or nice-to-have?

If this is not delivered in the initial release, what would the impact be?"
```

### Changed Intentions Log

If the user changes their mind during the process:

```
### Intention Changes Log

| Original Intent | Changed To | Why | When | Approved By |
|---|---|---|---|---|
| Build full mobile app | Build responsive web app | Budget constraint | Phase 2 | CFO |
```

---

## Phase 4: Feature Feasibility Assessment

**Gate: Requirements defined and scoped.**

### For Each Feature or Requirement

Assess feasibility on 4 dimensions:

```
### Feasibility Assessment

| Requirement | Technical | Operational | Financial | Timeline | Overall | Confidence |
|---|---|---|---|---|---|---|
| {req} | {Feasible/Risky/Blocked} | {Feasible/Needs Hire} | {In Budget/Over} | {On Track/Tight} | {Go/Caution/Stop} | High/Med/Low |
```

### Technical Feasibility

- Does the technology exist? Is it proven?
- Does the team have the skills?
- Are there integration risks with existing systems?

### Operational Feasibility

- Can the organization absorb the change?
- Is training needed? How much?
- Will existing processes break during transition?

### Financial Feasibility

- Is it within budget? If not, what is the gap?
- What is the operational cost after launch?
- What is the expected ROI timeline?

### Timeline Feasibility

- Can it be delivered by the deadline?
- What is the critical path? What has no slack?
- What can be descoped to meet the date?

---

## Phase 5: Glossary

**Goal**: Maintain a shared vocabulary. Update continuously.

### Glossary Template

```
## Glossary

| Term | Definition | Used In | Clarified By |
|---|---|---|---|
| {term} | {precise definition — no ambiguity} | Phases {X-Y} | {user / AI} |
| {acronym} | {expansion + definition} | Phases {X-Y} | {user / AI} |
```

### Glossary Rules

1. Define every domain-specific term the first time it appears
2. Define every acronym — spell it out
3. If the user uses a term ambiguously, ask: "You said {term}. Does that include {interpretation A} or just {interpretation B}?"
4. Add terms proactively when you detect potential confusion

---

## Phase 6: Consistency Review

**Gate: All content drafted before consistency check.**

### Cross-Reference Checks

Before finalizing, verify:

| Check | How |
|---|---|
| No contradictions | Scan all requirements — does any requirement conflict with another? |
| Consistent terminology | Every term matches the Glossary. No synonyms for the same concept. |
| Traceability | Every requirement maps to a business objective from Phase 0 |
| Completeness | No phase left empty. All templates filled. |
| Forward references | Nothing references a section that does not exist |

### Back-to-Forth Consistency

When adding new content, re-read earlier phases:

```
"I am about to add {new content} in Phase {N}.
This relates to {earlier content} in Phase {X}.
Let me cross-check: are these consistent? Do they conflict?
If they conflict, I will flag it now.
```

---

## Phase 7: Polish & Format

**Gate: All content complete and consistent.**

### Output Standards

| Element | Standard |
|---|---|
| **Executive summary** | 1 page. Busy executive can read it in 2 minutes and decide. |
| **Tables** | All using consistent column alignment. Monetary values right-aligned. |
| **Diagrams** | All Mermaid. Every process has both as-is and to-be. |
| **Headings** | Consistent depth: Phase → Section → Subsection. No skipped levels. |
| **Tone** | Professional, neutral, data-driven. No exclamation marks. No passive-aggressive notes. |
| **Citations** | Every data point has a source or an explicit assumption marker. |

### Final BRD Structure

```
# Business Requirements Document: {Project}

## Executive Summary
{Problem, recommendation, cost, timeline, ROI — 1 page}

## 1. Discovery Notes
{Phase 0}

## 2. Process Maps
### Current State
{Mermaid diagram + narrative + pain points}
### Future State
{Mermaid diagram + improvements + KPIs}
### Alternatives Considered
{Decision tables}

## 3. Scope
{In scope, out of scope, gray area}

## 4. Requirements
### Business Requirements
### Functional Requirements
### Non-Functional Requirements
{All traced to business objectives}

## 5. Feasibility Assessment
{Per-requirement feasibility matrix}

## 6. Risk Register
{Risks with likelihood, impact, mitigation, owner}

## 7. Cost-Benefit Analysis
{Costs, benefits, ROI, payback period}

## 8. Glossary
{All terms and acronyms}

## 9. Intention Changes Log
{Drift tracking}

## 10. Recommendations
{Clear, specific, actionable}
```

---

## Bare Minimum

Under tight constraints:

| Deliverable | Minimum |
|---|---|
| Core problem | 1 sentence |
| Stakeholders | 3 roles with interests |
| As-is flow | Mermaid diagram with 5+ nodes |
| To-be flow | Mermaid diagram with 5+ nodes |
| Requirements | 5 minimum, traced to objectives |
| Scope | In-scope + out-of-scope explicitly |
| Glossary | 5+ terms defined |
| Recommendation | Clear yes/no with rationale |

## Quality Gates

- [ ] Every requirement traces back to a business objective from Phase 0
- [ ] Both as-is and to-be processes have Mermaid diagrams
- [ ] Scope is explicitly defined (what is IN and what is OUT)
- [ ] Feasibility assessed on all 4 dimensions for each feature
- [ ] Glossary covers all domain terms and acronyms
- [ ] No contradictions between sections (cross-referenced)
- [ ] Intention changes are logged if any occurred
- [ ] Executive summary is 1 page, actionable, professional
