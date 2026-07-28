"""Replay recovered messages using DbRunEventStore.put() for correct serialization.

Usage: cd backend && uv run python ../scripts/replay_events.py <thread_id>
"""
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
os.environ["DEER_FLOW_AUTH_DISABLED"] = "1"

from deerflow.config.app_config import get_app_config
from deerflow.persistence.engine import init_engine_from_config, close_engine
from deerflow.runtime import get_checkpointer
from deerflow.runtime.events.store.db import DbRunEventStore
from deerflow.persistence.engine import get_session_factory


async def replay(tid: str) -> int:
    config = get_app_config()
    await init_engine_from_config(config.database)
    cp = get_checkpointer()

    # Collect unique messages
    seen_ids = set()
    all_msgs = []
    for h in cp.list({"configurable": {"thread_id": tid}}, limit=5000, before=None):
        for m in h.checkpoint.get("channel_values", {}).get("messages", []):
            mid = getattr(m, "id", None)
            extra = getattr(m, "additional_kwargs", {}) or {}
            if mid and mid not in seen_ids and not extra.get("hide_from_ui"):
                seen_ids.add(mid)
                all_msgs.append(m)

    print(f"Found {len(all_msgs)} messages")

    # Use DbRunEventStore.put() for correct serialization
    store = DbRunEventStore(get_session_factory())

    count = 0
    for m in all_msgs:
        t = getattr(m, "type", "?")
        content = {
            "type": t,
            "content": getattr(m, "content", ""),
            "id": getattr(m, "id", None),
        }
        name = getattr(m, "name", None)
        if name:
            content["name"] = name
        extra = getattr(m, "additional_kwargs", {}) or {}
        if extra:
            content["additional_kwargs"] = extra

        # Skip system messages
        if t == "system":
            continue

        try:
            await store.put(
                thread_id=tid,
                run_id="recovery",
                event_type=f"{t}_message",
                category="message",
                content=content,
            )
            count += 1
        except Exception as e:
            # Skip duplicates
            pass

    await close_engine()
    return count


if __name__ == "__main__":
    tid = sys.argv[1] if len(sys.argv) > 1 else "dac9fba5-e5d7-4033-b30a-c400b181f4c5"
    # First clear old recovery events
    print("Clearing old events...")
    import sqlite3
    db_path = Path(__file__).resolve().parents[1] / "backend" / ".deer-flow" / "data" / "deerflow.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("DELETE FROM run_events WHERE run_id = 'recovery'")
    conn.commit()
    conn.close()
    print("Cleared.")

    count = asyncio.run(replay(tid))
    print(f"\nDone! {count} events written. Restart the Gateway.")
