from __future__ import annotations

import hashlib
import json
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional


def sha256_file(path: str | Path, *, chunk_size: int = 1024 * 1024) -> str:
    """Return hex-encoded sha256 for a file on disk."""
    p = Path(path)
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def json_dumps_stable(obj: Any) -> str:
    """Deterministic JSON string: sorted keys, 2-space indent, newline-terminated."""
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def write_json_stable(path: str | Path, obj: Any) -> Path:
    """Write deterministic JSON (sorted keys + newline) to `path`."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json_dumps_stable(obj), encoding="utf-8")
    return p


def relpath_posix(path: str | Path, *, base_dir: str | Path) -> str:
    """Return a POSIX-style relative path from base_dir to path.

    Raises ValueError if path is not within base_dir (to protect determinism).
    """
    p = Path(path).resolve()
    base = Path(base_dir).resolve()
    try:
        rel = p.relative_to(base)
    except Exception as e:
        raise ValueError(f"path is not under base_dir: path={p} base_dir={base}") from e
    return rel.as_posix()


@dataclass(frozen=True)
class HashedPath:
    path: str  # relative POSIX path
    sha256: str


def hash_paths(
    paths: Mapping[str, str | Path],
    *,
    base_dir: str | Path,
) -> dict[str, HashedPath]:
    """Compute sha256 for each provided path and return a stable-keyed mapping.

    The returned `path` values are always relative to base_dir (POSIX style).
    """
    out: dict[str, HashedPath] = {}
    for key in sorted(paths.keys()):
        p = Path(paths[key]).resolve()
        out[key] = HashedPath(path=relpath_posix(p, base_dir=base_dir), sha256=sha256_file(p))
    return out


def get_python_version() -> str:
    # Prefer stable semantic version string only (avoid build tags).
    return platform.python_version()


def get_module_version(import_name: str) -> str:
    """Best-effort __version__ discovery; never raises."""
    try:
        mod = __import__(import_name)
        v = getattr(mod, "__version__", None)
        if isinstance(v, str) and v.strip():
            return v.strip()
    except Exception:
        pass
    return "unknown"


def get_runtime_versions(*, extra: Optional[Mapping[str, str]] = None) -> dict[str, str]:
    """Collect versions for core runtime and optional extra tool/version strings.

    Note: This is intentionally deterministic (no timestamps, no absolute paths).
    """
    versions = {
        "python": get_python_version(),
        "molsaic": get_module_version("molsaic"),
        "usm": get_module_version("usm"),
        "upm": get_module_version("upm"),
    }
    if extra:
        for k in sorted(extra.keys()):
            versions[str(k)] = str(extra[k])
    return versions


__all__ = [
    "HashedPath",
    "get_module_version",
    "get_python_version",
    "get_runtime_versions",
    "hash_paths",
    "json_dumps_stable",
    "relpath_posix",
    "sha256_file",
    "write_json_stable",
]