# CrewLine

YAML-configured AI dev team: define agents and tasks in config, point at any project, get code + review + tests.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![CrewAI](https://img.shields.io/badge/CrewAI-1.12+-green.svg)](https://github.com/crewAIInc/crewAI)

**[Русская версия ниже / Russian version below](#русская-версия)**

## Why CrewLine?

- **No Python needed for config** — new agent = a few lines in YAML. Core logic lives in `main.py`.
- **Any project** — point `--project` at any codebase and go.
- **Two modes** — agents build the plan, or you provide your own.
- **Sandboxed** — agents can only touch files inside the project directory.
- **Budget-friendly** — expensive models for thinking, cheap models for mechanical tasks.
- **Dry-run** — preview the execution plan without spending a cent.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Create .env with your API key
cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env

# 3a. Run interactively (no arguments needed — wizard will ask everything)
python main.py

# 3b. Or pass everything via flags
python main.py --project ./projects/example_project --goal "Add JWT authentication"

# 4. See available agents and tasks
python main.py --list-agents
python main.py --list-tasks
```

## Architecture

```
CrewLine/
├── main.py              # Single entry point (CLI)
├── AGENTS.md            # Instructions for AI assistants working on CrewLine itself
├── config/
│   ├── agents.yaml      # Agent roles (edit here)
│   └── tasks.yaml       # Workflow stages (edit here)
├── tools/
│   └── file_tools.py    # Sandboxed file tools for agents
├── projects/            # Your projects (each in its own folder)
│   └── example_project/
└── .env                 # Your API keys (don't commit!)
```

> **Tip:** Add `AGENTS.md` (or `CLAUDE.md`) to your target project — agents read it automatically
> as extra context. Describe architecture decisions, conventions, things agents must know.

## Two Modes of Operation

### Mode 1 — Agents build the plan (default)

The architect analyzes the project, creates a plan, the developer implements it.

```bash
python main.py -p ./projects/app -g "Add OAuth authentication"
```

### Mode 2 — You provide the plan

You describe the architecture and logic in a file, agents implement it directly.

```bash
python main.py --plan plan.md -p ./projects/app -g "Implement JWT auth"
```

See [GUIDE.md](GUIDE.md) for detailed instructions on writing plan files.

## CLI Options

```
--project / -p   Path to project directory
--goal    / -g   Goal / task for the agent crew
--tasks   / -t   Comma-separated task list (default: analyze,implement,review)
--plan           Path to plan file with architecture/logic (skips architect)
--memory         Enable agent memory across sessions (ChromaDB)
--human-review   Pause for human approval after every task (overrides tasks.yaml)
--no-human-review  Skip all human approval pauses (overrides tasks.yaml)
--dry-run        Show execution plan without calling API (debug)
```

## Available Tasks

| Task                   | Agent       | What it does                       |
| ---------------------- | ----------- | ---------------------------------- |
| `analyze_requirements` | Architect   | Inspects project, creates plan     |
| `implement_solution`   | Senior Dev  | Writes code per architect's plan   |
| `execute_plan`         | Senior Dev  | Writes code per your plan (--plan) |
| `review_code`          | Reviewer    | Checks quality, security           |
| `write_tests`          | QA Engineer | Writes pytest tests                |
| `write_documentation`  | Tech Writer | Documentation and README           |
| `validate_environment` | QA Engineer | Checks imports vs requirements.txt |

## Examples

```bash
# Agents build plan and implement (default)
python main.py -p ./projects/my-app -g "Add OAuth via Google"

# Interactive wizard — no flags needed
python main.py

# Your plan — agents implement directly
python main.py --plan plan.md -p ./projects/my-app -g "Implement JWT auth"

# Your plan + full cycle
python main.py --plan plan.md -p ./projects/app -g "Goal" \
  -t execute_plan,review_code,write_tests,validate_environment

# Check what will run (no API calls)
python main.py --dry-run -p ./projects/my-app -g "Test"

# Full development cycle
python main.py -p ./projects/my-app -g "Add OAuth via Google" \
  --tasks analyze_requirements,implement_solution,review_code,write_tests,write_documentation

# With memory — agents remember previous sessions
python main.py -p ./projects/my-app -g "Refactor users module" --memory

# Risky change — pause for human approval after every step
python main.py -p ./projects/my-app -g "Migrate database schema" --human-review

# Fully autonomous pipeline (ignore human_input in tasks.yaml)
python main.py -p ./projects/my-app -g "Fix typo in README" --no-human-review

# Review only
python main.py -p ./projects/legacy -g "Check API security" --tasks review_code
```

## Adding a New Agent

Edit `config/agents.yaml`:

```yaml
security_expert:
  role: Security Expert
  goal: Find OWASP Top 10 vulnerabilities and suggest fixes
  backstory: Experienced pentester. Thinks like an attacker, defends like an engineer.
  model_tier: smart
  verbose: true
  allow_delegation: false
  max_iter: 5
```

Then add a task in `config/tasks.yaml` — no code changes needed.

## Models — Switch Provider in `.env`, Not YAML

Agents use **model tiers** (`smart` / `lite`) instead of hardcoded model names.
Switch provider by editing `.env` — `agents.yaml` stays untouched:

```bash
# .env — just change these two lines to switch provider
MODEL_SMART=anthropic/claude-sonnet-4-6
MODEL_LITE=anthropic/claude-haiku-4-5
```

| Tier    | Used by                                                       | Purpose                                  |
| ------- | ------------------------------------------------------------- | ---------------------------------------- |
| `smart` | architect, senior_developer                                   | Complex tasks: planning, code generation |
| `lite`  | code_reviewer, qa_engineer, technical_writer, devops_engineer | Mechanical tasks: review, tests, docs    |

### Provider examples (copy to `.env`)

```bash
# Anthropic
MODEL_SMART=anthropic/claude-sonnet-4-6
MODEL_LITE=anthropic/claude-haiku-4-5

# OpenAI
MODEL_SMART=openai/gpt-4o
MODEL_LITE=openai/gpt-4o-mini

# Groq (free)
MODEL_SMART=groq/llama-3.3-70b-versatile
MODEL_LITE=groq/llama-3.1-8b-instant

# OpenRouter (free)
MODEL_SMART=openrouter/nvidia/nemotron-3-super-120b-a12b:free
MODEL_LITE=openrouter/nvidia/nemotron-nano-9b-v2:free

# Ollama (local, free)
MODEL_SMART=ollama/qwen3-coder:30b   # or any model from `ollama list`
MODEL_LITE=ollama/llama3.2:3b
OLLAMA_BASE_URL=http://127.0.0.1:11434  # 127.0.0.1 required (macOS IPv6 quirk)
```

## Security

All file tools are sandboxed — agents can only read/write within the `--project` directory.
Path traversal attempts are blocked automatically.

## Requirements

- Python 3.11+
- CrewAI 1.12+
- API key in `.env` (Anthropic, OpenAI, Groq, OpenRouter, or local Ollama)

---

# Русская версия

CrewLine — AI-команда разработки: настрой агентов в YAML, укажи на проект, получи код + ревью + тесты.

## Быстрый старт

```bash
# 1. Установите зависимости
pip install -r requirements.txt

# 2. Создайте .env с API ключом
cp .env.example .env
# Добавьте ANTHROPIC_API_KEY в .env

# 3. Запустите агентов на проекте
python main.py --project ./projects/example_project --goal "Добавить JWT авторизацию"
```

## Два режима работы

### Режим 1 — Агенты сами строят план (по умолчанию)

```bash
python main.py -p ./projects/app -g "Добавить авторизацию"
```

Цепочка: архитектор (план) → разработчик (код) → ревьюер (проверка).

### Режим 2 — Вы даёте готовый план

```bash
python main.py --plan plan.md -p ./projects/app -g "Реализовать JWT авторизацию"
```

Подробные инструкции — в [GUIDE.md](GUIDE.md).

## Параметры CLI

```
--project / -p   Путь к папке проекта
--goal    / -g   Цель для команды агентов
--tasks   / -t   Список задач через запятую (default: analyze,implement,review)
--plan           Путь к файлу с планом (пропускает архитектора)
--memory         Память агентов между сессиями (ChromaDB)
--human-review   Пауза для ручного подтверждения после каждой задачи (переопределяет tasks.yaml)
--no-human-review  Отключить все паузы (переопределяет tasks.yaml)
--dry-run        Показать план без вызова API (отладка)
```

## Примеры

```bash
# Агенты строят план и реализуют
python main.py -p ./projects/my-app -g "Добавить OAuth через Google"

# Готовый план — агенты реализуют напрямую
python main.py --plan plan.md -p ./projects/my-app -g "Реализовать JWT авторизацию"

# Проверить что запустится (без API)
python main.py --dry-run -p ./projects/my-app -g "Тест"

# Рисковое изменение — пауза для ревью после каждого шага
python main.py -p ./projects/my-app -g "Мигрировать БД" --human-review

# Полный цикл
python main.py -p ./projects/my-app -g "Добавить OAuth" \
  --tasks analyze_requirements,implement_solution,review_code,write_tests,write_documentation
```

## Безопасность

Все файловые инструменты работают в sandbox — агенты могут читать/писать только внутри директории `--project`.

## Требования

- Python 3.11+
- CrewAI 1.12+
- API ключ в `.env` (Anthropic, OpenAI, Groq, OpenRouter или локальный Ollama)

## Смена провайдера

Не нужно редактировать `agents.yaml`. Поменяйте 2 строки в `.env`:

```bash
MODEL_SMART=openai/gpt-4o        # архитектор + разработчик
MODEL_LITE=openai/gpt-4o-mini    # ревьюер + QA + документация
```
