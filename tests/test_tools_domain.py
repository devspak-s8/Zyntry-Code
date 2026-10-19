"""Tests for the tool catalog / command policy (domain layer)."""

from domain import tools


def test_detect_commands_from_python_repo():
    repo = [
        {"path": "pyproject.toml", "language": "toml", "content": "[project]\ndependencies = []"},
        {"path": "src/app.py", "language": "python", "content": "print('hi')"},
    ]
    commands = tools.detect_commands(repo)
    assert commands["test"]["cmd"].startswith("pytest")
    assert "lint" in commands


def test_detect_commands_from_node_repo():
    repo = [{"path": "package.json", "language": "json",
             "content": '{"scripts": {"test": "vitest run", "build": "vite build"}}'}]
    commands = tools.detect_commands(repo)
    assert commands["test"]["cmd"] in ("npm test", "vitest run")
    assert "build" in commands


def test_detect_none_without_ecosystem():
    assert tools.detect_commands([{"path": "README.md"}]) == {}


def test_dangerous_classification():
    assert tools.is_dangerous("rm -rf node_modules")
    assert tools.is_dangerous("git push origin main")
    assert not tools.is_dangerous("npm test")


def test_allowlist():
    assert tools.is_allowed("npm test", [])
    assert tools.is_allowed("pytest -q", [])
    assert not tools.is_allowed("rm -rf /", [])
    assert tools.is_allowed("custom-tool run", ["custom-tool"])


def test_verification_command_mapping():
    assert tools.command_key_for_verification("tests") == "test"
    assert tools.command_key_for_verification("lint") == "lint"
    assert tools.command_key_for_verification("type_check") == "type_check"
    assert tools.command_key_for_verification("build") == "build"
    assert tools.command_key_for_verification("contract") is None
    assert tools.verification_for_command_key("test") == "tests"