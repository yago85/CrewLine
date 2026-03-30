# CrewLine — Instructions for AI Assistants

> This file is named `AGENTS.md` — a provider-agnostic convention for AI assistant instructions.
> It is read automatically by agents working on target projects (alongside `CLAUDE.md` for Claude-specific tools).

This directory contains a **universal agentic environment**. External AI agents (CrewAI)
work on top of projects in the `projects/` folder. This is not a regular project — it's an "agent factory".

## Structure — do not change without discussion

```
config/agents.yaml   ← agent roles (add here, not in code)
config/tasks.yaml    ← workflow stages + explicit dependencies (context:)
tools/               ← sandboxed file tools for agents
projects/            ← user's working projects
main.py              ← single entry point, CLI
```

## Rules for working in this directory

- **New agent** — add entry to `config/agents.yaml`. Don't touch code.
- **New stage** — add to `config/tasks.yaml` with explicit `context:` field.
- **New project** — create folder in `projects/` with `README.md`.
- **Change provider** — edit `MODEL_SMART` and `MODEL_LITE` in `.env`. Don't touch agents.yaml.

## The `context` field in tasks.yaml is critical

Each task must explicitly state which tasks it depends on:

```yaml
review_code:
  context: [implement_solution] # reviewer sees concrete code, not an abstraction
```

Don't use `context: []` instead of omitting the field — they mean different things.

## Running

```bash
python main.py                                                               # interactive wizard
python main.py --project ./projects/<name> --goal "<task description>"
python main.py --plan plan.md --project ./projects/<name> --goal "<task>"
python main.py --dry-run --project ./projects/<name> --goal "<task>"
python main.py --human-review --project ./projects/<name> --goal "<task>"   # pause after every task
python main.py --no-human-review --project ./projects/<name> --goal "<task>" # fully autonomous
python main.py --list-agents
python main.py --list-tasks
```

## Interactive wizard

Running `python main.py` without `--project`/`--goal` launches an interactive setup
that prompts for: project path, goal, plan file, tasks, human review mode, memory.

## human_input in tasks.yaml

Tasks can declare `human_input: true` to pause by default (without `--human-review`).
`--human-review` forces pause for ALL tasks; `--no-human-review` disables ALL pauses.

## Security

File tools run in a sandbox — all operations are restricted to the project directory.
`set_project_root()` is called automatically in `build_crew()`.
Agents cannot read/write files outside the `--project` path.

## Dependencies

CrewAI 1.12+, Python 3.11+, at least one provider key in `.env`
(e.g. `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`).
For local/free setup: Ollama — set `OLLAMA_BASE_URL=http://127.0.0.1:11434` (not `localhost` — macOS IPv6 quirk).
Do not commit `.env`.
