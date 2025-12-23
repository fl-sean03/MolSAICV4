"""Writers for CAR and MDF files.

This module contains functions for writing CAR and MDF files
from intermediate data (atoms DataFrame, meta JSON).
"""

from __future__ import annotations

import json as _json
import re as _re
from pathlib import Path

import pandas as _pd

from ._formatters import _to_old_full_label, _transform_connections_to_old
from ._models import ATOM_COLUMN_NAMES, _format_numeric_or_question

__all__ = [
    "write_mdf",
    "write_car",
]


def write_mdf(prefix, output_mdf=None):
    """Write an MDF file from intermediate files.

    Reads from {prefix}_atoms.parquet (or .csv), {prefix}_molecules.csv,
    and {prefix}_meta.json to produce the final MDF output.

    Args:
        prefix: Path prefix for intermediate files
        output_mdf: Optional output path; defaults to {prefix}.mdf
    """
    atoms_file_parquet = f"{prefix}_atoms.parquet"
    atoms_file_csv = f"{prefix}_atoms.csv"
    molecules_file = f"{prefix}_molecules.csv"
    meta_file = f"{prefix}_meta.json"

    if Path(atoms_file_parquet).exists():
        atoms_path = atoms_file_parquet
    elif Path(atoms_file_csv).exists():
        atoms_path = atoms_file_csv
    else:
        raise SystemExit(f"Error: Neither {atoms_file_parquet} nor {atoms_file_csv} found.")

    if not Path(molecules_file).exists():
        raise SystemExit(f"Error: {molecules_file} not found.")
    if not Path(meta_file).exists():
        raise SystemExit(f"Error: {meta_file} not found.")

    try:
        if atoms_path.endswith(".parquet"):
            atoms_df = _pd.read_parquet(atoms_path)
        else:
            atoms_df = _pd.read_csv(atoms_path, keep_default_na=False)
        if "connections" in atoms_df.columns:
            atoms_df["connections"] = atoms_df["connections"].fillna("").astype(str)
            atoms_df.loc[atoms_df["connections"].str.lower() == "nan", "connections"] = ""
        if "atom_type" in atoms_df.columns:
            atoms_df["atom_type"] = atoms_df["atom_type"].astype(str).str.strip()
            atoms_df.loc[atoms_df["atom_type"] == "H*", "atom_type"] = "h*"
            atoms_df.loc[atoms_df["atom_type"] == "O*", "atom_type"] = "o*"
        molecules_df = _pd.read_csv(molecules_file)
        with open(meta_file, "r") as f:
            meta_data = _json.load(f)
    except Exception as e:
        raise SystemExit(f"Error reading input files: {e}")

    if output_mdf is None:
        output_mdf = f"{prefix}.mdf"

    if "global_index" in atoms_df.columns:
        atoms_sorted = atoms_df.sort_values(by="global_index")
    else:
        atoms_sorted = atoms_df.sort_values(by=["molecule", "serial"], kind="stable")

    with open(output_mdf, "w") as f:
        f.write("!BIOSYM molecular_data 4\n")
        f.write(" \n")
        if "date" in meta_data:
            f.write(f"!Date: {meta_data['date']}\n")
        else:
            f.write("!Date: Unknown\n")
        f.write(" \n")
        f.write("#topology\n")
        f.write("\n")
        for i, col_name in enumerate(ATOM_COLUMN_NAMES[:-1]):
            f.write(f"@column {i + 1} {col_name}\n")
        f.write(f"@column {len(ATOM_COLUMN_NAMES)} connections\n")
        f.write(" \n")

        current_molecule = None
        for _, row in atoms_sorted.iterrows():
            mol_name = str(row.get("molecule", ""))
            if mol_name != current_molecule:
                if current_molecule is not None:
                    f.write(" \n")
                f.write(f"@molecule {mol_name}\n\n")
                current_molecule = mol_name

            raw_label = (
                row.get("full_mdf_label")
                or row.get("mdf_label")
                or row.get("car_label")
                or ""
            )
            label = _to_old_full_label(str(raw_label))

            element = str(row.get("element", "") or "")
            atom_type = str(row.get("atom_type", "") or "")
            charge_group = _format_numeric_or_question(row.get("charge_group"))
            isotope = _format_numeric_or_question(row.get("isotope"))
            formal_charge = _format_numeric_or_question(
                row.get("formal_charge"), is_formal_charge=True
            )
            charge = _format_numeric_or_question(
                row.get("charge"), is_float=True, default_val="0.0000"
            )
            switching_atom = _format_numeric_or_question(
                row.get("switching_atom"), default_val="0"
            )
            oop_flag = _format_numeric_or_question(row.get("oop_flag"), default_val="0")
            chirality_flag = _format_numeric_or_question(
                row.get("chirality_flag"), default_val="0"
            )
            occupancy = _format_numeric_or_question(
                row.get("occupancy"), is_float=True, default_val="1.0000"
            )
            xray_temp_factor = _format_numeric_or_question(
                row.get("xray_temp_factor"), is_float=True, default_val="0.0000"
            )

            connections = _transform_connections_to_old(row.get("connections", ""))

            atom_line = (
                f"{label:<20}"
                f"{element:<3}"
                f"{atom_type:<8}"
                f"{charge_group:<6}"
                f"{isotope:<3}"
                f"{formal_charge:<4}"
                f"{charge:>10}"
                f"{switching_atom:>2}"
                f"{oop_flag:>2}"
                f"{chirality_flag:>2}"
                f"{occupancy:>7}"
                f"{xray_temp_factor:>8}"
                f" {connections}"
            )
            f.write(atom_line + "\n")

        f.write("\n!\n")
        f.write("#end\n")


def write_car(prefix_path: Path, output_car_path: Path = None):
    """Write a CAR file from intermediate files.

    Reads from {prefix}_atoms.parquet (or .csv) and {prefix}_meta.json
    to produce the final CAR output.

    Args:
        prefix_path: Path prefix for intermediate files
        output_car_path: Optional output path; defaults to {prefix}.car
    """
    input_dir = prefix_path.parent
    file_stem = prefix_path.name

    atoms_parq = input_dir / f"{file_stem}_atoms.parquet"
    atoms_csv = input_dir / f"{file_stem}_atoms.csv"
    meta_file = input_dir / f"{file_stem}_meta.json"

    if not meta_file.exists():
        raise SystemExit(
            f"Error: Meta file not found for prefix '{prefix_path}' in {input_dir}"
        )

    atoms_df = None
    if atoms_parq.exists():
        try:
            atoms_df = _pd.read_parquet(atoms_parq)
        except Exception as e:
            print(
                f"[WARN] read_parquet failed ({e}); attempting CSV fallback for {file_stem}_atoms.csv"
            )
            atoms_df = None
    if atoms_df is None:
        if atoms_csv.exists():
            atoms_df = _pd.read_csv(atoms_csv)
        else:
            raise SystemExit(
                f"Error: Neither Parquet nor CSV atoms files found for prefix '{prefix_path}' in {input_dir}"
            )

    if "atom_type" in atoms_df.columns:
        atoms_df["atom_type"] = atoms_df["atom_type"].astype(str).str.strip()
        atoms_df.loc[atoms_df["atom_type"] == "H*", "atom_type"] = "h*"
        atoms_df.loc[atoms_df["atom_type"] == "O*", "atom_type"] = "o*"

    with meta_file.open("r") as f:
        meta = _json.load(f)

    a_cell = None
    b_cell = None
    box_info = meta.get("box") if isinstance(meta.get("box"), dict) else None
    if box_info:
        try:
            a_cell = float(box_info.get("a")) if box_info.get("a") is not None else None
            b_cell = float(box_info.get("b")) if box_info.get("b") is not None else None
        except Exception:
            pass
    if a_cell is None or b_cell is None:
        hdr = meta.get("header_lines", [])
        for hl in hdr:
            s = str(hl).strip()
            if s.upper().startswith("PBC") and "=" not in s.upper():
                nums = _re.findall(r"[-+]?\d*\.\d+|\d+", s)
                if len(nums) >= 2:
                    try:
                        a_cell = float(nums[0])
                        b_cell = float(nums[1])
                    except Exception:
                        pass
                break

    def _wrap_coord(val, L):
        if L is None or _pd.isna(val):
            return val
        w = val % L
        if abs(w - L) < 1e-9 or w >= L:
            w -= L
        if w < 0:
            w += L
        return w

    if output_car_path is None:
        output_car_path = input_dir / f"{file_stem}.car"

    with output_car_path.open("w") as f:
        header_lines = meta.get("header_lines", [])
        for i in range(4):
            if i < len(header_lines):
                f.write(header_lines[i])
            else:
                f.write(" \n")

        if "global_index" in atoms_df.columns:
            atoms_sorted = atoms_df.sort_values(by="global_index")
        else:
            atoms_sorted = atoms_df.sort_values(by=["molecule", "serial"], kind="stable")

        current_mol = None
        for _, row in atoms_sorted.iterrows():
            mol_name = row.get("molecule", "")
            if current_mol is None:
                current_mol = mol_name
            elif mol_name != current_mol:
                f.write("end\n")
                current_mol = mol_name

            full = str(
                row.get("full_mdf_label")
                or row.get("mdf_label")
                or row.get("car_label")
                or ""
            )
            x = row.get("x")
            y = row.get("y")
            z = row.get("z")
            if a_cell is not None:
                x = _wrap_coord(x, a_cell)
            if b_cell is not None:
                y = _wrap_coord(y, b_cell)
            atom_type = str(row.get("atom_type", "") or "").lower()
            resname = str(row.get("resname", "") or "")
            element = str(row.get("element", "") or "")
            charge = row.get("charge")

            base_label = None
            # allow ion-like labels (na+, cl-) in the label/name field
            name_re = r"[A-Za-z0-9_+\-]+"
            m = _re.match(rf"^XXXX_\d+:({name_re})$", full)
            if m:
                base_label = m.group(1)
            if base_label is None:
                m = _re.match(rf"^MOL_\d+:(XXXX_\d+)_({name_re})$", full)
                if m:
                    base_label = m.group(2)
            if base_label is None:
                m = _re.match(rf"^(XXXX_\d+)_({name_re})$", full)
                if m:
                    base_label = m.group(2)
            if base_label is None:
                base_label = str(
                    row.get("label") or row.get("car_label") or row.get("element") or ""
                )

            atom_id = ""
            m = _re.match(r"^(XXXX_\d+):", full)
            if m:
                atom_id = m.group(1)
            else:
                m = _re.match(r"^MOL_\d+:(XXXX_\d+)_", full)
                if m:
                    atom_id = m.group(1)
                else:
                    m = _re.match(r"^(XXXX_\d+)_", full)
                    if m:
                        atom_id = m.group(1)
            atom_id_str = f"{atom_id.replace('_', ' '):<12}" if atom_id else " " * 12

            label_str = f"{base_label:<9}"
            x_str = f"{x:13.9f}" if _pd.notna(x) else " " * 13
            y_str = f"{y:13.9f}" if _pd.notna(y) else " " * 13
            z_str = f"{z:13.9f}" if _pd.notna(z) else " " * 13
            atom_type_str = f" {atom_type:<6}"
            resname_out = resname or element
            resname_str = f" {resname_out:<6}"
            charge_str = f" {charge:8.4f}" if _pd.notna(charge) else " " * 9

            f.write(
                f"{label_str}{x_str}    {y_str}    {z_str} {atom_id_str}{atom_type_str}{resname_str}{charge_str}\n"
            )

        footer_lines = meta.get("footer_lines")
        if footer_lines and isinstance(footer_lines, list) and len(footer_lines) > 0:
            for line_footer in footer_lines:
                f.write(line_footer if line_footer.endswith("\n") else line_footer + "\n")
        else:
            f.write("end\n")
            f.write("end\n")
