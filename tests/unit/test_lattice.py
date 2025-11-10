from __future__ import annotations

import math
import numpy as np
import pytest

from usm.ops.lattice import (
    lattice_matrix,
    lattice_inverse,
    frac_to_xyz,
    xyz_to_frac,
)

RT_TOL = 1e-12


def _random_valid_cell(rng: np.random.Generator):
    """
    Sample a random valid triclinic cell by retrying until lattice_matrix succeeds.
    Lengths in [1, 30], angles in (10°, 170°) with gamma kept away from singularities.
    """
    for _ in range(1000):
        a = float(rng.uniform(1.0, 30.0))
        b = float(rng.uniform(1.0, 30.0))
        c = float(rng.uniform(1.0, 30.0))
        # Keep angles reasonably away from 0/180; especially gamma (singularity at 0/180)
        alpha = float(rng.uniform(15.0, 165.0))
        beta = float(rng.uniform(15.0, 165.0))
        # Keep gamma further from 0/180 to avoid sin(gamma) ~ 0
        gamma = float(rng.uniform(20.0, 160.0))
        try:
            A = lattice_matrix(a, b, c, alpha, beta, gamma)
            return (a, b, c, alpha, beta, gamma), A
        except ValueError:
            continue
    raise RuntimeError("Failed to sample a valid random cell within retries")


def test_roundtrip_frac_xyz_frac_seeded():
    rng = np.random.default_rng(42)
    # Try multiple random cells
    for _ in range(10):
        (a, b, c, alpha, beta, gamma), A = _random_valid_cell(rng)
        Ainv = lattice_inverse(A)

        # Random fractional coordinates in a moderate range (not restricted to [0,1))
        frac = rng.uniform(-2.0, 3.0, size=(50, 3)).astype(np.float64)

        xyz = frac_to_xyz(A, frac)
        frac_rt = xyz_to_frac(Ainv, xyz)

        # Direct round-trip should match within tolerance
        diff = np.max(np.abs(frac - frac_rt))
        assert diff <= RT_TOL, f"frac->xyz->frac round-trip exceeded tol: {diff}"


def test_roundtrip_xyz_frac_xyz_seeded():
    rng = np.random.default_rng(123)
    for _ in range(10):
        (a, b, c, alpha, beta, gamma), A = _random_valid_cell(rng)
        Ainv = lattice_inverse(A)

        # Generate base frac, compute xyz, then round-trip xyz->frac->xyz
        base_frac = rng.uniform(-1.0, 2.0, size=(40, 3)).astype(np.float64)
        xyz = frac_to_xyz(A, base_frac)

        frac_rt = xyz_to_frac(Ainv, xyz)
        xyz_rt = frac_to_xyz(A, frac_rt)

        diff = np.max(np.abs(xyz - xyz_rt))
        assert diff <= RT_TOL, f"xyz->frac->xyz round-trip exceeded tol: {diff}"


def test_invalid_gamma_near_zero_raises():
    # sin(gamma) ~ 0 should be rejected
    a = b = c = 5.0
    alpha = 90.0
    beta = 90.0
    gamma = 1e-14  # degrees, extremely small -> sin(gamma) ~ 0
    with pytest.raises(ValueError):
        lattice_matrix(a, b, c, alpha, beta, gamma)


def test_invalid_configuration_negative_cz_squared_raises():
    # Construct a configuration that yields negative cz^2 (physically invalid)
    # Example: a=b=c=1, alpha=0°, beta=0°, gamma=60° leads to cz^2 < 0
    a = b = c = 1.0
    alpha = 0.0
    beta = 0.0
    gamma = 60.0
    with pytest.raises(ValueError):
        lattice_matrix(a, b, c, alpha, beta, gamma)


def test_inverse_shape_and_singularity_checks():
    (a, b, c, alpha, beta, gamma), A = _random_valid_cell(np.random.default_rng(7))
    Ainv = lattice_inverse(A)
    assert A.shape == (3, 3) and Ainv.shape == (3, 3)

    # Singular matrix check: craft an obviously singular A and ensure lattice_inverse raises
    with pytest.raises(ValueError):
        lattice_inverse(np.zeros((3, 3), dtype=np.float64))


def test_vectorized_and_1d_api_shapes():
    (a, b, c, alpha, beta, gamma), A = _random_valid_cell(np.random.default_rng(9))
    Ainv = lattice_inverse(A)

    f1 = np.array([0.2, -0.3, 1.1], dtype=np.float64)
    r1 = frac_to_xyz(A, f1)
    assert r1.shape == (3,)
    f1_rt = xyz_to_frac(Ainv, r1)
    assert f1_rt.shape == (3,)
    assert np.max(np.abs(f1 - f1_rt)) <= RT_TOL

    fN = np.array([[0.1, 0.2, 0.3], [1.1, -0.5, 2.2]], dtype=np.float64)
    rN = frac_to_xyz(A, fN)
    assert rN.shape == (2, 3)
    fN_rt = xyz_to_frac(Ainv, rN)
    assert fN_rt.shape == (2, 3)
    assert np.max(np.abs(fN - fN_rt)) <= RT_TOL