# CVFF Ultimate Minimization and Canonical Base Plan

## Executive Summary

**Goal**: Create the absolute minimum CVFF .frc structure that:
1. Passes msi2lmp.exe validation
2. Contains NO base type entries (all custom)
3. Is robust and extensible for future UPM development
4. Becomes the "one true base" for all .frc generation

**Current State**: M24 at 205 lines (96.3% reduction from 5571)

**Target State**: ~50-80 lines theoretical minimum + canonical skeleton API

---

## Phase 7: Ultimate Minimization Testing

### Current M24 Structure Analysis (205 lines)

| Component | Lines | Bytes Est. | Removable? | Priority |
|-----------|-------|------------|------------|----------|
| Header `!BIOSYM forcefield 1` | 1 | 30 | NO | - |
| Version history (16 lines) | 3-18 | 500 | YES | HIGH |
| Insight comments (4 lines) | 20-23 | 200 | YES | HIGH |
| Blank lines (~10) | various | 10 | MOSTLY | LOW |
| `#define cvff_nocross_nomorse` | 27-41 | 400 | MAYBE | HIGH |
| `#define cvff` | 44-64 | 550 | KEEP ONE | HIGH |
| `#define cvff_nocross` | 67-81 | 400 | MAYBE | HIGH |
| `#define cvff_nomorse` | 85-104 | 550 | MAYBE | HIGH |
| Section headers + custom data | 108-205 | 2500 | NO (core) | - |

### Experiment Matrix

| Preset | Change from M24 | Expected Lines | Test |
|--------|-----------------|----------------|------|
| M25 | Keep only latest #version | ~189 | msi2lmp |
| M26 | Remove ALL #version lines | ~173 | msi2lmp |
| M27 | Remove Insight comments | ~169 | msi2lmp |
| M28 | Keep only `#define cvff` block | ~118 | msi2lmp |
| M29 | Remove `>` description lines | ~105 | msi2lmp |
| M30 | Remove `!Ver Ref...` column headers | ~90 | msi2lmp |
| M31 | Minimize blank lines | ~80 | msi2lmp |

### Implementation Details

#### M25-M27: Preamble Cleanup
```python
class CvffPruneOptions:
    # Add new options:
    keep_version_history: bool = True      # M25/M26: False
    keep_insight_comments: bool = True     # M27: False
```

#### M28: Single Define Block
```python
class CvffPruneOptions:
    define_blocks: Literal['all', 'cvff_only', 'nocross_nomorse_only'] = 'all'  # M28: 'cvff_only'
```

#### M29-M31: Section Cleanup
```python
class CvffPruneOptions:
    keep_description_comments: bool = True   # M29: False (> lines)
    keep_column_headers: bool = True         # M30: False (!Ver Ref lines)
    minimize_blank_lines: bool = False       # M31: True
```

### Verification Command Template
```bash
cd workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/outputs/msi2lmp_run
timeout --preserve-status 30s stdbuf -oL -eL \
  /home/sf2/LabWork/software/msi2lmp.exe CALF20 \
  -class I -frc ../frc_files/cvff_M<N>.frc \
  </dev/null >manual_M<N>.stdout.txt 2>manual_M<N>.stderr.txt
echo "exit_code=$?"
ls -la CALF20.data
```

---

## Phase 8: Canonical CVFF Skeleton Creation

### Design Goals

1. **Skeleton = Structure Only**: No type entries, just headers and required directives
2. **Clear Insertion Points**: Marked locations for custom type injection
3. **Validated Minimum**: Every line is required by msi2lmp.exe
4. **Single Source of Truth**: Used by all .frc builders

### Proposed Skeleton Structure

```
!BIOSYM forcefield          1

#define cvff

> CVFF forcefield skeleton

!Ver  Ref   Function                    Label
!---- ---   --------------------------  ------
 2.0  18    atom_types                  cvff
 1.0   1    equivalence                 cvff
 2.0  18    auto_equivalence            cvff_auto
 1.0   1    hbond_definition            cvff
 2.0  18    quadratic_bond              cvff   cvff_auto
 2.0  18    morse_bond                  cvff   cvff_auto
 2.0  18    quadratic_angle             cvff   cvff_auto
 2.0  18    torsion_1                   cvff   cvff_auto
 2.0  18    out_of_plane                cvff   cvff_auto
 1.0   1    nonbond(12-6)               cvff

#atom_types	cvff

!Ver  Ref  Type    Mass      Element  Connections   Comment
!---- ---  ----  ----------  -------  -----------------------------------------
{{ATOM_TYPES}}

#equivalence	cvff

!Ver  Ref   Type  NonB     Bond    Angle    Torsion    OOP
!---- ---   ----  ----     ----    -----    -------    ----
{{EQUIVALENCE}}

#auto_equivalence	cvff_auto

!Ver  Ref   Type  NonB Bond   Bond     Angle    Angle     Torsion   Torsion      OOP      OOP
!---- ---   ----  ---- ------ ----  ---------- --------- --------- -----------  -------- -----------
{{AUTO_EQUIVALENCE}}

#hbond_definition	cvff

 1.0   1   distance      2.5000
 1.0   1   angle        90.0000
 1.0   1   donors        hn  h*  hspc   htip
 1.0   1   acceptors     o'  o   o*  ospc   otip

#morse_bond	cvff

> E = D * (1 - exp(-ALPHA*(R - R0)))^2

!Ver  Ref     I     J          R0         D           ALPHA
!---- ---    ----  ----     -------    --------      -------
{{MORSE_BOND}}

#quadratic_bond	cvff

> E = K2 * (R - R0)^2

!Ver  Ref     I     J          R0         K2
!---- ---    ----  ----     -------    --------
{{QUADRATIC_BOND}}

#quadratic_angle	cvff

> E = K2 * (Theta - Theta0)^2

!Ver  Ref     I     J     K       Theta0         K2
!---- ---    ----  ----  ----    --------     -------
{{QUADRATIC_ANGLE}}

#torsion_1	cvff

> E = Kphi * [ 1 + cos(n*Phi - Phi0) ]

!Ver  Ref     I     J     K     L           Kphi        n           Phi0
!---- ---    ----  ----  ----  ----      -------      ------     -------
{{TORSION}}

#out_of_plane	cvff

> E = Kchi * [ 1 + cos(n*Chi - Chi0) ]

!Ver  Ref     I     J     K     L           Kchi        n           Chi0
!---- ---    ----  ----  ----  ----      -------      ------     -------
{{OUT_OF_PLANE}}

#nonbond(12-6)	cvff

@type A-B
@combination geometric

> E = Aij/r^12 - Bij/r^6

!Ver  Ref     I           A             B
!---- ---    ----    -----------   -----------
{{NONBOND}}

#bond_increments	cvff

!Ver  Ref     I     J       DeltaIJ     DeltaJI
!---- ---    ----  ----     -------     -------
{{BOND_INCREMENTS}}
```

### Python Implementation

```python
# src/upm/src/upm/build/cvff_skeleton.py

"""Canonical CVFF skeleton for msi2lmp.exe compatibility.

This module defines the absolute minimum .frc structure validated
to work with msi2lmp.exe v3.9.6. All UPM .frc builders should use
this skeleton as their foundation.

Version: 1.0
Validated: CALF-20 system (Zn-MOF)
Lines: ~65 (before custom type injection)
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Literal

# The canonical CVFF skeleton - every line is required
CVFF_SKELETON_V1: str = '''!BIOSYM forcefield          1

#define cvff
...
'''

@dataclass
class CvffCustomTypes:
    """Custom type definitions to inject into skeleton."""
    atom_types: list[str]       # formatted rows
    equivalence: list[str]      # formatted rows
    auto_equivalence: list[str] # formatted rows
    morse_bond: list[str] = field(default_factory=list)
    quadratic_bond: list[str] = field(default_factory=list)
    quadratic_angle: list[str] = field(default_factory=list)
    torsion: list[str] = field(default_factory=list)
    out_of_plane: list[str] = field(default_factory=list)
    nonbond: list[str]          # required
    bond_increments: list[str] = field(default_factory=list)


def build_frc_from_skeleton(
    custom: CvffCustomTypes,
    *,
    skeleton: str = CVFF_SKELETON_V1,
) -> str:
    """Build a complete .frc file from skeleton + custom types.
    
    This is the canonical API for all CVFF .frc generation.
    """
    result = skeleton
    result = result.replace('{{ATOM_TYPES}}', '\n'.join(custom.atom_types))
    result = result.replace('{{EQUIVALENCE}}', '\n'.join(custom.equivalence))
    # ... etc
    return result


def validate_skeleton(skeleton: str) -> list[str]:
    """Validate a skeleton has all required markers."""
    required = [
        '!BIOSYM forcefield',
        '#define cvff',
        '#atom_types',
        '#equivalence',
        '#nonbond(12-6)',
        '@type A-B',
        '@combination geometric',
    ]
    errors = []
    for req in required:
        if req not in skeleton:
            errors.append(f"Missing required element: {req}")
    return errors
```

---

## Phase 9: Refactor All Builders

### Current Builder Inventory

| Builder | Location | Current Approach | Refactor Target |
|---------|----------|------------------|-----------------|
| `build_frc_nonbond_only()` | frc_from_scratch.py:99 | Manual string building | Use skeleton |
| `build_frc_cvff_minimal_bonded()` | frc_from_scratch.py:190 | Manual + MSI codec | Use skeleton |
| `build_frc_cvff_with_pruned_base()` | frc_from_scratch.py:1850 | Prune embedded base | Keep for backwards compat |
| Legacy `_build_frc_cvff_minimal_bonded_legacy()` | frc_from_scratch.py:~600 | Emit options | Deprecate or keep for E0-E10 |

### Refactoring Strategy

1. **Create `build_frc_from_skeleton()` as primary API**
2. **Refactor `build_frc_cvff_minimal_bonded()` to use skeleton internally**
3. **Keep `build_frc_cvff_with_pruned_base()` for backwards compatibility (M01-M24 presets)**
4. **Add deprecation warnings to legacy builders**

### New Test Requirements

```python
# tests for cvff_skeleton.py

def test_skeleton_has_required_markers():
    """CVFF_SKELETON_V1 contains all msi2lmp.exe required elements."""
    errors = validate_skeleton(CVFF_SKELETON_V1)
    assert errors == []

def test_build_from_skeleton_determinism():
    """Two builds with same input produce identical output."""
    custom = CvffCustomTypes(...)
    out1 = build_frc_from_skeleton(custom)
    out2 = build_frc_from_skeleton(custom)
    assert out1 == out2

def test_skeleton_msi2lmp_validation():
    """Built .frc passes msi2lmp.exe on CALF-20."""
    # This requires real tool - mark as integration test
    pass
```

---

## Phase 10: Final Validation

### Acceptance Criteria

1. **Canonical skeleton produces valid CALF20.data**
2. **Determinism verified with A/B/A test**
3. **All existing tests pass**
4. **Documentation updated**

### Verification Commands

```bash
# 1. Build with skeleton
python -c "
from upm.build.cvff_skeleton import build_frc_from_skeleton, CvffCustomTypes
# ... create custom types from CALF-20
frc = build_frc_from_skeleton(custom)
Path('outputs/frc_files/ff_skeleton.frc').write_text(frc)
"

# 2. Run msi2lmp
cd workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/outputs/msi2lmp_run
timeout 30s /home/sf2/LabWork/software/msi2lmp.exe CALF20 \
  -class I -frc ../frc_files/ff_skeleton.frc

# 3. Verify output
ls -la CALF20.data
sha256sum CALF20.data
```

---

## Implementation Order

1. **Subtask 1**: Phase 7 experiments (M25-M31) to find absolute minimum
2. **Subtask 2**: Phase 8 create CVFF_SKELETON_V1 and cvff_skeleton.py
3. **Subtask 3**: Phase 9 refactor builders to use skeleton
4. **Subtask 4**: Phase 10 final validation and documentation

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| M25-M31 experiments fail | Fall back to M24 as skeleton base |
| Column headers required | Keep them in skeleton |
| #define block required | Keep one block in skeleton |
| Builder refactor breaks existing workflows | Keep legacy functions, add deprecation |

---

## Success Metrics

- [ ] Skeleton line count < 80 (excluding custom types)
- [ ] msi2lmp.exe PASS with skeleton on CALF-20
- [ ] All 40+ existing tests pass
- [ ] `build_frc_from_skeleton()` becomes primary API
- [ ] Documentation updated with skeleton architecture
