# Subtask 3: frc_writer.py Implementation Plan

**Date**: 2025-12-21  
**Status**: READY FOR IMPLEMENTATION  
**Target File**: `src/upm/src/upm/build/frc_writer.py`

---

## 1) Overview

This module completes the FRC generation pipeline by implementing:
1. **Formatting functions** for each entry type (8 functions)
2. **Main writer function** `write_cvff_frc()` that populates the skeleton template

## 2) Dependencies

```python
from pathlib import Path
from .cvff_skeleton import CVFF_SKELETON
from .frc_input import (
    FRCInput, AtomTypeEntry, BondEntry, AngleEntry,
    TorsionEntry, OOPEntry, NonbondEntry,
)
```

---

## 3) Row Format Specifications

### 3.1 Version/Reference Constants

| Section | Ver | Ref |
|---------|-----|-----|
| `#atom_types` | 2.0 | 18 |
| `#equivalence` | 1.0 | 1 |
| `#auto_equivalence` | 2.0 | 18 |
| `#quadratic_bond` | 2.0 | 18 |
| `#quadratic_angle` | 2.0 | 18 |
| `#torsion_1` | 2.0 | 18 |
| `#out_of_plane` | 2.0 | 18 |
| `#nonbond(12-6)` | 2.0 | 18 |

### 3.2 Format Strings

Based on skeleton column headers:

```python
# #atom_types cvff
# !Ver  Ref  Type    Mass      Element  Connections   Comment
# !---- ---  ----  ----------  -------  -----------------------------------------
FMT_ATOM_TYPE = " 2.0  18    {type:<6s} {mass:10.6f}  {elem:<2s}      {conn:d}"

# #equivalence cvff (self-equivalence - all columns same)
# !Ver  Ref   Type  NonB     Bond    Angle    Torsion    OOP
FMT_EQUIVALENCE = " 1.0   1    {t:<6s} {t:<6s}  {t:<6s}  {t:<6s}  {t:<6s}  {t:<6s}"

# #auto_equivalence cvff_auto (self-equivalence - all 10 columns same)
# !Ver  Ref   Type  NonB Bond   Bond     Angle    Angle     Torsion   Torsion      OOP      OOP
FMT_AUTO_EQUIV = " 2.0  18    {t:<6s} {t:<6s} {t:<6s}  {t:<6s}  {t:<6s}  {t:<6s}  {t:<6s}  {t:<6s}  {t:<6s}  {t:<6s}"

# #quadratic_bond cvff
# !Ver  Ref     I     J          R0         K2
FMT_BOND = " 2.0  18    {i:<6s} {j:<6s} {r0:10.6f} {k:12.6f}"

# #quadratic_angle cvff
# !Ver  Ref     I     J     K       Theta0         K2
FMT_ANGLE = " 2.0  18    {i:<6s} {j:<6s} {k:<6s} {theta:10.6f} {force:12.6f}"

# #torsion_1 cvff
# !Ver  Ref     I     J     K     L           Kphi        n           Phi0
FMT_TORSION = " 2.0  18    {i:<6s} {j:<6s} {k:<6s} {l:<6s} {kphi:10.6f}   {n:d}   {phi0:10.6f}"

# #out_of_plane cvff (same format as torsion)
# !Ver  Ref     I     J     K     L           Kchi        n           Chi0
FMT_OOP = " 2.0  18    {i:<6s} {j:<6s} {k:<6s} {l:<6s} {kchi:10.6f}   {n:d}   {chi0:10.6f}"

# #nonbond(12-6) cvff
# !Ver  Ref     I           A               B
FMT_NONBOND = " 2.0  18    {i:<6s} {a:14.6f}  {b:14.6f}"
```

---

## 4) Function Signatures

### 4.1 Internal Formatting Functions

```python
def _format_atom_type_entry(entry: AtomTypeEntry) -> str:
    """Format single #atom_types row.
    
    Example output: " 2.0  18    C_MOF  12.011000  C       4"
    """

def _format_equivalence_entry(atom_type: str) -> str:
    """Format single #equivalence row with self-equivalence.
    
    All equivalence columns use the same atom type.
    Example: " 1.0   1    C_MOF  C_MOF   C_MOF   C_MOF   C_MOF   C_MOF"
    """

def _format_auto_equivalence_entry(atom_type: str) -> str:
    """Format single #auto_equivalence row with self-equivalence.
    
    All 10 columns use the same atom type.
    """

def _format_bond_entry(entry: BondEntry) -> str:
    """Format single #quadratic_bond row.
    
    Example: " 2.0  18    C_MOF  H_MOF    1.090000   340.000000"
    """

def _format_angle_entry(entry: AngleEntry) -> str:
    """Format single #quadratic_angle row.
    
    Example: " 2.0  18    H_MOF  C_MOF  H_MOF   109.500000    50.000000"
    """

def _format_torsion_entry(entry: TorsionEntry) -> str:
    """Format single #torsion_1 row.
    
    Example: " 2.0  18    C_MOF  N_MOF  C_MOF  H_MOF     0.000000   1     0.000000"
    """

def _format_oop_entry(entry: OOPEntry) -> str:
    """Format single #out_of_plane row.
    
    Example: " 2.0  18    C_MOF  N_MOF  C_MOF  Zn_MO     0.000000   0     0.000000"
    """

def _format_nonbond_entry(entry: NonbondEntry) -> str:
    """Format single #nonbond(12-6) row.
    
    Example: " 2.0  18    C_MOF   1234567.890000    1234.567890"
    """
```

### 4.2 Main Writer Function

```python
def write_cvff_frc(
    frc_input: FRCInput,
    out_path: Path | str,
    *,
    skeleton: str = CVFF_SKELETON,
) -> str:
    """Write a CVFF .frc file from FRCInput specification.
    
    Args:
        frc_input: Complete specification of all entries.
        out_path: Where to write the file.
        skeleton: Template string (default: canonical CVFF skeleton).
    
    Returns:
        The output path as a string.
    
    Notes:
        - Output is deterministic (sorted entries, stable formatting)
        - File is UTF-8 encoded with Unix line endings
        - Entries are sorted alphabetically for stable diffs
    """
```

---

## 5) Deterministic Output Rules

### 5.1 Sorting

| Section | Sort Key |
|---------|----------|
| atom_types | `entry.atom_type` |
| equivalences | `atom_type` |
| auto_equivalences | `atom_type` |
| bonds | `(entry.type1, entry.type2)` |
| angles | `(entry.type1, entry.type2, entry.type3)` |
| torsions | `(entry.type1, entry.type2, entry.type3, entry.type4)` |
| oops | `(entry.type1, entry.type2, entry.type3, entry.type4)` |
| nonbonds | `entry.atom_type` |

### 5.2 Float Formatting

All floats use `%.6f` format for consistent precision:
- Mass: 10.6f (10 chars, 6 decimal places)
- R0, Theta0, Kphi, Kchi, Phi0, Chi0: 10.6f
- K2 (force constants): 12.6f
- LJ A, B: 14.6f

### 5.3 File Encoding

- UTF-8 encoding
- Unix line endings (`\n`)
- No trailing whitespace normalization (preserve format strings)

---

## 6) Implementation Pseudocode

```python
def write_cvff_frc(frc_input: FRCInput, out_path: Path | str, *, skeleton: str = CVFF_SKELETON) -> str:
    # Extract unique atom types for equivalence sections
    atom_types = sorted({e.atom_type for e in frc_input.atom_types})
    
    # Format all sections
    atom_types_block = "\n".join(
        _format_atom_type_entry(e) for e in sorted(frc_input.atom_types, key=lambda x: x.atom_type)
    )
    
    equivalences_block = "\n".join(
        _format_equivalence_entry(t) for t in atom_types
    )
    
    auto_equivalences_block = "\n".join(
        _format_auto_equivalence_entry(t) for t in atom_types
    )
    
    bonds_block = "\n".join(
        _format_bond_entry(e) for e in sorted(frc_input.bonds, key=lambda x: (x.type1, x.type2))
    )
    
    angles_block = "\n".join(
        _format_angle_entry(e) for e in sorted(frc_input.angles, key=lambda x: (x.type1, x.type2, x.type3))
    )
    
    torsions_block = "\n".join(
        _format_torsion_entry(e) for e in sorted(frc_input.torsions, key=lambda x: (x.type1, x.type2, x.type3, x.type4))
    )
    
    oops_block = "\n".join(
        _format_oop_entry(e) for e in sorted(frc_input.oops, key=lambda x: (x.type1, x.type2, x.type3, x.type4))
    )
    
    nonbonds_block = "\n".join(
        _format_nonbond_entry(e) for e in sorted(frc_input.nonbonds, key=lambda x: x.atom_type)
    )
    
    # Populate skeleton
    content = skeleton.format(
        atom_types=atom_types_block,
        equivalences=equivalences_block,
        auto_equivalences=auto_equivalences_block,
        bonds=bonds_block,
        angles=angles_block,
        torsions=torsions_block,
        oops=oops_block,
        nonbonds=nonbonds_block,
    )
    
    # Write with Unix line endings
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8", newline="\n")
    
    return str(out)
```

---

## 7) Module Structure (Target: <200 lines)

```python
# frc_writer.py - Estimated line counts

"""Docstring"""                                     # 5 lines
from __future__ import annotations                  # 1 line
from pathlib import Path                            # 1 line
from .cvff_skeleton import CVFF_SKELETON            # 1 line
from .frc_input import (...)                        # 3 lines

# Formatting functions
def _format_atom_type_entry(...)    -> str: ...     # 6 lines
def _format_equivalence_entry(...)  -> str: ...     # 4 lines
def _format_auto_equivalence_entry(...) -> str: ... # 5 lines
def _format_bond_entry(...)         -> str: ...     # 4 lines
def _format_angle_entry(...)        -> str: ...     # 4 lines
def _format_torsion_entry(...)      -> str: ...     # 5 lines
def _format_oop_entry(...)          -> str: ...     # 5 lines
def _format_nonbond_entry(...)      -> str: ...     # 4 lines

# Main function
def write_cvff_frc(...) -> str: ...                 # 55 lines

# Exports
__all__ = ["write_cvff_frc"]                        # 1 line

# TOTAL: ~100 lines (well under 200 limit)
```

---

## 8) Acceptance Criteria

1. ✅ File created at `src/upm/src/upm/build/frc_writer.py`
2. ✅ Line count < 200
3. ✅ Exports `write_cvff_frc` in `__all__`
4. ✅ Output is byte-deterministic (same FRCInput → identical file)
5. ✅ UTF-8 encoding with Unix line endings
6. ✅ All 8 formatting functions implemented
7. ✅ Module is importable

---

## 9) Scope Guardrails

**DO:**
- Implement all 8 formatting functions
- Implement `write_cvff_frc()` main function
- Ensure deterministic output (sorted entries, stable formatting)
- Use `CVFF_SKELETON` from `cvff_skeleton.py`
- Import entry types from `frc_input.py`

**DO NOT:**
- Modify `cvff_skeleton.py`
- Modify `frc_input.py`
- Add conversion logic (that's in `frc_input.py`)
- Add validation logic beyond basic type hints

---

## 10) Ready for Implementation

The plan is complete. Switch to Code mode to implement:

```
src/upm/src/upm/build/frc_writer.py
```
