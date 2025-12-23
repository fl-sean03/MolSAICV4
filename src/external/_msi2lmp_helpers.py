"""Helper utilities for msi2lmp wrapper.

Private module containing file staging, hashing, and result persistence helpers.
"""

from __future__ import annotations

import filecmp
import hashlib
import json
import shutil
from pathlib import Path


def ensure_file(f: Path) -> None:
    """Raise FileNotFoundError if file does not exist."""
    if not f.exists() or not f.is_file():
        raise FileNotFoundError(f"File not found: {f}")


def stage_file(src_path: Path, work_dir: Path) -> Path:
    """Ensure src_path is present in work_dir; copy only if needed; return destination path."""
    src = Path(src_path).resolve()
    ensure_file(src)
    work_dir.mkdir(parents=True, exist_ok=True)
    dest = work_dir / src.name

    # If already exactly the same path, nothing to do.
    try:
        if src.resolve() == dest.resolve():
            return dest
    except Exception:
        pass

    if dest.exists():
        try:
            if filecmp.cmp(str(src), str(dest), shallow=False):
                return dest
        except Exception:
            pass

    shutil.copy2(str(src), str(dest))
    return dest


def sha256_file(p: Path, chunk_size: int = 1024 * 1024) -> str:
    """Compute SHA256 hash of a file."""
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def write_result_json(work_dir: Path, envelope: dict) -> Path:
    """Write deterministic result.json (sorted keys + newline) into work_dir."""
    work_dir.mkdir(parents=True, exist_ok=True)
    out = work_dir / "result.json"
    out.write_text(json.dumps(envelope, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out
