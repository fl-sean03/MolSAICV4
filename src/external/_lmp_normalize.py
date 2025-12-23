"""LAMMPS data file normalization logic for msi2lmp wrapper.

Private module containing post-processing normalization for LAMMPS .data files,
including header normalization and coordinate shifting.
"""

from __future__ import annotations

import re
from pathlib import Path


def parse_abc_from_car(p: Path) -> tuple[float | None, float | None, float | None]:
    """Parse a/b/c lattice parameters from a CAR file PBC line."""
    a = b = c = None
    try:
        with open(p, "r", encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                s = line.strip()
                if s.upper().startswith("PBC") and "=" not in s.upper():
                    nums = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", s)
                    if len(nums) >= 3:
                        a = float(nums[0])
                        b = float(nums[1])
                        c = float(nums[2])
                        break
    except Exception:
        pass
    return a, b, c


def normalize_data_file(
    data_path: Path,
    a_dim: float | None,
    b_dim: float | None,
    do_xy: bool,
    z_target: float | None,
    do_z_shift: bool,
    do_z_center: bool,
) -> None:
    """Normalize LAMMPS .data file header and optionally shift Z coordinates.

    Parameters:
    - data_path: Path to the LAMMPS .data file to normalize in-place
    - a_dim: CAR PBC a dimension (x extent)
    - b_dim: CAR PBC b dimension (y extent)
    - do_xy: whether to normalize x/y header extents
    - z_target: target z-dimension for header normalization
    - do_z_shift: if True, shift atom Z so min(z)=0 (legacy behavior)
    - do_z_center: if True, shift atom Z so structure midpoint maps to z_target/2
      (takes precedence over do_z_shift)
    """

    def _fmt(x: float) -> str:
        return f"{x:.6f}"

    # Read file
    with open(data_path, "r", encoding="utf-8", errors="ignore") as fh:
        lines = fh.read().splitlines()

    # Find header bounds and indices
    x_idx = y_idx = z_idx = None
    atoms_header_idx = None
    for i, line in enumerate(lines[:300]):
        if re.search(r"\bxlo\s+xhi\b", line):
            x_idx = i
        elif re.search(r"\bylo\s+yhi\b", line):
            y_idx = i
        elif re.search(r"\bzlo\s+zhi\b", line):
            z_idx = i
        if atoms_header_idx is None and re.match(r"^\s*Atoms\b", line):
            atoms_header_idx = i

    # Update XY header extents
    if do_xy:
        if a_dim is not None and x_idx is not None:
            lines[x_idx] = f"0.000000 {_fmt(a_dim)} xlo xhi"
        if b_dim is not None and y_idx is not None:
            lines[y_idx] = f"0.000000 {_fmt(b_dim)} ylo yhi"

    # Identify Atoms section range
    if atoms_header_idx is not None:
        start = atoms_header_idx + 1
        while start < len(lines) and (lines[start].strip() == "" or lines[start].lstrip().startswith("#")):
            start += 1
        end = start
        section_header_pat = re.compile(
            r"^(Bonds|Angles|Dihedrals|Impropers|Velocities|Masses|Pair Coeffs|Bond Coeffs|Angle Coeffs|Dihedral Coeffs|Improper Coeffs)\b",
            re.IGNORECASE,
        )
        while end < len(lines):
            s = lines[end].strip()
            if s != "" and section_header_pat.match(s):
                break
            end += 1

        # Determine atom style (from header comment, e.g., 'Atoms # full')
        style = "unknown"
        m = re.search(r"^\s*Atoms\s*(?:#\s*(\w+))?", lines[atoms_header_idx])
        if m and m.group(1):
            style = m.group(1).strip().lower()

        def _extract_xyz_tokens(parts: list[str]) -> tuple[float | None, float | None, float | None, int | None]:
            try:
                if style == "full":
                    x_i, y_i, z_i = 4, 5, 6
                elif style == "molecular":
                    x_i, y_i, z_i = 3, 4, 5
                elif style == "atomic":
                    x_i, y_i, z_i = 2, 3, 4
                else:
                    # Fallback: last three numeric tokens
                    z_i = y_i = x_i = None
                    count = 0
                    for idx in range(len(parts) - 1, -1, -1):
                        tok = parts[idx]
                        if re.match(r"^[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?$", tok):
                            count += 1
                            if count == 1:
                                z_i = idx
                            elif count == 2:
                                y_i = idx
                            elif count == 3:
                                x_i = idx
                                break
                    if x_i is None or y_i is None or z_i is None:
                        return None, None, None, None
                return float(parts[x_i]), float(parts[y_i]), float(parts[z_i]), z_i
            except Exception:
                return None, None, None, None

        # Pass 1: compute z_min and z_max
        z_min = float("inf")
        z_max = -float("inf")
        for j in range(start, end):
            line = lines[j]
            left = line.split("#", 1)[0].strip()
            if not left:
                continue
            parts = left.split()
            _, _, z_val, _ = _extract_xyz_tokens(parts)
            if z_val is None:
                continue
            if z_val < z_min:
                z_min = z_val
            if z_val > z_max:
                z_max = z_val

        # Pass 2 (optional): rewrite atoms lines with uniformly shifted z.
        # Precedence: centering wins over legacy min(z)=0 shifting.
        z_shift = None
        if do_z_center:
            if z_target is not None and z_min != float("inf") and z_max != -float("inf"):
                z_mid = 0.5 * (z_min + z_max)
                z_shift = 0.5 * float(z_target) - z_mid
        elif do_z_shift:
            if z_min != float("inf"):
                z_shift = -z_min

        if z_shift is not None:
            for j in range(start, end):
                original = lines[j]
                head, sep, comment = original.partition("#")
                left = head.strip()
                if not left:
                    continue
                parts = left.split()
                _, _, z_val, z_index = _extract_xyz_tokens(parts)
                if z_index is None or z_val is None:
                    lines[j] = original.rstrip()
                    continue
                parts[z_index] = _fmt(z_val + float(z_shift))
                new_left = " ".join(parts)
                # Ensure a space before '#' so image flags and comments don't merge
                lines[j] = (new_left + (" " + sep + comment if sep else "")).rstrip()

        # Update Z header:
        # - If z_target is provided, always normalize header to [0, z_target]
        # - Else if we performed a legacy z-shift, normalize to [0, span]
        # - Else leave header unchanged
        if z_idx is not None and (z_target is not None or (do_z_shift and not do_z_center)):
            if z_target is None:
                zhi_val = (z_max - z_min) if (z_min != float("inf") and z_max != -float("inf")) else None
            else:
                zhi_val = float(z_target)
            if zhi_val is not None:
                lines[z_idx] = f"0.000000 {_fmt(zhi_val)} zlo zhi"

    # Write back
    with open(data_path, "w", encoding="utf-8") as outfh:
        outfh.write("\n".join(lines) + "\n")
