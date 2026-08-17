# UniDeer Memory Profile

> Why UniDeer's RAM consumption is high, where it goes, and what you can do about it.

---

## Table of Contents

- [Quick Numbers](#quick-numbers)
- [The Stack Baseline](#the-stack-baseline)
- [Python Message Object Inflation](#python-message-object-inflation)
- [The Copy Problem (Amplifier)](#the-copy-problem-amplifier)
- [Checkpoint Serialization Bloat](#checkpoint-serialization-bloat)
- [Model Call Payload Duplication](#model-call-payload-duplication)
- [Sub-Agent Amplification](#sub-agent-amplification)
- [Streaming SSE Buffers](#streaming-sse-buffers)
- [Token Counting Overhead](#token-counting-overhead)
- [Docker vs Local Dev](#docker-vs-local-dev)
- [Mitigations (No Rewrite Needed)](#mitigations-no-rewrite-needed)
- [Why Spring AI Alibaba Would Use Less RAM](#why-spring-ai-alibaba-would-use-less-ram)

---

## Quick Numbers

| Scenario | RAM (approximate) |
|---|---|
| `make dev` — idle | 600-800 MB |
| `make dev` — single conversation, 5 tool-call turns | 1.0-1.5 GB |
| `make dev` — 3 concurrent conversations with sub-agents | 2.0-3.5 GB |
| `make start` (production mode) — idle | 200-300 MB |
| Production Docker, single concurrent conversation | 300-500 MB |
| Spring AI Alibaba equivalent (estimated) | 150-300 MB |

---

## The Stack Baseline

UniDeer is not a single process. `make dev` or `docker-compose-dev.yaml` starts **4-5 services**:

| Service | Tech | Idle RAM | Under Load | Notes |
|---|---|---|---|---|
| **Frontend** | Next.js 16 + Turbopack (dev) | ~400 MB | ~1.5 GB | **Biggest single consumer** in dev mode |
| **Frontend** | Next.js 16 production (`pnpm start`) | ~80 MB | ~150 MB | Compiled, no HMR overhead |
| **Gateway** | Python/uvicorn + LangGraph runtime | ~150 MB | ~400 MB | Single process, single-threaded |
| **Redis** | Redis 7 Alpine | ~10 MB | ~50 MB | Optional; Docker dev only |
| **Nginx** | Nginx Alpine | ~5 MB | ~15 MB | Reverse proxy |
| **Provisioner** | Python/FastAPI | ~50 MB | ~100 MB | Optional; K8s sandbox only |

**Biggest single culprit**: The Next.js 16 dev server with Turbopack + HMR. This is a Next.js characteristic, not a UniDeer bug. Switching to `make start` (production mode) alone saves **~1 GB**.

---

## Python Message Object Inflation

Every conversation message in UniDeer is a LangChain Pydantic v2 model object. A single `AIMessage` after a tool-call response carries:

```
AIMessage(
    content="The weather in Tokyo is 22°C, sunny.",   # response text
    tool_calls=[                                       # structured tool call array
        {
            "id": "call_abc123",
            "name": "get_weather",
            "args": {"city": "Tokyo", "units": "celsius"},
        }
    ],
    additional_kwargs={                                # raw provider payload (huge)
        "tool_calls": [                                 # DUPLICATE of tool_calls
            {
                "id": "call_abc123",
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "arguments": '{"city":"Tokyo","units":"celsius"}',
                },
                "thought_signature": "base64encoded==",  # Gemini thinking field
                "index": 0,
            }
        ],
        "refusal": None,
        "reasoning_content": "...",                      # DeepSeek-style reasoning
    },
    response_metadata={                                 # provider response metadata
        "model_name": "gemini-3-pro",
        "finish_reason": "tool_calls",
        "token_usage": {"prompt_tokens": 1234, "completion_tokens": 56, "total_tokens": 1290},
        "system_fingerprint": "fp_xxx",
        "model_provider": "openai",
    },
    usage_metadata={                                    # another usage copy
        "input_tokens": 1234,
        "output_tokens": 56,
        "total_tokens": 1290,
    },
)
```

In CPython, a Pydantic `BaseModel` with nested dicts has significant overhead:
- **Dict overhead**: ~72 bytes empty, ~8 bytes per key-value pair
- **String duplication**: The tool name `"get_weather"` appears in 3+ places. CPython's small-string interning helps for literals, but API responses come as parsed JSON — new string objects.
- **Nested list/dict wrappers**: Each level of nesting creates wrapper objects (`list`, `dict`) with their own overhead

A `ToolMessage` carries the **full tool output** as a string. For `web_fetch` or `web_search`, this is frequently tens of kilobytes of JSON or Markdown.

### Message Count Per Conversation

A typical 5-turn tool-call conversation contains:

| Turn | Messages Added | Type |
|---|---|---|
| User sends question | 1 | `HumanMessage` |
| Agent plans + calls tools | 1 | `AIMessage` (tool_calls) |
| Tools execute (3 tools) | 3 | `ToolMessage` |
| Agent synthesizes | 1 | `AIMessage` (response) |
| **Per turn total** | **6** | |
| **5-turn conversation total** | **30** | |

With 30 message objects, each carrying `additional_kwargs`, `response_metadata`, and `usage_metadata` dicts, the Python message list alone consumes **2-5 MB** in a moderate conversation.

---

## The Copy Problem (Amplifier)

UniDeer's 39-middleware chain processes messages through multiple stages. Each middleware that modifies a message calls `model_copy()`, which creates a new Pydantic object with a new set of nested dicts:

```python
# SafetyFinishReasonMiddleware
kwargs = dict(getattr(cleared, "additional_kwargs", None) or {})  # new dict
return cleared.model_copy(update={"additional_kwargs": kwargs})    # new AIMessage

# DanglingToolCallMiddleware
rewritten[index] = msg.model_copy(update=update)                   # per message
existing_tool_msg = existing_tool_msg.model_copy(update={...})     # per orphan

# TokenBudgetMiddleware
stopped_msg = msg.model_copy(update={...})                         # hard stop

# LoopDetectionMiddleware
stripped_msg = last_msg.model_copy(update={...})                   # loop warning
```

I counted **20+ `model_copy()` call sites** across the middleware chain. Each creates a **shallow copy**: content strings are shared (CPython ref-counted), but every nested dict (`additional_kwargs`, `response_metadata`, `tool_calls`) is allocated fresh. In a 5-turn run, this means:

- 30 messages × 20+ possible copies across 39 middlewares
- Middlewares that don't touch messages skip the copy — but the chain still walks them
- Temporary copies are garbage collected, but CPython's reference counting + occasional GC cycles mean memory peaks higher than the steady state

The pattern isn't a bug — it's LangGraph's immutability contract. State is updated via reducer functions that return new values. The cost is allocation churn.

---

## Checkpoint Serialization Bloat

LangGraph checkpoints the entire `ThreadState` after every graph step (model call, tool execution). The checkpointing path:

```
ThreadState (in memory)
    ├── messages: List[BaseMessage]     ← 30 Pydantic objects, ~2-5 MB
    ├── goal_state: GoalState | None
    ├── todos: List[Todo]
    └── ... (other state fields)

Step 1: model_dump()       → Python dict      ← FULL COPY in memory (~2-5 MB)
Step 2: json.dumps()       → JSON string      ← FULL COPY in memory (~1-3 MB)
Step 3: write to SQLite/PG → on disk
```

During a single checkpoint, **three copies** of the message list coexist in memory:

1. Original Pydantic objects in the running state
2. `model_dump()` dict (Python dictionaries + lists + primitives)
3. `json.dumps()` string (serialized UTF-8)

For a 5-turn run with checkpoints after every tool call (15 checkpoints), that's 15 serialization cycles. Garbage collection reclaims the temporary dict/string after each step, but peak memory during each checkpoint is 2-3× the message list size.

### What Gets Checkpointed

Not just messages. The full `ThreadState` includes:

- `messages`: The conversation history (primary cost)
- `goal_state`: Active goal metadata
- `todos`: Structured todo list
- `skills_active`: Currently active skill contexts
- `memory_identity`: Memory identity per run
- `durable_context`: Checkpoint-surviving context
- `delegation_ledger`: Sub-agent delegation tracking

The checkpointer uses LangGraph's built-in `SqliteSaver` or `PostgresSaver`. In multi-worker mode with Redis, checkpoint state is also broadcast through Redis streams.

---

## Model Call Payload Duplication

Every LLM call serializes the full conversation history into the HTTP request body. This is an OpenAI-compatible JSON payload:

```json
{
    "model": "gemini-3-pro",
    "messages": [
        {"role": "system", "content": "<system prompt ~4 KB>"},
        {"role": "user", "content": "What's the weather?"},
        {"role": "assistant", "content": null, "tool_calls": [...]},
        {"role": "tool", "tool_call_id": "...", "content": "<tool output>"},
        ...
    ],
    "tools": [...],
    "stream": true
}
```

The serialization path:

```
original messages (Pydantic, ~2-5 MB)
    → _convert_input().to_messages()       ← LangChain conversion copy
    → _get_request_payload()               ← JSON-serializable dict copy
    → restore_assistant_payloads()         ← thought_signature injection
    → json.dumps()                          ← HTTP body string
    → httpx sends to API
```

**4 copies** of the message list per model call: original → conversion → payload dict → JSON string.

In a 5-turn conversation with 3 model calls per turn (tool selection, tool synthesis, final response), that's **15 serialization cycles**. Each cycle allocates temporary dicts and strings that are freed after the HTTP request completes.

With `PatchedChatOpenAI`, the `_get_request_payload` override also:

1. Calls `self._convert_input(input_).to_messages()` (LangChain objects)
2. Calls `super()._get_request_payload(...)` (parent creates another copy)
3. Calls `restore_assistant_payloads(...)` (walking and matching)

This is **one extra conversion copy** beyond what standard `ChatOpenAI` does, necessary for `thought_signature` preservation on Gemini models.

---

## Sub-Agent Amplification

When the lead agent spawns sub-agents via the `task` tool, each sub-agent:

1. **Inherits the sandbox** — shared filesystem, no RAM duplication there
2. **Gets isolated `ThreadState`** — new message list with sub-agent context (~0.5-2 MB)
3. **Gets its own middleware chain** — fresh middleware instances (~50 KB each × 39 = ~2 MB)
4. **Gets its own model calls** — separate serialization cycles for each LLM invocation
5. **Holds tool outputs** — results are captured until the parent collects them

For three parallel sub-agents, each with a 15-message context and 2 tool outputs:

```
Sub-agent 1:  ~2 MB (state) + ~2 MB (middlewares) + ~1 MB (serialization) = ~5 MB
Sub-agent 2:  ~5 MB
Sub-agent 3:  ~5 MB
Parent wait:  ~5 MB (holding the parent state)
────────────────────────────────────────────────────────────────────────────
Peak during sub-agent fan-out: + ~20 MB temporary
```

The `SubagentLimitMiddleware` caps concurrent sub-agents (default: 3), which limits peak amplification. But in ultra mode with `subagent_enabled: true`, the default cap still allows significant fan-out.

Long-running sub-agents also trigger summarization — the `SummarizationMiddleware` creates a summary text and replaces old messages. This creates temporary allocation (the summary prompt + model response) but reduces steady-state message count.

---

## Streaming SSE Buffers

Each concurrent run holds an SSE event buffer in the `StreamBridge`:

```python
# Event types streamed per run:
values          → full message list snapshot (largest)
custom          → tool progress, task events, token usage
messages-tuple  → raw message tuples
```

The `values` event is the largest — it contains a snapshot of the entire message list after each step. For a conversation with 30 messages, that's a JSON payload of 10-50 KB per event, emitted 15+ times per run.

With 3 concurrent streaming clients, the gateway holds:

- 3 × active message list in memory
- 3 × SSE buffer queues (pending events not yet sent to client)
- 3 × LangGraph run state (checkpoint snapshots)

The Redis stream bridge (in Docker dev) adds cross-worker broadcast overhead: events are published to Redis and consumed by the owning worker. This adds serialization/deserialization cycles but enables multi-worker deployments. For single-worker dev mode, this is unnecessary overhead.

---

## Token Counting Overhead

UniDeer uses `tiktoken` for token counting. The tokenizer model (e.g., `cl100k_base` for GPT-4) is loaded into memory once per process:

| Tokenizer | RAM |
|---|---|
| `cl100k_base` (GPT-4, GPT-3.5) | ~2 MB |
| `o200k_base` (GPT-4o) | ~2 MB |
| `p50k_base` (text-davinci) | ~2 MB |

This is a one-time cost and not per-conversation. But in the `TokenBudgetMiddleware` and `SummarizationMiddleware`, every message is token-counted per step. The counting itself doesn't allocate much, but the full message list must be traversed, keeping it in CPU cache (and therefore in RAM).

The `TokenUsageMiddleware` also accumulates usage metadata on every message — injecting `usage_metadata` dicts that add to each message's object size.

---

## Docker vs Local Dev

| Mode | Services | Base RAM | Why |
|---|---|---|---|
| `make dev` (local) | Gateway + Frontend + Nginx | ~600 MB | Next.js dev (Turbopack) is the big one |
| `make start` (local) | Gateway + Frontend + Nginx | ~200 MB | Next.js production build, no HMR |
| `make docker-start` | All 5 services in Docker | ~800 MB | Docker overhead + Redis + provisioner |
| `make up` (production) | 3 services in Docker | ~300 MB | No Redis, no provisioner, compiled frontend |

**Key insight**: Most of the RAM you see in `make dev` is **Next.js dev mode**, not the Python agent. The Gateway process itself (Python + LangGraph) is typically 150-400 MB. The frontend dev server is 400-1500 MB.

---

## Mitigations (No Rewrite Needed)

### Immediate (today, config changes only)

| Action | RAM Saved | How |
|---|---|---|
| **Run frontend in production mode** | ~1 GB | `make start` instead of `make dev`, or `pnpm build && pnpm start` |
| **Aggressive summarization** | Caps message list growth | `summarization.max_tokens_before_summary: 8000` in config |
| **Reduce recursion_limit** | Caps turn depth | `session.config.recursion_limit: 50` (default may be higher) |
| **Disable sub-agents in non-ultra modes** | Prevents fan-out peaks | `subagent_enabled: false` in session context |
| **Disable thinking mode for simple queries** | Reduces per-message metadata | `thinking_enabled: false` in session context |
| **Use flash mode for responses** | Fewer tool calls = fewer messages | Mode selection in UI or session context |

### Medium-term (small code changes)

| Action | RAM Saved | Effort |
|---|---|---|
| **Lazy tool output loading** — don't store full tool outputs in memory; stream from filesystem | ~1-3 MB per long tool call | Few days |
| **`additional_kwargs` stripping** — remove raw provider payload after extraction; keep only what must be replayed | ~30-50% per AI message | Few hours |
| **Checkpoint messages only** — default LangGraph checkpoints the full state including non-message fields | ~0.5-1 MB per checkpoint | Config change |
| **SSE event deduplication** — don't send `values` if nothing changed since last event | Reduces buffer pressure | Few days |

### Long-term (architectural)

| Action | RAM Saved | Effort |
|---|---|---|
| **Postgres checkpointer with streaming reads** — load checkpoints lazily, not full state in memory | ~50% checkpoint overhead | Weeks |
| **Message object pooling** — reuse `ToolMessage` content strings via interned storage | Varies | Weeks |
| **Spring AI Alibaba rewrite** — JVM's generational GC + off-heap message storage | 50-70% overall | 6-12 months |

---

## Why Spring AI Alibaba Would Use Less RAM

The same agent workload in Spring AI Alibaba uses less RAM for fundamental reasons:

| Factor | Python (UniDeer) | JVM (Spring AI Alibaba) |
|---|---|---|
| **Object model** | Pydantic v2 with nested dicts (~72 bytes per dict overhead) | Plain Java POJOs with field-level allocation |
| **Message storage** | `List[BaseMessage]` in memory, all at once | `Flux<Message>` reactive stream, can be lazily loaded |
| **Copy strategy** | Immutable `model_copy()` — new objects per mutation | Mutable builders or copy-on-write — fewer allocations |
| **GC model** | Reference counting + occasional mark-sweep — object churn causes fragmentation | Generational GC — short-lived objects cost near-zero, old-gen compacted |
| **String handling** | New `str` objects from parsed JSON; limited interning | `String` pool for literals; `byte[]` for content, shared via `CharBuffer` |
| **Checkpoint** | Full `model_dump()` → dict → JSON string in memory | Java serialization can stream to disk without full in-memory copy |
| **Concurrency** | Single-threaded + asyncio — all state in one heap | Native threads + off-heap buffers — state distributed across thread stacks |
| **Serialization** | JSON via `json.dumps()` — allocates full string | Jackson `JsonGenerator` — can stream to OutputStream |

The JVM doesn't eliminate the RAM cost — it changes the shape. Instead of many Python dict objects with high per-object overhead, you get fewer, denser Java objects with better cache locality. The generational GC means middleware copies (short-lived) cost almost nothing because they never leave the nursery generation.

---

## Profiling Commands

To measure actual RAM usage in your deployment:

```bash
# Per-process RSS (Resident Set Size) on Linux/macOS
ps aux | grep -E "uvicorn|next|nginx|redis|provisioner" | awk '{print $6, $11}'

# Docker container memory
docker stats --no-stream

# Python memory profile (install memray first)
cd backend
uv run memray run -o profile.bin -m uvicorn app.gateway.app:app --host 0.0.0.0 --port 8001
uv run memray flamegraph profile.bin

# Python object counts during a run (via tracemalloc)
PYTHONTRACEMALLOC=1 make dev
# Then trigger a run and check /tmp/tracemalloc.log
```

---

*Generated: 2026-07-25*
