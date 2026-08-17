# UniDeer - 2.0

English | [中文](./README_zh.md) | [日本語](./README_ja.md) | [Français](./README_fr.md) | [Русский](./README_ru.md)

[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](./backend/pyproject.toml)
[![Node.js](https://img.shields.io/badge/Node.js-22%2B-339933?logo=node.js&logoColor=white)](./Makefile)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

UniDeer (**D**eep **E**xploration and **E**fficient **R**esearch **Flow**) is an open-source **super agent harness** built on top of **LangGraph**. It orchestrates **sub-agents**, **long-term memory**, and **sandboxed execution** to handle complex, multi-step tasks — powered by **extensible skills**.

UniDeer is a **community fork of [DeerFlow](https://github.com/bytedance/deer-flow), created by [ByteDance](https://www.bytedance.com/)** (v2.0+), and has evolved into a distinct project with its own engineering direction. It shares the deep-research lineage and much of the original architecture; the codebase, the middleware pipeline, and the runtime behavior have been reworked. See [How UniDeer differs from DeerFlow](#how-unideer-differs-from-deerflow) and [Acknowledgments](#acknowledgments).

> **Note on lineage:** DeerFlow 2.0 was a ground-up rewrite that shared no code with v1. UniDeer builds on that 2.0 foundation and continues from there. The original v1 deep-research framework remains maintained upstream on the [1.x branch](https://github.com/bytedance/deer-flow/tree/main-1.x).

---

## Table of Contents

- [Why UniDeer](#why-unideer)
  - [The problem with chatbot-plus-tools](#the-problem-with-chatbot-plus-tools)
  - [Design principles](#design-principles)
- [Acknowledgments](#acknowledgments)
- [How UniDeer differs from DeerFlow](#how-unideer-differs-from-deerflow)
- [Architecture Overview](#architecture-overview)
  - [Service topology](#service-topology)
  - [The harness / app dependency firewall](#the-harness--app-dependency-firewall)
  - [A typical request, end to end](#a-typical-request-end-to-end)
- [Core Features](#core-features)
  - [Skills & Tools](#skills--tools)
  - [The Middleware Pipeline](#the-middleware-pipeline)
  - [Sub-Agents](#sub-agents)
  - [Sandbox & File System](#sandbox--file-system)
  - [Context Engineering](#context-engineering)
  - [Long-Term Memory](#long-term-memory)
  - [MCP & Model Factory](#mcp--model-factory)
  - [Tool Catalog](#tool-catalog)
- [Runtime & Reliability](#runtime--reliability)
  - [Run ownership, leases, and recovery](#run-ownership-leases-and-recovery)
  - [Checkpointing](#checkpointing)
  - [Database-level concurrency invariants](#database-level-concurrency-invariants)
- [Quick Start](#quick-start)
  - [Prerequisites](#prerequisites)
  - [Configuration](#configuration)
  - [Running the Application](#running-the-application)
  - [Startup modes](#startup-modes)
- [Advanced](#advanced)
  - [Sandbox Providers](#sandbox-providers)
  - [IM Channels](#im-channels)
  - [Authorization & RBAC](#authorization--rbac)
  - [Tracing & Observability](#tracing--observability)
  - [Scheduled Tasks](#scheduled-tasks)
  - [Provisioner (Kubernetes)](#provisioner-kubernetes)
- [Embedded Python Client](#embedded-python-client)
- [Terminal Workbench (TUI)](#terminal-workbench-tui)
- [Deployment](#deployment)
  - [Local development](#local-development)
  - [Docker](#docker)
  - [Kubernetes](#kubernetes)
- [Security](#security)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [License](#license)

---

## Why UniDeer

Most "AI agent" tools are chat interfaces with a search tool bolted on. UniDeer is a **harness**: a structured runtime that turns a stochastic LLM into a deterministic, state-machine-governed execution pipeline.

A single request flows through:

1. **Lead agent** — plans the turn, decides whether to delegate, and synthesizes the final answer
2. **Middleware chain** — a pipeline of 35+ composable interceptors that enforce skills, budgets, safety, and tool policy before and after each model call
3. **Sub-agents** — parallel, isolated workers for tasks that benefit from real concurrency, specialist capability, or context isolation
4. **Sandbox** — an isolated filesystem per thread (skills, workspace, uploads, outputs), with pluggable execution isolation
5. **Memory** — persistent cross-session facts and user summaries, injected into the prompt when relevant
6. **Streaming** — SSE events that render live in the web UI, the TUI, or IM channels

The guiding philosophy is a single sentence: **skills teach, middlewares enforce.** Capabilities are declared in `SKILL.md` files; invariants — read-before-write, token budgets, tool policies, loop detection, safety terminations — are enforced in code, deterministically, regardless of what the model decides to do.

### The problem with chatbot-plus-tools

A plain chat wrapper around an LLM with tools has three structural weaknesses that UniDeer is designed to fix:

- **No enforcement.** A model can ignore instructions. A prompt that says "always search before answering" is a suggestion; a middleware that counts searches and injects a correction is a guarantee.
- **No isolation.** Every tool call runs in the same context as the chat, so a long research task pollutes the conversation and a sub-task cannot safely run in parallel.
- **No state discipline.** Without checkpoints, compaction, and cross-session memory, a multi-turn task loses coherence and a multi-hour task blows the context window.

UniDeer addresses all three with a state-machine runtime, an enforcement pipeline, and a sandboxed filesystem.

### Design principles

- **Deterministic over stochastic.** Prompt nudges steer; middlewares enforce. Gates, counters, and policies are derived from message history and thread state, not from model whims.
- **Progressive loading.** Skills are loaded only when needed, keeping the context window lean. Tools are discovered via `tool_search` and promoted only when relevant.
- **Isolation by default.** Sub-agents cannot see the parent's history; sandbox paths are per-thread; memory is per-user and per-agent; runs are owned and leased.
- **Fail closed.** Conflicting state updates raise, tool authorization filters before execution, and checkpoint invariants are enforced at the database layer with partial unique indexes.
- **Operable.** Run leases, orphan recovery, request trace correlation, and pluggable tracing (Langfuse, LangSmith, Monocle) are first-class, not afterthoughts.

## How UniDeer differs from DeerFlow

UniDeer keeps the super-agent-harness vision but diverges in engineering and product direction. The differences that matter today:

| Area | DeerFlow (upstream) | UniDeer (this project) |
| --- | --- | --- |
| **Repository** | `bytedance/deer-flow` | Independent fork with its own roadmap and release cadence |
| **Middleware pipeline** | Broad keyword-triggered skill gates that inject activation nudges on shaped-but-inactive conversations | **Inactive-skill fast exits**: skill gates (deep-research, system-design, startup-sketch, and similar) fire only when the skill is explicitly slash-activated or loaded into `skill_context`. Casual queries pass through untouched — no prompt pollution, lower time-to-first-token |
| **Post-answer correction** | Metacognition and similar gates can trigger a second full LLM generation to "fix" an answer | **Advisory corrections**: post-answer nudges land on the next natural turn instead of forcing an immediate re-generation, eliminating the second-LLM-roundtrip latency spike |
| **Sub-agent observability** | Collapsed sub-agent cards show status only | **Live runtime metadata**: collapsed cards show the effective model name and cumulative token usage, updated after each sub-agent LLM call and durable across reloads |
| **Session persistence** | Session cookie only | **"Keep me logged in"** policy: unified session-cookie lifecycle, `remember_me` handling, and Secure/Max-Age strategy per deployment (HTTPS, loopback, public HTTP) |
| **Memory backends** | DeerMem default | DeerMem default **plus an OpenViking HTTP backend** for remote, cross-instance memory recall |
| **Authorization** | Disabled by default | **Pluggable authorization + built-in RBAC** provider with per-role tool/route allow-deny policies |
| **Trace correlation** | Basic | X-Trace-ID propagation plus Langfuse/LangSmith/Monocle tracing with `metadata.deerflow_trace_id` correlation |
| **Codebase** | — | The harness package (`backend/packages/harness/deerflow/`) is maintained here, with its own tests, invariants (harness/app import firewall), and docs |

The shared DNA remains: skills, sub-agents, sandboxes, memory, MCP, and the IM-channel bridges. UniDeer's focus is on **predictable latency** (no wasted tokens, no surprise re-generations) and **operational depth** (ownership, leases, database-level concurrency, observability).

## Architecture Overview

### Service topology

A standard deployment runs four cooperating services, orchestrated from a single command or a Docker Compose stack:

| Service | Port | Role |
| --- | --- | --- |
| **Nginx** | `2026` | Unified reverse-proxy entry point. Routes `/api/langgraph/*` to the Gateway's embedded LangGraph runtime and proxies everything else to the Frontend. |
| **Gateway API** | `8001` | FastAPI REST API plus the embedded LangGraph runtime (`RunManager`, `run_agent()`, `StreamBridge`). There is no standalone LangGraph service — the runtime lives inside the Gateway process. |
| **Frontend** | `3000` | Next.js 16 web interface (React 19, TypeScript, Tailwind CSS 4, pnpm). |
| **Provisioner** | `8002` | Optional — only started when the sandbox is configured for provisioner/Kubernetes mode. Manages sandbox pod/VM lifecycle. |

```
                    Browser / IM Client (Feishu, Slack, Telegram, WeChat, WeCom, DingTalk, GitHub, Discord)
                                       |
                                       v
                            Nginx (port 2026)
                     /api/langgraph/*          /, /workspace/*, /blog/*
                     |                        |
                     v                        v
            Gateway API (FastAPI :8001)   Frontend (Next.js :3000)
            + embedded LangGraph runtime
                     |
        +------------+------------+-----------+
        |            |            |           |
        v            v            v           v
   Sandbox      IM Channels  Provisioner   Persistence
   (E2B/Aio/    (8 bridges)   (:8002, K8s)  (SQLAlchemy +
    Local)                                  Alembic)
```

### The harness / app dependency firewall

The backend is split into two layers with a hard, CI-enforced dependency rule:

- `app.*` (the FastAPI host: gateway routers, channel bridges, scheduler) **may** import `deerflow.*`
- `packages/harness/deerflow/` (the harness package, importable as `deerflow.*`) **must never** import `app.*`

This is enforced by `backend/tests/test_harness_boundary.py`, which runs in CI. The harness stays publishable, app-agnostic, and testable in isolation. A second invariant is enforced by `make test-blocking-io`: zero synchronous file/DB/network I/O on the async event loop — blocking work must be offloaded via `asyncio.to_thread`.

### A typical request, end to end

1. The user types a message in the Frontend composer (optionally voice-transcribed or AI-polished).
2. `POST /api/threads/{id}/runs/stream` opens an SSE streaming request.
3. The Gateway validates auth (Better Auth cookie sessions, CSRF, RBAC), resolves the agent configuration, and creates a LangGraph run.
4. `RunManager.run_agent()` loads `ThreadState` from the checkpointer, resolves the model, and builds the middleware chain.
5. The lead-agent node executes: memory middleware injects user context, skill activation loads `SKILL.md` if slash-activated, the system prompt is assembled (goal, skills, tools, memory), and the model is called with tool definitions.
6. If the model calls tools, they are routed to built-in / sandbox / community / MCP handlers, results are sanitized, and loop detection runs.
7. If the `task` tool is called, the sub-agent executor spawns parallel sub-agents with isolated contexts and scoped toolsets; each reports a structured `TaskResult`; the lead synthesizes.
8. After the run: memory extraction saves new facts, a title is generated (first turn), workspace changes are computed, the goal is evaluated, and suggestions are produced.
9. `StreamBridge` converts internal events into SSE events (`values`, `messages-tuple`, `custom`, `tasks`) that the Frontend renders live: animated markdown, sub-agent cards with step timelines and token usage, workspace-change diffs, todos, goal status, and follow-up suggestions.

## Core Features

### Skills & Tools

Skills are structured capability modules — a `SKILL.md` file defining a workflow, best practices, and references to supporting resources. UniDeer ships with 30+ built-in skills and lets you add your own, replace built-ins, or combine them into compound workflows.

**How skills work:**

1. Each skill lives in its own directory under `skills/public/` (committed) or `skills/custom/` (gitignored).
2. The `SKILL.md` file is the entry point — instructions the agent follows when the skill is active.
3. Skills load **progressively** — only when the task needs them, keeping the context window lean.
4. Skills can declare `allowed-tools` to restrict which tools the agent may use while active (best-effort behavioral scoping).
5. **Slash activation**: `/skill-name` at the start of a request activates the skill for that turn.
6. **SkillScan**: a deterministic safety scanner runs on installed skills, flagging high-confidence issues (private keys, shell execution patterns).

**Activation gating.** Domain-specific skill gates (deep-research, system-design, startup-sketch, and similar) fire only when their skill is explicitly active in the thread — slash-activated via `/skill-name` or captured in `skill_context` after a `read_file` load. A conversational query that merely contains skill-shaped words (for example "why...", "explain...", or "design...") passes through untouched: no hidden activation nudges are injected, so casual turns do not pollute the prompt or slow down time-to-first-token.

**Built-in skills include:**

- Research and analysis: `deep-research`, `github-deep-research`, `data-analysis`, `academic-paper-review`, `systematic-literature-review`, `consulting-analysis`
- Content generation: `report-generation`, `ppt-generation`, `image-generation`, `video-generation`, `music-generation`, `podcast-generation`, `newsletter-generation`
- Engineering: `frontend-design`, `web-design-guidelines`, `chart-visualization`, `code-documentation`, `system-design`, `bootstrap`
- Product and requirements: `business-requirement`, `product-requirements`, `software-requirements`, `startup-sketch`
- Meta: `skill-creator`, `skill-reviewer`, `find-skills`, `surprise-me`, `vercel-deploy-claimable`, `claude-to-deerflow`

An enabled skill's `allowed-tools` policy applies only after that skill is explicitly activated. Merely enabling, advertising, or listing a skill does not reduce the agent's normal toolset. Once active, the policy filters both model-visible tool schemas and tool execution. This is best-effort behavioral scoping, not a hard security boundary.

### The Middleware Pipeline

The lead agent graph (`make_lead_agent`) assembles a pipeline of 35+ middleware stages (60+ modules in the source tree) that wrap every model call and tool execution. This is the main extensibility point of the harness.

Selected stages, in rough order:

| Middleware | Purpose |
| --- | --- |
| `InputSanitization` | Neutralizes malicious system tags in raw input |
| `ToolOutputBudget` | Clamps large tool outputs to prevent context overflow |
| `ToolResultSanitization` | Sanitizes remote fetched HTML/web results |
| `ThreadData` / `Uploads` | Mounts thread isolation scopes and injects uploaded-file metadata |
| `Sandbox` | Acquires the sandbox container or local context |
| `DanglingToolCall` | Patches unfulfilled tool calls after interrupt recovery |
| `LLMErrorHandling` | Normalizes provider errors into recoverable turns |
| `SandboxAudit` | AST-inspects bash commands for unsafe patterns |
| `ReadBeforeWrite` | Enforces the cryptographic SHA hash-stamp gate before file writes |
| `ToolProgress` | State machine detecting tool stagnation (ACTIVE to WARNED to BLOCKED) |
| `SkillActivation` / `SkillToolPolicy` | Binds `SKILL.md` context and enforces `allowed-tools` |
| `Metacognition` | Think-first enforcement for complex prompts (pre-answer; advisory post-answer) |
| `Planner` | "No plan, no edits" rule for multi-step mutations |
| `EmojiGate` | Unicode scanner keeping generated code/config emoji-free |
| `Summarization` / `TokenBudget` | Context compaction on high token watermarks |
| `TodoList` / `Title` | Plan-mode task tracking and auto-titles after turn one |
| `Memory` | Injects long-term memory before runs, extracts new facts after |
| `LoopDetection` | Hard-stops repetitive identical tool-calling loops |
| `TerminalResponse` | Retries empty assistant responses; prevents silent failures |
| `Safety / ModelLengthFinishReason` | Handles provider content filters and max-token limits |
| `Clarification` (last) | Intercepts `ask_clarification` and issues `Command(goto=END)` |

The same chain (minus lead-agent-specific stages) is applied to sub-agents, so a delegated task is governed by the same invariants as the parent.

### Sub-Agents

Sub-agents are an optimization, not the default response to a complex request.

The lead agent spawns sub-agents on the fly — each with its own scoped context, tools, and termination conditions — when delegation has clear net benefit from real parallel latency, specialist capability, or context isolation. It keeps interdependent scopes and overlapping side effects out of parallel dispatch. Sub-agents report back structured results; the lead verifies and synthesizes them.

**Execution model.** The sub-agent executor is a thread-pool + asyncio hybrid: contextvars are propagated correctly from the parent, each sub-agent runs its own isolated event loop, and lifecycle state follows a strict state machine: `PENDING` to `RUNNING` to `COMPLETED` / `FAILED` / `CANCELLED` / `TIMED_OUT`. Guardrail caps (`token_capped`, `turn_capped`, `loop_capped`) end a run early while preserving partial output, and the lead can distinguish "finished" from "capped".

**Concurrency limits.** `SubagentLimitMiddleware` clamps concurrent delegations (default 3, configurable 1-4) and total delegations per run (default 6, maximum 50).

**Structured contracts.** Sub-agent results ride in `ToolMessage.additional_kwargs` as a pinned contract: status, stop reason, error, a SHA-256 digest of the full result, effective model name, and cumulative token usage. The enum values are shared between Python and TypeScript via `contracts/subagent_status_contract.json`, and a contract test pins them against each other so the frontend and backend can never drift.

**Live runtime metadata.** Collapsed sub-agent cards show the effective model and, when the provider returns usage metadata, a cumulative token total that updates after each completed sub-agent LLM call and persists across reloads. Concurrent sub-agents keep independent totals keyed by `task_id`. Providers that omit usage show an explicit unavailable state, never a fabricated zero.

Independent read-only research can run concurrently when wall-clock savings outweigh duplicated discovery cost. A repository refactor with shared files and sequential test feedback stays with the lead agent. When `max_concurrent_subagents` is 1, parallel and multi-batch routing guidance is disabled; delegation remains available only for material specialist or context-isolation benefit.

### Sandbox & File System

Each task gets its own execution environment with a full filesystem view — skills, workspace, uploads, outputs.

```
/mnt/user-data/
├── uploads/          # your files
├── workspace/        # agents' working directory
└── outputs/          # final deliverables
```

**Providers:**

| Provider | Description |
| --- | --- |
| `E2BSandboxProvider` | Remote E2B sandbox with VM isolation, warm pool, bursting, and Redis-backed ownership for multi-worker deployments |
| `AioSandboxProvider` | Container-based isolation (Docker) |
| `LocalSandboxProvider` | Host filesystem with per-thread directories; host bash disabled by default |

**Key features:**

- Per-thread directory isolation with path security policies and environment-variable policies
- File-operation locking to serialize concurrent reads/writes on the same path
- **Read-before-write enforcement**: `read_file` stamps a SHA-256 hash of the file's current content onto the message; `write_file` / `str_replace` on an existing file is deterministically blocked unless the on-disk hash matches the stamp. Any write invalidates earlier reads, forcing a re-read between consecutive modifications.
- **Workspace change tracking**: after each run, a diff summary of changed files in `workspace` and `outputs` is recorded and shown as a "files changed" badge with text diffs in the UI. Uploads are excluded (they are user inputs).
- Image handling: base64 images are removed from checkpoints after vision-model consumption to avoid payload duplication.
- Search across sandbox files with the built-in `grep` tool.

### Context Engineering

- **Isolated sub-agent context** — sub-agents cannot see the parent's or siblings' history
- **Summarization** — completed sub-tasks are compacted, intermediate results offloaded to the filesystem, and context compressed to stay within token limits
- **Strict tool-call recovery** — dangling tool calls are patched with placeholder results before the next model invocation, keeping strict reasoning models from failing on malformed history
- **Visible tool-run completion** — an empty post-tool final response is retried once, then surfaced as a visible error instead of a silent success
- **Manual compaction** — `/compact` in the composer summarizes older context while keeping the full chat visible
- **Session goals** — `/goal <condition>` attaches a thread-scoped completion condition; the runtime evaluates the conversation against it after each run and injects hidden continuations (safety-capped at 8) until it is satisfied or cleared

### Long-Term Memory

Persistent, cross-session memory of user profile, preferences, and accumulated knowledge.

**Storage architecture:**

```
{deerflow_home}/memory/
├── users/{user_id}/
│   ├── memory.json              # user profile + history summaries (JSON)
│   └── agents/{agent_name}/
│       └── facts/
│           ├── ab/cdef123...md  # individual fact (Markdown, sharded by SHA-256)
│           └── ...
```

- Facts are canonical Markdown files, sharded by the first two hex characters of `SHA-256(fact_id)`
- Journaled writes prevent silent lost updates; a shared user lock and optimistic revisions protect concurrent access
- Retrieval uses a scoped SQLite FTS5/BM25 adapter by default, with a local substring fallback; the derived index is rebuildable and corrupt indexes are recreated automatically
- Legacy `memory.json` facts auto-migrate on first read

**Backends:**

- **DeerMem** (default) — file-backed, scope-aware, with an extraction write gate that classifies every proposed fact by scope, durability, and authority before storage. Only durable, descriptive user-level facts are stored; current-thread constraints and one-time permissions stay in conversation state.
- **OpenViking** (optional) — connects to an independent OpenViking server over HTTP for remote, cross-instance recall. Bounded submission watermarks and jittered retries prevent duplicate commits on retry.

Memory injection is mode-configurable (`middleware` vs `tool`), and `memory.injection_enabled: false` disables the block entirely.

### MCP & Model Factory

UniDeer supports the **Model Context Protocol** for connecting external tool servers over stdio or HTTP, with tool schema caching, MCP routing middleware, and tool annotations for MCP-sourced tools.

The model factory is provider-agnostic:

- OpenAI and OpenAI-compatible APIs (`langchain_openai:ChatOpenAI`)
- vLLM (self-hosted, with thinking/reasoning support via `chat_template_kwargs.enable_thinking`)
- OpenAI Codex CLI (`gpt-5.4` class) and Anthropic Claude (OAuth or API key)
- Huawei MindIE, plus patched providers (DeepSeek, MiniMax, StepFun, MiMo) for reasoning

Thinking/reasoning support (`supports_thinking`, `supports_reasoning_effort`), vision models, and the Responses API (`output_version: responses/v1`) are all first-class. Credentials load from environment variables via the credential loader.

### Tool Catalog

**Built-in tools** — `task` (spawn a sub-agent), `tool_search` (discover tools by description), `ask_clarification` (pause for user input), `view_image`, `present_file`, `list_uploaded_files`, `review_skill_package`, `setup_agent` / `update_agent`, `invoke_acp_agent`.

**Community tools** — `web_search`, `web_fetch`, `web_capture`, `image_search` (provider-configurable).

**Sandbox tools** — `bash`, `ls`, `read_file` (with line ranges), `write_file`, `str_replace`.

**Browser tools** (optional extra) — `browser_navigate`, `browser_snapshot`, `browser_click`, `browser_type`, `browser_get_text`, `browser_back`, `browser_screenshot`, `browser_close`. Powered by Playwright with SSRF screening; disabled by default.

**Authorization.** With `authorization.enabled`, a pluggable `AuthorizationProvider` filters denied tools before they reach the model or the deferred-tool catalog, and again before every business-tool execution. The built-in RBAC provider supports per-role `tools` and `routes` allow/deny policies.

## Runtime & Reliability

### Run ownership, leases, and recovery

Every run is owned. The run manager assigns a unique worker id (`hostname:hex_uuid`), stamps each run with a lease, and persists ownership in the runs table. If a Gateway restarts or a worker becomes unreachable before a run reaches a durable final state, the run is recovered as an orphan with a clear stop reason:

- `"Gateway restarted before this run reached a durable final state."`
- `"Run lease expired - owning worker is unreachable."`

Lease-expiry detection, startup orphan recovery, and multi-worker run ownership are supported across both SQLite (local) and Postgres (deployed). Transient SQLite lock contention on status finalization is retried with bounded backoff, and driver-native unique-constraint signals (Postgres `23505`, SQLite constraint codes) are detected without relying on locale-dependent error text.

### Checkpointing

Thread state is checkpointed after every step so runs can resume or branch. The runtime ships compatibility patches for upstream LangGraph checkpoint machinery (for example, a fix for `InMemorySaver` dropping writes on full-to-delta migrated threads), pinned to the validated LangGraph version and automatically standing down if upstream fixes the issue. Checkpoint channel modes and snapshot frequencies are configurable per deployment.

### Database-level concurrency invariants

Concurrency is governed by the database, not by in-memory flags. Partial unique indexes enforce the load-bearing invariants:

| Index | Invariant |
| --- | --- |
| `uq_runs_thread_active` | At most one pending/running run per thread (`WHERE status IN ('pending','running')`) |
| `uq_scheduled_task_run_active` | At most one active run per scheduled task (`WHERE status IN ('queued','running')`) |
| `uq_channel_connection_active_identity` | Single-active-owner transfer for external IM identities (`WHERE status != 'revoked'`) |

Migrations include deduplication pre-steps so the indexes can be built even on databases that already violate the invariant (field databases, pre-fix multi-worker deployments). The losing writer in a race surfaces as a typed conflict (for example, `ActiveScheduledRunConflict`), and scheduled dispatches that overlap an active run record a terminal `skipped` tombstone that never occupies the active slot.

## Quick Start

### Prerequisites

- Python 3.12+ and `uv`
- Node.js 22+ and pnpm 10
- `nginx` (required for `make dev` unified local endpoint)
- Docker (optional, for containerized deployment)

Run `make check` to verify the toolchain.

### Configuration

```bash
git clone https://github.com/bytedance/deer-flow.git
cd deer-flow
```

> The clone URL above points at the upstream repository. For UniDeer, clone from the fork URL you received instead.

1. Install dependencies: `make install` (backend first, then frontend, as implemented by the target)
2. Run the setup wizard:

```bash
make setup
```

The wizard guides you through choosing an LLM provider, optional web search, and execution/safety preferences such as sandbox mode, bash access, and file-write tools. It generates a minimal `config.yaml` and writes your keys to `.env`. Takes about 2 minutes.

Run `make doctor` at any time to verify your setup and get actionable fix hints. If you are opening a GitHub issue about a local setup or runtime problem, run `make support-bundle` — it writes a redacted issue summary, an AI-assisted issue draft, and an optional evidence zip under `.deer-flow/support-bundles/`.

**Configuration files:**

- `config.yaml` (gitignored) — the main application config: models, sandbox, tools, channels, scheduler, logging, tracing
- `extensions_config.json` (gitignored) — MCP servers and skill definitions
- `config.example.yaml` / `extensions_config.example.json` — templates to copy

Use `make config-upgrade` to merge new fields from `config.example.yaml` into an existing `config.yaml` without losing local settings.

**Models** are configured in `config.yaml` under `models:`. Each entry names a provider class, a model id, and credentials via environment variables:

```yaml
models:
  - name: gpt-4o
    display_name: GPT-4o
    use: langchain_openai:ChatOpenAI
    model: gpt-4o
    api_key: $OPENAI_API_KEY
  - name: qwen3-32b-vllm
    display_name: Qwen3 32B (vLLM)
    use: deerflow.models.vllm_provider:VllmChatModel
    model: Qwen/Qwen3-32B
    api_key: $VLLM_API_KEY
    base_url: http://localhost:8000/v1
    supports_thinking: true
```

**Environment variables** (paths and runtime state):

- `UNI_DEER_PROJECT_ROOT` — explicit project root
- `UNI_DEER_CONFIG_PATH` — point at a specific config file
- `UNI_DEER_HOME` — runtime state location (defaults to `.deer-flow` under the project root)
- `UNI_DEER_SKILLS_PATH` — skills directory (defaults to `skills/` under the project root)

### Running the Application

**Option 1: Docker (Recommended)**

```bash
make docker-start
```

Mode-aware startup from `config.yaml`, unified endpoint at `http://localhost:2026`. Other targets: `make docker-stop`, `make docker-logs`, `make docker-logs-gateway`, `make docker-logs-frontend`, `make docker-logs-redis`.

**Option 2: Local Development**

```bash
make dev
```

Starts three services with hot reload:

- Gateway API (FastAPI, port 8001, with the embedded LangGraph runtime)
- Frontend (Next.js, port 3000)
- Nginx (port 2026 — the unified entry point)

Stop everything with `make stop`. Logs land in `logs/gateway.log`, `logs/frontend.log`, and `logs/nginx.log`. On Windows, run the local flow from Git Bash (native `cmd.exe`/PowerShell are not supported for the bash-based service scripts).

**Backend development commands** (from `backend/`):

```bash
make dev                # FastAPI Gateway with reload (port 8001)
make test               # offline unit tests
make test-blocking-io   # strict blocking-IO runtime gate
make lint               # ruff check
make format             # ruff format
make migrate-rev MSG="" # autogenerate an Alembic migration
```

**Frontend development commands** (from `frontend/`):

```bash
pnpm dev                # Next.js Turbopack dev server (port 3000)
pnpm lint               # ESLint
pnpm typecheck          # TypeScript check
pnpm test               # unit tests
pnpm test:e2e           # Playwright E2E tests
```

### Startup modes

The `config.yaml` supports mode-aware startup:

| Mode | Description |
| --- | --- |
| `flash` | Fast responses, minimal reasoning |
| `standard` | Balanced speed and depth |
| `pro` | Planning mode with explicit reasoning |
| `ultra` | Full sub-agent orchestration |

## Advanced

### Sandbox Providers

**E2B** uses `wait` as its default overflow policy: it waits for `acquire_timeout`, then fails the agent turn (UniDeer does not retry automatically; clients can use the structured error to schedule a retry). `burst` with `burst_limit` permits bounded extra VMs; `reject` can remove one warm VM before returning an error. With Redis ownership, `replicas` is a deployment-wide hard limit shared across workers via one capacity hash; mismatched workers fail closed.

**Aio** runs shell execution inside isolated Docker containers, with thread-data mounts detected from its backend (local containers use mounted gateway directories; remote/provisioner sandboxes receive uploads through explicit synchronization).

**Local** maps file tools to per-thread directories on the host, but host `bash` is disabled by default because it is not a secure isolation boundary. Re-enable only for fully trusted local workflows. Host bash commands have a wall-clock timeout.

### IM Channels

UniDeer bridges into external messaging platforms: **Feishu, Slack, Telegram, Discord, DingTalk, WeChat, WeCom, and GitHub**. All channels share a common execution path through the Gateway run lifecycle:

- Each channel receives user messages, converts them to thread runs, and streams responses back
- Session management (assistant id, recursion limits, thinking mode) is configurable per channel
- A message bus, per-channel run policies, and connection identity linking unify the 8 bridges
- **Single-active-owner transfer**: an external identity is keyed by `(provider, external_account_id, workspace_id)`; the latest successful bind wins, enforced race-free by the `uq_channel_connection_active_identity` partial unique index
- Inbound-redelivery deduplication, file attachment staging into the sandbox, and artifact delivery (outputs only — other paths are rejected to prevent exfiltration)

### Authorization & RBAC

Advanced deployments can enable pluggable authorization with `authorization.enabled` in `config.yaml`. A configured `AuthorizationProvider` filters denied tools before they reach the model or deferred-tool catalog, then the same provider is checked again before every business-tool execution. Gateway `threads:*` and `runs:*` route permissions derive from the same provider, while existing owner checks and admin-only management gates remain in force. The built-in RBAC provider supports per-role `tools` and `routes` allow/deny policies and validates that `default_role` names a configured role. Disabled by default.

### Tracing & Observability

- **Request trace correlation**: every Gateway HTTP response includes `X-Trace-Id`; logs include `trace_id`
- **Langfuse**: traces include `metadata.deerflow_trace_id` matching `X-Trace-Id`; set `UNI_DEER_ENV` (or `ENVIRONMENT`) to tag traces by deployment environment
- **LangSmith and Monocle**: pluggable tracing providers
- Tracing callbacks attach at the graph invocation root so spans are not duplicated; the codebase documents this invariant explicitly

### Scheduled Tasks

Configure recurring agent runs from the web UI or the Gateway API. A background scheduler dispatches each task on its cron schedule, with:

- Database-enforced "at most one active run per task" semantics (`uq_scheduled_task_run_active`)
- A `skipped` tombstone when a dispatch overlaps an active run (never occupies the active slot)
- Manual triggers racing the poller collapse to the same outcome as the fast path (manual: 409 conflict; scheduled: `skipped`)

### Provisioner (Kubernetes)

The optional Provisioner service (port 8002) manages sandbox infrastructure for Kubernetes-based deployments: allocates sandbox pods/VMs on demand, maintains warm pools for fast acquisition, and handles the full lifecycle (create, health check, destroy). It is only started when the sandbox is configured for provisioner/K8s mode; local and Docker Compose deployments with E2B/Aio providers do not need it.

## Embedded Python Client

Interact with a UniDeer instance programmatically — no web UI required:

```python
from deerflow.client import DeerFlowClient

client = DeerFlowClient(base_url="http://localhost:8001")

# Stream a turn
for event in client.stream("thread-id", "your prompt"):
    print(event)

# Create a thread
thread = client.create_thread(agent="lead_agent")
```

The client supports thread creation, message streaming (same SSE modes as the UI), memory management, file uploads, and agent configuration. Run `make test-live` in `backend/` for live API tests.

## Terminal Workbench (TUI)

A terminal user interface for interacting with UniDeer without the web UI — new threads, streaming responses, goals, and skill commands from the CLI. Launch it with the `deerflow` CLI command; on a non-TTY it degrades to headless `--print` / `--json` output for scripting.

## Deployment

### Local development

```bash
make dev       # Gateway (8001) + Frontend (3000) + Nginx (2026)
make stop      # stop everything
```

### Docker

```bash
make docker-start   # mode-aware development stack from config.yaml (localhost:2026)
make up             # production compose (localhost:2026)
make down           # stop and remove production containers
```

### Kubernetes

A Helm chart lives at `deploy/helm/deer-flow/` for Kubernetes deployments, with the Provisioner managing sandbox infrastructure.

## Security

UniDeer gives agents real filesystem and execution power by design. Deployment must be treated as privileged infrastructure:

- **Improper deployment may introduce security risks.** The gateway admin is effectively equivalent to code execution on the host.
- The local sandbox disables host bash by default; re-enable only for fully trusted local workflows.
- Keep `headless: true` and `allow_private_addresses: false` for browser control outside trusted debugging. Attaching to an existing Chrome with `cdp_url` cannot enforce the SSRF guard and fails closed unless `allow_unguarded_cdp: true` explicitly acknowledges the risk.
- Treat `config.yaml` and `extensions_config.json` as trusted operator-controlled files: middleware, tool, model, sandbox, guardrail, and MCP declarations are code execution.
- Authentication uses HttpOnly cookies, CSRF protection, and pluggable RBAC; the "keep me logged in" policy downgrades to session cookies on public HTTP and only uses Secure + Max-Age on HTTPS or loopback.

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — service topology, all 8 layers, data flow, repository map, glossary
- [Context guide](context.md) — system architecture and agent context for coding agents
- [Plans and RFCs](docs/plans/) — authorization, tracing, memory, and more
- [Contributing](CONTRIBUTING.md) — development environment and workflow
- [Install](Install.md) — one-line agent setup instructions

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development environment setup, the required command order, and validation expectations. Before submitting changes:

- Backend: `cd backend && make lint && make test` (CI parity: `uv sync --group dev`, then lint, then test)
- Frontend (if touched): `cd frontend && pnpm lint && pnpm typecheck`; set `BETTER_AUTH_SECRET` for production builds
- Never break the harness/app import firewall (`tests/test_harness_boundary.py`)
- Keep the async event loop blocking-IO-free (`make test-blocking-io`)
- Update docs when changing features (`README.md`) or architecture/middlewares (`AGENTS.md`)

## Acknowledgments

UniDeer would not exist without the work of the teams and communities that came before it.

- **[ByteDance](https://www.bytedance.com/)** — creator of the original DeerFlow project and the deep-research framework that UniDeer is forked from. This project builds on their open-source foundation.
- **[DeerFlow](https://github.com/bytedance/deer-flow)** — the upstream open-source project (MIT licensed) that UniDeer is a community fork of. We are grateful for the architecture, the skills ecosystem, and the engineering that made this possible.
- **DeerFlow v1 maintainers and contributors** — the original Deep Research framework (maintained on the [1.x branch](https://github.com/bytedance/deer-flow/tree/main-1.x)) laid the groundwork that led to the 2.0 rewrite UniDeer builds on.
- **The DeerFlow community** — contributors, testers, and users who shaped the upstream project.

UniDeer's own differences, optimizations, and additions are documented in [How UniDeer differs from DeerFlow](#how-unideer-differs-from-deerflow).

## License

UniDeer is distributed under the **MIT License** — see [LICENSE](LICENSE). As a fork of DeerFlow (also MIT), the original copyright and attribution for the portions derived from the upstream project remain with ByteDance and the DeerFlow contributors.
