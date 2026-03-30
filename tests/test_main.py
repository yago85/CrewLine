"""Tests for main.py helper functions and CLI logic."""

import pytest
from pathlib import Path


class TestEnsureProviderPrefix:
    def test_adds_anthropic_prefix(self):
        from main import _ensure_provider_prefix
        assert _ensure_provider_prefix("claude-sonnet-4-6") == "anthropic/claude-sonnet-4-6"

    def test_keeps_existing_prefix(self):
        from main import _ensure_provider_prefix
        assert _ensure_provider_prefix("openai/gpt-4o") == "openai/gpt-4o"

    def test_keeps_anthropic_prefix(self):
        from main import _ensure_provider_prefix
        assert _ensure_provider_prefix("anthropic/claude-haiku-4-5") == "anthropic/claude-haiku-4-5"

    def test_keeps_ollama_prefix(self):
        from main import _ensure_provider_prefix
        assert _ensure_provider_prefix("ollama/llama3.2") == "ollama/llama3.2"


class TestLoadYaml:
    def test_loads_agents_config(self):
        from main import load_yaml, AGENTS_CONFIG
        agents = load_yaml(AGENTS_CONFIG)
        assert "architect" in agents
        assert "senior_developer" in agents
        assert "code_reviewer" in agents

    def test_loads_tasks_config(self):
        from main import load_yaml, TASKS_CONFIG
        tasks = load_yaml(TASKS_CONFIG)
        assert "analyze_requirements" in tasks
        assert "implement_solution" in tasks
        assert "execute_plan" in tasks
        assert "review_code" in tasks

    def test_agents_have_required_fields(self):
        from main import load_yaml, AGENTS_CONFIG
        agents = load_yaml(AGENTS_CONFIG)
        required = {"role", "goal", "backstory"}
        for key, cfg in agents.items():
            missing = required - set(cfg.keys())
            assert not missing, f"Agent '{key}' missing fields: {missing}"

    def test_tasks_have_required_fields(self):
        from main import load_yaml, TASKS_CONFIG
        tasks = load_yaml(TASKS_CONFIG)
        required = {"description", "expected_output", "agent"}
        for key, cfg in tasks.items():
            missing = required - set(cfg.keys())
            assert not missing, f"Task '{key}' missing fields: {missing}"

    def test_task_agents_exist(self):
        from main import load_yaml, AGENTS_CONFIG, TASKS_CONFIG
        agents = load_yaml(AGENTS_CONFIG)
        tasks = load_yaml(TASKS_CONFIG)
        for task_key, task_cfg in tasks.items():
            assert task_cfg["agent"] in agents, \
                f"Task '{task_key}' references unknown agent '{task_cfg['agent']}'"

    def test_task_context_references_exist(self):
        from main import load_yaml, TASKS_CONFIG
        tasks = load_yaml(TASKS_CONFIG)
        all_keys = set(tasks.keys())
        for task_key, task_cfg in tasks.items():
            for dep in task_cfg.get("context", []):
                assert dep in all_keys, \
                    f"Task '{task_key}' context references unknown task '{dep}'"


class TestDryRun:
    def test_dry_run_no_errors(self, capsys):
        from main import dry_run, load_yaml, AGENTS_CONFIG, TASKS_CONFIG
        agents = load_yaml(AGENTS_CONFIG)
        tasks = load_yaml(TASKS_CONFIG)
        dry_run(agents, tasks, ["analyze_requirements", "implement_solution", "review_code"])
        output = capsys.readouterr().out
        assert "DRY RUN" in output
        assert "architect" in output

    def test_dry_run_with_plan(self, capsys):
        from main import dry_run, load_yaml, AGENTS_CONFIG, TASKS_CONFIG
        agents = load_yaml(AGENTS_CONFIG)
        tasks = load_yaml(TASKS_CONFIG)
        dry_run(agents, tasks, ["execute_plan", "review_code"], plan_path=Path("plan.md"))
        output = capsys.readouterr().out
        assert "plan.md" in output

    def test_dry_run_missing_task(self, capsys):
        from main import dry_run, load_yaml, AGENTS_CONFIG, TASKS_CONFIG
        agents = load_yaml(AGENTS_CONFIG)
        tasks = load_yaml(TASKS_CONFIG)
        dry_run(agents, tasks, ["nonexistent_task"])
        output = capsys.readouterr().out
        assert "NOT FOUND" in output
