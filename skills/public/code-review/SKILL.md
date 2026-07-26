---
name: code-review
description: Review code changes with structured, human-aware analysis. Use when the user asks for "review this code", "code review", "review PR", "look at my code", "check this diff", or "is this code good". Covers logic correctness, security, style, architecture fit, and edge cases.
---

# Code Review Skill

## Purpose

Review code with a human-in-the-loop, asking questions continuously throughout the process. The AI owns **logic review** (correctness, architecture, edge cases, security). SonarQube owns **syntax conventions** (style, code smells, duplications, coverage). The user confirms findings at every stage.

## Core Principles

1. **Ask continuously** — never go more than one finding without confirming with the user
2. **Figure it out yourself** — if the user can't answer (language, framework, libs), inspect the code directly
3. **SonarQube = syntax, AI = logic** — never confuse the two. SonarQube reports are style-only.
4. **Scale strictness** — hobby project gets lenient review. Enterprise gets full strictness.

---

## Phase 0: Continuous Context Discovery

**Gate: Never fully complete. Keep asking as the review progresses.**

This is not a one-time phase. As you review the code, you discover new context you need. Ask for it.

### Initial Questions (ask 1-2 at a time, not all at once)

| Question | Why | If User Doesn't Know |
|---|---|---|
| What does this code do overall? | Scope the review | "I'll figure it out by reading the code" |
| What language? | Tooling, patterns, linting | Detect from file extensions |
| What framework? | Framework-specific best practices | Detect from imports and config files |
| Is this new code, a bug fix, or a refactor? | Review depth | Assume new code |
| Who maintains this? (you / small team / enterprise) | Strictness level | "I'll be moderate — not too strict, not too lenient" |
| What's the scale? (script / hobby / production) | Severity calibration | Assume hobby if <500 lines, production if >5000 |
| Any proprietary libs or internal dependencies? | Don't flag what's out of scope | Search for unknown import sources |
| Is there a CI/CD pipeline? Tests? Linting? | Don't suggest what already exists | "I'll check for test files and configs" |

### If the User Can't Answer

**Do not give up.** Inspect the code directly:

```
To find the language:    ls the project for file extensions
To find the framework:   read package.json, go.mod, Cargo.toml, requirements.txt, pom.xml
To find dependencies:    grep imports, check lockfiles
To find tests:           search for */test*, */spec*, */__test__*
To find CI/CD:           look for .github/workflows/, Jenkinsfile, .gitlab-ci.yml
```

### Output (update as you learn)

```
## Review Context (Updated Continuously)

- **Purpose**: {summary — updated as you understand more}
- **Type**: New code / Bug fix / Refactor
- **Language**: {detected or confirmed}
- **Framework**: {detected or confirmed}
- **Key Libs**: {list — detected from imports/dependencies}
- **Maintainer**: {hobby / small team / enterprise}
- **Scale**: {script / production / critical — estimated from code size and complexity}
- **Strictness**: {lenient / moderate / strict}
- **Tests found**: Yes / No — {path if found}
- **CI/CD found**: Yes / No — {path if found}
```

---

## Phase 1: Index the Codebase

**Goal**: Map the structure so every finding references real files, not guesses.

### What to Map

Walk the project directory tree with `bash ls -R` or individual `ls` calls. Then drill into files to extract:

```
### Directory Structure
{root}/
├── src/
│   ├── {module}/     ← {purpose: what this module does}
│   │   ├── {file}    ← {purpose}
│   │   └── {file}    ← {purpose}
│   └── {module}/     ← {purpose}
├── tests/            ← {test coverage}
├── config/           ← {configuration}
├── {package manager file}    ← {dependencies}
└── {CI/CD files}             ← {pipeline config}
```

### Function/Class Index

Parse the files in scope to extract:

```
### Key Functions & Classes

| Signature | File | Role |
|---|---|---|
| class {Name} | src/{path} | {what it represents} |
| def {name}(...) | src/{path} | {what it does} |
| function {name}(...) | src/{path} | {what it does} |

### Dependency Graph (simplified)
{Mention which modules depend on which — flag circular dependencies}
```

### Dependencies & Proprietary Libs

```
### External Dependencies
| Package | Version | Used For |
|---|---|---|
| {name} | {ver} | {purpose} |

### Proprietary / Internal Dependencies
| Import | Source | Public API? | Risk for Review |
|---|---|---|---|
| {import} | Internal | Yes / No | {can't review without source / need user context} |
```

---

## Phase 2: Static Analysis — SonarQube Integration

**Goal**: Get code convention, style, and smell data from SonarQube. These are SYNTAX issues — not logic.

### What SonarQube Provides (syntax only)

| Category | What It Checks | AI Role |
|---|---|---|
| Code smells | Duplicated code, overly complex methods | AI reads the report, confirms with user |
| Bugs (static) | Null pointer risks, resource leaks | AI reads the report, explains impact |
| Vulnerabilities | Hardcoded passwords, SQL injection patterns | AI reads the report, adds context |
| Coverage | Test coverage gaps | AI notes what's missing |
| Duplications | Copy-pasted code | AI suggests consolidation |
| Style violations | Naming, formatting, lint rules | AI filters: report only what the user cares about |

### How to Use the Report

```
1. Run `sonar-scanner` or fetch SonarQube project page via web_fetch
2. Filter: only NEW issues introduced by the changes (not pre-existing)
3. For each finding:
   - "SonarQube flagged {issue}. This is a syntax/style concern — not a logic bug."
   - Ask: "Is this something you want me to flag in the review, or skip?"
4. Do NOT mix SonarQube findings with AI logic findings
5. SonarQube findings go in "Static Analysis" section, AI findings in "Logic Review"
```

### SonarQube Section Template

```
## Static Analysis (SonarQube)

| Issue | File:Line | Rule | Severity | Review Decision |
|---|---|---|---|---|
| {description} | {file}:{line} | {rule key} | {blocker / critical / major / minor} | Report / Skip (user choice) |
```

---

## Phase 3: Logic Review — AI's Domain

**Gate: For each finding, confirm with user before moving to the next.**

SonarQube does not review logic. The AI reviews:

| Category | What the AI Checks |
|---|---|
| **Correctness** | Wrong operators, off-by-one, inverted conditions, race conditions, missing null checks, unhandled edge cases |
| **Architecture** | Layer violations, circular dependencies, God objects, wrong abstraction |
| **Security** | Auth bypass, injection, exposed secrets, missing CSRF, insecure defaults |
| **Performance** | N+1 queries, unnecessary allocations, blocking IO on async path |
| **Error handling** | Swallowed exceptions, missing retries, unclear error messages |
| **Testability** | Untestable code (hard dep on global state), missing test coverage for changed paths |

### Review Process (Per Finding)

```
Step 1 — Find: "I noticed {observation} in {file}:{line}. Here's the code: `{snippet}`"

Step 2 — Explain: "This could cause {impact} because {reason}."

Step 3 — Ask: "Is this intentional?"
  - If YES → skip it, move on
  - If NO → suggest a fix

Step 4 — Confirm fix: "Would {suggestion} solve it? Any constraints I'm missing?"

Step 5 — Repeat: Move to the next finding. Never batch questions.
```

### Confidence Levels

| Confidence | When | How to Present |
|---|---|---|
| **High** | Clear bug (wrong operator, missing null check, SQL injection) | "This is a bug: {explanation}" |
| **Medium** | Suspicious pattern but could be intentional | "I think this might be wrong. Is this intentional?" |
| **Low** | Style or preference, could go either way | "Optional: consider {alternative}. Your call." |

---

## Phase 4: Compile & Confirm Report

**Gate: All findings confirmed, user ready for final output.**

### Report Structure

```
# Code Review: {Title}

## Scope
- **Files reviewed**: {N}
- **Language**: {detected}
- **Framework**: {detected}
- **Scale**: {hobby / team / enterprise}
- **Strictness**: {lenient / moderate / strict}

---

## Quick Summary
{One paragraph: readiness, safety, biggest concern}

---

## Static Analysis (SonarQube) — Syntax Only
| # | File | Issue | Severity | Action |
|---|---|---|---|---|
| 1 | {path}:{line} | {issue} | {severity} | {fix / skip} |

---

## Logic Review (AI) — Correctness & Architecture

### Critical
| # | File | Finding | Fix |
|---|---|---|---|

### Major
| # | File | Finding | Fix |
|---|---|---|---|

### Minor
| # | File | Finding | Fix |
|---|---|---|---|

---

## What Went Well
- {positive}

---

## Verdict
{merge as-is / minor changes recommended / blocked}
```

---

## Bare Minimum

| What | Minimum |
|---|---|
| Context | Purpose, language, framework — detected or confirmed |
| Index | Directory tree + key files list |
| Review | Top 3 findings, each confirmed with user |
| Report | Verdict + top findings |

## Quality Gates

- [ ] Every finding was confirmed with the user before the final report
- [ ] Language, framework, and key libs were detected or confirmed
- [ ] SonarQube findings are separated from logic findings in the report
- [ ] Proprietary/internal dependencies are noted
- [ ] Verdict is clear and actionable
