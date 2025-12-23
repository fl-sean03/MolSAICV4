"""Argument building and command execution for msi2lmp wrapper.

Private module containing argv construction, CVFF detection, and subprocess execution.
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from .adapter import augment_env_with_exe_dir


def frc_looks_cvff_labeled(frc_path: Path, max_lines: int = 200) -> bool:
    """Heuristic to decide if an .frc appears CVFF-labeled.

    Some `msi2lmp.exe` builds expect CVFF-labeled section headers like
    `#atom_types\tcvff` and/or a `#define cvff` header.

    We only scan the first N lines for determinism and speed.
    """
    try:
        with open(frc_path, "r", encoding="utf-8", errors="ignore") as fh:
            for i, line in enumerate(fh):
                if i >= max_lines:
                    break
                s = line.strip().lower()
                if not s:
                    continue
                # Common CVFF markers
                if "#define" in s and "cvff" in s:
                    return True
                if s.startswith("#atom_types") and "cvff" in s:
                    return True
                if s.startswith("#nonbond(12-6)") and "cvff" in s:
                    return True
    except Exception:
        return False
    return False


def build_msi2lmp_argv(
    *,
    exe: Path,
    base_stem: str,
    wd: Path,
    staged_frc: Path,
    forcefield_class: str | None,
    use_f_flag: bool | None,
    ignore: bool,
    print_level: int | None,
) -> list[str]:
    """Build msi2lmp argv in a deterministic, backward-compatible way.

    Selection precedence:
    - If use_f_flag is True: legacy `-f <frc_stem>`; do not pass `-class`.
    - If use_f_flag is False: modern `-class <X> -frc <relpath>`.
    - If use_f_flag is None:
        - If forcefield_class is not None: modern `-class forcefield_class -frc <relpath>`.
        - Else auto-detect by FRC content:
            - CVFF-labeled => modern `-class I -frc <relpath>`
            - otherwise => legacy `-f <frc_stem>`

    Diagnostics flags are opt-in and inserted deterministically:
    `-ignore` then `-print N`.
    """

    # --- Choose invocation mode ---
    if use_f_flag is True:
        mode = "legacy"
    elif use_f_flag is False:
        mode = "modern"
    else:
        if forcefield_class is not None:
            mode = "modern"
        else:
            mode = "modern" if frc_looks_cvff_labeled(staged_frc) else "legacy"

    # --- Build argv ---
    cmd: list[str] = [str(exe), str(base_stem)]

    # Diagnostics (opt-in; stable ordering)
    if ignore:
        cmd.append("-ignore")
    if print_level is not None:
        cmd += ["-print", str(int(print_level))]

    if mode == "legacy":
        # Some builds expect a *forcefield base name* here (no extension).
        cmd += ["-f", str(staged_frc.stem)]
        return cmd

    # Modern mode
    ff_class = forcefield_class if forcefield_class is not None else "I"
    frc_rel = os.path.relpath(str(staged_frc), start=str(wd))
    cmd += ["-class", str(ff_class), "-frc", str(frc_rel)]
    return cmd


def augment_env(exe_path: str) -> dict:
    """Delegate to shared adapter helper for PATH augmentation."""
    return augment_env_with_exe_dir(exe_path)


def run_command(cmd: list[str], cwd: Path, env: dict, timeout_s: int) -> tuple[float, str, str]:
    """Run a command with deterministic cwd/env/timeout. Raises CalledProcessError on nonzero exit."""
    t0 = time.perf_counter()
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        env=env,
        # Hardening: prevent the external tool from blocking on stdin (observed as
        # deterministic stalls/hangs in some environments).
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_s,
        check=True,
    )
    return (time.perf_counter() - t0, proc.stdout, proc.stderr)
