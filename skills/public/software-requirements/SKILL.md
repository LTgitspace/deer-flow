---
name: software-requirements
description: Elicit, structure, and validate software requirements with clear acceptance criteria. Use when the user asks for "requirements", "specification", "user stories", "acceptance criteria", or "functional spec". Produces user stories, functional specs, data dictionaries, and traceability matrices. For product-level docs (vision, personas, metrics, roadmap) use the product-requirements skill instead.
---

# Software Requirements Skill

## Purpose

Transform a vague idea into a complete, testable software requirements specification. The output must be unambiguous enough that a development team can estimate, build, and test against it without needing to ask the user clarifying questions.

---

## Phase 1: Context Discovery

**Gate: Must complete before writing any requirements.**

### What to Establish

Ask the user with `ask_clarification` if not already provided:

| Question | Why |
|---|---|
| Who is the target user? | Defines persona, priorities |
| What problem does this solve? | Keeps scope in check |
| Is this new or replacing existing? | Migration vs greenfield |
| Who are the stakeholders? | Different stakeholders = different priorities |
| What is the business goal? | Revenue, retention, compliance, efficiency |
| What is the timeline? | MVP vs V2 scoping |
| What platforms? | Web, mobile, desktop, API |
| Any existing systems to integrate with? | Integration requirements |

### Output

```
## Context

### Problem Statement
{one paragraph explaining the problem}

### Target Users
| Persona | Description | Goals | Pain Points |
|---|---|---|---|
| {persona} | {description} | {goals} | {pain points} |

### Stakeholders
| Stakeholder | Interest | Success Metric |
|---|---|---|
| {stakeholder} | {what they care about} | {how they measure success} |
```

---

## Phase 2: User Stories & Acceptance Criteria

**Gate: Context must be defined.**

### Story Format

```
As a {persona}
I want {goal}
So that {reason}

Acceptance Criteria (all must be testable):
1. [ ] {criterion — verifiable, not vague}
2. [ ] {criterion}
3. [ ] {criterion}

Example: 
  As a customer
  I want to reset my password via email
  So that I can regain access without contacting support

  AC:
  1. [ ] Click "Forgot password" opens email input
  2. [ ] Submitting valid email shows "Check your inbox" message
  3. [ ] Email arrives within 60 seconds
  4. [ ] Link expires after 15 minutes
  5. [ ] Clicking expired link shows "Link expired — request a new one"
```

### Story Categorization

| Epic | Story | Priority (MoSCoW) | Effort (S/M/L) | Dependencies |
|---|---|---|---|---|
| Authentication | Password reset | Must-have | S | Email service |
| Authentication | OAuth sign-in | Should-have | M | Auth0 setup |
| Notifications | Push notifications | Could-have | L | Firebase setup |

### Non-Functional Requirements

```
| Category | Requirement | Measurement | Priority |
|---|---|---|---|
| Performance | Page load < 2s | Lighthouse | Must-have |
| Availability | 99.9% uptime | Uptime monitor | Must-have |
| Security | Passwords hashed with bcrypt | Code review | Must-have |
| Accessibility | WCAG 2.1 AA | Axe scan | Should-have |
| Browser support | Chrome, Firefox, Safari, Edge | Last 2 major versions | Should-have |
| Mobile | Responsive layout down to 320px | Viewport tests | Should-have |
```

---

## Phase 3: Functional Specification

**Gate: User stories approved.**

### For Each Feature

```
### Feature: {Feature Name}

**Story link**: {reference to story ID}

**Description**: {what the feature does, in one paragraph}

**Flow:
1. User lands on {page}
2. User {action}
3. System {reaction}
4. User sees {result}

**Diagram**: include a mermaid flowchart or state diagram (```mermaid ... ``` code block) for every non-trivial flow.

**Edge cases**:
- {edge case}: {expected behavior}
- {edge case}: {expected behavior}

**Validation rules**:
| Field | Rule | Error Message |
|---|---|---|
| email | Must be valid format | "Enter a valid email" |
| password | Min 8 chars, 1 uppercase | "Password must be 8+ characters with 1 uppercase letter" |

**State transitions**:
- **Empty state**: {what user sees with no data}
- **Loading state**: {skeleton/spinner}
- **Error state**: {error message and retry}
- **Success state**: {confirmation}
- **Edge case**: {empty results / rate limited / offline}
```

---

## Phase 4: Data Dictionary

**Gate: Functional spec for at least core features.**

```
### Core Entities

**{Entity Name}**
| Field | Type | Required | Default | Constraints | Notes |
|---|---|---|---|---|---|
| id | UUID | Yes | Auto | PK | |
| email | string | Yes | — | Unique, max 255 chars | LCase before store |
| status | enum | Yes | active | active / inactive / suspended | |
| created_at | timestamp | Yes | now() | — | |

### Enumerations
| Enum | Values | Where Used |
|---|---|---|
| OrderStatus | pending / confirmed / shipped / delivered / cancelled | Order.status |
| UserRole | admin / editor / viewer | User.role |
```

---

## Phase 5: Validation & Traceability

**Gate: Full requirements draft complete.**

### Review Checklist

- [ ] Every functional requirement has an acceptance criterion that proves it
- [ ] Every acceptance criterion is testable (not "fast" but "< 2 seconds")
- [ ] Non-functional requirements have concrete targets (not "reliable" but "99.9%")
- [ ] Non-trivial flows have a mermaid flowchart or state diagram
- [ ] No requirement contradicts another
- [ ] All roles/permissions are defined
- [ ] All error states are documented (not just the happy path)
- [ ] External dependencies are identified
- [ ] Data retention and privacy requirements are addressed

### Traceability Matrix

| Requirement ID | Type | Source | Test Case | Status |
|---|---|---|---|---|
| REQ-001 | Functional | User story AUTH-01 | TC-001 | Draft |
| REQ-002 | Non-functional | Stakeholder interview | TC-002 | Draft |
```

---

## Phase 6: Deliver

### Final Document

```
# Software Requirements Specification: {Project Name}

## 1. Context
{Phase 1}

## 2. User Stories
{Phase 2}

## 3. Functional Specification
{Phase 3}

## 4. Data Dictionary
{Phase 4}

## 5. Traceability
{Phase 5}
```

### Bare Minimum

| Phase | Minimum deliverable |
|---|---|
| Context | Problem statement + target user persona |
| Stories | 3 core user stories with acceptance criteria |
| Non-functional | 3 key NFRs with measurable targets |
| Data | 2 core entities with fields |
| Validation | Happy path + 2 error states per feature |

### Quality Gates

- [ ] Every requirement is testable — no vague words ("fast", "easy", "reliable")
- [ ] Every feature has a defined error state — not just the happy path
- [ ] Edge cases are documented separately from the main flow
- [ ] Priorities are explicitly assigned (not everything is P0)
- [ ] External dependencies are identified
