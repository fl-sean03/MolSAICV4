# Phase 12: Cleanup and Hardening Plan

## Executive Summary

With the CVFF minimization thrust complete (97.2% reduction, 157 lines, no -ignore flag needed), this phase cleans up experimental artifacts and hardens the final solution for production use.

**Final Solution**: `build_frc_cvff_with_generic_bonded()` @ 157 lines

---

## 12.1: Archive Plans to docs/plans/cvff_base_minimization/

### Files to Move (27 files)
All files in `plans/` directory related to this thrust:
- `cvff_base_minimization_implementation_plan.md`
- `cvff_ultimate_minimization_and_canonical_base_plan.md`
- `E21_skeleton_experiment_implementation_plan.md`
- `phase8_canonical_cvff_skeleton_implementation.md`
- `phase9_skeleton_integration_plan.md`
- `phase10_final_validation_documentation.md`
- `phase10_realignment_and_validation_plan.md`
- `phase11_ignore_free_operation_plan.md`
- `subtask_generic_bonded_params_implementation.md`
- `subtask1_mdf_topology_parser_plan.md`
- `subtask1_phase1_pruned_builder_plan.md`
- `subtask2_phase2_entry_level_pruning_plan.md`
- `subtask2A_experiment_execution_plan.md`
- `subtask2B_combined_presets_analysis.md`
- `subtask3_phase3_final_validation_plan.md`
- `subtask4_msi2lmp_stall_remediation_plan.md`
- `subtask4_phase4_extended_minimization_plan.md`
- `subtask4A_cvff_base_embedding_implementation_plan.md`
- `subtask4A_cvff_minimization_search_plan.md`
- `subtask4A2_E16_E19_truncation_experiments.md`
- `subtask4A3_E20_embedded_base_implementation.md`
- `subtask4B_tests_defaults_documentation.md`
- `subtask5_phase5_true_zero_entries_plan.md`
- `subtask6_m23_analysis_demo_plan.md`
- `subtask7_phase6_theoretical_minimum_plan.md`
- `subtask8_phase7_M25_M31_experiments.md`
- `subtask8_phase7_M25_M31_implementation.md`

### Target Structure
```
docs/plans/cvff_base_minimization/
├── README.md                    # Index of all plans with final status
├── 01_implementation_plan.md
├── 02_ultimate_minimization.md
├── ... (remaining plans)
└── 27_phase12_cleanup.md        # This plan (move last)
```

---

## 12.2: Clean NIST Workspace

### Directory: `workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/`

### Files to DELETE

#### Experiment Output Directories (20+)
```
outputs_E0_aba/
outputs_E16/
outputs_E17/
outputs_E18/
outputs_E19/
outputs_E20/
outputs_E20_classII/
outputs_E20_run2/
outputs_E21/
outputs_E21_classII/
outputs_M23_demo/
outputs_M24/
outputs_M25/
outputs_M26/
outputs_M27/
outputs_M28/
outputs_M29/
outputs_M30/
outputs_M31/
outputs_missing_1/
outputs_missing_2/
outputs_phase10/
outputs_phase10_test/
outputs_skeleton/
```

#### Experiment Config Files (40+)
```
config_E0_aba.json
config_E16.json through config_E19.json
config_E20_classII.json
config_E20_run2.json
config_exp_E0.json through config_exp_E14.json
config_M01.json through config_M31.json
config_missing.json
config_missingtool_quick.json
config_real_guarded.json
config_real_short.json
config_real.json
config_use_nonbond.json
```

#### Obsolete Files
```
experiment_results_E16_E19.json
experiment_results_E20.json
experiment_results.json
ff_skeleton_bonded.frc
generate_minimal_base.py
```

### Files to KEEP
```
inputs/
  CALF20.car
  CALF20.mdf
  parameterset.json
tools/
  run_real_tool_guarded.py
run.py           # Updated in 12.3
validate_run.py  # Keep as-is
config.json      # Updated in 12.4
```

---

## 12.3: Update run.py

### Current State
- Complex preset/emit selection logic with 50+ code paths
- Imports many legacy builders
- Supports E0-E21, M01-M31 experiments

### Target State
- Simple, clean builder invocation
- Use `build_frc_cvff_with_generic_bonded()` as default
- Optional config param to use skeleton mode (with -ignore)
- Remove experiment preset code

### Changes Required

```python
# REMOVE these imports:
# - build_frc_cvff_with_embedded_base
# - build_frc_cvff_with_pruned_base
# - build_frc_e21_asset_skeleton
# - build_frc_asset_truncated
# - ASSET_TRUNCATION_LINES
# - CVFF_MINIMIZATION_PRESETS
# - resolve_cvff_frc_experiment_preset

# ADD this import:
from upm.build.frc_from_scratch import build_frc_cvff_with_generic_bonded

# SIMPLIFY builder selection:
ff_path = frc_files_dir / "cvff_generic_bonded.frc"
build_frc_cvff_with_generic_bonded(
    termset=json.loads(termset_path.read_text(encoding="utf-8")),
    parameterset=json.loads(parameterset_path.read_text(encoding="utf-8")),
    out_path=ff_path,
)
```

---

## 12.4: Create Clean config.json

### Current config.json Structure
Unknown - need to check current default

### Target config.json
```json
{
  "inputs": {
    "car": "inputs/CALF20.car",
    "mdf": "inputs/CALF20.mdf",
    "parameterset": "inputs/parameterset.json"
  },
  "outputs_dir": "outputs",
  "executables": {
    "msi2lmp": "/home/sf2/LabWork/software/msi2lmp.exe"
  },
  "params": {
    "timeout_s": 60,
    "coord_norm_enabled": true,
    "coord_norm_mode": "wrap_shift"
  }
}
```

Note: No `frc_experiment_preset` param needed - defaults to generic_bonded

---

## 12.5: Rerun and Validate

### Validation Steps

1. **Clean outputs**
   ```bash
   rm -rf workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/outputs
   ```

2. **Run workspace**
   ```bash
   python workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/run.py \
     --config workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/config.json
   ```

3. **Verify outputs**
   ```bash
   ls -la workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/outputs/msi2lmp_run/CALF20.data
   wc -l workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/outputs/frc_files/*.frc
   ```

4. **Verify determinism (A/B run)**
   ```bash
   # Run A
   sha256sum outputs/msi2lmp_run/CALF20.data outputs/frc_files/*.frc > /tmp/run_a.sha256
   # Clean and run B
   rm -rf outputs && python run.py --config config.json
   sha256sum outputs/msi2lmp_run/CALF20.data outputs/frc_files/*.frc > /tmp/run_b.sha256
   # Compare
   diff /tmp/run_a.sha256 /tmp/run_b.sha256
   ```

### Expected Results
- `CALF20.data` exists and is non-empty
- `.frc` file has ~157 lines
- A/B hashes match exactly
- No `-ignore` flag used

---

## 12.6: Update Documentation

### Files to Update

1. **`docs/DevGuides/thrust_log_cvff_base_minimization.md`**
   - Add Phase 12 cleanup section
   - Mark thrust as COMPLETE
   - Document final recommended API

2. **`docs/DevGuides/msi2lmp_diagnostics_repro.md`**
   - Update recommended command to use generic_bonded .frc
   - Remove references to experimental presets
   - Simplify reproduction steps

---

## 12.7: Code Cleanup in frc_from_scratch.py

### Considerations

The `frc_from_scratch.py` file now contains:
- Legacy builders (E0-E10 presets)
- M-series pruned base builders
- Skeleton builders
- **Generic bonded builder (RECOMMENDED)**

### Recommendation
- **Keep all builders** for backwards compatibility
- Add deprecation warnings to legacy builders
- Add clear "RECOMMENDED" docstring to `build_frc_cvff_with_generic_bonded()`
- Consider refactoring into separate modules in future

### Docstring Update
```python
def build_frc_cvff_with_generic_bonded(
    termset: dict[str, Any],
    parameterset: dict[str, Any],
    *,
    out_path: str | Path,
) -> str:
    """Build a minimal CVFF .frc with generic bonded parameters.

    **RECOMMENDED API** for production use.

    This builder generates a ~157 line .frc file that:
    - Works with msi2lmp.exe WITHOUT -ignore flag
    - Uses generic bonded parameters derived from termset topology
    - Is fully deterministic
    - Achieves 97.2% reduction from full CVFF base (5571 -> 157 lines)

    For skeleton mode (120 lines, requires -ignore flag), use:
        build_frc_cvff_from_skeleton()

    ...
    """
```

---

## Execution Order

1. Archive plans (12.1) - safe, no code changes
2. Clean NIST workspace (12.2) - delete experimental artifacts
3. Update run.py (12.3) - simplify code
4. Create clean config.json (12.4) - update defaults
5. Rerun and validate (12.5) - verify everything works
6. Update documentation (12.6) - record final state
7. Code cleanup (12.7) - optional hardening

---

## Success Criteria

- [ ] All 27 plan files archived to `docs/plans/cvff_base_minimization/`
- [ ] NIST workspace has only essential files
- [ ] run.py is simplified and uses generic_bonded by default
- [ ] config.json is clean with recommended settings
- [ ] CALF20.data produced successfully without -ignore flag
- [ ] Determinism verified
- [ ] Documentation updated with final recommendations
