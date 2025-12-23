# Minimal FRC Workspace Wiring Plan

**Date**: 2025-12-21  
**Status**: READY FOR IMPLEMENTATION  
**Mode**: Architect → Orchestrator

---

## 1) Executive Summary

The NIST CALF-20 workspace is generating a bloated 1057-line `.frc` file when it should produce ~150-200 lines. The modular components for minimal `.frc` generation were built but never wired to the workspace.

### Current vs Expected

| Metric | Current | Expected | Improvement |
|--------|---------|----------|-------------|
| FRC file size | 1057 lines | ~150 lines | **86% reduction** |
| Atom types included | 5 needed + ~60 unused | 5 needed only | No waste |
| Builder used | `build_frc_cvff_with_minimal_base()` | `build_frc_input()` + `write_cvff_frc()` | Modular |
| Source data | Embedded 1033-line base | Skeleton + termset/parameterset | Dynamic |

---

## 2) Root Cause Analysis

### What Exists

1. **Modular components (correct approach)**:
   - [`cvff_skeleton.py`](../src/upm/src/upm/build/cvff_skeleton.py) - 124-line CVFF template with placeholders
   - [`frc_input.py`](../src/upm/src/upm/build/frc_input.py) - `build_frc_input()` converts termset/parameterset → FRCInput
   - [`frc_writer.py`](../src/upm/src/upm/build/frc_writer.py) - `write_cvff_frc()` fills template with entries

2. **Deprecated components (wrong approach)**:
   - [`cvff_minimal_base.py`](../src/upm/src/upm/build/cvff_minimal_base.py) - 1033-line embedded CVFF base
   - `build_frc_cvff_with_minimal_base()` in [`frc_builders.py`](../src/upm/src/upm/build/frc_builders.py)

### What Happened

During Phase 13 migration, the NIST workspace was wired to `build_frc_cvff_with_minimal_base()` instead of the modular approach. The minimal base contains hundreds of standard CVFF types (`h`, `c`, `cp`, etc.) that are NOT needed for CALF-20.

---

## 3) The Vision

### Input Flow

```
USM Structure → derive_termset() → termset.json
           → derive_parameterset() → parameterset.json
                          ↓
                    build_frc_input(termset, parameterset)
                          ↓
                    FRCInput dataclass
                          ↓
                    write_cvff_frc(frc_input, out_path)
                          ↓
                    Minimal .frc (~150 lines)
```

### Output Content

The minimal `.frc` should contain ONLY:

1. **CVFF skeleton** (~80 lines of structure):
   - `!BIOSYM forcefield` header
   - `#define cvff` block with function table
   - Section headers with column labels

2. **Structure-derived entries** (~70 lines):
   - 5 atom types: `C_MOF`, `H_MOF`, `N_MOF`, `O_MOF`, `Zn_MOF`
   - 6 bond parameters
   - 11 angle parameters
   - 16 torsion parameters
   - 6 out-of-plane parameters
   - 5-6 nonbond parameters

### NOT Included

- Hundreds of standard CVFF types (`h`, `c`, `cp`, `n`, etc.)
- Cross-terms (bond-bond, bond-angle, etc.)
- Morse bond parameters for unused types
- Auto-equivalence for types we don't use

---

## 4) Implementation Steps

### Subtask 1: Wire Modular Builder to NIST Workspace

**File**: `workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/run.py`

**Changes**:
1. Change import from:
   ```python
   from upm.build.frc_builders import build_frc_cvff_with_minimal_base
   ```
   To:
   ```python
   from upm.build.frc_input import build_frc_input
   from upm.build.frc_writer import write_cvff_frc
   ```

2. Replace builder call from:
   ```python
   build_frc_cvff_with_minimal_base(termset, parameterset, out_path)
   ```
   To:
   ```python
   frc_input = build_frc_input(termset, parameterset)
   write_cvff_frc(frc_input, out_path)
   ```

3. Update output filename from `cvff_minimal_base.frc` to `cvff_minimal.frc`

**Acceptance**:
- [ ] Workspace runs without errors
- [ ] Output `.frc` file is ~150-200 lines
- [ ] Output contains only 5 atom types

### Subtask 2: Validate msi2lmp.exe Compatibility

**Test**:
```bash
cd workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1
rm -rf outputs
python run.py --config config.json
ls -la outputs/msi2lmp_run/CALF20.data
wc -l outputs/frc_files/cvff_minimal.frc
```

**Acceptance**:
- [ ] `CALF20.data` exists and is non-empty
- [ ] msi2lmp.exe exit code = 0
- [ ] `.frc` line count < 250

### Subtask 3: Clean Up Deprecated Code

**Files to Archive/Delete**:
1. [`cvff_minimal_base.py`](../src/upm/src/upm/build/cvff_minimal_base.py) - Archive then delete
2. `build_frc_cvff_with_minimal_base()` function in `frc_builders.py` - Remove

**Note**: Check for other callers before deletion.

### Subtask 4: Update Tests

**Files**:
- Add test for minimal `.frc` generation: line count < 250
- Add test for no-base-types: only structure types in output
- Update determinism tests

### Subtask 5: Documentation

**Files to Update**:
- [`docs/plans/cvff_base_minimization/README.md`](../docs/plans/cvff_base_minimization/README.md) - Update final results

---

## 5) Risk Assessment

### Risk: msi2lmp.exe May Require Base Types

**Mitigation**: Phase 11 experiments validated that `build_frc_cvff_with_generic_bonded()` produces working files without base types. The modular approach uses the same skeleton.

### Risk: Other Workspaces Use Deprecated Builder

**Mitigation**: Search for usages before deleting:
```bash
grep -r "build_frc_cvff_with_minimal_base" --include="*.py"
```

---

## 6) Success Criteria

| Criterion | Measurement |
|-----------|-------------|
| FRC file size | < 250 lines |
| Atom types | Only 5 structure types |
| msi2lmp.exe | Exit code 0, CALF20.data exists |
| Determinism | Identical output across runs |
| No base types | No `h`, `c`, `cp`, `n` etc. in output |

---

## 7) Files Changed

| File | Action |
|------|--------|
| `workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/run.py` | Update imports and builder call |
| `src/upm/src/upm/build/frc_builders.py` | Remove deprecated function |
| `src/upm/src/upm/build/cvff_minimal_base.py` | Archive then delete |
| `docs/plans/cvff_base_minimization/README.md` | Update with final results |

---

*Plan created: 2025-12-21*
