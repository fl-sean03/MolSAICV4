"""Formatting functions for CAR and MDF output.

This module contains functions for formatting atoms, headers,
and other components of CAR and MDF files.
"""

from __future__ import annotations

import datetime
import re as _re
from typing import List, Sequence

__all__ = [
    "_format_car_header",
    "_format_car_atom",
    "_format_mdf_header",
    "_format_mdf_atom",
    "_to_old_full_label",
    "_transform_connections_to_old",
]


def _format_car_header(
    a: float, b: float, c: float, alpha: float, beta: float, gamma: float
) -> List[str]:
    """Format the header lines for a CAR file.

    Args:
        a, b, c: Cell dimensions in Angstroms
        alpha, beta, gamma: Cell angles in degrees

    Returns:
        List of header lines for the CAR file
    """
    now = datetime.datetime.now().strftime("%a %b %d %H:%M:%S %Y")
    return [
        "!BIOSYM archive 3",
        "PBC=ON",
        "pm2mdfcar generated CAR File",
        f"!DATE {now}",
        f"PBC {a:10.6f} {b:10.6f} {c:10.6f} {alpha:10.6f} {beta:10.6f} {gamma:10.6f} (P1)",
    ]


def _format_car_atom(
    label: str,
    x: float,
    y: float,
    z: float,
    res_seq: int,
    atom_type: str,
    element: str,
    charge: float,
) -> str:
    """Format a single atom line for a CAR file.

    Args:
        label: Atom label (e.g., "Al1")
        x, y, z: Atomic coordinates
        res_seq: Residue sequence number
        atom_type: Force field atom type
        element: Element symbol
        charge: Partial charge

    Returns:
        Formatted atom line string
    """
    # Match general spacing style seen in templates
    return f"{label:<8s}{x:14.6f}{y:14.6f}{z:14.6f} XXXX {res_seq:<6d}{atom_type:<8s}{element:>3s}{charge:8.3f}"


def _format_mdf_header() -> List[str]:
    """Format the header lines for an MDF file.

    Returns:
        List of header lines for the MDF file
    """
    now = datetime.datetime.now().strftime("%a %b %d %H:%M:%S %Y")
    return [
        "!BIOSYM molecular_data 4",
        "",
        f"!Date: {now}   pm2mdfcar output MDF file",
        "",
        "#topology",
        "",
        "@column 1 element",
        "@column 2 atom_type",
        "@column 3 charge_group",
        "@column 4 isotope",
        "@column 5 formal_charge",
        "@column 6 charge",
        "@column 7 switching_atom",
        "@column 8 oop_flag",
        "@column 9 chirality_flag",
        "@column 10 occupancy",
        "@column 11 xray_temp_factor",
        "@column 12 connections",
        "",
        "@molecule Combined",
        "",
    ]


def _format_mdf_atom(
    stamp: str, element: str, atom_type: str, charge: float, connections: Sequence[str]
) -> str:
    """Format a single atom line for an MDF file.

    Args:
        stamp: Atom stamp (e.g., "XXXX_23:Al1")
        element: Element symbol
        atom_type: Force field atom type
        charge: Partial charge
        connections: List of connected atom labels

    Returns:
        Formatted atom line string
    """
    # Columns per templates; we keep unknowns/zeros similar to examples; formal_charge set to 0
    # stamp example: "XXXX_23:Al1"
    # connections: tokens separated by spaces
    conns = " ".join(connections)
    return f"{stamp:<16s} {element:<2s} {atom_type:<7s} ?     0  0    {charge:8.4f} 0 0 8 1.0000  0.0000 {conns}".rstrip()


def _to_old_full_label(label_token: str) -> str:
    """Normalize the first MDF column ("label") into the legacy `XXXX_####:NAME` form.

    Why:
    - `msi2lmp` expects CAR/MDF labels to agree. It effectively compares
      `XXXX_####:<car_label>` (from CAR) with `XXXX_####:<mdf_label>` (from MDF).
    - Our hydrated pH workflows include counterions with names like `na+2593Na`.
      The legacy normalization regex used to reject '+' / '-' and therefore left
      labels in the underscore form (e.g. `XXXX_2593_na+2593Na`), which does not
      match the CAR-side `XXXX_2593:na+2593Na`.

    Policy:
    - Allow '+'/'-' in the "name" portion of the stamp so ions normalize the same
      way as slab/water atoms.

    Args:
        label_token: The label token to normalize

    Returns:
        Normalized label in XXXX_####:NAME format
    """
    if not isinstance(label_token, str) or not label_token:
        return label_token or ""
    s = label_token.strip()

    # allow ion-like labels (na+, cl-) in the "name" field
    name_re = r"[A-Za-z0-9_+\-]+"

    if _re.match(rf"^XXXX_\d+:{name_re}$", s):
        return s

    m = _re.match(rf"^MOL_\d+:(XXXX_\d+)_({name_re})$", s)
    if m:
        return f"{m.group(1)}:{m.group(2)}"

    m = _re.match(rf"^(XXXX_\d+)_({name_re})$", s)
    if m:
        return f"{m.group(1)}:{m.group(2)}"

    m = _re.match(rf"^MOL_\d+:(XXXX_\d+:{name_re})$", s)
    if m:
        return m.group(1)

    return s


def _transform_connections_to_old(connections_str: str) -> str:
    """Convert connection tokens into the legacy label style.

    Preserves MSI-style suffix metadata like '%0-10#1'.

    Tokens can look like:
      - "XXXX_123:O"
      - "XXXX_123:O%0-10#1"
      - "O%100#1"

    IMPORTANT:
    Historically we used a regex that only preserved bare '%' / '#', which truncated
    suffixes like '%0-10#1' to '%' and broke downstream tools (notably msi2lmp
    connect-count validation).

    Args:
        connections_str: Space-separated connection tokens

    Returns:
        Transformed connections string with legacy-style labels
    """
    if not isinstance(connections_str, str) or not connections_str.strip():
        return ""
    out_tokens: list[str] = []
    for token in connections_str.split():
        s = str(token)

        idx_pct = s.find("%")
        idx_hash = s.find("#")
        idxs = [i for i in (idx_pct, idx_hash) if i != -1]
        cut = min(idxs) if idxs else -1

        if cut == -1:
            atom_id = s
            op = ""
        else:
            atom_id = s[:cut]
            op = s[cut:]

        out_tokens.append(_to_old_full_label(atom_id) + op)

    return " ".join(out_tokens)
