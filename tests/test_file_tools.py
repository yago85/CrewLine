"""Tests for file tools sandbox security and basic operations."""

import pytest
from pathlib import Path

from tools.file_tools import set_project_root, _safe_resolve, _project_root


@pytest.fixture(autouse=True)
def setup_sandbox(tmp_path):
    """Set up a temporary project root for each test."""
    set_project_root(tmp_path)
    yield tmp_path
    # Reset after test
    set_project_root(tmp_path)


class TestSandbox:
    """Verify that path traversal is blocked."""

    def test_safe_resolve_allows_project_files(self, setup_sandbox):
        tmp = setup_sandbox
        test_file = tmp / "app.py"
        test_file.write_text("print('hello')")
        resolved = _safe_resolve("app.py")
        assert resolved == test_file

    def test_safe_resolve_allows_nested_paths(self, setup_sandbox):
        tmp = setup_sandbox
        nested = tmp / "src" / "main.py"
        nested.parent.mkdir(parents=True)
        nested.write_text("")
        resolved = _safe_resolve("src/main.py")
        assert resolved == nested

    def test_safe_resolve_blocks_parent_traversal(self, setup_sandbox):
        with pytest.raises(PermissionError, match="outside project"):
            _safe_resolve("../../etc/passwd")

    def test_safe_resolve_blocks_absolute_outside(self, setup_sandbox):
        with pytest.raises(PermissionError, match="outside project"):
            _safe_resolve("/etc/passwd")

    def test_safe_resolve_blocks_symlink_escape(self, setup_sandbox):
        tmp = setup_sandbox
        link = tmp / "escape"
        link.symlink_to("/tmp")
        with pytest.raises(PermissionError, match="outside project"):
            _safe_resolve("escape/secret.txt")

    def test_safe_resolve_without_root_raises(self):
        import tools.file_tools as ft
        old_root = ft._project_root
        ft._project_root = None
        try:
            with pytest.raises(RuntimeError, match="project_root not set"):
                _safe_resolve("any.py")
        finally:
            ft._project_root = old_root


class TestReadFile:
    def test_read_existing_file(self, setup_sandbox):
        from tools.file_tools import read_file
        tmp = setup_sandbox
        (tmp / "hello.txt").write_text("world")
        result = read_file.run("hello.txt")
        assert "world" in result

    def test_read_missing_file(self, setup_sandbox):
        from tools.file_tools import read_file
        result = read_file.run("nonexistent.py")
        assert "not found" in result.lower()

    def test_read_blocked_path(self, setup_sandbox):
        from tools.file_tools import read_file
        result = read_file.run("/etc/hosts")
        assert "denied" in result.lower() or "outside" in result.lower()


class TestWriteFile:
    def test_write_creates_file(self, setup_sandbox):
        from tools.file_tools import write_file
        tmp = setup_sandbox
        result = write_file.run(file_path="output.txt", content="hello")
        assert "written" in result.lower()
        assert (tmp / "output.txt").read_text() == "hello"

    def test_write_creates_subdirectories(self, setup_sandbox):
        from tools.file_tools import write_file
        tmp = setup_sandbox
        write_file.run(file_path="a/b/c.txt", content="deep")
        assert (tmp / "a" / "b" / "c.txt").read_text() == "deep"

    def test_write_blocked_path(self, setup_sandbox):
        from tools.file_tools import write_file
        result = write_file.run(file_path="/tmp/evil.txt", content="hack")
        assert "denied" in result.lower() or "outside" in result.lower()


class TestListDirectory:
    def test_list_project_root(self, setup_sandbox):
        from tools.file_tools import list_directory
        tmp = setup_sandbox
        (tmp / "file1.py").write_text("")
        (tmp / "file2.py").write_text("")
        result = list_directory.run(".")
        assert "file1.py" in result
        assert "file2.py" in result


class TestSearchInFiles:
    def test_search_finds_match(self, setup_sandbox):
        from tools.file_tools import search_in_files
        tmp = setup_sandbox
        (tmp / "code.py").write_text("def hello():\n    return 'world'")
        result = search_in_files.run(directory_path=".", search_term="hello")
        assert "hello" in result

    def test_search_no_match(self, setup_sandbox):
        from tools.file_tools import search_in_files
        tmp = setup_sandbox
        (tmp / "code.py").write_text("def foo(): pass")
        result = search_in_files.run(directory_path=".", search_term="nonexistent_xyz")
        assert "not found" in result.lower()
