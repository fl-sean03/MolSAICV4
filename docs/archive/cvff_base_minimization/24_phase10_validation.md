# Phase 10: Final Validation & Documentation Plan

## 1) Context Summary

Phase 10 is the final phase of the CVFF Ultimate Minimization and Canonical Base Plan. The previous phases achieved:

| Phase | Achievement | Lines | Reduction |
|-------|-------------|-------|-----------|
| Phase 1 | M04 Section-level pruning | 4663 | 16.3% |
| Phase 2 | M16 Entry-level pruning | 1057 | 81.0% |
| Phase 4 | M22 Extended minimization | 395 | 92.9% |
| Phase 5 | M23 True zero entries | 386 | 93.1% |
| Phase 6 | M24 Prune auto_equivalence | 205 | 96.3% |
| Phase 7 | **M29 Absolute minimum** | **120** | **97.8%** |
| Phase 8 | CVFF_MINIMAL_SKELETON constant created | - | - |
| Phase 9 | use_skeleton parameter integrated | - | - |

## 2) Key Deliverables Already Created

### Phase 8 Deliverables
- `CVFF_MINIMAL_SKELETON` constant in [`frc_from_scratch.py:3290`](../src/upm/src/upm/build/frc_from_scratch.py:3290)
- `build_frc_cvff_from_skeleton()` builder function in [`frc_from_scratch.py:3567`](../src/upm/src/upm/build/frc_from_scratch.py:3567)
- Helper functions:
  - `_format_skeleton_atom_type_entry()`
  - `_format_skeleton_equivalence_entry()`
  - `_format_skeleton_auto_equivalence_entry()`
  - `_format_skeleton_nonbond_entry()`
  - `_skeleton_element_to_connects()`
  - `_build_skeleton_alias_map()`

### Phase 9 Deliverables
- `use_skeleton=True` parameter added to:
  - `build_frc_cvff_minimal_bonded()` line 166
  - `build_frc_cvff_with_pruned_base()`
- Tests for skeleton functionality in [`test_build_frc_from_scratch_cvff_minimal_bonded.py:521-744`](../src/upm/tests/test_build_frc_from_scratch_cvff_minimal_bonded.py:521)

## 3) Phase 10 Execution Steps

### Step 1: Run UPM Test Suite
```bash
cd src/upm && python -m pytest tests/ -v --tb=short 2>&1 | head -100
```

Expected tests:
- `test_build_frc_cvff_minimal_bonded_is_byte_deterministic`
- `test_cvff_minimal_bonded_use_skeleton_produces_minimal_output`
- `test_skeleton_is_byte_deterministic`
- `test_skeleton_direct_call_matches_delegation`
- Plus 30+ other existing tests

### Step 2: Run msi2lmp Integration Test
```bash
python -m pytest tests/integration/test_workspace_nist_calf20_msi2lmp_unbonded_determinism.py -v --tb=short
```

### Step 3: Real-world msi2lmp.exe Validation with Skeleton

Generate skeleton output and run msi2lmp.exe:

```python
import json
from pathlib import Path
from upm.build.frc_from_scratch import build_frc_cvff_from_skeleton

# Load CALF20 termset and parameterset
ts_path = Path("workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/outputs/termset.json")
ps_path = Path("workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/outputs/parameterset.json")

ts = json.loads(ts_path.read_text())
ps = json.loads(ps_path.read_text())

# Generate skeleton output
out_path = Path("workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/outputs_phase10/ff_skeleton.frc")
build_frc_cvff_from_skeleton(ts, ps, out_path=out_path)

# Check line count
print(f"Skeleton FRC lines: {len(out_path.read_text().splitlines())}")
```

Then run msi2lmp.exe:
```bash
cd workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/outputs_phase10
cp ../inputs/CALF20.car ../inputs/CALF20.mdf .
timeout 30s /home/sf2/LabWork/software/msi2lmp.exe CALF20 -class I -frc ff_skeleton.frc
echo "exit_code=$?"
ls -la CALF20.data
sha256sum CALF20.data
```

### Step 4: Update Thrust Log

Add Phase 10 section to [`thrust_log_cvff_base_minimization.md`](../docs/DevGuides/thrust_log_cvff_base_minimization.md):

```markdown
## 20) Phase 10 Results: Final Validation & Documentation

**Executed**: 2025-12-21

### 20.1 Test Suite Results

| Test Suite | Tests | Passed | Failed |
|------------|-------|--------|--------|
| UPM tests | XX | XX | 0 |
| Integration tests | XX | XX | 0 |

### 20.2 msi2lmp.exe Skeleton Validation

| Metric | Result |
|--------|--------|
| Skeleton FRC lines | ~120 |
| msi2lmp exit code | 0 |
| CALF20.data size | 6856 bytes |
| CALF20.data SHA256 | cbf9981e... (matches all prior) |

### 20.3 API Summary

New exports added to `upm.build.frc_from_scratch`:

| Function/Constant | Description |
|-------------------|-------------|
| `CVFF_MINIMAL_SKELETON` | 120-line canonical skeleton template |
| `build_frc_cvff_from_skeleton()` | Primary skeleton builder |
| `use_skeleton=True` parameter | Skeleton delegation for existing builders |

### 20.4 Final Statistics

| Metric | Original | Final | Change |
|--------|----------|-------|--------|
| Base file | 5571 lines | 120 lines | **97.8% reduction** |
| CALF20.data | 6856 bytes | 6856 bytes | **Identical** |
| Determinism | Full | Full | **Maintained** |

### 20.5 Complete Minimization Journey

The M-series experiments from M01 to M31:
- M01-M05: Section-level pruning
- M10-M16: Entry-level pruning  
- M17-M22: Extended minimization
- M23: True zero entries
- M24: Prune auto_equivalence
- M25-M29: Structural cleanup
- M30-M31: FAILED (column headers required)
- M_SKELETON: Canonical skeleton template

### 20.6 Key Technical Findings

1. **Column headers are REQUIRED**: M30/M31 failed - msi2lmp.exe stalls without `!Ver Ref...` lines
2. **Zero base entries sufficient**: Only custom CALF20 types are used
3. **Single #define block works**: Only cvff_nocross_nomorse needed
4. **Version history optional**: Can be removed without impact
5. **Description comments optional**: `>` lines can be removed

### 20.7 Recommendations

For production use:
- **Maximum reduction**: Use `build_frc_cvff_from_skeleton()` directly or `use_skeleton=True`
- **Conservative**: Use M16 preset for safety margin
- **Maximum compatibility**: Use E20 full base for unknown systems
```

### Step 5: Check Documentation

Review and update if needed:
- [`DevGuide_v0.1.3.md`](../docs/DevGuides/DevGuide_v0.1.3.md) - Add skeleton usage
- [`msi2lmp_diagnostics_repro.md`](../docs/DevGuides/msi2lmp_diagnostics_repro.md) - Update with skeleton commands

## 4) Success Criteria

- [ ] All UPM tests pass (target: 30+ tests)
- [ ] Integration test passes
- [ ] msi2lmp.exe produces CALF20.data with skeleton output
- [ ] CALF20.data SHA256 matches baseline: `cbf9981e990d02b4e8b7cf96a9a42a9a24da3a8238ebe601f3ca4192e6d1af45`
- [ ] Thrust log updated with Phase 10 section
- [ ] Documentation updated

## 5) Final Deliverables

1. **Test results**: Pass counts for UPM and integration suites
2. **Validation proof**: CALF20.data SHA256 match with skeleton
3. **Updated thrust log**: Phase 10 section added
4. **Completion summary**: Statistics and API reference

## 6) Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Test failures | Review and fix any failing tests |
| msi2lmp.exe stall | Fall back to M29 baseline if skeleton fails |
| SHA256 mismatch | Compare with M29 output first |
