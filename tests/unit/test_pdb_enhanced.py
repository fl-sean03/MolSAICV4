import re
from pathlib import Path

import pandas as pd
from usm.core.model import USM
from usm.io.pdb import save_pdb

def make_usm(atoms_rows, bonds_edges=None, cell=None):
    atoms_df = pd.DataFrame(atoms_rows)
    # ensure AIDs contiguous and ints
    if "aid" not in atoms_df.columns:
        atoms_df["aid"] = range(len(atoms_df))
    if "x" not in atoms_df.columns:
        atoms_df["x"] = 0.0
        atoms_df["y"] = 0.0
        atoms_df["z"] = 0.0
    if "element" not in atoms_df.columns:
        atoms_df["element"] = "X"
    if "name" not in atoms_df.columns:
        atoms_df["name"] = "X"
    if "mol_block_name" not in atoms_df.columns:
        atoms_df["mol_block_name"] = "RES"
    if "mol_index" not in atoms_df.columns:
        atoms_df["mol_index"] = 1
    bonds_df = None
    if bonds_edges:
        bonds_df = pd.DataFrame([{"a1": int(a1), "a2": int(a2)} for a1,a2 in bonds_edges])
    return USM(atoms=atoms_df, bonds=bonds_df, molecules=None, cell=cell or {}, provenance={}, preserved_text={})

def read_lines(path):
    return Path(path).read_text(encoding="utf-8").strip().splitlines()

def test_cryst1_emission_and_atom_formatting(tmp_path):
    atoms = [
        {"aid":0, "name":"O", "element":"O", "x":0.0, "y":0.0, "z":0.0, "mol_block_name":"WAT", "mol_index":1},
        {"aid":1, "name":"H1", "element":"H", "x":0.1, "y":0.2, "z":0.3, "mol_block_name":"WAT", "mol_index":1},
        {"aid":2, "name":"H2", "element":"H", "x":-0.1, "y":-0.2, "z":-0.3, "mol_block_name":"WAT", "mol_index":1},
    ]
    cell = {"pbc": True, "a":10.0, "b":10.0, "c":10.0, "alpha":90.0, "beta":90.0, "gamma":90.0}
    usm = make_usm(atoms, cell=cell)
    out = save_pdb(usm, str(tmp_path / "wat.pdb"))
    lines = read_lines(out)
    assert lines[0].startswith("CRYST1")
    # First ATOM line should be second line
    atom_line = next(l for l in lines if l.startswith("ATOM"))
    # name is columns 13-16 (0-based 12:16), right-justified to width 4
    assert atom_line[12:16] == "   O"
    # element is columns 77-78 (0-based 76:78)
    assert atom_line[76:78] == " O"
    # serial is 1-based aid+1 in columns 7-11 (0-based 6:11)
    assert int(atom_line[6:11]) == 1

    # Now disable pbc -> no CRYST1
    usm2 = make_usm(atoms, cell={"pbc": False})
    out2 = save_pdb(usm2, str(tmp_path / "wat_nocell.pdb"))
    lines2 = read_lines(out2)
    assert not any(l.startswith("CRYST1") for l in lines2)

def test_conect_dedup_policy(tmp_path):
    # Build star: 0 connected to 1..6 (degree=6)
    atoms = [{"aid":i, "name":f"A{i}", "element":"C", "x":i*0.1, "y":0.0, "z":0.0, "mol_block_name":"M", "mol_index":1} for i in range(7)]
    bonds = [(0,i) for i in range(1,7)]
    usm = make_usm(atoms, bonds_edges=bonds, cell={"pbc": False})
    out = save_pdb(usm, str(tmp_path / "star_dedup.pdb"), include_conect=True, conect_policy="dedup")
    lines = read_lines(out)
    conect = [l for l in lines if l.startswith("CONECT")]
    # Expect two lines, both for serial 1 (aid 0 + 1), neighbors 2..7 in order
    assert len(conect) == 2
    nums = [[int(x) for x in l.split()[1:]] for l in conect]
    # First field of each line should be 1
    assert all(n[0] == 1 for n in nums)
    neighbors = sorted(set(n for row in nums for n in row[1:]))
    assert neighbors == [2,3,4,5,6,7]

def test_conect_full_policy(tmp_path):
    atoms = [{"aid":i, "name":f"A{i}", "element":"C", "x":i*0.1, "y":0.0, "z":0.0, "mol_block_name":"M", "mol_index":1} for i in range(3)]
    bonds = [(0,1),(1,2)]
    usm = make_usm(atoms, bonds_edges=bonds, cell={"pbc": False})
    out = save_pdb(usm, str(tmp_path / "chain_full.pdb"), include_conect=True, conect_policy="full")
    lines = read_lines(out)
    conect = [l for l in lines if l.startswith("CONECT")]
    # Should include both directions, e.g., 1-2 and 2-1, 2-3 and 3-2
    tokens = [l.split() for l in conect]
    pairs = set()
    for t in tokens:
        src = int(t[1])
        for dst_str in t[2:]:
            pairs.add((src, int(dst_str)))
    assert (1,2) in pairs and (2,1) in pairs
    assert (2,3) in pairs and (3,2) in pairs

def test_model_block_emission(tmp_path):
    atoms = [
        {"aid":0, "name":"C", "element":"C", "x":0.0, "y":0.0, "z":0.0, "mol_block_name":"M", "mol_index":1},
    ]
    cell = {"pbc": True, "a":5.0, "b":6.0, "c":7.0, "alpha":88.0, "beta":92.0, "gamma":75.0}
    usm = make_usm(atoms, cell=cell)
    out = save_pdb(usm, str(tmp_path / "model1.pdb"), include_model=True, model_index=3)
    lines = read_lines(out)
    assert lines[0].startswith("MODEL")
    assert lines[0].strip().endswith("   3")
    # CRYST1 should be the first record after MODEL when present
    assert lines[1].startswith("CRYST1")
    # ENDMDL should appear before END
    assert any(l == "ENDMDL" for l in lines)
    assert lines[-2] == "ENDMDL"
    assert lines[-1] == "END"

def test_defaults_preserve_prior_behavior(tmp_path):
    atoms = [
        {"aid":0, "name":"C", "element":"C", "x":0.0, "y":0.0, "z":0.0, "mol_block_name":"M", "mol_index":1},
        {"aid":1, "name":"H", "element":"H", "x":1.0, "y":0.0, "z":0.0, "mol_block_name":"M", "mol_index":1},
    ]
    usm = make_usm(atoms, bonds_edges=[(0,1)], cell={"pbc": False})
    out = save_pdb(usm, str(tmp_path / "defaults.pdb"))
    text = Path(out).read_text(encoding="utf-8")
    assert "MODEL" not in text
    assert "ENDMDL" not in text
    assert "CONECT" not in text