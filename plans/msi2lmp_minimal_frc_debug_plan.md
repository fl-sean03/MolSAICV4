# Plan: Find True Minimum FRC Structure for msi2lmp

**Status**: ✅ **RESOLVED** (2025-12-22)
**Date**: 2025-12-22
**Goal**: Determine the absolute minimum FRC file structure that msi2lmp.exe will accept

## Resolution Summary

The root cause was identified through systematic testing (A-U experiments):

**Entry lists inside `#define` sections cause msi2lmp to segfault.**

See [`docs/methods/MSI2LMP_FRC_REQUIREMENTS.md`](../docs/methods/MSI2LMP_FRC_REQUIREMENTS.md) for:
- Complete requirements documentation
- Minimal required sections (in order)
- Canonical minimal template reference (`test_U_no_hbond.frc`)

### Key Findings
- Only 60 lines needed (vs. original 5000+)
- `#define` sections must be EMPTY (header only)
- `#morse_bond` header REQUIRED even if empty
- Single `#version` line sufficient
- No cross-term sections needed

---

## Problem Statement (Historical)

Our current `CVFF_MINIMAL_SKELETON` template generates ~130 lines FRC files with only the custom atom types (e.g., cdc, cdo for CO2). However, msi2lmp segfaults with these files. The original 5000+ line FRC works. We need to find what's missing.

## Key Observations

1. **Filename matters**: msi2lmp checks if the FRC filename contains "cvff" when using `-class I`
2. **`#version` lines needed**: Fixed by adding `#version cvff.frc` lines
3. **Segfault persists**: Even with correct filename and version lines, minimal FRC causes segfault
4. **Original works**: The full 5000+ line FRC works perfectly

## Debugging Strategy: Binary Search on Original FRC

### Phase 1: Binary Reduction (Find Breaking Point)

Start with the working original FRC and progressively remove sections/entries until it breaks. This identifies what's truly required.

```
Iteration 1: Remove 50% of atom_types entries → Test
Iteration 2: If works, remove another 50% → Test
Iteration 3: Continue until it breaks
Iteration 4: Restore last working state, remove different 50%
```

### Phase 2: Section-by-Section Analysis

Test each FRC section independently:

| Section | Test Method |
|---------|-------------|
| `#atom_types` | Keep only cdc/cdo + minimal required |
| `#equivalence` | Keep only cdc/cdo entries |
| `#auto_equivalence` | Empty vs. with entries vs. standard base |
| `#hbond_definition` | With vs. without |
| `#quadratic_bond` | Only cdc-cdo entry |
| `#quadratic_angle` | Only cdo-cdc-cdo entry |
| `#torsion_1` | Empty |
| `#out_of_plane` | Empty |
| `#nonbond(12-6)` | Only cdc/cdo entries |
| `#bond_increments` | Only cdc-cdo entry |

### Phase 3: Identify Essential Base Requirements

Hypothesis: msi2lmp may require certain base/generic atom types to be defined even if not directly used. Test:

1. Empty `#auto_equivalence` section (no entries at all)
2. With wildcard/generic types (e.g., `c_`, `h_`, `o_`)
3. With standard CVFF base types (h, c, o, etc.)

## Implementation Tasks

### Task 1: Create Test Harness Script
- Script that takes an FRC file and tests it with msi2lmp
- Returns: exit_code, warnings, whether .data was created
- Location: `workspaces/NIST/CO2_construct/test_frc_minimal.py`

### Task 2: Binary Reduction Experiments
- Create stripped versions of original FRC
- Keep only cdc/cdo relevant entries in each section
- Test progressively reduced versions

### Task 3: Section Isolation Tests
- Create test FRC files with variations of each section
- Document which variations work/fail

### Task 4: Identify Minimum Structure
- Based on experiments, document:
  - Required sections
  - Required entries within sections
  - Entry format requirements

### Task 5: Update CVFF_MINIMAL_SKELETON
- Modify template with identified requirements
- Ensure it works for both CO2_construct and nist_calf20

### Task 6: Validation
- Run both workspaces end-to-end
- Verify clean msi2lmp execution (exit 0, no warnings)

## Specific Experiments to Run

### Experiment A: Auto-Equivalence Section
```
Test A1: Remove #auto_equivalence section entirely
Test A2: Keep section header but empty
Test A3: Keep section with only our custom types (cdc, cdo)
Test A4: Keep section with standard CVFF base types
```

### Experiment B: Equivalence Format
```
Test B1: Self-referential (cdc → cdc for all columns)
Test B2: Map to standard types (cdc → c for all columns)
Test B3: Different mappings per column
```

### Experiment C: Required Standard Types
```
Test C1: No standard types at all
Test C2: Add generic placeholder types (c_, o_, h_)
Test C3: Add minimal standard types (c, o)
```

### Experiment D: File Structure
```
Test D1: Single #define block
Test D2: Multiple #define blocks (like original)
Test D3: Different #define names
```

## Success Criteria

1. msi2lmp exits with code 0 (not -11 segfault)
2. No warnings in stderr
3. .data file is created and non-empty
4. Works for both:
   - CO2_construct (cdc, cdo types)
   - nist_calf20 (C_MOF, H_MOF, N_MOF, O_MOF, Zn_MOF types)

## Execution Order

1. [ ] Create test harness script
2. [ ] Run Experiment A (auto_equivalence)
3. [ ] Run Experiment B (equivalence format)
4. [ ] Run Experiment C (standard types)
5. [ ] Run Experiment D (file structure)
6. [ ] Synthesize findings into minimal template
7. [ ] Update CVFF_MINIMAL_SKELETON
8. [ ] Test CO2_construct
9. [ ] Test nist_calf20
10. [ ] Document final minimal structure

## Notes

- The nist_calf20 "inconsistent # of connects" warning is separate from segfault
- That warning is about FRC declaring 4 connections for C but MDF atoms having 2-3
- This can be fixed by deriving connections from actual MDF topology
