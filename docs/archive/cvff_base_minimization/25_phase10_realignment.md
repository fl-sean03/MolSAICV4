# Phase 10 Realignment: msi2lmp.exe Validation - CORRECTED

## 1) Situation Summary

### Problem Statement (CORRECTED)
**Original Goal**: msi2lmp.exe working without `-ignore` flag.
**Actual Result**: Testing confirmed that **M29 ALSO requires `-ignore` flag** for nonbond-only workflows like CALF20.

### Critical Finding (2025-12-21)

Testing M29 WITHOUT the `-ignore` flag revealed:
- **Exit Code**: 12 (failure)
- **Error**: `Unable to find bond data for Zn_MO N_MOF`
- **Root Cause**: CALF20 parameterset contains ONLY nonbond parameters; M29's `max_*=-1` removes all base bonded entries

### Current State Analysis (CORRECTED)

Based on actual testing:

| Approach | Lines | msi2lmp.exe without -ignore | Notes |
|----------|-------|----------------------------|-------|
| E20 (full base) | 5571 | **WORKS** ✓ | Has base bonded params |
| M29 (pruned base) | 120 | **FAILS** ✗ | No bonded params in base or custom |
| M30/M31 (no column headers) | 95/81 | **FAILS** ✗ | Timeout - column headers required |
| Skeleton (from template) | ~120 | **REQUIRES -ignore** | Empty bonded sections |

### Key Findings (CORRECTED)

1. **Column headers (`!` lines) are CRITICAL** - M30 and M31 failed when removed
2. **Bonded parameters are required** unless using `-ignore` flag
3. **M29 and skeleton BOTH require -ignore** for nonbond-only workflows
4. **All Phase 7 experiments used -ignore flag** (not previously documented)

### Why M29 Also Requires -ignore

The M29 preset uses `build_frc_cvff_with_pruned_base()` which:
1. Starts with the embedded CVFF base content
2. Applies pruning with `max_*=-1` which **removes ALL base entries**
3. Appends CALF20 custom types to each section
4. **Custom parameterset has NO bonded parameters**
5. **Result: Empty bonded sections = msi2lmp cannot resolve bonds**

The skeleton builder has identical behavior:
1. Uses a minimal template with placeholders
2. Populates only nonbond sections with actual parameters
3. Leaves bonded sections empty (no parameter entries)
4. **Requires `-ignore` to skip missing bonded parameters**

## 2) Strategic Plan (CORRECTED)

### Objective (Updated)
Document that for **nonbond-only workflows** (like CALF20), both M29 and skeleton builders require the `-ignore` flag.
For **full bonded workflows**, use `build_frc_cvff_with_embedded_base()` which retains base bonded parameters.

### Validation Steps Completed

#### Step 1: M29 Without -ignore Flag (FAILED)
```bash
msi2lmp.exe CALF20 -class I -frc cvff_M29.frc
# NO -ignore flag
```

**Result**: Exit code 12, Error: `Unable to find bond data for Zn_MO N_MOF`

#### Step 2: M29 With -ignore Flag (PASSED)
```bash
msi2lmp.exe CALF20 -class I -frc cvff_M29.frc -ignore
```

**Result**: Exit code 0, CALF20.data created successfully

#### Step 3: Run Test Suite
```bash
cd src/upm && python -m pytest tests/ -v --tb=short
python -m pytest tests/integration/test_workspace_nist_calf20_msi2lmp_unbonded_determinism.py -v
```

#### Step 4: Corrected Production Recommendations

**For nonbond-only workflows (CALF20 style)** - WITH -ignore flag:
```python
from upm.build.frc_from_scratch import build_frc_cvff_with_pruned_base, CVFF_MINIMIZATION_PRESETS

# M29: 120 lines, 97.8% reduction, REQUIRES -ignore for nonbond-only
build_frc_cvff_with_pruned_base(
    termset, parameterset,
    out_path="output.frc",
    prune=CVFF_MINIMIZATION_PRESETS["M29"]
)
# Then: msi2lmp.exe CALF20 -class I -frc output.frc -ignore
```

**For full bonded workflows** - NO -ignore flag needed:
```python
from upm.build.frc_from_scratch import build_frc_cvff_with_embedded_base

# Full base: ~5595 lines, retains bonded parameters, no -ignore needed
build_frc_cvff_with_embedded_base(termset, parameterset, out_path="output.frc")
# Then: msi2lmp.exe <name> -class I -frc output.frc
```

## 3) Acceptance Criteria (CORRECTED)

1. ✅ M29 produces .frc that works WITH -ignore flag (validated)
2. ✗ M29 does NOT work without -ignore for nonbond-only workflows
3. ✅ Output is deterministic (SHA256 match across runs)
4. ✅ All tests pass (using -ignore flag)
5. ✅ Documentation updated with CORRECT guidance

## 4) Key API Reference (CORRECTED)

| Function | Use Case | Output Lines | -ignore Required |
|----------|----------|--------------|------------------|
| `build_frc_cvff_with_embedded_base()` | Full bonded workflows | ~5595 | **No** |
| `build_frc_cvff_with_pruned_base(prune=M29)` | Nonbond-only minimal | 120 | **Yes** |
| `build_frc_cvff_from_skeleton()` | Nonbond-only minimal | ~120 | **Yes** |
| `build_frc_cvff_minimal_bonded(use_skeleton=True)` | Skeleton delegation | ~120 | **Yes** |

## 5) Final Statistics (CORRECTED)

| Metric | Original (E20) | Final (M29) | Notes |
|--------|----------------|-------------|-------|
| FRC file size | 5571 lines | 120 lines | **97.8% reduction** |
| msi2lmp.exe compatibility | ✓ | ✓ (with -ignore) | Requires flag |
| -ignore flag required | No | **Yes** | For nonbond-only |
| CALF20.data output | 6856 bytes | 6856 bytes | Identical |

---

**Plan created**: 2025-12-21
**Corrected**: 2025-12-21
**Status**: Documentation corrected - M29 requires -ignore for nonbond-only workflows
