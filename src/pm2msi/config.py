"""Configuration for rn_v2 enrichment bridge."""

from __future__ import annotations

import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class TemplateConfig:
    """Configuration for a single molecule type template."""
    mdf: str                          # Path to MDF template file
    pdb_resname: str                  # Residue name in Packmol PDB (matched via mol_block_name)
    grouping: str = "separate"        # "single" (one block) or "separate" (per-molecule blocks)


@dataclass
class CellConfig:
    """Periodic boundary conditions.

    If a, b, c are all set: uses those values (explicit mode).
    If any are None: auto-derives from PDB bounding box + padding.
    """
    a: Optional[float] = None
    b: Optional[float] = None
    c: Optional[float] = None
    alpha: float = 90.0
    beta: float = 90.0
    gamma: float = 90.0
    spacegroup: str = "P1"
    padding: float = 5.0             # Angstroms added to each side when auto-deriving

    @property
    def is_explicit(self) -> bool:
        """True if all dimensions are explicitly set."""
        return self.a is not None and self.b is not None and self.c is not None


@dataclass
class SystemConfig:
    """Complete system configuration."""
    pdb: str                          # Packmol output PDB
    templates: list[TemplateConfig]   # One per molecule type
    cell: CellConfig                  # PBC specification (explicit or auto)
    output: str                       # Output prefix (writes {output}.car, {output}.mdf)
    base_molecule_name: str = "cbs"   # Base name for @molecule blocks in MDF


def load_config(path: str | Path) -> SystemConfig:
    """Load configuration from a YAML file.

    Cell dimensions can be explicit or auto-derived:

        # Explicit cell (recommended when you know the box size):
        cell:
          a: 120.0
          b: 120.0
          c: 120.0

        # Auto-derive from PDB bounding box (omit cell entirely or set padding):
        cell:
          padding: 5.0    # adds 5 A to each side of the bounding box

        # Or just omit cell: block — defaults to auto with 5 A padding
    """
    with open(path) as f:
        raw = yaml.safe_load(f)

    templates = []
    for t in raw["templates"]:
        templates.append(TemplateConfig(
            mdf=t["mdf"],
            pdb_resname=t["pdb_resname"],
            grouping=t.get("grouping", "separate"),
        ))

    cell_raw = raw.get("cell", {}) or {}

    # Check if explicit dimensions are provided
    has_a = "a" in cell_raw
    has_b = "b" in cell_raw
    has_c = "c" in cell_raw

    if has_a and has_b and has_c:
        # Explicit mode
        cell = CellConfig(
            a=float(cell_raw["a"]),
            b=float(cell_raw["b"]),
            c=float(cell_raw["c"]),
            alpha=float(cell_raw.get("alpha", 90.0)),
            beta=float(cell_raw.get("beta", 90.0)),
            gamma=float(cell_raw.get("gamma", 90.0)),
            spacegroup=cell_raw.get("spacegroup", "P1"),
            padding=float(cell_raw.get("padding", 5.0)),
        )
    else:
        # Auto mode — will derive from PDB bounding box
        cell = CellConfig(
            padding=float(cell_raw.get("padding", 5.0)),
            alpha=float(cell_raw.get("alpha", 90.0)),
            beta=float(cell_raw.get("beta", 90.0)),
            gamma=float(cell_raw.get("gamma", 90.0)),
            spacegroup=cell_raw.get("spacegroup", "P1"),
        )

    return SystemConfig(
        pdb=raw["pdb"],
        templates=templates,
        cell=cell,
        output=raw["output"],
        base_molecule_name=raw.get("base_molecule_name", "cbs"),
    )
