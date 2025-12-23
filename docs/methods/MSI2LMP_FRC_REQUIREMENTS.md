# msi2lmp FRC File Requirements

**Status**: CANONICAL  
**Date**: 2025-12-22  
**Source**: Phase 7-13 experiments with test files A through U

## Overview

This document distills the findings from systematic msi2lmp debugging into actionable requirements for generating compatible FRC (forcefield) files.

## Root Cause of msi2lmp Segfault

**Entry lists inside `#define` sections cause msi2lmp to segfault.**

### WRONG (causes segfault):
```
#define cvff

> This is the new format version of the cvff forcefield

!Ver  Ref 		Function		Label
!---- ---   ---------------------------------	------
 2.0  18    atom_types				cvff
 1.0   1    equivalence				cvff
 2.0  18    auto_equivalence     		cvff_auto
...
```

### CORRECT (works):
```
#define cvff

> Minimal cvff forcefield

!Ver  Ref 		Function		Label
!---- ---   ---------------------------------	------
#atom_types	cvff
```

The `#define` section should have ONLY the header comments, then immediately proceed to `#atom_types`.

## Minimal Required Structure (60 lines)

See `workspaces/NIST/CO2_construct/outputs/test_frc/test_U_no_hbond.frc` as the canonical minimal example.

### Required Sections (in order):

| Section | Content Required |
|---------|------------------|
| `#version cvff.frc` | Only ONE version line needed |
| `#define cvff` | EMPTY (header only, no entry list) |
| `#atom_types cvff` | WITH entries for custom types |
| `#equivalence cvff` | WITH entries for custom types |
| `#auto_equivalence cvff_auto` | EMPTY (header only) |
| `#morse_bond cvff` | EMPTY (header only, but REQUIRED) |
| `#quadratic_bond cvff` | WITH entries for custom bonds |
| `#quadratic_angle cvff` | WITH entries for custom angles |
| `#torsion_1 cvff` | EMPTY header required |
| `#out_of_plane cvff` | EMPTY header required |
| `#nonbond(12-6) cvff` | WITH entries + @type/@combination |
| `#bond_increments cvff` | WITH entries for custom pairs |

### NOT Required:

- Multiple `#version` lines
- Multiple `#define` variants (`cvff_nocross`, `cvff_nomorse`, `cvff_nocross_nomorse`)
- Entry lists inside `#define` sections
- `#hbond_definition` section
- Cross-term sections (`bond-bond`, `bond-angle`, `angle-angle-torsion_1`, etc.)
- `_auto` sections (`morse_bond cvff_auto`, `quadratic_bond cvff_auto`, etc.)
- Entries in `#auto_equivalence`
- `#reference` sections

## Column Headers

Column headers are REQUIRED in each section. msi2lmp parses these to understand the data format:

```
!Ver  Ref  Type    Mass      Element  Connections   Comment
!---- ---  ----  ----------  -------  -----------------------------------------
```

## Nonbond Section Requirements

The `#nonbond(12-6)` section MUST include the `@type` and `@combination` directives:

```
#nonbond(12-6)	cvff

@type A-B
@combination geometric

!Ver  Ref     I           A             B
!---- ---    ----    -----------   -----------
```

## Builder Function Selection

| Use Case | Builder Function |
|----------|-----------------|
| Extract real params from source FRC | `build_frc_from_existing()` |
| Generate with placeholder params | `build_frc_cvff_with_generic_bonded()` |
| Nonbond-only FRC | `build_frc_nonbond_only()` |

## Templates

- **`CVFF_SKELETON`**: Canonical template in `src/upm/src/upm/build/frc_templates.py` (for `frc_writer.py`)
- **`CVFF_MINIMAL_SKELETON`**: Minimal template with placeholders (for `frc_builders.py`)

Both templates follow the empty `#define` pattern to avoid segfaults.

## Experimental Evidence

| Test | Lines | Result | Key Finding |
|------|-------|--------|-------------|
| Original FRC | 5477 | PASS | Working baseline |
| minimal.frc | 134 | SEGFAULT | Entry lists in #define |
| test_I_extracted | 239 | PASS | Extracted structure from original |
| test_O_clean_minimal | 150 | PASS | Clean rewrite |
| test_P_one_version | 118 | PASS | Single #version line |
| test_Q_one_define | 112 | PASS | Single #define cvff |
| test_R_no_auto | 82 | PASS | Removed _auto sections |
| test_S_no_crossterms | 62 | PASS | Removed cross-term sections |
| test_T_no_morse | 49 | FAIL | Missing #morse_bond (required!) |
| **test_U_no_hbond** | **60** | **PASS** | **MINIMAL WORKING** |

## References

- Canonical minimal template: `workspaces/NIST/CO2_construct/outputs/test_frc/test_U_no_hbond.frc`
- Full findings: `workspaces/NIST/CO2_construct/outputs/test_frc/FINDINGS.md`
- Debug plan: `plans/msi2lmp_minimal_frc_debug_plan.md`
