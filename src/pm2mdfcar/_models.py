"""Data models and common utilities for pm2mdfcar.

This module contains:
- Data classes for atoms (TemplateAtom, PDBAtom)
- Column name constants for MDF files
- Common utility functions used across parsers and writers
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List

import pandas as _pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TemplateAtom:
    """Represents an atom from a CAR template file."""

    label: str  # e.g., "Al1", "O1", "H1"
    res_seq: int  # numeric residue (from CAR "XXXX <res_seq>")
    atom_type: str  # e.g., "alo1", "o*", "h*"
    element: str  # "Al", "O", "H", etc
    charge: float  # partial charge (from CAR)


@dataclass
class PDBAtom:
    """Represents an atom from a PDB file."""

    serial: int
    name: str  # atom name from PDB (columns 13-16)
    resname: str  # residue name from PDB (columns 18-20)
    chain: str  # chain ID
    resseq: int  # residue sequence integer
    x: float
    y: float
    z: float
    element: str


# 11 canonical MDF columns (+ trailing connections)
ATOM_COLUMN_NAMES = [
    "element",
    "atom_type",
    "charge_group",
    "isotope",
    "formal_charge",
    "charge",
    "switching_atom",
    "oop_flag",
    "chirality_flag",
    "occupancy",
    "xray_temp_factor",
    "connections",
]


def _read_text(path: Path) -> List[str]:
    """Read a text file and return its lines."""
    return path.read_text().splitlines()


def _normalize_name(name: str) -> str:
    """Normalize an atom name to uppercase stripped string."""
    return name.strip().upper()


def _numeric_or_none(val: str):
    """Parse a string value to numeric (int or float) or return None.

    Handles special cases like '?' and ionic notation (e.g., '2+', '1-').
    """
    val = val.strip()
    if val in {"", "?"}:
        return None
    try:
        if val.endswith("+"):
            return int(val[:-1])
        if val.endswith("-"):
            return -int(val[:-1])
        if "." in val or "e" in val.lower():
            return float(val)
        return int(val)
    except ValueError:
        return None


def _format_numeric_or_question(
    value, is_float=False, default_val="?", is_formal_charge=False
):
    """Format a numeric value for MDF output.

    Args:
        value: The value to format
        is_float: Whether to format as float
        default_val: Default value if None/NaN
        is_formal_charge: Whether this is a formal charge field

    Returns:
        Formatted string representation
    """
    if value is None:
        return default_val
    try:
        if _pd.isna(value):
            return default_val
    except Exception:
        pass
    if isinstance(value, str):
        s = value.strip()
        if s == "" or s.lower() in {"nan", "na", "none", "null", "?"}:
            return default_val
        if is_formal_charge:
            try:
                if s.endswith("+"):
                    v = int(s[:-1]) if s[:-1] else 0
                elif s.endswith("-"):
                    v = -int(s[:-1]) if s[:-1] else 0
                else:
                    v = int(float(s))
            except Exception:
                return default_val
            if v > 0:
                return f"{v:>2}+"
            if v < 0:
                return f"{abs(v):>2}-"
            return f"{v:>2} "
        try:
            if is_float:
                return f"{float(s):.4f}"
            else:
                return str(int(float(s)))
        except Exception:
            return default_val
    if is_formal_charge:
        try:
            v = int(value)
        except Exception:
            try:
                v = int(float(value))
            except Exception:
                return default_val
        if v > 0:
            return f"{v:>2}+"
        if v < 0:
            return f"{abs(v):>2}-"
        return f"{v:>2} "
    if is_float:
        try:
            return f"{float(value):.4f}"
        except Exception:
            return default_val
    else:
        try:
            return str(int(value))
        except Exception:
            try:
                return str(int(float(value)))
            except Exception:
                return default_val
