"""Recover full thread conversation from checkpoints and save as Markdown.

Usage: cd backend && uv run python ../scripts/recover_thread.py <thread_id>
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


async def recover(tid: str) -> list:
    config = get_app_config()
    await init_engine_from_config(config.database)
    cp = get_checkpointer()
    state = cp.get({"configurable": {"thread_id": tid}})
    await close_engine()
    msgs = state.get("channel_values", {}).get("messages", [])
    return msgs


def to_markdown(msgs: list) -> str:
    lines = ["# Recovered Conversation\n"]
    for m in msgs:
        extra = getattr(m, "additional_kwargs", None) or {}
        if extra.get("hide_from_ui"):
            continue
        t = getattr(m, "type", "?")
        content = str(getattr(m, "content", "") or "")
        name = getattr(m, "name", "") or ""

        if t == "human":
            lines.append(f"## User\n\n{content}\n")
        elif t == "ai":
            lines.append(f"## Assistant\n\n{content}\n")
        elif t == "tool":
            lines.append(f"### Tool: {name}\n\n{content}\n")
        elif t == "system":
            # Skip system messages
            continue
    return "\n".join(lines)


if __name__ == "__main__":
    tid = sys.argv[1] if len(sys.argv) > 1 else "dac9fba5-e5d7-4033-b30a-c400b181f4c5"
    msgs = asyncio.run(recover(tid))
    if not msgs:
        print("No messages found")
        sys.exit(1)
    print(f"Recovered {len(msgs)} messages")
    md = to_markdown(msgs)
    out_dir = Path(__file__).resolve().parents[1] / "recover"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f"{tid[:12]}.md"
    out.write_text(md, encoding="utf-8")
    print(f"Saved to {out}")
