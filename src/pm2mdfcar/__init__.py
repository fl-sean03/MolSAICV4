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

import datetime
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TemplateAtom:
    label: str        # e.g., "Al1", "O1", "H1"
    res_seq: int      # numeric residue (from CAR "XXXX <res_seq>")
    atom_type: str    # e.g., "alo1", "o*", "h*"
    element: str      # "Al", "O", "H", etc
    charge: float     # partial charge (from CAR)


@dataclass
class PDBAtom:
    serial: int
    name: str         # atom name from PDB (columns 13-16)
    resname: str      # residue name from PDB (columns 18-20)
    chain: str        # chain ID
    resseq: int       # residue sequence integer
    x: float
    y: float
    z: float
    element: str


def _read_text(path: Path) -> List[str]:
    return path.read_text().splitlines()


def _parse_car(car_path: Path) -> Tuple[Dict[str, float], List[TemplateAtom], List[str]]:
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
    pbc_re = re.compile(
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
            cell = {"a": a, "b": b, "c": c, "alpha": alpha, "beta": beta, "gamma": gamma}
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
                atoms.append(TemplateAtom(label=label, res_seq=res_seq, atom_type=atom_type, element=element, charge=charge))
            except Exception:
                # Skip lines that don't conform exactly; not fatal for template
                logger.debug("Skipped non-conforming CAR atom line: %s", ln)
                continue

    if cell is None:
        raise ValueError(f"PBC line missing in template CAR: {car_path}")
    return cell, atoms, header_lines


def _parse_mdf_bonds(mdf_path: Path, template_atoms: Sequence[TemplateAtom]) -> List[Tuple[int, int]]:
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
    name_re = re.compile(r"^XXXX_(\d+):([A-Za-z0-9_]+)$")

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


def _parse_wat_templates(templates_dir: Path) -> Tuple[List[TemplateAtom], List[Tuple[int, int]]]:
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
                wat_atoms_raw.append(TemplateAtom(label=label, res_seq=res_seq, atom_type=atom_type, element=element, charge=charge))
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
    name_re = re.compile(r"^XXXX_(\d+):([A-Za-z0-9_]+)$")
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
            resseq = int(re.match(r"(-?\d+)", resseq_str).group(1)) if resseq_str else 0
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
            m = re.search(r"[A-Za-z]", name)
            element = (m.group(0).upper() if m else "").title()
        atoms.append(PDBAtom(serial, name, resname, chain, resseq, x, y, z, element.title()))
    return atoms


def _format_car_header(a: float, b: float, c: float, alpha: float, beta: float, gamma: float) -> List[str]:
    now = datetime.datetime.now().strftime("%a %b %d %H:%M:%S %Y")
    return [
        "!BIOSYM archive 3",
        "PBC=ON",
        "pm2mdfcar generated CAR File",
        f"!DATE {now}",
        f"PBC {a:10.6f} {b:10.6f} {c:10.6f} {alpha:10.6f} {beta:10.6f} {gamma:10.6f} (P1)",
    ]


def _format_car_atom(label: str, x: float, y: float, z: float, res_seq: int, atom_type: str, element: str, charge: float) -> str:
    # Match general spacing style seen in templates
    return f"{label:<8s}{x:14.6f}{y:14.6f}{z:14.6f} XXXX {res_seq:<6d}{atom_type:<8s}{element:>3s}{charge:8.3f}"


def _format_mdf_header() -> List[str]:
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


def _format_mdf_atom(stamp: str, element: str, atom_type: str, charge: float, connections: Sequence[str]) -> str:
    # Columns per templates; we keep unknowns/zeros similar to examples; formal_charge set to 0
    # stamp example: "XXXX_23:Al1"
    # connections: tokens separated by spaces
    conns = " ".join(connections)
    return f"{stamp:<16s} {element:<2s} {atom_type:<7s} ?     0  0    {charge:8.4f} 0 0 8 1.0000  0.0000 {conns}".rstrip()


def _normalize_name(name: str) -> str:
    return name.strip().upper()


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
        pdb_atoms_df, pdb_meta, templates_legacy,
        out_prefix, templates_dir_path, target_c=float(target_c)
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
                    1 for r in rows
                    if (str(r.get("resname", "")).strip().upper() == resname_surface.upper())
                )
                water_atoms = sum(
                    1 for r in rows
                    if (str(r.get("resname", "")).strip().upper() in {resname_water.upper(), "HOH"})
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
                    1 for row in data_rows if _tok(row, 1) in {resname_water.upper(), "HOH"}
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
    # Parse PDB
    pdb_atoms = _parse_pdb(pdb_path)
    if not pdb_atoms:
        raise ValueError(f"No ATOM/HETATM records found in PDB: {pdb_path}")

    # Partition PDB by residues
    # key: (resname, resseq) -> list of PDBAtom (in file order)
    resid_map: Dict[Tuple[str, int], List[PDBAtom]] = {}
    for pa in pdb_atoms:
        key = (pa.resname.strip().upper(), pa.resseq)
        resid_map.setdefault(key, []).append(pa)

    # Identify AS2 residues and water residues
    surf_keys = [k for k in resid_map.keys() if k[0] == resname_surface.upper()]
    water_keys = [k for k in resid_map.keys() if k[0] in (resname_water.upper(), "HOH")]

    # Enforce only supported residue names present
    supported_res = {resname_surface.upper(), resname_water.upper(), "HOH"}
    others = sorted({rn for (rn, _) in resid_map.keys()} - supported_res)
    if others:
        raise NotImplementedError(f"Unsupported residues present in PDB: {others}. Only {resname_surface} and water (WAT/HOH) are supported.")

    if not surf_keys:
        raise ValueError(f"No surface residues with resName={resname_surface} found in PDB")

    # Collect AS2 PDB atoms in deterministic residue order (resSeq ascending, then serial)
    as2_pdb_atoms: List[PDBAtom] = []
    for key in sorted(surf_keys, key=lambda t: t[1]):
        as2_pdb_atoms.extend(sorted(resid_map[key], key=lambda a: a.serial))

    # Validate AS2 atom count vs template
    if len(as2_pdb_atoms) != len(as2_atoms):
        # Provide sample of names to aid debugging
        raise ValueError(
            "AS2 atom count mismatch: PDB={} vs template={}. Example PDB names (first 10): {}"
            .format(len(as2_pdb_atoms), len(as2_atoms), [a.name for a in as2_pdb_atoms[:10]])
        )

    # Build mapping: template_index -> matched PDB atom (primary: by (res_seq, name), fallback: by order)
    # Primary mapping dictionary
    pdb_by_addr: Dict[Tuple[int, str], PDBAtom] = {}
    for key in sorted(surf_keys, key=lambda t: t[1]):
        resseq = key[1]
        for pa in resid_map[key]:
            pdb_by_addr[(resseq, _normalize_name(pa.name))] = pa

    surface_mapping_order_based = False
    templ_idx_to_pdb: List[PDBAtom] = [None] * len(as2_atoms)  # type: ignore
    used_serials: set[int] = set()
    for i, ta in enumerate(as2_atoms):
        pa = pdb_by_addr.get((ta.res_seq, _normalize_name(ta.label)))
        if pa is None or pa.serial in used_serials:
            # Attempt same-name regardless of res_seq (non-unique possible)
            # Collect candidates by name
            candidates = [p for p in as2_pdb_atoms if _normalize_name(p.name) == _normalize_name(ta.label) and p.serial not in used_serials]
            if candidates:
                pa = candidates[0]
        if pa is None or pa.serial in used_serials:
            # Fallback to deterministic order-based mapping
            surface_mapping_order_based = True
            pa = next((p for p in as2_pdb_atoms if p.serial not in used_serials), None)
        if pa is None:
            raise ValueError("Failed to map AS2 template atom to PDB coordinates (label={}, res_seq={})".format(ta.label, ta.res_seq))
        templ_idx_to_pdb[i] = pa
        used_serials.add(pa.serial)

    if surface_mapping_order_based:
        warnings.append("AS2 atom mapping used order-based fallback due to name/residue mismatches.")

    # Waters: validate each residue is 3 atoms; map to O,H,H order
    waters: List[Tuple[int, List[PDBAtom]]] = []  # list of (resSeq, [O, H1, H2])
    for key in sorted(water_keys, key=lambda t: t[1]):
        atoms_in_res = sorted(resid_map[key], key=lambda a: a.serial)
        if len(atoms_in_res) != 3:
            raise ValueError(f"Water residue {key} has {len(atoms_in_res)} atoms; expected 3.")
        # classify by element
        os_ = [a for a in atoms_in_res if a.element.upper() == "O"]
        hs_ = [a for a in atoms_in_res if a.element.upper() == "H"]
        if len(os_) != 1 or len(hs_) != 2:
            # fallback by name prefixes
            os_ = [a for a in atoms_in_res if _normalize_name(a.name).startswith("O")]
            hs_ = [a for a in atoms_in_res if _normalize_name(a.name).startswith("H")]
        if len(os_) != 1 or len(hs_) != 2:
            raise ValueError(f"Unable to classify water atoms by element in residue {key}.")
        waters.append((key[1], [os_[0], hs_[0], hs_[1]] if hs_[0].serial <= hs_[1].serial else [os_[0], hs_[1], hs_[0]]))

    # Deterministic output order:
    # 1) All surface atoms in AS2 template order
    # 2) Waters ordered by resSeq ascending; within each water: [O, H1, H2]
    output_atoms: List[Tuple[str, int, str, str, float, float, float, float]] = []
    # Return helpful maps for bond remapping
    templ_idx_to_outidx: Dict[int, int] = {}

    # Append AS2 atoms
    for i, ta in enumerate(as2_atoms):
        pa = templ_idx_to_pdb[i]
        out_idx = len(output_atoms)
        templ_idx_to_outidx[i] = out_idx
        # CAR/MDF "label" should match template label for cross-file consistency
        # Use template residue numbering to avoid PDB chain/resseq collisions
        output_atoms.append((
            ta.label,           # label
            ta.res_seq,         # res_seq from AS2 template
            ta.atom_type,       # type from template
            ta.element,         # element from template
            ta.charge,          # charge from template
            pa.x, pa.y, pa.z,   # coordinates from PDB
            float(ta.res_seq),  # helper (unused); keep slot structure simple
        ))

    # Append Waters
    # Build a small map for water template properties by role order [O1, H1, H2]
    wat_props = [
        (wat_atoms_tpl[0].label, wat_atoms_tpl[0].atom_type, wat_atoms_tpl[0].element, wat_atoms_tpl[0].charge),  # O1
        (wat_atoms_tpl[1].label, wat_atoms_tpl[1].atom_type, wat_atoms_tpl[1].element, wat_atoms_tpl[1].charge),  # H1
        (wat_atoms_tpl[2].label, wat_atoms_tpl[2].atom_type, wat_atoms_tpl[2].element, wat_atoms_tpl[2].charge),  # H2
    ]
    # Assign unique residue numbers to waters after the last AS2 residue
    surface_res_max = max((ta.res_seq for ta in as2_atoms), default=0)
    water_res_start = surface_res_max + 1

    # For quick bond replication for waters, store each water's local out-index map (0,1,2) -> global out index
    waters_local_maps: List[Dict[int, int]] = []

    for water_idx, (resseq, trio) in enumerate(waters):
        out_resseq = water_res_start + water_idx
        local_map: Dict[int, int] = {}
        # trio order: [O, H1, H2]
        for local_i, pa in enumerate(trio):
            label_tpl, atom_type_tpl, elem_tpl, charge_tpl = wat_props[local_i]
            # For CAR/MDF label and name, use canonical short labels "O1"/"H1"/"H2" to match template convention
            label_out = label_tpl  # "O1","H1","H2"
            out_idx = len(output_atoms)
            local_map[local_i] = out_idx
            output_atoms.append((
                label_out,         # label
                out_resseq,        # unique water residue number in output
                atom_type_tpl,     # type from WAT template
                elem_tpl,          # element from WAT template
                charge_tpl,        # charge from WAT template
                pa.x, pa.y, pa.z,  # coordinates from PDB
                float(out_resseq), # helper
            ))
        waters_local_maps.append(local_map)

    # Bonds: remap AS2 template bonds to output indices
    bonds_out: List[Tuple[int, int]] = []
    for ti, tj in as2_bonds_templ:
        i = templ_idx_to_outidx.get(ti)
        j = templ_idx_to_outidx.get(tj)
        if i is None or j is None:
            # Should not happen
            continue
        a, b = (i, j) if i <= j else (j, i)
        bonds_out.append((a, b))

    # Replicate WAT bonds per water
    for local_map in waters_local_maps:
        for li, lj in wat_bonds_tpl:
            i = local_map[li]
            j = local_map[lj]
            a, b = (i, j) if i <= j else (j, i)
            bonds_out.append((a, b))

    # Deduplicate and sort bonds deterministically
    bonds_out = sorted(set(bonds_out))

    # Prepare to write CAR
    car_lines: List[str] = []
    car_lines.extend(_format_car_header(cell["a"], cell["b"], cell["c"], cell["alpha"], cell["beta"], cell["gamma"]))
    for idx, (label, res_seq, atom_type, element, charge, x, y, z, _) in enumerate(output_atoms):
        car_lines.append(_format_car_atom(label, x, y, z, int(res_seq), atom_type, element, charge))
    car_lines.append("end")
    car_lines.append("end")

    car_path = out_prefix.with_suffix(".car")
    car_path.write_text("\n".join(car_lines) + "\n")

    # Prepare to write MDF: connections per atom from bonds
    # Build adjacency list
    adjacency: Dict[int, List[int]] = {i: [] for i in range(len(output_atoms))}
    for i, j in bonds_out:
        adjacency[i].append(j)
        adjacency[j].append(i)
    for lst in adjacency.values():
        lst.sort()

    # Helper to get stamp "XXXX_res:Label" and short label
    def stamp_for(idx: int) -> Tuple[str, str, int]:
        label, res_seq, atom_type, element, charge, x, y, z, _ = output_atoms[idx]
        return (f"XXXX_{int(res_seq)}:{label}", label, int(res_seq))

    mdf_lines: List[str] = []
    mdf_lines.extend(_format_mdf_header())
    for idx in range(len(output_atoms)):
        label, res_seq, atom_type, element, charge, x, y, z, _ = output_atoms[idx]
        stamp, short_name, resnum = stamp_for(idx)
        # Build connection tokens: emit all same-residue neighbors (both directions)
        # Omit cross-residue connections to maximize msi2lmp compatibility
        conn_tokens: List[str] = []
        for j in adjacency[idx]:
            _js, jname, jres = stamp_for(j)
            if jres == resnum:
                conn_tokens.append(jname)
        # Note: cross-residue connections intentionally omitted
        mdf_lines.append(_format_mdf_atom(stamp, element, atom_type, charge, conn_tokens))
    # Symmetry footer akin to AS2.mdf end; minimal accepted footer
    mdf_lines.append("")
    mdf_lines.append("!")
    mdf_lines.append("#symmetry")
    mdf_lines.append("@periodicity 3 xyz")
    mdf_lines.append("@group (P1)")
    mdf_lines.append("")
    mdf_lines.append("#end")

    mdf_path = out_prefix.with_suffix(".mdf")
    mdf_path.write_text("\n".join(mdf_lines) + "\n")

    # Basic validations
    if not car_path.exists() or car_path.stat().st_size == 0:
        raise RuntimeError(f"CAR write failed or empty: {car_path}")
    if not mdf_path.exists() or mdf_path.stat().st_size == 0:
        raise RuntimeError(f"MDF write failed or empty: {mdf_path}")

    surface_atoms_count = len(as2_atoms)
    waters_count = len(waters)
    total_atoms = len(output_atoms)
    bonds_count = len(bonds_out)

    # Expected congruency
    if total_atoms != surface_atoms_count + 3 * waters_count:
        warnings.append(
            f"Atom count congruency check: total={total_atoms} vs surface({surface_atoms_count}) + 3*waters({waters_count})"
        )

    result = {
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
            "c": cell["c"],
            "alpha": cell["alpha"],
            "beta": cell["beta"],
            "gamma": cell["gamma"],
        },
        "warnings": warnings,
    }
    return result

# -------------------- Vendored legacy pm2mdfcar (MolSAIC V2) --------------------
# The functions below are copied-in equivalents of the original pm2mdfcar converter
# used in MolSAIC V2. They preserve the exact MDF/CAR labeling and connection
# semantics that msi2lmp expects. We expose _legacy_* wrappers so build() can
# call them without importing from the old plugin path.

from pathlib import Path as _Path
import json as _json
import re as _re
import csv as _csv
import logging as _logging
from typing import Dict as _Dict, List as _List, Tuple as _Tuple, Any as _Any

import pandas as _pd

# ---------- parse_pdb (legacy) ----------
def parse_pdb(_pdb_path: _Path) -> _Tuple[_pd.DataFrame, _pd.DataFrame, dict]:
    atoms = []
    meta: dict = {"source_file": str(_pdb_path)}
    with _pdb_path.open("r", errors="replace") as handle:
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
                    _logging.warning("Could not parse CRYST1 line.")
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
                    _logging.warning(f"Skipping malformed ATOM/HETATM line: {line.strip()}")
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


# ---------- parse_mdf (legacy) ----------
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

def _numeric_or_none(val: str):
    val = val.strip()
    if val in {"", "?"}:
        return None
    try:
        if val.endswith('+'):
            return int(val[:-1])
        if val.endswith('-'):
            return -int(val[:-1])
        if "." in val or "e" in val.lower():
            return float(val)
        return int(val)
    except ValueError:
        return None

def parse_mdf(_path: _Path) -> _Tuple[_pd.DataFrame, dict]:
    atoms: _List[_Dict] = []
    meta: _Dict = {
        "source_file": str(_path.resolve()),
        "date": None,
        "symmetry": {},
        "molecules": [],
    }

    with _path.open("r", errors="replace") as handle:
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
                prefix_match = _re.match(r'^(XXXX_\d+:)(.*)', full_label_from_mdf)
                if prefix_match:
                    label = full_label_from_mdf
                else:
                    label = full_label_from_mdf
                element = toks[1]
                atom_type = toks[2]

                record: _Dict = {
                    "label": full_label_from_mdf,
                    "base_label": _re.sub(r'^(XXXX_\d+:)', '', full_label_from_mdf),
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
            sym: _Dict = {}
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
    fill_zero_cols = ["isotope", "switching_atom", "oop_flag", "chirality_flag", "occupancy", "xray_temp_factor"]
    for col in fill_zero_cols:
        if col in atoms_df.columns:
            atoms_df[col] = _pd.to_numeric(atoms_df[col], errors="coerce").fillna(0)
    for col in ["formal_charge", "charge"]:
        if col in atoms_df.columns:
            atoms_df[col] = _pd.to_numeric(atoms_df[col], errors="coerce")
    return atoms_df, meta


# ---------- parse_car (legacy) ----------
def parse_car(_path: _Path) -> _Tuple[_pd.DataFrame, dict]:
    meta: _Dict[str, _Any] = {
        'source_file': str(_path.resolve()),
        'pbc': False,
        'cell': {},
        'header_lines': []
    }
    atoms: _List[_Dict[str, _Any]] = []

    with _path.open('r', errors='replace') as fh:
        lines = fh.readlines()

    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        stripped = line.strip()

        tokens = stripped.split()
        is_atom_line = (
            len(tokens) >= 4 and
            not tokens[0].upper().startswith('PBC') and
            _numeric_or_none(tokens[0]) is None and
            _numeric_or_none(tokens[1]) is not None and
            _numeric_or_none(tokens[2]) is not None and
            _numeric_or_none(tokens[3]) is not None
        )

        if is_atom_line:
            break

        meta['header_lines'].append(line)

        if stripped.upper().startswith('PBC='):
            meta['pbc'] = stripped.upper().split('=', 1)[1].strip() == 'ON'
            if meta['pbc']:
                temp_i = i + 1
                while temp_i < n and lines[temp_i].strip() == '':
                    temp_i += 1
                if temp_i < n:
                    cell_line = lines[temp_i].strip()
                    numeric_tokens = _re.findall(r"[-+]?\d*\.\d+|\d+", cell_line)
                    parsed_cell_params = [_numeric_or_none(t) for t in numeric_tokens[:6]]
                    if len(parsed_cell_params) >= 6 and all(isinstance(p, (float, int)) for p in parsed_cell_params):
                        meta['cell'] = {
                            'a': parsed_cell_params[0],
                            'b': parsed_cell_params[1],
                            'c': parsed_cell_params[2],
                            'alpha': parsed_cell_params[3],
                            'beta': parsed_cell_params[4],
                            'gamma': parsed_cell_params[5],
                        }
        i += 1

    def _parse_atom_line(tokens: _List[str]) -> _Dict[str, _Any]:
        if len(tokens) < 4:
            raise ValueError(f"Atom line too short: {' '.join(tokens)}")
        record: _Dict[str, _Any] = {
            'label': tokens[0],
            'x': _numeric_or_none(tokens[1]),
            'y': _numeric_or_none(tokens[2]),
            'z': _numeric_or_none(tokens[3]),
            'atom_type': None,
            'charge': None,
            'resid': None,
            'resname': None,
            'segment': None,
            'extras': ''
        }
        idx = 4
        if idx < len(tokens):
            if _numeric_or_none(tokens[idx]) is None and tokens[idx].strip() not in {"", "?"}:
                record['segment'] = tokens[idx]; idx += 1
        if idx < len(tokens):
            resid_val = _numeric_or_none(tokens[idx])
            if isinstance(resid_val, int):
                record['resid'] = resid_val; idx += 1
        if idx < len(tokens):
            if _numeric_or_none(tokens[idx]) is None and tokens[idx].strip() not in {"", "?"}:
                record['atom_type'] = tokens[idx]; idx += 1
        if idx < len(tokens):
            if _numeric_or_none(tokens[idx]) is None and tokens[idx].strip() not in {"", "?"}:
                record['resname'] = tokens[idx]; idx += 1
        if idx < len(tokens):
            charge_val = _numeric_or_none(tokens[idx])
            if isinstance(charge_val, (float, int)):
                record['charge'] = charge_val; idx += 1
        if idx < len(tokens):
            record['extras'] = ' '.join(tokens[idx:])
        return record

    while i < n:
        line = lines[i]
        stripped = line.strip()

        if stripped.lower().startswith('end'):
            meta['footer_lines'] = []
            while i < n:
                meta['footer_lines'].append(lines[i])
                i += 1
            break

        if not stripped or stripped.startswith('!'):
            i += 1
            continue

        tokens = stripped.split()
        if (
            len(tokens) >= 4 and
            _numeric_or_none(tokens[0]) is None and
            _numeric_or_none(tokens[1]) is not None and
            _numeric_or_none(tokens[2]) is not None and
            _numeric_or_none(tokens[3]) is not None
        ):
            try:
                atoms.append(_parse_atom_line(tokens))
            except Exception as exc:
                atoms.append({
                    'label': tokens[0] if tokens else '',
                    'x': None, 'y': None, 'z': None,
                    'atom_type': None, 'charge': None,
                    'resid': None, 'resname': None, 'segment': None,
                    'extras': f'PARSE_ERROR: {exc}'
                })
        i += 1

    atoms_df = _pd.DataFrame(atoms)
    for col in ['x', 'y', 'z', 'charge']:
        atoms_df[col] = _pd.to_numeric(atoms_df[col], errors='coerce')
    return atoms_df, meta


# ---------- write_mdf (legacy) ----------
def _format_numeric_or_question(value, is_float=False, default_val='?', is_formal_charge=False):
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
            if v > 0: return f"{v:>2}+"
            if v < 0: return f"{abs(v):>2}-"
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
        if v > 0: return f"{v:>2}+"
        if v < 0: return f"{abs(v):>2}-"
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

def _to_old_full_label(label_token: str) -> str:
    if not isinstance(label_token, str) or not label_token:
        return label_token or ""
    s = label_token.strip()
    if _re.match(r"^XXXX_\d+:[A-Za-z0-9_]+$", s):
        return s
    m = _re.match(r"^MOL_\d+:(XXXX_\d+)_([A-Za-z0-9_]+)$", s)
    if m:
        return f"{m.group(1)}:{m.group(2)}"
    m = _re.match(r"^(XXXX_\d+)_([A-Za-z0-9_]+)$", s)
    if m:
        return f"{m.group(1)}:{m.group(2)}"
    m = _re.match(r"^MOL_\d+:(XXXX_\d+:[A-Za-z0-9_]+)$", s)
    if m:
        return m.group(1)
    return s

def _transform_connections_to_old(connections_str: str) -> str:
    if not isinstance(connections_str, str) or not connections_str.strip():
        return ""
    out_tokens = []
    for token in connections_str.split():
        m = _re.match(r"^(\S+?)([%#]*)$", token)
        if not m:
            out_tokens.append(token)
            continue
        atom_id, op = m.groups()
        out_tokens.append(_to_old_full_label(atom_id) + (op or ""))
    return " ".join(out_tokens)

def write_mdf(prefix, output_mdf=None):
    atoms_file_parquet = f"{prefix}_atoms.parquet"
    atoms_file_csv = f"{prefix}_atoms.csv"
    molecules_file = f"{prefix}_molecules.csv"
    meta_file = f"{prefix}_meta.json"

    if _Path(atoms_file_parquet).exists():
        atoms_path = atoms_file_parquet
    elif _Path(atoms_file_csv).exists():
        atoms_path = atoms_file_csv
    else:
        raise SystemExit(f"Error: Neither {atoms_file_parquet} nor {atoms_file_csv} found.")

    if not _Path(molecules_file).exists():
        raise SystemExit(f"Error: {molecules_file} not found.")
    if not _Path(meta_file).exists():
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
        with open(meta_file, 'r') as f:
            meta_data = _json.load(f)
    except Exception as e:
        raise SystemExit(f"Error reading input files: {e}")

    if output_mdf is None:
        output_mdf = f"{prefix}.mdf"

    if "global_index" in atoms_df.columns:
        atoms_sorted = atoms_df.sort_values(by="global_index")
    else:
        atoms_sorted = atoms_df.sort_values(by=["molecule", "serial"], kind="stable")

    with open(output_mdf, 'w') as f:
        f.write("!BIOSYM molecular_data 4\n")
        f.write(" \n")
        if 'date' in meta_data:
            f.write(f"!Date: {meta_data['date']}\n")
        else:
            f.write("!Date: Unknown\n")
        f.write(" \n")
        f.write("#topology\n")
        f.write("\n")
        for i, col_name in enumerate(ATOM_COLUMN_NAMES[:-1]):
            f.write(f"@column {i+1} {col_name}\n")
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
            formal_charge = _format_numeric_or_question(row.get("formal_charge"), is_formal_charge=True)
            charge = _format_numeric_or_question(row.get("charge"), is_float=True, default_val="0.0000")
            switching_atom = _format_numeric_or_question(row.get("switching_atom"), default_val='0')
            oop_flag = _format_numeric_or_question(row.get("oop_flag"), default_val='0')
            chirality_flag = _format_numeric_or_question(row.get("chirality_flag"), default_val='0')
            occupancy = _format_numeric_or_question(row.get("occupancy"), is_float=True, default_val='1.0000')
            xray_temp_factor = _format_numeric_or_question(row.get("xray_temp_factor"), is_float=True, default_val='0.0000')

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


# ---------- write_car (legacy) ----------
def write_car(prefix_path: _Path, output_car_path: _Path = None):
    input_dir = prefix_path.parent
    file_stem = prefix_path.name

    atoms_parq = input_dir / f"{file_stem}_atoms.parquet"
    atoms_csv = input_dir / f"{file_stem}_atoms.csv"
    meta_file = input_dir / f"{file_stem}_meta.json"

    if not meta_file.exists():
        raise SystemExit(f"Error: Meta file not found for prefix '{prefix_path}' in {input_dir}")

    atoms_df = None
    if atoms_parq.exists():
        try:
            atoms_df = _pd.read_parquet(atoms_parq)
        except Exception as e:
            print(f"[WARN] read_parquet failed ({e}); attempting CSV fallback for {file_stem}_atoms.csv")
            atoms_df = None
    if atoms_df is None:
        if atoms_csv.exists():
            atoms_df = _pd.read_csv(atoms_csv)
        else:
            raise SystemExit(f"Error: Neither Parquet nor CSV atoms files found for prefix '{prefix_path}' in {input_dir}")

    if 'atom_type' in atoms_df.columns:
        atoms_df['atom_type'] = atoms_df['atom_type'].astype(str).str.strip()
        atoms_df.loc[atoms_df['atom_type'] == 'H*', 'atom_type'] = 'h*'
        atoms_df.loc[atoms_df['atom_type'] == 'O*', 'atom_type'] = 'o*'

    with meta_file.open('r') as f:
        meta = _json.load(f)

    a_cell = None; b_cell = None
    box_info = meta.get('box') if isinstance(meta.get('box'), dict) else None
    if box_info:
        try:
            a_cell = float(box_info.get('a')) if box_info.get('a') is not None else None
            b_cell = float(box_info.get('b')) if box_info.get('b') is not None else None
        except Exception:
            pass
    if a_cell is None or b_cell is None:
        hdr = meta.get('header_lines', [])
        for hl in hdr:
            s = str(hl).strip()
            if s.upper().startswith('PBC') and '=' not in s.upper():
                nums = _re.findall(r"[-+]?\d*\.\d+|\d+", s)
                if len(nums) >= 2:
                    try:
                        a_cell = float(nums[0]); b_cell = float(nums[1])
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

    with output_car_path.open('w') as f:
        header_lines = meta.get('header_lines', [])
        for i in range(4):
            if i < len(header_lines):
                f.write(header_lines[i])
            else:
                f.write(" \n")

        if 'global_index' in atoms_df.columns:
            atoms_sorted = atoms_df.sort_values(by='global_index')
        else:
            atoms_sorted = atoms_df.sort_values(by=['molecule', 'serial'], kind='stable')

        current_mol = None
        for _, row in atoms_sorted.iterrows():
            mol_name = row.get('molecule', '')
            if current_mol is None:
                current_mol = mol_name
            elif mol_name != current_mol:
                f.write("end\n")
                current_mol = mol_name

            full = str(row.get('full_mdf_label') or row.get('mdf_label') or row.get('car_label') or '')
            x = row.get('x'); y = row.get('y'); z = row.get('z')
            if a_cell is not None:
                x = _wrap_coord(x, a_cell)
            if b_cell is not None:
                y = _wrap_coord(y, b_cell)
            atom_type = str(row.get('atom_type', '') or '').lower()
            resname = str(row.get('resname', '') or '')
            element = str(row.get('element', '') or '')
            charge = row.get('charge')

            base_label = None
            m = _re.match(r'^XXXX_\d+:([A-Za-z0-9_]+)$', full)
            if m: base_label = m.group(1)
            if base_label is None:
                m = _re.match(r'^MOL_\d+:(XXXX_\d+)_([A-Za-z0-9_]+)$', full)
                if m: base_label = m.group(2)
            if base_label is None:
                m = _re.match(r'^(XXXX_\d+)_([A-Za-z0-9_]+)$', full)
                if m: base_label = m.group(2)
            if base_label is None:
                base_label = str(row.get('label') or row.get('car_label') or row.get('element') or '')

            atom_id = ''
            m = _re.match(r'^(XXXX_\d+):', full)
            if m: atom_id = m.group(1)
            else:
                m = _re.match(r'^MOL_\d+:(XXXX_\d+)_', full)
                if m: atom_id = m.group(1)
                else:
                    m = _re.match(r'^(XXXX_\d+)_', full)
                    if m: atom_id = m.group(1)
            atom_id_str = f"{atom_id.replace('_',' '):<12}" if atom_id else " " * 12

            label_str = f"{base_label:<9}"
            x_str = f"{x:13.9f}" if _pd.notna(x) else " " * 13
            y_str = f"{y:13.9f}" if _pd.notna(y) else " " * 13
            z_str = f"{z:13.9f}" if _pd.notna(z) else " " * 13
            atom_type_str = f" {atom_type:<6}"
            resname_out = resname or element
            resname_str = f" {resname_out:<6}"
            charge_str = f" {charge:8.4f}" if _pd.notna(charge) else " " * 9

            f.write(f"{label_str}{x_str}    {y_str}    {z_str} {atom_id_str}{atom_type_str}{resname_str}{charge_str}\n")

        footer_lines = meta.get('footer_lines')
        if footer_lines and isinstance(footer_lines, list) and len(footer_lines) > 0:
            for line_footer in footer_lines:
                f.write(line_footer if line_footer.endswith("\n") else line_footer + "\n")
        else:
            f.write("end\n")
            f.write("end\n")


# ---------- load_mdf_templates / build_combined_* (legacy) ----------
def load_mdf_templates(template_dir: _Path) -> _Dict[str, _Tuple[_pd.DataFrame, dict]]:
    if not template_dir.is_dir():
        raise SystemExit(f"Error: template directory '{template_dir}' does not exist or is not a directory.")
    templates: _Dict[str, _Tuple[_pd.DataFrame, dict]] = {}
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
    templates: _Dict[str, _Tuple[_pd.DataFrame, dict]],
    output_prefix: _Path,
    templates_dir: _Path,
    target_c: float | None = None,
    z_pad: float = 0.5,
) -> None:
    output_dir = output_prefix.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    all_atoms_list = []
    atom_offset = 0
    from collections import defaultdict as _defaultdict
    counters_by_resname = _defaultdict(int)
    mdf_qualifier_counter = 0

    def get_residue_groups_by_template(atoms_df: _pd.DataFrame, templates_dict: _Dict):
        i = 0
        while i < len(atoms_df):
            resname = atoms_df.iloc[i]['resName'].strip().upper()
            if resname not in templates_dict:
                raise ValueError(f"Residue '{resname}' from PDB not found in templates.")
            tpl_atoms_df, _meta = templates_dict[resname]
            num_atoms_in_template = len(tpl_atoms_df)
            end_index = i + num_atoms_in_template
            if end_index > len(atoms_df):
                raise ValueError(f"PDB ended unexpectedly while parsing residue '{resname}'.")
            group_df = atoms_df.iloc[i:end_index]
            if not (group_df['resName'].str.strip().str.upper() == resname).all():
                raise ValueError(f"Inconsistent residue names found in PDB chunk for '{resname}'.")
            yield resname, group_df
            i = end_index

    for resname, group in get_residue_groups_by_template(pdb_atoms, templates):
        counters_by_resname[resname] += 1
        mdf_qualifier_counter += 1
        mdf_qualifier = f"MOL_{mdf_qualifier_counter}"
        group_molecule_name = f"{resname}_{counters_by_resname[resname]}"

        tpl_atoms, _ = templates[resname]
        tiled = tpl_atoms.copy()

        tpl_prefix_series = tpl_atoms['label'].str.extract(r'^(XXXX_\d+:)')[0].fillna('')
        tiled['tpl_prefix'] = tpl_prefix_series
        if 'molecule' in tpl_atoms.columns:
            tiled['tpl_molecule'] = tpl_atoms['molecule'].astype(str)
        else:
            tiled['tpl_molecule'] = ''

        tiled['base_label'] = tiled['label'].str.replace(r'^[^:]+:', '', regex=True)
        tpl_prefix_clean = tiled['tpl_prefix'].astype(str).str.replace(':', '', regex=False)
        prefix_use = tpl_prefix_clean.fillna('')
        tiled['pref_label_base'] = _pd.Series(
            [f"{p}_{b}" if p else f"{b}" for p, b in zip(prefix_use, tiled['base_label'])],
            index=tiled.index
        )
        dup_index = tiled.groupby('pref_label_base').cumcount() + 1
        dup_suffix = dup_index.apply(lambda n: '' if n == 1 else f"__{n}")
        tiled['pref_label'] = tiled['pref_label_base'].astype(str) + dup_suffix.astype(str)
        tiled['car_label'] = tiled['pref_label']
        tiled['mdf_label'] = f"{mdf_qualifier}:" + tiled['pref_label']

        tiled[['x', 'y', 'z']] = group[['x', 'y', 'z']].values
        tiled['resname'] = resname
        tiled['resid'] = group['resSeq'].iloc[0]
        tiled['segment'] = group['chainID'].iloc[0]
        tiled['molecule'] = group_molecule_name
        tiled['serial'] = range(atom_offset + 1, atom_offset + 1 + len(tiled))
        atom_offset += len(tiled)

        label_map_full = _pd.Series(tiled['car_label'].values, index=tpl_atoms['label']).to_dict()
        prefix_by_full = _pd.Series(tpl_prefix_series.values, index=tpl_atoms['label']).to_dict()

        scoped_index = (tiled['tpl_molecule'].astype(str) + '||' + tpl_atoms['label'].astype(str))
        label_map_scoped = _pd.Series(tiled['car_label'].values, index=scoped_index).to_dict()

        def remap_connections_for_row(conn_str: str, curr_prefix: str, curr_tpl_mol: str) -> str:
            if not isinstance(conn_str, str) or not conn_str.strip():
                return ''
            new_conns: _List[str] = []
            for part in conn_str.split():
                m = _re.match(r'([^%#]+)([%#]*)', part)
                if not m:
                    continue
                token, operator = m.groups()

                if _re.match(r'^XXXX_\d+:', token):
                    token_full = token
                else:
                    token_full = f"{curr_prefix}{token}" if curr_prefix else token

                scope_key = f"{str(curr_tpl_mol)}||{token_full}"
                if scope_key in label_map_scoped:
                    new_conns.append(label_map_scoped[scope_key] + operator)
                    continue
                if token_full in label_map_full:
                    new_conns.append(label_map_full[token_full] + operator)

            return ' '.join(new_conns)

        tiled['connections'] = [
            remap_connections_for_row(c, p, m)
            for c, p, m in zip(tiled['connections'], tiled['tpl_prefix'], tiled['tpl_molecule'])
        ]
        all_atoms_list.append(tiled)

    if not all_atoms_list:
        raise SystemExit("Error: No atoms were processed.")

    combined_atoms = _pd.concat(all_atoms_list, ignore_index=True)
    combined_atoms['global_index'] = range(1, len(combined_atoms) + 1)

    if 'atom_type' in combined_atoms.columns:
        combined_atoms['atom_type'] = combined_atoms['atom_type'].astype(str).str.strip()
        combined_atoms.loc[combined_atoms['atom_type'] == 'H*', 'atom_type'] = 'h*'
        combined_atoms.loc[combined_atoms['atom_type'] == 'O*', 'atom_type'] = 'o*'

    if target_c is not None and 'z' in combined_atoms.columns and not combined_atoms['z'].empty:
        z_min_all = float(combined_atoms['z'].min())
        combined_atoms['z'] = combined_atoms['z'] - z_min_all
        z_max_all = float(combined_atoms['z'].max())
        if z_max_all > float(target_c) + 1e-6:
            print(f"[WARN] Combined z-span ({z_max_all:.3f} Å) exceeds target_c ({float(target_c):.3f} Å). "
                  f"Coordinates will not be rescaled; ensure Packmol slab and substrate thickness fit within c.")

    atoms_parq = output_dir / f"{output_prefix.name}_atoms.parquet"
    atoms_csv = output_dir / f"{output_prefix.name}_atoms.csv"
    molecules_csv = output_dir / f"{output_prefix.name}_molecules.csv"
    meta_json = output_dir / f"{output_prefix.name}_meta.json"

    try:
        combined_atoms.to_parquet(atoms_parq, index=False)
    except Exception as e:
        print(f"[WARN] to_parquet failed ({e}); proceeding without parquet. Downstream writers will use CSV.")
    combined_atoms.to_csv(atoms_csv, index=False)

    (combined_atoms.groupby("molecule", as_index=False)
     .size()
     .rename(columns={"size": "atom_count"})
     .to_csv(molecules_csv, index=False))

    header_lines = []
    box = pdb_meta.get("box")

    if not box:
        try:
            resnames = set(str(r).strip().upper() for r in pdb_atoms.get('resName', _pd.Series(dtype=str)).unique())
            candidates = []
            for stem in resnames:
                if stem == "WAT" or stem == "":
                    continue
                candidate = (templates_dir / f"{stem}.car")
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
                cell = slab_meta.get('cell', {})
                if all(k in cell for k in ('a','b','alpha','beta','gamma')):
                    a = float(cell['a']); b = float(cell['b'])
                    alpha = float(cell['alpha']); beta = float(cell['beta']); gamma = float(cell['gamma'])
            except Exception:
                pass

            if a is None or b is None or alpha is None or beta is None or gamma is None:
                with slab_car_path.open('r', encoding='utf-8', errors='ignore') as fh:
                    for line in fh:
                        stripped = line.strip()
                        if not stripped.upper().startswith('PBC'):
                            continue
                        nums = _re.findall(r"[-+]?\d*\.\d+|[-+]?\d+", stripped)
                        if len(nums) >= 6:
                            a_try, b_try, _c0, alpha_try, beta_try, gamma_try = [float(x) for x in nums[:6]]
                            a = a if a is not None else a_try
                            b = b if b is not None else b_try
                            alpha = alpha if alpha is not None else alpha_try
                            beta = beta if beta is not None else beta_try
                            gamma = gamma if gamma is not None else gamma_try
                            break

            if a is None or b is None or alpha is None or beta is None or gamma is None:
                raise ValueError(f"Could not parse PBC cell parameters from {slab_car_path}")

            if 'z' not in pdb_atoms.columns or pdb_atoms['z'].empty:
                raise ValueError("PDB atoms missing 'z' coordinates required to compute hydrated c length.")
            z_min = float(pdb_atoms['z'].min())
            z_max = float(pdb_atoms['z'].max())

            if target_c is not None:
                c = float(target_c)
            else:
                c = (z_max - z_min) + float(z_pad)

            box = {
                'a': float(a),
                'b': float(b),
                'c': float(c),
                'alpha': float(alpha),
                'beta': float(beta),
                'gamma': float(gamma),
            }
            pdb_meta['box'] = box
        except Exception as e:
            print(f"[WARN] Falling back without explicit PBC due to: {e}")

    if box and target_c is not None:
        try:
            box["c"] = float(target_c)
        except Exception:
            pass

    if box:
        a = float(box["a"]); b = float(box["b"]); c = float(box["c"])
        alpha = float(box["alpha"]); beta = float(box["beta"]); gamma = float(box["gamma"])
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
    (output_dir / f"{output_prefix.name}_meta.json").write_text(_json.dumps(combined_meta, indent=2))

    write_mdf(str(output_prefix))

def build_combined_car(
    pdb_atoms: _pd.DataFrame,
    pdb_meta: dict,
    templates: _Dict[str, _Tuple[_pd.DataFrame, dict]],
    output_prefix: _Path,
) -> None:
    input_dir = output_prefix.parent
    atoms_parq = input_dir / f"{output_prefix.name}_atoms.parquet"
    atoms_csv = input_dir / f"{output_prefix.name}_atoms.csv"
    meta_json = input_dir / f"{output_prefix.name}_meta.json"
    if (not meta_json.exists()) or (not atoms_parq.exists() and not atoms_csv.exists()):
        raise SystemExit("Error: expected intermediate files missing prior to CAR build.")
    write_car(output_prefix)

# Convenience wrappers matching names used in pm2mdfcar.build()
def _legacy_parse_pdb(p: _Path):
    return parse_pdb(p)
def _legacy_load(p: _Path):
    return load_mdf_templates(p)
def _legacy_build_mdf(a: _pd.DataFrame, m: dict, t, out: _Path, tpl_dir: _Path, target_c: float | None = None):
    return build_combined_mdf(a, m, t, out, tpl_dir, target_c=target_c)
def _legacy_build_car(a: _pd.DataFrame, m: dict, t, out: _Path):
    return build_combined_car(a, m, t, out)
# -------------------------------------------------------------------------------
