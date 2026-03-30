"""
File system tools for agents.
All operations are sandboxed to the project directory via set_project_root().
"""

from pathlib import Path
from crewai.tools import tool

_project_root: Path | None = None


def set_project_root(path: Path) -> None:
    global _project_root
    _project_root = path.resolve()


def _safe_resolve(file_path: str) -> Path:
    """Resolves path and ensures it stays within the project root."""
    if _project_root is None:
        raise RuntimeError("project_root not set — call set_project_root() before running")

    path = Path(file_path)
    if not path.is_absolute():
        path = _project_root / path
    resolved = path.resolve()

    if not str(resolved).startswith(str(_project_root)):
        raise PermissionError(f"Access denied — path is outside project: {file_path}")

    return resolved


@tool("Read File")
def read_file(file_path: str) -> str:
    """Reads file contents by path. Use to explore project code."""
    try:
        path = _safe_resolve(file_path)
        if not path.exists():
            return f"File not found: {file_path}"
        if not path.is_file():
            return f"Not a file: {file_path}"
        content = path.read_text(encoding="utf-8")
        return f"=== {path.relative_to(_project_root)} ===\n{content}"
    except PermissionError as e:
        return str(e)
    except Exception as e:
        return f"Error reading {file_path}: {e}"


@tool("Write File")
def write_file(file_path: str, content: str) -> str:
    """Writes content to a file inside the project. Creates directories automatically."""
    try:
        path = _safe_resolve(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return f"File written: {path.relative_to(_project_root)} ({len(content)} chars)"
    except PermissionError as e:
        return str(e)
    except Exception as e:
        return f"Error writing {file_path}: {e}"


@tool("List Directory")
def list_directory(directory_path: str, max_depth: int = 3) -> str:
    """Shows directory structure as a tree. Use '.' for project root. max_depth controls depth (default 3)."""
    try:
        path = _safe_resolve(directory_path)
        if not path.exists():
            return f"Directory not found: {directory_path}"

        lines = [f"{path.name}/"]
        _build_tree(path, lines, prefix="  ", depth=0, max_depth=max_depth)
        return "\n".join(lines)
    except PermissionError as e:
        return str(e)
    except Exception as e:
        return f"Error reading directory {directory_path}: {e}"


def _build_tree(path: Path, lines: list, prefix: str, depth: int, max_depth: int):
    if depth >= max_depth:
        return

    ignore = {".git", "__pycache__", ".venv", "venv", "node_modules", ".pytest_cache", ".mypy_cache"}

    items = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name))
    for i, item in enumerate(items):
        if item.name in ignore or item.name.startswith("."):
            continue
        connector = "└── " if i == len(items) - 1 else "├── "
        lines.append(f"{prefix}{connector}{item.name}")
        if item.is_dir():
            extension = "    " if i == len(items) - 1 else "│   "
            _build_tree(item, lines, prefix + extension, depth + 1, max_depth)


@tool("Search In Files")
def search_in_files(search_term: str, directory_path: str = ".", file_extension: str = "") -> str:
    """Searches for a string in project files. Returns matching files and lines. Use '.' for project root."""
    try:
        base = _safe_resolve(directory_path)
        results = []
        ignore = {".git", "__pycache__", ".venv", "venv", "node_modules"}

        for file_path in base.rglob("*"):
            if any(part in ignore for part in file_path.parts):
                continue
            if not file_path.is_file():
                continue
            if file_extension and not file_path.suffix == file_extension:
                continue
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                lines_found = [
                    f"  Line {i+1}: {line.strip()}"
                    for i, line in enumerate(content.splitlines())
                    if search_term.lower() in line.lower()
                ]
                if lines_found:
                    results.append(f"\n{file_path.relative_to(_project_root)}:")
                    results.extend(lines_found[:5])
            except Exception:
                continue

        if not results:
            return f"'{search_term}' not found"
        return "\n".join(results)
    except PermissionError as e:
        return str(e)
    except Exception as e:
        return f"Search error: {e}"
