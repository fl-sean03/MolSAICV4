#!/usr/bin/env python3
"""
Generate ion-free alumina surface templates for use as the new base.

Reads original AS{2,5,10,12}.car/.mdf from:
  assets/AluminaSurfaces/templates

Writes filtered (Na+/Cl- removed) templates to:
  assets/AluminaSurfaces/templates_noions

Also copies over WAT/NA/CL templates unchanged for completeness.

Outputs a counts report:
  assets/AluminaSurfaces/templates_noions/ion_strip_counts.{json,txt}

Usage:
  python3 scripts/make_ion_free_templates.py
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Dict, Tuple

ION_TYPES = {"na+", "cl-"}  # atom_type tokens to remove


def _read_lines(p: Path) -> list[str]:
    return p.read_text(encoding="utf-8", errors="ignore").splitlines()


def _write_lines(p: Path, lines: list[str]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    # Ensure trailing newline
    text = "\n".join(lines)
    if not text.endswith("\n"):
        text += "\n"
    p.write_text(text, encoding="utf-8")


def _is_car_atom_line(s: str) -> bool:
    """
    CAR atom line shape:
      label x y z XXXX res_seq atom_type element charge
    """
    toks = s.strip().split()
    return len(toks) >= 9 and toks[4].upper() == "XXXX"


def _car_atom_type(s: str) -> str:
    toks = s.strip().split()
    return toks[6].strip().lower() if len(toks) >= 7 else ""


def filter_car_remove_ions(src: Path, dst: Path) -> int:
    """
    Remove any atom lines with atom_type in ION_TYPES.
    Returns number of removed atom lines.
    """
    removed = 0
    out: list[str] = []
    for ln in _read_lines(src):
        if _is_car_atom_line(ln):
            atype = _car_atom_type(ln)
            if atype in ION_TYPES:
                removed += 1
                continue
        out.append(ln)
    _write_lines(dst, out)
    return removed


_MDF_SKIP_PREFIXES = ("!", "#", "@")  # comments, topology headers, directives
_MDF_STAMP_RE = re.compile(r"^\s*XXXX[_:]", re.IGNORECASE)


def _mdf_atom_type(s: str) -> str:
    """
    MDF atom line (per templates) general shape:
      stamp element atom_type ...
    Example stamp: 'XXXX_23:Al1'
    We parse tokens by whitespace and extract token[2] as atom_type.
    """
    toks = re.split(r"\s+", s.strip())
    if len(toks) >= 3:
        return toks[2].strip().lower()
    return ""


def filter_mdf_remove_ions(src: Path, dst: Path) -> int:
    """
    Remove any MDF atom lines whose atom_type token matches ION_TYPES.
    Leaves headers, directives, bonds, etc. untouched. Ions are monatomic
    and are not expected to have bonds, so bond sections should remain valid.
    Returns number of removed atom lines.
    """
    removed = 0
    out: list[str] = []
    for ln in _read_lines(src):
        s = ln.strip()
        if s and not s.startswith(_MDF_SKIP_PREFIXES) and _MDF_STAMP_RE.match(s):
            atype = _mdf_atom_type(s)
            if atype in ION_TYPES:
                removed += 1
                continue
        out.append(ln)
    _write_lines(dst, out)
    return removed


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    src_dir = repo_root / "assets" / "AluminaSurfaces" / "templates"
    dst_dir = repo_root / "assets" / "AluminaSurfaces" / "templates_noions"

    surfaces = ["AS2", "AS5", "AS10", "AS12"]
    passthrough = ["WAT", "NA", "CL"]

    if not src_dir.exists():
        raise FileNotFoundError(f"Source templates directory not found: {src_dir}")

    dst_dir.mkdir(parents=True, exist_ok=True)

    report: Dict[str, Dict[str, int]] = {}

    # Filter AS{2,5,10,12}
    for surf in surfaces:
        car_in = src_dir / f"{surf}.car"
        mdf_in = src_dir / f"{surf}.mdf"
        car_out = dst_dir / f"{surf}.car"
        mdf_out = dst_dir / f"{surf}.mdf"

        if not car_in.exists():
            raise FileNotFoundError(f"Missing input CAR: {car_in}")
        if not mdf_in.exists():
            raise FileNotFoundError(f"Missing input MDF: {mdf_in}")

        removed_car = filter_car_remove_ions(car_in, car_out)
        removed_mdf = filter_mdf_remove_ions(mdf_in, mdf_out)

        report[surf] = {
            "removed_car_atoms": removed_car,
            "removed_mdf_atoms": removed_mdf,
        }

    # Copy WAT/NA/CL as-is for completeness
    for name in passthrough:
        for ext in (".car", ".mdf"):
            src = src_dir / f"{name}{ext}"
            if src.exists():
                shutil.copy2(str(src), str(dst_dir / src.name))

    # Emit report
    report_path_json = dst_dir / "ion_strip_counts.json"
    report_path_txt = dst_dir / "ion_strip_counts.txt"
    report_path_json.write_text(json.dumps(report, indent=2), encoding="utf-8")

    # Human-readable summary
    lines = []
    for k in surfaces:
        r = report.get(k, {})
        lines.append(f"{k}: removed_car_atoms={r.get('removed_car_atoms', 0)}, removed_mdf_atoms={r.get('removed_mdf_atoms', 0)}")
    report_path_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"[done] Wrote ion-free templates to: {dst_dir}")
    print(f"Report: {report_path_json}")
    for ln in lines:
        print("  - " + ln)


if __name__ == "__main__":
    main()