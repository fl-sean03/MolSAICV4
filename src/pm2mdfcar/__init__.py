"""pm2mdfcar operation.

Build a code-first replacement for the original pm2mdfcar step that composes
final Materials Studio CAR/MDF files from a hydrated PDB and template topologies.

Functionality:
- Load AS2 and WAT template CAR/MDF files
- Parse hydrated PDB; group atoms by residue
- Keep AS2 topology and replicate WAT topology per water molecule
- Compose deterministic output order and bonds
- Write CAR/MDF with PBC c set to a provided target

Exceptions:
- FileNotFoundError: missing hydrated PDB or template files
- ValueError: parsing errors, mismatched counts, or mapping failures
- RuntimeError: write failures (e.g., empty outputs)

No external deps beyond the Python stdlib.
"""

from __future__ import annotations

import csv as _csv
import json as _json
from pathlib import Path
from typing import List

# Re-export data models
from ._models import PDBAtom, TemplateAtom

# Re-export simple template parsers
from ._parsers import (
    _parse_car,
    _parse_mdf_bonds,
    _parse_pdb,
    _parse_wat_templates,
)

# Re-export legacy pandas-based parsers
from ._legacy_parsers import (
    parse_car,
    parse_mdf,
    parse_pdb,
)

# Re-export formatters
from ._formatters import (
    _format_car_atom,
    _format_car_header,
    _format_mdf_atom,
    _format_mdf_header,
    _to_old_full_label,
    _transform_connections_to_old,
)

# Re-export writers
from ._writers import write_car, write_mdf

# Re-export builders
from ._builders import (
    _legacy_build_car,
    _legacy_build_mdf,
    _legacy_load,
    _legacy_parse_pdb,
    build_combined_car,
    build_combined_mdf,
    load_mdf_templates,
)

# Re-export utilities from _models
from ._models import (
    ATOM_COLUMN_NAMES,
    _format_numeric_or_question,
    _normalize_name,
    _numeric_or_none,
    _read_text,
)

__all__ = [
    # Main public API
    "build",
    # Data models
    "TemplateAtom",
    "PDBAtom",
    # Constants
    "ATOM_COLUMN_NAMES",
    # Parsers (simple)
    "_parse_car",
    "_parse_mdf_bonds",
    "_parse_wat_templates",
    "_parse_pdb",
    # Parsers (legacy pandas-based)
    "parse_pdb",
    "parse_mdf",
    "parse_car",
    # Formatters
    "_format_car_header",
    "_format_car_atom",
    "_format_mdf_header",
    "_format_mdf_atom",
    "_to_old_full_label",
    "_transform_connections_to_old",
    # Writers
    "write_mdf",
    "write_car",
    # Builders
    "load_mdf_templates",
    "build_combined_mdf",
    "build_combined_car",
    # Legacy wrappers (for test monkeypatching compatibility)
    "_legacy_parse_pdb",
    "_legacy_load",
    "_legacy_build_mdf",
    "_legacy_build_car",
    # Utilities
    "_read_text",
    "_normalize_name",
    "_numeric_or_none",
    "_format_numeric_or_question",
]


def build(
    hydrated_pdb: str,
    templates_dir: str,
    output_prefix: str,
    target_c: float,
    resname_surface: str = "AS2",
    resname_water: str = "WAT",
) -> dict:
    """Compose final CAR/MDF from a hydrated PDB and AS2/WAT templates.

    Signature:
      def build(hydrated_pdb: str, templates_dir: str, output_prefix: str, target_c: float,
                resname_surface: str = "AS2", resname_water: str = "WAT") -> dict

    Behavior:
      - Loads AS2.car/mdf and WAT.car/mdf from templates_dir
      - Parses hydrated PDB (ATOM/HETATM) and groups atoms by residue
      - Constructs deterministic output order: AS2 (template order), then waters (resSeq ascending, O H H)
      - Assigns types/charges/labels via templates
      - Composes bonds: reuse AS2 connections; replicate WAT bonds per water residue
      - Writes CAR/MDF with numeric PBC where c is set to target_c
      - Returns metadata dict (paths, counts, cell, warnings)

    Raises:
      FileNotFoundError, ValueError, RuntimeError
    """
    warnings: List[str] = []

    templates_dir_path = Path(templates_dir)
    pdb_path = Path(hydrated_pdb)
    out_prefix = Path(output_prefix)
    out_prefix.parent.mkdir(parents=True, exist_ok=True)

    # Load templates
    as2_car = templates_dir_path / "AS2.car"
    as2_mdf = templates_dir_path / "AS2.mdf"
    if not as2_car.exists():
        raise FileNotFoundError(f"AS2.car not found in {templates_dir_path}")
    if not as2_mdf.exists():
        raise FileNotFoundError(f"AS2.mdf not found in {templates_dir_path}")

    as2_cell, as2_atoms, _ = _parse_car(as2_car)
    # Override c
    cell = dict(as2_cell)
    cell["c"] = float(target_c)

    # AS2 bonds in template index space
    as2_bonds_templ = _parse_mdf_bonds(as2_mdf, as2_atoms)

    # WAT template atoms (O1,H1,H2) and bonds in that order
    wat_atoms_tpl, wat_bonds_tpl = _parse_wat_templates(templates_dir_path)

    # Use a vendored legacy pm2mdfcar builder to reproduce MSI2LMP-compatible MDF/CAR
    # (kept for output compatibility/stability with existing pipelines).
    pdb_atoms_df, residues_df, pdb_meta = _legacy_parse_pdb(pdb_path)
    templates_legacy = _legacy_load(templates_dir_path)
    _legacy_build_mdf(
        pdb_atoms_df,
        pdb_meta,
        templates_legacy,
        out_prefix,
        templates_dir_path,
        target_c=float(target_c),
    )
    _legacy_build_car(pdb_atoms_df, pdb_meta, templates_legacy, out_prefix)

    car_path = out_prefix.with_suffix(".car")
    mdf_path = out_prefix.with_suffix(".mdf")
    if not car_path.exists() or car_path.stat().st_size == 0:
        raise RuntimeError(f"CAR write failed or empty: {car_path}")
    if not mdf_path.exists() or mdf_path.stat().st_size == 0:
        raise RuntimeError(f"MDF write failed or empty: {mdf_path}")

    # Cell from vendored meta (which already enforces c := target_c)
    meta_path = out_prefix.parent / f"{out_prefix.name}_meta.json"
    if meta_path.exists():
        try:
            meta = _json.loads(meta_path.read_text())
            box = meta.get("box") or {}
            if box:
                cell = {
                    "a": float(box.get("a", cell.get("a"))),
                    "b": float(box.get("b", cell.get("b"))),
                    "c": float(box.get("c", target_c)),
                    "alpha": float(box.get("alpha", cell.get("alpha"))),
                    "beta": float(box.get("beta", cell.get("beta"))),
                    "gamma": float(box.get("gamma", cell.get("gamma"))),
                }
        except Exception:
            pass

    # Counts via CSV emitted by vendored builder
    atoms_csv = out_prefix.parent / f"{out_prefix.name}_atoms.csv"
    total_atoms = 0
    surface_atoms_count = 0
    waters_count = 0
    if atoms_csv.exists():
        # Robust CSV handling: support files with or without header row
        text = atoms_csv.read_text(encoding="utf-8")
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if lines:
            header_tokens = [tok.strip().lower() for tok in lines[0].split(",")]
            has_header = ("serial" in header_tokens) or ("resname" in header_tokens)
            if has_header:
                reader = _csv.DictReader(lines)
                rows = list(reader)
                total_atoms = len(rows)
                surface_atoms_count = sum(
                    1
                    for r in rows
                    if (str(r.get("resname", "")).strip().upper() == resname_surface.upper())
                )
                water_atoms = sum(
                    1
                    for r in rows
                    if (
                        str(r.get("resname", "")).strip().upper()
                        in {resname_water.upper(), "HOH"}
                    )
                )
                waters_count = water_atoms // 3
            else:
                reader = _csv.reader(lines)
                data_rows = list(reader)
                total_atoms = len(data_rows)

                def _tok(row, idx):
                    try:
                        return str(row[idx]).strip().upper()
                    except Exception:
                        return ""

                surface_atoms_count = sum(
                    1 for row in data_rows if _tok(row, 1) == resname_surface.upper()
                )
                water_atoms = sum(
                    1
                    for row in data_rows
                    if _tok(row, 1) in {resname_water.upper(), "HOH"}
                )
                waters_count = water_atoms // 3

    bonds_count = len(as2_bonds_templ) + waters_count * len(wat_bonds_tpl)

    return {
        "car_file": str(car_path),
        "mdf_file": str(mdf_path),
        "counts": {
            "atoms": total_atoms,
            "bonds": bonds_count,
            "waters": waters_count,
            "surface_atoms": surface_atoms_count,
        },
        "cell": {
            "a": cell["a"],
            "b": cell["b"],
            "c": float(target_c),
            "alpha": cell["alpha"],
            "beta": cell["beta"],
            "gamma": cell["gamma"],
        },
        "warnings": warnings,
    }
