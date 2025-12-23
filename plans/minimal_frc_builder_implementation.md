# Minimal FRC Builder Implementation Plan

**Date**: 2025-12-21  
**Status**: READY FOR IMPLEMENTATION  
**Mode**: Architect → Orchestrator

---

## 1) Executive Summary

This plan creates a **new minimal FRC builder** to replace the bloated `frc_from_scratch.py` (4323 lines) and `cvff_embedded_base.py` (5591 lines). The new system will:

1. **Take a minimal CVFF skeleton template** (~80 lines of structure)
2. **Accept USM-derived TermSet + ParameterSet** as inputs
3. **Produce a ~157-line `.frc`** compatible with `msi2lmp.exe` WITHOUT `-ignore` flag
4. **Support structure-only mode** (zeroed/placeholder parameters when values unknown)
5. **Be organized across multiple small files** (max 500 lines each)

### Key Design Principles

- **Minimal**: Only the code needed for the job
- **Deterministic**: Same inputs → identical output bytes
- **Layered**: USM outputs → FRCInput spec → `.frc` file
- **Extensible**: Easy to add parameter sources later

---

## 2) Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USM Package                                     │
│  ┌─────────────────────┐    ┌─────────────────────┐                         │
│  │ derive_termset()    │    │ derive_parameterset()│                        │
│  │ - atom_types        │    │ - atom_types         │                        │
│  │ - bond_types        │    │   - mass_amu         │                        │
│  │ - angle_types       │    │   - lj_sigma         │                        │
│  │ - dihedral_types    │    │   - lj_epsilon       │                        │
│  │ - improper_types    │    │   - element          │                        │
│  └──────────┬──────────┘    └──────────┬──────────┘                         │
└─────────────┼──────────────────────────┼────────────────────────────────────┘
              │                          │
              ▼                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          NEW: Conversion Layer                               │
│                     src/upm/src/upm/build/frc_input.py                       │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ build_frc_input(termset, parameterset, *, placeholders=True)        │    │
│  │ → FRCInput dataclass                                                 │    │
│  │   - atom_type_entries: list[AtomTypeEntry]                          │    │
│  │   - bond_entries: list[BondEntry]                                   │    │
│  │   - angle_entries: list[AngleEntry]                                 │    │
│  │   - torsion_entries: list[TorsionEntry]                             │    │
│  │   - oop_entries: list[OOPEntry]                                     │    │
│  │   - nonbond_entries: list[NonbondEntry]                             │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          NEW: FRC Writer                                     │
│                     src/upm/src/upm/build/frc_writer.py                      │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ write_cvff_frc(frc_input, out_path, *, skeleton=CVFF_SKELETON)      │    │
│  │ → Deterministic .frc file (~157 lines)                              │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          NEW: CVFF Skeleton Template                         │
│                     src/upm/src/upm/build/cvff_skeleton.py                   │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ CVFF_SKELETON: str = ...  (~80 lines template)                      │    │
│  │ - Contains msi2lmp.exe required structure                           │    │
│  │ - Placeholders for entries: {atom_types}, {bonds}, etc.             │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3) Data Model

### 3.1 FRCInput Specification

```python
# src/upm/src/upm/build/frc_input.py

from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class AtomTypeEntry:
    """Single atom type for #atom_types section."""
    atom_type: str      # e.g., "C_MOF"
    mass_amu: float     # e.g., 12.011
    element: str        # e.g., "C"
    connects: int       # Expected connection count (for msi2lmp validation)
    # Optional computed values
    lj_a: Optional[float] = None  # LJ A parameter (kcal/mol * Å^12)
    lj_b: Optional[float] = None  # LJ B parameter (kcal/mol * Å^6)

@dataclass(frozen=True)
class BondEntry:
    """Single bond parameter for #quadratic_bond section."""
    type1: str          # First atom type
    type2: str          # Second atom type
    r0: float           # Equilibrium distance (Å)
    k: float            # Force constant (kcal/mol/Å²)

@dataclass(frozen=True)  
class AngleEntry:
    """Single angle parameter for #quadratic_angle section."""
    type1: str          # First atom type
    type2: str          # Central atom type
    type3: str          # Third atom type
    theta0: float       # Equilibrium angle (degrees)
    k: float            # Force constant (kcal/mol/rad²)

@dataclass(frozen=True)
class TorsionEntry:
    """Single torsion parameter for #torsion_1 section."""
    type1: str
    type2: str
    type3: str
    type4: str
    kphi: float         # Barrier height (kcal/mol)
    n: int              # Periodicity
    phi0: float         # Phase angle (degrees)

@dataclass(frozen=True)
class OOPEntry:
    """Single out-of-plane parameter for #out_of_plane section."""
    type1: str          # First peripheral
    type2: str          # Central atom
    type3: str          # Second peripheral
    type4: str          # Third peripheral
    kchi: float         # Force constant (kcal/mol)
    n: int              # Periodicity
    chi0: float         # Equilibrium angle (degrees)

@dataclass(frozen=True)
class NonbondEntry:
    """Single nonbond parameter for #nonbond(12-6) section."""
    atom_type: str
    lj_a: float         # A parameter
    lj_b: float         # B parameter

@dataclass
class FRCInput:
    """Complete specification for generating an .frc file."""
    atom_types: list[AtomTypeEntry]
    bonds: list[BondEntry]
    angles: list[AngleEntry]
    torsions: list[TorsionEntry]
    oops: list[OOPEntry]
    nonbonds: list[NonbondEntry]
    
    # Metadata
    forcefield_label: str = "cvff"
    msi2lmp_max_type_len: int = 5  # For alias generation
```

### 3.2 Placeholder Parameter Policy

When parameters are missing (structure-only mode), use these **tool-satisfying defaults**:

| Section | Field | Default Value | Rationale |
|---------|-------|---------------|-----------|
| `#quadratic_bond` | k | 300.0 | Typical C-C bond stiffness |
| `#quadratic_bond` | r0 | 1.50 | Average single bond length |
| `#quadratic_bond` (H-X) | k/r0 | 340.0/1.09 | H bonds are shorter |
| `#quadratic_bond` (Zn-X) | k/r0 | 150.0/2.05 | Metal bonds are longer |
| `#quadratic_angle` | k | 50.0 | Moderate angle stiffness |
| `#quadratic_angle` | theta0 | 109.5 | Tetrahedral default |
| `#quadratic_angle` (Zn center) | theta0 | 90.0 | Octahedral coordination |
| `#torsion_1` | kphi | 0.0 | Zero barrier (no preference) |
| `#torsion_1` | n | 1 | Single periodicity |
| `#torsion_1` | phi0 | 0.0 | No phase shift |
| `#out_of_plane` | kchi | 0.0 | Zero barrier |
| `#out_of_plane` | n | 0 | No periodicity |
| `#out_of_plane` | chi0 | 0.0 | No phase shift |
| `#atom_types` | connects | Element-based | See table below |

**Connections by Element** (for `#atom_types`):

| Element | Connects |
|---------|----------|
| H | 1 |
| C | 4 |
| N | 3 |
| O | 2 |
| Zn | 6 |
| Other | 0 |

---

## 4) Module Layout

### 4.1 New Files to Create

```
src/upm/src/upm/build/
├── __init__.py              # Updated exports
├── cvff_skeleton.py         # ~100 lines - Template string only
├── frc_input.py             # ~200 lines - Data model + conversion
├── frc_writer.py            # ~200 lines - Format and write .frc
└── frc_from_scratch.py      # DELETE or reduce to ~50 lines (legacy shim)
```

### 4.2 Files to Delete/Archive

```
src/upm/src/upm/build/
├── cvff_embedded_base.py    # DELETE - 5591 lines of static content
└── frc_from_scratch.py      # REPLACE - 4323 lines → ~50 line shim
```

### 4.3 Line Count Targets

| File | Max Lines | Purpose |
|------|-----------|---------|
| `cvff_skeleton.py` | 100 | CVFF template constant |
| `frc_input.py` | 250 | Data model + conversion logic |
| `frc_writer.py` | 150 | Deterministic formatting + writing |
| `__init__.py` | 20 | Re-exports |
| **Total** | **520** | Within 500-line constraint (close enough) |

---

## 5) Implementation Details

### 5.1 cvff_skeleton.py

```python
"""Canonical CVFF skeleton template for msi2lmp.exe compatibility.

This module contains the minimal required structure validated through
Phase 7-11 experiments (M25-M31). Every line is necessary.
"""

CVFF_SKELETON: str = '''!BIOSYM forcefield          1


! Currently Insight does not handle version numbers on lines correctly.
! It uses the first occurence of a line, so when making changes you
! can either comment the original out temporarily or put the correct
! line first.



#define cvff

> This is the new format version of the cvff forcefield

!Ver  Ref 		Function		Label
!---- ---   ---------------------------------	------
 2.0  18    atom_types				cvff
 1.0   1    equivalence				cvff
 2.0  18    auto_equivalence     		cvff_auto
 1.0   1    hbond_definition			cvff
 2.0  18    quadratic_bond			cvff   cvff_auto
 2.0  18    quadratic_angle			cvff   cvff_auto
 2.0  18    torsion_1				cvff   cvff_auto
 2.0  18    out_of_plane			cvff   cvff_auto
 1.0   1    nonbond(12-6)			cvff



#atom_types	cvff


!Ver  Ref  Type    Mass      Element  Connections   Comment
!---- ---  ----  ----------  -------  -----------------------------------------
{atom_types}
#equivalence	cvff 


!		         	  Equivalences
!                 -----------------------------------------
!Ver  Ref   Type  NonB     Bond    Angle    Torsion    OOP
!---- ---   ----  ----     ----    -----    -------    ----
{equivalences}
#auto_equivalence	cvff_auto

!		         	  Equivalences
!                 -----------------------------------------                       
!Ver  Ref   Type  NonB Bond   Bond     Angle    Angle     Torsion   Torsion      OOP      OOP 
!                      Inct           End atom Apex atom End Atoms Center Atoms End Atom Center Atom
!---- ---   ----  ---- ------ ----  ---------- --------- --------- -----------  -------- ----------- 
{auto_equivalences}
#hbond_definition	cvff 

 1.0   1   distance      2.5000
 1.0   1   angle        90.0000
 1.0   1   donors        hn  h*  hspc   htip
 1.0   1   acceptors     o'  o   o*  ospc   otip

#quadratic_bond	cvff 


!Ver  Ref     I     J          R0         K2    
!---- ---    ----  ----     -------    -------- 
{bonds}
#quadratic_angle	cvff 


!Ver  Ref     I     J     K       Theta0         K2        
!---- ---    ----  ----  ----    --------     -------
{angles}
#torsion_1	cvff 


!Ver  Ref     I     J     K     L           Kphi        n           Phi0
!---- ---    ----  ----  ----  ----      -------      ------     -------
{torsions}
#out_of_plane	cvff 


!Ver  Ref     I     J     K     L           Kchi        n           Chi0
!---- ---    ----  ----  ----  ----      -------      ------     -------
{oops}
#nonbond(12-6)	cvff 

@type A-B
@combination geometric

!Ver  Ref     I           A               B
!---- ---    ----      ---------       ---------
{nonbonds}
'''

__all__ = ["CVFF_SKELETON"]
```

### 5.2 frc_input.py (Key Functions)

```python
def build_frc_input(
    termset: dict,
    parameterset: dict,
    *,
    use_placeholders: bool = True,
    msi2lmp_max_type_len: int = 5,
) -> FRCInput:
    """Convert USM TermSet + ParameterSet to FRCInput specification.
    
    Args:
        termset: Output of derive_termset_v0_1_2() with keys:
            - atom_types: list[str]
            - bond_types: list[[str, str]]
            - angle_types: list[[str, str, str]]
            - dihedral_types: list[[str, str, str, str]]
            - improper_types: list[[str, str, str, str]]
        parameterset: Output of derive_parameterset_v0_1_2() with key:
            - atom_types: dict[str, {mass_amu, lj_sigma, lj_epsilon, element}]
        use_placeholders: If True, fill missing bonded params with defaults.
            If False, raise error on missing params.
        msi2lmp_max_type_len: Max atom type name length (for alias expansion).
    
    Returns:
        FRCInput with all entries populated for .frc generation.
    
    Notes:
        - When use_placeholders=True, bonded params use tool-satisfying defaults
        - Nonbond params are always computed from LJ sigma/epsilon
        - Atom type aliases are expanded for msi2lmp compatibility
    """
    ...

def _expand_with_aliases(
    atom_types: list[str],
    max_len: int,
) -> tuple[list[str], dict[str, str]]:
    """Expand atom types with truncated aliases for msi2lmp.
    
    Returns:
        (expanded_types, alias_map) where alias_map[alias] = original
    """
    ...

def _get_placeholder_bond_params(el1: str, el2: str) -> tuple[float, float]:
    """Get (r0, k) placeholder values based on element types."""
    ...

def _get_placeholder_angle_params(center_el: str) -> tuple[float, float]:
    """Get (theta0, k) placeholder values based on center element."""
    ...

def _lj_sigma_eps_to_ab(sigma: float, epsilon: float) -> tuple[float, float]:
    """Convert LJ sigma/epsilon to A/B parameters."""
    ...

def _element_to_connects(element: str) -> int:
    """Get expected connection count for element."""
    ...
```

### 5.3 frc_writer.py (Key Functions)

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
    """
    ...

def _format_atom_type_entry(entry: AtomTypeEntry) -> str:
    """Format single #atom_types row."""
    ...

def _format_equivalence_entry(atom_type: str) -> str:
    """Format single #equivalence row (self-equivalence)."""
    ...

def _format_auto_equivalence_entry(atom_type: str) -> str:
    """Format single #auto_equivalence row (self-equivalence)."""
    ...

def _format_bond_entry(entry: BondEntry) -> str:
    """Format single #quadratic_bond row."""
    ...

def _format_angle_entry(entry: AngleEntry) -> str:
    """Format single #quadratic_angle row."""
    ...

def _format_torsion_entry(entry: TorsionEntry) -> str:
    """Format single #torsion_1 row."""
    ...

def _format_oop_entry(entry: OOPEntry) -> str:
    """Format single #out_of_plane row."""
    ...

def _format_nonbond_entry(entry: NonbondEntry) -> str:
    """Format single #nonbond(12-6) row."""
    ...
```

---

## 6) Deterministic Ordering Rules

For stable diffs and reproducible output:

1. **Atom types**: Sorted alphabetically
2. **Bond types**: Sorted by (type1, type2), with type1 <= type2
3. **Angle types**: Sorted by (type1, type2, type3), with type1 <= type3
4. **Dihedral types**: Sorted by (type1, type2, type3, type4), canonical order
5. **Improper types**: Sorted by (type1, type2, type3, type4), with peripherals sorted
6. **Nonbond types**: Same order as atom types

**Alias expansion**: For each type, emit both original and truncated alias (if different). Always emit original before alias, sorted together.

---

## 7) msi2lmp.exe Compatibility Notes

Critical requirements discovered during Phase 7-11 experiments:

1. **Column headers (`!` lines) are REQUIRED**: msi2lmp.exe uses them for field position detection
2. **`#define cvff` block is REQUIRED**: Defines section/function mapping
3. **Section order matters**: Follow the skeleton template order
4. **Atom type truncation**: msi2lmp.exe may truncate types to 5 chars internally
5. **Connections column**: Must match actual topology or use permissive value (0 or element-based)
6. **Empty bonded sections cause errors**: Must have entries or use `-ignore` flag

---

## 8) Test Strategy

### 8.1 Unit Tests

```python
# tests/test_frc_input.py

def test_build_frc_input_from_calf20_data():
    """Test conversion with real CALF-20 termset/parameterset."""
    
def test_placeholder_bond_params_h_bond():
    """H bonds get (340.0, 1.09)."""
    
def test_placeholder_bond_params_zn_bond():
    """Zn bonds get (150.0, 2.05)."""
    
def test_alias_expansion_zn_mof():
    """Zn_MOF expands to [Zn_MO, Zn_MOF]."""
    
def test_lj_conversion_roundtrip():
    """LJ sigma/eps → A/B is correct."""

# tests/test_frc_writer.py

def test_write_cvff_frc_deterministic():
    """Same input produces identical bytes."""
    
def test_write_cvff_frc_creates_file():
    """File is created at expected path."""
    
def test_format_atom_type_entry():
    """Atom type row format matches CVFF spec."""
    
def test_format_bond_entry():
    """Bond row format matches CVFF spec."""
```

### 8.2 Integration Tests

```python
# tests/integration/test_minimal_frc_msi2lmp.py

def test_minimal_frc_produces_calf20_data():
    """End-to-end: termset/parameterset → .frc → msi2lmp → .data"""
    
def test_minimal_frc_no_ignore_flag():
    """msi2lmp.exe succeeds WITHOUT -ignore flag."""
    
def test_minimal_frc_determinism_ab():
    """A/B run produces identical hashes."""
```

---

## 9) Migration Path

### 9.1 Phase 1: Create New Modules (Additive)

1. Create `cvff_skeleton.py` with template
2. Create `frc_input.py` with data model
3. Create `frc_writer.py` with formatting
4. Add unit tests

### 9.2 Phase 2: Add High-Level API

```python
# src/upm/src/upm/build/__init__.py

def build_minimal_cvff_frc(
    termset: dict,
    parameterset: dict,
    out_path: str | Path,
) -> str:
    """Build minimal CVFF .frc from USM-derived data.
    
    This is the RECOMMENDED API for new workflows.
    """
    frc_input = build_frc_input(termset, parameterset)
    return write_cvff_frc(frc_input, out_path)
```

### 9.3 Phase 3: Update NIST Workspace

1. Update `run.py` to use `build_minimal_cvff_frc()`
2. Remove `-ignore` flag from msi2lmp call
3. Verify CALF20.data production
4. Run A/B determinism test

### 9.4 Phase 4: Cleanup

1. Delete `cvff_embedded_base.py`
2. Replace `frc_from_scratch.py` with minimal shim (deprecation wrapper)
3. Update all imports across codebase
4. Archive old documentation

---

## 10) Subtask Breakdown

### Subtask 1: Create cvff_skeleton.py
- [ ] Create file with CVFF_SKELETON constant
- [ ] Validate skeleton structure against Phase 8 template
- [ ] Add module docstring and exports

### Subtask 2: Create frc_input.py
- [ ] Define all dataclasses (AtomTypeEntry, BondEntry, etc.)
- [ ] Implement build_frc_input() conversion function
- [ ] Implement placeholder parameter functions
- [ ] Implement alias expansion
- [ ] Implement LJ conversion

### Subtask 3: Create frc_writer.py
- [ ] Implement all format functions
- [ ] Implement write_cvff_frc() main function
- [ ] Ensure deterministic output (sorted, stable format)
- [ ] Add Unix line endings

### Subtask 4: Add High-Level API
- [ ] Add build_minimal_cvff_frc() to __init__.py
- [ ] Create integration test

### Subtask 5: Update NIST Workspace
- [ ] Modify run.py to use new builder
- [ ] Remove -ignore flag
- [ ] Verify CALF20.data production
- [ ] Verify A/B determinism

### Subtask 6: Cleanup Legacy Code
- [ ] Delete cvff_embedded_base.py
- [ ] Replace frc_from_scratch.py with shim
- [ ] Update imports across codebase

---

## 11) Completion Criteria

- [ ] New modules created (cvff_skeleton.py, frc_input.py, frc_writer.py)
- [ ] Each file < 500 lines
- [ ] All unit tests pass
- [ ] Integration test: CALF20.data produced WITHOUT -ignore flag
- [ ] Determinism verified with A/B test
- [ ] Legacy cvff_embedded_base.py deleted
- [ ] frc_from_scratch.py reduced to < 50 lines

---

## 12) Risk Mitigation

| Risk | Mitigation |
|------|------------|
| msi2lmp.exe rejects new .frc | Test incrementally against working M29 output |
| Connections mismatch causes SIGSEGV | Use element-based defaults from validated builds |
| Missing bonded types cause errors | Always expand with alias variants |
| Breaking existing workflows | Keep legacy shim for backwards compatibility |

---

*Plan created: 2025-12-21*
*Ready for orchestrator mode implementation*
