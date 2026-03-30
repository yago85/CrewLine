#!/usr/bin/env python3
"""
CrewLine — universal entry point for agentic development.

Usage:
  python main.py --project ./projects/my-app --goal "Add authentication"
  python main.py --plan plan.md --project ./projects/my-app --goal "Implement per plan"
  python main.py --dry-run --project ./projects/my-app --goal "Test"
  python main.py --list-agents
  python main.py --list-tasks
"""

import argparse
import os
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

CONFIG_DIR = Path(__file__).parent / "config"
AGENTS_CONFIG = CONFIG_DIR / "agents.yaml"
TASKS_CONFIG = CONFIG_DIR / "tasks.yaml"


def load_yaml(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_project_context(project_path: Path) -> str:
    """Collects project context: directory tree + key files."""
    if not project_path.exists():
        return f"Project not found: {project_path}"

    context_parts = [f"Project path: {project_path.absolute()}"]

    from tools.file_tools import list_directory
    structure = list_directory.run(".")
    context_parts.append(f"\nProject structure:\n{structure}")

    key_files = ["README.md", "README.rst", "pyproject.toml", "package.json",
                 "requirements.txt", "AGENTS.md", "CLAUDE.md", ".cursorrules"]
    for filename in key_files:
        filepath = project_path / filename
        if filepath.exists():
            content = filepath.read_text(encoding="utf-8", errors="ignore")
            if len(content) > 2000:
                content = content[:2000] + "\n... [truncated]"
            context_parts.append(f"\n=== {filename} ===\n{content}")

    return "\n".join(context_parts)


def _ensure_provider_prefix(model: str) -> str:
    """Adds provider/ prefix if missing. Defaults to anthropic/."""
    if "/" in model:
        return model
    return f"anthropic/{model}"


def _get_embedder() -> dict | None:
    """
    Auto-selects an embedder for CrewAI memory based on available API keys.
    Priority: MEMORY_PROVIDER env > OpenAI > Google > Cohere > Ollama > None.
    Returns embedder config dict, or None if no provider is available.
    """
    provider = os.getenv("MEMORY_PROVIDER", "").lower()

    # Explicit override via .env
    if provider == "openai" or (not provider and os.getenv("OPENAI_API_KEY")):
        return {"provider": "openai", "config": {"model": os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")}}

    if provider == "google" or (not provider and os.getenv("GOOGLE_API_KEY")):
        return {"provider": "google", "config": {
            "api_key": os.getenv("GOOGLE_API_KEY"),
            "model_name": os.getenv("GOOGLE_EMBEDDING_MODEL", "models/text-embedding-004"),
        }}

    if provider == "cohere" or (not provider and os.getenv("COHERE_API_KEY")):
        return {"provider": "cohere", "config": {
            "api_key": os.getenv("COHERE_API_KEY"),
            "model_name": os.getenv("COHERE_EMBEDDING_MODEL", "embed-english-v3.0"),
        }}

    if provider == "ollama" or not provider:
        # Ollama is local — always try it last.
        # IMPORTANT: use 127.0.0.1, not localhost — on macOS `localhost` resolves
        # to IPv6 ::1 first, but Ollama listens only on IPv4 127.0.0.1 → 503.
        ollama_base = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        # Replace localhost with 127.0.0.1 even if set explicitly in .env
        ollama_base = ollama_base.replace("//localhost", "//127.0.0.1")
        return {"provider": "ollama", "config": {
            "model_name": os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text"),
            "url": f"{ollama_base.rstrip('/')}/api/embeddings",
        }}

    return None


def _build_memory(project_name: str) -> "object | None":
    """
    Creates a Memory instance with the configured provider's LLM and embedder.
    No OpenAI required — works with Anthropic, Google, Cohere, Ollama or any
    LiteLLM-compatible provider.
    """
    embedder = _get_embedder()
    if embedder is None:
        return None

    try:
        from crewai.memory.unified_memory import Memory
    except ImportError:
        return None

    # Use MEMORY_LLM → MODEL_SMART → DEFAULT_LLM for memory analysis/summarization.
    # Intentionally skip MODEL_LITE — free/cheap models often return 503.
    default_llm = os.getenv("DEFAULT_LLM", "claude-sonnet-4-6")
    raw_memory_llm = (
        os.getenv("MEMORY_LLM")
        or os.getenv("MODEL_SMART", default_llm)
    )
    memory_llm = _ensure_provider_prefix(raw_memory_llm)

    # For Ollama models litellm needs explicit base_url — OLLAMA_API_BASE is not read.
    # Use 127.0.0.1: macOS resolves `localhost` → IPv6 ::1 first, Ollama listens IPv4 only → 503.
    ollama_base = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").replace("//localhost", "//127.0.0.1")
    if memory_llm.startswith("ollama/") or memory_llm.startswith("ollama_chat/"):
        from crewai import LLM
        llm_arg = LLM(model=memory_llm, base_url=ollama_base)
    else:
        llm_arg = memory_llm  # non-Ollama: pass as string

    return Memory(
        llm=llm_arg,
        embedder=embedder,
        root_scope=project_name,
    )


def build_crew(agents_config: dict, tasks_config: dict, selected_tasks: list[str],
               project_path: Path, goal: str, plan: str = "",
               memory: bool = False, human_review: bool | None = None):
    """Builds a Crew from YAML configs."""
    from crewai import Agent, Task, Crew, Process
    from tools import (
        read_file, write_file, list_directory, search_in_files,
        set_project_root,
    )

    # Sandbox — all file operations restricted to this directory
    set_project_root(project_path)

    project_context = get_project_context(project_path)
    file_tools = [read_file, write_file, list_directory, search_in_files]

    default_llm = os.getenv("DEFAULT_LLM", "claude-sonnet-4-6")
    model_tiers = {
        "smart": os.getenv("MODEL_SMART", default_llm),
        "lite": os.getenv("MODEL_LITE", default_llm),
    }

    # For Ollama models, litellm needs explicit base_url (OLLAMA_API_BASE is not read).
    # Use 127.0.0.1 — on macOS `localhost` resolves to IPv6 ::1 first → 503.
    ollama_base = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").replace("//localhost", "//127.0.0.1")

    def _make_llm(model_str: str):
        """Return a CrewAI LLM instance, injecting base_url for Ollama models."""
        from crewai import LLM
        if model_str.startswith("ollama/") or model_str.startswith("ollama_chat/"):
            return LLM(model=model_str, base_url=ollama_base)
        return model_str  # non-Ollama: pass as string, CrewAI resolves via litellm

    agents: dict[str, Agent] = {}
    for agent_key, agent_cfg in agents_config.items():
        # Priority: MODEL_<AGENT> env > model (yaml) > model_tier > DEFAULT_LLM
        env_model = os.getenv(f"MODEL_{agent_key.upper()}")
        raw_model = env_model or agent_cfg.get("model") or model_tiers.get(
            agent_cfg.get("model_tier", ""), default_llm
        )
        agent_model = _ensure_provider_prefix(raw_model)
        agents[agent_key] = Agent(
            role=agent_cfg["role"],
            goal=agent_cfg["goal"],
            backstory=agent_cfg["backstory"],
            verbose=agent_cfg.get("verbose", True),
            allow_delegation=agent_cfg.get("allow_delegation", False),
            max_iter=agent_cfg.get("max_iter", 5),
            tools=file_tools,
            llm=_make_llm(agent_model),
        )

    # Template variables available in tasks.yaml
    template_vars = {
        "goal": goal,
        "project_context": project_context,
        "plan": plan,
    }

    # First pass: create Task objects without context
    built_tasks: dict[str, Task] = {}

    for task_key in selected_tasks:
        if task_key not in tasks_config:
            print(f"[WARN] Task '{task_key}' not found in tasks.yaml, skipping")
            continue
        task_cfg = tasks_config[task_key]
        agent_key = task_cfg["agent"]

        if agent_key not in agents:
            print(f"[WARN] Agent '{agent_key}' for task '{task_key}' not found, skipping")
            continue

        description = task_cfg["description"].format(**template_vars)
        expected_output = task_cfg["expected_output"].format(**template_vars)

        # human_review=True  → force on for all tasks
        # human_review=False → force off for all tasks
        # human_review=None  → respect per-task human_input in tasks.yaml
        if human_review is True:
            task_human_input = True
        elif human_review is False:
            task_human_input = False
        else:
            task_human_input = task_cfg.get("human_input", False)

        built_tasks[task_key] = Task(
            description=description,
            expected_output=expected_output,
            agent=agents[agent_key],
            async_execution=task_cfg.get("async_execution", False),
            human_input=task_human_input,
        )

    # Second pass: wire explicit dependencies from context field
    for task_key in selected_tasks:
        if task_key not in built_tasks:
            continue
        task_cfg = tasks_config[task_key]
        dep_keys = task_cfg.get("context", [])
        deps = [built_tasks[k] for k in dep_keys if k in built_tasks]
        if deps:
            built_tasks[task_key].context = deps

    tasks = [built_tasks[k] for k in selected_tasks if k in built_tasks]

    # Build a provider-agnostic Memory instance.
    # Memory.llm = analysis/summarization LLM (configurable via MEMORY_LLM env).
    # Memory.embedder = vector store embedder (auto-detected: OpenAI/Google/Cohere/Ollama).
    # No OpenAI required — any LiteLLM-compatible provider works.
    memory_obj = None
    if memory:
        memory_obj = _build_memory(project_path.name)
        if memory_obj is None:
            print("[WARN] Memory disabled: no embedder provider detected.")
            print("[WARN] Configure MEMORY_PROVIDER or install Ollama with nomic-embed-text.")

    crew = Crew(
        agents=list(agents.values()),
        tasks=tasks,
        process=Process.sequential,
        verbose=True,
        memory=memory_obj if memory_obj is not None else False,
    )

    return crew


def dry_run(agents_config: dict, tasks_config: dict, selected_tasks: list[str],
            plan_path: Path | None = None, human_review: bool | None = None):
    """Shows execution plan without calling any API."""
    default_llm = os.getenv("DEFAULT_LLM", "claude-sonnet-4-6")
    model_tiers = {
        "smart": os.getenv("MODEL_SMART", default_llm),
        "lite": os.getenv("MODEL_LITE", default_llm),
    }

    print("\n--- DRY RUN (no API calls) ---\n")

    if plan_path:
        print(f"Plan file: {plan_path}")
    else:
        print("Mode: agents build the plan (architect)")

    print("\nAgents:")
    used_agents = set()
    for task_key in selected_tasks:
        if task_key in tasks_config:
            used_agents.add(tasks_config[task_key]["agent"])

    for agent_key in used_agents:
        if agent_key not in agents_config:
            print(f"  [!] {agent_key} — NOT FOUND in agents.yaml")
            continue
        cfg = agents_config[agent_key]
        env_model = os.getenv(f"MODEL_{agent_key.upper()}")
        raw_model = env_model or cfg.get("model") or model_tiers.get(
            cfg.get("model_tier", ""), default_llm
        )
        model = _ensure_provider_prefix(raw_model)
        print(f"  {agent_key:25} model={model}  max_iter={cfg.get('max_iter', 5)}")

    print("\nTasks (execution order):")
    for i, task_key in enumerate(selected_tasks, 1):
        if task_key not in tasks_config:
            print(f"  {i}. [!] {task_key} — NOT FOUND in tasks.yaml")
            continue
        cfg = tasks_config[task_key]
        deps = cfg.get("context", [])
        deps_str = f" (depends on: {', '.join(deps)})" if deps else ""
        if human_review is True:
            hi_marker = " [REVIEW]"
        elif human_review is False:
            hi_marker = ""
        else:
            hi_marker = " [REVIEW]" if cfg.get("human_input", False) else ""
        print(f"  {i}. {task_key:30} agent: {cfg['agent']}{deps_str}{hi_marker}")

    print("\n--- End DRY RUN ---")


def interactive_setup(tasks_config: dict) -> dict:
    """Interactive wizard when no --project/--goal provided."""
    print("\n╭─ CrewLine — Interactive Setup ─────────────────────────╮")
    print("│  Press Enter to accept [default value]                  │")
    print("╰─────────────────────────────────────────────────────────╯\n")

    # Project path
    while True:
        project_raw = input("Project path [./projects/example_project]: ").strip()
        project_path = Path(project_raw) if project_raw else Path("./projects/example_project")
        if project_path.exists():
            break
        print(f"  ✗ Not found: {project_path}. Try again.")

    # Goal
    while True:
        goal = input("Goal: ").strip()
        if goal:
            break
        print("  ✗ Goal cannot be empty.")

    # Plan file (optional)
    plan_raw = input("Plan file (optional, press Enter to skip): ").strip()
    plan_path = Path(plan_raw) if plan_raw else None
    if plan_path and not plan_path.exists():
        print(f"  ✗ Plan file not found: {plan_path}. Ignoring.")
        plan_path = None

    # Tasks
    default_tasks = "execute_plan,review_code,fix_issues,final_review" if plan_path else "analyze_requirements,implement_solution,review_code,fix_issues,final_review"
    print(f"\n  Available tasks (enter names separated by comma):")
    for t in tasks_config.keys():
        print(f"    {t}")
    while True:
        tasks_raw = input(f"Tasks [{default_tasks}]: ").strip()
        selected_tasks = [t.strip() for t in tasks_raw.split(",")] if tasks_raw else default_tasks.split(",")
        invalid = [t for t in selected_tasks if t not in tasks_config]
        if not invalid:
            break
        print(f"  ✗ Unknown task(s): {', '.join(invalid)}. Pick names from the list above.")

    # Human review
    print("\n  Human review mode:")
    print("   y   — pause after EVERY task")
    print("   n   — fully autonomous (no pauses)")
    print("  [Enter] — use per-task settings from tasks.yaml")
    hr_raw = input("Human review [per-task]: ").strip().lower()
    if hr_raw == "y":
        human_review = True
    elif hr_raw == "n":
        human_review = False
    else:
        human_review = None

    # Memory
    embedder = _get_embedder()
    default_llm = os.getenv("DEFAULT_LLM", "claude-sonnet-4-6")
    raw_memory_llm = os.getenv("MEMORY_LLM") or os.getenv("MODEL_SMART", default_llm)
    memory_llm = _ensure_provider_prefix(raw_memory_llm)
    if embedder is not None:
        provider_name = embedder.get("provider", "unknown")
        print(f"\nMemory available (embedder: {provider_name}, LLM: {memory_llm})")
        mem_raw = input("Enable cross-session memory? [y/N]: ").strip().lower()
        memory = mem_raw == "y"
    else:
        print("\nMemory unavailable: no embedder provider detected.")
        print("  Configure MEMORY_PROVIDER in .env or install Ollama with nomic-embed-text.")
        memory = False

    print()
    return {
        "project": project_path,
        "goal": goal,
        "plan": plan_path,
        "tasks": selected_tasks,
        "human_review": human_review,
        "memory": memory,
    }


def list_agents():
    agents = load_yaml(AGENTS_CONFIG)
    print("\nAvailable agents:")
    for key, cfg in agents.items():
        print(f"  {key:25} — {cfg['role']}")


def list_tasks():
    tasks = load_yaml(TASKS_CONFIG)
    print("\nAvailable tasks:")
    for key, cfg in tasks.items():
        deps = cfg.get("context", [])
        deps_str = f" <- [{', '.join(deps)}]" if deps else ""
        print(f"  {key:30} — agent: {cfg['agent']}{deps_str}")


def main():
    parser = argparse.ArgumentParser(
        description="CrewLine — universal entry point for agentic development",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full autonomous cycle (default): analyze → implement → review → fix → verify
  python main.py -p ./projects/my-app -g "Add OAuth authentication"

  # Your plan — agents implement, review, fix and verify
  python main.py --plan plan.md -p ./projects/my-app -g "Implement JWT auth"

  # Quick: implement only, no review/fix loop
  python main.py -p ./projects/app -g "Goal" -t analyze_requirements,implement_solution

  # Check what will run (no API calls)
  python main.py --dry-run -p ./projects/my-app -g "Test"
        """
    )
    parser.add_argument("--project", "-p", type=Path, help="Path to project directory")
    parser.add_argument("--goal", "-g", type=str, help="Goal / task for the agent crew")
    parser.add_argument(
        "--tasks", "-t", type=str,
        default="analyze_requirements,implement_solution,review_code,fix_issues,final_review",
        help="Comma-separated list of tasks (default: full autonomous cycle)"
    )
    parser.add_argument(
        "--plan", type=Path, default=None,
        help="Path to plan file with architecture/logic (skips architect agent)"
    )
    parser.add_argument("--list-agents", action="store_true", help="Show available agents")
    parser.add_argument("--list-tasks", action="store_true", help="Show available tasks")
    parser.add_argument(
        "--memory", action="store_true", default=False,
        help="Enable agent memory (short-term + long-term via ChromaDB)"
    )
    parser.add_argument(
        "--human-review", dest="human_review",
        action="store_true", default=None,
        help="Force human approval after every task (overrides tasks.yaml)"
    )
    parser.add_argument(
        "--no-human-review", dest="human_review",
        action="store_false",
        help="Disable human approval for all tasks (overrides tasks.yaml)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", default=False,
        help="Show execution plan without calling API (debug)"
    )

    args = parser.parse_args()

    if args.list_agents:
        list_agents()
        return

    if args.list_tasks:
        list_tasks()
        return

    agents_config = load_yaml(AGENTS_CONFIG)
    tasks_config = load_yaml(TASKS_CONFIG)

    # No --project/--goal → launch interactive wizard
    if not args.project or not args.goal:
        wizard = interactive_setup(tasks_config)
        args.project = wizard["project"]
        args.goal = wizard["goal"]
        args.plan = wizard["plan"]
        args.memory = wizard["memory"]
        args.human_review = wizard["human_review"]
        selected_tasks = wizard["tasks"]
        plan_content = args.plan.read_text(encoding="utf-8") if args.plan else ""
    else:
        # Read plan file if provided
        plan_content = ""
        if args.plan:
            if not args.plan.exists():
                print(f"Plan file not found: {args.plan}")
                sys.exit(1)
            plan_content = args.plan.read_text(encoding="utf-8")

        # If --plan is set and --tasks not explicitly overridden,
        # automatically switch to execute_plan → review → fix → final_review
        tasks_explicitly_set = "--tasks" in sys.argv or "-t" in sys.argv
        if plan_content and not tasks_explicitly_set:
            selected_tasks = ["execute_plan", "review_code", "fix_issues", "final_review"]
        else:
            selected_tasks = [t.strip() for t in args.tasks.split(",")]

    if args.dry_run:
        dry_run(agents_config, tasks_config, selected_tasks, plan_path=args.plan,
                human_review=args.human_review)
        return

    api_keys = ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY"]
    if not any(os.getenv(k) for k in api_keys):
        print("No API key found in .env")
        print("Set at least one of: " + ", ".join(api_keys))
        print("Create .env from .env.example and add your key")
        sys.exit(1)

    print(f"\nStarting CrewLine")
    print(f"  Project: {args.project.absolute()}")
    print(f"  Goal:    {args.goal}")
    if plan_content:
        print(f"  Plan:    {args.plan} ({len(plan_content)} chars)")
    print(f"  Tasks:   {', '.join(selected_tasks)}")
    print(f"  Memory:  {'on' if args.memory else 'off (use --memory to enable)'}")
    hrv = args.human_review
    if hrv is True:
        hr_label = "on (all tasks)"
    elif hrv is False:
        hr_label = "off (forced)"
    else:
        hr_label = "per-task (tasks.yaml)"
    print(f"  Review:  {hr_label}")
    print()

    try:
        crew = build_crew(
            agents_config=agents_config,
            tasks_config=tasks_config,
            selected_tasks=selected_tasks,
            project_path=args.project,
            goal=args.goal,
            plan=plan_content,
            memory=args.memory,
            human_review=args.human_review,
        )
        result = crew.kickoff()
    except KeyboardInterrupt:
        print("\nStopped by user")
        sys.exit(130)
    except Exception as e:
        print(f"\nError: {e}")
        print("Check: API keys, models in agents.yaml, network connectivity")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("RESULT:")
    print("=" * 60)
    print(result)


if __name__ == "__main__":
    main()
