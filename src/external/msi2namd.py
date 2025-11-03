"""Deterministic wrapper for the external 'msi2namd' executable.

This module provides a thin, deterministic wrapper around the external
msi2namd tool to convert Accelrys/MSI CAR/MDF inputs into NAMD-compatible
PDB/PSF outputs.

Determinism and assumptions:
- Working directory is derived from the parent directory of 'output_prefix'.
- Input CAR/MDF files are staged into the working directory if not already
  present (copied when needed; identical-content files are not recopied).
- Forcefield parameter file (.prm) is referenced via absolute path (not copied).
- The PATH is augmented so the dynamic linker can resolve adjacent libraries.
- Execution enforces a timeout and raises on failure.
- Outputs are validated (existence and non-empty).

Return value:
- Dict with keys:
  - 'pdb_file': absolute path to the generated .pdb file
  - 'psf_file': absolute path to the generated .psf file
  - 'duration_s': wall-clock seconds (float)
  - 'stdout': process stdout (string)
  - 'stderr': process stderr (string)

Exceptions:
- FileNotFoundError: if any required file (exe, inputs) is missing.
- ValueError: if residue length > 4.
- RuntimeError: if the external process fails or expected outputs are missing.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import time
from pathlib import Path
import filecmp
from .adapter import ExternalToolResult, augment_env_with_exe_dir, get_tool_version

logger = logging.getLogger(__name__)


def _augment_env(exe_path: str) -> dict:
    """Delegate to shared adapter helper for PATH augmentation."""
    return augment_env_with_exe_dir(exe_path)


def _run(cmd: list[str], cwd: Path, env: dict, timeout_s: int) -> tuple[float, str, str]:
    """Run a command with deterministic cwd/env/timeout. Raises CalledProcessError on nonzero exit."""
    t0 = time.perf_counter()
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout_s,
        check=True,
    )
    return (time.perf_counter() - t0, proc.stdout, proc.stderr)


def _ensure_file(f: Path) -> None:
    if not f.exists() or not f.is_file():
        raise FileNotFoundError(f"File not found: {f}")


def _stage_file(src_path: str, work_dir: Path) -> Path:
    """Ensure a file is present in work_dir; copy only if needed; return destination path."""
    src = Path(src_path).resolve()
    _ensure_file(src)
    work_dir.mkdir(parents=True, exist_ok=True)
    dest = work_dir / src.name

    # If already exactly the same path, nothing to do.
    try:
        if src.resolve() == dest.resolve():
            return dest
    except Exception:
        # Fallback to content comparison if resolution fails oddly
        pass

    if dest.exists():
        try:
            if filecmp.cmp(str(src), str(dest), shallow=False):
                return dest
        except Exception:
            # If comparison fails, fall through to copying
            pass

    shutil.copy2(str(src), str(dest))
    return dest


def run(
    mdf_file: str,
    car_file: str,
    prm_file: str,
    residue: str,
    output_prefix: str,
    exe_path: str,
    timeout_s: int = 600,
) -> dict:
    """Convert CAR/MDF to PDB/PSF via msi2namd.

    Assumptions:
    - Working directory is the parent of 'output_prefix'. Inputs are staged into that directory.
    - '.prm' is not copied; it's referenced via absolute path.

    Parameters:
    - mdf_file: path to the MDF file
    - car_file: path to the CAR file
    - prm_file: path to the CHARMM-style parameter file (.prm)
    - residue: residue name (≤ 4 characters) to apply
    - output_prefix: target basename (may include directory); outputs will be '{name}.pdb' and '{name}.psf'
    - exe_path: path to msi2namd executable
    - timeout_s: seconds before the process is terminated

    Returns:
    - dict with keys: 'pdb_file', 'psf_file', 'duration_s', 'stdout', 'stderr'

    Raises:
    - FileNotFoundError, ValueError, RuntimeError
    """
    exe = Path(exe_path).resolve()
    if not exe.exists() or not exe.is_file():
        raise FileNotFoundError(f"Executable not found: {exe}")

    if residue is None or len(residue) == 0 or len(residue) > 4:
        raise ValueError(f"Residue must be 1-4 characters, got {residue!r}")

    name = Path(output_prefix).name
    work_dir = Path(output_prefix).resolve().parent
    work_dir.mkdir(parents=True, exist_ok=True)

    # Stage inputs (CAR/MDF) to deterministic working directory
    staged_car = _stage_file(car_file, work_dir)
    staged_mdf = _stage_file(mdf_file, work_dir)
    base_name = staged_car.stem  # Prefer CAR stem per spec

    prm_abs = Path(prm_file).resolve()
    _ensure_file(prm_abs)

    cmd = [
        str(exe),
        "-file",
        base_name,
        "-res",
        residue,
        "-classII",
        str(prm_abs),
        "-output",
        name,
    ]

    env = _augment_env(str(exe))
    try:
        duration, stdout, stderr = _run(cmd, cwd=work_dir, env=env, timeout_s=timeout_s)
    except subprocess.CalledProcessError as e:
        msg = e.stderr or e.stdout or str(e)
        raise RuntimeError(f"msi2namd failed with exit code {e.returncode}: {msg.strip()}") from e

    out_pdb = work_dir / f"{name}.pdb"
    out_psf = work_dir / f"{name}.psf"
    if not out_pdb.exists() or out_pdb.stat().st_size == 0:
        raise RuntimeError(f"Expected output not created or empty: {out_pdb}")
    if not out_psf.exists() or out_psf.stat().st_size == 0:
        raise RuntimeError(f"Expected output not created or empty: {out_psf}")

    # Adapter-conformant result envelope with back-compat aliases
    tool_version = get_tool_version(str(exe))
    result = ExternalToolResult(
        tool="msi2namd",
        argv=cmd,
        cwd=str(work_dir),
        duration_s=float(duration),
        stdout=stdout or "",
        stderr=stderr or "",
        outputs={
            "pdb_file": str(out_pdb),
            "psf_file": str(out_psf),
        },
        tool_version=tool_version,
    )
    d = result.to_dict()
    # Convenience aliases preserved for existing callers
    d["pdb_file"] = str(out_pdb)
    d["psf_file"] = str(out_psf)
    return d
