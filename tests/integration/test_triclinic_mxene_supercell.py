"""Integration tests for triclinic MXene supercell pipeline.

Tests the full chain: load unit cell CAR+MDF -> compose -> replicate supercell
-> save CAR/MDF -> reload and verify.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from usm.io.car import load_car, save_car
from usm.io.mdf import load_mdf, save_mdf
from usm.ops.compose import compose_on_keys
from usm.ops.replicate import replicate_supercell

FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "mxene_tri_unitcell"
MDF_PATH = FIXTURE_DIR / "EXPT_TRI_UnitCell_100OH.mdf"
CAR_PATH = FIXTURE_DIR / "EXPT_TRI_UnitCell_100OH.car"

# Unit cell constants
UNIT_ATOMS = 72
UNIT_A = 6.101
UNIT_B = 6.101
UNIT_C = 19.86
UNIT_GAMMA = 120.0


@pytest.fixture
def composed_unit_cell():
    """Load and compose the MXene triclinic unit cell."""
    car = load_car(str(CAR_PATH))
    mdf = load_mdf(str(MDF_PATH))
    return compose_on_keys(car, mdf)


@pytest.mark.integration
class TestLoadComposeReplicateRoundtrip:
    """Validate load -> compose -> replicate -> save CAR/MDF -> reload."""

    def test_compose_merges_coords_and_bonds(self, composed_unit_cell):
        usm = composed_unit_cell
        assert len(usm.atoms) == UNIT_ATOMS
        assert usm.bonds is not None
        assert len(usm.bonds) > 0
        # Should have both coordinates and bonds
        assert not usm.atoms["x"].isna().any(), "Coordinates missing after compose"
        periodic = (usm.bonds["ix"] != 0) | (usm.bonds["iy"] != 0) | (usm.bonds["iz"] != 0)
        assert periodic.sum() > 0, "No periodic bonds after compose"

    def test_replicate_2x2x1(self, composed_unit_cell, tmp_path):
        sup = replicate_supercell(composed_unit_cell, 2, 2, 1)

        # Atom count
        assert len(sup.atoms) == UNIT_ATOMS * 4

        # Cell
        assert np.isclose(sup.cell["a"], UNIT_A * 2)
        assert np.isclose(sup.cell["b"], UNIT_B * 2)
        assert np.isclose(sup.cell["c"], UNIT_C)
        assert np.isclose(sup.cell["gamma"], UNIT_GAMMA)

        # Bonds scale with tile count
        n_unit_bonds = len(composed_unit_cell.bonds)
        assert len(sup.bonds) == n_unit_bonds * 4

        # Save and reload CAR
        car_out = tmp_path / "supercell.car"
        save_car(sup, str(car_out), preserve_headers=False)
        car_reloaded = load_car(str(car_out))
        assert len(car_reloaded.atoms) == UNIT_ATOMS * 4
        assert np.isclose(car_reloaded.cell["gamma"], UNIT_GAMMA)

        # Save and reload MDF
        mdf_out = tmp_path / "supercell.mdf"
        save_mdf(sup, str(mdf_out), preserve_headers=False, write_normalized_connections=True)
        mdf_reloaded = load_mdf(str(mdf_out))
        assert len(mdf_reloaded.atoms) == UNIT_ATOMS * 4
        assert len(mdf_reloaded.bonds) == len(sup.bonds)

    def test_replicate_3x3x1_no_z_periodic(self, composed_unit_cell):
        """After 3x3x1 (nc=1), bonds should not have iz shifts (only XY replication)."""
        sup = replicate_supercell(composed_unit_cell, 3, 3, 1)
        # nc=1 means no z-direction replication, so iz should always be 0
        # for bonds that were iz=0 in the unit cell
        assert len(sup.atoms) == UNIT_ATOMS * 9


@pytest.mark.integration
class TestSupercellBondTopology:
    """Verify bond topology correctness after replication."""

    def test_bond_set_roundtrip_through_mdf(self, composed_unit_cell, tmp_path):
        """Full roundtrip: compose -> replicate -> save MDF -> reload -> compare."""
        sup = replicate_supercell(composed_unit_cell, 3, 3, 1)

        mdf_out = tmp_path / "sup_3x3.mdf"
        save_mdf(sup, str(mdf_out), preserve_headers=False, write_normalized_connections=True)
        reloaded = load_mdf(str(mdf_out))

        def bond_set(bonds_df):
            return set(
                (int(r["a1"]), int(r["a2"]), int(r["ix"]), int(r["iy"]), int(r["iz"]))
                for _, r in bonds_df.iterrows()
            )

        assert bond_set(sup.bonds) == bond_set(reloaded.bonds)

    def test_oh_bonds_all_internal_after_replication(self, composed_unit_cell):
        """O-H bonds should never cross periodic boundaries."""
        sup = replicate_supercell(composed_unit_cell, 3, 3, 1)
        atoms = sup.atoms
        bonds = sup.bonds
        o_aids = set(atoms[atoms["element"] == "O"]["aid"].values)
        h_aids = set(atoms[atoms["element"] == "H"]["aid"].values)
        oh_bonds = bonds[
            ((bonds["a1"].isin(o_aids)) & (bonds["a2"].isin(h_aids)))
            | ((bonds["a1"].isin(h_aids)) & (bonds["a2"].isin(o_aids)))
        ]
        for _, b in oh_bonds.iterrows():
            assert b["ix"] == 0 and b["iy"] == 0 and b["iz"] == 0


@pytest.mark.integration
class TestBilayerZSeparation:
    """Test z-separation of the two slabs in the unit cell."""

    def test_unit_cell_has_two_slabs(self, composed_unit_cell):
        """The unit cell should have atoms spanning two distinct slab regions."""
        z = composed_unit_cell.atoms["z"].values
        # Slab 1 roughly z < 5, Slab 2 roughly z > 5
        slab1 = z[z < 5.0]
        slab2 = z[z > 5.0]
        assert len(slab1) > 0 and len(slab2) > 0
        assert len(slab1) == len(slab2)  # symmetric bilayer

    def test_z_shift_creates_gap(self, composed_unit_cell):
        """Shifting top slab atoms creates a water-accessible gap."""
        import pandas as pd
        usm = composed_unit_cell
        atoms = usm.atoms.copy()
        z = atoms["z"].values.copy()

        z_threshold = 5.0
        gap_shift = 8.0

        top_mask = z > z_threshold
        z[top_mask] += gap_shift
        atoms["z"] = z

        # Compute gap between slabs
        z_top_of_slab1 = z[~top_mask].max()
        z_bot_of_slab2 = z[top_mask].min()
        gap = z_bot_of_slab2 - z_top_of_slab1

        assert gap > 5.0, f"Gap is only {gap:.2f} A, need > 5 A for water"
        assert math.isclose(gap, 0.874 + gap_shift, rel_tol=0.1)


@pytest.mark.integration
class TestCarSavePreservesAngles:
    """Verify CAR save preserves triclinic cell angles."""

    def test_car_roundtrip_hexagonal_angles(self, composed_unit_cell, tmp_path):
        out = tmp_path / "test.car"
        save_car(composed_unit_cell, str(out), preserve_headers=False)
        reloaded = load_car(str(out))
        assert np.isclose(reloaded.cell["gamma"], 120.0)
        assert np.isclose(reloaded.cell["alpha"], 90.0)
        assert np.isclose(reloaded.cell["beta"], 90.0)
        assert np.isclose(reloaded.cell["a"], UNIT_A, rtol=1e-3)
        assert np.isclose(reloaded.cell["b"], UNIT_B, rtol=1e-3)
