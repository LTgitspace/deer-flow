# Gemini 3 Family: Thinking + Tool Call Signature Compatibility

**Status**: Planned
**Impact**: Users cannot use Gemini 3 (Pro/Flash) thinking mode with tool calling
**Scope**: Model adapter layer only — no harness changes needed

---

## Problem

DeerFlow's `PatchedChatOpenAI` (`backend/packages/harness/deerflow/models/patched_openai.py`)
preserves the `thought_signature` field on tool-call objects required by Gemini 2.5's
OpenAI-compatible API. Gemini 3 introduced a **new signature format** that this adapter
does not recognize. The result: thinking-mode multi-turn tool-call conversations fail
with `HTTP 400 INVALID_ARGUMENT` because the required signature field is missing from
the payload.

## Background — Why This Matters

DeerFlow is a **deterministic harness**, not a probabilistic wrapper. Tool-call ID
validation, orphan recovery, dangling-call injection, and provider-specific field
replay are all enforced by code — not by prompting the model. When the adapter
silently drops a required field, the harness has no way to recover because the
failure happens at the HTTP boundary before the model even sees the request.

The fix is **surgical**: only the model adapter layer needs to change. The entire
middleware chain, sandbox, sub-agent executor, tool registry, and checkpointer are
provider-agnostic and consume normalized `AIMessage` / `ToolMessage` objects.

## Current State

### What works

| Path | Gemini 2.5 | Gemini 3 |
|---|---|---|
| Chat (no tools, no thinking) via OpenAI-compat gateway | Working | Untested (likely works) |
| Chat + tools (no thinking) via OpenAI-compat gateway | Working | Untested (likely works) |
| Chat + tools + thinking via OpenRouter (`supports_thinking: false`) | Working | Working |
| Safety termination detection (SAFETY, BLOCKLIST, etc.) | Working | Working (generic) |
| `native_api: true` (Google GenAI SDK path) | Working | Unknown |

### What's broken

| Path | Gemini 2.5 | Gemini 3 |
|---|---|---|
| **Chat + tools + thinking via OpenAI-compat gateway** | Working (with `PatchedChatOpenAI`) | **Broken** |
| **Chat + tools + thinking via native Google API** | Partial | **Broken** |

### Current adapter: `PatchedChatOpenAI`

```python
# patched_openai.py — the only Gemini-specific logic:
sig = raw_tc.get("thought_signature") or raw_tc.get("thoughtSignature")
if sig:
    payload_tc["thought_signature"] = sig
```

This pattern-matches two field names:
- `thought_signature` (snake_case)
- `thoughtSignature` (camelCase)

It does **not** capture or replay `reasoning_content` from assistant messages (unlike
DeepSeek, MiMo, StepFun, and MiniMax adapters which all do). It has **zero automated
tests**.

## What We Need to Determine

1. **What is Gemini 3's new signature format?**
   - New field name? (e.g., `reasoning_signature`, `thinking_signature`)
   - New structure? (per-message header, linked `thought_id` chain, nested object)
   - Same `thought_signature` but different location in the response object?

2. **Does Gemini 3 return `reasoning_content` on assistant messages?**
   - If yes: the adapter must capture, store in `additional_kwargs`, and replay it
     on historical assistant messages — same pattern as `patched_deepseek.py` and
     `patched_mimo.py`.

3. **Does Gemini 3's streaming delta format differ from OpenAI-compatible?**
   - If yes: `_convert_chunk_to_generation_chunk` must handle provider-specific
     delta fields.

4. **Does the `extra_body.thinking` config work for Gemini 3?**
   - If the thinking toggle format changed, `when_thinking_enabled.extra_body`
     must be updated in `config.example.yaml`.

## Fix Plan

### Phase 1: Gather the wire format

Capture a **real Gemini 3 API response** (with thinking + tool calls) via the
OpenAI-compatible endpoint. Record:

- Full response JSON (assistant message with `tool_calls` + thinking signature)
- Streaming chunk format (if different from non-streaming)
- Request payload shape expected on the second turn (which fields must be echoed)

Tools:
- `curl` against the gateway endpoint with `stream: false`
- MITM proxy or debug logging in LangChain's `_get_request_payload`
- Or: compare against Gemini 3's published API docs / OpenAPI spec

### Phase 2: Extend or create a new adapter

Based on findings, either:

**Option A**: Extend `PatchedChatOpenAI` if the changes are backward-compatible
(add fallback field detection, add `reasoning_content` capture)

**Option B**: Create `PatchedChatGemini3` (new class in `patched_openai.py` or its
own module) if the format is too divergent from Gemini 2.5's `thought_signature`

Required capabilities:

| Capability | Existing? | Needed? |
|---|---|---|
| `thought_signature` replay on tool calls | Yes (Gemini 2.5) | Yes (if Gemini 3 kept it) |
| New signature field capture & replay | No | **Yes** |
| `reasoning_content` capture (non-streaming) | No | Likely |
| `reasoning_content` capture (streaming) | No | Likely |
| `reasoning_content` replay on historical messages | No | Likely |
| Extra body thinking toggle | Yes | Verify |

### Phase 3: Add automated tests

Current test coverage for the Gemini path: **zero tests**.

Add tests in `backend/tests/`:

1. **Unit test**: `PatchedChatGemini3` correctly extracts the new signature from a
   recorded Gemini 3 API response
2. **Unit test**: The adapter replays the signature on subsequent request payloads
3. **Unit test**: Round-trip: response → `AIMessage` → serialized → matches original
   expected request format
4. **Unit test**: Streaming chunks correctly accumulate `reasoning_content`
5. **Integration test** (optional): End-to-end conversation with a mock Gemini 3 endpoint

### Phase 4: Update configuration and docs

1. `config.example.yaml` — add a documented Gemini 3 model entry with the correct
   `when_thinking_enabled` block
2. `backend/docs/CONFIGURATION.md` — update the "Gemini with thinking" section
3. `frontend/src/app/mock/api/models/route.ts` — update the mock model from stub
   to real model name if applicable

### Phase 5: Validate

- Manual test: `Gemini 3 Pro + thinking + tool calls` with a real API key
- Verify: multi-turn conversation with `bash`, `web_search`, and `write_file` tools
- Verify: streaming mode
- Verify: non-streaming mode
- Verify: sub-agent delegation with the Gemini 3 model

## Affected Files

| File | Change |
|---|---|
| `backend/packages/harness/deerflow/models/patched_openai.py` | Extend or add Gemini 3 adapter |
| `backend/packages/harness/deerflow/models/assistant_payload_replay.py` | Possible: new restorer if new field type |
| `backend/tests/test_patched_openai.py` (**new**) | Test the Gemini 3 adapter |
| `backend/docs/CONFIGURATION.md` | Document Gemini 3 thinking config |
| `config.example.yaml` | Add Gemini 3 model entry |

## Unaffected Components

These layers are provider-agnostic and require **no changes**:

- Middleware chain (all 39 middlewares)
- Sandbox system (E2B, Docker, local)
- Sub-agent executor and registry
- Tool registry and built-in tools
- Memory system
- MCP integration
- Gateway API routers
- IM channels
- Frontend
- Checkpointer and persistence

## References

- `backend/packages/harness/deerflow/models/patched_openai.py` — current Gemini 2.5 adapter
- `backend/packages/harness/deerflow/models/assistant_payload_replay.py` — shared replay matching
- `backend/packages/harness/deerflow/models/patched_deepseek.py` — reference: reasoning_content adapter
- `backend/packages/harness/deerflow/models/patched_mimo.py` — reference: reasoning_content + streaming adapter
- `backend/docs/CONFIGURATION.md` — current Gemini thinking config docs (lines 160-188)
- `contracts/skill_review/` — cross-component contract patterns

---

*Created: 2026-07-25*
