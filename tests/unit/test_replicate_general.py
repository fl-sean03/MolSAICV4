from __future__ import annotations

import numpy as np

from usm.core.model import USM  # [USM()](src/usm/core/model.py:89)
from usm.ops.replicate import replicate_supercell  # [replicate_supercell()](src/usm/ops/replicate.py:34)
from usm.ops.lattice import lattice_matrix, lattice_inverse, xyz_to_frac  # [lattice_matrix()](src/usm/ops/lattice.py:47), [lattice_inverse()](src/usm/ops/lattice.py:106), [xyz_to_frac()](src/usm/ops/lattice.py:134)


def _make_small_structure(cell: dict) -> USM:
    # Three atoms in a line with two bonds: 0-1, 1-2
    atoms = [
        {"name": "A1", "element": "C", "x": 0.0, "y": 0.0, "z": 0.0},
        {"name": "A2", "element": "H", "x": 1.0, "y": 0.2, "z": 0.3},
        {"name": "A3", "element": "O", "x": 2.0, "y": 0.1, "z": 0.4},
    ]
    bonds = [
        {"a1": 0, "a2": 1, "order": 1.0},
        {"a1": 1, "a2": 2, "order": 1.0},
    ]
    return USM.from_records(atoms_records=atoms, bonds_records=bonds, cell=cell)


def _assert_cell_scaled_and_angles_same(base: dict, new: dict, na: int, nb: int, nc: int):
    assert np.isclose(float(new.get("a", np.nan)), float(base.get("a", np.nan)) * na)
    assert np.isclose(float(new.get("b", np.nan)), float(base.get("b", np.nan)) * nb)
    assert np.isclose(float(new.get("c", np.nan)), float(base.get("c", np.nan)) * nc)
    # Angles unchanged
    for ang in ("alpha", "beta", "gamma"):
        assert np.isclose(float(new.get(ang, np.nan)), float(base.get(ang, np.nan)))


def test_replicate_monoclinic_counts_cell_and_bonds():
    # Monoclinic cell: alpha=90, beta=100, gamma=90
    base_cell = dict(pbc=True, a=10.0, b=12.0, c=8.0, alpha=90.0, beta=100.0, gamma=90.0, spacegroup="")
    base = _make_small_structure(base_cell)

    na, nb, nc = 2, 1, 3
    sup = replicate_supercell(base, na, nb, nc, add_image_indices=True)

    # Atom/bond counts scale with number of images
    n_base_atoms = len(base.atoms)
    n_base_bonds = len(base.bonds)
    n_images = na * nb * nc
    assert len(sup.atoms) == n_base_atoms * n_images
    assert len(sup.bonds) == n_base_bonds * n_images

    # Atom names must be unique across replicated tiles
    names = sup.atoms["name"].astype(str)
    assert names.nunique() == len(names)

    # Cell scaling and angles preserved
    _assert_cell_scaled_and_angles_same(base.cell, sup.cell, na, nb, nc)

    # Bonds remapped correctly: endpoints are valid aids in the new table, and a1 < a2
    amax = int(sup.atoms["aid"].max())
    a1 = sup.bonds["a1"].to_numpy(dtype=int)
    a2 = sup.bonds["a2"].to_numpy(dtype=int)
    assert np.all(a1 >= 0) and np.all(a2 >= 0) and np.all(a1 <= amax) and np.all(a2 <= amax)
    assert np.all(a1 < a2)

    # Optional: ensure per-image mapping produces no duplicate bonds beyond expected count
    pairs = set((int(x), int(y)) for x, y in zip(a1, a2))
    assert len(pairs) == len(sup.bonds)


def test_replicate_hexagonal_counts_cell_and_bonds():
    # Hexagonal cell: alpha=90, beta=90, gamma=120
    base_cell = dict(pbc=True, a=10.0, b=10.0, c=15.0, alpha=90.0, beta=90.0, gamma=120.0, spacegroup="")
    base = _make_small_structure(base_cell)

    na, nb, nc = 3, 2, 1
    sup = replicate_supercell(base, na, nb, nc, add_image_indices=False)

    n_base_atoms = len(base.atoms)
    n_base_bonds = len(base.bonds)
    n_images = na * nb * nc
    assert len(sup.atoms) == n_base_atoms * n_images
    assert len(sup.bonds) == n_base_bonds * n_images

    _assert_cell_scaled_and_angles_same(base.cell, sup.cell, na, nb, nc)

    amax = int(sup.atoms["aid"].max())
    a1 = sup.bonds["a1"].to_numpy(dtype=int)
    a2 = sup.bonds["a2"].to_numpy(dtype=int)
    assert np.all(a1 >= 0) and np.all(a2 >= 0) and np.all(a1 <= amax) and np.all(a2 <= amax)
    assert np.all(a1 < a2)
