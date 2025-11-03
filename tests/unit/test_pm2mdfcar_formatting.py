import json
from pathlib import Path
from typing import List, Tuple

import pytest

# Ensure repo root import
import sys
REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import pm2mdfcar  # noqa: E402


@pytest.mark.unit
def test_build_writes_car_mdf_and_honors_target_c(tmp_path: Path, monkeypatch):
    """
    Validate pm2mdfcar.build() writes non-empty CAR/MDF, returns counts/cell,
    and enforces cell.c := target_c via meta box override, independent of templates.
    """

    # Prepare templates_dir with placeholder files (won't be parsed due to monkeypatch)
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir(parents=True, exist_ok=True)
    (templates_dir / "AS2.car").write_text("! stub AS2.car\nPBC 9.0 9.0 9.0 90.0 90.0 90.0\n", encoding="utf-8")
    (templates_dir / "AS2.mdf").write_text("# stub AS2.mdf\n", encoding="utf-8")
    (templates_dir / "WAT.car").write_text("! stub WAT.car\n", encoding="utf-8")
    (templates_dir / "WAT.mdf").write_text("# stub WAT.mdf\n", encoding="utf-8")

    # Hydrated PDB placeholder
    hydrated_pdb = tmp_path / "hydrated.pdb"
    hydrated_pdb.write_text("REMARK stub\n", encoding="utf-8")

    converted_dir = tmp_path / "converted"
    out_prefix = converted_dir / "ASX_hydrated"

    # Monkeypatch light-weight internals to avoid depending on vendored legacy parser/builder
    def fake_parse_car(_p: Path):
        # Return a,b,c that differ from target to confirm override path
        cell = {"a": 10.0, "b": 20.0, "c": 30.0, "alpha": 90.0, "beta": 90.0, "gamma": 90.0}
        # Minimal TemplateAtom-like tuples (label,res_seq,atom_type,element,charge)
        atoms = []  # not used by this test; bonds count path is separately patched
        header = []
        return cell, atoms, header

    def fake_parse_mdf_bonds(_mdf_path: Path, _atoms) -> List[Tuple[int, int]]:
        # Pretend AS2 template has 5 bonds
        return [(1, 2)] * 5

    def fake_parse_wat_templates(_dir: Path):
        # WAT has 3 atoms (O H H) and 2 bonds
        wat_atoms = [("O1", 1, "oh", "O", -0.834), ("H1", 1, "ho", "H", 0.417), ("H2", 1, "ho", "H", 0.417)]
        wat_bonds = [(1, 2), (1, 3)]
        return wat_atoms, wat_bonds

    def fake_legacy_parse_pdb(_pdb_path: Path):
        # Shape is not used by our fake builders; return sentinel tuple
        return object(), object(), {"remarks": ["stub"]}

    def fake_legacy_build_mdf(_pdb_atoms_df, _pdb_meta, _templates_legacy, out_prefix_path: Path, _templ_dir: Path, target_c: float):
        out_prefix_path.parent.mkdir(parents=True, exist_ok=True)
        # Emit meta.json with box values (include target_c)
        meta = {"box": {"a": 12.3, "b": 23.4, "c": float(target_c), "alpha": 90.0, "beta": 90.0, "gamma": 90.0}}
        (out_prefix_path.parent / f"{out_prefix_path.name}_meta.json").write_text(json.dumps(meta), encoding="utf-8")
        # Emit atoms.csv with 8 surface atoms and 6 water atoms (2 waters)
        atoms_csv = out_prefix_path.parent / f"{out_prefix_path.name}_atoms.csv"
        atoms_csv.write_text("serial,resname\n", encoding="utf-8")
        atoms_csv.write_text("".join(["1,AS2\n"] * 8 + ["9,WAT\n"] * 6), encoding="utf-8")

        # Emit MDF file
        (out_prefix_path.with_suffix(".mdf")).write_text("# MDF stub\n", encoding="utf-8")

    def fake_legacy_build_car(_pdb_atoms_df, _pdb_meta, _templates_legacy, out_prefix_path: Path):
        (out_prefix_path.with_suffix(".car")).write_text("! CAR stub\n", encoding="utf-8")

    def fake_legacy_load(_dir: Path):
        return {"loaded": True}

    # Apply monkeypatches
    monkeypatch.setattr(pm2mdfcar, "_parse_car", fake_parse_car)
    monkeypatch.setattr(pm2mdfcar, "_parse_mdf_bonds", fake_parse_mdf_bonds)
    monkeypatch.setattr(pm2mdfcar, "_parse_wat_templates", fake_parse_wat_templates)
    monkeypatch.setattr(pm2mdfcar, "_legacy_parse_pdb", fake_legacy_parse_pdb)
    monkeypatch.setattr(pm2mdfcar, "_legacy_build_mdf", fake_legacy_build_mdf)
    monkeypatch.setattr(pm2mdfcar, "_legacy_build_car", fake_legacy_build_car)
    monkeypatch.setattr(pm2mdfcar, "_legacy_load", fake_legacy_load)

    # Act
    res = pm2mdfcar.build(
        hydrated_pdb=str(hydrated_pdb),
        templates_dir=str(templates_dir),
        output_prefix=str(out_prefix),
        target_c=81.397,
        resname_surface="AS2",
        resname_water="WAT",
    )

    # Assert result shape
    assert isinstance(res, dict)
    car = Path(res["car_file"])
    mdf = Path(res["mdf_file"])
    assert car.exists() and car.stat().st_size > 0
    assert mdf.exists() and mdf.stat().st_size > 0

    # Cell.c must equal target_c
    cell = res.get("cell", {})
    assert pytest.approx(cell.get("c"), rel=0, abs=1e-6) == 81.397

    # Counts presence and rough consistency from our fake CSV (8 surface atoms, 2 waters -> 14 atoms total)
    counts = res.get("counts", {})
    assert "atoms" in counts and "surface_atoms" in counts and "waters" in counts and "bonds" in counts
    assert counts["atoms"] == 14
    assert counts["surface_atoms"] == 8
    assert counts["waters"] == 2