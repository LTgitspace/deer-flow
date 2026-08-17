# 🦌 UniDeer 2.0 — System Architecture & Agent Context Guide

> **Target Audience**: AI Coding Agents (Claude Code, Codex, Cursor, Antigravity, Aider, etc.)  
> **Repository Root**: `deer-flow/`  
> **Core Architectural Philosophy**: *"Skills teach, middlewares enforce."*

---

## 1. Executive Overview

**UniDeer 2.0** is an open-source, full-stack **AI Super-Agent Harness** orchestrated on top of **LangGraph**. It transforms stochastic LLM generations into deterministic, state-machine-governed execution pipelines. 

The harness governs **multi-agent delegation**, **process-isolated sandboxing**, **AST-level command & code safety**, **cryptographic file modification locks**, **long-term memory**, **pluggable MCP servers**, and **multi-channel IM bots**.

---

## 2. System Topology & Network Architecture

A standard deployment runs four cooperating services orchestrated via Nginx:

```
                               ┌─────────────────────────────────────────┐
                               │           Nginx Proxy (:2026)           │
                               │      (Single Public Loopback Entry)     │
                               └────────────┬───────────────┬────────────┘
                                            │               │
                         Frontend Traffic   │               │  /api/* & SSE
                                            ▼               ▼
                                 ┌────────────────────┐   ┌───────────────────────────┐
                                 │ Frontend (Next.js) │   │ Gateway API (FastAPI)     │
                                 │ Port: 3000         │   │ Port: 8001                │
                                 └────────────────────┘   └─────────────┬─────────────┘
                                                                        │
                                             ┌──────────────────────────┼──────────────────────────┐
                                             ▼                          ▼                          ▼
                                    ┌─────────────────┐        ┌─────────────────┐        ┌─────────────────┐
                                    │ Lead & Subagents│        │ Sandbox Engine  │        │ IM Channel Bots │
                                    │(deerflow-harness│        │ (Local/K8s/E2B) │        │ (Feishu, Slack, │
                                    │     Package)    │        │                 │        │  Telegram, etc.)│
                                    └─────────────────┘        └─────────────────┘        └─────────────────┘
```

| Service | Internal Port | External Route | Role |
| :--- | :--- | :--- | :--- |
| **Nginx** | `2026` | `http://127.0.0.1:2026` | Unified reverse-proxy entry point. Proxies `/api/langgraph/*` to Gateway REST routes. |
| **Gateway API** | `8001` | *Internal only* | FastAPI REST API + embedded LangGraph runtime + WebSocket streams + Background scheduler. |
| **Frontend** | `3000` | *Internal only* | Next.js 16 (App Router) + React 19 + Tailwind CSS 4 web interface. |
| **Provisioner** | `8002` | *Internal only* | *(Optional)* Remote Kubernetes / container provisioner for sandboxes. |

---

## 3. Monorepo Structure & Dependency Firewalls

```
deer-flow/
├── Makefile                        # Root orchestration (dev, start, stop, check, setup)
├── config.example.yaml             # Master configuration template -> config.yaml
├── extensions_config.example.json  # MCP servers & skills template -> extensions_config.json
├── backend/                        # Python 3.12+ backend
│   ├── Makefile                    # Backend commands (dev, test, lint, format, migrate-rev)
│   ├── packages/harness/           # Framework package: `deerflow-harness` (import: deerflow.*)
│   │   └── deerflow/
│   │       ├── agents/             # Lead agent, middlewares, memory, thread state
│   │       ├── authz/              # RBAC & Layer 1/2 authorization providers
│   │       ├── community/          # Third-party tools (search, scrapers, sandboxes)
│   │       ├── config/             # Pydantic configuration schemas & reload boundaries
│   │       ├── mcp/                # MCP protocol client, routing, and tool filters
│   │       ├── models/             # Model factory (thinking, vision, reasoning effort)
│   │       ├── runtime/            # RunManager, runs worker, StreamBridge
│   │       ├── sandbox/            # Sandbox abstraction, tools (bash, read, write)
│   │       ├── skills/             # Skill loading, SkillScan AST engine, review CLI
│   │       ├── subagents/          # Subagent executor, status contracts, registry
│   │       └── tools/              # Built-in tools (task, ask_clarification, present_files)
│   ├── app/                        # Host application (import: app.*)
│   │   ├── gateway/                # FastAPI routers (threads, runs, models, auth, mcp)
│   │   ├── channels/               # IM Platform bridges (Feishu, Slack, Discord, Telegram)
│   │   └── scheduler/              # Cron scheduled-task execution service
│   └── tests/                      # Unit, E2E, and blocking-io regression test suite
├── frontend/                       # Next.js 16 frontend (import: @/*)
│   ├── src/app/                    # App Router pages (/workspace/chats, /login, /docs)
│   ├── src/components/             # UI components, workspace panels, message cards
│   ├── src/core/                   # Business logic (threads, API client, streaming, tasks)
│   └── tests/                      # Unit (Rstest) and E2E (Playwright) test suites
├── skills/                         # Agent skill packages
│   ├── public/                     # Committed public skills (deep-research, system-design, etc.)
│   └── custom/                     # Local/custom skills (gitignored)
└── contracts/                      # Versioned JSON contracts (run_events, subagents, review)
```

### 🔒 The Harness / App Import Firewall
* **Rule**: `app.*` may import `deerflow.*`, but `packages/harness/deerflow/` **MUST NEVER** import `app.*`.
* **Enforcement**: Hard-fail CI test at `backend/tests/test_harness_boundary.py`.

---

## 4. The 35-Stage Middleware Pipeline

The lead agent graph (`deerflow.agents.lead_agent.agent:make_lead_agent`) is assembled across a strict sequence of interceptors:

```
[ Incoming User Turn / API Request ]
                  │
                  ▼
 1. InputSanitizationMiddleware        -> Neutralizes malicious system tags in raw input
 2. ToolOutputBudgetMiddleware         -> Clamps large tool outputs to prevent context overflow
 3. ToolResultSanitizationMiddleware   -> Sanitizes remote fetched HTML/web results
 4. ThreadDataMiddleware               -> Mounts thread isolation scopes (/mnt/user-data/)
 5. UploadsMiddleware                  -> Injects uploaded file metadata into conversation
 6. SandboxMiddleware                  -> Acquires sandbox container / local context
 7. DanglingToolCallMiddleware         -> Patches unfulfilled AIMessage tool_calls (interrupt recovery)
 8. LLMErrorHandlingMiddleware         -> Normalizes upstream provider errors into recoverable turns
 9. Authorization / GuardrailMiddleware-> Layer 1 & 2 RBAC tool execution filters
10. SandboxAuditMiddleware             -> AST bash command position vs value position inspection
11. ReadBeforeWriteMiddleware          -> Enforces cryptographic SHA hash-stamp before file writes
12. ToolProgressMiddleware             -> State machine detecting tool stagnation (ACTIVE->WARNED->BLOCKED)
13. ToolErrorHandlingMiddleware        -> Wraps tool exceptions into structured ToolMessages
                  │
                  ▼
[ Dynamic Context & Cognitive Enforcements ]
14. DynamicContextMiddleware           -> Injects current timestamp & date into <system-reminder>
15. SkillActivationMiddleware          -> Detects `/skill-name` syntax and binds skill instructions
16. SkillToolPolicyMiddleware          -> Token-bound policy restricting tool execution to `allowed-tools`
17. MetacognitionMiddleware            -> Forces reasoning/thinking on complex inputs
18. PlannerMiddleware                  -> Enforces "No plan, no edits" rule on multi-step mutations
19. EmojiGateMiddleware                -> Unicode scanner stripping emojis from code & config writes
20. PushbackMiddleware                 -> Detects polarity contradictions against recorded commitments
21. RequirementsPipelineMiddleware     -> Enforces lifecycle order (BRD -> PRD -> SRS -> SAD)
22. Domain Skill Middlewares           -> DeepResearch, SystemDesign, ProductRequirements gates
23. DurableContextMiddleware           -> Preserves delegation ledgers & skill refs across compaction
24. ProjectStateMiddleware             -> Persists pipeline deliverables to project store
25. SkillEvolutionMiddleware           -> Reviewer-first writes for skill modifications
26. SummarizationMiddleware            -> Context compactor triggered on high token watermarks
27. TodoListMiddleware                 -> Plan mode task tracker (`write_todos`)
28. TokenUsageMiddleware / Forensics   -> Per-turn token usage calculation and breakdown
29. TitleMiddleware                    -> Auto-generates conversation title after Turn 1
30. MemoryMiddleware                   -> Async extraction queue for semantic recall
31. ViewImageMiddleware / VisionBridge -> Injects base64 vision payloads or routes to fallback model
32. McpRoutingMiddleware / Deferred   -> Hides unpromoted MCP tools until `tool_search` matches
33. SystemMessageCoalescingMiddleware  -> Combines multiple SystemMessages for strict backends
34. SubagentLimitMiddleware            -> Clamps concurrent (`max_concurrent`) and total delegations
35. LoopDetectionMiddleware            -> Hard-stops repetitive identical tool-calling loops
36. TerminalResponseMiddleware         -> Retries empty assistant responses; prevents silent failures
37. Safety / ModelLengthFinishReason   -> Handles provider content filter and max token limits
38. ClarificationMiddleware (MUST BE LAST) -> Intercepts `ask_clarification`, issues `Command(goto=END)`
                  │
                  ▼
[ LLM Generation / Model Provider ]
```

---

## 5. Critical Invariants & Rules for Coding Agents

### Rule 1: Never Break the Read-Before-Write Lock
* Every file modification tool (`write_file`, `str_replace`) requires a preceding `read_file` call in the active context.
* `read_file` stamps a cryptographic SHA hash onto message metadata. If the on-disk file hash does not match the mark, the write is **deterministically blocked**.

### Rule 2: Guard the Async Event Loop (`blocking-io-guard`)
* **Zero Synchronous I/O on Event Loop**: Synchronous disk access, SQLite commits, network requests, or subprocess calls (`subprocess.run`, `open()`, `shutil`) inside async handlers must be offloaded via `await asyncio.to_thread(...)`.
* **Validation**: Run `make test-blocking-io` and `make detect-blocking-io` before committing backend changes.

### Rule 3: Database Concurrency via Partial Unique Indexes
* Never use in-memory Python flags to govern concurrency. Rely on database-level constraints:
  * `uq_scheduled_task_run_active`: Enforces at most 1 active run per scheduled task.
  * `uq_runs_thread_active`: Prevents concurrent active runs within a single thread.
  * `uq_channel_connection_active_identity`: Guarantees single-active-owner transfer for external IM identities.

### Rule 4: Sandbox Paths & Thread Isolation
* User workspaces are always mounted under `/mnt/user-data/` with three subdirectories:
  * `/mnt/user-data/workspace/`: Main project workspace and source files.
  * `/mnt/user-data/uploads/`: Staged user file uploads.
  * `/mnt/user-data/outputs/`: Final generated deliverables and artifacts.
* Stdio and local paths referencing files inside the user directory must translate to `/mnt/user-data/...`.

### Rule 5: Subagent Concurrency & Delegation Ledgers
* The `task` tool launches subagents (`general_purpose`, `bash_agent`, or custom agents).
* `SubagentLimitMiddleware` clamps concurrency to `max_concurrent_subagents` (default 3) and total delegations per run to `max_total_subagents` (default 6, max 50).
* Subagent lifecycle states (`task_started`, `task_running`, `task_complete`, `task_failed`) emit structured telemetry captured into `ThreadState.delegations`.

---

## 6. Frontend Interaction & Streaming Protocols

### Core Frontend Stack
* **Framework**: Next.js 16 (App Router), React 19, TypeScript 5.8, Tailwind CSS 4, pnpm 10.26+.
* **State Management**: TanStack Query v5 + LangGraph SDK streaming client.
* **Rendering**: Streamdown streaming markdown engine with syntax highlighting and Mermaid diagram support.

### Composer Commands vs. Skills
* `/goal <condition>`: Built-in composer command setting thread-level completion criteria (`AgentThreadState.goal`).
* `/compact`: Built-in composer command triggering manual context summarization without losing visible chat history.
* `/skill-name <query>`: Explicit skill invocation chip; loads `SKILL.md` into hidden turn context and activates `SkillToolPolicyMiddleware`.

### Human Input & Clarification Cards
* `ClarificationMiddleware` intercepts `ask_clarification` and yields structured payloads to `ToolMessage.artifact.human_input`.
* **Protocol Modes**:
  * `version: 1`: Legacy `free_text` and `choice_with_other`.
  * `version: 2`: Structured `form` (typed fields: text, textarea, number, select, multi-select, checkbox, date).
* Replies submit as hidden `HumanMessage`s with `additional_kwargs.human_input_response`, enabling headless replay without UI pollution.

---

## 7. Standard Developer & CI Commands

### Root Orchestration
```bash
make setup              # Run interactive setup wizard (config.yaml + .env)
make dev                # Start full stack (Gateway + Frontend + Nginx) with hot-reload
make doctor             # Validate configuration, dependencies, and environment
make support-bundle     # Generate redacted diagnostic bundle and triage report
make detect-blocking-io # Static AST scan for event loop blocking operations
```

### Backend (`backend/`)
```bash
cd backend
make dev                # Run FastAPI Gateway with reload (Port 8001)
make test               # Run backend offline unit tests
make test-blocking-io   # Strict Blockbuster runtime gate
make lint               # Lint with ruff
make format             # Format with ruff
make migrate-rev MSG="" # Autogenerate Alembic database migration
```

### Frontend (`frontend/`)
```bash
cd frontend
pnpm dev                # Start Next.js Turbopack dev server (Port 3000)
pnpm check              # Run ESLint + TypeScript typecheck (Mandatory before commit)
pnpm test               # Run unit tests (Rstest)
pnpm test:e2e           # Run Playwright E2E integration tests
pnpm perf:check         # Verify route asset bundle budgets
```

---

## 8. Summary Checklist for Modifying Code

Before submitting PRs or finalizing code modifications:
1. [ ] **Harness Boundary**: Ensure `packages/harness/deerflow/` does NOT import from `app.*`.
2. [ ] **Async Health**: Ensure all file/DB/network I/O on async execution paths uses `asyncio.to_thread`.
3. [ ] **Doc Sync Policy**: If modifying features, update `README.md`; if modifying architecture/middlewares, update `AGENTS.md` and `backend/AGENTS.md`.
4. [ ] **Lint & Format**: Run `ruff check` / `ruff format` on Python code and `pnpm check` on TypeScript code.
5. [ ] **Tests**: Include regression unit tests under `backend/tests/` or `frontend/tests/`.
