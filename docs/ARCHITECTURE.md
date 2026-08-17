# UniDeer Architecture

> **UniDeer** (Deep Exploration and Efficient Research Flow) is an open-source
> **super agent harness** that orchestrates sub-agents, memory, and sandboxes to
> do almost anything — powered by extensible skills.

---

## Table of Contents

- [High-Level Overview](#high-level-overview)
- [Service Topology](#service-topology)
- [Layer 1: Frontend (Next.js)](#layer-1-frontend-nextjs)
- [Layer 2: Nginx Reverse Proxy](#layer-2-nginx-reverse-proxy)
- [Layer 3: Gateway API (FastAPI)](#layer-3-gateway-api-fastapi)
- [Layer 4: Agent Harness (LangGraph)](#layer-4-agent-harness-langgraph)
  - [Lead Agent](#lead-agent)
  - [Middleware Chain](#middleware-chain)
  - [Sub-Agent System](#sub-agent-system)
  - [Memory System](#memory-system)
  - [Skills System](#skills-system)
  - [Tools System](#tools-system)
  - [Sandbox & File System](#sandbox--file-system)
  - [MCP Integration](#mcp-integration)
  - [Model Factory](#model-factory)
- [Layer 5: Persistence](#layer-5-persistence)
- [Layer 6: IM Channels](#layer-6-im-channels)
- [Layer 7: Provisioner](#layer-7-provisioner)
- [Layer 8: Deployment & Orchestration](#layer-8-deployment--orchestration)
- [Data Flow: A Typical Request](#data-flow-a-typical-request)
- [Repository Map](#repository-map)
- [Key Concepts Glossary](#key-concepts-glossary)

---

## High-Level Overview

UniDeer is a full-stack AI agent platform. It takes a user query, plans a
multi-step execution strategy, spawns parallel sub-agents to do the work,
manages a sandboxed filesystem for intermediate artifacts, remembers past
interactions across sessions, and returns a synthesized result.

The stack spans four cooperating services orchestrated from a single `make dev`
command or a Docker Compose deployment.

```
                    ┌──────────────────────────────────────┐
                    │           Browser / IM Client         │
                    └──────────────┬───────────────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────────────┐
                    │         Nginx (port 2026)             │
                    │     Unified Reverse Proxy             │
                    └──────┬─────────────────────┬─────────┘
                           │                     │
              /api/*       │                     │  /, /workspace/*, /blog/*
                           ▼                     ▼
              ┌──────────────────┐   ┌──────────────────────┐
              │  Gateway API     │   │  Frontend (Next.js)   │
              │  FastAPI :8001   │   │  :3000                │
              │  + LangGraph RT  │   └──────────────────────┘
              └────┬───┬────┬────┘
                   │   │    │
          ┌────────┘   │    └──────────┐
          ▼            ▼               ▼
   ┌──────────┐ ┌──────────┐   ┌──────────────┐
   │Sandbox   │ │ IM Ch.   │   │ Provisioner  │
   │Provider  │ │(Feishu,  │   │  (optional)  │
   │(E2B/Loc.)│ │Slack,etc)│   │   :8002      │
   └──────────┘ └──────────┘   └──────────────┘
```

---

## Service Topology

A single `make dev` starts four cooperating services:

| Service           | Port   | Role                                                        |
| ----------------- | ------ | ----------------------------------------------------------- |
| **Nginx**         | `2026` | Unified reverse-proxy entry point — open this in a browser  |
| **Gateway API**   | `8001` | FastAPI REST API + embedded LangGraph-compatible runtime    |
| **Frontend**      | `3000` | Next.js 16 web interface (React 19, TypeScript)             |
| **Provisioner**   | `8002` | Optional — only when sandbox is configured for K8s mode     |

Nginx routes `/api/langgraph/*` → Gateway's LangGraph runtime, rewrites it to
Gateway's native `/api/*` routes, and proxies everything else to the Frontend.

---

## Layer 1: Frontend (Next.js)

**Stack**: Next.js 16, React 19, TypeScript 5.8, Tailwind CSS 4, pnpm

### Directory Layout

```
frontend/src/
├── app/                    # Next.js App Router (pages & API handlers)
│   ├── (auth)/             # Login, setup, OAuth callback
│   ├── workspace/          # Main chat workspace
│   │   ├── chats/[id]/     # Thread conversation view
│   │   └── agents/         # Custom agent management
│   ├── blog/               # Blog pages (MDX)
│   └── api/                # Next.js API route handlers
├── components/
│   ├── ui/                 # Shadcn UI primitives (auto-generated)
│   ├── ai-elements/        # Vercel AI SDK elements
│   ├── workspace/          # Chat page components
│   ├── landing/            # Landing page sections
│   └── docs/               # MDX rendering components
├── core/                   # Business logic (heart of the app)
│   ├── threads/            # Thread creation, streaming, state management
│   ├── api/                # LangGraph client singleton
│   ├── agents/             # Custom agent CRUD & configuration
│   ├── auth/               # Authentication (Better Auth integration)
│   ├── memory/             # Long-term memory management UI
│   ├── skills/             # Skill catalog & management
│   ├── messages/           # Message normalization & rendering
│   ├── streamdown/         # Streaming Markdown rendering (incremental animation)
│   ├── tasks/              # Sub-task history, steps, token tracking
│   ├── input-polish/       # Pre-send draft rewrite API
│   ├── voice-input/        # Browser speech-recognition helpers
│   ├── workspace-changes/  # Run-scoped file change summaries & diffs
│   ├── suggestions/        # AI-generated follow-up suggestions
│   ├── tools/              # Tool metadata display
│   ├── models/             # Model configuration
│   ├── mcp/                # MCP server management
│   ├── channels/           # IM channel connection management
│   ├── scheduled-tasks/    # Scheduled task management
│   ├── i18n/               # Internationalization (en-US, zh-CN)
│   └── utils/              # Shared utilities
├── hooks/                  # Shared React hooks
├── lib/                    # Utilities (cn(), etc.)
├── content/                # MDX content (blog posts, docs)
├── styles/                 # Global CSS (Tailwind v4)
└── typings/                # Ambient TypeScript declarations
```

### Data Flow

1. User types in the **composer** (with optional voice transcription or AI polish)
2. `useSubmitThread` hook sends the message via the **LangGraph SDK** client
3. Server-Sent Events (SSE) stream back: `values`, `messages-tuple`, `custom`, `tasks`
4. `useThreadStream` processes events → updates thread state (messages, artifacts,
   todos, goal, run duration, workspace changes)
5. **TanStack Query** manages server state; components subscribe and re-render
6. Long conversation history is paginated via `useThreadHistory` with cursor-based
   navigation

### Key Patterns

- Server Components by default; `"use client"` only for interactive widgets
- Thread routes are percent-encoded via `pathOfThread()` in `core/threads/utils.ts`
- Streaming Markdown uses `streamdown` for incremental word animation
- Composer drafts survive page reloads via `sessionStorage`
- `/goal` and `/compact` are built-in composer commands, not skills

---

## Layer 2: Nginx Reverse Proxy

Nginx is the single public entry point at **port 2026**. It:

- Serves the **Frontend** static assets and pages (`/`, `/workspace/*`, `/blog/*`)
- Proxies `/api/langgraph/*` → Gateway's embedded LangGraph runtime
- Rewrites `/api/langgraph/*` to Gateway's native `/api/*` routes
- Proxies all other `/api/*` → Gateway REST routers directly

Configuration lives at `docker/nginx/`. No standalone LangGraph service exists;
the LangGraph runtime is embedded inside the Gateway process.

---

## Layer 3: Gateway API (FastAPI)

The Gateway is the central orchestrator: a FastAPI application at **port 8001**
that serves both REST endpoints and hosts the embedded LangGraph agent runtime.

### Directory Layout

```
backend/app/gateway/
├── app.py                  # FastAPI application factory
├── config.py               # Gateway configuration
├── deps.py                 # Dependency injection (get_db, get_current_user, etc.)
├── auth.py                 # Authentication & authorization logic
├── auth_middleware.py      # Request-level auth middleware
├── auth_disabled.py        # Auth bypass for local development
├── authz.py                # RBAC authorization provider
├── csrf_middleware.py      # CSRF protection
├── trace_middleware.py     # Request trace correlation (X-Request-ID)
├── checkpoint_lineage.py   # Checkpoint parent/child chain tracking
├── browser_capability.py   # Browser control capability detection
├── run_models.py           # Run request/response models
├── pagination.py           # Cursor-based pagination helpers
├── services.py             # Shared service layer
├── routers/
│   ├── agents.py           # Custom agent CRUD
│   ├── auth.py             # Login, logout, session
│   ├── threads.py          # Thread CRUD, goal, compaction
│   ├── thread_runs.py      # Run execution & streaming
│   ├── runs.py             # Run history & events
│   ├── models.py           # Model listing & configuration
│   ├── skills.py           # Skill install, catalog, reload
│   ├── mcp.py              # MCP server management
│   ├── memory.py           # Long-term memory API
│   ├── uploads.py          # File upload management
│   ├── artifacts.py        # Generated artifact management
│   ├── features.py         # Feature flag listing
│   ├── suggestions.py      # Follow-up suggestion generation
│   ├── input_polish.py     # Pre-send draft rewrite
│   ├── feedback.py         # User feedback collection
│   ├── channels.py         # IM channel configuration
│   ├── channel_connections.py  # Channel identity linking
│   ├── browser.py          # Browser session management
│   ├── scheduled_tasks.py  # Scheduled task CRUD
│   ├── assistants_compat.py # OpenAI Assistants API compatibility
│   ├── github_webhooks.py  # GitHub webhook receiver
│   └── console.py          # Admin console endpoints
└── github/                 # GitHub integration helpers
```

### Key Responsibilities

- **REST API**: Full CRUD for threads, runs, agents, skills, MCP servers, memory,
  scheduled tasks, channels
- **LangGraph Runtime**: The Gateway process embeds `RunManager` + `run_agent()` +
  `StreamBridge` from `backend/packages/harness/deerflow/runtime/`
- **Authentication**: Better Auth integration with cookie-based sessions, CSRF
  protection, RBAC authorization
- **Streaming**: SSE-based agent run streaming with `values`, `messages-tuple`,
  `custom`, and `tasks` modes
- **Request Tracing**: X-Request-ID header propagation, LangSmith/Langfuse/Monocle
  tracing integration

---

## Layer 4: Agent Harness (LangGraph)

This is the core intelligence layer, implemented in the `deerflow-harness` Python
package (`backend/packages/harness/deerflow/`). It is importable as `deerflow.*`.

### Lead Agent

**Path**: `backend/packages/harness/deerflow/agents/lead_agent/`

The lead agent is a LangGraph `StateGraph` built by `make_lead_agent()` (entry
point declared in `backend/langgraph.json`). It:

- Constructs the **system prompt** from user context, memory, skills metadata,
  active goal, and tool descriptions
- Builds the **middleware chain** around the core LLM node
- Supports **modes**: flash (fast), standard, pro (planning), ultra (sub-agents)
- Handles **human-in-the-loop** pauses for clarifications or approvals
- Manages **ThreadState** — the per-conversation state schema that flows through
  the graph

The agent factory (`factory.py`) wires together all configuration: model, tools,
sandbox, sub-agents, memory, and middlewares.

### Middleware Chain

**Path**: `backend/packages/harness/deerflow/agents/middlewares/`

Middlewares wrap the core LLM invocation in a pipeline. They execute before and/or
after each model call and tool execution. This is a critical extensibility point.

| Middleware                       | Purpose                                                        |
| -------------------------------- | -------------------------------------------------------------- |
| `memory_middleware`              | Injects long-term memory context; extracts new memories after runs |
| `skill_activation_middleware`    | Loads skill SKILL.md when slash-activated or read               |
| `skill_tool_policy_middleware`   | Enforces skill-level `allowed-tools` restrictions               |
| `summarization_middleware`       | Compacts older context when token budget is exceeded            |
| `token_budget_middleware`        | Monitors and enforces token limits                              |
| `tool_output_budget_middleware`  | Truncates tool outputs that exceed per-output token limits       |
| `tool_progress_middleware`       | Emits tool execution progress events                            |
| `tool_error_handling_middleware` | Catches tool failures, injects structured error messages        |
| `tool_result_sanitization_middleware` | Sanitizes tool results for safety                           |
| `deferred_tool_filter_middleware`| Filters deferred tool catalog based on authorization/skills     |
| `dangling_tool_call_middleware`  | Cleans up incomplete tool calls on forced stops                 |
| `loop_detection_middleware`      | Detects infinite tool-call loops                                |
| `llm_error_handling_middleware`  | Handles provider-level errors, retries, fallback                |
| `safety_finish_reason_middleware`| Detects content-filter refusals and safety terminations         |
| `terminal_response_middleware`   | Ensures a final text response is always produced                |
| `clarification_middleware`       | Routes clarification requests to human-in-the-loop              |
| `subagent_limit_middleware`      | Enforces limits on concurrent sub-agent spawning                |
| `sandbox_audit_middleware`       | Audits sandbox operations for security                          |
| `tool_call_metadata`             | Attaches metadata (timing, usage) to tool calls                 |
| `token_usage_middleware`         | Tracks cumulative token usage across the run                    |
| `todo_middleware`                | Manages the structured todo list during task execution          |
| `title_middleware`               | Auto-generates conversation titles after the first turn         |
| `thread_data_middleware`         | Initializes thread-scoped data on first run                     |
| `uploads_middleware`             | Manages file upload lifecycle within the run                    |
| `view_image_middleware`          | Injects vision-model image content into context                 |
| `system_message_coalescing_middleware` | Merges consecutive system messages to reduce token waste  |
| `dynamic_context_middleware`     | Injects runtime-dynamic context (goals, skill metadata)          |
| `durable_context_middleware`     | Manages durable (checkpoint-surviving) context injection        |
| `mcp_routing_middleware`         | Routes MCP tool calls to the correct MCP server                 |
| `read_before_write_middleware`   | Ensures file reads happen before writes for safety              |
| `input_sanitization_middleware`  | Sanitizes user input before model processing                    |
| `configured_extensions`          | Loads user-configured `AgentMiddleware` extensions from config  |
| `delegation_ledger`              | Tracks sub-agent delegation metadata                            |

### Sub-Agent System

**Path**: `backend/packages/harness/deerflow/subagents/`

Complex tasks are decomposed. The lead agent can spawn sub-agents via the
built-in `task` tool. Each sub-agent:

- Runs in its **own isolated context** (cannot see the parent or siblings'
  chat history)
- Gets its own **scoped toolset** (subset of available tools)
- Inherits the parent's **sandbox** for file access
- Reports back **structured results** (`TaskResult`) with status, output, and
  token usage
- Runs in **parallel** when possible (fan-out pattern)

**Built-in sub-agents**:

| Sub-agent            | Purpose                                    |
| -------------------- | ------------------------------------------ |
| `general_purpose`    | Default task execution with full toolset   |
| `bash_agent`         | Specialized shell/script execution agent   |

**Key components**:

- `executor.py` — Background execution engine that manages sub-agent lifecycle
- `registry.py` — Sub-agent type registry for lookup and instantiation
- `status_contract.py` — Standardized sub-agent status reporting contract
- `step_events.py` — Per-step event emission for progress tracking
- `token_collector.py` — Cumulative token usage tracking across sub-agent LLM calls

### Memory System

**Path**: `backend/packages/harness/deerflow/agents/memory/`

UniDeer builds persistent, cross-session memory of user profile, preferences,
and accumulated knowledge.

**Components**:

- `manager.py` (`MemoryManager`) — Core CRUD for facts and user summaries
- `memory_middleware.py` — Injects memory context before runs; extracts new
  memories after runs
- `tools.py` — Memory management tools available to the agent
- `backends/` — Storage backends (file-based with Markdown per-fact files,
  user-level JSON summaries)

**Memory Architecture**:

```
{deerflow_home}/memory/
├── users/{user_id}/
│   ├── memory.json              # User profile + history summaries (JSON)
│   └── agents/{agent_name}/
│       └── facts/
│           ├── ab/cdef123...md  # Individual fact (Markdown, sharded by SHA-256)
│           └── ...
└── ...
```

- Facts are stored as canonical Markdown files, sharded by the first two hex
  characters of `SHA-256(fact_id)`
- User summaries (`user`, `history` sections) live in a single `memory.json`
- Legacy `memory.json` facts auto-migrate on first read
- Journaled writes prevent silent lost updates
- Optional retrieval adapter for semantic search (falls back to substring search)

### Skills System

**Path**: `backend/packages/harness/deerflow/skills/`

Skills are structured capability modules — a `SKILL.md` file that defines a
workflow, best practices, and references to supporting resources.

**How skills work**:

1. Each skill lives in its own directory under `skills/public/` (committed) or
   `skills/custom/` (gitignored)
2. The `SKILL.md` file is the entry point — it contains instructions the agent
   follows when the skill is active
3. Skills are **loaded progressively** — only when the task needs them, keeping
   the context window lean
4. Skills can declare `allowed-tools` to restrict which tools the agent can use
   while that skill is active (best-effort behavioral scoping)
5. **Slash activation**: `/skill-name` at the start of a request activates the
   skill for that turn
6. **SkillScan**: A deterministic safety scanner runs on installed skills, flagging
   high-confidence issues (private keys, shell execution patterns)

**Built-in skills** (27 total):

| Skill                          | Purpose                                         |
| ------------------------------ | ----------------------------------------------- |
| `deep-research`                | Multi-source research with synthesis            |
| `data-analysis`                | CSV/JSON analysis with charts                   |
| `report-generation`            | Structured report writing                       |
| `ppt-generation`               | Slide deck creation                             |
| `image-generation`             | AI image generation workflows                   |
| `video-generation`             | AI video generation workflows                   |
| `music-generation`             | Music composition                               |
| `podcast-generation`           | Podcast script and audio production             |
| `newsletter-generation`        | Email newsletter creation                       |
| `frontend-design`              | UI/UX design and frontend code                  |
| `web-design-guidelines`        | Web design principles reference                 |
| `chart-visualization`          | Data visualization and charting                 |
| `code-documentation`           | Codebase documentation generation               |
| `academic-paper-review`        | Academic paper analysis and review              |
| `systematic-literature-review` | Systematic literature review methodology        |
| `consulting-analysis`          | Business/management consulting analysis         |
| `github-deep-research`         | GitHub repository deep analysis                 |
| `skill-creator`                | Meta-skill for creating new skills              |
| `skill-reviewer`               | Read-only skill quality review                  |
| `bootstrap`                    | Project bootstrapping and scaffolding           |
| `claude-to-deerflow`           | Interact with UniDeer from Claude Code CLI     |
| `find-skills`                  | Skill search and discovery                      |
| `surprise-me`                  | Random creative tasks                           |
| `vercel-deploy-claimable`      | Deploy projects to Vercel                       |

### Tools System

**Path**: `backend/packages/harness/deerflow/tools/`

Tools are the agent's capabilities — functions it can call during execution.

**Built-in tools**:

| Tool                      | Description                                            |
| ------------------------- | ------------------------------------------------------ |
| `task`                    | Spawn a sub-agent to handle a delegated task           |
| `tool_search`             | Search available tools by description                  |
| `ask_clarification`       | Pause and ask the user for clarification               |
| `view_image`              | Load images for vision-model analysis                  |
| `present_file`            | Display a file to the user                             |
| `list_uploaded_files`     | List user-uploaded files                               |
| `review_skill_package`    | Review a skill package without activating it           |
| `setup_agent`             | Create/configure a custom agent                        |
| `update_agent`            | Update a custom agent's configuration                  |
| `invoke_acp_agent`        | Invoke an ACP (Agent Communication Protocol) agent     |

**Community tools** (loaded from `deerflow/community/`):

- `web_search` — Web search via configurable providers
- `web_fetch` — Read full page content as Markdown
- `web_capture` — Rendered screenshot of a page
- `image_search` — Search for images

**Sandbox tools** (from `deerflow/sandbox/tools.py`):

- `bash` — Execute shell commands (container-isolated or host-disabled)
- `ls` — List directory contents
- `read_file` — Read file contents with line-range support
- `write_file` — Create or overwrite a file
- `str_replace` — String-based find-and-replace editing

**Browser tools** (optional, `browser` extra):

- `browser_navigate` — Navigate to a URL
- `browser_snapshot` — Get accessible page element tree
- `browser_click` — Click on an element by ref
- `browser_type` — Type into an input field
- `browser_get_text` — Extract text from an element
- `browser_back` — Navigate back
- `browser_screenshot` — Take a page screenshot
- `browser_close` — Close the browser session

**Tool Authorization** (optional, gated by `authorization.enabled`):

- Pluggable `AuthorizationProvider` filters tools before they reach the model
- Built-in RBAC provider with per-role tool allow/deny policies
- `tool_search` is filtered to only show authorized tools

### Sandbox & File System

**Path**: `backend/packages/harness/deerflow/sandbox/`

Each agent task gets its own execution environment with a full filesystem view.

**Sandbox providers**:

| Provider              | Description                                                |
| --------------------- | ---------------------------------------------------------- |
| `E2BSandboxProvider`  | Remote E2B sandbox with VM isolation, warm pool, bursting  |
| `AioSandboxProvider`  | Container-based isolation (Docker)                         |
| `LocalSandboxProvider`| Host filesystem with per-thread directories (bash disabled) |

**Filesystem structure inside the sandbox**:

```
/mnt/
├── skills/
│   ├── public/           # Built-in skills (read-only)
│   └── custom/           # User-installed skills
└── user-data/
    ├── uploads/          # User-uploaded files
    ├── workspace/        # Agent's working directory
    └── outputs/          # Final deliverables
```

**Key features**:

- Per-thread directory isolation
- File operation locking (`file_operation_lock.py`)
- Path security policies (`security.py`, `path_patterns.py`)
- Environment variable policies (`env_policy.py`)
- Search across sandbox files (`search.py`)
- Workspace change tracking — after each run, a diff summary of changed files
  is recorded and displayed in the UI
- Image handling: Base64 images are removed from checkpoints after vision-model
  consumption to avoid payload duplication

### MCP Integration

**Path**: `backend/packages/harness/deerflow/mcp/`

UniDeer supports the Model Context Protocol (MCP) for connecting external tool
servers. MCP servers are configured in `extensions_config.json` or via the
Gateway API.

- **MCP client**: Connects to MCP servers over stdio or HTTP
- **Tool caching**: MCP tool schemas are cached and refreshed on reload
- **MCP routing middleware**: Routes tool calls to the correct MCP server
- **MCP metadata**: Tool annotations for MCP-sourced tools

### Model Factory

**Path**: `backend/packages/harness/deerflow/models/`

UniDeer is model-agnostic. It supports any LLM that exposes an
OpenAI-compatible API, plus custom providers.

**Supported model providers**:

| Provider                 | Description                                    |
| ------------------------ | ---------------------------------------------- |
| `langchain_openai`       | OpenAI and OpenAI-compatible APIs              |
| `VllmChatModel`          | Self-hosted vLLM inference                     |
| `CodexChatModel`         | OpenAI Codex CLI (GPT-5.4)                     |
| `ClaudeChatModel`        | Anthropic Claude (via OAuth or API key)        |
| `MindieProvider`         | Huawei MindIE models                           |
| Patched providers        | DeepSeek, MiniMax, StepFun, MiMo (with reasoning patches) |

**Key features**:

- Thinking/reasoning support (`supports_thinking`, `supports_reasoning_effort`)
- Vision model support for image understanding
- Responses API support (`output_version: responses/v1`)
- Credential loading from environment variables (`credential_loader.py`)

---

## Layer 5: Persistence

**Path**: `backend/packages/harness/deerflow/persistence/`

The persistence layer uses SQLAlchemy with Alembic for schema migrations.
Models cover:

| Module                   | Purpose                                      |
| ------------------------ | -------------------------------------------- |
| `user`                   | User accounts and profiles                   |
| `thread_meta`            | Thread metadata (title, timestamps, agent)   |
| `run`                    | Run records, status, and lineage             |
| `models`                 | Model configuration records                  |
| `agents`                 | Custom agent definitions                     |
| `schedule_tasks`         | Scheduled task definitions                   |
| `schedule_task_runs`     | Scheduled task execution history             |
| `feedback`               | User feedback on responses                   |
| `channel_connections`    | IM channel identity links                    |
| `migrations/`            | Alembic migration scripts                    |

**Key components**:

- `engine.py` — Async SQLAlchemy engine factory
- `base.py` — Repository base class with common CRUD
- `bootstrap.py` — Initial data seeding
- `json_compat.py` — JSON field compatibility helpers

---

## Layer 6: IM Channels

**Path**: `backend/app/channels/`

UniDeer bridges into external instant messaging platforms so users can interact
with the agent from their preferred chat app. All channels share a common
execution path through the Gateway run lifecycle.

**Supported channels**:

| Channel    | Status     |
| ---------- | ---------- |
| Feishu     | Supported  |
| Slack      | Supported  |
| Telegram   | Supported  |
| Discord    | Supported  |
| DingTalk   | Supported  |
| WeChat     | Supported  |
| WeCom      | Supported  |
| GitHub     | Supported  |

**Architecture**:

- `manager.py` — Channel lifecycle manager (start/stop all configured channels)
- `service.py` — Channel run dispatch service (threads messages into Gateway runs)
- `base.py` — Abstract channel base class
- `commands.py` — Common command handling (`/new`, `/help`, skill slash commands)
- `message_bus.py` — Internal message routing
- `store.py` / `runtime_config_store.py` — Channel state persistence
- `run_policy.py` — Per-channel run execution policies
- `connection_identity.py` — User identity linking across channels

Each channel receives user messages, converts them to Gateway thread runs, and
streams responses back. Session management (assistant_id, recursion limits,
thinking mode) is configurable per channel.

---

## Layer 7: Provisioner

The Provisioner (port 8002, optional) is a companion service that manages
sandbox infrastructure for Kubernetes-based deployments. It:

- Allocates sandbox pods/VMs on demand
- Manages warm sandbox pools for fast acquisition
- Handles sandbox lifecycle (create, health check, destroy)
- Is only started when the sandbox is configured for provisioner/K8s mode

In local development and Docker Compose with E2B/Aio providers, the provisioner
is not needed.

---

## Layer 8: Deployment & Orchestration

### Local Development

```bash
make dev     # Starts Gateway (8001) + Frontend (3000) + Nginx (2026)
```

### Docker Development

```bash
make docker-start   # Mode-aware from config.yaml (localhost:2026)
```

### Docker Production

```bash
make up             # docker-compose.yaml (production services at localhost:2026)
```

### Kubernetes

Helm chart at `deploy/helm/deer-flow/` for Kubernetes deployments.

### Configuration

- `config.yaml` (gitignored) — Main application config (models, sandbox, tools,
  channels, scheduler, logging, tracing)
- `extensions_config.json` (gitignored) — MCP servers and skill definitions
- `config.example.yaml` / `extensions_config.example.json` — Templates

### Startup Modes

The `config.yaml` supports mode-aware startup:

| Mode        | Description                                |
| ----------- | ------------------------------------------ |
| `flash`     | Fast responses, minimal reasoning          |
| `standard`  | Balanced speed and depth                   |
| `pro`       | Planning mode with explicit reasoning      |
| `ultra`     | Full sub-agent orchestration               |

---

## Data Flow: A Typical Request

```
1. User types a message in the Frontend composer
       │
2.     ▼  POST /api/threads/{id}/runs/stream
       │  (SSE streaming request)
3.     ▼  Gateway router validates auth, resolves agent config
       │
4.     ▼  RunManager.run_agent() creates a LangGraph run
       │     ├── Loads ThreadState from checkpointer
       │     ├── Resolves model (from config or thread override)
       │     ├── Builds middleware chain
       │     └── Invokes the lead agent graph
       │
5.     ▼  Lead Agent node executes:
       │     ├── Memory middleware injects user context
       │     ├── Skill activation loads SKILL.md if slash-activated
       │     ├── System prompt assembled (goal, skills, tools, memory)
       │     ├── LLM call with tool definitions
       │     └── Model responds with text + optional tool calls
       │
6.     ▼  Tool execution (if model calls tools):
       │     ├── Sandbox middleware provisions filesystem
       │     ├── Tool call routed to: built-in / sandbox / MCP / community
       │     ├── Tool result captured and sanitized
       │     └── Loop detection checks for infinite loops
       │
7.     ▼  Sub-agent orchestration (if task tool is called):
       │     ├── Sub-agent executor spawns parallel sub-agents
       │     ├── Each sub-agent gets isolated context + scoped tools
       │     ├── Sub-agents report TaskResult on completion
       │     └── Lead agent synthesizes sub-agent outputs
       │
8.     ▼  After run completes:
       │     ├── Memory extraction runs (new facts saved)
       │     ├── Title generation (if first turn)
       │     ├── Workspace changes computed
       │     ├── Goal evaluation (if active)
       │     ├── Suggestions generated
       │     └── Checkpoint saved
       │
9.     ▼  StreamBridge sends SSE events to Frontend:
       │     values → messages list with tool results and sub-agent cards
       │     custom → tool progress, task events, token usage
       │     messages-tuple → raw message tuples
       │
10.    ▼  Frontend renders:
            ├── Markdown response with animated word streaming
            ├── Sub-agent cards with step timelines and token usage
            ├── Workspace change badge with file diffs
            ├── Todo list updates
            ├── Goal status
            └── Follow-up suggestions
```

---

## Repository Map

```
deer-flow/
├── Makefile                        # Root orchestration: full stack (dev/start/stop/docker/setup)
├── config.example.yaml             # Template → copy to config.yaml (gitignored)
├── extensions_config.example.json  # Template → copy to extensions_config.json (gitignored)
├── AGENTS.md                       # Monorepo orientation for AI coding agents
├── README.md                       # Project README (+ translations: zh, ja, fr, ru)
│
├── backend/                        # Python backend
│   ├── Makefile                    # Backend commands (dev, gateway, test, lint, migrate-rev)
│   ├── langgraph.json              # LangGraph entry point (deerflow.agents:make_lead_agent)
│   ├── pyproject.toml              # Python dependencies (uv)
│   ├── ruff.toml                   # Lint/format policy
│   ├── packages/harness/deerflow/  # Core agent framework (import: deerflow.*)
│   │   ├── agents/                 # Lead agent, middleware chain, memory
│   │   ├── sandbox/                # Sandbox providers + file tools
│   │   ├── subagents/              # Sub-agent registry + executor
│   │   ├── tools/builtins/         # Built-in tools
│   │   ├── mcp/                    # MCP integration
│   │   ├── models/                 # Model factory + providers
│   │   ├── skills/                 # Skills discovery, loading, scanning
│   │   ├── runtime/                # RunManager, StreamBridge, checkpointer
│   │   ├── config/                 # Configuration system
│   │   ├── persistence/            # SQLAlchemy models + Alembic migrations
│   │   ├── guardrails/             # Guardrail middleware + provider interface
│   │   ├── authz/                  # Authorization provider interface
│   │   ├── community/              # Community tools (search, fetch, image search)
│   │   ├── reflection/             # Dynamic module loading
│   │   ├── scheduler/              # Background task scheduler
│   │   ├── tui/                    # Terminal workbench (TUI)
│   │   ├── uploads/                # File upload management
│   │   ├── workspace_changes/      # Workspace diff computation
│   │   ├── tracing/                # LangSmith/Langfuse/Monocle integration
│   │   └── client.py               # Embedded Python client (UniDeerClient)
│   ├── app/                        # Application layer
│   │   ├── gateway/                # FastAPI Gateway + REST routers
│   │   └── channels/               # IM platform integrations
│   ├── tests/                      # Backend test suite (277+ tests)
│   ├── scripts/                    # Migration and utility scripts
│   └── docs/                       # Backend-specific documentation
│
├── frontend/                       # Next.js frontend (pnpm)
│   ├── src/
│   │   ├── app/                    # Next.js App Router
│   │   ├── components/             # React components
│   │   ├── core/                   # Business logic (threads, api, auth, skills, etc.)
│   │   ├── hooks/                  # Shared React hooks
│   │   ├── lib/                    # Utilities
│   │   ├── styles/                 # Global CSS (Tailwind v4)
│   │   └── content/                # MDX content
│   └── tests/                      # Unit + E2E tests
│
├── docker/                         # Docker compose files, nginx config, provisioner
├── deploy/helm/deer-flow/          # Kubernetes Helm chart
├── skills/public/                  # 24+ built-in skill packs
├── contracts/                      # Cross-component JSON contracts
├── scripts/                        # Root orchestration scripts (check, configure, doctor)
├── tests/                          # Root-level tests (public skill tests)
├── docs/                           # Cross-cutting docs, plans, design notes
└── plans/                          # Feature planning & design documents
```

---

## Key Concepts Glossary

| Term                  | Definition                                                                                     |
| --------------------- | ---------------------------------------------------------------------------------------------- |
| **Lead Agent**        | The primary LangGraph agent that orchestrates a conversation turn                               |
| **Sub-Agent**         | A delegated agent spawned by the lead agent for parallel task execution                         |
| **Skill**             | A structured capability module (SKILL.md) that extends what the agent can do                    |
| **Thread**            | A conversation session with persistent state, checkpoints, and history                          |
| **Run**               | A single execution of the agent within a thread (one user message → agent response)             |
| **Middleware**        | A composable pipeline component that wraps agent steps (before/after model calls)              |
| **Sandbox**           | An isolated filesystem/execution environment per thread (E2B, Docker, or local)                |
| **Checkpointer**      | Persists thread state after each step so runs can resume or branch                              |
| **StreamBridge**      | Converts LangGraph internal events into SSE streams for the frontend                           |
| **MCP**               | Model Context Protocol — standard for connecting external tool servers                         |
| **Tool**              | A callable function the agent can invoke (built-in, sandbox, community, MCP-sourced)           |
| **Memory**            | Persistent, cross-session storage of user profile, preferences, and facts                      |
| **Context Compaction**| Summarizing older conversation context to stay within token limits                              |
| **Goal**              | A thread-scoped completion condition set via `/goal` — agent auto-continues until satisfied     |
| **Workspace Changes** | Per-run diff summary of files created, modified, or deleted in the sandbox                     |
| **Provisioner**       | Optional service that manages sandbox infrastructure for Kubernetes deployments                |
| **TUI**               | Terminal User Interface — a CLI workbench for interacting with UniDeer                        |
| **SkillScan**         | Deterministic safety scanner that runs on installed skills before activation                   |
| **UniDeerClient**    | Embedded Python client for programmatic interaction with a UniDeer instance                   |

---

*Generated from the UniDeer repository source. See [README.md](../README.md) for
usage instructions, and [AGENTS.md](../AGENTS.md) for development orientation.*
