"""Core enrichment logic for pm2msi.

Index-based positional matching: PDB atoms are matched to MDF template atoms
by their position within each residue group, not by name. This handles any
atom count without the >999 name mismatch problem.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

import usm

from .config import SystemConfig, load_config
from .validation import validate_enrichment, validate_mdf_output

logger = logging.getLogger(__name__)

# FF columns to copy from template → enriched structure
FF_COLUMNS = [
    "atom_type", "charge", "connections_raw",
    "isotope", "formal_charge", "switching_atom",
    "oop_flag", "chirality_flag", "occupancy", "xray_temp_factor",
    "charge_group",
]


def build(config_path: str | Path) -> dict:
    """Build enriched CAR/MDF from a YAML config file.

    Args:
        config_path: Path to system YAML configuration.

    Returns:
        Dict with keys: car_file, mdf_file, summary, warnings.
    """
    config = load_config(config_path)
    # Resolve relative paths against config file's directory
    config_dir = Path(config_path).resolve().parent
    if not Path(config.pdb).is_absolute():
        config.pdb = str(config_dir / config.pdb)
    for tc in config.templates:
        if not Path(tc.mdf).is_absolute():
            tc.mdf = str(config_dir / tc.mdf)
    if not Path(config.output).is_absolute():
        config.output = str(config_dir / config.output)
    return enrich(config)


def _load_pdb_robust(pdb_path: Path) -> usm.USM:
    """Load PDB with fallback for large systems (>99,999 atoms).

    USM's PDB parser can't handle hexadecimal atom serials that Packmol
    writes for systems exceeding the PDB 5-digit serial limit.
    This function tries USM first, then falls back to column-based parsing
    if USM reads fewer atoms than the file contains.
    """
    # Count actual ATOM lines in file
    n_lines = 0
    with open(pdb_path) as f:
        for line in f:
            if line.startswith(("ATOM", "HETATM")):
                n_lines += 1

    # Try USM
    pdb = usm.load(str(pdb_path))
    if len(pdb.atoms) == n_lines:
        return pdb

    logger.warning(
        f"USM read {len(pdb.atoms)}/{n_lines} atoms (PDB may have hex serials). "
        f"Using column-based fallback parser."
    )

    # Column-based PDB parsing (handles any serial format)
    rows = []
    with open(pdb_path) as f:
        for line in f:
            if not line.startswith(("ATOM", "HETATM")):
                continue
            name = line[12:16].strip()
            resname = line[17:20].strip()
            # resSeq: columns 22-26, may be hex for large systems
            resseq_str = line[22:26].strip()
            try:
                resseq = int(resseq_str)
            except ValueError:
                try:
                    resseq = int(resseq_str, 16)
                except ValueError:
                    resseq = 0
            x = float(line[30:38])
            y = float(line[38:46])
            z = float(line[46:54])
            element = line[76:78].strip() if len(line) > 76 else name[0]
            rows.append({
                "name": name, "element": element,
                "x": x, "y": y, "z": z,
                "mol_block_name": resname,
                "mol_index": resseq,
                "mol_label": "XXXX",
                "atom_type": "", "charge": 0.0,
                "mass_amu": None, "lj_epsilon_kcal_mol": None,
                "lj_sigma_angstrom": None,
                "isotope": None, "formal_charge": None,
                "switching_atom": None, "oop_flag": None,
                "chirality_flag": None, "occupancy": None,
                "xray_temp_factor": None, "charge_group": None,
                "connections_raw": None,
            })

    df = pd.DataFrame(rows)
    df["aid"] = range(1, len(df) + 1)
    return usm.USM(atoms=df)


def enrich(config: SystemConfig) -> dict:
    """Run the full enrichment pipeline.

    1. Load Packmol PDB (coordinates only).
    2. Load MDF templates (force field data).
    3. Group PDB atoms by residue type (mol_block_name).
    4. For each group, match atoms to template by positional index.
    5. Copy FF columns from template to structure.
    6. Assign molecule grouping (single block vs separate molecules).
    7. Set PBC cell.
    8. Write CAR and MDF.

    Args:
        config: SystemConfig with all paths and parameters.

    Returns:
        Dict with keys: car_file, mdf_file, summary, warnings.
    """
    warnings = []

    # --- Step 1: Load PDB ---
    pdb_path = Path(config.pdb)
    logger.info(f"Loading PDB: {pdb_path}")
    pdb = _load_pdb_robust(pdb_path)
    logger.info(f"  Atoms: {len(pdb.atoms)}")

    # --- Step 2: Load templates ---
    templates = {}
    for tc in config.templates:
        mdf_path = Path(tc.mdf)
        logger.info(f"Loading template: {mdf_path} (resname={tc.pdb_resname})")
        tpl = usm.load(str(mdf_path))
        templates[tc.pdb_resname] = {
            "structure": tpl,
            "config": tc,
            "n_atoms": len(tpl.atoms),
        }
        logger.info(f"  Template atoms: {len(tpl.atoms)}, types: {tpl.atoms['atom_type'].unique().tolist()}")

    # --- Step 3: Pre-flight validation ---
    atoms = pdb.atoms.copy()
    resname_col = "mol_block_name"
    unique_resnames = atoms[resname_col].unique().tolist()
    logger.info(f"PDB residue types: {unique_resnames}")

    # Check 1: Every PDB residue has a matching template
    resname_map = {}
    missing_templates = []
    for pdb_resname in unique_resnames:
        matched = False
        for tpl_resname, tpl_data in templates.items():
            if pdb_resname.strip().upper() == tpl_resname.strip().upper():
                resname_map[pdb_resname] = tpl_resname
                matched = True
                break
        if not matched:
            n_atoms = int((atoms[resname_col] == pdb_resname).sum())
            missing_templates.append((pdb_resname, n_atoms))

    if missing_templates:
        msg_parts = [f"'{name}' ({n} atoms)" for name, n in missing_templates]
        raise ValueError(
            f"Missing templates for PDB residues: {', '.join(msg_parts)}. "
            f"Templates provided: {list(templates.keys())}. "
            f"Every molecule type in the Packmol PDB must have a corresponding "
            f"MDF template in the config."
        )

    # Check 2: Every template is used by at least one PDB residue
    unused_templates = []
    for tpl_resname in templates:
        if tpl_resname not in resname_map.values():
            unused_templates.append(tpl_resname)
    if unused_templates:
        warnings.append(
            f"Templates provided but not found in PDB: {unused_templates}. "
            f"PDB residues: {unique_resnames}"
        )

    # Check 3: Atom count divisibility (each molecule group must be a multiple of template size)
    for pdb_resname, tpl_resname in resname_map.items():
        tpl_n = templates[tpl_resname]["n_atoms"]
        tc = templates[tpl_resname]["config"]
        group_n = int((atoms[resname_col] == pdb_resname).sum())

        if tc.grouping == "single":
            if group_n != tpl_n:
                raise ValueError(
                    f"Atom count mismatch for '{pdb_resname}' (grouping=single): "
                    f"PDB has {group_n} atoms, template has {tpl_n}. Must match exactly."
                )
        elif tc.grouping == "separate":
            if group_n % tpl_n != 0:
                raise ValueError(
                    f"Atom count mismatch for '{pdb_resname}' (grouping=separate): "
                    f"PDB has {group_n} atoms, template has {tpl_n} per molecule. "
                    f"{group_n} is not evenly divisible by {tpl_n}."
                )
            n_mols = group_n // tpl_n
            logger.info(f"  '{pdb_resname}': {n_mols} molecules × {tpl_n} atoms = {group_n}")

    logger.info("Pre-flight validation passed")

    # --- Step 4: Index-based enrichment ---
    enriched_rows = []
    molecule_assignments = []  # (mol_label, mol_index, mol_block_name) per atom
    mol_counter = 0

    # Process templates in config order (determines output ordering)
    for tc in config.templates:
        tpl_key = tc.pdb_resname
        tpl_data = templates[tpl_key]
        tpl_atoms = tpl_data["structure"].atoms
        n_tpl = tpl_data["n_atoms"]

        # Find matching PDB atoms
        pdb_resname = None
        for k, v in resname_map.items():
            if v == tpl_key:
                pdb_resname = k
                break

        mask = atoms[resname_col] == pdb_resname
        group_atoms = atoms[mask].copy()
        n_group = len(group_atoms)

        if n_group == 0:
            warnings.append(f"No atoms found for residue '{tpl_key}' (PDB name: '{pdb_resname}')")
            continue

        logger.info(f"Enriching '{tpl_key}': {n_group} PDB atoms, template has {n_tpl} atoms")

        if tc.grouping == "single":
            # All atoms belong to one molecule block
            if n_group != n_tpl:
                # For NPs: PDB should have exactly n_tpl atoms
                # Allow if it's a multiple (shouldn't happen for "single")
                if n_group % n_tpl != 0:
                    warnings.append(
                        f"Atom count mismatch for '{tpl_key}': PDB has {n_group}, "
                        f"template has {n_tpl} (not evenly divisible)"
                    )

            mol_counter += 1
            for i, (idx, row) in enumerate(group_atoms.iterrows()):
                t_idx = i % n_tpl
                enriched = _enrich_atom(row, tpl_atoms.iloc[t_idx], i)
                enriched_rows.append(enriched)
                molecule_assignments.append({
                    "mol_label": "XXXX",
                    "mol_index": 1,
                    "mol_block_name": f"{config.base_molecule_name}",
                })

        elif tc.grouping == "separate":
            # Each molecule is a separate block, identified by mol_index in PDB
            mol_indices = group_atoms["mol_index"].unique()
            mol_indices.sort()

            for mol_idx in mol_indices:
                mol_mask = group_atoms["mol_index"] == mol_idx
                mol_atoms = group_atoms[mol_mask]
                n_mol = len(mol_atoms)

                if n_mol != n_tpl:
                    warnings.append(
                        f"Molecule {tpl_key}#{mol_idx}: {n_mol} atoms, "
                        f"template has {n_tpl}"
                    )

                mol_counter += 1
                for i, (idx, row) in enumerate(mol_atoms.iterrows()):
                    t_idx = i % n_tpl
                    enriched = _enrich_atom(row, tpl_atoms.iloc[t_idx], i)
                    enriched_rows.append(enriched)
                    molecule_assignments.append({
                        "mol_label": "XXXX",
                        "mol_index": int(mol_idx),
                        "mol_block_name": f"{config.base_molecule_name}_{tpl_key}_{mol_idx}",
                    })

    # --- Step 5: Assemble enriched structure ---
    enriched_df = pd.DataFrame(enriched_rows)
    mol_df = pd.DataFrame(molecule_assignments)
    enriched_df["mol_label"] = mol_df["mol_label"].values
    enriched_df["mol_index"] = mol_df["mol_index"].values
    enriched_df["mol_block_name"] = mol_df["mol_block_name"].values
    enriched_df["aid"] = range(1, len(enriched_df) + 1)

    # --- Step 6: Set cell ---
    if config.cell.is_explicit:
        # Explicit mode: use specified dimensions
        cell = {
            "pbc": True,
            "a": config.cell.a,
            "b": config.cell.b,
            "c": config.cell.c,
            "alpha": config.cell.alpha,
            "beta": config.cell.beta,
            "gamma": config.cell.gamma,
            "spacegroup": config.cell.spacegroup,
        }
        logger.info(f"Cell (explicit): {config.cell.a} x {config.cell.b} x {config.cell.c}")
    else:
        # Auto mode: derive from bounding box of enriched coordinates + padding
        padding = config.cell.padding
        x_min, x_max = enriched_df["x"].min(), enriched_df["x"].max()
        y_min, y_max = enriched_df["y"].min(), enriched_df["y"].max()
        z_min, z_max = enriched_df["z"].min(), enriched_df["z"].max()

        a = float(x_max - x_min + 2 * padding)
        b = float(y_max - y_min + 2 * padding)
        c = float(z_max - z_min + 2 * padding)

        # Shift coordinates so they sit padding away from origin
        enriched_df["x"] = enriched_df["x"] - x_min + padding
        enriched_df["y"] = enriched_df["y"] - y_min + padding
        enriched_df["z"] = enriched_df["z"] - z_min + padding

        cell = {
            "pbc": True,
            "a": round(a, 4),
            "b": round(b, 4),
            "c": round(c, 4),
            "alpha": config.cell.alpha,
            "beta": config.cell.beta,
            "gamma": config.cell.gamma,
            "spacegroup": config.cell.spacegroup,
        }
        logger.info(
            f"Cell (auto, padding={padding} A): {a:.1f} x {b:.1f} x {c:.1f} "
            f"(from bounding box {x_max-x_min:.1f} x {y_max-y_min:.1f} x {z_max-z_min:.1f})"
        )

    result_structure = usm.USM(atoms=enriched_df, cell=cell)

    # --- Step 7: Validate ---
    validation_warnings = validate_enrichment(result_structure, templates, config)
    warnings.extend(validation_warnings)

    # --- Step 8: Write outputs ---
    car_path = f"{config.output}.car"
    mdf_path = f"{config.output}.mdf"

    logger.info(f"Writing CAR: {car_path}")
    usm.save_car(result_structure, car_path)

    logger.info(f"Writing MDF: {mdf_path}")
    usm.save_mdf(result_structure, mdf_path)

    # Post-write validation
    mdf_warnings = validate_mdf_output(mdf_path)
    warnings.extend(mdf_warnings)

    # --- Summary ---
    summary = {
        "total_atoms": len(enriched_df),
        "atom_types": enriched_df["atom_type"].value_counts().to_dict(),
        "molecules": mol_counter,
        "cell": cell,
        "templates_used": {k: v["n_atoms"] for k, v in templates.items()},
    }

    if warnings:
        for w in warnings:
            logger.warning(w)

    return {
        "car_file": str(Path(car_path).resolve()),
        "mdf_file": str(Path(mdf_path).resolve()),
        "summary": summary,
        "warnings": warnings,
    }


def _enrich_atom(pdb_row: pd.Series, tpl_row: pd.Series, local_index: int) -> dict:
    """Merge one PDB atom with its template match.

    Takes coordinates from PDB, everything else from the template.
    """
    enriched = {}

    # From PDB: coordinates only
    enriched["x"] = float(pdb_row["x"])
    enriched["y"] = float(pdb_row["y"])
    enriched["z"] = float(pdb_row["z"])

    # From template: name, element, and all FF data
    enriched["name"] = tpl_row["name"]
    enriched["element"] = tpl_row["element"]

    for col in FF_COLUMNS:
        if col in tpl_row.index:
            enriched[col] = tpl_row[col]

    # Mass from template element (USM may have it)
    if "mass_amu" in tpl_row.index and pd.notna(tpl_row["mass_amu"]):
        enriched["mass_amu"] = tpl_row["mass_amu"]

    # LJ parameters from template
    for lj_col in ["lj_epsilon_kcal_mol", "lj_sigma_angstrom"]:
        if lj_col in tpl_row.index and pd.notna(tpl_row[lj_col]):
            enriched[lj_col] = tpl_row[lj_col]

    return enriched
