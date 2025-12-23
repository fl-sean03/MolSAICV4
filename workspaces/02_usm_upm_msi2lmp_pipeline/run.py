#!/usr/bin/env python3
"""
Golden workspace (v0.1.1): USM (CAR+MDF) -> requirements.json -> UPM minimal .frc -> msi2lmp wrapper -> run_manifest.json

Determinism contract:
- All artifacts live under outputs_dir (default: ./outputs).
- run_manifest.json contains ONLY relative paths (relative to outputs_dir) + sha256 + tool versions + external status.
- No timestamps, durations, or absolute paths in run_manifest.json.

Run:
  python run.py --config config.json
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Minimal bootstrap (supports direct execution without editable install)
# ---------------------------------------------------------------------------


def _bootstrap_repo_src_on_path(start_dir: Path) -> Path:
    """
    Walk upward until pyproject.toml is found, then ensure:
      - <repo_root>/src is on sys.path (molsaic + external + usm)
      - <repo_root>/src/upm/src is on sys.path (upm standalone package)
    Returns discovered repo_root.
    """
    p = start_dir.resolve()
    for cand in (p, *p.parents):
        if (cand / "pyproject.toml").is_file():
            src_root = cand / "src"
            upm_src_root = cand / "src" / "upm" / "src"

            # IMPORTANT: always prefer repo-local sources over any installed packages.
            # Mirror the precedence behavior used by newer workspaces.
            src_root_s = str(src_root)
            if src_root_s in sys.path:
                sys.path.remove(src_root_s)
            sys.path.insert(0, src_root_s)

            if upm_src_root.is_dir():
                upm_src_root_s = str(upm_src_root)
                if upm_src_root_s in sys.path:
                    sys.path.remove(upm_src_root_s)
                sys.path.insert(0, upm_src_root_s)
            return cand
    raise RuntimeError(f"Could not locate repo root (pyproject.toml) starting from: {start_dir}")


WORKSPACE_DIR = Path(__file__).resolve().parent
_bootstrap_repo_src_on_path(WORKSPACE_DIR)

from molsaic.workspaces import find_repo_root  # noqa: E402
from molsaic.manifest_utils import (  # noqa: E402
    get_runtime_versions,
    sha256_file,
    write_json_stable,
    relpath_posix,
)
from usm.io import load_car, load_mdf  # noqa: E402
from usm.ops.requirements import write_requirements_json  # noqa: E402

from external import msi2lmp  # noqa: E402

from upm.codecs.msi_frc import read_frc, write_frc  # noqa: E402
from upm.bundle.io import save_package, load_package  # noqa: E402
from upm.io.requirements import read_requirements_json  # noqa: E402
from upm.core.resolve import resolve_minimal  # noqa: E402


REPO_ROOT = find_repo_root(start=WORKSPACE_DIR)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _read_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def _to_abs(base: Path, maybe_rel: str | Path) -> Path:
    pp = Path(maybe_rel)
    return pp if pp.is_absolute() else (base / pp).resolve()


def _ensure_file(p: Path, note: str = "") -> None:
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(f"Missing file: {p} {f'({note})' if note else ''}")


def _validate_nonempty(p: Path, note: str = "") -> None:
    if (not p.exists()) or p.stat().st_size == 0:
        raise RuntimeError(f"Expected output not created or empty: {p} {f'({note})' if note else ''}")


def _copy_exact(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(src), str(dest))


def _manifest_entry(path: Path, *, base_dir: Path) -> dict[str, str]:
    return {"path": relpath_posix(path, base_dir=base_dir), "sha256": sha256_file(path)}


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Golden USM->UPM->msi2lmp workspace (v0.1.1).")
    ap.add_argument("--config", type=str, default="config.json", help="Path to workspace config.json")
    args = ap.parse_args(argv)

    cfg_path = _to_abs(WORKSPACE_DIR, args.config)
    _ensure_file(cfg_path, "workspace config")
    cfg = _read_json(cfg_path)

    outputs_dir = _to_abs(WORKSPACE_DIR, cfg.get("outputs_dir", "outputs"))
    outputs_dir.mkdir(parents=True, exist_ok=True)

    # Stage all inputs into outputs_dir so run_manifest contains only relpaths under outputs_dir.
    staged_inputs_dir = outputs_dir / "inputs"
    staged_inputs_dir.mkdir(parents=True, exist_ok=True)

    car_src = _to_abs(WORKSPACE_DIR, cfg["inputs"]["car"])
    mdf_src = _to_abs(WORKSPACE_DIR, cfg["inputs"]["mdf"])
    frc_src = _to_abs(WORKSPACE_DIR, cfg["inputs"]["source_frc"])
    _ensure_file(car_src, "CAR input")
    _ensure_file(mdf_src, "MDF input")
    _ensure_file(frc_src, "source .frc input")

    car_in = staged_inputs_dir / "MXN.car"
    mdf_in = staged_inputs_dir / "MXN.mdf"
    frc_in = staged_inputs_dir / "source.frc"
    _copy_exact(car_src, car_in)
    _copy_exact(mdf_src, mdf_in)
    _copy_exact(frc_src, frc_in)

    # --- 1) Load USM (CAR+MDF) ---
    # NOTE: for v0.1.1 requirements we only need atom_type + bonds; MDF is authoritative.
    # We still load CAR for sanity (coordinates present), but requirements are derived from MDF.
    _ = load_car(str(car_in))
    usm_topo = load_mdf(str(mdf_in))

    # --- 2) requirements.json ---
    req_path = outputs_dir / "requirements.json"
    write_requirements_json(usm_topo, req_path)
    _validate_nonempty(req_path, "requirements.json")

    # --- 3) UPM package import (into outputs_dir/packages/...) ---
    pkg_root = outputs_dir / "packages" / "cvff_IFF_metal_oxides_v2" / "v0"
    source_text = frc_in.read_text(encoding="utf-8")
    tables, unknown_sections = read_frc(frc_in)
    save_package(
        pkg_root,
        name="cvff_IFF_metal_oxides_v2",
        version="v0",
        tables=tables,
        source_text=source_text,
        unknown_sections=unknown_sections,
    )
    bundle = load_package(pkg_root)

    # --- 4) Resolve + export minimal .frc ---
    params = cfg.get("params", {}) or {}
    include_raw = bool(params.get("upm_include_raw", False))
    allow_missing = bool(params.get("upm_allow_missing", False))

    req = read_requirements_json(req_path)
    resolved_res = resolve_minimal(bundle.tables, req, allow_missing=allow_missing)
    if allow_missing:
        resolved, _missing = resolved_res  # type: ignore[misc]
    else:
        resolved = resolved_res  # type: ignore[assignment]

    tables_subset: dict[str, object] = {"atom_types": resolved.atom_types}
    if resolved.bonds is not None:
        tables_subset["bonds"] = resolved.bonds
    if resolved.angles is not None:
        tables_subset["angles"] = resolved.angles

    ff_min_path = outputs_dir / "ff_minimal.frc"
    write_frc(
        ff_min_path,
        tables=tables_subset,
        unknown_sections=bundle.raw.get("unknown_sections", []),
        include_raw=include_raw,
        mode="minimal",
    )
    _validate_nonempty(ff_min_path, "ff_minimal.frc")

    # --- 5) External: msi2lmp wrapper (always called; wrapper returns missing_tool if exe missing) ---
    # Prefer an explicit path from config; otherwise try PATH; if not found,
    # fall back to a non-existent resolved path so the wrapper returns status=missing_tool.
    exe_cfg = (cfg.get("executables") or {}).get("msi2lmp")

    from external.adapter import resolve_executable  # noqa: E402

    try:
        exe_path = resolve_executable(
            str(exe_cfg) if isinstance(exe_cfg, str) and str(exe_cfg).strip() else None,
            "msi2lmp",
            search_dirs=[WORKSPACE_DIR, REPO_ROOT],
        )
    except FileNotFoundError:
        fallback = str(exe_cfg).strip() if isinstance(exe_cfg, str) and str(exe_cfg).strip() else "msi2lmp"
        exe_path = str(Path(fallback).resolve())

    normalize_xy = bool(params.get("normalize_xy", True))
    normalize_z_to = params.get("normalize_z_to", None)
    if normalize_z_to is not None:
        normalize_z_to = float(normalize_z_to)

    msi2lmp_run_dir = outputs_dir / "msi2lmp_run"
    msi2lmp_out_prefix = outputs_dir / "lammps" / "MXN"
    (outputs_dir / "lammps").mkdir(parents=True, exist_ok=True)

    base_name = str((staged_inputs_dir / "MXN").resolve())

    ext_res = msi2lmp.run(
        base_name=base_name,
        frc_file=str(ff_min_path),
        exe_path=exe_path,
        output_prefix=str(msi2lmp_out_prefix),
        normalize_xy=normalize_xy,
        normalize_z_to=normalize_z_to,
        work_dir=str(msi2lmp_run_dir),
    )

    # External wrapper always writes result.json; ensure it's present for debugging.
    # NOTE: we intentionally do NOT hash result.json into run_manifest.json because
    # wrapper envelopes include non-deterministic fields (cwd, duration_s, etc).
    result_json_path = Path((ext_res.get("outputs") or {}).get("result_json", msi2lmp_run_dir / "result.json"))
    _ensure_file(result_json_path, "msi2lmp result.json")
    _validate_nonempty(result_json_path, "msi2lmp result.json")

    # --- 6) Deterministic run_manifest.json ---
    # Only include relpaths under outputs_dir.
    run_manifest_path = outputs_dir / "run_manifest.json"

    outputs: dict[str, Path] = {
        "requirements": req_path,
        "ff_minimal": ff_min_path,
    }

    # Include lammps output hash only when it exists.
    lmp_data = None
    try:
        lmp_data = (ext_res.get("outputs") or {}).get("lmp_data_file")
    except Exception:
        lmp_data = None
    if isinstance(lmp_data, str) and lmp_data:
        lmp_data_p = Path(lmp_data)
        if lmp_data_p.exists():
            outputs["lammps_data"] = lmp_data_p

    manifest_obj: dict[str, Any] = {
        "schema": "molsaic.run_manifest.v0.1.1",
        "workspace": "02_usm_upm_msi2lmp_pipeline",
        "tool_versions": get_runtime_versions(
            extra={
                "msi2lmp": str(ext_res.get("tool_version") or "unknown"),
            }
        ),
        "inputs": {
            "car": _manifest_entry(car_in, base_dir=outputs_dir),
            "mdf": _manifest_entry(mdf_in, base_dir=outputs_dir),
            "source_frc": _manifest_entry(frc_in, base_dir=outputs_dir),
        },
        "outputs": {k: _manifest_entry(v, base_dir=outputs_dir) for k, v in sorted(outputs.items(), key=lambda kv: kv[0])},
        "external": {
            "tool": "msi2lmp",
            "status": str(ext_res.get("status") or "ok"),
            "tool_version": str(ext_res.get("tool_version") or "unknown"),
            "result_json_path": relpath_posix(result_json_path, base_dir=outputs_dir),
        },
    }

    write_json_stable(run_manifest_path, manifest_obj)
    _validate_nonempty(run_manifest_path, "run_manifest.json")

    print("[done] Golden pipeline complete.")
    print(f"  - outputs_dir:      {outputs_dir}")
    print(f"  - requirements:     {req_path}")
    print(f"  - ff_minimal:       {ff_min_path}")
    print(f"  - msi2lmp status:   {manifest_obj['external']['status']}")
    print(f"  - run_manifest:     {run_manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
