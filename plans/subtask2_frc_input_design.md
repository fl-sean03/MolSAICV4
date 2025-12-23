# Subtask 2: frc_input.py Design Document

**Status**: READY FOR IMPLEMENTATION  
**Target File**: `src/upm/src/upm/build/frc_input.py`  
**Line Count Target**: < 300 lines

---

## 1. Data Model Summary

### 1.1 Input Data Structures (from USM)

**TermSet** (dict from `derive_termset_v0_1_2`):
```python
{
    "schema": "molsaic.termset.v0.1.2",
    "atom_types": ["C_MOF", "H_MOF", "N_MOF", "O_MOF", "Zn_MOF"],
    "bond_types": [["C_MOF", "H_MOF"], ["C_MOF", "N_MOF"], ...],
    "angle_types": [["C_MOF", "N_MOF", "C_MOF"], ...],
    "dihedral_types": [["C_MOF", "N_MOF", "C_MOF", "H_MOF"], ...],
    "improper_types": [["C_MOF", "N_MOF", "C_MOF", "Zn_MOF"], ...]
}
```

**ParameterSet** (dict from `derive_parameterset_v0_1_2`):
```python
{
    "schema": "upm.parameterset.v0.1.2",
    "atom_types": {
        "C_MOF": {
            "mass_amu": 12.011,
            "lj_sigma_angstrom": 3.4309,
            "lj_epsilon_kcal_mol": 0.105,
            "element": "C"  # optional
        },
        ...
    }
}
```

### 1.2 Output Dataclasses (frozen)

```python
@dataclass(frozen=True)
class AtomTypeEntry:
    atom_type: str      # e.g., "C_MOF"
    mass_amu: float     # e.g., 12.011
    element: str        # e.g., "C"
    connects: int       # Expected connections (for msi2lmp validation)
    lj_a: float         # LJ A parameter (kcal/mol * Å^12)
    lj_b: float         # LJ B parameter (kcal/mol * Å^6)

@dataclass(frozen=True)
class BondEntry:
    type1: str
    type2: str
    r0: float           # Equilibrium distance (Å)
    k: float            # Force constant (kcal/mol/Å²)

@dataclass(frozen=True)
class AngleEntry:
    type1: str
    type2: str          # Central atom
    type3: str
    theta0: float       # Equilibrium angle (degrees)
    k: float            # Force constant (kcal/mol/rad²)

@dataclass(frozen=True)
class TorsionEntry:
    type1: str
    type2: str
    type3: str
    type4: str
    kphi: float         # Barrier height (kcal/mol)
    n: int              # Periodicity
    phi0: float         # Phase angle (degrees)

@dataclass(frozen=True)
class OOPEntry:
    type1: str          # First peripheral
    type2: str          # Central atom
    type3: str          # Second peripheral
    type4: str          # Third peripheral
    kchi: float         # Force constant (kcal/mol)
    n: int              # Periodicity
    chi0: float         # Equilibrium angle (degrees)

@dataclass(frozen=True)
class NonbondEntry:
    atom_type: str
    lj_a: float
    lj_b: float

@dataclass
class FRCInput:
    atom_types: list[AtomTypeEntry]
    bonds: list[BondEntry]
    angles: list[AngleEntry]
    torsions: list[TorsionEntry]
    oops: list[OOPEntry]
    nonbonds: list[NonbondEntry]
    forcefield_label: str = "cvff"
    msi2lmp_max_type_len: int = 5
```

---

## 2. Helper Functions

### 2.1 _lj_sigma_eps_to_ab(sigma, eps) → tuple[float, float]
Convert Lennard-Jones sigma/epsilon to A/B form:
```python
A = 4.0 * eps * (sigma ** 12)
B = 4.0 * eps * (sigma ** 6)
return (A, B)
```

### 2.2 _element_to_connects(element) → int
Map element symbol to expected connection count:
```python
CONNECTS = {"H": 1, "C": 4, "N": 3, "O": 2, "Zn": 6}
return CONNECTS.get(element, 0)
```

### 2.3 _placeholder_bond_params(el1, el2) → tuple[float, float]
Return (r0, k) placeholder based on element types:
```python
if "H" in (el1, el2):
    return (1.09, 340.0)  # H-X bonds
if "Zn" in (el1, el2):
    return (2.05, 150.0)  # Zn-X bonds
return (1.50, 300.0)      # Default
```

### 2.4 _placeholder_angle_params(center_el) → tuple[float, float]
Return (theta0, k) placeholder based on center element:
```python
k = 50.0
if center_el == "Zn":
    return (90.0, k)   # Octahedral
if center_el == "N":
    return (120.0, k)  # Trigonal planar
return (109.5, k)      # Tetrahedral default (C, O, others)
```

### 2.5 _expand_with_aliases(atom_types, max_len) → tuple[list[str], dict[str, str]]
Handle msi2lmp 5-character truncation:
```python
expanded = []
alias_map = {}  # alias → original
for t in sorted(atom_types):
    expanded.append(t)
    if len(t) > max_len:
        alias = t[:max_len]
        if alias != t and alias not in expanded:
            expanded.append(alias)
            alias_map[alias] = t
return (expanded, alias_map)
```

---

## 3. Main Conversion Function

### build_frc_input(termset, parameterset, *, use_placeholders=True, msi2lmp_max_type_len=5) → FRCInput

**Algorithm**:

1. **Extract atom types** from termset["atom_types"]
2. **Expand with aliases** for msi2lmp compatibility
3. **Build AtomTypeEntry list**:
   - For each atom_type in expanded list:
     - Get params from parameterset (lookup original if alias)
     - Compute LJ A/B from sigma/epsilon
     - Get connects from element
4. **Build BondEntry list** from termset["bond_types"]:
   - For each [t1, t2]:
     - Look up elements from parameterset
     - Get placeholder (r0, k) based on elements
5. **Build AngleEntry list** from termset["angle_types"]:
   - For each [t1, t2, t3]:
     - Look up center element (t2) from parameterset
     - Get placeholder (theta0, k) based on center element
6. **Build TorsionEntry list** from termset["dihedral_types"]:
   - All use placeholder: kphi=0.0, n=1, phi0=0.0
7. **Build OOPEntry list** from termset["improper_types"]:
   - All use placeholder: kchi=0.0, n=0, chi0=0.0
8. **Build NonbondEntry list**:
   - One entry per atom_type with LJ A/B values
9. **Return FRCInput** with all lists sorted deterministically

---

## 4. Deterministic Ordering Rules

1. **Atom types**: Sorted alphabetically
2. **Bonds**: Sorted by (type1, type2) where type1 <= type2
3. **Angles**: Sorted by (type1, type2, type3) where type1 <= type3
4. **Torsions**: Sorted by tuple (type1, type2, type3, type4)
5. **OOPs**: Sorted by tuple (type1, type2, type3, type4)
6. **Nonbonds**: Same order as atom types

---

## 5. Placeholder Parameter Defaults

| Section | Field | Default | H-bond | Zn-bond |
|---------|-------|---------|--------|---------|
| bond | k | 300.0 | 340.0 | 150.0 |
| bond | r0 | 1.50 | 1.09 | 2.05 |
| angle | k | 50.0 | - | - |
| angle | theta0 | 109.5 (C,O) / 120.0 (N) / 90.0 (Zn) | - | - |
| torsion | kphi | 0.0 | - | - |
| torsion | n | 1 | - | - |
| torsion | phi0 | 0.0 | - | - |
| oop | kchi | 0.0 | - | - |
| oop | n | 0 | - | - |
| oop | chi0 | 0.0 | - | - |

---

## 6. Module Exports

```python
__all__ = [
    "AtomTypeEntry",
    "BondEntry",
    "AngleEntry",
    "TorsionEntry",
    "OOPEntry",
    "NonbondEntry",
    "FRCInput",
    "build_frc_input",
]
```

---

## 7. Implementation Checklist

- [ ] Module docstring with purpose and usage
- [ ] Import statements (dataclasses, typing)
- [ ] AtomTypeEntry dataclass (frozen)
- [ ] BondEntry dataclass (frozen)
- [ ] AngleEntry dataclass (frozen)
- [ ] TorsionEntry dataclass (frozen)
- [ ] OOPEntry dataclass (frozen)
- [ ] NonbondEntry dataclass (frozen)
- [ ] FRCInput container dataclass
- [ ] _lj_sigma_eps_to_ab() function
- [ ] _element_to_connects() function
- [ ] _placeholder_bond_params() function
- [ ] _placeholder_angle_params() function
- [ ] _expand_with_aliases() function
- [ ] build_frc_input() main function
- [ ] __all__ exports
- [ ] Line count verification (< 300)

---

## 8. Sample Usage

```python
from upm.build.frc_input import build_frc_input, FRCInput
import json

# Load termset and parameterset (typically from JSON files)
with open("termset.json") as f:
    termset = json.load(f)
with open("parameterset.json") as f:
    parameterset = json.load(f)

# Build FRCInput specification
frc_input: FRCInput = build_frc_input(termset, parameterset)

# Access entries
for atom in frc_input.atom_types:
    print(f"{atom.atom_type}: mass={atom.mass_amu}, LJ_A={atom.lj_a}")
```
