from __future__ import annotations

import numpy as np

from usm.core.model import USM  # [USM()](src/usm/core/model.py:89)
from usm.ops.transform import wrap_to_cell  # [wrap_to_cell()](src/usm/ops/transform.py:91)
from usm.ops.lattice import lattice_matrix, lattice_inverse, xyz_to_frac  # [lattice_matrix()](src/usm/ops/lattice.py:47), [lattice_inverse()](src/usm/ops/lattice.py:106), [xyz_to_frac()](src/usm/ops/lattice.py:134)

RT_TOL = 1e-12


def _make_usm_with_random_xyz(cell: dict, seed: int = 0, n: int = 8) -> USM:
    rng = np.random.default_rng(seed)
    # Create random xyz in a broad range to exercise wrapping
    xyz = rng.uniform(-15.0, 25.0, size=(n, 3)).astype(np.float64)
    atoms_records = [{"x": float(x), "y": float(y), "z": float(z)} for x, y, z in xyz]
    return USM.from_records(atoms_records, cell=cell)


def _assert_frac_in_unit_interval(frac: np.ndarray):
    # Check all components in [0,1) within tolerance
    assert np.all(frac >= -RT_TOL)
    assert np.all(frac < 1.0 + RT_TOL)


def test_wrap_monoclinic_frac_space_consistency():
    # Monoclinic: alpha=90, beta=100, gamma=90
    cell = dict(pbc=True, a=10.0, b=12.0, c=8.0, alpha=90.0, beta=100.0, gamma=90.0, spacegroup="")
    u0 = _make_usm_with_random_xyz(cell, seed=42, n=10)

    # Compute lattice and inverse
    A = lattice_matrix(cell["a"], cell["b"], cell["c"], cell["alpha"], cell["beta"], cell["gamma"])
    Ainv = lattice_inverse(A)

    # Original fractional coordinates
    xyz0 = u0.atoms[["x", "y", "z"]].to_numpy(dtype=np.float64)
    frac0 = xyz_to_frac(Ainv, xyz0)

    # Wrap
    u1 = wrap_to_cell(u0)
    xyz1 = u1.atoms[["x", "y", "z"]].to_numpy(dtype=np.float64)
    frac1 = xyz_to_frac(Ainv, xyz1)

    # Expected wrapped fractional coordinates
    expected = frac0 - np.floor(frac0)

    max_abs = float(np.max(np.abs(frac1 - expected)))
    assert max_abs <= RT_TOL, f"Monoclinic wrap frac mismatch: {max_abs}"
    _assert_frac_in_unit_interval(frac1)


def test_wrap_hexagonal_frac_space_consistency():
    # Hexagonal: alpha=90, beta=90, gamma=120
    cell = dict(pbc=True, a=10.0, b=10.0, c=15.0, alpha=90.0, beta=90.0, gamma=120.0, spacegroup="")
    u0 = _make_usm_with_random_xyz(cell, seed=7, n=12)

    A = lattice_matrix(cell["a"], cell["b"], cell["c"], cell["alpha"], cell["beta"], cell["gamma"])
    Ainv = lattice_inverse(A)

    xyz0 = u0.atoms[["x", "y", "z"]].to_numpy(dtype=np.float64)
    frac0 = xyz_to_frac(Ainv, xyz0)

    u1 = wrap_to_cell(u0)
    xyz1 = u1.atoms[["x", "y", "z"]].to_numpy(dtype=np.float64)
    frac1 = xyz_to_frac(Ainv, xyz1)

    expected = frac0 - np.floor(frac0)
    max_abs = float(np.max(np.abs(frac1 - expected)))
    assert max_abs <= RT_TOL, f"Hexagonal wrap frac mismatch: {max_abs}"
    _assert_frac_in_unit_interval(frac1)