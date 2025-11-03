"""Deterministic Packmol wrapper.

This module provides a thin wrapper around the external 'packmol' executable,
feeding the provided deck via stdin and writing outputs into the current working
directory.

Assumptions:
- The current working directory (Path.cwd()) is the desired output directory.
- Input PDBs referenced by 'structure ...' directives are expected to be
  resolvable relative to the CWD. Missing structures are reported in 'warnings'
  and are appended to stderr. Optionally escalate to error via flag.
- PATH is augmented with the packmol executable's directory to mitigate dynamic
  linker/library path issues.
- Optional RNG determinism via 'seed N' deck directive injection.

Return value:
- Dict (ExternalToolResult.to_dict()) with keys:
  - 'tool','argv','cwd','duration_s','stdout','stderr','outputs','tool_version','warnings','seed'
  - Back-compat convenience: 'packed_structure' at top-level (same as outputs['packed_structure'])

Exceptions:
- FileNotFoundError: if the executable or deck is missing.
- ValueError: if the deck is missing an 'output ...' directive.
- RuntimeError: if packmol fails or the expected output is not created.
"""

from __future__ import annotations

import logging
import re
import subprocess
import time
from pathlib import Path
from typing import Optional, List

from .adapter import ExternalToolResult, augment_env_with_exe_dir, get_tool_version

logger = logging.getLogger(__name__)

def _inject_seed(deck_text: str, seed: int) -> str:
    # Remove existing seed lines and insert a single deterministic seed at the top
    seed_re = re.compile(r"^\s*seed\b.*$", re.IGNORECASE | re.MULTILINE)
    pruned = seed_re.sub("", deck_text).lstrip("\n")
    return f"seed {seed}\n{pruned}"

def run(deck_path: str, exe_path: str, timeout_s: int = 600, seed: int | None = None, escalate_warnings_to_error: bool = False) -> dict:
    """Run Packmol by feeding the deck via a seekable stdin file handle.

    Parameters:
    - deck_path: path to the Packmol input deck file (text)
    - exe_path: path to the packmol executable
    - timeout_s: seconds before the process is terminated
    - seed: optional integer RNG seed to inject into the deck (determinism)
    - escalate_warnings_to_error: when True, raise on missing structure warnings before running

    Returns:
    - ExternalToolResult.to_dict() with unified keys; includes 'packed_structure' alias for compatibility.

    Raises:
    - FileNotFoundError, ValueError, RuntimeError
    """
    exe = Path(exe_path).resolve()
    if not exe.exists() or not exe.is_file():
        raise FileNotFoundError(f"Executable not found: {exe}")

    deck_p = Path(deck_path)
    if not deck_p.exists() or not deck_p.is_file():
        raise FileNotFoundError(f"Packmol deck not found: {deck_p}")

    # Prepare working directory and deck text
    work_dir = Path.cwd()
    deck_text = deck_p.read_text(encoding="utf-8")

    if seed is not None:
        deck_text = _inject_seed(deck_text, int(seed))

    # Parse directives we care about from the final deck text
    out_name: Optional[str] = None
    structure_files: List[str] = []
    out_re = re.compile(r"^\s*output\s+(.+?)\s*$", re.IGNORECASE)
    struct_re = re.compile(r"^\s*structure\s+(.+?)\s*$", re.IGNORECASE)

    for raw_line in deck_text.splitlines():
        line_no_comment = raw_line.split("#", 1)[0].strip()
        if not line_no_comment:
            continue
        m_out = out_re.match(line_no_comment)
        if m_out and out_name is None:
            val = m_out.group(1).strip().strip('\'"')
            if val.endswith(";"):
                val = val[:-1].strip()
            out_name = val
        m_struct = struct_re.match(line_no_comment)
        if m_struct:
            sval = m_struct.group(1).strip().strip('\'"')
            if sval.endswith(";"):
                sval = sval[:-1].strip()
            structure_files.append(sval)

    if not out_name:
        raise ValueError("Packmol deck missing output directive ('output <filename>')")

    # Prepare warnings for missing structure files (non-fatal unless escalated)
    warnings: List[str] = []
    for s in structure_files:
        s_path = (work_dir / s) if not Path(s).is_absolute() else Path(s)
        if not s_path.exists():
            warnings.append(f"[packmol] Warning: structure file not found: {s_path}")

    if escalate_warnings_to_error and warnings:
        joined = "\n".join(warnings)
        raise RuntimeError(f"Packmol deck validation failed due to warnings escalation:\n{joined}")

    # Write a temp copy of the deck into the working directory; pass as stdin (seekable file handle)
    tmp_deck = work_dir / (deck_p.name if deck_p.name else "packmol_deck.inp")
    tmp_deck.write_text(deck_text, encoding="utf-8")

    env = augment_env_with_exe_dir(str(exe))
    tool_version = get_tool_version(str(exe))

    t0 = time.perf_counter()
    try:
        with tmp_deck.open("r", encoding="utf-8") as fh:
            proc = subprocess.run(
                [str(exe)],
                stdin=fh,
                text=True,
                capture_output=True,
                check=True,
                cwd=str(work_dir),
                env=env,
                timeout=timeout_s,
            )
        duration = time.perf_counter() - t0
        stdout = proc.stdout
        stderr = proc.stderr
    except subprocess.CalledProcessError as e:
        duration = time.perf_counter() - t0
        msg = e.stderr or e.stdout or str(e)
        raise RuntimeError(f"packmol failed with exit code {e.returncode}: {msg.strip()}") from e

    out_path = work_dir / out_name
    if not out_path.exists() or out_path.stat().st_size == 0:
        raise RuntimeError(f"Expected Packmol output not created or empty: {out_path}")

    merged_stderr = "\n".join(warnings + ([stderr] if stderr else [])) if warnings else (stderr or "")

    result = ExternalToolResult(
        tool="packmol",
        argv=[str(exe)],
        cwd=str(work_dir),
        duration_s=float(duration),
        stdout=stdout or "",
        stderr=merged_stderr,
        outputs={"packed_structure": str(out_path)},
        tool_version=tool_version,
        warnings=warnings,
        seed=seed,
    )
    d = result.to_dict()
    # Back-compat alias
    d["packed_structure"] = str(out_path)
    return d
