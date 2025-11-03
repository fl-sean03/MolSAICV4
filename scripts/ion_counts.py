#!/usr/bin/env python3
"""
Scan alumina surface templates to count ions per surface (ASx) and report totals.

- Parses .mdf first (preferred), falls back to .car when needed.
- Counts atom_type 'na+' and 'cl-' (case-insensitive) from MDF third column or CAR atom_type field.
- Captures the '@molecule ...' label from MDF (often includes pH annotation).
- Writes:
  - reports/ion_counts.json
  - reports/ion_counts.csv
  - reports/ion_counts.txt
- Prints a summary table to stdout.

Usage:
  python3 scripts/ion_counts.py
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional


REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = REPO_ROOT / "assets" / "AluminaSurfaces" / "templates"
REPORTS_DIR = REPO_ROOT / "reports"
JSON_OUT = REPORTS_DIR / "ion_counts.json"
CSV_OUT = REPORTS_DIR / "ion_counts.csv"
TXT_OUT = REPORTS_DIR / "ion_counts.txt"


def _read_lines(p: Path) -> List[str]:
    return p.read_text(encoding="utf-8", errors="ignore").splitlines()


def _parse_mdf_counts(mdf_path: Path) -> Tuple[int, int, Optional[str]]:
    """
    Return (na_count, cl_count, molecule_name)
    - MDF lines use: [stamp, element, atom_type, ...]
    - Ignore comment/meta lines starting with !, #, @ (except '@molecule' to capture molecule name)
    """
    na = 0
    cl = 0
    molecule = None
    for raw in _read_lines(mdf_path):
        s = raw.strip()
        if not s:
            continue
        if s.startswith("@molecule"):
            try:
                # e.g., '@molecule Al2O3_pH8_9_OH_unit'
                molecule = s.split(None, 1)[1].strip()
            except Exception:
                pass
            continue
        if s[0] in ("!", "#", "@"):
            continue
        toks = s.split()
        if len(toks) >= 3:
            atom_type = toks[2].strip().lower()
            if atom_type == "na+":
                na += 1
            elif atom_type == "cl-":
                cl += 1
    return na, cl, molecule


def _parse_car_counts(car_path: Path) -> Tuple[int, int]:
    """
    Return (na_count, cl_count) from CAR atom lines:
      label x y z XXXX res_seq atom_type element charge
    """
    na = 0
    cl = 0
    for raw in _read_lines(car_path):
        s = raw.strip()
        if (not s) or s.startswith(("!", "PBC")) or s.lower() == "end":
            continue
        toks = s.split()
        if len(toks) >= 9 and toks[4].upper() == "XXXX":
            atype = toks[6].strip().lower()
            if atype == "na+":
                na += 1
            elif atype == "cl-":
                cl += 1
    return na, cl


def _surface_stem(p: Path) -> str:
    return p.stem.upper()


def _find_surfaces() -> List[str]:
    # Discover AS*.mdf; prefer known ordering AS2, AS5, AS10, AS12 when present
    stems = sorted({_surface_stem(p) for p in TEMPLATES_DIR.glob("AS*.mdf")})
    order = ["AS2", "AS5", "AS10", "AS12"]
    ordered = [s for s in order if s in stems]
    for s in stems:
        if s not in ordered:
            ordered.append(s)
    return ordered


def _collect() -> Dict:
    results: List[Dict] = []
    totals = {"na+": 0, "cl-": 0}
    for stem in _find_surfaces():
        mdf = TEMPLATES_DIR / f"{stem}.mdf"
        car = TEMPLATES_DIR / f"{stem}.car"
        na = cl = 0
        molecule = None
        if mdf.exists():
            try:
                na, cl, molecule = _parse_mdf_counts(mdf)
            except Exception:
                pass
        # Fallback or augmentation via CAR (in case MDF parse failed silently)
        if (na == 0 and cl == 0) and car.exists():
            try:
                na2, cl2 = _parse_car_counts(car)
                na += na2
                cl += cl2
            except Exception:
                pass
        totals["na+"] += na
        totals["cl-"] += cl
        results.append({
            "surface": stem,
            "molecule": molecule,
            "counts": {"na+": na, "cl-": cl},
            "paths": {"mdf": str(mdf), "car": str(car)}
        })
    return {"surfaces": results, "totals": totals}


def _write_reports(data: Dict) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    # JSON
    JSON_OUT.write_text(json.dumps(data, indent=2), encoding="utf-8")
    # CSV
    with CSV_OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["surface", "molecule", "na_plus", "cl_minus"])
        for row in data["surfaces"]:
            w.writerow([
                row.get("surface", ""),
                (row.get("molecule") or ""),
                row.get("counts", {}).get("na+", 0),
                row.get("counts", {}).get("cl-", 0),
            ])
    # TXT
    lines: List[str] = []
    lines.append("Ion counts per surface (from templates):\n")
    for row in data["surfaces"]:
        surf = row.get("surface", "")
        mol = row.get("molecule") or ""
        na = row.get("counts", {}).get("na+", 0)
        cl = row.get("counts", {}).get("cl-", 0)
        lines.append(f"{surf:<6s}  molecule={mol:<30s}  na+={na:>4d}  cl-={cl:>4d}")
    tna = data.get("totals", {}).get("na+", 0)
    tcl = data.get("totals", {}).get("cl-", 0)
    lines.append("")
    lines.append(f"Totals: na+={tna}  cl-={tcl}")
    TXT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    if not TEMPLATES_DIR.is_dir():
        print(f"[error] Templates dir not found: {TEMPLATES_DIR}", file=sys.stderr)
        return 2
    data = _collect()
    _write_reports(data)
    # Print concise table
    print("surface  molecule                         na+   cl-")
    print("-------  ------------------------------  ----  ----")
    for row in data["surfaces"]:
        surf = row.get("surface", "")
        mol = (row.get("molecule") or "")[:30]
        na = row.get("counts", {}).get("na+", 0)
        cl = row.get("counts", {}).get("cl-", 0)
        print(f"{surf:<7s}  {mol:<30s}  {na:>4d}  {cl:>4d}")
    tna = data.get("totals", {}).get("na+", 0)
    tcl = data.get("totals", {}).get("cl-", 0)
    print("-------  ------------------------------  ----  ----")
    print(f"{'TOTAL':<7s}  {'':<30s}  {tna:>4d}  {tcl:>4d}")
    print(f"\nWrote: {JSON_OUT}")
    print(f"Wrote: {CSV_OUT}")
    print(f"Wrote: {TXT_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())