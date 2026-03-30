# Usage Guide / Руководство по использованию

## What is this? / Что это?

CrewLine is your personal AI studio. You give agents a task, and they analyze the project, write code, review it, and write tests.

Set up once — use for any project.

---

## Initial Setup (once)

### 1. Install dependencies

```bash
cd CrewLine
pip install -r requirements.txt
```

### 2. Create API key file

```bash
cp .env.example .env
```

Open `.env` and paste your key:

```
ANTHROPIC_API_KEY=sk-ant-...
```

### 3. Verify it works

```bash
python main.py --list-agents
python main.py --list-tasks
```

Done. No further configuration needed.

---

## Working with an Existing Project

Say you have a project at `~/dev/my-api` and want agents to add authentication.

### Step 1 — Copy project to the projects folder

```bash
cp -r ~/dev/my-api ./projects/my-api
```

> Why copy? Agents will modify files. The copy is your safety net.
> If you like the result — move changes to the original.

> **Tip:** Add `AGENTS.md` to your project with architecture notes, conventions, and constraints.
> Agents read it automatically, giving them better context about your codebase.

### Step 2 — Check the plan (no cost)

```bash
python main.py --dry-run -p ./projects/my-api -g "Add JWT authentication"
```

Shows: which agents will run, with which models, in what order.
No API calls, no money spent.

### Step 3 — Run the agents

**Option A — Interactive wizard** (easiest, no flags to remember):

```bash
python main.py
```

The wizard will ask for project path, goal, tasks, human review mode and memory.

**Option B — CLI flags**:

```bash
python main.py -p ./projects/my-api -g "Add JWT authentication"
```

Default pipeline (3 tasks):

1. **Architect** — analyzes the project, creates a plan
2. **Developer** — writes code per plan
3. **Reviewer** — checks quality and security

---

## Creating a New Project from Scratch

### Step 1 — Create folder and describe the idea

```bash
mkdir -p ./projects/my-new-app
```

Create `./projects/my-new-app/README.md`:

```markdown
# My New App

Personal finance tracking web app.

## Tech Stack

- Python + Flask
- SQLite for storage
- Jinja2 for templates

## Features

- Add income and expenses
- Spending categories
- Simple dashboard with monthly totals
```

> The more detailed the README — the better the result. Agents read it first.

### Step 2 — Run

```bash
python main.py -p ./projects/my-new-app -g "Create basic app structure with models and routes"
```

Agents will create files directly in the project folder.

---

## Two Modes of Operation

### Mode 1 — Agents build the plan (default)

The architect analyzes the project, creates a plan, the developer implements it.
Use when you don't know exactly how to solve the task.

```bash
python main.py -p ./projects/app -g "Add JWT authentication"
```

Pipeline: architect (plan) → developer (code) → reviewer (check).

### Mode 2 — You provide the plan

You describe architecture and logic in a file, agents implement it.
Use when you know exactly what you want and don't want to pay for analysis.

**Step 1** — Create a plan file (e.g., `plan.md`):

```markdown
# Plan: JWT Authentication

## Architecture

- auth/ module with three files: models.py, routes.py, utils.py
- Middleware for token verification
- Refresh token storage in Redis

## Files to Create

### auth/models.py

- User class with fields: id, email, password_hash, created_at
- Function verify_password(plain, hashed) -> bool

### auth/routes.py

- POST /auth/register — registration, returns access + refresh tokens
- POST /auth/login — login, verifies password, returns tokens
- POST /auth/refresh — refresh access token using refresh token

### auth/utils.py

- create_access_token(user_id) — JWT, 15 min TTL
- create_refresh_token(user_id) — JWT, 30 day TTL
- decode_token(token) -> payload

## Dependencies

- PyJWT for tokens
- bcrypt for password hashing
```

> The more detailed the plan — the more precise the result. Describe files, functions, dependencies.

**Step 2** — Run with `--plan`:

```bash
python main.py --plan plan.md -p ./projects/app -g "Implement JWT authentication"
```

Automatically runs: developer (execute_plan) → reviewer (review_code).
Architect is skipped — the plan is already there.

**Step 3 (optional)** — Full cycle with your plan:

```bash
python main.py --plan plan.md -p ./projects/app -g "Implement JWT" \
  --tasks execute_plan,review_code,write_tests,validate_environment
```

---

## Choosing Tasks — What to Run

You don't have to run everything. Pick tasks for the situation:

### Quick development (default)

```bash
python main.py -p ./projects/app -g "Goal"
```

Runs: analyze → code → review.

### Full cycle

```bash
python main.py -p ./projects/app -g "Goal" \
  --tasks analyze_requirements,implement_solution,review_code,write_tests,write_documentation
```

### With dependency check

```bash
python main.py -p ./projects/app -g "Goal" \
  --tasks analyze_requirements,implement_solution,review_code,validate_environment
```

`validate_environment` checks that all `import`s are in `requirements.txt`.

### Analysis only (no code changes)

```bash
python main.py -p ./projects/app -g "How to best organize the auth module?" \
  --tasks analyze_requirements
```

### Code review only

```bash
python main.py -p ./projects/app -g "Check API endpoint security" \
  --tasks review_code
```

---

## Available Tasks

| Task                   | What it does                      | When to use                 |
| ---------------------- | --------------------------------- | --------------------------- |
| `analyze_requirements` | Project inspection, work plan     | When you need auto-analysis |
| `implement_solution`   | Write code per architect's plan   | After analyze_requirements  |
| `execute_plan`         | Write code per your plan          | With --plan flag            |
| `review_code`          | Quality and security check        | After code is written       |
| `write_tests`          | Pytest tests                      | When you need tests         |
| `write_documentation`  | README and docs                   | When you need documentation |
| `validate_environment` | Check imports vs requirements.txt | After adding libraries      |

---

## Budget Savings

Agents use two model tiers based on task complexity:

- **smart** (architect, developer) — complex tasks requiring reasoning
- **lite** (reviewer, QA, docs, devops) — mechanical tasks, ~6x cheaper

To switch provider — edit `MODEL_SMART` and `MODEL_LITE` in `.env`.
No need to touch `agents.yaml`:

```bash
# Anthropic
MODEL_SMART=anthropic/claude-sonnet-4-6
MODEL_LITE=anthropic/claude-haiku-4-5

# OpenAI
MODEL_SMART=openai/gpt-4o
MODEL_LITE=openai/gpt-4o-mini

# Free (OpenRouter)
MODEL_SMART=openrouter/nvidia/nemotron-3-super-120b-a12b:free
MODEL_LITE=openrouter/nvidia/nemotron-nano-9b-v2:free
```

---

## Adding Your Own Agent

Edit `config/agents.yaml`:

```yaml
security_expert:
  role: Security Expert
  goal: >
    Find OWASP Top 10 vulnerabilities and suggest fixes.
  backstory: >
    Experienced pentester. Thinks like an attacker, defends like an engineer.
  model_tier: smart
  verbose: true
  allow_delegation: false
  max_iter: 5
```

Then add a task in `config/tasks.yaml`:

```yaml
security_audit:
  async_execution: false
  context: [implement_solution]
  description: >
    Perform a security audit of the code:
    GOAL: {goal}
    CONTEXT: {project_context}
  expected_output: >
    Report with found vulnerabilities and recommendations.
  agent: security_expert
```

Now use it:

```bash
python main.py -p ./projects/app -g "Check security" \
  --tasks analyze_requirements,implement_solution,security_audit
```

No code changes needed — YAML files only.

---

## Memory Across Sessions

Add `--memory` so agents remember context from past runs:

```bash
python main.py -p ./projects/app -g "Add pagination to API" --memory
```

On the next run with `--memory`, agents will remember what they did before.
Requires ChromaDB (installed automatically with crewai).

---

## Human-in-the-Loop (Manual Review)

You can pause execution after any task and review the agent's output before continuing.
This is useful for risky or critical changes where you want to stay in control.

### Three modes

```bash
# Default: respect per-task settings from tasks.yaml
python main.py -p ./projects/app -g "Add OAuth"

# Force pause after EVERY task
python main.py -p ./projects/app -g "Migrate database schema" --human-review

# Fully autonomous — ignore all pauses (overrides tasks.yaml)
python main.py -p ./projects/app -g "Fix typo" --no-human-review
```

### Per-task default in tasks.yaml

You can mark individual tasks to always pause by default:

```yaml
analyze_requirements:
  human_input: true   # Pause: approve the plan before coding starts
  ...
```

Currently `analyze_requirements` and `review_code` are marked `human_input: true` by default.
To disable permanently, remove the field or set it to `false`.

### What happens on pause

CrewAI prints the agent's result and waits for your input:

- Press **Enter** (empty line) — approve and continue
- Type corrections — the agent incorporates them before proceeding

### When to use `--human-review`

| Scenario                     | Recommendation      |
| ---------------------------- | ------------------- |
| Working with production code | `--human-review`    |
| Risky migrations (DB, auth)  | `--human-review`    |
| Trusted CI/CD pipeline       | `--no-human-review` |
| Quick iterative dev loop     | `--no-human-review` |

---

## FAQ

**Agents broke the code — what do I do?**
That's why you copy the project to `projects/`. The original is untouched.
If you use git — even easier: `git diff` shows changes, `git checkout .` reverts.

**Agent output looks wrong — how to correct it without restarting?**
Run with `--human-review`. After each task you'll get a prompt to provide corrections
before the next agent starts.

**Can I use OpenAI instead of Claude?**
Yes. Add `OPENAI_API_KEY` to `.env`, set `MODEL_SMART=openai/gpt-4o` and `MODEL_LITE=openai/gpt-4o-mini` in `.env`. No need to edit `agents.yaml`.

**Can I use local models (Ollama)?**
Yes. Run `ollama serve`, set `MODEL_SMART=ollama/llama3.2` and `MODEL_LITE=ollama/llama3.2` in `.env`.

**How do I know what a run cost?**
CrewAI outputs token counts at the end. Cost depends on the model.
Use `--dry-run` to check the plan before running.

---

# Русская версия

Подробное руководство на русском языке.

## Первоначальная настройка

```bash
cd CrewLine
pip install -r requirements.txt
cp .env.example .env
# Вставьте ANTHROPIC_API_KEY в .env
python main.py --list-agents
```

## Работа с существующим проектом

```bash
# 1. Скопируйте проект
cp -r ~/dev/my-api ./projects/my-api

# 2. Проверьте план (бесплатно)
python main.py --dry-run -p ./projects/my-api -g "Добавить JWT авторизацию"

# 3a. Запустите интерактивно (мастер задаст все вопросы)
python main.py

# 3b. Или сразу с флагами
python main.py -p ./projects/my-api -g "Добавить JWT авторизацию"
```

## Новый проект с нуля

```bash
mkdir -p ./projects/my-new-app
# Создайте README.md с описанием проекта
python main.py -p ./projects/my-new-app -g "Создать структуру приложения"
```

## Два режима

**Режим 1** — агенты строят план сами:

```bash
python main.py -p ./projects/app -g "Добавить авторизацию"
```

**Режим 2** — вы даёте готовый план:

```bash
python main.py --plan plan.md -p ./projects/app -g "Реализовать авторизацию"
```

Создайте файл `plan.md` с архитектурой, списком файлов и логикой. Чем подробнее план — тем точнее результат.

## Выбор задач

| Задача                 | Что делает                       | Когда нужна                |
| ---------------------- | -------------------------------- | -------------------------- |
| `analyze_requirements` | Анализ проекта, план             | Автоматический анализ      |
| `implement_solution`   | Код по плану архитектора         | После analyze_requirements |
| `execute_plan`         | Код по готовому плану            | С флагом --plan            |
| `review_code`          | Проверка качества                | После написания кода       |
| `write_tests`          | Pytest-тесты                     | Когда нужны тесты          |
| `write_documentation`  | Документация                     | Когда нужна документация   |
| `validate_environment` | Проверка imports vs requirements | После добавления библиотек |

---

## Ручное подтверждение (Пауза после задачи)

Флаг `--human-review` останавливает выполнение после каждой задачи и ждёт вашего ввода.

```bash
# Пауза после каждого шага
python main.py -p ./projects/app -g "Мигрировать БД" --human-review

# Полностью автономно (игнорирует настройки tasks.yaml)
python main.py -p ./projects/app -g "Исправить опечатку" --no-human-review
```

По умолчанию пауза включена для `analyze_requirements` (перед написанием кода) и `review_code` (финальный вердикт).
Паузы можно отключить через `human_input: false` в `tasks.yaml`.

Что происходит на паузе: агент выводит результат и ждёт.
**Enter** — одобрить и продолжить. Текст — агент учтёт правку перед следующим шагом.

---

- **Архитектор и Разработчик** — Claude Sonnet (умная, дороже)
- **Ревьюер, QA, Документация, DevOps** — Claude Haiku (быстрая, ~6x дешевле)

Смена провайдера: `MODEL_SMART` и `MODEL_LITE` в `.env`. YAML не трогаем.

## FAQ

**Агенты сломали код?** Оригинал в безопасности — работа идёт в `projects/`.

**OpenAI вместо Claude?** Да: `OPENAI_API_KEY` и `MODEL_SMART=openai/gpt-4o`, `MODEL_LITE=openai/gpt-4o-mini` в `.env`.

**Локальные модели?** Да: `ollama serve`, `MODEL_SMART=ollama/llama3.2`, `MODEL_LITE=ollama/llama3.2` в `.env`.
