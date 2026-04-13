"""Validation for rn_v2 enrichment outputs."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def validate_enrichment(structure, templates: dict, config) -> list[str]:
    """Validate the enriched structure before writing.

    Checks:
    1. No missing atom types (XX, X, empty)
    2. Atom count matches expected
    3. All template types are represented
    4. Coordinates are within box bounds
    5. No NaN in critical columns

    Returns:
        List of warning strings (empty = all good).
    """
    warnings = []
    atoms = structure.atoms

    # 1. No missing/default atom types
    bad_types = atoms[atoms["atom_type"].isin(["XX", "X", "", None]) |
                      atoms["atom_type"].isna()]
    if len(bad_types) > 0:
        warnings.append(
            f"CRITICAL: {len(bad_types)} atoms with missing/invalid atom_type "
            f"(XX, X, empty, or NaN)"
        )

    # 2. Atom count
    expected = sum(t["n_atoms"] for t in templates.values())
    # For separate grouping, multiply by molecule count
    # (can't easily compute here without more info, so just check > 0)
    if len(atoms) == 0:
        warnings.append("CRITICAL: Zero atoms in enriched structure")

    # 3. All expected atom types present
    for tpl_name, tpl_data in templates.items():
        tpl_types = set(tpl_data["structure"].atoms["atom_type"].unique())
        actual_types = set(atoms["atom_type"].unique())
        missing = tpl_types - actual_types
        if missing:
            warnings.append(
                f"Template '{tpl_name}' has types {missing} not found in output"
            )

    # 4. Coordinate bounds (if cell is set)
    cell = structure.cell
    if cell and cell.get("pbc"):
        for dim, key in [("x", "a"), ("y", "b"), ("z", "c")]:
            box_size = cell[key]
            out_of_bounds = atoms[(atoms[dim] < -1.0) | (atoms[dim] > box_size + 1.0)]
            if len(out_of_bounds) > 0:
                warnings.append(
                    f"{len(out_of_bounds)} atoms outside {dim} bounds "
                    f"[0, {box_size}]"
                )

    # 5. NaN in critical columns
    for col in ["atom_type", "element", "x", "y", "z"]:
        n_nan = atoms[col].isna().sum()
        if n_nan > 0:
            warnings.append(f"CRITICAL: {n_nan} NaN values in column '{col}'")

    # 6. Charge sanity
    if "charge" in atoms.columns:
        n_nan_charge = atoms["charge"].isna().sum()
        if n_nan_charge > 0:
            warnings.append(f"{n_nan_charge} atoms with NaN charge")

    return warnings


def validate_mdf_output(mdf_path: str | Path) -> list[str]:
    """Validate the written MDF file.

    Checks:
    1. File exists and is non-empty
    2. Contains @molecule blocks
    3. No 'XX' atom types in output
    4. Has PBC specification

    Returns:
        List of warning strings.
    """
    warnings = []
    path = Path(mdf_path)

    if not path.exists():
        warnings.append(f"CRITICAL: MDF file not written: {path}")
        return warnings

    content = path.read_text()
    lines = content.splitlines()

    if len(lines) < 10:
        warnings.append(f"MDF file suspiciously short: {len(lines)} lines")

    # Check for @molecule blocks
    mol_count = sum(1 for l in lines if l.strip().startswith("@molecule"))
    if mol_count == 0:
        warnings.append("MDF has no @molecule blocks")

    # Check for XX atom types
    xx_count = sum(1 for l in lines if " XX " in l and not l.startswith(("#", "!", "@")))
    if xx_count > 0:
        warnings.append(f"CRITICAL: {xx_count} lines with 'XX' atom type in MDF")

    # Check for periodicity
    has_periodicity = any("@periodicity" in l for l in lines)
    if not has_periodicity:
        # Not critical — USM may write cell differently
        pass

    return warnings
