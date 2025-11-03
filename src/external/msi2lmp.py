"""Deterministic wrapper for the external 'msi2lmp' executable.

This module provides a thin wrapper around 'msi2lmp' to convert Accelrys/MSI
CAR/MDF inputs into a LAMMPS data file.

Determinism and assumptions:
- 'base_name' points to the CAR/MDF basename (without extension) or either file
  path; the working directory is the parent directory of that path.
- The PATH is augmented so the dynamic linker can resolve adjacent libraries.
- Execution enforces a timeout and raises on failure.
- The produced '.data' file is validated (existence and non-empty).
- If 'output_prefix' is provided, the produced '.data' is moved/renamed to
  the file '{Path(output_prefix).name}.data' within its parent directory.
- Optional post-processing supports header-only Z-range normalization (zlo/zhi).
  NOTE: Atom coordinates are NOT modified in this subtask (header-only).

Return value:
- Dict with keys:
  - 'lmp_data_file': absolute path to the generated .data file
  - 'duration_s': wall-clock seconds (float)
  - 'stdout': process stdout (string)
  - 'stderr': process stderr (string)

Exceptions:
- FileNotFoundError: if any required file (exe, inputs) is missing.
- RuntimeError: if the external process fails or expected outputs are missing.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
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


def run(
    base_name: str,
    frc_file: str,
    exe_path: str,
    output_prefix: str,
    normalize_xy: bool = True,
    normalize_z_to: float | None = None,
    timeout_s: int = 600,
) -> dict:
    """Run msi2lmp to produce a LAMMPS .data file.

    Parameters:
    - base_name: path to the CAR/MDF base (without extension) or either .car/.mdf path
    - frc_file: path to the .frc forcefield file
    - exe_path: path to the msi2lmp executable
    - output_prefix: target basename (may include directory) for the resulting .data
    - normalize_xy: reserved for future use (no-op in this subtask)
    - normalize_z_to: if provided, set header 'zlo zhi' to 0.0 and this value (header-only)
    - timeout_s: seconds before the process is terminated

    Returns:
    - dict with keys: 'lmp_data_file', 'duration_s', 'stdout', 'stderr'

    Raises:
    - FileNotFoundError, RuntimeError
    """
    exe = Path(exe_path).resolve()
    if not exe.exists() or not exe.is_file():
        raise FileNotFoundError(f"Executable not found: {exe}")

    base = Path(base_name).resolve()
    base_dir = base.parent
    base_stem = base.stem

    car_path = base_dir / f"{base_stem}.car"
    mdf_path = base_dir / f"{base_stem}.mdf"
    _ensure_file(car_path)
    _ensure_file(mdf_path)

    frc_abs = Path(frc_file).resolve()
    _ensure_file(frc_abs)

    cmd = [str(exe), base_stem, "-f", str(frc_abs)]
    env = _augment_env(str(exe))

    try:
        duration, stdout, stderr = _run(cmd, cwd=base_dir, env=env, timeout_s=timeout_s)
    except subprocess.CalledProcessError as e:
        msg = e.stderr or e.stdout or str(e)
        raise RuntimeError(f"msi2lmp failed with exit code {e.returncode}: {msg.strip()}") from e

    data_in = base_dir / f"{base_stem}.data"
    if not data_in.exists() or data_in.stat().st_size == 0:
        raise RuntimeError(f"Expected msi2lmp output not created or empty: {data_in}")

    # Determine output destination
    if output_prefix:
        dest_dir = Path(output_prefix).resolve().parent
        dest_dir.mkdir(parents=True, exist_ok=True)
        out_name = Path(output_prefix).name
        data_out = dest_dir / f"{out_name}.data"
        # Overwrite if exists
        if data_out.exists():
            data_out.unlink()
        shutil.move(str(data_in), str(data_out))
    else:
        data_out = data_in

    # Post-process header to match legacy behavior:
    # - Normalize XY header to [0,a]/[0,b] using CAR PBC values when requested.
    # - Normalize Z header to [0,z_target] (use provided normalize_z_to or CAR PBC c if available).
    # - Uniformly shift atom Z so min(z)=0 (parity with legacy).
    try:
        import re as _re

        def _parse_abc_from_car(p: Path):
            a = b = c = None
            try:
                with open(p, "r", encoding="utf-8", errors="ignore") as fh:
                    for line in fh:
                        s = line.strip()
                        if s.upper().startswith("PBC") and "=" not in s.upper():
                            nums = _re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", s)
                            if len(nums) >= 3:
                                a = float(nums[0]); b = float(nums[1]); c = float(nums[2])
                                break
            except Exception:
                pass
            return a, b, c

        def _normalize_data_file(data_path: Path, a_dim, b_dim, do_xy: bool, z_target):
            def _fmt(x: float) -> str:
                return f"{x:.6f}"

            # Read file
            with open(data_path, "r", encoding="utf-8", errors="ignore") as fh:
                lines = fh.read().splitlines()

            # Find header bounds and indices
            x_idx = y_idx = z_idx = None
            atoms_header_idx = None
            for i, line in enumerate(lines[:300]):
                if _re.search(r"\bxlo\s+xhi\b", line):
                    x_idx = i
                elif _re.search(r"\bylo\s+yhi\b", line):
                    y_idx = i
                elif _re.search(r"\bzlo\s+zhi\b", line):
                    z_idx = i
                if atoms_header_idx is None and _re.match(r"^\s*Atoms\b", line):
                    atoms_header_idx = i

            # Update XY header extents
            if do_xy:
                if a_dim is not None and x_idx is not None:
                    lines[x_idx] = f"0.000000 {_fmt(a_dim)} xlo xhi"
                if b_dim is not None and y_idx is not None:
                    lines[y_idx] = f"0.000000 {_fmt(b_dim)} ylo yhi"

            # Identify Atoms section range
            if atoms_header_idx is not None:
                start = atoms_header_idx + 1
                while start < len(lines) and (lines[start].strip() == "" or lines[start].lstrip().startswith("#")):
                    start += 1
                end = start
                section_header_pat = _re.compile(r"^(Bonds|Angles|Dihedrals|Impropers|Velocities|Masses|Pair Coeffs|Bond Coeffs|Angle Coeffs|Dihedral Coeffs|Improper Coeffs)\b", _re.IGNORECASE)
                while end < len(lines):
                    s = lines[end].strip()
                    if s != "" and section_header_pat.match(s):
                        break
                    end += 1

                # Determine atom style (from header comment, e.g., 'Atoms # full')
                style = "unknown"
                m = _re.search(r"^\s*Atoms\s*(?:#\s*(\w+))?", lines[atoms_header_idx])
                if m and m.group(1):
                    style = m.group(1).strip().lower()

                def _extract_xyz_tokens(parts: list[str]):
                    try:
                        if style == "full":
                            x_i, y_i, z_i = 4, 5, 6
                        elif style == "molecular":
                            x_i, y_i, z_i = 3, 4, 5
                        elif style == "atomic":
                            x_i, y_i, z_i = 2, 3, 4
                        else:
                            # Fallback: last three numeric tokens
                            z_i = y_i = x_i = None
                            count = 0
                            for idx in range(len(parts) - 1, -1, -1):
                                tok = parts[idx]
                                if _re.match(r"^[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?$", tok):
                                    count += 1
                                    if count == 1:
                                        z_i = idx
                                    elif count == 2:
                                        y_i = idx
                                    elif count == 3:
                                        x_i = idx
                                        break
                            if x_i is None or y_i is None or z_i is None:
                                return None, None, None, None
                        return float(parts[x_i]), float(parts[y_i]), float(parts[z_i]), z_i
                    except Exception:
                        return None, None, None, None

                # Pass 1: compute z_min and z_max
                z_min = float("inf")
                z_max = -float("inf")
                for j in range(start, end):
                    line = lines[j]
                    left = line.split("#", 1)[0].strip()
                    if not left:
                        continue
                    parts = left.split()
                    _, _, z_val, _ = _extract_xyz_tokens(parts)
                    if z_val is None:
                        continue
                    if z_val < z_min:
                        z_min = z_val
                    if z_val > z_max:
                        z_max = z_val

                # Pass 2: rewrite atoms lines with shifted z (uniform shift so min(z)=0)
                if z_min != float("inf"):
                    z_shift = -z_min
                    for j in range(start, end):
                        original = lines[j]
                        head, sep, comment = original.partition("#")
                        left = head.strip()
                        if not left:
                            continue
                        parts = left.split()
                        _, _, z_val, z_index = _extract_xyz_tokens(parts)
                        if z_index is None or z_val is None:
                            lines[j] = original.rstrip()
                            continue
                        parts[z_index] = _fmt(z_val + z_shift)
                        new_left = " ".join(parts)
                        # Ensure a space before '#' so image flags and comments don't merge
                        lines[j] = (new_left + (" " + sep + comment if sep else "")).rstrip()

                # Update Z header
                if z_idx is not None:
                    # prefer explicit target; else use span after shift
                    if z_target is None:
                        zhi_val = (z_max - z_min) if (z_min != float("inf") and z_max != -float("inf")) else None
                    else:
                        zhi_val = float(z_target)
                    if zhi_val is not None:
                        lines[z_idx] = f"0.000000 {_fmt(zhi_val)} zlo zhi"

            # Write back
            with open(data_path, "w", encoding="utf-8") as outfh:
                outfh.write("\n".join(lines) + "\n")

        a_dim, b_dim, c_dim = _parse_abc_from_car(car_path)
        z_target = normalize_z_to if normalize_z_to is not None else c_dim
        _normalize_data_file(data_out, a_dim, b_dim, bool(normalize_xy), z_target)
        logger.info("Applied post-msi2lmp normalization to LAMMPS .data (header and Z shift).")
    except Exception as _:
        # Do not fail the overall run on normalization issues in this subtask
        pass

    # Adapter-conformant result envelope with back-compat alias
    tool_version = get_tool_version(str(exe))
    result = ExternalToolResult(
        tool="msi2lmp",
        argv=cmd,
        cwd=str(base_dir),
        duration_s=float(duration),
        stdout=stdout or "",
        stderr=stderr or "",
        outputs={"lmp_data_file": str(data_out)},
        tool_version=tool_version,
    )
    d = result.to_dict()
    # Preserve top-level alias for existing callers
    d["lmp_data_file"] = str(data_out)
    return d
