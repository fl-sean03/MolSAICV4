"""Deterministic wrapper for the external 'msi2lmp' executable.

This module provides a thin wrapper around 'msi2lmp' to convert Accelrys/MSI
CAR/MDF inputs into a LAMMPS data file.

Contract compliance (v0.1.1):
- Returns a deterministic result envelope aligned with
  [`ExternalToolResult.to_dict()`](src/external/adapter.py:77), including stable
  `status` and `outputs_sha256`.
- Deterministic CWD:
  - Prefer explicit `work_dir` when provided
  - Else derive from `output_prefix` parent
  - Else fall back to the CAR/MDF directory
- Writes stdout/stderr to files in `work_dir` (`stdout.txt`, `stderr.txt`) and
  includes the captured text in the envelope.
- Validates expected outputs exist and are non-empty; computes sha256 for outputs.
- Always writes `result.json` into `work_dir` for stable workspace manifests.
- Missing tool behavior: if the executable is missing, do not raise; instead
  create `work_dir`, write `result.json` with `status: missing_tool`, and return
  the envelope (no LAMMPS data output).

Post-processing:
- Optional header normalization supports:
  - XY normalization to [0,a]/[0,b] using CAR PBC when requested
  - Z header normalization to [0, normalize_z_to or CAR PBC c]
  - Optional Z coordinate normalization:
    - legacy: uniform atom Z shift so min(z)=0
    - centering: uniform atom Z shift so the structure midpoint (zmin+zmax)/2 maps to z_target/2
      (centering takes precedence over legacy shifting)
"""

from __future__ import annotations

import filecmp
import hashlib
import json
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
        encoding="utf-8",
        errors="replace",
        timeout=timeout_s,
        check=True,
    )
    return (time.perf_counter() - t0, proc.stdout, proc.stderr)


def _ensure_file(f: Path) -> None:
    if not f.exists() or not f.is_file():
        raise FileNotFoundError(f"File not found: {f}")


def _stage_file(src_path: Path, work_dir: Path) -> Path:
    """Ensure src_path is present in work_dir; copy only if needed; return destination path."""
    src = Path(src_path).resolve()
    _ensure_file(src)
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


def _sha256_file(p: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_result_json(work_dir: Path, envelope: dict) -> Path:
    """Write deterministic result.json (sorted keys + newline) into work_dir."""
    work_dir.mkdir(parents=True, exist_ok=True)
    out = work_dir / "result.json"
    out.write_text(json.dumps(envelope, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out


def run(
    base_name: str,
    frc_file: str,
    exe_path: str,
    output_prefix: str,
    normalize_xy: bool = True,
    normalize_z_to: float | None = None,
    normalize_z_shift: bool = True,
    normalize_z_center: bool = False,
    timeout_s: int = 600,
    work_dir: str | None = None,
) -> dict:
    """Run msi2lmp to produce a LAMMPS .data file.

    Parameters:
    - base_name: path to the CAR/MDF base (without extension) or either .car/.mdf path
    - frc_file: path to the .frc forcefield file
    - exe_path: path to the msi2lmp executable
    - output_prefix: target basename (may include directory) for the resulting .data
    - normalize_xy: normalize x/y header extents using CAR PBC a/b when available
    - normalize_z_to: if provided, normalize header 'zlo zhi' to 0.0 and this value
    - normalize_z_shift: if True, uniformly shift atom Z so min(z)=0 during post-processing (legacy behavior)
    - normalize_z_center: if True, uniformly shift atom Z so the midpoint (zmin+zmax)/2 maps to z_target/2.
      This takes precedence over normalize_z_shift (they are mutually exclusive; centering wins).
    - timeout_s: seconds before the process is terminated
    - work_dir: optional explicit working directory to run within (deterministic)

    Returns:
    - ExternalToolResult.to_dict() (plus back-compat alias 'lmp_data_file')

    Raises:
    - FileNotFoundError (inputs missing), RuntimeError (tool fails / output missing)
      NOTE: missing executable does NOT raise; returns status=missing_tool.
    """
    exe = Path(exe_path).resolve()

    base = Path(base_name).resolve()
    base_dir = base.parent
    base_stem = base.stem

    src_car = base_dir / f"{base_stem}.car"
    src_mdf = base_dir / f"{base_stem}.mdf"
    _ensure_file(src_car)
    _ensure_file(src_mdf)

    frc_abs = Path(frc_file).resolve()
    _ensure_file(frc_abs)

    # Deterministic workdir selection
    if work_dir:
        wd = Path(work_dir).resolve()
    elif output_prefix:
        wd = Path(output_prefix).resolve().parent
    else:
        wd = base_dir
    wd.mkdir(parents=True, exist_ok=True)

    # Prepare deterministic stdout/stderr capture files
    stdout_path = wd / "stdout.txt"
    stderr_path = wd / "stderr.txt"

    # Missing-tool behavior: create workdir + write result.json + return envelope without raising
    if not exe.exists() or not exe.is_file():
        stderr_text = f"Executable not found: {exe}"
        stdout_text = ""
        stdout_path.write_text(stdout_text, encoding="utf-8")
        stderr_path.write_text(stderr_text + "\n", encoding="utf-8")

        argv = [str(exe)]
        result = ExternalToolResult(
            tool="msi2lmp",
            argv=argv,
            cwd=str(wd),
            duration_s=0.0,
            stdout=stdout_text,
            stderr=stderr_text,
            outputs={
                "stdout_file": str(stdout_path),
                "stderr_file": str(stderr_path),
            },
            status="missing_tool",
            outputs_sha256={},
            tool_version="unknown",
            warnings=[],
        )
        d = result.to_dict()
        # Persist envelope deterministically
        result_json = _write_result_json(wd, d)
        d["outputs"]["result_json"] = str(result_json)
        d["outputs_sha256"] = {
            **d.get("outputs_sha256", {}),
            "stdout_file": _sha256_file(stdout_path),
            "stderr_file": _sha256_file(stderr_path),
        }
        # Re-write so on-disk result.json matches the returned envelope
        result_json = _write_result_json(wd, d)
        d["outputs"]["result_json"] = str(result_json)
        return d

    # Stage inputs into deterministic workdir so cwd is stable (and tool writes outputs there)
    staged_car = _stage_file(src_car, wd)
    staged_mdf = _stage_file(src_mdf, wd)
    base_stem = staged_car.stem  # prefer CAR stem

    out_name = Path(output_prefix).name if output_prefix else base_stem

    # NOTE: msi2lmp has legacy behavior where it may try to open forcefields from
    # "../frc_files/<frc_filename>" relative to its CWD, even if an absolute path is provided.
    # To be robust/deterministic, always stage the frc into that location as well, and pass the
    # basename to match the tool's expectation.
    frc_dir = wd.parent / "frc_files"
    frc_dir.mkdir(parents=True, exist_ok=True)
    staged_frc = _stage_file(frc_abs, frc_dir)

    cmd = [str(exe), base_stem, "-f", staged_frc.name]
    env = _augment_env(str(exe))

    try:
        duration, stdout, stderr = _run(cmd, cwd=wd, env=env, timeout_s=timeout_s)
    except subprocess.CalledProcessError as e:
        # Persist stdout/stderr deterministically even on failure so workspaces have diagnostics.
        stdout_text = e.stdout or ""
        stderr_text = e.stderr or ""
        stdout_path.write_text(stdout_text, encoding="utf-8")
        stderr_path.write_text(stderr_text, encoding="utf-8")

        # Provide a concise error message but point to the persisted logs for full context.
        msg = (stderr_text.strip() or stdout_text.strip() or str(e)).strip()
        raise RuntimeError(
            f"msi2lmp failed with exit code {e.returncode}: {msg}\n"
            f"(see {stdout_path} and {stderr_path})"
        ) from e

    stdout_text = stdout or ""
    stderr_text = stderr or ""
    stdout_path.write_text(stdout_text, encoding="utf-8")
    stderr_path.write_text(stderr_text, encoding="utf-8")

    data_in = wd / f"{base_stem}.data"
    if not data_in.exists() or data_in.stat().st_size == 0:
        raise RuntimeError(f"Expected msi2lmp output not created or empty: {data_in}")

    # Determine output destination (always within workdir to keep artifacts colocated)
    data_out = wd / f"{out_name}.data"

    # IMPORTANT: if out_name == base_stem, data_out == data_in.
    # Do NOT unlink in that case, or we'd delete the freshly created output.
    if data_in.resolve() != data_out.resolve():
        if data_out.exists():
            data_out.unlink()
        shutil.move(str(data_in), str(data_out))

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

        def _normalize_data_file(
            data_path: Path,
            a_dim,
            b_dim,
            do_xy: bool,
            z_target,
            do_z_shift: bool,
            do_z_center: bool,
        ):
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

                # Pass 2 (optional): rewrite atoms lines with uniformly shifted z.
                # Precedence: centering wins over legacy min(z)=0 shifting.
                z_shift = None
                if do_z_center:
                    if z_target is not None and z_min != float("inf") and z_max != -float("inf"):
                        z_mid = 0.5 * (z_min + z_max)
                        z_shift = 0.5 * float(z_target) - z_mid
                elif do_z_shift:
                    if z_min != float("inf"):
                        z_shift = -z_min

                if z_shift is not None:
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
                        parts[z_index] = _fmt(z_val + float(z_shift))
                        new_left = " ".join(parts)
                        # Ensure a space before '#' so image flags and comments don't merge
                        lines[j] = (new_left + (" " + sep + comment if sep else "")).rstrip()

                # Update Z header:
                # - If z_target is provided, always normalize header to [0, z_target]
                # - Else if we performed a legacy z-shift, normalize to [0, span]
                # - Else leave header unchanged
                if z_idx is not None and (z_target is not None or (do_z_shift and not do_z_center)):
                    if z_target is None:
                        zhi_val = (z_max - z_min) if (z_min != float("inf") and z_max != -float("inf")) else None
                    else:
                        zhi_val = float(z_target)
                    if zhi_val is not None:
                        lines[z_idx] = f"0.000000 {_fmt(zhi_val)} zlo zhi"

            # Write back
            with open(data_path, "w", encoding="utf-8") as outfh:
                outfh.write("\n".join(lines) + "\n")

        a_dim, b_dim, c_dim = _parse_abc_from_car(staged_car)
        z_target = normalize_z_to if normalize_z_to is not None else c_dim

        do_z_center = bool(normalize_z_center)
        if do_z_center and z_target is None:
            logger.warning(
                "normalize_z_center=True but z_target is unknown (no normalize_z_to and CAR PBC c not parsed); skipping Z-centering."
            )
            do_z_center = False

        # Precedence: centering wins over legacy shifting
        do_z_shift = bool(normalize_z_shift) and (not do_z_center)

        _normalize_data_file(
            data_out,
            a_dim,
            b_dim,
            bool(normalize_xy),
            z_target,
            do_z_shift,
            do_z_center,
        )
        logger.info(
            "Applied post-msi2lmp normalization to LAMMPS .data (header; Z shift=%s; Z center=%s).",
            bool(do_z_shift),
            bool(do_z_center),
        )
    except Exception as _:
        # Do not fail the overall run on normalization issues in this subtask
        pass

    # Adapter-conformant result envelope with back-compat alias + deterministic artifacts
    tool_version = get_tool_version(str(exe))

    outputs = {
        "lmp_data_file": str(data_out),
        "stdout_file": str(stdout_path),
        "stderr_file": str(stderr_path),
    }
    outputs_sha256 = {
        "lmp_data_file": _sha256_file(data_out),
        "stdout_file": _sha256_file(stdout_path),
        "stderr_file": _sha256_file(stderr_path),
    }

    result = ExternalToolResult(
        tool="msi2lmp",
        argv=cmd,
        cwd=str(wd),
        duration_s=float(duration),
        stdout=stdout_text,
        stderr=stderr_text,
        outputs=outputs,
        status="ok",
        outputs_sha256=outputs_sha256,
        tool_version=tool_version,
        warnings=[],
    )
    d = result.to_dict()

    # Preserve top-level alias for existing callers
    d["lmp_data_file"] = str(data_out)

    # Persist deterministic result.json (and surface it in outputs)
    result_json = _write_result_json(wd, d)
    d["outputs"]["result_json"] = str(result_json)

    # Re-write so on-disk result.json matches the returned envelope (including result_json path)
    result_json = _write_result_json(wd, d)
    d["outputs"]["result_json"] = str(result_json)

    return d
