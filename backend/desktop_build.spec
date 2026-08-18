# PyInstaller spec for the DeerFlow desktop sidecar.
#
# Build with (from repo root, backend venv active):
#   python -m PyInstaller backend/desktop_build.spec
#
# Produces a single-folder bundle in dist/deerflow-desktop/ containing the
# sidecar executable. The Tauri build then copies this folder into
# desktop/src-tauri/binaries/ next to the Next.js standalone output.
#
# Hidden imports are explicit: the harness loads middleware modules and
# subagent machinery dynamically, so PyInstaller cannot discover them.
# The `app` package (FastAPI host) is imported by string at runtime
# (uvicorn "app.gateway.app:app"), so it must be collected explicitly too.

from pathlib import Path

REPO_ROOT = Path(SPEC).parent.parent  # backend/.. -> repo root
BACKEND_ROOT = REPO_ROOT / "backend"

block_cipher = None

datas = [
    # Default skills (SKILL.md + references) shipped read-only inside the bundle.
    (str(REPO_ROOT / "skills" / "public"), "skills/public"),
    # Alembic migration scripts are loaded from disk at startup
    # (init_engine_from_config -> alembic Config.script_location); collect the
    # whole migrations directory as data.
    (str(BACKEND_ROOT / "packages" / "harness" / "deerflow" / "persistence" / "migrations"),
     "deerflow/persistence/migrations"),
    # Memory backends are discovered by walking the backends/ directory on
    # disk (_scan_backends -> iterdir + __init__.py check). PyInstaller packs
    # modules into the archive, so the real directory tree must also ship as
    # data for the scan to find the deermem backend.
    (str(BACKEND_ROOT / "packages" / "harness" / "deerflow" / "agents" / "memory" / "backends"),
     "deerflow/agents/memory/backends"),
]

hiddenimports = [
    # The FastAPI host package (uvicorn imports it by string at runtime).
    "app",
    "app.gateway",
    "app.gateway.app",
    "app.gateway.desktop_entry",
    "app.channels",
    "app.scheduler",
    # Harness middleware package (loaded dynamically by the agent factory).
    "deerflow.agents.middlewares",
    "deerflow.agents.middlewares.deep_research_middleware",
    "deerflow.agents.middlewares.system_design_middleware",
    "deerflow.agents.middlewares.startup_sketch_middleware",
    "deerflow.agents.middlewares.business_requirement_middleware",
    "deerflow.agents.middlewares.product_requirements_middleware",
    "deerflow.agents.middlewares.software_requirements_middleware",
    "deerflow.agents.middlewares.requirements_pipeline_middleware",
    "deerflow.agents.middlewares.planting_research_middleware",
    "deerflow.agents.middlewares.skill_activation_middleware",
    "deerflow.agents.middlewares.skill_tool_policy_middleware",
    "deerflow.agents.middlewares.skill_evolution_middleware",
    "deerflow.agents.middlewares.project_state_middleware",
    "deerflow.agents.middlewares.durable_context_middleware",
    "deerflow.agents.middlewares.dynamic_context_middleware",
    "deerflow.agents.middlewares.summarization_middleware",
    "deerflow.agents.middlewares.token_budget_middleware",
    "deerflow.agents.middlewares.token_usage_middleware",
    "deerflow.agents.middlewares.tool_output_budget_middleware",
    "deerflow.agents.middlewares.tool_progress_middleware",
    "deerflow.agents.middlewares.tool_error_handling_middleware",
    "deerflow.agents.middlewares.tool_result_sanitization_middleware",
    "deerflow.agents.middlewares.deferred_tool_filter_middleware",
    "deerflow.agents.middlewares.dangling_tool_call_middleware",
    "deerflow.agents.middlewares.loop_detection_middleware",
    "deerflow.agents.middlewares.llm_error_handling_middleware",
    "deerflow.agents.middlewares.safety_finish_reason_middleware",
    "deerflow.agents.middlewares.model_length_finish_reason_middleware",
    "deerflow.agents.middlewares.terminal_response_middleware",
    "deerflow.agents.middlewares.clarification_middleware",
    "deerflow.agents.middlewares.subagent_limit_middleware",
    "deerflow.agents.middlewares.sandbox_audit_middleware",
    "deerflow.agents.middlewares.read_before_write_middleware",
    "deerflow.agents.middlewares.todo_middleware",
    "deerflow.agents.middlewares.title_middleware",
    "deerflow.agents.middlewares.thread_data_middleware",
    "deerflow.agents.middlewares.uploads_middleware",
    "deerflow.agents.middlewares.view_image_middleware",
    "deerflow.agents.middlewares.vision_bridge_middleware",
    "deerflow.agents.middlewares.system_message_coalescing_middleware",
    "deerflow.agents.middlewares.mcp_routing_middleware",
    "deerflow.agents.middlewares.input_sanitization_middleware",
    "deerflow.agents.middlewares.metacognition_middleware",
    "deerflow.agents.middlewares.planner_middleware",
    "deerflow.agents.middlewares.emoji_gate_middleware",
    "deerflow.agents.middlewares.pushback_middleware",
    "deerflow.agents.middlewares.token_forensics_middleware",
    # Subagent executor + registry (dynamic instantiation).
    "deerflow.subagents.executor",
    "deerflow.subagents.registry",
    "deerflow.subagents.builtins.general_purpose",
    "deerflow.subagents.builtins.bash_agent",
    # Persistence + migrations (SQLAlchemy models are discovered at runtime).
    "deerflow.persistence",
    "deerflow.persistence.user",
    "deerflow.persistence.thread_meta",
    "deerflow.persistence.run",
    "deerflow.persistence.models",
    "deerflow.persistence.agents",
    "deerflow.persistence.schedule_tasks",
    "deerflow.persistence.schedule_task_runs",
    "deerflow.persistence.feedback",
    "deerflow.persistence.channel_connections",
    # Memory backends are discovered by folder name at runtime (drop-in
    # contract); PyInstaller cannot see the dynamic scan, so collect the
    # default DeerMem backend explicitly.
    "deerflow.agents.memory.backends",
    "deerflow.agents.memory.backends.deermem",
    "deerflow.agents.memory.backends.deermem.deer_mem",
    "deerflow.agents.memory.backends.deermem.deermem.config",
    "deerflow.agents.memory.backends.deermem.deermem.core.llm",
    "deerflow.agents.memory.backends.deermem.deermem.core.message_processing",
    "deerflow.agents.memory.backends.deermem.deermem.core.paths",
    "deerflow.agents.memory.backends.deermem.deermem.core.prompt",
    "deerflow.agents.memory.backends.deermem.deermem.core.queue",
    "deerflow.agents.memory.backends.deermem.deermem.core.storage",
    "deerflow.agents.memory.backends.deermem.deermem.core.updater",
    # Community tools loaded by name.
    "deerflow.community.web_search",
    "deerflow.community.web_fetch",
    "deerflow.community.web_capture",
    "deerflow.community.image_search",
]

a = Analysis(
    [str(BACKEND_ROOT / "app" / "gateway" / "desktop_entry.py")],
    pathex=[str(BACKEND_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="deerflow-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="deerflow-desktop",
)
