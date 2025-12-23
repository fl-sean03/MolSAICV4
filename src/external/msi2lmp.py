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

import logging
import shutil
import subprocess
from pathlib import Path

from .adapter import ExternalToolResult, get_tool_version

# Import from private modules
from ._msi2lmp_helpers import (
    ensure_file as _ensure_file,
    stage_file as _stage_file,
    sha256_file as _sha256_file,
    write_result_json as _write_result_json,
)
from ._msi2lmp_argv import (
    frc_looks_cvff_labeled as _frc_looks_cvff_labeled,
    build_msi2lmp_argv as _build_msi2lmp_argv,
    augment_env as _augment_env,
    run_command as _run,
)
from ._lmp_normalize import (
    parse_abc_from_car as _parse_abc_from_car,
    normalize_data_file as _normalize_data_file,
)

logger = logging.getLogger(__name__)


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
    forcefield_class: str | None = None,
    use_f_flag: bool | None = None,
    ignore: bool = False,
    print_level: int | None = None,
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

    # NOTE: observed usage variants for msi2lmp.exe in this repo:
    # - legacy: `msi2lmp.exe <rootname> -f <forcefield_basename>`
    # - modern: `msi2lmp.exe <rootname> -class I -frc <relative_path>`
    # Some builds are sensitive to CVFF-style headers/labels.
    # Default behavior: auto-detect based on `.frc` content.

    cmd = _build_msi2lmp_argv(
        exe=exe,
        base_stem=base_stem,
        wd=wd,
        staged_frc=staged_frc,
        forcefield_class=forcefield_class,
        use_f_flag=use_f_flag,
        ignore=bool(ignore),
        print_level=print_level,
    )
    env = _augment_env(str(exe))

    try:
        duration, stdout, stderr = _run(cmd, cwd=wd, env=env, timeout_s=timeout_s)
    except subprocess.TimeoutExpired as e:
        # Persist stdout/stderr deterministically even on timeout so workspaces have diagnostics.
        # Note: TimeoutExpired uses .stdout/.stderr on py3.11+; fall back to .output.
        def _to_text(x) -> str:
            if x is None:
                return ""
            if isinstance(x, bytes):
                return x.decode("utf-8", errors="replace")
            return str(x)

        stdout_raw = None
        stderr_raw = None
        try:
            stdout_raw = e.stdout if getattr(e, "stdout", None) is not None else getattr(e, "output", None)
        except Exception:
            stdout_raw = None
        try:
            stderr_raw = getattr(e, "stderr", None)
        except Exception:
            stderr_raw = None

        stdout_text = _to_text(stdout_raw)
        stderr_text = _to_text(stderr_raw)

        stdout_path.write_text(stdout_text, encoding="utf-8")
        stderr_path.write_text(stderr_text, encoding="utf-8")

        # Write deterministic result.json for parity with missing-tool and ok paths.
        tool_version = get_tool_version(str(exe))
        result = ExternalToolResult(
            tool="msi2lmp",
            argv=cmd,
            cwd=str(wd),
            duration_s=float(timeout_s),
            stdout=stdout_text,
            stderr=stderr_text,
            outputs={
                "stdout_file": str(stdout_path),
                "stderr_file": str(stderr_path),
            },
            status="timeout",
            outputs_sha256={
                "stdout_file": _sha256_file(stdout_path),
                "stderr_file": _sha256_file(stderr_path),
            },
            tool_version=tool_version,
            warnings=[f"timeout after {int(timeout_s)}s"],
        )
        d = result.to_dict()
        result_json = _write_result_json(wd, d)
        d["outputs"]["result_json"] = str(result_json)
        # Re-write so on-disk result.json matches the returned envelope (including result_json path)
        result_json = _write_result_json(wd, d)
        d["outputs"]["result_json"] = str(result_json)

        raise RuntimeError(
            f"msi2lmp timed out after {timeout_s}s\n(see {stdout_path} and {stderr_path})"
        ) from e
    except subprocess.CalledProcessError as e:
        # Persist stdout/stderr deterministically even on failure so workspaces have diagnostics.
        stdout_text = e.stdout or ""
        stderr_text = e.stderr or ""
        stdout_path.write_text(stdout_text, encoding="utf-8")
        stderr_path.write_text(stderr_text, encoding="utf-8")

        # Also persist result.json for deterministic manifests/debugging.
        tool_version = get_tool_version(str(exe))
        result = ExternalToolResult(
            tool="msi2lmp",
            argv=cmd,
            cwd=str(wd),
            duration_s=0.0,
            stdout=stdout_text,
            stderr=stderr_text,
            outputs={
                "stdout_file": str(stdout_path),
                "stderr_file": str(stderr_path),
            },
            status="error",
            outputs_sha256={
                "stdout_file": _sha256_file(stdout_path),
                "stderr_file": _sha256_file(stderr_path),
            },
            tool_version=tool_version,
            warnings=[f"exit_code={e.returncode}"],
        )
        d = result.to_dict()
        result_json = _write_result_json(wd, d)
        d["outputs"]["result_json"] = str(result_json)
        result_json = _write_result_json(wd, d)
        d["outputs"]["result_json"] = str(result_json)

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
