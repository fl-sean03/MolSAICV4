#!/usr/bin/env python3
"""Build dry bilayer supercells for all three MXene terminations.

Runs the same pipeline as run.py for each termination:
  100OH  - 100% hydroxyl
  50F50OH - 50% fluorine / 50% hydroxyl
  100F   - 100% fluorine
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Import the core pipeline from run.py
sys.path.insert(0, str(Path(__file__).parent))
from run import _build_supercell, _run_msi2lmp, _resolve_path, _ensure_dir

WORKSPACE_DIR = Path(__file__).parent.resolve()

TERMINATIONS = {
    "100OH": {
        "unit_cell_car": "inputs/EXPT_TRI_UnitCell_100OH.car",
        "unit_cell_mdf": "inputs/EXPT_TRI_UnitCell_100OH.mdf",
        "label": "100% OH (72 atoms/cell)",
    },
    "50F50OH": {
        "unit_cell_car": "inputs/EXPT_TRI_UnitCell_50OH.car",
        "unit_cell_mdf": "inputs/EXPT_TRI_UnitCell_50OH.mdf",
        "label": "50% F / 50% OH (64 atoms/cell)",
    },
    "100F": {
        "unit_cell_car": "inputs/EXPT_TRI_UnitCell_100F.car",
        "unit_cell_mdf": "inputs/EXPT_TRI_UnitCell_100F.mdf",
        "label": "100% F (56 atoms/cell)",
    },
}


def main() -> int:
    # Load base config
    cfg_path = WORKSPACE_DIR / "config.json"
    base_cfg = json.loads(cfg_path.read_text(encoding="utf-8"))

    results = {}
    for term_name, term_info in TERMINATIONS.items():
        print(f"\n{'='*60}")
        print(f"  Building: {term_name} — {term_info['label']}")
        print(f"{'='*60}")

        # Override config for this termination
        cfg = dict(base_cfg)
        cfg["unit_cell_car"] = term_info["unit_cell_car"]
        cfg["unit_cell_mdf"] = term_info["unit_cell_mdf"]
        cfg["outputs_dir"] = f"outputs/{term_name}"

        try:
            supercell_info = _build_supercell(cfg, WORKSPACE_DIR)
            lmp_result = _run_msi2lmp(cfg, WORKSPACE_DIR, supercell_info)

            results[term_name] = {
                "supercell": supercell_info,
                "msi2lmp": lmp_result,
                "status": lmp_result.get("status", "unknown"),
            }

            if lmp_result.get("status") == "ok":
                print(f"\n  {term_name}: SUCCESS")
            else:
                print(f"\n  {term_name}: msi2lmp FAILED", file=sys.stderr)
        except Exception as e:
            print(f"\n  {term_name}: EXCEPTION: {e}", file=sys.stderr)
            results[term_name] = {"status": "error", "error": str(e)}

    # Write combined summary
    outputs_dir = _resolve_path(WORKSPACE_DIR, "outputs")
    _ensure_dir(outputs_dir)
    summary_path = outputs_dir / "all_terminations_summary.json"
    summary_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(f"\n\nWrote combined summary: {summary_path}")

    # Final status
    print("\n" + "=" * 60)
    print("  RESULTS")
    print("=" * 60)
    all_ok = True
    for name, res in results.items():
        status = res.get("status", "unknown")
        atoms = res.get("supercell", {}).get("n_atoms", "?")
        bonds = res.get("supercell", {}).get("n_bonds", "?")
        sym = "OK" if status == "ok" else "FAIL"
        print(f"  [{sym}] {name:10s}: {atoms} atoms, {bonds} bonds")
        if status != "ok":
            all_ok = False

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
