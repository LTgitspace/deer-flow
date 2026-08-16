---
name: startup-sketch
description: "Lean startup sketching: turn an idea into a mermaid sketch, a product description, a business description, and a plain HTML/CSS landing page. Use when the user wants to visualize or sketch a startup idea, a product concept, an MVP pitch, or a landing page for a new venture. Standalone lean flow — NOT the BRD/PRD/SRS requirements pipeline."
---

# Startup Sketch Skill

## Purpose

Take a raw idea and shape it into a **lean, visual, implementable startup sketch** in five stages: idea core, mermaid sketch, product description, business description, and a single-file HTML/CSS landing page. This is the fast path for early-stage concepts — deliberately lean. For formal engineering work, use the requirements pipeline skills instead.

## Core Principles

1. **Product before business.** Define what is being built (product description) before who pays for it (business description). The user's idea is the source of truth.
2. **Sketch before prose.** The mermaid diagram comes before any written description — visualize the concept first, then describe it.
3. **Lean, not exhaustive.** One-pagers, not documents. Every stage fits on a screen.
4. **Plain HTML only.** The landing page is a single self-contained HTML file with inline CSS — no frameworks, no build tools, no external JavaScript.
5. **One question at a time.** Clarify the idea via `ask_clarification`, never batch questions, never invent answers.

---

## Phase 0: Idea Core (Gate: nothing else starts before this)

Ask the user (via `ask_clarification`, ONE question at a time):

1. What problem does it solve?
2. Who has this problem (the target customer)?
3. What do they do today instead (current alternatives)?
4. What is the one-sentence product vision?

Do not proceed until the user's answers cover at least: the problem, the customer, and the vision.

---

## Phase 1: Sketch (Gate: idea core answered)

Visualize the idea with **mermaid** before writing any description:

1. **Concept map** — `graph TD` showing the core entities and their relationships.
2. **User flow** — `graph TD` or `flowchart LR` showing the user's journey: arrive -> sign up -> core action -> value.

Both diagrams must be mermaid code blocks (```mermaid). No ASCII art.

---

## Phase 2: Product Description (Gate: sketch exists)

A one-pager answering **what** is being built:

```
## Product Description
- **Vision**: {one sentence}
- **Core features** (3-5, prioritized)
- **MVP scope**: {what ships first}
- **Explicitly out of scope**: {what does NOT ship}
```

---

## Phase 3: Business Description (Gate: product description exists)

A one-pager answering **why it works as a business**:

```
## Business Description
- **Problem**: {the pain, in the customer's words}
- **Solution**: {how the product removes it}
- **Value proposition**: {why customers choose this}
- **Customer**: {who pays}
- **Revenue model**: {how money is made}
```

---

## Phase 4: Landing Page (Gate: business description exists)

A **single self-contained HTML file** with inline CSS. Rules:

- One `<html>` document: `<style>` block inside, no external stylesheets
- No frameworks (React, Next, Tailwind, Bootstrap, Vite) — pure HTML/CSS
- No external JavaScript, no CDN scripts
- Sections: hero (headline + subline + CTA), problem, product features, how it works, footer
- Responsive basics: mobile-friendly with simple flex/grid or max-width layout

Present the result via `present_file`.

---

## Output

Final deliverables in order:
1. Mermaid sketch (concept map + user flow)
2. Product description
3. Business description
4. Landing page (single HTML file)
