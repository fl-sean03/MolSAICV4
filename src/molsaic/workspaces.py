from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, Optional


class RepoRootNotFoundError(RuntimeError):
    """Raised when we cannot locate the repository root."""


class WorkspaceNotFoundError(FileNotFoundError):
    """Raised when a workspace cannot be located under workspaces/."""


class WorkspaceCollisionError(RuntimeError):
    """Raised when more than one workspace directory matches a basename."""


def find_repo_root(start: Optional[Path] = None) -> Path:
    """Find the repository root by walking up until we see pyproject.toml.

    This is intentionally robust to workspace re-organization and nesting depth.
    """
    p = (start or Path.cwd()).resolve()
    if p.is_file():
        p = p.parent

    for parent in (p,) + tuple(p.parents):
        if (parent / "pyproject.toml").is_file():
            return parent

    raise RepoRootNotFoundError(
        f"Could not find repo root (pyproject.toml) starting from: {start or Path.cwd()}"
    )


def workspaces_root(repo_root: Optional[Path] = None) -> Path:
    rr = repo_root or find_repo_root()
    return rr / "workspaces"


def _iter_workspace_dirs(root: Path) -> Iterable[Path]:
    """Yield candidate workspace directories beneath workspaces/.

    Rules:
    - A workspace is any directory that contains a run.py OR config.json.
    - Excludes hidden directories and the _template directory by name.
    """
    if not root.exists():
        return []

    # Walk one level at a time (Path.rglob is fine here; workspaces is not huge).
    for d in root.rglob("*"):
        if not d.is_dir():
            continue
        name = d.name
        if name.startswith("."):
            continue
        if name == "_template":
            continue

        if (d / "run.py").is_file() or (d / "config.json").is_file():
            yield d


@lru_cache(maxsize=1)
def _workspace_index_cached(workspaces_root_str: str) -> Dict[str, Path]:
    """Index basename -> full workspace dir. Enforces uniqueness by basename."""
    root = Path(workspaces_root_str)
    idx: Dict[str, Path] = {}
    collisions: Dict[str, list[Path]] = {}

    for d in _iter_workspace_dirs(root):
        base = d.name
        if base in idx:
            collisions.setdefault(base, [idx[base]]).append(d)
            continue
        idx[base] = d

    if collisions:
        lines = ["Workspace basename collisions detected under workspaces/:"]
        for base, paths in sorted(collisions.items(), key=lambda x: x[0]):
            lines.append(f"- {base}:")
            for p in paths:
                lines.append(f"  - {p}")
        raise WorkspaceCollisionError("\n".join(lines))

    return idx


def _invalidate_workspace_index_cache() -> None:
    """For tests/tools that modify the workspaces tree at runtime."""
    _workspace_index_cached.cache_clear()


def find_workspace_dir(name: str, repo_root: Optional[Path] = None) -> Path:
    """Find a workspace directory by basename anywhere under workspaces/**.

    Enforces uniqueness: if more than one directory has the same basename, raises
    WorkspaceCollisionError.

    Raises:
      WorkspaceNotFoundError if no match.
    """
    wr = workspaces_root(repo_root).resolve()
    idx = _workspace_index_cached(str(wr))

    if name not in idx:
        # Provide helpful suggestions: close matches by prefix
        suggestions = sorted([k for k in idx.keys() if k.startswith(name[: max(1, len(name) // 2)])])[:10]
        hint = f" Did you mean one of: {', '.join(suggestions)}" if suggestions else ""
        raise WorkspaceNotFoundError(f"Workspace '{name}' not found under {wr}.{hint}")

    return idx[name]


@dataclass(frozen=True)
class WorkspaceFiles:
    dir: Path
    config: Path
    run: Path
    outputs: Path
    summary: Path

    def as_dict(self) -> Dict[str, Path]:
        return {
            "dir": self.dir,
            "config": self.config,
            "run": self.run,
            "outputs": self.outputs,
            "summary": self.summary,
        }


def workspace_files(name: str, repo_root: Optional[Path] = None) -> WorkspaceFiles:
    d = find_workspace_dir(name, repo_root=repo_root)
    return WorkspaceFiles(
        dir=d,
        config=d / "config.json",
        run=d / "run.py",
        outputs=d / "outputs",
        summary=d / "outputs" / "summary.json",
    )


def resolve_workspace_dir(
    *,
    workspace_name: Optional[str] = None,
    workspace_dir: Optional[Path] = None,
    repo_root: Optional[Path] = None,
) -> Path:
    """Resolve a workspace directory from either an explicit dir or a basename.

    Contract for scripts/CLIs:
      - If workspace_dir is provided, it is used directly (after validation).
      - Else if workspace_name is provided, it is resolved via find_workspace_dir().
      - If both are provided, raises ValueError (avoid ambiguity).
      - If neither is provided, raises ValueError with an actionable message.
    """
    if workspace_name and workspace_dir:
        raise ValueError("Provide only one of --workspace-name or --workspace-dir (not both).")

    if workspace_dir is not None:
        d = Path(workspace_dir).expanduser().resolve()
        if not d.is_dir():
            raise WorkspaceNotFoundError(f"Workspace directory does not exist or is not a directory: {d}")
        return d

    if workspace_name is not None:
        name = workspace_name.strip()
        if not name:
            raise ValueError("--workspace-name must be a non-empty string.")
        return find_workspace_dir(name, repo_root=repo_root)

    raise ValueError("Missing workspace selection: provide --workspace-name or --workspace-dir.")