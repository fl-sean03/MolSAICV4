# TermSet Derivation and FRC Building Pipeline

This document provides comprehensive implementation details for the automatic derivation of bonded topology terms (bonds, angles, dihedrals, impropers) from molecular structure files and the subsequent generation of force field (`.frc`) files for use with msi2lmp.exe.

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Step 1: Parsing Molecular Structure Files](#step-1-parsing-molecular-structure-files)
4. [Step 2: TermSet Derivation](#step-2-termset-derivation)
5. [Step 3: ParameterSet Definition](#step-3-parameterset-definition)
6. [Step 4: Generic Bonded Parameter Generation](#step-4-generic-bonded-parameter-generation)
7. [Step 5: FRC File Construction](#step-5-frc-file-construction)
8. [Complete Workflow Example](#complete-workflow-example)
9. [Extension Points](#extension-points)
10. [API Reference](#api-reference)

---

## Overview

The MOLSAIC pipeline automatically derives all bonded interaction types needed for molecular dynamics simulations directly from molecular connectivity information. This eliminates the need for manual force field assignment when:

1. You have structure files (MDF/CAR) with explicit connectivity
2. You have nonbonded parameters (LJ σ/ε, masses) for each atom type
3. You need to generate a LAMMPS `.data` file via msi2lmp.exe

The pipeline produces **generic placeholder parameters** for bonded terms, which:
- Satisfy msi2lmp.exe's requirement for complete parameter coverage
- Enable structural validation and format conversion
- Are NOT physically accurate (must be replaced for production MD)

### When to Use This Pipeline

| Use Case | Appropriate |
|----------|-------------|
| Generating LAMMPS input for structural analysis | ✅ |
| Testing msi2lmp workflow integration | ✅ |
| Quick visualization of MOF/framework structures | ✅ |
| Production MD with accurate dynamics | ❌ (replace params) |
| Free energy calculations | ❌ (need fitted params) |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                        Input Files                                    │
├────────────────────┬─────────────────────┬───────────────────────────┤
│     CAR File       │      MDF File       │    ParameterSet JSON      │
│  (coordinates,     │  (connectivity,     │  (mass, LJ σ/ε,           │
│   cell params)     │   atom types)       │   element per type)       │
└────────────────────┴─────────────────────┴───────────────────────────┘
           │                    │                        │
           ▼                    ▼                        │
    ┌──────────────────────────────────────┐             │
    │         USM Structure                 │             │
    │  (Unified Structural Model)           │             │
    │  - atoms DataFrame                    │             │
    │  - bonds DataFrame                    │             │
    │  - cell parameters                    │             │
    └──────────────────────────────────────┘             │
                       │                                  │
                       ▼                                  │
    ┌──────────────────────────────────────┐             │
    │      derive_termset_v0_1_2()         │             │
    │                                       │             │
    │  Outputs:                             │             │
    │  - atom_types: [A, B, C, ...]        │             │
    │  - bond_types: [[A,B], [B,C], ...]   │             │
    │  - angle_types: [[A,B,C], ...]       │             │
    │  - dihedral_types: [[A,B,C,D], ...]  │             │
    │  - improper_types: [[A,B,C,D], ...]  │             │
    └──────────────────────────────────────┘             │
                       │                                  │
                       ▼                                  ▼
    ┌────────────────────────────────────────────────────────┐
    │        generate_generic_bonded_params()                 │
    │                                                         │
    │  For each bonded term type, generate placeholder        │
    │  parameters based on element types:                     │
    │  - Bonds: k, r0 from element pair                       │
    │  - Angles: θ0, k from center element                    │
    │  - Dihedrals: Kphi=0, n=1, phi0=0                       │
    │  - Impropers: Kchi=0.1, n=2, chi0=180                   │
    └────────────────────────────────────────────────────────┘
                       │
                       ▼
    ┌────────────────────────────────────────────────────────┐
    │     build_frc_cvff_with_generic_bonded()               │
    │                                                         │
    │  Assembles complete CVFF .frc file with:               │
    │  - Header and #define blocks                           │
    │  - #atom_types section                                  │
    │  - #equivalence section                                 │
    │  - #auto_equivalence section                            │
    │  - #quadratic_bond section                              │
    │  - #quadratic_angle section                             │
    │  - #torsion_1 section                                   │
    │  - #out_of_plane section                                │
    │  - #nonbond(12-6) section                               │
    │  - #bond_increments section                             │
    └────────────────────────────────────────────────────────┘
                       │
                       ▼
    ┌──────────────────────────────────────┐
    │          Output: .frc File            │
    │  (CVFF-format force field file)       │
    └──────────────────────────────────────┘
                       │
                       ▼
    ┌──────────────────────────────────────┐
    │           msi2lmp.exe                 │
    │  Input: .car, .mdf, .frc              │
    │  Output: LAMMPS .data file            │
    └──────────────────────────────────────┘
```

---

## Step 1: Parsing Molecular Structure Files

### MDF File Structure

The MDF (Molecular Definition Format) file contains atom definitions and connectivity:

```
!BIOSYM molecular_data 4

#topology

@column 1 element
@column 2 atom_type
@column 3 charge_group
...
@column 12 connections

@molecule molecule_name

XXXX_1:Atom1    C  C_type  ?  0  0  0.123  0 0 8  1.0  0.02  Atom2 Atom3 Atom4
XXXX_1:Atom2    N  N_type  ?  0  0 -0.456  0 0 8  1.0  0.03  Atom1 Atom5
...

#end
```

**Key columns for termset derivation:**
- `atom_type` (column 2): The force field type label (e.g., `C_MOF`, `N_MOF`)
- `connections` (column 12): Space-separated list of bonded atom names

### CAR File Structure

The CAR (Cartesian coordinates) file contains atomic positions and cell parameters:

```
!BIOSYM archive 3
PBC=ON
Materials Studio Generated CAR File
!DATE ...
PBC   a   b   c   alpha   beta   gamma   (P1)
Atom1    x1    y1    z1   MOL  1   atom_type  element  charge
Atom2    x2    y2    z2   MOL  1   atom_type  element  charge
...
end
end
```

### USM Structure Creation

The parsing functions create a unified structure model:

```python
from usm.io import load_car, load_mdf
from usm.ops.compose import compose_on_keys

# Load and merge CAR + MDF
usm_car = load_car("structure.car")
usm_mdf = load_mdf("structure.mdf")
usm = compose_on_keys(usm_car, usm_mdf)

# Result: usm.atoms DataFrame with columns:
#   name, element, atom_type, x, y, z, charge, aid, ...
# Result: usm.bonds DataFrame with columns:
#   a1, a2 (atom indices), ix, iy, iz (PBC image flags)
```

---

## Step 2: TermSet Derivation

### Overview

The TermSet is a JSON-serializable dictionary containing all unique bonded interaction types present in the molecular structure. It is generated by the `derive_termset_v0_1_2()` function in `src/usm/ops/termset.py`.

### Algorithm Details

#### 2.1 Atom Type Extraction

```python
def _extract_atom_types_by_aid(structure):
    """Extract atom types indexed by atom ID (aid).
    
    Returns a list where index i contains the atom_type of atom with aid=i.
    This ensures consistent indexing for bond/angle/dihedral enumeration.
    """
```

#### 2.2 Bond Type Enumeration

For each bond `(a1, a2)` in the bonds table:
1. Look up `atom_type[a1]` and `atom_type[a2]`
2. Canonicalize: sort alphabetically so `(A, B)` and `(B, A)` → `(A, B)`
3. Add to set of unique bond types

```python
def _canonicalize_bond_key(t1: str, t2: str) -> tuple[str, str]:
    """Canonical bond ordering: alphabetically smaller type first."""
    return (t1, t2) if t1 <= t2 else (t2, t1)
```

**Example:**
```
Bonds in structure: Zn-N, N-Zn, C-H, H-C, N-C
Canonicalized: (C, H), (C, N), (N, Zn)
```

#### 2.3 Angle Type Enumeration

For each atom `j` with 2+ neighbors:
1. Enumerate all pairs `(i, k)` of neighbors where `i < k`
2. Form angle type `(atom_type[i], atom_type[j], atom_type[k])`
3. Canonicalize: ensure first endpoint ≤ last endpoint alphabetically

```python
def _canonicalize_angle_key(t1: str, t2: str, t3: str) -> tuple[str, str, str]:
    """Canonical angle ordering: center fixed, endpoints sorted."""
    return (t1, t2, t3) if t1 <= t3 else (t3, t2, t1)
```

**Example:**
```
Atom j = C connected to [H, N, O]
Angles: H-C-N, H-C-O, N-C-O
After canonicalization: (H, C, N), (H, C, O), (N, C, O)
```

#### 2.4 Dihedral Type Enumeration

For each bond `(j, k)`:
1. Enumerate all `i` neighbors of `j` (excluding `k`)
2. Enumerate all `l` neighbors of `k` (excluding `j`)
3. Form dihedral `(atom_type[i], atom_type[j], atom_type[k], atom_type[l])`
4. Canonicalize: compare forward vs reverse, take lexicographically smaller

```python
def _canonicalize_dihedral_key(t1, t2, t3, t4) -> tuple[str, str, str, str]:
    """Canonical dihedral: forward vs reverse comparison."""
    fwd = (t1, t2, t3, t4)
    rev = (t4, t3, t2, t1)
    return fwd if fwd <= rev else rev
```

**Example:**
```
Bond j-k = N-C with neighbors:
  j(N) neighbors: [Zn, C']
  k(C) neighbors: [H, N']
Dihedrals: Zn-N-C-H, Zn-N-C-N', C'-N-C-H, C'-N-C-N'
```

#### 2.5 Improper Type Enumeration

For each atom `j` with 3+ neighbors:
1. Take all combinations of 3 neighbors: `(i, k, l)` where `i < k < l`
2. Form improper `(atom_type[i], atom_type[j], atom_type[k], atom_type[l])`
3. Canonicalize: sort peripheral atoms, keep center in position 2

```python
def _canonicalize_improper_key(t1, t2, t3, t4) -> tuple[str, str, str, str]:
    """Canonical improper: center at position 2, peripherals sorted."""
    p1, p2, p3 = sorted([t1, t3, t4])
    return (p1, t2, p2, p3)
```

**Example:**
```
Atom j = Zn connected to [N1, N2, N3, O1, O2]
Impropers: (N, Zn, N, N), (N, Zn, N, O), (N, Zn, O, O), ...
```

### TermSet JSON Schema

```json
{
  "schema": "molsaic.termset.v0.1.2",
  "atom_types": ["C_MOF", "H_MOF", "N_MOF", "O_MOF", "Zn_MOF"],
  "bond_types": [
    ["C_MOF", "H_MOF"],
    ["C_MOF", "N_MOF"],
    ["C_MOF", "O_MOF"],
    ["N_MOF", "N_MOF"],
    ["N_MOF", "Zn_MOF"],
    ["O_MOF", "Zn_MOF"]
  ],
  "angle_types": [
    ["C_MOF", "N_MOF", "C_MOF"],
    ["C_MOF", "N_MOF", "N_MOF"],
    ...
  ],
  "dihedral_types": [...],
  "improper_types": [...],
  "counts": {
    "bond_types": {"C_MOF|H_MOF": 2, ...},
    "angle_types": {...},
    "dihedral_types": {...},
    "improper_types": {...}
  }
}
```

The `counts` section tracks how many instances of each type exist in the structure (useful for validation).

---

## Step 3: ParameterSet Definition

The ParameterSet is **critical** to the pipeline - it provides the physical parameters that the TermSet alone cannot supply. While the TermSet defines *what* bonded interactions exist, the ParameterSet defines *how* atoms should be treated in the force field.

### What ParameterSet Provides

| Data | Used For | FRC Section |
|------|----------|-------------|
| `element` | Placeholder bonded params (k, r0, θ0) | - |
| `mass_amu` | Atom type mass definition | `#atom_types` |
| `lj_sigma_angstrom` | Nonbonded LJ interactions | `#nonbond(12-6)` |
| `lj_epsilon_kcal_mol` | Nonbonded LJ interactions | `#nonbond(12-6)` |

### How ParameterSet Is Used in FRC Generation

#### 1. Element Information → Bonded Parameter Selection

The `element` field determines which placeholder parameters are assigned:

```python
# In placeholder_bond_params():
#   Element "H" → (k=340.0, r0=1.09) for X-H bonds
#   Element "Zn" → (k=150.0, r0=2.05) for Zn-X coordination
#   Default → (k=300.0, r0=1.50)

# In placeholder_angle_params():
#   Center "Zn" → (θ0=90.0, k=50.0)
#   Center "N" → (θ0=120.0, k=50.0)
#   Center "C" → (θ0=109.5, k=50.0)
```

#### 2. Mass → Atom Types Section

```
#atom_types    cvff

!Ver  Ref  Type    Mass      Element  Connections
 2.0  18    C_MOF  12.011000   C   4     ← mass_amu from ParameterSet
 2.0  18    H_MOF  1.008000    H   1
 2.0  18    Zn_MOF 65.379997   Zn  6
```

#### 3. LJ σ/ε → Nonbond Section

```python
# Conversion: σ/ε → A/B coefficients
# A = 4ε·σ¹², B = 4ε·σ⁶

# Example for C_MOF (σ=3.431, ε=0.105):
a = 4 * 0.105 * (3.431**12)  # = 1117239.14
b = 4 * 0.105 * (3.431**6)   # = 685.01
```

```
#nonbond(12-6)    cvff

@type A-B
@combination geometric

!Ver  Ref     I           A             B
 2.0  18    C_MOF    1117239.1430      685.01126   ← Computed from σ/ε
 2.0  18    Zn_MOF      24552.2675      110.35363
```

### ParameterSet JSON Schema

```json
{
  "schema": "upm.parameterset.v0.1.2",
  "atom_types": {
    "C_MOF": {
      "element": "C",
      "mass_amu": 12.011,
      "lj_sigma_angstrom": 3.431,
      "lj_epsilon_kcal_mol": 0.105
    },
    "H_MOF": {
      "element": "H",
      "mass_amu": 1.008,
      "lj_sigma_angstrom": 2.571,
      "lj_epsilon_kcal_mol": 0.044
    },
    "N_MOF": {
      "element": "N",
      "mass_amu": 14.007,
      "lj_sigma_angstrom": 3.261,
      "lj_epsilon_kcal_mol": 0.069
    },
    "O_MOF": {
      "element": "O",
      "mass_amu": 15.999,
      "lj_sigma_angstrom": 3.118,
      "lj_epsilon_kcal_mol": 0.060
    },
    "Zn_MOF": {
      "element": "Zn",
      "mass_amu": 65.380,
      "lj_sigma_angstrom": 2.462,
      "lj_epsilon_kcal_mol": 0.124
    }
  }
}
```

### Required Fields

| Field | Type | Description | Source |
|-------|------|-------------|--------|
| `element` | string | Chemical element symbol (C, H, N, O, Zn, etc.) | Periodic table lookup or manual |
| `mass_amu` | float | Atomic mass in unified atomic mass units | Standard atomic weights |
| `lj_sigma_angstrom` | float | LJ σ parameter in Ångströms | Force field database (UFF, DREIDING, etc.) |
| `lj_epsilon_kcal_mol` | float | LJ ε parameter in kcal/mol | Force field database |

### Sources for LJ Parameter Values

#### 1. Universal Force Field (UFF)

UFF provides LJ parameters for nearly all elements:

```python
# UFF parameters for common elements
UFF_PARAMS = {
    "C": {"sigma": 3.431, "epsilon": 0.105},
    "H": {"sigma": 2.571, "epsilon": 0.044},
    "N": {"sigma": 3.261, "epsilon": 0.069},
    "O": {"sigma": 3.118, "epsilon": 0.060},
    "Zn": {"sigma": 2.462, "epsilon": 0.124},
}
```

#### 2. DREIDING Force Field

Alternative parameters often used for organic/MOF systems:

```python
DREIDING_PARAMS = {
    "C": {"sigma": 3.473, "epsilon": 0.095},
    "H": {"sigma": 3.195, "epsilon": 0.016},
    "N": {"sigma": 3.263, "epsilon": 0.077},
    "O": {"sigma": 3.033, "epsilon": 0.096},
}
```

#### 3. Literature/Custom

For novel systems, parameters may come from:
- DFT fitting
- Experimental data fitting
- Hybrid approaches (e.g., interface force field - IFF)

### Creating ParameterSet

#### Option A: Manual Creation

```python
import json

parameterset = {
    "schema": "upm.parameterset.v0.1.2",
    "atom_types": {
        "C_MOF": {
            "element": "C",
            "mass_amu": 12.011,
            "lj_sigma_angstrom": 3.431,
            "lj_epsilon_kcal_mol": 0.105
        },
        # ... more types
    }
}

with open("parameterset.json", "w") as f:
    json.dump(parameterset, f, indent=2)
```

#### Option B: Derive from Structure

If the USM structure already has parameter columns:

```python
from usm.ops.parameterset import export_parameterset_json

# Assumes USM has columns: atom_type, element, mass_amu,
#   lj_sigma_angstrom, lj_epsilon_kcal_mol
export_parameterset_json(usm, "outputs/parameterset.json")
```

#### Option C: Apply External Parameters to Structure

```python
def apply_parameterset_to_usm(usm, parameterset):
    """Enrich USM atoms with parameters from a ParameterSet."""
    ps_map = parameterset.get("atom_types", {})
    
    for col in ["element", "mass_amu", "lj_sigma_angstrom", "lj_epsilon_kcal_mol"]:
        if col not in usm.atoms.columns:
            usm.atoms[col] = None
    
    for at, rec in ps_map.items():
        mask = usm.atoms["atom_type"] == at
        for col in rec:
            usm.atoms.loc[mask, col] = rec[col]
    
    return usm
```

### Validation: TermSet ↔ ParameterSet Coverage

The builder validates that every atom type in the TermSet has a corresponding entry in the ParameterSet:

```python
def build_frc_cvff_with_generic_bonded(termset, parameterset, *, out_path):
    ts_types = list(termset.get("atom_types") or [])
    ps_map = dict(parameterset.get("atom_types") or {})
    
    # Check coverage
    missing = sorted([t for t in ts_types if t not in ps_map])
    if missing:
        raise MissingTypesError(tuple(missing))
    
    # Proceed with FRC generation...
```

**Error example:**
```
MissingTypesError: missing ParameterSet entries for atom_types: ['Cu_MOF', 'Fe_MOF']
```

---

## Step 4: Generic Bonded Parameter Generation

The `generate_generic_bonded_params()` function produces placeholder force field parameters that satisfy msi2lmp.exe but are not physically meaningful.

### Bond Parameters

```python
def placeholder_bond_params(*, t1_el: str, t2_el: str) -> tuple[float, float]:
    """Return (k_bond, r0) based on element types."""
    els = {t1_el.upper(), t2_el.upper()}
    
    if "H" in els:
        # X-H bonds: stiff spring, short distance
        return (340.0, 1.09)  # k in kcal/mol/Å², r0 in Å
    
    if "ZN" in els:
        # Metal coordination: softer spring, longer distance
        return (150.0, 2.05)
    
    # Generic organic bonds
    return (300.0, 1.50)
```

### Angle Parameters

```python
def placeholder_angle_params(*, center_el: str) -> tuple[float, float]:
    """Return (theta0_degrees, k_angle) based on center element."""
    el = center_el.upper()
    
    if el == "ZN":
        # Octahedral/tetrahedral metal center
        return (90.0, 50.0)  # 90° for square planar
    
    if el == "O":
        # Tetrahedral oxygen (water-like)
        return (109.5, 50.0)
    
    if el == "N":
        # Trigonal planar nitrogen (aromatic)
        return (120.0, 50.0)
    
    if el == "C":
        # Tetrahedral carbon (sp³)
        return (109.5, 50.0)
    
    return (120.0, 50.0)  # Default
```

### Dihedral Parameters

All dihedrals use zero-barrier placeholders:

```python
# Format: Kphi, n, Phi0
# Kphi = 0.0: no torsional barrier
# n = 1: periodicity
# Phi0 = 0.0: phase
dihedral_params = (0.0, 1, 0.0)
```

### Improper (Out-of-Plane) Parameters

Small restoring force to maintain planarity:

```python
# Format: Kchi, n, Chi0
# Kchi = 0.1: small force constant
# n = 2: periodicity
# Chi0 = 180.0: equilibrium at planar
improper_params = (0.1, 2, 180.0)
```

### Output Format

The function returns formatted `.frc` entry lines:

```python
result = generate_generic_bonded_params(termset, parameterset)

# result["bond_entries"]:
#   " 2.0  18    C_MOF  H_MOF   1.090000   340.000000"
#   " 2.0  18    N_MOF  Zn_MOF   2.050000   150.000000"

# result["angle_entries"]:
#   " 2.0  18    C_MOF  N_MOF  C_MOF   120.000000   50.000000"

# result["torsion_entries"]:
#   " 2.0  18    C_MOF  N_MOF  C_MOF  H_MOF   0.000000   1   0.000000"

# result["oop_entries"]:
#   " 2.0  18    C_MOF  N_MOF  C_MOF  Zn_MOF   0.100000   2   180.000000"
```

---

## Step 5: FRC File Construction

The `build_frc_cvff_with_generic_bonded()` function assembles the complete `.frc` file using a template and the generated parameter entries.

### FRC File Structure

```
!BIOSYM forcefield          1

#define cvff_nocross_nomorse
> Description line

!Ver  Ref  Function          Label
...

#atom_types    cvff

!Ver  Ref  Type    Mass      Element  Connections   Comment
 2.0  18    C_MOF  12.011000   C   4
 2.0  18    H_MOF  1.008000   H   1
...

#equivalence   cvff

!Ver  Ref  Type  NonB   Bond   Angle  Torsion  OOP
 1.0   1    C_MOF  C_MOF  C_MOF  C_MOF  C_MOF  C_MOF
...

#auto_equivalence   cvff_auto
...

#quadratic_bond    cvff

!Ver  Ref     I     J          R0         K2
 2.0  18    C_MOF  H_MOF   1.090000   340.000000
 2.0  18    N_MOF  Zn_MOF   2.050000   150.000000
...

#quadratic_angle   cvff

!Ver  Ref     I     J     K       Theta0         K2
 2.0  18    C_MOF  N_MOF  C_MOF   120.000000   50.000000
...

#torsion_1   cvff

!Ver  Ref     I     J     K     L       Kphi    n      Phi0
 2.0  18    C_MOF  N_MOF  C_MOF  H_MOF   0.000000   1   0.000000
...

#out_of_plane   cvff

!Ver  Ref     I     J     K     L       Kchi    n      Chi0
 2.0  18    C_MOF  N_MOF  C_MOF  Zn_MOF   0.100000   2   180.000000
...

#nonbond(12-6)   cvff

@type A-B
@combination geometric

!Ver  Ref     I           A             B
 2.0  18    C_MOF    1117239.1430      685.01126
 2.0  18    Zn_MOF      24552.2675      110.35363
...

#bond_increments   cvff

!Ver  Ref     I     J       DeltaIJ     DeltaJI
 2.0  18    C_MOF  H_MOF   0.000000   0.000000
...
```

### LJ Parameter Conversion

The ParameterSet uses σ/ε form; MSI .frc uses A/B form:

```python
def lj_sigma_eps_to_ab(*, sigma: float, epsilon: float) -> tuple[float, float]:
    """Convert LJ σ/ε to A/B coefficients.
    
    U(r) = A/r¹² - B/r⁶ = 4ε[(σ/r)¹² - (σ/r)⁶]
    
    Therefore:
      A = 4ε·σ¹²
      B = 4ε·σ⁶
    """
    s6 = sigma ** 6
    a = 4.0 * epsilon * (s6 ** 2)
    b = 4.0 * epsilon * s6
    return a, b
```

---

## Complete Workflow Example

### Using the Pipeline Programmatically

```python
from pathlib import Path
import json

# 1. Load structure files
from usm.io import load_car, load_mdf
from usm.ops.compose import compose_on_keys

usm_car = load_car("inputs/structure.car")
usm_mdf = load_mdf("inputs/structure.mdf")
usm = compose_on_keys(usm_car, usm_mdf)

# 2. Derive TermSet
from usm.ops.termset import export_termset_json
export_termset_json(usm, "outputs/termset.json")

# 3. Load ParameterSet (or derive from structure)
parameterset = json.loads(Path("inputs/parameterset.json").read_text())

# 4. Build FRC with generic bonded params
from upm.build.frc_builders import build_frc_cvff_with_generic_bonded

termset = json.loads(Path("outputs/termset.json").read_text())
build_frc_cvff_with_generic_bonded(
    termset=termset,
    parameterset=parameterset,
    out_path="outputs/force_field.frc"
)

# 5. Run msi2lmp
from external import msi2lmp

result = msi2lmp.run(
    base_name="structure",
    frc_file="outputs/force_field.frc",
    exe_path="/path/to/msi2lmp.exe",
    output_prefix="outputs/structure",
    ignore=True  # Use -ignore flag for missing params
)

print(f"Generated: {result['outputs']['lmp_data_file']}")
```

### Using the Workspace Runner

The `run.py` script in workspace directories encapsulates the full pipeline:

```bash
cd workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/
python run.py --config config.json
```

**config.json:**
```json
{
  "inputs": {
    "car": "inputs/CALF20.car",
    "mdf": "inputs/CALF20.mdf",
    "parameterset": "inputs/parameterset.json"
  },
  "outputs_dir": "outputs",
  "executables": {
    "msi2lmp": "/path/to/msi2lmp.exe"
  },
  "params": {
    "timeout_s": 60,
    "coord_norm_enabled": true,
    "coord_norm_mode": "wrap_shift"
  }
}
```

---

## Extension Points

### Custom Bonded Parameter Functions

To use physically meaningful parameters instead of placeholders:

```python
# 1. Create custom parameter function
def my_bond_params(t1: str, t2: str, t1_el: str, t2_el: str) -> tuple[float, float]:
    """Look up real bond parameters from a database."""
    key = tuple(sorted([t1, t2]))
    if key in MY_BOND_DB:
        return MY_BOND_DB[key]
    # Fall back to placeholder
    return placeholder_bond_params(t1_el=t1_el, t2_el=t2_el)

# 2. Modify generate_generic_bonded_params() or create custom builder
```

### Adding New Term Types

To support cross-terms (e.g., bond-bond, bond-angle):

1. Extend `derive_termset_v0_1_2()` to enumerate the new term type
2. Add canonicalization function for the new type
3. Add placeholder parameter function
4. Update FRC template with new section
5. Update builder to populate new section

### Custom FRC Templates

Different force field families require different section structures:

```python
from upm.build.frc_templates import CVFF_MINIMAL_SKELETON

# Create custom template for Class II force field
CLASS_II_TEMPLATE = """
!BIOSYM forcefield          2

#define pcff
...
#quartic_bond   pcff
{bond_entries}

#quartic_angle  pcff
{angle_entries}
...
"""
```

---

## API Reference

### Core Functions

| Function | Module | Description |
|----------|--------|-------------|
| `derive_termset_v0_1_2(structure)` | `usm.ops.termset` | Derive TermSet from USM structure |
| `export_termset_json(structure, path)` | `usm.ops.termset` | Derive and write TermSet JSON |
| `generate_generic_bonded_params(termset, parameterset)` | `upm.build.frc_builders` | Generate FRC entry lines |
| `build_frc_cvff_with_generic_bonded(termset, parameterset, out_path)` | `upm.build.frc_builders` | Build complete FRC file |
| `build_frc_nonbond_only(termset, parameterset, out_path)` | `upm.build.frc_builders` | Build nonbonded-only FRC |

### Helper Functions

| Function | Module | Description |
|----------|--------|-------------|
| `lj_sigma_eps_to_ab(sigma, epsilon)` | `upm.build.frc_helpers` | Convert LJ σ/ε to A/B |
| `placeholder_bond_params(t1_el, t2_el)` | `upm.build.frc_helpers` | Generic bond k, r0 |
| `placeholder_angle_params(center_el)` | `upm.build.frc_helpers` | Generic angle θ0, k |

### I/O Functions

| Function | Module | Description |
|----------|--------|-------------|
| `load_car(path)` | `usm.io.car` | Parse CAR file to USM |
| `load_mdf(path)` | `usm.io.mdf` | Parse MDF file to USM |
| `compose_on_keys(car_usm, mdf_usm)` | `usm.ops.compose` | Merge CAR+MDF structures |
| `read_termset_json(path)` | `upm.io.termset` | Load TermSet JSON |
| `read_parameterset_json(path)` | `upm.io.parameterset` | Load ParameterSet JSON |

---

## File Locations

```
src/
├── usm/
│   ├── io/
│   │   ├── car.py          # CAR file parser
│   │   └── mdf.py          # MDF file parser
│   └── ops/
│       ├── compose.py      # CAR+MDF composition
│       ├── termset.py      # TermSet derivation
│       └── parameterset.py # ParameterSet derivation
│
├── upm/
│   ├── src/upm/
│   │   ├── build/
│   │   │   ├── frc_builders.py  # Main builder functions
│   │   │   ├── frc_helpers.py   # Helper utilities
│   │   │   └── frc_templates.py # FRC skeleton templates
│   │   └── io/
│   │       ├── termset.py       # TermSet I/O
│   │       └── parameterset.py  # ParameterSet I/O
│   └── tests/
│       ├── test_build_frc_generic_bonded.py
│       └── test_build_frc_from_scratch_nonbond_only.py
│
└── external/
    └── msi2lmp.py          # msi2lmp.exe wrapper
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| v0.1.2 | 2024-12 | Added improper canonicalization, counts tracking |
| v0.1.1 | 2024-11 | Added dihedral enumeration, PBC-aware bonds |
| v0.1.0 | 2024-10 | Initial termset derivation with bonds/angles |

---

## References

- [DevGuide v0.1.2](../DevGuides/DevGuide_v0.1.2.md) - TermSet schema specification
- [CVFF Base Minimization Plans](../plans/cvff_base_minimization/) - Phase 1-12 implementation history
- [msi2lmp Documentation](msi2lmp_standalone_usage.md) - msi2lmp.exe usage guide
