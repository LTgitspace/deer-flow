---
name: product-requirements
description: "Create a product requirements document (PRD): product vision, personas, user problems, measurable success metrics, scope, prioritized features with acceptance criteria, UX considerations, release criteria, and roadmap. Use when the user asks for a \"PRD\", \"product requirements\", \"product spec\", \"product doc\", or feature definition for a product. Bridge between BRD (business case) and SRS (engineering specification)."
---

# Product Requirements Skill

## Purpose

Turn a product idea into a complete PRD that a design and engineering team can build against without guessing: who the product serves, what problem it solves, what success looks like in numbers, what is in and out of scope, and which features ship first.

---

## Phase 1: Context Discovery

**Gate: Must complete before writing any requirements.**

### What to Establish

Ask the user with `ask_clarification`, one question at a time (never batch):

| Question | Why |
|---|---|
| Who is the target user? | Personas, priorities |
| What core problem does the product solve? | Keeps scope in check |
| What is the product vision? | North star for all decisions |
| What does success look like in numbers? | Measurable metrics, not feelings |
| What is the timeline? | MVP vs V2 scoping |
| What platforms? | Web, mobile, desktop |

---

## Phase 2: Problem, Personas, Vision, Metrics

**Gate: Context must be defined.**

### Output

```
## Problem Statement
{one paragraph - the problem, who has it, and the cost of not solving it}

## Personas
| Persona | Description | Goals | Pain Points |
|---|---|---|---|
| {persona} | {description} | {goals} | {pain points} |

## Product Vision
{elevator pitch: For {target user} who {need}, {product} is a {category}
that {key benefit}. Unlike {alternatives}, it {differentiator}.}

## Success Metrics
| Metric | Current | Target | Timeframe | Measurement |
|---|---|---|---|---|
| Weekly active users | 0 | 1,000 | 3 months | Analytics |
| Activation rate | n/a | 40% | 3 months | Funnel events |
| Retention D30 | n/a | 25% | 6 months | Cohort analysis |
```

Every metric must be measurable - no vague goals.

---

## Phase 3: Scope

**Gate: Vision and metrics defined.**

### Output

```
## Scope
### In Scope (MVP)
- {feature} - {why}
### Out of Scope (for now)
- {feature} - {why} (V2 / later)
### Open Questions
- {decision needed}
```

Explicitly state WHY each item is in or out.

---

## Phase 4: Prioritized Features

**Gate: Scope defined.**

### Feature Format

```
### Feature: {Feature Name}

**Story**: As a {persona}, I want {goal}, so that {reason}

**Acceptance Criteria** (all testable):
1. [ ] {criterion - measurable, not vague}
2. [ ] {criterion}

**Priority**: Must-have / Should-have / Could-have / Won't have
**Effort**: S / M / L
**Dependencies**: {services, teams, data}
```

### Prioritization Table

| Epic | Feature | Priority (MoSCoW) | Effort | Dependencies |
|---|---|---|---|---|
| Onboarding | Sign up with email | Must-have | S | Auth service |
| Core | Expense tracking | Must-have | M | - |
| Growth | Share reports | Should-have | M | Export service |

### Diagram

Include a mermaid diagram (```mermaid ... ``` code block) for the core user journey or product flow.

---

## Phase 5: UX, Dependencies, Risks

**Gate: Core features defined.**

### Output

```
## UX Considerations
- {navigation, accessibility, states, key screens}

## External Dependencies
| Dependency | What for | Owner | Status |
|---|---|---|---|
| Payment provider | Billing | External | Needs contract |

## Risks and Open Questions
| Risk / Question | Impact | Mitigation / Owner |
|---|---|---|
```

---

## Phase 6: Release Criteria and Roadmap

**Gate: Full feature set defined.**

### Output

```
## Release Criteria (Definition of Done for launch)
- [ ] {criterion - testable, e.g. "checkout flow completes in < 5 seconds"}
- [ ] {criterion}

## Roadmap
| Phase | Scope | Target |
|---|---|---|
| MVP | {in-scope features} | {date} |
| V2 | {out-of-scope promoted} | {date} |
| Later | {ideas} | - |
```

### Review Checklist

- [ ] Every feature has a testable acceptance criterion (no vague words)
- [ ] Success metrics have numeric targets and measurement methods
- [ ] Scope explicitly in/out with reasons
- [ ] Priorities assigned (not everything is Must-have)
- [ ] Core user journey has a mermaid diagram
- [ ] Release criteria are testable
- [ ] Dependencies and open questions identified
- [ ] Handoff to SRS is possible: stories and ACs are engineering-ready

### Final Document

```
# PRD: {Product Name}

## 1. Problem Statement
## 2. Personas
## 3. Product Vision
## 4. Success Metrics
## 5. Scope
## 6. Prioritized Features
## 7. UX Considerations
## 8. Dependencies and Risks
## 9. Release Criteria and Roadmap
```
