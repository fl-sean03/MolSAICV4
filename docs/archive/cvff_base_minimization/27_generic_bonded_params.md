# Implementation Plan: Generic Bonded Parameters Builder

**Status**: READY FOR IMPLEMENTATION
**Date**: 2025-12-21
**Target Files**: 
- `src/upm/src/upm/build/frc_from_scratch.py`
- `src/upm/tests/test_build_frc_generic_bonded.py`

## 1) Executive Summary

This plan implements a builder that generates CVFF .frc files with **generic bonded parameters** for all bonded types in a termset, enabling msi2lmp.exe to run **without** the `-ignore` flag.

### Problem Statement
- M29 preset (120 lines) requires `-ignore` flag because bonded sections are empty
- Root cause: M29's `max_*=-1` removes all base entries, and CALF20's parameterset only has nonbond parameters
- Error without `-ignore`: `Unable to find bond data for Zn_MO N_MOF`

### Key Discovery
The existing [`build_frc_cvff_from_skeleton()`](src/upm/src/upm/build/frc_from_scratch.py:3691) function already generates bonded entries from termset with placeholder parameters. However, the M29 validation file was generated with a different builder that doesn't use termset bonded types.

### Solution
Create a cleaner abstraction:
1. `generate_generic_bonded_params(termset, parameterset)` - standalone function for bonded param generation
2. `build_frc_cvff_with_generic_bonded()` - builder using skeleton + generic bonded params

## 2) Analysis of Existing Code

### 2.1 CVFF Section Formats (from skeleton template)

```
#quadratic_bond cvff
!Ver  Ref     I     J          R0         K2
 2.0  18    C_MOF  H_MOF   1.090000   340.000000

#quadratic_angle cvff
!Ver  Ref     I     J     K       Theta0         K2
 2.0  18    H_MOF  C_MOF  H_MOF   109.500000   44.400000

#torsion_1 cvff
!Ver  Ref     I     J     K     L           Kphi        n           Phi0
 2.0  18    C_MOF  N_MOF  C_MOF  H_MOF   0.000000   1   0.000000

#out_of_plane cvff
!Ver  Ref     I     J     K     L           Kchi        n           Chi0
 2.0  18    C_MOF  N_MOF  C_MOF  Zn_MOF   0.000000   0   0.000000
```

### 2.2 Existing Placeholder Functions

Located in [`frc_from_scratch.py`](src/upm/src/upm/build/frc_from_scratch.py:56):

```python
def _placeholder_bond_params(*, t1_el: str, t2_el: str) -> tuple[float, float]:
    # Returns (k, r0) based on element types
    # H-bonds: (340.0, 1.09)
    # Zn-bonds: (150.0, 2.05)
    # Default: (300.0, 1.50)

def _placeholder_angle_params(*, center_el: str) -> tuple[float, float]:
    # Returns (theta0, k) based on center element
    # Zn: (90.0, 30.0)
    # O: (109.5, 50.0)
    # N: (120.0, 50.0)
    # C: (109.5, 44.4)
    # Default: (120.0, 50.0)
```

### 2.3 CALF20 Termset Structure

```json
{
  "atom_types": ["C_MOF", "H_MOF", "N_MOF", "O_MOF", "Zn_MOF"],
  "bond_types": [["C_MOF", "H_MOF"], ["C_MOF", "N_MOF"], ...],
  "angle_types": [["C_MOF", "N_MOF", "C_MOF"], ...],
  "dihedral_types": [["C_MOF", "N_MOF", "C_MOF", "H_MOF"], ...],
  "improper_types": [["C_MOF", "N_MOF", "C_MOF", "Zn_MOF"], ...]
}
```

### 2.4 CALF20 Parameterset Structure

```json
{
  "atom_types": {
    "C_MOF": {"element": "C", "mass_amu": 12.011, "lj_sigma_angstrom": 3.43, "lj_epsilon_kcal_mol": 0.105},
    "Zn_MOF": {"element": "Zn", "mass_amu": 65.38, ...}
  }
}
```

## 3) Detailed Implementation Plan

### 3.1 New Function: `generate_generic_bonded_params()`

**Location**: [`src/upm/src/upm/build/frc_from_scratch.py`](src/upm/src/upm/build/frc_from_scratch.py)

**Signature**:
```python
def generate_generic_bonded_params(
    termset: dict[str, Any],
    parameterset: dict[str, Any],
    *,
    msi2lmp_max_atom_type_len: int = 5,
) -> dict[str, list[str]]:
    """Generate CVFF-formatted bonded parameter lines from termset.
    
    This function extracts bonded type information from the termset and
    generates .frc-formatted entry lines with generic/placeholder parameters.
    The element information from parameterset is used to select appropriate
    parameter values.
    
    Args:
        termset: Output of derive_termset_v0_1_2() with keys:
            - bond_types: list of [t1, t2] pairs
            - angle_types: list of [t1, t2, t3] triplets
            - dihedral_types: list of [t1, t2, t3, t4] quadruplets
            - improper_types: list of [t1, t2, t3, t4] quadruplets
        parameterset: Output of derive_parameterset_v0_1_2() with key:
            - atom_types: dict mapping type name to {"element": ..., ...}
        msi2lmp_max_atom_type_len: Maximum atom type name length for
            msi2lmp.exe compatibility. Types longer than this get
            truncated alias variants emitted.
    
    Returns:
        Dict with keys:
            - bond_entries: list of formatted #quadratic_bond lines
            - angle_entries: list of formatted #quadratic_angle lines
            - torsion_entries: list of formatted #torsion_1 lines
            - oop_entries: list of formatted #out_of_plane lines
        
    Example:
        >>> params = generate_generic_bonded_params(termset, parameterset)
        >>> params["bond_entries"]
        [" 2.0  18    C_MOF  H_MOF   1.090000   340.000000", ...]
    """
```

**Implementation Details**:
1. Extract atom type to element mapping from parameterset
2. Build alias map for msi2lmp truncation compatibility (reuse `_build_skeleton_alias_map`)
3. Expand bonded terms with alias variants (both directions for symmetry)
4. Generate formatted entries using existing `_format_skeleton_*_entry()` functions
5. Use existing `_placeholder_bond_params()` and `_placeholder_angle_params()` for values

### 3.2 New Builder: `build_frc_cvff_with_generic_bonded()`

**Location**: [`src/upm/src/upm/build/frc_from_scratch.py`](src/upm/src/upm/build/frc_from_scratch.py)

**Signature**:
```python
def build_frc_cvff_with_generic_bonded(
    termset: dict[str, Any],
    parameterset: dict[str, Any],
    *,
    out_path: str | Path,
    msi2lmp_max_atom_type_len: int = 5,
) -> str:
    """Build minimal CVFF .frc with generic bonded params for all termset types.
    
    This builder produces a compact .frc file (~150-200 lines) that:
    1. Uses the M29/skeleton base structure for minimal overhead
    2. Contains custom atom types from parameterset with LJ parameters
    3. Contains generic bonded parameters for ALL bonded types in termset
    4. Works with msi2lmp.exe WITHOUT the -ignore flag
    
    This is the recommended builder for workflows where:
    - Bonded parameters are not critical (e.g., nonbond-only analysis)
    - Maximum file size reduction is desired
    - -ignore flag usage should be avoided for cleaner workflows
    
    Args:
        termset: Output of derive_termset_v0_1_2() containing bonded types.
        parameterset: Output of derive_parameterset_v0_1_2() containing
            atom type parameters (mass, LJ sigma/epsilon, element).
        out_path: Where to write the .frc file.
        msi2lmp_max_atom_type_len: Maximum atom type name length (default 5).
    
    Returns:
        The output path as a string.
    
    Raises:
        MissingTypesError: If parameterset is missing entries for termset types.
    
    Example:
        >>> build_frc_cvff_with_generic_bonded(
        ...     termset=termset_data,
        ...     parameterset=parameterset_data,
        ...     out_path="cvff_generic_bonded.frc"
        ... )
        'cvff_generic_bonded.frc'
    
    Note:
        The generic bonded parameters are tool-satisfying placeholders,
        not physically accurate. They exist to allow msi2lmp.exe to
        complete without errors. For production simulations requiring
        accurate bonded interactions, use proper force field parameters.
    """
```

**Implementation Details**:
1. Validate termset types exist in parameterset (reuse validation logic)
2. Call `generate_generic_bonded_params()` to get bonded entry lines
3. Generate atom_types, equivalence, auto_equivalence, nonbond entries (reuse existing logic)
4. Populate CVFF_MINIMAL_SKELETON template
5. Write to out_path

### 3.3 Relationship to Existing Functions

```
┌─────────────────────────────────────────────────────────────────┐
│                     Existing Functions                          │
├─────────────────────────────────────────────────────────────────┤
│  _placeholder_bond_params()     ─────────────────────┐          │
│  _placeholder_angle_params()    ─────────────────────┤          │
│  _format_skeleton_bond_entry()  ─────────────────────┤          │
│  _format_skeleton_angle_entry() ─────────────────────┤          │
│  _format_skeleton_torsion_entry() ───────────────────┤          │
│  _format_skeleton_oop_entry()   ─────────────────────┤          │
│  _build_skeleton_alias_map()    ─────────────────────┤          │
│  CVFF_MINIMAL_SKELETON          ─────────────────────┤          │
└──────────────────────────────────────────────────────┼──────────┘
                                                       │
                                                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                     NEW Functions                               │
├─────────────────────────────────────────────────────────────────┤
│  generate_generic_bonded_params()                               │
│      ├── Uses all the existing helper functions                 │
│      ├── Returns dict with bond/angle/torsion/oop entries       │
│      └── Handles alias expansion for msi2lmp compatibility      │
│                                                                 │
│  build_frc_cvff_with_generic_bonded()                           │
│      ├── Calls generate_generic_bonded_params()                 │
│      ├── Generates atom_types, equivalence, nonbond entries     │
│      ├── Populates CVFF_MINIMAL_SKELETON template               │
│      └── Writes output file                                     │
└─────────────────────────────────────────────────────────────────┘
```

### 3.4 Unit Tests

**Location**: [`src/upm/tests/test_build_frc_generic_bonded.py`](src/upm/tests/test_build_frc_generic_bonded.py)

```python
# Test structure following existing test patterns

def test_generate_generic_bonded_params_returns_expected_keys():
    """Test that generate_generic_bonded_params returns all required keys."""

def test_generate_generic_bonded_params_bond_format():
    """Test bond entry format matches CVFF spec."""

def test_generate_generic_bonded_params_angle_format():
    """Test angle entry format matches CVFF spec."""

def test_generate_generic_bonded_params_torsion_format():
    """Test torsion entry format matches CVFF spec."""

def test_generate_generic_bonded_params_oop_format():
    """Test out-of-plane entry format matches CVFF spec."""

def test_generate_generic_bonded_params_alias_expansion():
    """Test that Zn_MOF generates both Zn_MOF and Zn_MO variants."""

def test_build_frc_cvff_with_generic_bonded_creates_file():
    """Test that builder creates output file."""

def test_build_frc_cvff_with_generic_bonded_is_deterministic():
    """Test byte-determinism across multiple runs."""

def test_build_frc_cvff_with_generic_bonded_includes_all_sections():
    """Test output includes all required CVFF sections."""

def test_build_frc_cvff_with_generic_bonded_calf20_integration():
    """Test with real CALF20 termset/parameterset data."""

def test_build_frc_cvff_with_generic_bonded_bonded_entries_not_empty():
    """Test that bonded sections contain actual data entries."""
```

### 3.5 Expected Output Size

| Component | Lines |
|-----------|-------|
| Skeleton metadata + headers | ~65 |
| Atom types (6 with alias) | 6 |
| Equivalence (6) | 6 |
| Auto-equivalence (6) | 6 |
| Bonds (6 types × ~4 variants) | ~24 |
| Angles (11 types × ~4 variants) | ~44 |
| Dihedrals (16 types × ~8 variants) | ~128 |
| OOP (6 types × ~24 variants) | ~144 |
| Nonbond (6) | 6 |
| **Total** | **~430** |

Note: The variant expansion for symmetric entries may increase this. Deduplication should reduce it.

## 4) msi2lmp.exe Validation Plan

### 4.1 Generate Test .frc File

```bash
cd workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/outputs

python -c "
import json
from pathlib import Path
from upm.build.frc_from_scratch import build_frc_cvff_with_generic_bonded

termset = json.loads(Path('termset.json').read_text())
parameterset = json.loads(Path('parameterset.json').read_text())

build_frc_cvff_with_generic_bonded(
    termset, parameterset,
    out_path='frc_files/cvff_generic_bonded.frc'
)
print('Generated cvff_generic_bonded.frc')
"
```

### 4.2 Run msi2lmp.exe WITHOUT -ignore

```bash
cd workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/outputs/msi2lmp_run

# Copy input files
cp ../frc_files/CALF20.car .
cp ../frc_files/CALF20.mdf .

# Run WITHOUT -ignore flag (this is the key test!)
timeout 30s /home/sf2/LabWork/software/msi2lmp.exe CALF20 \
    -class I -frc ../frc_files/cvff_generic_bonded.frc \
    > generic_bonded_stdout.txt 2> generic_bonded_stderr.txt

echo "Exit code: $?"
ls -la CALF20.data 2>/dev/null || echo "CALF20.data NOT CREATED"
```

### 4.3 Success Criteria

| Criterion | Expected |
|-----------|----------|
| Exit code | 0 |
| CALF20.data | Created |
| -ignore flag | NOT USED |
| Output file size | ~150-430 lines |
| Stderr | No "Unable to find bond data" errors |

## 5) Code Integration

### 5.1 Update `__all__` Export

Add to [`frc_from_scratch.py`](src/upm/src/upm/build/frc_from_scratch.py:3922) `__all__`:

```python
__all__ = [
    # ... existing exports ...
    # Phase 11: Generic bonded parameters
    "generate_generic_bonded_params",
    "build_frc_cvff_with_generic_bonded",
]
```

### 5.2 Test Import Path

```python
from upm.build.frc_from_scratch import (
    generate_generic_bonded_params,
    build_frc_cvff_with_generic_bonded,
)
```

## 6) Scope Guardrails

### DO
- Reuse existing helper functions (`_placeholder_*`, `_format_skeleton_*`, etc.)
- Follow existing test patterns from `test_build_frc_from_scratch_cvff_minimal_bonded.py`
- Add new functions to existing file `frc_from_scratch.py`
- Test with real CALF20 data

### DO NOT
- Modify USM termset/parameterset code
- Modify existing builders (create new ones)
- Change the CVFF_MINIMAL_SKELETON template
- Change existing placeholder parameter values

## 7) Completion Checklist

- [ ] `generate_generic_bonded_params()` implemented
- [ ] `build_frc_cvff_with_generic_bonded()` implemented
- [ ] Unit tests in `test_build_frc_generic_bonded.py`
- [ ] All tests pass
- [ ] msi2lmp.exe validation (exit code 0, CALF20.data created)
- [ ] `-ignore` flag NOT required
- [ ] `__all__` updated with new exports
