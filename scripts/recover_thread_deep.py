"""Deep recover: walk ALL checkpoints to find messages that were compacted by summarization.

Usage: cd backend && uv run python ../scripts/recover_thread_deep.py <thread_id>
"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
os.environ["DEER_FLOW_AUTH_DISABLED"] = "1"

from deerflow.config.app_config import get_app_config
from deerflow.persistence.engine import init_engine_from_config, close_engine
from deerflow.runtime import get_checkpointer


async def deep_recover(tid: str) -> list:
    """Walk ALL checkpoints in history and collect unique messages from each."""
    config = get_app_config()
    await init_engine_from_config(config.database)
    cp = get_checkpointer()

    seen_ids: set[str] = set()
    all_msgs: list = []
    checkpoint_count = 0
    max_depth = 4000  # safety limit

    # Walk backward through checkpoint history (latest first, then parent chain)
    cfg = {"configurable": {"thread_id": tid}}
    for depth in range(max_depth):
        state = cp.get(cfg)
        if not state:
            break

        vals = state.get("channel_values", {})
        msgs = vals.get("messages", [])

        checkpoint_count += 1
        found_new = 0
        for m in msgs:
            mid = getattr(m, "id", None)
            if mid and mid not in seen_ids:
                seen_ids.add(mid)
                all_msgs.append((depth, m))
                found_new += 1

        if depth % 100 == 0:
            print(f"  depth={depth} checkpoints={checkpoint_count} unique_msgs={len(seen_ids)} found_new={found_new}")

        parent = state.get("parent_config")
        if not parent:
            print(f"  depth={depth}: no parent — end of chain")
            break
        cfg = parent

    await close_engine()

    # Sort by depth (oldest first = highest depth first, since depth=0 is latest)
    all_msgs.sort(key=lambda x: -x[0])
    messages = [m for _, m in all_msgs]

    print(f"\n=== Recovery complete ===")
    print(f"Checkpoints scanned: {checkpoint_count}")
    print(f"Unique messages: {len(messages)}")
    return messages


def to_markdown(msgs: list) -> str:
    lines = ["# Recovered Conversation (Full History)\n"]
    for m in msgs:
        extra = getattr(m, "additional_kwargs", None) or {}
        if extra.get("hide_from_ui"):
            continue
        t = getattr(m, "type", "?")
        content = str(getattr(m, "content", "") or "")
        name = getattr(m, "name", "") or ""

        if not content and t == "tool":
            # Tool call without text result — might have structured output
            content = f"*Tool call: {name}*"

        if t == "human":
            lines.append(f"## User\n\n{content}\n")
        elif t == "ai":
            if content.strip():
                lines.append(f"## Assistant\n\n{content}\n")
        elif t == "tool":
            lines.append(f"### Tool: {name}\n\n{content}\n")
        elif t == "system":
            continue

    return "\n".join(lines)


if __name__ == "__main__":
    tid = sys.argv[1] if len(sys.argv) > 1 else "dac9fba5-e5d7-4033-b30a-c400b181f4c5"
    print(f"Deep recovering thread: {tid}")
    msgs = asyncio.run(deep_recover(tid))

    if not msgs:
        print("No messages found")
        sys.exit(1)

    md = to_markdown(msgs)
    out_dir = Path(__file__).resolve().parents[1] / "recover"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f"{tid[:12]}-full.md"
    out.write_text(md, encoding="utf-8")
    print(f"Saved to {out}")
