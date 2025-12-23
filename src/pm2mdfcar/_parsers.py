"""Simple parsers for CAR, MDF, and PDB template files.

This module contains simple parsers used for template files.
For pandas-based legacy parsers, see _legacy_parsers.py.
"""

from __future__ import annotations

import re as _re
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

from ._models import (
    PDBAtom,
    TemplateAtom,
    _read_text,
    logger,
)

__all__ = [
    "_parse_car",
    "_parse_mdf_bonds",
    "_parse_wat_templates",
    "_parse_pdb",
]


def _parse_car(
    car_path: Path,
) -> Tuple[Dict[str, float], List[TemplateAtom], List[str]]:
    """Parse a Materials Studio 'archive 3' CAR file (template) into:
    - cell dict: {"a","b","c","alpha","beta","gamma"}
    - ordered template atoms (label, res_seq, atom_type, element, charge)
    - header comment lines (to optionally echo)

    Accepts atom lines like:
    Al1   x y z XXXX 1 alo1 Al 1.620
    H1    x y z XXXX 1 H*   H  0.410

    Raises ValueError if PBC line missing.
    """
    if not car_path.exists():
        raise FileNotFoundError(f"Template CAR not found: {car_path}")
    lines = _read_text(car_path)

    # Parse PBC
    cell = None
    pbc_re = _re.compile(
        r"^PBC\s+([+-]?\d+(?:\.\d+)?)\s+([+-]?\d+(?:\.\d+)?)\s+([+-]?\d+(?:\.\d+)?)\s+"
        r"([+-]?\d+(?:\.\d+)?)\s+([+-]?\d+(?:\.\d+)?)\s+([+-]?\d+(?:\.\d+)?)"
    )

    header_lines: List[str] = []
    atoms: List[TemplateAtom] = []

    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        if s.startswith("!"):
            header_lines.append(ln)
            continue
        if s.upper().startswith("PBC="):
            # keep it but we will write our own PBC line later
            header_lines.append(ln)
            continue
        m = pbc_re.match(s)
        if m:
            a, b, c, alpha, beta, gamma = map(float, m.groups())
            cell = {
                "a": a,
                "b": b,
                "c": c,
                "alpha": alpha,
                "beta": beta,
                "gamma": gamma,
            }
            header_lines.append(ln)
            continue
        if s.lower() == "end":
            # trailing end sections
            continue

        # Attempt to parse atom line
        # Expected tokens: label x y z XXXX res_seq atom_type element charge
        toks = s.split()
        if len(toks) >= 9 and toks[4].upper() == "XXXX":
            try:
                label = toks[0]
                # x = float(toks[1]); y = float(toks[2]); z = float(toks[3])  # coord unused in template
                res_seq = int(toks[5])
                atom_type = toks[6]
                element = toks[7]
                charge = float(toks[8])
                atoms.append(
                    TemplateAtom(
                        label=label,
                        res_seq=res_seq,
                        atom_type=atom_type,
                        element=element,
                        charge=charge,
                    )
                )
            except Exception:
                # Skip lines that don't conform exactly; not fatal for template
                logger.debug("Skipped non-conforming CAR atom line: %s", ln)
                continue

    if cell is None:
        raise ValueError(f"PBC line missing in template CAR: {car_path}")
    return cell, atoms, header_lines


def _parse_mdf_bonds(
    mdf_path: Path, template_atoms: Sequence[TemplateAtom]
) -> List[Tuple[int, int]]:
    """Parse bonds from MDF 'connections' column style.

    We only keep bonds between atoms present in the provided template_atoms
    (AS2 template). We build a mapping from (res_seq, label_upper) -> template_index
    using template_atoms (the parsing authority for atom presence/order).

    Returns list of unique, sorted index pairs (i, j) in template atom index space.
    """
    if not mdf_path.exists():
        raise FileNotFoundError(f"Template MDF not found: {mdf_path}")

    addr_to_idx: Dict[Tuple[int, str], int] = {
        (ta.res_seq, ta.label.upper()): i for i, ta in enumerate(template_atoms)
    }

    bonds_set: set[Tuple[int, int]] = set()
    name_re = _re.compile(r"^XXXX_(\d+):([A-Za-z0-9_]+)$")

    for ln in _read_text(mdf_path):
        s = ln.strip()
        if not s or s.startswith("!") or s.startswith("#") or s.startswith("@"):
            continue

        # Expect first token like: XXXX_23:Al1
        toks = s.split()
        if not toks:
            continue
        head = toks[0]
        m = name_re.match(head)
        if not m:
            continue

        try:
            cur_res = int(m.group(1))
            cur_label = m.group(2)
        except Exception:
            continue

        cur_addr = (cur_res, cur_label.upper())
        if cur_addr not in addr_to_idx:
            # Not part of the AS2 CAR catalogue; skip (e.g., ions, extra species)
            continue
        cur_idx = addr_to_idx[cur_addr]

        # MDF 'connections' are tokens after the 12th column; empirically tokens[12:]
        # But robustly: the MDF format defines 11 numeric/non-connection columns after head.
        # Here we simply take remaining tokens and attempt to parse addresses or local labels.
        conn_toks = toks[12:] if len(toks) > 12 else []
        for ct in conn_toks:
            # connections may be "Label" (same residue) or "XXXX_n:Label"
            if ":" in ct:
                mm = name_re.match(ct)
                if not mm:
                    continue
                res2 = int(mm.group(1))
                lab2 = mm.group(2)
            else:
                res2 = cur_res
                lab2 = ct

            addr2 = (res2, lab2.upper())
            if addr2 not in addr_to_idx:
                continue
            j = addr_to_idx[addr2]
            i, k = (cur_idx, j) if cur_idx <= j else (j, cur_idx)
            if i != k:
                bonds_set.add((i, k))

    bonds = sorted(bonds_set)
    return bonds


def _parse_wat_templates(
    templates_dir: Path,
) -> Tuple[List[TemplateAtom], List[Tuple[int, int]]]:
    """Parse WAT CAR/MDF template:
    - Return canonical atom order [O1, H1, H2]
    - Return bonds in that order (indices into that order)
    """
    wat_car = templates_dir / "WAT.car"
    wat_mdf = templates_dir / "WAT.mdf"
    if not wat_car.exists():
        raise FileNotFoundError(f"WAT.car not found in {templates_dir}")
    if not wat_mdf.exists():
        raise FileNotFoundError(f"WAT.mdf not found in {templates_dir}")

    # Parse WAT.car atom types, elements, charges (tolerate PBC=OFF with no numeric PBC line)
    wat_atoms_raw: List[TemplateAtom] = []
    for ln in _read_text(wat_car):
        s = ln.strip()
        if not s or s.startswith("!") or s.lower() == "end" or s.upper().startswith("PBC"):
            continue
        toks = s.split()
        if len(toks) >= 9 and toks[4].upper() == "XXXX":
            try:
                label = toks[0]
                res_seq = int(toks[5])
                atom_type = toks[6]
                element = toks[7]
                charge = float(toks[8])
                wat_atoms_raw.append(
                    TemplateAtom(
                        label=label,
                        res_seq=res_seq,
                        atom_type=atom_type,
                        element=element,
                        charge=charge,
                    )
                )
            except Exception:
                logger.debug("Skipped non-conforming WAT.car atom line: %s", ln)
                continue
    if not wat_atoms_raw:
        raise ValueError(f"No atoms parsed from WAT.car at {wat_car}")

    # Normalize into dict by label
    by_lab: Dict[str, TemplateAtom] = {a.label.upper(): a for a in wat_atoms_raw}
    # Expected labels present
    missing = [lab for lab in ("O1", "H1", "H2") if lab not in by_lab]
    if missing:
        raise ValueError(f"WAT.car missing labels {missing}; found {list(by_lab.keys())}")
    ordered: List[TemplateAtom] = [by_lab["O1"], by_lab["H1"], by_lab["H2"]]

    # Parse bonds from WAT.mdf using local molecule (res=1)
    # Build mapping for XXXX_1:Label -> index in 'ordered'
    addr_to_idx: Dict[Tuple[int, str], int] = {(1, "O1"): 0, (1, "H1"): 1, (1, "H2"): 2}
    name_re = _re.compile(r"^XXXX_(\d+):([A-Za-z0-9_]+)$")
    bonds_set: set[Tuple[int, int]] = set()

    for ln in _read_text(wat_mdf):
        s = ln.strip()
        if not s or s.startswith("!") or s.startswith("#") or s.startswith("@"):
            continue
        toks = s.split()
        if not toks:
            continue
        head = toks[0]
        m = name_re.match(head)
        if not m:
            continue
        try:
            res = int(m.group(1))
            lab = m.group(2).upper()
        except Exception:
            continue
        cur_addr = (res, lab)
        if cur_addr not in addr_to_idx:
            continue
        cur_idx = addr_to_idx[cur_addr]
        conn_toks = toks[12:] if len(toks) > 12 else []
        for ct in conn_toks:
            if ":" in ct:
                mm = name_re.match(ct)
                if not mm:
                    continue
                res2 = int(mm.group(1))
                lab2 = mm.group(2).upper()
            else:
                res2 = res
                lab2 = ct.upper()
            addr2 = (res2, lab2)
            if addr2 not in addr_to_idx:
                continue
            j = addr_to_idx[addr2]
            i, k = (cur_idx, j) if cur_idx <= j else (j, cur_idx)
            if i != k:
                bonds_set.add((i, k))

    bonds = sorted(bonds_set)
    return ordered, bonds


def _parse_pdb(pdb_path: Path) -> List[PDBAtom]:
    """Minimal PDB ATOM/HETATM parser. Returns list of atoms in file order."""
    if not pdb_path.exists():
        raise FileNotFoundError(f"PDB not found: {pdb_path}")

    atoms: List[PDBAtom] = []
    for ln in _read_text(pdb_path):
        if not (ln.startswith("ATOM") or ln.startswith("HETATM")):
            continue
        # Fixed columns per PDB spec
        try:
            serial = int(ln[6:11].strip())
        except Exception:
            continue
        name = ln[12:16].strip()
        resname = ln[17:20].strip()
        chain = ln[21:22].strip()
        resseq_str = ln[22:26].strip()
        try:
            resseq = int(_re.match(r"(-?\d+)", resseq_str).group(1)) if resseq_str else 0
        except Exception:
            resseq = 0
        try:
            x = float(ln[30:38].strip())
            y = float(ln[38:46].strip())
            z = float(ln[46:54].strip())
        except Exception:
            # attempt whitespace split fallback
            toks = ln.split()
            # expect tokens like: ATOM serial name resname chain resseq x y z ...
            if len(toks) >= 9:
                try:
                    x, y, z = float(toks[-6]), float(toks[-5]), float(toks[-4])
                except Exception:
                    continue
            else:
                continue
        element = ln[76:78].strip() if len(ln) >= 78 else ""
        if not element:
            # Infer element from atom name's first alpha char
            m = _re.search(r"[A-Za-z]", name)
            element = (m.group(0).upper() if m else "").title()
        atoms.append(
            PDBAtom(serial, name, resname, chain, resseq, x, y, z, element.title())
        )
    return atoms
