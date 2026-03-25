"""Tests for MDF periodic bond token (%abc#d) parsing, encoding, and round-trip."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Ensure repo src is importable
REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from usm.io._mdf_parser import _parse_periodic_shift, _encode_periodic_shift, build_bonds_from_connections
from usm.io.mdf import load_mdf, save_mdf
from usm.io.car import load_car
from usm.ops.compose import compose_on_keys
from usm.ops.replicate import replicate_supercell

FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "mxene_tri_unitcell"
MDF_PATH = FIXTURE_DIR / "EXPT_TRI_UnitCell_100OH.mdf"
CAR_PATH = FIXTURE_DIR / "EXPT_TRI_UnitCell_100OH.car"


# ---------------------------------------------------------------------------
# Unit tests for _parse_periodic_shift
# ---------------------------------------------------------------------------
class TestParsePeriodicShift:
    """Test parsing of %abc shift suffix strings."""

    @pytest.mark.parametrize(
        "suffix, expected",
        [
            ("0-10", (0, -1, 0)),
            ("010", (0, 1, 0)),
            ("100", (1, 0, 0)),
            ("-100", (-1, 0, 0)),
            ("110", (1, 1, 0)),
            ("-1-10", (-1, -1, 0)),
            # Edge cases
            ("000", (0, 0, 0)),
            ("111", (1, 1, 1)),
            ("-1-1-1", (-1, -1, -1)),
            ("001", (0, 0, 1)),
            ("00-1", (0, 0, -1)),
        ],
    )
    def test_parse_known_patterns(self, suffix: str, expected: tuple):
        assert _parse_periodic_shift(suffix) == expected

    def test_parse_empty_string(self):
        assert _parse_periodic_shift("") == (0, 0, 0)

    def test_parse_short_string(self):
        # Only 2 digits -> third defaults to 0
        assert _parse_periodic_shift("10") == (1, 0, 0)

    def test_parse_single_digit(self):
        assert _parse_periodic_shift("1") == (1, 0, 0)


# ---------------------------------------------------------------------------
# Unit tests for _encode_periodic_shift
# ---------------------------------------------------------------------------
class TestEncodePeriodicShift:
    """Test encoding of (ix, iy, iz) to %abc#1 suffix."""

    def test_zero_shift_returns_empty(self):
        assert _encode_periodic_shift(0, 0, 0) == ""

    def test_positive_shift(self):
        assert _encode_periodic_shift(1, 0, 0) == "%100#1"

    def test_negative_shift(self):
        assert _encode_periodic_shift(0, -1, 0) == "%0-10#1"

    def test_mixed_shift(self):
        result = _encode_periodic_shift(-1, -1, 0)
        assert result == "%-1-10#1"

    def test_all_positive(self):
        assert _encode_periodic_shift(1, 1, 1) == "%111#1"


# ---------------------------------------------------------------------------
# Round-trip: parse(encode(x)) == x
# ---------------------------------------------------------------------------
class TestEncodeDecodeRoundtrip:
    """Verify parse(encode(ix,iy,iz)) == (ix,iy,iz) for all single-digit combos."""

    @pytest.mark.parametrize("ix", [-1, 0, 1])
    @pytest.mark.parametrize("iy", [-1, 0, 1])
    @pytest.mark.parametrize("iz", [-1, 0, 1])
    def test_roundtrip(self, ix: int, iy: int, iz: int):
        encoded = _encode_periodic_shift(ix, iy, iz)
        if ix == 0 and iy == 0 and iz == 0:
            assert encoded == ""
            return
        # Strip leading '%' and trailing '#1' for parsing
        suffix = encoded[1:]  # remove '%'
        suffix = suffix.rsplit("#", 1)[0]  # remove '#1'
        parsed = _parse_periodic_shift(suffix)
        assert parsed == (ix, iy, iz), f"Roundtrip failed: ({ix},{iy},{iz}) -> {encoded!r} -> {parsed}"


# ---------------------------------------------------------------------------
# Integration: load real MXene MDF and verify periodic bonds
# ---------------------------------------------------------------------------
class TestLoadMdfPeriodicBonds:
    """Test loading the real MXene MDF populates ix, iy, iz correctly."""

    @pytest.fixture
    def mdf_usm(self):
        assert MDF_PATH.exists(), f"Fixture missing: {MDF_PATH}"
        return load_mdf(str(MDF_PATH))

    def test_bonds_exist(self, mdf_usm):
        assert mdf_usm.bonds is not None
        assert len(mdf_usm.bonds) > 0

    def test_periodic_bonds_populated(self, mdf_usm):
        """At least some bonds should have nonzero ix, iy, or iz."""
        bonds = mdf_usm.bonds
        has_shift = (bonds["ix"] != 0) | (bonds["iy"] != 0) | (bonds["iz"] != 0)
        n_periodic = has_shift.sum()
        assert n_periodic > 0, "No periodic bonds found — parsing likely failed"

    def test_periodic_bond_count_reasonable(self, mdf_usm):
        """The MXene unit cell MDF has connections with % tokens.
        There are 6 unique shift patterns across the file.
        The number of periodic bonds should be substantial."""
        bonds = mdf_usm.bonds
        has_shift = (bonds["ix"] != 0) | (bonds["iy"] != 0) | (bonds["iz"] != 0)
        n_periodic = has_shift.sum()
        # The MDF has many Ti-C bonds crossing boundaries; expect dozens
        assert n_periodic >= 10, f"Only {n_periodic} periodic bonds, expected >=10"

    def test_no_periodic_bonds_for_oh_pairs(self, mdf_usm):
        """O-H bonds within the unit cell should all have zero shift."""
        bonds = mdf_usm.bonds
        atoms = mdf_usm.atoms
        # Get aids for O and H atoms
        o_aids = set(atoms[atoms["element"] == "O"]["aid"].values)
        h_aids = set(atoms[atoms["element"] == "H"]["aid"].values)
        oh_bonds = bonds[
            ((bonds["a1"].isin(o_aids)) & (bonds["a2"].isin(h_aids)))
            | ((bonds["a1"].isin(h_aids)) & (bonds["a2"].isin(o_aids)))
        ]
        assert len(oh_bonds) > 0, "No O-H bonds found"
        for _, b in oh_bonds.iterrows():
            assert b["ix"] == 0 and b["iy"] == 0 and b["iz"] == 0, \
                f"O-H bond {b['a1']}-{b['a2']} has unexpected periodic shift"

    def test_atom_count(self, mdf_usm):
        assert len(mdf_usm.atoms) == 72


# ---------------------------------------------------------------------------
# MDF write round-trip with normalized connections
# ---------------------------------------------------------------------------
class TestMdfRoundtripNormalized:
    """Load MDF -> save with normalized connections -> reload -> compare."""

    def test_roundtrip_preserves_bond_topology(self, tmp_path):
        assert MDF_PATH.exists(), f"Fixture missing: {MDF_PATH}"
        usm1 = load_mdf(str(MDF_PATH))
        out_path = tmp_path / "roundtrip.mdf"
        save_mdf(usm1, str(out_path), preserve_headers=False, write_normalized_connections=True)
        usm2 = load_mdf(str(out_path))

        # Same atom count
        assert len(usm2.atoms) == len(usm1.atoms)

        # Same bond count
        assert len(usm2.bonds) == len(usm1.bonds), \
            f"Bond count mismatch: {len(usm1.bonds)} -> {len(usm2.bonds)}"

        # Compare bond sets (a1, a2, ix, iy, iz)
        def bond_set(bonds_df):
            return set(
                (int(r["a1"]), int(r["a2"]), int(r["ix"]), int(r["iy"]), int(r["iz"]))
                for _, r in bonds_df.iterrows()
            )

        set1 = bond_set(usm1.bonds)
        set2 = bond_set(usm2.bonds)
        assert set1 == set2, f"Bond sets differ: {set1.symmetric_difference(set2)}"


# ---------------------------------------------------------------------------
# Replicate with periodic bonds
# ---------------------------------------------------------------------------
class TestReplicateWithPeriodicBonds:
    """Load MXene MDF+CAR, compose, replicate, verify topology."""

    @pytest.fixture
    def composed_usm(self):
        assert MDF_PATH.exists() and CAR_PATH.exists()
        car_usm = load_car(str(CAR_PATH))
        mdf_usm = load_mdf(str(MDF_PATH))
        return compose_on_keys(car_usm, mdf_usm)

    def test_compose_has_periodic_bonds(self, composed_usm):
        bonds = composed_usm.bonds
        has_shift = (bonds["ix"] != 0) | (bonds["iy"] != 0) | (bonds["iz"] != 0)
        assert has_shift.sum() > 0

    def test_replicate_2x2x1_atom_count(self, composed_usm):
        sup = replicate_supercell(composed_usm, 2, 2, 1)
        assert len(sup.atoms) == 72 * 4

    def test_replicate_2x2x1_cell_angles_preserved(self, composed_usm):
        sup = replicate_supercell(composed_usm, 2, 2, 1)
        assert np.isclose(sup.cell["gamma"], 120.0)
        assert np.isclose(sup.cell["alpha"], 90.0)
        assert np.isclose(sup.cell["beta"], 90.0)

    def test_replicate_2x2x1_cell_lengths_scaled(self, composed_usm):
        sup = replicate_supercell(composed_usm, 2, 2, 1)
        assert np.isclose(sup.cell["a"], composed_usm.cell["a"] * 2)
        assert np.isclose(sup.cell["b"], composed_usm.cell["b"] * 2)
        assert np.isclose(sup.cell["c"], composed_usm.cell["c"] * 1)

    def test_replicate_2x2x1_bond_count_increases(self, composed_usm):
        """Bond count should scale with tile count for fully periodic systems."""
        n_orig = len(composed_usm.bonds)
        sup = replicate_supercell(composed_usm, 2, 2, 1)
        n_sup = len(sup.bonds)
        # For 2x2x1, all unit cell bonds (including periodic) get materialized
        # Total should be 4x original bond count
        assert n_sup == n_orig * 4, f"Expected {n_orig * 4}, got {n_sup}"

    def test_replicate_2x2x1_boundary_bonds_exist(self, composed_usm):
        """After 2x2x1, some bonds should still cross the supercell boundary."""
        sup = replicate_supercell(composed_usm, 2, 2, 1)
        has_shift = (sup.bonds["ix"] != 0) | (sup.bonds["iy"] != 0) | (sup.bonds["iz"] != 0)
        # In a 2x2x1 supercell of a structure with periodic XY bonds,
        # boundary bonds should still exist
        assert has_shift.sum() > 0, "No boundary bonds in supercell"


# ---------------------------------------------------------------------------
# Full chain: load -> compose -> replicate -> save MDF -> reload -> compare
# ---------------------------------------------------------------------------
class TestReplicateThenSaveMdfRoundtrip:
    """End-to-end: compose, replicate, save MDF, reload, verify."""

    def test_full_chain_2x2x1(self, tmp_path):
        car_usm = load_car(str(CAR_PATH))
        mdf_usm = load_mdf(str(MDF_PATH))
        composed = compose_on_keys(car_usm, mdf_usm)

        sup = replicate_supercell(composed, 2, 2, 1)

        out_path = tmp_path / "supercell.mdf"
        save_mdf(sup, str(out_path), preserve_headers=False, write_normalized_connections=True)

        reloaded = load_mdf(str(out_path))

        # Atom count preserved
        assert len(reloaded.atoms) == len(sup.atoms)

        # Bond count preserved
        assert len(reloaded.bonds) == len(sup.bonds), \
            f"Bond count: {len(sup.bonds)} -> {len(reloaded.bonds)}"

        # Bond set matches
        def bond_key_set(bonds_df):
            return set(
                (int(r["a1"]), int(r["a2"]), int(r["ix"]), int(r["iy"]), int(r["iz"]))
                for _, r in bonds_df.iterrows()
            )

        set_sup = bond_key_set(sup.bonds)
        set_rel = bond_key_set(reloaded.bonds)
        assert set_sup == set_rel, \
            f"Bond topology mismatch after MDF roundtrip: {len(set_sup.symmetric_difference(set_rel))} differences"
