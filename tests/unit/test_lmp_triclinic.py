"""Tests for triclinic LAMMPS box support in _lmp_normalize.py."""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from external._lmp_normalize import (
    parse_cell_from_car,
    is_triclinic,
    compute_lammps_tilt,
    normalize_data_file,
)

FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "mxene_tri_unitcell"
CAR_PATH = FIXTURE_DIR / "EXPT_TRI_UnitCell_100OH.car"


# ---------------------------------------------------------------------------
# is_triclinic
# ---------------------------------------------------------------------------
class TestIsTriclinic:
    def test_orthogonal(self):
        assert not is_triclinic(90.0, 90.0, 90.0)

    def test_hexagonal(self):
        assert is_triclinic(90.0, 90.0, 120.0)

    def test_monoclinic(self):
        assert is_triclinic(90.0, 115.0, 90.0)

    def test_general(self):
        assert is_triclinic(80.0, 85.0, 110.0)

    def test_near_90_within_tol(self):
        assert not is_triclinic(90.005, 90.005, 90.005, tol=0.01)


# ---------------------------------------------------------------------------
# compute_lammps_tilt
# ---------------------------------------------------------------------------
class TestComputeLammpsTilt:
    def test_orthogonal_zero_tilt(self):
        tilt = compute_lammps_tilt(10.0, 10.0, 15.0, 90.0, 90.0, 90.0)
        assert math.isclose(tilt["lx"], 10.0)
        assert math.isclose(tilt["ly"], 10.0)
        assert math.isclose(tilt["lz"], 15.0)
        assert math.isclose(tilt["xy"], 0.0, abs_tol=1e-10)
        assert math.isclose(tilt["xz"], 0.0, abs_tol=1e-10)
        assert math.isclose(tilt["yz"], 0.0, abs_tol=1e-10)

    def test_hexagonal_gamma120(self):
        a, b, c = 6.101, 6.101, 19.86
        tilt = compute_lammps_tilt(a, b, c, 90.0, 90.0, 120.0)
        assert math.isclose(tilt["lx"], a)
        # xy = b * cos(120) = -b/2
        assert math.isclose(tilt["xy"], -b / 2, rel_tol=1e-6)
        # xz = 0, yz = 0 (alpha=beta=90)
        assert math.isclose(tilt["xz"], 0.0, abs_tol=1e-10)
        assert math.isclose(tilt["yz"], 0.0, abs_tol=1e-10)
        # ly = b * sin(120) = b * sqrt(3)/2
        assert math.isclose(tilt["ly"], b * math.sqrt(3) / 2, rel_tol=1e-6)
        assert math.isclose(tilt["lz"], c, rel_tol=1e-6)

    def test_monoclinic_beta(self):
        a, b, c = 8.0, 10.0, 12.0
        alpha, beta, gamma = 90.0, 115.0, 90.0
        tilt = compute_lammps_tilt(a, b, c, alpha, beta, gamma)
        assert math.isclose(tilt["lx"], a)
        assert math.isclose(tilt["xy"], 0.0, abs_tol=1e-10)
        assert math.isclose(tilt["xz"], c * math.cos(math.radians(beta)), rel_tol=1e-6)
        assert math.isclose(tilt["yz"], 0.0, abs_tol=1e-10)

    def test_general_triclinic(self):
        """Test with a general triclinic cell and verify LAMMPS conventions."""
        a, b, c = 8.0, 10.0, 12.0
        alpha, beta, gamma = 80.0, 85.0, 110.0
        tilt = compute_lammps_tilt(a, b, c, alpha, beta, gamma)
        # Verify basic relations
        assert tilt["lx"] > 0
        assert tilt["ly"] > 0
        assert tilt["lz"] > 0
        # Verify: a^2 = lx^2
        assert math.isclose(a, tilt["lx"])
        # Verify: b^2 = xy^2 + ly^2
        assert math.isclose(b * b, tilt["xy"] ** 2 + tilt["ly"] ** 2, rel_tol=1e-10)
        # Verify: c^2 = xz^2 + yz^2 + lz^2
        assert math.isclose(c * c, tilt["xz"] ** 2 + tilt["yz"] ** 2 + tilt["lz"] ** 2, rel_tol=1e-10)


# ---------------------------------------------------------------------------
# parse_cell_from_car
# ---------------------------------------------------------------------------
class TestParseCellFromCar:
    def test_parse_hexagonal_car(self):
        assert CAR_PATH.exists(), f"Fixture missing: {CAR_PATH}"
        a, b, c, alpha, beta, gamma = parse_cell_from_car(CAR_PATH)
        assert math.isclose(a, 6.101, rel_tol=1e-3)
        assert math.isclose(b, 6.101, rel_tol=1e-3)
        assert math.isclose(c, 19.86, rel_tol=1e-3)
        assert math.isclose(alpha, 90.0)
        assert math.isclose(beta, 90.0)
        assert math.isclose(gamma, 120.0)

    def test_parse_missing_file_returns_nones(self, tmp_path):
        fake = tmp_path / "nonexistent.car"
        a, b, c, alpha, beta, gamma = parse_cell_from_car(fake)
        assert a is None and alpha is None


# ---------------------------------------------------------------------------
# normalize_data_file with triclinic header
# ---------------------------------------------------------------------------
class TestNormalizeTriclinicHeader:
    """Test that normalize_data_file inserts xy/xz/yz tilt line for triclinic cells."""

    MOCK_DATA = """\
LAMMPS data file (test)

72 atoms
100 bonds

4 atom types
2 bond types

-5.000000 55.000000 xlo xhi
-3.000000 53.000000 ylo yhi
-5.000000 25.000000 zlo zhi

Masses

1 47.867 # Ti
2 12.011 # C

Atoms # full

1 1 1 0.675 1.5 0.8 2.4
2 1 1 0.675 4.5 0.8 2.4
"""

    def test_triclinic_inserts_tilt_line(self, tmp_path):
        data_path = tmp_path / "test.data"
        data_path.write_text(self.MOCK_DATA)

        normalize_data_file(
            data_path,
            a_dim=6.101,
            b_dim=6.101,
            do_xy=True,
            z_target=19.86,
            do_z_shift=False,
            do_z_center=False,
            cell_angles=(90.0, 90.0, 120.0),
        )

        text = data_path.read_text()
        assert "xy xz yz" in text, "Tilt factor line not found in output"
        # Verify tilt values
        for line in text.splitlines():
            if "xy xz yz" in line:
                parts = line.split()
                xy_val = float(parts[0])
                xz_val = float(parts[1])
                yz_val = float(parts[2])
                assert math.isclose(xy_val, -6.101 / 2, rel_tol=1e-3)
                assert math.isclose(xz_val, 0.0, abs_tol=1e-6)
                assert math.isclose(yz_val, 0.0, abs_tol=1e-6)
                break

    def test_orthogonal_no_tilt_line(self, tmp_path):
        """When gamma=90, no tilt line should be added."""
        data_path = tmp_path / "test.data"
        data_path.write_text(self.MOCK_DATA)

        normalize_data_file(
            data_path,
            a_dim=48.808,
            b_dim=47.552,
            do_xy=True,
            z_target=9.58,
            do_z_shift=False,
            do_z_center=False,
            cell_angles=(90.0, 90.0, 90.0),
        )

        text = data_path.read_text()
        assert "xy xz yz" not in text, "Tilt line should not appear for orthogonal cell"

    def test_triclinic_updates_xy_extents_to_lx_ly(self, tmp_path):
        """For triclinic, XY extents should use lx/ly, not a/b."""
        data_path = tmp_path / "test.data"
        data_path.write_text(self.MOCK_DATA)

        a, b = 6.101, 6.101
        normalize_data_file(
            data_path,
            a_dim=a,
            b_dim=b,
            do_xy=True,
            z_target=19.86,
            do_z_shift=False,
            do_z_center=False,
            cell_angles=(90.0, 90.0, 120.0),
        )

        text = data_path.read_text()
        for line in text.splitlines():
            if "xlo xhi" in line:
                parts = line.split()
                xhi = float(parts[1])
                # lx = a for any cell
                assert math.isclose(xhi, a, rel_tol=1e-6)
            if "ylo yhi" in line:
                parts = line.split()
                yhi = float(parts[1])
                # ly = b * sin(120) = b * sqrt(3)/2
                expected_ly = b * math.sqrt(3) / 2
                assert math.isclose(yhi, expected_ly, rel_tol=1e-3)

    def test_no_cell_angles_backward_compat(self, tmp_path):
        """Without cell_angles, behavior is identical to original."""
        data_path = tmp_path / "test.data"
        data_path.write_text(self.MOCK_DATA)

        normalize_data_file(
            data_path,
            a_dim=48.0,
            b_dim=47.0,
            do_xy=True,
            z_target=9.58,
            do_z_shift=False,
            do_z_center=False,
        )

        text = data_path.read_text()
        assert "xy xz yz" not in text
        # Check a/b used directly
        for line in text.splitlines():
            if "xlo xhi" in line:
                assert "48.000000" in line
            if "ylo yhi" in line:
                assert "47.000000" in line
