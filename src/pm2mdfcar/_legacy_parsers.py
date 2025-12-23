"""Legacy pandas-based parsers for CAR, MDF, and PDB files.

These parsers are used by the MolSAIC V2 builder functions and produce
pandas DataFrames for downstream processing.
"""

from __future__ import annotations

import logging
import re as _re
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as _pd

from ._models import ATOM_COLUMN_NAMES, _numeric_or_none

__all__ = [
    "parse_pdb",
    "parse_mdf",
    "parse_car",
]


def parse_pdb(pdb_path: Path) -> Tuple[_pd.DataFrame, _pd.DataFrame, dict]:
    """Parse a PDB file using pandas.

    Returns:
        Tuple of (atoms_df, residues_df, meta dict)
    """
    atoms = []
    meta: dict = {"source_file": str(pdb_path)}
    with pdb_path.open("r", errors="replace") as handle:
        for line in handle:
            if line.startswith("CRYST1"):
                try:
                    meta["box"] = {
                        "a": float(line[6:15]),
                        "b": float(line[15:24]),
                        "c": float(line[24:33]),
                        "alpha": float(line[33:40]),
                        "beta": float(line[40:47]),
                        "gamma": float(line[47:54]),
                        "space_group": line[55:66].strip(),
                        "z_value": line[66:70].strip(),
                    }
                except (ValueError, IndexError):
                    logging.warning("Could not parse CRYST1 line.")
            elif line.startswith("ATOM") or line.startswith("HETATM"):
                try:
                    record = {
                        "record_type": line[0:6].strip(),
                        "serial": int(line[6:11]),
                        "name": line[12:16].strip(),
                        "altLoc": line[16:17].strip(),
                        "resName": line[17:21].strip(),
                        "chainID": line[21:22].strip(),
                        "resSeq": int(line[22:26]),
                        "iCode": line[26:27].strip(),
                        "x": float(line[30:38]),
                        "y": float(line[38:46]),
                        "z": float(line[46:54]),
                        "occupancy": float(line[54:60]),
                        "tempFactor": float(line[60:66]),
                        "element": line[76:78].strip(),
                        "charge": line[78:80].strip(),
                    }
                    atoms.append(record)
                except (ValueError, IndexError):
                    logging.warning(f"Skipping malformed ATOM/HETATM line: {line.strip()}")
                    continue

    if not atoms:
        raise ValueError("No ATOM or HETATM records found in the PDB file.")

    atoms_df = _pd.DataFrame(atoms)
    residues_df = (
        atoms_df[["chainID", "resSeq", "resName"]]
        .drop_duplicates()
        .sort_values(by=["chainID", "resSeq"])
        .reset_index(drop=True)
    )
    return atoms_df, residues_df, meta


def parse_mdf(path: Path) -> Tuple[_pd.DataFrame, dict]:
    """Parse an MDF file using pandas.

    Returns:
        Tuple of (atoms_df, meta dict)
    """
    atoms: List[Dict] = []
    meta: Dict = {
        "source_file": str(path.resolve()),
        "date": None,
        "symmetry": {},
        "molecules": [],
    }

    with path.open("r", errors="replace") as handle:
        lines = handle.readlines()

    i = 0
    n = len(lines)
    in_topology = False
    current_mol = None

    while i < n:
        stripped = lines[i].strip()

        if stripped.startswith("!Date:"):
            meta["date"] = stripped.replace("!Date:", "", 1).strip()

        if stripped == "#topology":
            in_topology = True
            i += 1
            continue

        if in_topology:
            if stripped.startswith("#") and stripped in {"#symmetry", "#end"}:
                in_topology = False
                continue

            if stripped.startswith("@molecule"):
                current_mol = stripped.split(" ", 1)[1].strip()
                if current_mol not in meta["molecules"]:
                    meta["molecules"].append(current_mol)

            elif stripped.startswith("@") or stripped == "":
                pass

            else:
                toks = stripped.split()
                if len(toks) < 3:
                    i += 1
                    continue

                full_label_from_mdf = toks[0]
                prefix_match = _re.match(r"^(XXXX_\d+:)(.*)", full_label_from_mdf)
                if prefix_match:
                    label = full_label_from_mdf
                else:
                    label = full_label_from_mdf
                element = toks[1]
                atom_type = toks[2]

                record: Dict = {
                    "label": full_label_from_mdf,
                    "base_label": _re.sub(r"^(XXXX_\d+:)", "", full_label_from_mdf),
                    "molecule": current_mol,
                    "element": element,
                    "atom_type": atom_type,
                }

                numeric_column_names = ATOM_COLUMN_NAMES[2:-1]
                for col_name in numeric_column_names:
                    record[col_name] = None
                record["connections"] = ""

                current_token_idx = 3
                num_numeric_cols = len(numeric_column_names)

                for j in range(num_numeric_cols):
                    if current_token_idx < len(toks):
                        token = toks[current_token_idx]
                        parsed_val = _numeric_or_none(token)
                        if isinstance(parsed_val, str) and parsed_val not in {"", "?"}:
                            break
                        record[numeric_column_names[j]] = parsed_val
                        current_token_idx += 1
                    else:
                        break

                if current_token_idx < len(toks):
                    connections = " ".join(toks[current_token_idx:])
                    record["connections"] = connections

                atoms.append(record)

        if stripped == "#symmetry":
            sym: Dict = {}
            i += 1
            while i < n and not lines[i].strip().startswith("#"):
                line = lines[i].strip()
                if line.startswith("@periodicity"):
                    sym["periodicity"] = " ".join(line.split()[1:])
                elif line.startswith("@group"):
                    sym["group"] = line.split(" ", 1)[1].strip()
                i += 1
            meta["symmetry"] = sym
            continue

        i += 1

    atoms_df = _pd.DataFrame(atoms)
    fill_zero_cols = [
        "isotope",
        "switching_atom",
        "oop_flag",
        "chirality_flag",
        "occupancy",
        "xray_temp_factor",
    ]
    for col in fill_zero_cols:
        if col in atoms_df.columns:
            atoms_df[col] = _pd.to_numeric(atoms_df[col], errors="coerce").fillna(0)
    for col in ["formal_charge", "charge"]:
        if col in atoms_df.columns:
            atoms_df[col] = _pd.to_numeric(atoms_df[col], errors="coerce")
    return atoms_df, meta


def parse_car(path: Path) -> Tuple[_pd.DataFrame, dict]:
    """Parse a CAR file using pandas.

    Returns:
        Tuple of (atoms_df, meta dict)
    """
    meta: Dict[str, Any] = {
        "source_file": str(path.resolve()),
        "pbc": False,
        "cell": {},
        "header_lines": [],
    }
    atoms: List[Dict[str, Any]] = []

    with path.open("r", errors="replace") as fh:
        lines = fh.readlines()

    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        stripped = line.strip()

        tokens = stripped.split()
        is_atom_line = (
            len(tokens) >= 4
            and not tokens[0].upper().startswith("PBC")
            and _numeric_or_none(tokens[0]) is None
            and _numeric_or_none(tokens[1]) is not None
            and _numeric_or_none(tokens[2]) is not None
            and _numeric_or_none(tokens[3]) is not None
        )

        if is_atom_line:
            break

        meta["header_lines"].append(line)

        if stripped.upper().startswith("PBC="):
            meta["pbc"] = stripped.upper().split("=", 1)[1].strip() == "ON"
            if meta["pbc"]:
                temp_i = i + 1
                while temp_i < n and lines[temp_i].strip() == "":
                    temp_i += 1
                if temp_i < n:
                    cell_line = lines[temp_i].strip()
                    numeric_tokens = _re.findall(r"[-+]?\d*\.\d+|\d+", cell_line)
                    parsed_cell_params = [_numeric_or_none(t) for t in numeric_tokens[:6]]
                    if len(parsed_cell_params) >= 6 and all(
                        isinstance(p, (float, int)) for p in parsed_cell_params
                    ):
                        meta["cell"] = {
                            "a": parsed_cell_params[0],
                            "b": parsed_cell_params[1],
                            "c": parsed_cell_params[2],
                            "alpha": parsed_cell_params[3],
                            "beta": parsed_cell_params[4],
                            "gamma": parsed_cell_params[5],
                        }
        i += 1

    def _parse_atom_line(tokens: List[str]) -> Dict[str, Any]:
        if len(tokens) < 4:
            raise ValueError(f"Atom line too short: {' '.join(tokens)}")
        record: Dict[str, Any] = {
            "label": tokens[0],
            "x": _numeric_or_none(tokens[1]),
            "y": _numeric_or_none(tokens[2]),
            "z": _numeric_or_none(tokens[3]),
            "atom_type": None,
            "charge": None,
            "resid": None,
            "resname": None,
            "segment": None,
            "extras": "",
        }
        idx = 4
        if idx < len(tokens):
            if _numeric_or_none(tokens[idx]) is None and tokens[idx].strip() not in {
                "",
                "?",
            }:
                record["segment"] = tokens[idx]
                idx += 1
        if idx < len(tokens):
            resid_val = _numeric_or_none(tokens[idx])
            if isinstance(resid_val, int):
                record["resid"] = resid_val
                idx += 1
        if idx < len(tokens):
            if _numeric_or_none(tokens[idx]) is None and tokens[idx].strip() not in {
                "",
                "?",
            }:
                record["atom_type"] = tokens[idx]
                idx += 1
        if idx < len(tokens):
            if _numeric_or_none(tokens[idx]) is None and tokens[idx].strip() not in {
                "",
                "?",
            }:
                record["resname"] = tokens[idx]
                idx += 1
        if idx < len(tokens):
            charge_val = _numeric_or_none(tokens[idx])
            if isinstance(charge_val, (float, int)):
                record["charge"] = charge_val
                idx += 1
        if idx < len(tokens):
            record["extras"] = " ".join(tokens[idx:])
        return record

    while i < n:
        line = lines[i]
        stripped = line.strip()

        if stripped.lower().startswith("end"):
            meta["footer_lines"] = []
            while i < n:
                meta["footer_lines"].append(lines[i])
                i += 1
            break

        if not stripped or stripped.startswith("!"):
            i += 1
            continue

        tokens = stripped.split()
        if (
            len(tokens) >= 4
            and _numeric_or_none(tokens[0]) is None
            and _numeric_or_none(tokens[1]) is not None
            and _numeric_or_none(tokens[2]) is not None
            and _numeric_or_none(tokens[3]) is not None
        ):
            try:
                atoms.append(_parse_atom_line(tokens))
            except Exception as exc:
                atoms.append(
                    {
                        "label": tokens[0] if tokens else "",
                        "x": None,
                        "y": None,
                        "z": None,
                        "atom_type": None,
                        "charge": None,
                        "resid": None,
                        "resname": None,
                        "segment": None,
                        "extras": f"PARSE_ERROR: {exc}",
                    }
                )
        i += 1

    atoms_df = _pd.DataFrame(atoms)
    for col in ["x", "y", "z", "charge"]:
        atoms_df[col] = _pd.to_numeric(atoms_df[col], errors="coerce")
    return atoms_df, meta
