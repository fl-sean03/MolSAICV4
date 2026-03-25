#!/usr/bin/env python3
"""Triclinic MXene bilayer + water workspace (V4, code-first).

Pipeline:
  1. Load unit cell CAR+MDF, compose coords+topology
  2. Replicate supercell (na x nb x 1)
  3. Build bilayer (separate two slabs, adjust c)
  4. Save dry supercell CAR/MDF
  5. msi2namd -> PDB/PSF for surface and water
  6. Packmol -> pack water in interlayer gap
  7. pm2mdfcar -> compose hydrated CAR/MDF
  8. msi2lmp -> LAMMPS .data with triclinic tilt factors
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Optional

# Ensure repo src imports work
def _find_repo_root(start_dir: Path) -> Path:
    cur = start_dir
    for cand in (cur, *cur.parents):
        if (cand / "pyproject.toml").exists():
            return cand
    raise RuntimeError(f"Could not locate repo root from: {start_dir}")

REPO_ROOT = _find_repo_root(Path(__file__).resolve().parent)
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from usm.io.car import load_car, save_car
from usm.io.mdf import load_mdf, save_mdf
from usm.ops.compose import compose_on_keys
from usm.ops.replicate import replicate_supercell
from external import msi2lmp
from external.adapter import resolve_executable


@contextmanager
def pushd(path: Path):
    prev = Path.cwd()
    os.chdir(str(path))
    try:
        yield
    finally:
        os.chdir(str(prev))


def _resolve_path(base: Path, maybe_rel: str) -> Path:
    p = Path(maybe_rel)
    return p if p.is_absolute() else (base / p).resolve()


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


_TILE_SUFFIX_RE = re.compile(r"_T_\d+_\d+_\d+$")


def _strip_tile_suffixes(usm_obj) -> None:
    """Strip _T_i_j_k tile suffixes and renumber mol_index (in-place).

    After replicate_supercell(), atom names get tile-index suffixes for
    internal uniqueness, and mol_index values repeat across tiles. Both
    break msi2lmp. Fix by:
    1. Strip _T_i_j_k suffixes from names
    2. Assign sequential mol_index (1..N) so (mol_label, mol_index, name)
       is unique for each atom
    """
    names = usm_obj.atoms["name"].astype(str).tolist()
    usm_obj.atoms["name"] = [_TILE_SUFFIX_RE.sub("", n) for n in names]
    usm_obj.atoms["mol_index"] = list(range(1, len(usm_obj.atoms) + 1))


def _build_supercell(cfg: dict, workspace_dir: Path) -> dict:
    """Steps 1-4: Load, compose, replicate, build bilayer, save."""
    # Paths
    car_path = _resolve_path(workspace_dir, cfg["unit_cell_car"])
    mdf_path = _resolve_path(workspace_dir, cfg["unit_cell_mdf"])
    outputs_dir = _resolve_path(workspace_dir, cfg.get("outputs_dir", "outputs"))
    _ensure_dir(outputs_dir)
    supercell_dir = outputs_dir / "supercell"
    _ensure_dir(supercell_dir)

    sc_cfg = cfg.get("supercell", {})
    na = sc_cfg.get("na", 9)
    nb = sc_cfg.get("nb", 10)
    nc = sc_cfg.get("nc", 1)

    bl_cfg = cfg.get("bilayer", {})
    z_gap = bl_cfg.get("z_gap", 8.0)
    vacuum_above = bl_cfg.get("vacuum_above", 10.0)

    timings: Dict[str, float] = {}

    # Step 1: Load & compose
    print(f"Step 1: Loading unit cell from {car_path.name} + {mdf_path.name}")
    t0 = time.perf_counter()
    car_usm = load_car(str(car_path))
    mdf_usm = load_mdf(str(mdf_path))
    usm = compose_on_keys(car_usm, mdf_usm)
    timings["load_compose_s"] = time.perf_counter() - t0
    n_unit_atoms = len(usm.atoms)
    n_unit_bonds = len(usm.bonds)
    periodic = (usm.bonds["ix"] != 0) | (usm.bonds["iy"] != 0) | (usm.bonds["iz"] != 0)
    print(f"  Unit cell: {n_unit_atoms} atoms, {n_unit_bonds} bonds ({periodic.sum()} periodic)")

    # Step 2: Replicate
    print(f"Step 2: Replicating {na}x{nb}x{nc} supercell...")
    t0 = time.perf_counter()
    sup = replicate_supercell(usm, na, nb, nc)
    _strip_tile_suffixes(sup)  # Remove _T_i_j_k suffixes for msi2lmp compatibility
    timings["replicate_s"] = time.perf_counter() - t0
    print(f"  Supercell: {len(sup.atoms)} atoms, {len(sup.bonds)} bonds")
    print(f"  Cell: a={sup.cell['a']:.2f} b={sup.cell['b']:.2f} c={sup.cell['c']:.2f} gamma={sup.cell['gamma']:.1f}")

    # Step 3: Build bilayer
    print(f"Step 3: Building bilayer (z_gap={z_gap} A, vacuum={vacuum_above} A)")
    atoms = sup.atoms.copy()
    z = atoms["z"].values.copy()

    # Find the inter-slab gap. The unit cell has 2 symmetric slabs, so
    # the correct gap produces the most balanced split (closest to 50/50).
    # Sort unique z-values and find the gap that minimizes |n_below - n_above|.
    z_sorted = sorted(z)
    n_total = len(z_sorted)
    best_balance = n_total  # worst case
    best_idx = 0
    for i in range(len(z_sorted) - 1):
        gap_width = z_sorted[i + 1] - z_sorted[i]
        if gap_width < 0.5:  # skip tiny gaps (within same z-layer)
            continue
        n_below = i + 1
        n_above = n_total - n_below
        imbalance = abs(n_below - n_above)
        if imbalance < best_balance:
            best_balance = imbalance
            best_idx = i
    z_split = 0.5 * (z_sorted[best_idx] + z_sorted[best_idx + 1])
    natural_gap = z_sorted[best_idx + 1] - z_sorted[best_idx]
    print(f"  Inter-slab gap at z={z_split:.3f} A (width={natural_gap:.3f} A)")

    # Shift top slab up to create water gap
    top_mask = z > z_split
    n_top = top_mask.sum()
    n_bot = (~top_mask).sum()
    print(f"  Bottom slab: {n_bot} atoms, Top slab: {n_top} atoms")
    imbalance_pct = abs(n_top - n_bot) / n_total * 100
    if imbalance_pct > 5.0:
        print(f"  WARNING: Bilayer split is {imbalance_pct:.1f}% imbalanced — check structure", file=sys.stderr)

    shift_amount = z_gap - natural_gap
    if shift_amount > 0:
        z[top_mask] += shift_amount
        atoms["z"] = z
        sup.atoms = atoms
        print(f"  Shifted top slab by +{shift_amount:.3f} A")
    else:
        print(f"  Gap already >= {z_gap} A, no shift needed")

    # Update c to accommodate both slabs + vacuum
    z_min = z.min()
    z_max = z.max()
    z_span = z_max - z_min
    new_c = z_span + vacuum_above
    sup.cell["c"] = new_c

    # Shift all atoms so z_min = vacuum_above / 2 (center structure in box)
    z_shift = (vacuum_above / 2.0) - z_min
    sup.atoms["z"] = sup.atoms["z"].values + z_shift
    print(f"  New c = {new_c:.2f} A (span={z_span:.2f} + vacuum={vacuum_above})")
    print(f"  Z shifted by {z_shift:.3f} to center in box")

    # Step 4: Save dry supercell
    print("Step 4: Saving dry supercell CAR/MDF...")
    t0 = time.perf_counter()
    car_out = supercell_dir / "mxene_bilayer_dry.car"
    mdf_out = supercell_dir / "mxene_bilayer_dry.mdf"
    save_car(sup, str(car_out), preserve_headers=False)
    save_mdf(sup, str(mdf_out), preserve_headers=False, write_normalized_connections=True)
    timings["save_s"] = time.perf_counter() - t0

    # Validation: full bond set comparison (not just count)
    reloaded_mdf = load_mdf(str(mdf_out))
    def _bond_set(bonds_df):
        return set(
            (int(r["a1"]), int(r["a2"]), int(r["ix"]), int(r["iy"]), int(r["iz"]))
            for _, r in bonds_df.iterrows()
        )
    orig_set = _bond_set(sup.bonds)
    reload_set = _bond_set(reloaded_mdf.bonds)
    assert orig_set == reload_set, \
        f"Bond roundtrip corruption: {len(orig_set)} orig, {len(reload_set)} reloaded, {len(orig_set ^ reload_set)} differ"
    print(f"  Saved and verified: {car_out.name}, {mdf_out.name} ({len(orig_set)} bonds match)")

    return {
        "supercell_car": str(car_out),
        "supercell_mdf": str(mdf_out),
        "n_atoms": len(sup.atoms),
        "n_bonds": len(sup.bonds),
        "cell": dict(sup.cell),
        "z_split": float(z_split),
        "z_gap_actual": float(z_gap),
        "timings": timings,
    }


def _run_msi2lmp(cfg: dict, workspace_dir: Path, supercell_info: dict) -> dict:
    """Step 8: Convert dry supercell to LAMMPS .data."""
    outputs_dir = _resolve_path(workspace_dir, cfg.get("outputs_dir", "outputs"))
    sim_dir = outputs_dir / "simulation"
    _ensure_dir(sim_dir)

    frc_file = _resolve_path(workspace_dir, cfg["frc_file"])
    execs = cfg.get("executables", {})
    msi2lmp_exe = resolve_executable(execs.get("msi2lmp"), "msi2lmp")
    timeouts = cfg.get("timeouts_s", {})

    # msi2lmp needs base_name (path without extension) pointing to .car + .mdf
    car_path = Path(supercell_info["supercell_car"])
    base_name = str(car_path.with_suffix(""))
    out_prefix = str(sim_dir / "mxene_bilayer_dry")

    print("Step 8: Running msi2lmp...")
    t0 = time.perf_counter()
    result = msi2lmp.run(
        base_name=base_name,
        frc_file=str(frc_file),
        exe_path=str(msi2lmp_exe),
        output_prefix=out_prefix,
        normalize_xy=True,
        timeout_s=int(timeouts.get("msi2lmp", 600)),
    )
    dt = time.perf_counter() - t0

    status = result.get("status", "unknown")
    print(f"  msi2lmp status: {status} ({dt:.2f}s)")

    if status == "ok":
        data_file = result["outputs"]["lmp_data_file"]
        print(f"  Output: {data_file}")
        # Surface any warnings from msi2lmp stderr
        stderr = result.get("stderr", "")
        if stderr and stderr.strip():
            warn_lines = [l for l in stderr.strip().splitlines() if l.strip()]
            if warn_lines:
                print(f"  msi2lmp produced {len(warn_lines)} warning lines:")
                for wl in warn_lines[:3]:
                    print(f"    {wl.strip()}")
                if len(warn_lines) > 3:
                    print(f"    ... ({len(warn_lines) - 3} more)")
        return {"lmp_data_file": data_file, "msi2lmp_s": dt, "status": "ok", "warnings": len(stderr.splitlines()) if stderr else 0}
    else:
        stderr = result.get("stderr", "")
        print(f"  msi2lmp FAILED: {stderr[:500]}", file=sys.stderr)
        return {"status": status, "stderr": stderr, "msi2lmp_s": dt}


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Triclinic MXene supercell workspace")
    parser.add_argument("--config", type=str, default="config.json")
    parser.add_argument("--dry-only", action="store_true", help="Only build dry supercell, skip hydration")
    args = parser.parse_args(argv)

    workspace_dir = Path(__file__).parent.resolve()
    cfg_path = _resolve_path(workspace_dir, args.config)
    if not cfg_path.exists():
        print(f"Config not found: {cfg_path}", file=sys.stderr)
        return 2

    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    outputs_dir = _resolve_path(workspace_dir, cfg.get("outputs_dir", "outputs"))
    _ensure_dir(outputs_dir)

    # Build supercell (Steps 1-4)
    supercell_info = _build_supercell(cfg, workspace_dir)

    # Run msi2lmp on dry structure (Step 8)
    lmp_result = _run_msi2lmp(cfg, workspace_dir, supercell_info)

    # Write summary
    summary = {
        "unit_cell": {
            "car": cfg["unit_cell_car"],
            "mdf": cfg["unit_cell_mdf"],
        },
        "supercell": supercell_info,
        "msi2lmp": lmp_result,
    }
    summary_path = outputs_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote summary: {summary_path}")

    if lmp_result.get("status") == "ok":
        print("\nWorkspace completed successfully.")
        return 0
    else:
        print("\nmsi2lmp step failed — see output above.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
