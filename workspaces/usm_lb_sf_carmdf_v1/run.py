#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, List

# Ensure repo src on path (mirrors tests)
REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import numpy as np

# USM APIs
from usm.io.car import load_car, save_car  # [load_car()](src/usm/io/car.py:128), [save_car()](src/usm/io/car.py:187)
from usm.io.mdf import load_mdf, save_mdf  # [load_mdf()](src/usm/io/mdf.py:243), [save_mdf()](src/usm/io/mdf.py:378)
from usm.io.pdb import save_pdb  # [save_pdb()](src/usm/io/pdb.py:69)
from usm.ops.compose import compose_on_keys  # [compose_on_keys()](src/usm/ops/compose.py:13)
from usm.ops.select import select_by_element  # [select_by_element()](src/usm/ops/select.py:55)
from usm.ops.transform import (
    translate,
    rotate,
    rotation_matrix_from_axis_angle,
    wrap_to_cell,
)  # [translate()](src/usm/ops/transform.py:26), [rotate()](src/usm/ops/transform.py:62), [wrap_to_cell()](src/usm/ops/transform.py:91)
from usm.ops.replicate import replicate_supercell  # [replicate_supercell()](src/usm/ops/replicate.py:34)
from usm.ops.renumber import renumber_atoms  # [renumber_atoms()](src/usm/ops/renumber.py:30)


def is_orthorhombic(cell: Dict[str, Any], tol: float = 1e-3) -> bool:
    """
    Orthorhombic iff pbc=True and alpha=beta=gamma=90 (within tol).
    """
    if not bool((cell or {}).get("pbc", False)):
        return False
    a = float(cell.get("alpha", 90.0))
    b = float(cell.get("beta", 90.0))
    c = float(cell.get("gamma", 90.0))
    return abs(a - 90.0) < tol and abs(b - 90.0) < tol and abs(c - 90.0) < tol


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _xyz(usm) -> np.ndarray:
    return usm.atoms.sort_values("aid")[["x", "y", "z"]].to_numpy(dtype=float)


def _name_to_conn(usm) -> Dict[str, str]:
    a = usm.atoms.copy()
    names = a["name"].astype("string").fillna("").astype(str).tolist()
    conns = a["connections_raw"].astype("string").fillna("").astype(str).tolist() if "connections_raw" in a.columns else ["" for _ in names]
    return {n: c for n, c in zip(names, conns)}


def roundtrip_car(car_path: Path, out_dir: Path, atol: float = 1e-5) -> Dict[str, Any]:
    """
    Load → save → reload CAR and compute precise XYZ deltas.
    Metrics recorded:
      - xyz_equal (np.allclose with atol)
      - xyz_exact_equal (bitwise equality)
      - xyz_max_abs_diff (scalar) and per-axis maxima
      - xyz_nonzero_count (number of components with abs diff > 0)
      - xyz_worst (atom aid, axis, abs_diff)
    """
    u1 = load_car(str(car_path))
    out_file = out_dir / "car_rt.car"
    save_car(u1, str(out_file), preserve_headers=True)
    u2 = load_car(str(out_file))

    h1 = (u1.preserved_text or {}).get("car_header_lines", [])
    h2 = (u2.preserved_text or {}).get("car_header_lines", [])
    header_equal = h1 == h2

    xyz1 = _xyz(u1)
    xyz2 = _xyz(u2)

    # Exact equality and tolerance-based equality
    xyz_exact_equal = bool(np.array_equal(xyz1, xyz2))
    xyz_equal = bool(np.allclose(xyz1, xyz2, atol=atol))

    # Differences and metrics
    if xyz1.size == 0 or xyz2.size == 0:
        max_abs = 0.0
        per_axis_max = [0.0, 0.0, 0.0]
        nonzero_count = 0
        worst = {"atom_aid": None, "axis": None, "abs_diff": 0.0}
    else:
        diff = xyz2 - xyz1
        absdiff = np.abs(diff)
        # Scalar max
        max_abs = float(np.nanmax(absdiff))
        # Per-axis maxima (x,y,z)
        per_axis = np.nanmax(absdiff, axis=0)
        per_axis_max = [float(per_axis[0]), float(per_axis[1]), float(per_axis[2])]
        # Count of nonzero components
        nonzero_count = int(np.count_nonzero(absdiff > 0.0))
        # Worst component location
        flat_idx = int(np.nanargmax(absdiff))
        i, j = np.unravel_index(flat_idx, absdiff.shape)
        axis_label = ["x", "y", "z"][int(j)]
        # Aid equals row index in aid-sorted order by construction, but read it explicitly
        sorted_atoms = u1.atoms.sort_values("aid").reset_index(drop=True)
        atom_aid = int(sorted_atoms.loc[i, "aid"])
        worst = {"atom_aid": atom_aid, "axis": axis_label, "abs_diff": float(absdiff[i, j])}

    return {
        "ok": bool(header_equal and xyz_equal),
        "header_equal": bool(header_equal),
        "xyz_equal": bool(xyz_equal),
        "xyz_exact_equal": bool(xyz_exact_equal),
        "xyz_max_abs_diff": max_abs,
        "xyz_per_axis_max_abs_diff": per_axis_max,
        "xyz_nonzero_count": nonzero_count,
        "xyz_worst": worst,
        "xyz_atol_used": float(atol),
        "atoms": int(len(u1.atoms)),
        "out_file": str(out_file),
        "cell": dict(u1.cell or {}),
        "u1": u1,
        "u2": u2,
    }


def roundtrip_mdf(mdf_path: Path, out_dir: Path) -> Dict[str, Any]:
    m1 = load_mdf(str(mdf_path))
    out_file = out_dir / "mdf_rt.mdf"
    save_mdf(m1, str(out_file), preserve_headers=True, write_normalized_connections=False)
    m2 = load_mdf(str(out_file))

    h1 = (m1.preserved_text or {}).get("mdf_header_lines", [])
    h2 = (m2.preserved_text or {}).get("mdf_header_lines", [])
    header_equal = h1 == h2

    nc1 = _name_to_conn(m1)
    nc2 = _name_to_conn(m2)
    conn_equal = nc1 == nc2

    bonds_count = 0 if m1.bonds is None else int(len(m1.bonds))

    return {
        "ok": bool(header_equal and conn_equal),
        "header_equal": bool(header_equal),
        "connections_equal": bool(conn_equal),
        "atoms": int(len(m1.atoms)),
        "bonds": bonds_count,
        "out_file": str(out_file),
        "m1": m1,
        "m2": m2,
    }


def compose_and_exports(car_usm, mdf_usm, out_dir: Path) -> Dict[str, Any]:
    composed = compose_on_keys(car_usm, mdf_usm)
    # Save artifacts
    car_file = out_dir / "composed.car"
    mdf_file = out_dir / "composed.mdf"
    pdb_file = out_dir / "composed.pdb"
    save_car(composed, str(car_file), preserve_headers=False)  # synthesize canonical header if needed
    save_mdf(composed, str(mdf_file), preserve_headers=True, write_normalized_connections=False)
    save_pdb(composed, str(pdb_file))
    bonds_count = 0 if composed.bonds is None else int(len(composed.bonds))
    return {
        "composed": composed,
        "bonds": bonds_count,
        "car_file": str(car_file),
        "mdf_file": str(mdf_file),
        "pdb_file": str(pdb_file),
    }


def do_transforms(usm, out_dir: Path, apply_wrap: bool) -> Dict[str, Any]:
    # Example: translate + rotate 10 deg about z; optional wrap_to_cell
    t1 = translate(usm.copy(), (0.5, 0.0, 0.0))
    Rz = rotation_matrix_from_axis_angle((0.0, 0.0, 1.0), 10.0)
    t2 = rotate(t1, Rz)
    t3 = wrap_to_cell(t2) if apply_wrap else t2
    out_file = out_dir / "xform.car"
    save_car(t3, str(out_file), preserve_headers=False)
    return {"out_file": str(out_file), "atoms": int(len(t3.atoms))}


def do_replicate(usm, out_dir: Path, na: int, nb: int, nc: int) -> Dict[str, Any]:
    sup = replicate_supercell(usm, na, nb, nc, add_image_indices=True)
    out_file = out_dir / f"replicated_{na}x{nb}x{nc}.car"
    save_car(sup, str(out_file), preserve_headers=False)
    return {
        "out_file": str(out_file),
        "atoms": int(len(sup.atoms)),
        "bonds": 0 if sup.bonds is None else int(len(sup.bonds)),
        "cell": dict(sup.cell or {}),
    }


def element_histogram(usm) -> Dict[str, int]:
    elems = usm.atoms["element"].astype("string").fillna("").astype(str).tolist()
    hist: Dict[str, int] = {}
    for e in elems:
        hist[e] = hist.get(e, 0) + 1
    return dict(sorted(hist.items()))


def select_subset(usm, elements: List[str], out_dir: Path) -> Dict[str, Any]:
    sub = select_by_element(usm, elements)
    out_file = out_dir / f"subset_{'-'.join(elements)}.car"
    save_car(sub, str(out_file), preserve_headers=False)
    return {"out_file": str(out_file), "atoms": int(len(sub.atoms)), "elements": elements}


def renumber_demo(usm, out_dir: Path) -> Dict[str, Any]:
    rn = renumber_atoms(usm)
    out_file = out_dir / "renumbered.car"
    save_car(rn, str(out_file), preserve_headers=False)
    return {"out_file": str(out_file), "atoms": int(len(rn.atoms)), "bonds": 0 if rn.bonds is None else int(len(rn.bonds))}


def run_scenario(name: str, cfg: Dict[str, Any], outputs_root: Path) -> Dict[str, Any]:
    car_path = Path(cfg["car"]).resolve()
    mdf_path = Path(cfg["mdf"]).resolve()
    out_dir = outputs_root / name
    ensure_dir(out_dir)

    summary: Dict[str, Any] = {
        "scenario": name,
        "inputs": {"car": str(car_path), "mdf": str(mdf_path)},
        "outputs": {},
        "counts": {},
        "cell": {},
        "validations": {},
        "notes": [],
    }

    # CAR round-trip
    car_rt = roundtrip_car(car_path, out_dir)
    summary["validations"]["car_roundtrip_ok"] = car_rt["ok"]
    summary["validations"]["car_header_equal"] = car_rt["header_equal"]
    summary["validations"]["car_xyz_equal"] = car_rt["xyz_equal"]
    summary["validations"]["car_xyz_exact_equal"] = car_rt["xyz_exact_equal"]
    summary["validations"]["car_xyz_max_abs_diff"] = car_rt["xyz_max_abs_diff"]
    summary["validations"]["car_xyz_per_axis_max_abs_diff"] = car_rt["xyz_per_axis_max_abs_diff"]
    summary["validations"]["car_xyz_nonzero_count"] = car_rt["xyz_nonzero_count"]
    summary["validations"]["car_xyz_worst"] = car_rt["xyz_worst"]
    summary["validations"]["car_xyz_atol_used"] = car_rt["xyz_atol_used"]
    summary["outputs"]["car_rt"] = car_rt["out_file"]
    summary["counts"]["car_atoms"] = car_rt["atoms"]
    summary["cell"] = car_rt["cell"]

    # MDF round-trip
    mdf_rt = roundtrip_mdf(mdf_path, out_dir)
    summary["validations"]["mdf_roundtrip_ok"] = mdf_rt["ok"]
    summary["validations"]["mdf_header_equal"] = mdf_rt["header_equal"]
    summary["validations"]["mdf_connections_equal"] = mdf_rt["connections_equal"]
    summary["outputs"]["mdf_rt"] = mdf_rt["out_file"]
    summary["counts"]["mdf_atoms"] = mdf_rt["atoms"]
    summary["counts"]["mdf_bonds"] = mdf_rt["bonds"]

    # Compose CAR coords + MDF bonds
    comp = compose_and_exports(car_rt["u1"], mdf_rt["m1"], out_dir)
    summary["outputs"]["composed_car"] = comp["car_file"]
    summary["outputs"]["composed_mdf"] = comp["mdf_file"]
    summary["outputs"]["composed_pdb"] = comp["pdb_file"]
    summary["counts"]["composed_atoms"] = int(len(comp["composed"].atoms))
    summary["counts"]["composed_bonds"] = comp["bonds"]

    # Element histogram on composed
    summary["counts"]["elements_hist"] = element_histogram(comp["composed"])

    # Transforms (+wrap if orthorhombic)
    ortho = is_orthorhombic(car_rt["cell"])
    xform = do_transforms(comp["composed"], out_dir, apply_wrap=ortho)
    summary["outputs"]["xform_car"] = xform["out_file"]

    # Replication (only orthorhombic)
    rep_cfg = cfg.get("replicate", [2, 1, 1]) if ortho else None
    if ortho:
        try:
            na, nb, nc = [int(x) for x in rep_cfg]
            rep = do_replicate(comp["composed"], out_dir, na, nb, nc)
            summary["outputs"]["replicated_car"] = rep["out_file"]
            summary["counts"]["replicated_atoms"] = rep["atoms"]
            summary["counts"]["replicated_bonds"] = rep["bonds"]
            summary["cell_replicated"] = rep["cell"]
        except Exception as e:
            summary["notes"].append(f"replicate failed: {e}")
    else:
        summary["notes"].append("non-orthorhombic cell: wrap/replicate skipped")

    # Selection demo: pick up to 3 most common elements
    elems_sorted = sorted(summary["counts"]["elements_hist"].items(), key=lambda kv: (-kv[1], kv[0]))
    sel_elems = [kv[0] for kv in elems_sorted[:3]] if elems_sorted else []
    if sel_elems:
        subset = select_subset(comp["composed"], sel_elems, out_dir)
        summary["outputs"]["subset_car"] = subset["out_file"]
        summary["counts"]["subset_atoms"] = subset["atoms"]
        summary["counts"]["subset_elements"] = sel_elems

    # Renumber demo
    rn = renumber_demo(comp["composed"], out_dir)
    summary["outputs"]["renumbered_car"] = rn["out_file"]

    # A few top-level output aliases for convenience
    summary["outputs"]["car_file"] = summary["outputs"]["composed_car"]
    summary["outputs"]["mdf_file"] = summary["outputs"]["composed_mdf"]
    summary["outputs"]["pdb_file"] = summary["outputs"]["composed_pdb"]

    # Persist scenario summary
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def load_config(path: Path) -> Dict[str, Any]:
    cfg = json.loads(path.read_text(encoding="utf-8"))
    return cfg


def main() -> None:
    ap = argparse.ArgumentParser(description="USM on LB_SF_carmdf — round-trip and ops demos")
    ap.add_argument("--config", required=True, help="Path to config.json for this workspace")
    args = ap.parse_args()

    cfg = load_config(Path(args.config))
    outputs_root = Path(cfg.get("outputs_dir") or (REPO_ROOT / "workspaces" / "usm_lb_sf_carmdf_v1" / "outputs"))
    ensure_dir(outputs_root)

    scenarios = cfg.get("scenarios", {})
    summaries: Dict[str, Any] = {}
    for name, sc in scenarios.items():
        print(f"[USM] Running scenario {name} ...")
        try:
            s = run_scenario(name, sc, outputs_root)
            summaries[name] = s
            print(f"[USM] Scenario {name} done: atoms={s.get('counts',{}).get('composed_atoms','?')} bonds={s.get('counts',{}).get('composed_bonds','?')}")
        except Exception as e:
            print(f"[USM] Scenario {name} FAILED: {e}")
            summaries[name] = {"error": str(e)}

    # Write top-level summary
    top = {
        "workspace": "usm_lb_sf_carmdf_v1",
        "outputs_root": str(outputs_root),
        "scenarios": list(scenarios.keys()),
        "results": summaries,
    }
    (outputs_root / "summary.all.json").write_text(json.dumps(top, indent=2), encoding="utf-8")
    print(f"[USM] Wrote {outputs_root / 'summary.all.json'}")


if __name__ == "__main__":
    main()