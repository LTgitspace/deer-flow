# Middleware Pipeline Performance Optimization Plan

Address latency, high time-to-first-token (TTFT), and multi-turn execution delays caused by the 35+ Python middleware chain in `deerflow-harness`.

---

## 1. Problem Diagnosis & Root Causes

Profiling and code analysis of `packages/harness/deerflow/agents/middlewares/` identified **5 core performance bottlenecks**:

1. **The "Inactive Skill Nudge Storm" (False Positive Triggers)**:
   - Middlewares like [`DeepResearchMiddleware`](file:///c:/github/deer-flow/backend/packages/harness/deerflow/agents/middlewares/deep_research_middleware.py) and [`SystemDesignMiddleware`](file:///c:/github/deer-flow/backend/packages/harness/deerflow/agents/middlewares/system_design_middleware.py) use broad keyword triggers (`"why"`, `"what is"`, `"explain"`, `"system"`, `"design"`).
   - When a skill is **not active**, they still inject hidden activation nudges into `request.messages` on regular conversational queries, polluting prompt tokens and causing prompt drift.
2. **Multi-LLM Roundtrips from Post-Answer Correction Gates**:
   - `Metacognition` (Gate B), `EmojiGate` (Gate B), and `Planner` run post-generation correction gates. If a model generates text that violates a heuristic, the turn triggers a 2nd or 3rd full LLM generation call, multiplying turn latency by 2x–3x.
3. **Repeated Disk I/O in Middleware Hooks**:
   - `SkillActivationMiddleware` and `SkillToolPolicyMiddleware` read `SKILL.md` files from disk and recompute policy signatures on every single model call and tool execution without an in-memory hot cache.
   - `ReadBeforeWriteMiddleware` performs synchronous file stats and disk reads during tool execution.
4. **Repeated Message List Allocations (35+ Passes per Turn)**:
   - Every middleware executes `messages = list(request.messages)` and `request.override(messages=...)`, repeatedly cloning and mutating LangChain message objects across 35 sequential wrappers.
5. **Lack of Fast-Path Early Exits**:
   - Middlewares execute full regex scans, unicode scans, and history traversals even when irrelevant to the current turn (e.g. `EmojiGate` scanning text-only conversations, or `PlantingResearchMiddleware` scanning non-agricultural threads).

---

## 2. Proposed Architectural Optimizations

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         OPTIMIZATION ARCHITECTURE                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Phase 1: In-Memory Storage & Policy Cache                                  │
│  ├── Cache parsed `SKILL.md` contents & YAML frontmatter in memory (LRU)    │
│  └── Cache tool policy signatures per active skill set                      │
│                                                                             │
│  Phase 2: Strict Skill-Scoped Gating (Eliminate Nudge Storms)               │
│  ├── Inactive domain middlewares return `await handler(request)` on Line 1  │
│  └── Disable broad keyword "shaped-but-inactive" nagging nudges             │
│                                                                             │
│  Phase 3: Pre-Answer Nudge Consolidation                                    │
│  ├── Shift post-generation retries to single pre-generation nudges          │
│  └── Consolidate message list overrides into a single pre-model pass        │
│                                                                             │
│  Phase 4: Fast-Path Regex & Unicode Scanners                                │
│  ├── Check `_has_code_blocks` before running expensive unicode emoji scans │
│  └── Cache latest user message index across middleware passes               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. User Review Required

> [!IMPORTANT]
> **Behavioral Change on Inactive Skills**:
> Domain-specific middlewares (`deep-research`, `system-design`, `business-requirement`, `planting-research`) currently nag the model to load skills when a user query happens to contain words like `"explain"`, `"why"`, or `"design"`.
> **Proposed Fix**: Gate domain middlewares to fire **ONLY** when the skill is explicitly slash-activated (`/deep-research`) or already loaded into `ThreadState.skill_context`. General queries will proceed immediately without inactive skill nudges or wasted tokens.

> [!TIP]
> **Pre-Answer vs. Post-Answer Corrections**:
> Shifting `Metacognition` and `EmojiGate` to strictly **pre-answer instruction** saves 2–5 seconds per turn by eliminating second LLM roundtrips.

---

## 4. Proposed Changes by Component

### Component: Skill Storage & Tool Policy Caching

#### [MODIFY] [skill_storage.py](file:///c:/github/deer-flow/backend/packages/harness/deerflow/skills/storage/skill_storage.py)
- Add `@lru_cache` / in-memory dictionary caching for `get_skill()`, `load_skills()`, and `get_skill_file()`.
- Invalidate cache only when skills are mutated via `skill_manage` or `SkillStorage.save_skill()`.

#### [MODIFY] [skill_tool_policy_middleware.py](file:///c:/github/deer-flow/backend/packages/harness/deerflow/agents/middlewares/skill_tool_policy_middleware.py)
- Cache resolved `_PolicySignature` decisions per `(user_id, slash_path, skill_context_hash)` to avoid re-resolving storage on every tool call.

---

### Component: Domain Middleware Fast-Paths & Nudge Cleanup

#### [MODIFY] [deep_research_middleware.py](file:///c:/github/deer-flow/backend/packages/harness/deerflow/agents/middlewares/deep_research_middleware.py)
- Replace broad keyword matching with a strict `skill_is_active(messages, state, "deep-research")` fast-exit.
- Remove `_build_inactive_skill_nudge` so non-research queries aren't nagged.

#### [MODIFY] [system_design_middleware.py](file:///c:/github/deer-flow/backend/packages/harness/deerflow/agents/middlewares/system_design_middleware.py)
- Fast-exit immediately if `system-design` is not active in `skill_context` or slash command.
- Eliminate shaped-but-inactive reminder injections.

#### [MODIFY] [business_requirement_middleware.py](file:///c:/github/deer-flow/backend/packages/harness/deerflow/agents/middlewares/business_requirement_middleware.py)
- Add fast-path check: skip execution unless `business-requirement` is active.

#### [MODIFY] [planting_research_middleware.py](file:///c:/github/deer-flow/backend/packages/harness/deerflow/agents/middlewares/planting_research_middleware.py)
- Fast-path check: skip unless `planting-research` is active.

---

### Component: Cognitive & Sanitization Middlewares

#### [MODIFY] [metacognition_middleware.py](file:///c:/github/deer-flow/backend/packages/harness/deerflow/agents/middlewares/metacognition_middleware.py)
- Disable Gate B (post-answer re-trip) by default or make it single-turn advisory without forcing a second LLM generation.
- Strengthen Gate A (pre-answer prompt) so reasoning is produced on the initial generation.

#### [MODIFY] [emoji_gate_middleware.py](file:///c:/github/deer-flow/backend/packages/harness/deerflow/agents/middlewares/emoji_gate_middleware.py)
- Fast-path check: only run Unicode regex if text actually contains code block markers (```` ``` ````) or tool mutation intent (`write_file`, `str_replace`).

#### [MODIFY] [read_before_write_middleware.py](file:///c:/github/deer-flow/backend/packages/harness/deerflow/agents/middlewares/read_before_write_middleware.py)
- Offload synchronous file hash check via `asyncio.to_thread` and cache file hash by `(thread_id, file_path, mtime)` to avoid re-reading disk if unchanged.

---

## 5. Verification Plan

### Automated Tests
1. **Performance Benchmark**:
   - Measure TTFT (Time-to-first-token) and total turn wall-clock time on standard prompts before and after optimization:
   ```bash
   cd backend && python -m pytest tests/test_middleware_performance.py
   ```
2. **Regression & Safety Tests**:
   - Ensure all existing middleware invariant tests pass without regression:
   ```bash
   cd backend && make test
   cd backend && make test-blocking-io
   ```
3. **Skill & Policy Tests**:
   - Verify skill tool policies and slash activations remain strictly enforced:
   ```bash
   cd backend && pytest tests/test_skill_tool_policy_middleware.py tests/test_skill_activation_middleware.py
   ```

### Manual Verification
- Test interactive chat in Web UI (`http://localhost:2026`):
  1. Send a casual query (*"Why is the sky blue?"*) -> Verify zero inactive skill nudges, instant streaming response.
  2. Send a slash command (`/deep-research AI trends`) -> Verify deep-research skill activates and enforces research gates properly.
  3. Send a multi-step coding request -> Verify `PlannerMiddleware` and `ReadBeforeWriteMiddleware` function with minimal latency overhead.
