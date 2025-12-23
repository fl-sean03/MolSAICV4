"""Build/compose functions for CAR and MDF files.

This module contains the legacy MolSAIC V2 builder functions that
produce MSI2LMP-compatible output files.
"""

from __future__ import annotations

import json as _json
import re as _re
from collections import defaultdict as _defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as _pd

from ._legacy_parsers import parse_car, parse_mdf, parse_pdb
from ._writers import write_car, write_mdf

__all__ = [
    "load_mdf_templates",
    "build_combined_mdf",
    "build_combined_car",
    "_legacy_parse_pdb",
    "_legacy_load",
    "_legacy_build_mdf",
    "_legacy_build_car",
]


def load_mdf_templates(template_dir: Path) -> Dict[str, Tuple[_pd.DataFrame, dict]]:
    """Load all MDF templates from a directory.

    Args:
        template_dir: Directory containing .mdf template files

    Returns:
        Dict mapping residue names (uppercase) to (atoms_df, meta) tuples
    """
    if not template_dir.is_dir():
        raise SystemExit(
            f"Error: template directory '{template_dir}' does not exist or is not a directory."
        )
    templates: Dict[str, Tuple[_pd.DataFrame, dict]] = {}
    for file in template_dir.iterdir():
        if file.suffix.lower() != ".mdf":
            continue
        resname = file.stem.upper()
        atoms_df, meta = parse_mdf(file)
        templates[resname] = (atoms_df, meta)
    if not templates:
        raise SystemExit(f"No .mdf template files found in {template_dir}")
    return templates


def build_combined_mdf(
    pdb_atoms: _pd.DataFrame,
    pdb_meta: dict,
    templates: Dict[str, Tuple[_pd.DataFrame, dict]],
    output_prefix: Path,
    templates_dir: Path,
    target_c: float | None = None,
    z_pad: float = 0.5,
) -> None:
    """Build a combined MDF file from PDB atoms and templates.

    This function processes PDB atoms, maps them to templates,
    and produces intermediate files for final MDF generation.

    Args:
        pdb_atoms: DataFrame of PDB atoms
        pdb_meta: Metadata from PDB parsing
        templates: Dict of template DataFrames by residue name
        output_prefix: Path prefix for output files
        templates_dir: Directory containing template CAR files
        target_c: Target c cell dimension (optional)
        z_pad: Padding for z coordinate calculation
    """
    output_dir = output_prefix.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    all_atoms_list = []
    atom_offset = 0
    counters_by_resname = _defaultdict(int)
    mdf_qualifier_counter = 0

    def get_residue_groups_by_template(atoms_df: _pd.DataFrame, templates_dict: Dict):
        i = 0
        while i < len(atoms_df):
            resname = atoms_df.iloc[i]["resName"].strip().upper()
            if resname not in templates_dict:
                raise ValueError(f"Residue '{resname}' from PDB not found in templates.")
            tpl_atoms_df, _meta = templates_dict[resname]
            num_atoms_in_template = len(tpl_atoms_df)
            end_index = i + num_atoms_in_template
            if end_index > len(atoms_df):
                raise ValueError(f"PDB ended unexpectedly while parsing residue '{resname}'.")
            group_df = atoms_df.iloc[i:end_index]
            if not (group_df["resName"].str.strip().str.upper() == resname).all():
                raise ValueError(
                    f"Inconsistent residue names found in PDB chunk for '{resname}'."
                )
            yield resname, group_df
            i = end_index

    for resname, group in get_residue_groups_by_template(pdb_atoms, templates):
        counters_by_resname[resname] += 1
        mdf_qualifier_counter += 1
        mdf_qualifier = f"MOL_{mdf_qualifier_counter}"
        group_molecule_name = f"{resname}_{counters_by_resname[resname]}"

        tpl_atoms, _ = templates[resname]
        tiled = tpl_atoms.copy()

        tpl_prefix_series = tpl_atoms["label"].str.extract(r"^(XXXX_\d+:)")[0].fillna("")
        tiled["tpl_prefix"] = tpl_prefix_series
        if "molecule" in tpl_atoms.columns:
            tiled["tpl_molecule"] = tpl_atoms["molecule"].astype(str)
        else:
            tiled["tpl_molecule"] = ""

        tiled["base_label"] = tiled["label"].str.replace(r"^[^:]+:", "", regex=True)
        tpl_prefix_clean = tiled["tpl_prefix"].astype(str).str.replace(":", "", regex=False)
        prefix_use = tpl_prefix_clean.fillna("")
        tiled["pref_label_base"] = _pd.Series(
            [f"{p}_{b}" if p else f"{b}" for p, b in zip(prefix_use, tiled["base_label"])],
            index=tiled.index,
        )
        dup_index = tiled.groupby("pref_label_base").cumcount() + 1
        dup_suffix = dup_index.apply(lambda n: "" if n == 1 else f"__{n}")
        tiled["pref_label"] = tiled["pref_label_base"].astype(str) + dup_suffix.astype(str)
        tiled["car_label"] = tiled["pref_label"]
        tiled["mdf_label"] = f"{mdf_qualifier}:" + tiled["pref_label"]

        tiled[["x", "y", "z"]] = group[["x", "y", "z"]].values
        tiled["resname"] = resname
        tiled["resid"] = group["resSeq"].iloc[0]
        tiled["segment"] = group["chainID"].iloc[0]
        tiled["molecule"] = group_molecule_name
        tiled["serial"] = range(atom_offset + 1, atom_offset + 1 + len(tiled))
        atom_offset += len(tiled)

        label_map_full = _pd.Series(
            tiled["car_label"].values, index=tpl_atoms["label"]
        ).to_dict()
        prefix_by_full = _pd.Series(tpl_prefix_series.values, index=tpl_atoms["label"]).to_dict()

        scoped_index = tiled["tpl_molecule"].astype(str) + "||" + tpl_atoms["label"].astype(str)
        label_map_scoped = _pd.Series(tiled["car_label"].values, index=scoped_index).to_dict()

        def remap_connections_for_row(conn_str: str, curr_prefix: str, curr_tpl_mol: str) -> str:
            if not isinstance(conn_str, str) or not conn_str.strip():
                return ""
            new_conns: List[str] = []
            for part in conn_str.split():
                s = str(part)

                # Preserve full operator suffix (e.g. "%0-10#1"), not just bare '%'/'#'
                idx_pct = s.find("%")
                idx_hash = s.find("#")
                idxs = [i for i in (idx_pct, idx_hash) if i != -1]
                cut = min(idxs) if idxs else -1

                if cut == -1:
                    token = s
                    operator = ""
                else:
                    token = s[:cut]
                    operator = s[cut:]

                if _re.match(r"^XXXX_\d+:", token):
                    token_full = token
                else:
                    token_full = f"{curr_prefix}{token}" if curr_prefix else token

                scope_key = f"{str(curr_tpl_mol)}||{token_full}"
                if scope_key in label_map_scoped:
                    new_conns.append(label_map_scoped[scope_key] + operator)
                    continue
                if token_full in label_map_full:
                    new_conns.append(label_map_full[token_full] + operator)

            return " ".join(new_conns)

        tiled["connections"] = [
            remap_connections_for_row(c, p, m)
            for c, p, m in zip(
                tiled["connections"], tiled["tpl_prefix"], tiled["tpl_molecule"]
            )
        ]
        all_atoms_list.append(tiled)

    if not all_atoms_list:
        raise SystemExit("Error: No atoms were processed.")

    combined_atoms = _pd.concat(all_atoms_list, ignore_index=True)
    combined_atoms["global_index"] = range(1, len(combined_atoms) + 1)

    if "atom_type" in combined_atoms.columns:
        combined_atoms["atom_type"] = combined_atoms["atom_type"].astype(str).str.strip()
        combined_atoms.loc[combined_atoms["atom_type"] == "H*", "atom_type"] = "h*"
        combined_atoms.loc[combined_atoms["atom_type"] == "O*", "atom_type"] = "o*"

    if (
        target_c is not None
        and "z" in combined_atoms.columns
        and not combined_atoms["z"].empty
    ):
        z_min_all = float(combined_atoms["z"].min())
        combined_atoms["z"] = combined_atoms["z"] - z_min_all
        z_max_all = float(combined_atoms["z"].max())
        if z_max_all > float(target_c) + 1e-6:
            print(
                f"[WARN] Combined z-span ({z_max_all:.3f} Å) exceeds target_c ({float(target_c):.3f} Å). "
                f"Coordinates will not be rescaled; ensure Packmol slab and substrate thickness fit within c."
            )

    atoms_parq = output_dir / f"{output_prefix.name}_atoms.parquet"
    atoms_csv = output_dir / f"{output_prefix.name}_atoms.csv"
    molecules_csv = output_dir / f"{output_prefix.name}_molecules.csv"
    meta_json = output_dir / f"{output_prefix.name}_meta.json"

    try:
        combined_atoms.to_parquet(atoms_parq, index=False)
    except Exception as e:
        print(
            f"[WARN] to_parquet failed ({e}); proceeding without parquet. Downstream writers will use CSV."
        )
    combined_atoms.to_csv(atoms_csv, index=False)

    (
        combined_atoms.groupby("molecule", as_index=False)
        .size()
        .rename(columns={"size": "atom_count"})
        .to_csv(molecules_csv, index=False)
    )

    header_lines = []
    box = pdb_meta.get("box")

    if not box:
        try:
            resnames = set(
                str(r).strip().upper()
                for r in pdb_atoms.get("resName", _pd.Series(dtype=str)).unique()
            )
            candidates = []
            for stem in resnames:
                if stem == "WAT" or stem == "":
                    continue
                candidate = templates_dir / f"{stem}.car"
                if candidate.exists():
                    candidates.append(candidate)
            if not candidates:
                for p in templates_dir.glob("*.car"):
                    if p.stem.strip().upper() != "WAT":
                        candidates.append(p)
            if not candidates:
                raise FileNotFoundError(f"No slab template .car found in {templates_dir}")

            slab_car_path = candidates[0]

            a = b = alpha = beta = gamma = None
            try:
                _atoms_df, slab_meta = parse_car(slab_car_path)
                cell = slab_meta.get("cell", {})
                if all(k in cell for k in ("a", "b", "alpha", "beta", "gamma")):
                    a = float(cell["a"])
                    b = float(cell["b"])
                    alpha = float(cell["alpha"])
                    beta = float(cell["beta"])
                    gamma = float(cell["gamma"])
            except Exception:
                pass

            if a is None or b is None or alpha is None or beta is None or gamma is None:
                with slab_car_path.open("r", encoding="utf-8", errors="ignore") as fh:
                    for line in fh:
                        stripped = line.strip()
                        if not stripped.upper().startswith("PBC"):
                            continue
                        nums = _re.findall(r"[-+]?\d*\.\d+|[-+]?\d+", stripped)
                        if len(nums) >= 6:
                            (
                                a_try,
                                b_try,
                                _c0,
                                alpha_try,
                                beta_try,
                                gamma_try,
                            ) = [float(x) for x in nums[:6]]
                            a = a if a is not None else a_try
                            b = b if b is not None else b_try
                            alpha = alpha if alpha is not None else alpha_try
                            beta = beta if beta is not None else beta_try
                            gamma = gamma if gamma is not None else gamma_try
                            break

            if a is None or b is None or alpha is None or beta is None or gamma is None:
                raise ValueError(
                    f"Could not parse PBC cell parameters from {slab_car_path}"
                )

            if "z" not in pdb_atoms.columns or pdb_atoms["z"].empty:
                raise ValueError(
                    "PDB atoms missing 'z' coordinates required to compute hydrated c length."
                )
            z_min = float(pdb_atoms["z"].min())
            z_max = float(pdb_atoms["z"].max())

            if target_c is not None:
                c = float(target_c)
            else:
                c = (z_max - z_min) + float(z_pad)

            box = {
                "a": float(a),
                "b": float(b),
                "c": float(c),
                "alpha": float(alpha),
                "beta": float(beta),
                "gamma": float(gamma),
            }
            pdb_meta["box"] = box
        except Exception as e:
            print(f"[WARN] Falling back without explicit PBC due to: {e}")

    if box and target_c is not None:
        try:
            box["c"] = float(target_c)
        except Exception:
            pass

    if box:
        a = float(box["a"])
        b = float(box["b"])
        c = float(box["c"])
        alpha = float(box["alpha"])
        beta = float(box["beta"])
        gamma = float(box["gamma"])
        header_lines = [
            "PBC=ON\n",
            " \n",
            " \n",
            f"PBC   {a:.4f}   {b:.4f}   {c:.4f}   {alpha:.4f}   {beta:.4f}   {gamma:.4f} (P1)\n",
        ]
        symmetry = {}
    else:
        symmetry = {}

    combined_meta = {
        "date": _pd.Timestamp.now().strftime("%Y-%m-%d"),
        "symmetry": symmetry,
        "box": box if box else {},
        "source_pdb": pdb_meta.get("source_file", "unknown"),
        "header_lines": header_lines,
        "footer_lines": ["end\n", "end\n"],
    }
    (output_dir / f"{output_prefix.name}_meta.json").write_text(
        _json.dumps(combined_meta, indent=2)
    )

    write_mdf(str(output_prefix))


def build_combined_car(
    pdb_atoms: _pd.DataFrame,
    pdb_meta: dict,
    templates: Dict[str, Tuple[_pd.DataFrame, dict]],
    output_prefix: Path,
) -> None:
    """Build a combined CAR file from intermediate data.

    Requires that build_combined_mdf has been run first to produce
    the necessary intermediate files.

    Args:
        pdb_atoms: DataFrame of PDB atoms (not directly used)
        pdb_meta: Metadata from PDB parsing (not directly used)
        templates: Dict of template DataFrames by residue name (not directly used)
        output_prefix: Path prefix for output files
    """
    input_dir = output_prefix.parent
    atoms_parq = input_dir / f"{output_prefix.name}_atoms.parquet"
    atoms_csv = input_dir / f"{output_prefix.name}_atoms.csv"
    meta_json = input_dir / f"{output_prefix.name}_meta.json"
    if (not meta_json.exists()) or (not atoms_parq.exists() and not atoms_csv.exists()):
        raise SystemExit("Error: expected intermediate files missing prior to CAR build.")
    write_car(output_prefix)


# Convenience wrappers matching names used in pm2mdfcar.build()
def _legacy_parse_pdb(p: Path):
    """Legacy wrapper for parse_pdb."""
    return parse_pdb(p)


def _legacy_load(p: Path):
    """Legacy wrapper for load_mdf_templates."""
    return load_mdf_templates(p)


def _legacy_build_mdf(
    a: _pd.DataFrame,
    m: dict,
    t,
    out: Path,
    tpl_dir: Path,
    target_c: float | None = None,
):
    """Legacy wrapper for build_combined_mdf."""
    return build_combined_mdf(a, m, t, out, tpl_dir, target_c=target_c)


def _legacy_build_car(a: _pd.DataFrame, m: dict, t, out: Path):
    """Legacy wrapper for build_combined_car."""
    return build_combined_car(a, m, t, out)
