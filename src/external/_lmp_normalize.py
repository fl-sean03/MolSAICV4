"""LAMMPS data file normalization logic for msi2lmp wrapper.

Private module containing post-processing normalization for LAMMPS .data files,
including header normalization, coordinate shifting, and triclinic box support.
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Tuple


def parse_abc_from_car(p: Path) -> tuple[float | None, float | None, float | None]:
    """Parse a/b/c lattice parameters from a CAR file PBC line (legacy)."""
    cell = parse_cell_from_car(p)
    return cell[0], cell[1], cell[2]


def parse_cell_from_car(
    p: Path,
) -> Tuple[float | None, float | None, float | None, float | None, float | None, float | None]:
    """Parse full cell parameters (a, b, c, alpha, beta, gamma) from a CAR PBC line."""
    a = b = c = alpha = beta = gamma = None
    try:
        with open(p, "r", encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                s = line.strip()
                if s.upper().startswith("PBC") and "=" not in s.upper():
                    nums = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", s)
                    if len(nums) >= 6:
                        a, b, c = float(nums[0]), float(nums[1]), float(nums[2])
                        alpha, beta, gamma = float(nums[3]), float(nums[4]), float(nums[5])
                    elif len(nums) >= 3:
                        a, b, c = float(nums[0]), float(nums[1]), float(nums[2])
                        alpha, beta, gamma = 90.0, 90.0, 90.0
                    break
    except Exception:
        pass
    return a, b, c, alpha, beta, gamma


def is_triclinic(alpha: float, beta: float, gamma: float, tol: float = 0.01) -> bool:
    """Return True if any cell angle differs from 90 degrees."""
    return (abs(alpha - 90.0) > tol or abs(beta - 90.0) > tol or abs(gamma - 90.0) > tol)


def compute_lammps_tilt(
    a: float, b: float, c: float, alpha: float, beta: float, gamma: float
) -> dict[str, float]:
    """Convert crystallographic cell to LAMMPS box parameters.

    Returns dict with keys: lx, ly, lz, xy, xz, yz.
    For orthogonal cells, xy=xz=yz=0.
    """
    alpha_r = math.radians(alpha)
    beta_r = math.radians(beta)
    gamma_r = math.radians(gamma)

    lx = a
    xy = b * math.cos(gamma_r)
    xz = c * math.cos(beta_r)
    ly = math.sqrt(max(0.0, b * b - xy * xy))
    if ly < 1e-12:
        raise ValueError(f"Degenerate cell: sin(gamma) ~ 0 for gamma={gamma}")
    yz = (b * c * math.cos(alpha_r) - xy * xz) / ly
    lz = math.sqrt(max(0.0, c * c - xz * xz - yz * yz))
    return {"lx": lx, "ly": ly, "lz": lz, "xy": xy, "xz": xz, "yz": yz}


def normalize_data_file(
    data_path: Path,
    a_dim: float | None,
    b_dim: float | None,
    do_xy: bool,
    z_target: float | None,
    do_z_shift: bool,
    do_z_center: bool,
    cell_angles: tuple[float, float, float] | None = None,
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
    - cell_angles: (alpha, beta, gamma) in degrees; if triclinic, writes tilt factors
    """

    def _fmt(x: float) -> str:
        return f"{x:.6f}"

    # Determine if triclinic
    triclinic = False
    tilt = None
    if cell_angles is not None and a_dim is not None and b_dim is not None:
        alpha, beta, gamma = cell_angles
        if is_triclinic(alpha, beta, gamma):
            triclinic = True
            c_val = z_target if z_target is not None else 100.0  # fallback
            tilt = compute_lammps_tilt(a_dim, b_dim, c_val, alpha, beta, gamma)

    # Read file
    with open(data_path, "r", encoding="utf-8", errors="ignore") as fh:
        lines = fh.read().splitlines()

    # Find header bounds and indices
    x_idx = y_idx = z_idx = None
    tilt_idx = None  # existing "xy xz yz" line if present
    atoms_header_idx = None
    for i, line in enumerate(lines[:300]):
        if re.search(r"\bxlo\s+xhi\b", line):
            x_idx = i
        elif re.search(r"\bylo\s+yhi\b", line):
            y_idx = i
        elif re.search(r"\bzlo\s+zhi\b", line):
            z_idx = i
        elif re.search(r"\bxy\s+xz\s+yz\b", line):
            tilt_idx = i
        if atoms_header_idx is None and re.match(r"^\s*Atoms\b", line):
            atoms_header_idx = i

    # Update XY header extents
    if do_xy:
        if triclinic and tilt is not None:
            # For triclinic: LAMMPS data file uses internal box coords (xlo=0, xhi=lx).
            # The tilt factors on the separate xy/xz/yz line define the skew.
            if x_idx is not None:
                lines[x_idx] = f"0.000000 {_fmt(tilt['lx'])} xlo xhi"
            if y_idx is not None:
                lines[y_idx] = f"0.000000 {_fmt(tilt['ly'])} ylo yhi"
        else:
            if a_dim is not None and x_idx is not None:
                lines[x_idx] = f"0.000000 {_fmt(a_dim)} xlo xhi"
            if b_dim is not None and y_idx is not None:
                lines[y_idx] = f"0.000000 {_fmt(b_dim)} ylo yhi"

    # Write or update tilt factors for triclinic cells
    if triclinic and tilt is not None:
        tilt_line = f"{_fmt(tilt['xy'])} {_fmt(tilt['xz'])} {_fmt(tilt['yz'])} xy xz yz"
        if tilt_idx is not None:
            lines[tilt_idx] = tilt_line
        elif z_idx is not None:
            # Insert tilt line right after zlo/zhi
            lines.insert(z_idx + 1, tilt_line)
            # Adjust indices that follow
            if atoms_header_idx is not None and atoms_header_idx > z_idx:
                atoms_header_idx += 1

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

        # Wrap XY coordinates into the triclinic bounding box.
        # msi2lmp recenters atoms which can push them outside the periodic cell.
        # Wrapping in fractional ab-plane only (not z — may have vacuum).
        if triclinic and tilt is not None:
            lx_v = tilt["lx"]
            ly_v = tilt["ly"]
            xy_v = tilt["xy"]
            # Determine x,y column indices from style
            if style == "full":
                xi, yi = 4, 5
            elif style == "molecular":
                xi, yi = 3, 4
            elif style == "atomic":
                xi, yi = 2, 3
            else:
                xi, yi = None, None  # skip wrapping for unknown style
            if xi is not None and yi is not None:
                for j in range(start, end):
                    original = lines[j]
                    head, sep, comment = original.partition("#")
                    left = head.strip()
                    if not left:
                        continue
                    parts = left.split()
                    if len(parts) <= max(xi, yi):
                        continue
                    try:
                        x_val = float(parts[xi])
                        y_val = float(parts[yi])
                    except ValueError:
                        continue
                    # Convert to fractional ab-plane: x = s*lx + t*xy, y = t*ly
                    t_frac = y_val / ly_v
                    s_frac = (x_val - t_frac * xy_v) / lx_v
                    # Wrap to [0, 1)
                    s_frac -= math.floor(s_frac)
                    t_frac -= math.floor(t_frac)
                    # Convert back to Cartesian
                    parts[xi] = _fmt(s_frac * lx_v + t_frac * xy_v)
                    parts[yi] = _fmt(t_frac * ly_v)
                    new_left = " ".join(parts)
                    lines[j] = (new_left + (" " + sep + comment if sep else "")).rstrip()

    # Write back
    with open(data_path, "w", encoding="utf-8") as outfh:
        outfh.write("\n".join(lines) + "\n")
