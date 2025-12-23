# CVFF Base Minimization Thrust - Archived Plans

**Thrust Duration**: December 2025
**Final Result**: 96.8% reduction (5571 → 178 lines)
**Final Solution**: `build_frc_cvff_with_generic_bonded()` - works WITHOUT `-ignore` flag

---

## Executive Summary

This thrust systematically minimized the CVFF `.frc` force field file size for msi2lmp.exe compatibility while maintaining full CALF-20 workflow functionality.

### Key Achievements

| Metric | Original | Final | Improvement |
|--------|----------|-------|-------------|
| FRC file size | 5571 lines | 178 lines | **96.8% reduction** |
| Build module size | 8,978 lines | 2,230 lines | **75% reduction** |
| Deprecated code removed | 6,748 lines | - | **Deleted** |
| msi2lmp.exe compatibility | ✓ | ✓ | Maintained |
| -ignore flag required | N/A | **No** | Clean workflow |
| Output (CALF20.data) | 6856 bytes | 6856 bytes | Valid output |
| Determinism | Full | Full | Maintained |

### Recommended API

```python
from upm.build import build_frc_cvff_with_generic_bonded

# Production-recommended builder for CALF-20 style workflows
build_frc_cvff_with_generic_bonded(
    termset=termset_data,
    parameterset=parameterset_data,
    out_path="cvff_generic_bonded.frc"
)
```

---

## Phase Summary

| Phase | Description | Result |
|-------|-------------|--------|
| 1-3 | Section-level pruning experiments | 4663 lines (16.3% reduction) |
| 4-5 | Entry-level pruning (M16-M23) | 386 lines (93.1% reduction) |
| 6 | Auto_equivalence pruning (M24) | 205 lines (96.3% reduction) |
| 7 | Ultimate structural minimization (M25-M31) | 120 lines (97.8% reduction) |
| 8 | Skeleton template creation | CVFF_MINIMAL_SKELETON constant |
| 9 | Skeleton integration | use_skeleton parameter added |
| 10 | Final validation | Tests passed, M29 requires -ignore |
| 11 | -ignore-free operation | **157 lines, no -ignore needed** |
| 12 | Cleanup and hardening | Plans archived, workspace cleaned |

---

## Archived Plan Files

### Implementation Plans (1-3)
- [01_implementation_plan.md](01_implementation_plan.md) - Initial CVFF minimization implementation plan
- [02_ultimate_minimization.md](02_ultimate_minimization.md) - Ultimate minimization and canonical base plan
- [03_E21_skeleton_experiment.md](03_E21_skeleton_experiment.md) - E21 skeleton experiment implementation

### Phase 1-3: Foundation (4-9)
- [04_subtask1_mdf_topology.md](04_subtask1_mdf_topology.md) - MDF topology parser plan
- [05_phase1_pruned_builder.md](05_phase1_pruned_builder.md) - Phase 1 pruned builder plan
- [06_phase2_entry_pruning.md](06_phase2_entry_pruning.md) - Phase 2 entry-level pruning plan
- [07_subtask2A_execution.md](07_subtask2A_execution.md) - Experiment execution plan
- [08_subtask2B_presets.md](08_subtask2B_presets.md) - Combined presets analysis
- [09_phase3_validation.md](09_phase3_validation.md) - Phase 3 final validation plan

### Phase 4: Extended Minimization (10-16)
- [10_msi2lmp_stall_remediation.md](10_msi2lmp_stall_remediation.md) - msi2lmp stall remediation plan
- [11_phase4_extended_minimization.md](11_phase4_extended_minimization.md) - Phase 4 extended minimization plan
- [12_cvff_base_embedding.md](12_cvff_base_embedding.md) - CVFF base embedding implementation
- [13_minimization_search.md](13_minimization_search.md) - Minimization search plan
- [14_E16_E19_truncation.md](14_E16_E19_truncation.md) - E16-E19 truncation experiments
- [15_E20_embedded_base.md](15_E20_embedded_base.md) - E20 embedded base implementation
- [16_tests_defaults_docs.md](16_tests_defaults_docs.md) - Tests, defaults, and documentation

### Phase 5-6: Zero Entries & Analysis (17-19)
- [17_phase5_zero_entries.md](17_phase5_zero_entries.md) - Phase 5 true zero entries plan
- [18_M23_analysis.md](18_M23_analysis.md) - M23 analysis demo plan
- [19_phase6_theoretical_minimum.md](19_phase6_theoretical_minimum.md) - Phase 6 theoretical minimum plan

### Phase 7: M25-M31 Experiments (20-21)
- [20_phase7_M25_M31_experiments.md](20_phase7_M25_M31_experiments.md) - Phase 7 M25-M31 experiments
- [21_phase7_M25_M31_implementation.md](21_phase7_M25_M31_implementation.md) - Phase 7 M25-M31 implementation

### Phase 8-10: Skeleton & Integration (22-25)
- [22_phase8_skeleton.md](22_phase8_skeleton.md) - Phase 8 canonical CVFF skeleton implementation
- [23_phase9_integration.md](23_phase9_integration.md) - Phase 9 skeleton integration plan
- [24_phase10_validation.md](24_phase10_validation.md) - Phase 10 final validation documentation
- [25_phase10_realignment.md](25_phase10_realignment.md) - Phase 10 realignment and validation plan

### Phase 11-12: Production Hardening (26-28)
- [26_phase11_ignore_free.md](26_phase11_ignore_free.md) - Phase 11 -ignore-free operation plan
- [27_generic_bonded_params.md](27_generic_bonded_params.md) - Generic bonded params implementation
- [28_phase12_cleanup.md](28_phase12_cleanup.md) - Phase 12 cleanup and hardening plan

---

## Key Learnings

1. **Column headers (`!` lines) are REQUIRED**: msi2lmp.exe parser uses them for field position detection
2. **Section structure matters more than content**: Base entries can be empty with `-ignore` flag
3. **Generic bonded params enable -ignore-free**: Tool-satisfying placeholders allow clean workflows
4. **Macro table consistency**: `#define` block must match actual section types

---

## Related Documentation

- [Thrust Log](../../DevGuides/thrust_log_cvff_base_minimization.md) - Complete execution log with all phase results
- [frc_builders.py](../../../src/upm/src/upm/build/frc_builders.py) - Builder implementation
- [NIST CALF-20 Workspace](../../../workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/) - Test workspace

---

*Last updated: 2025-12-21 (Phase 12 Complete - 6,748 lines deprecated code removed, build module consolidated to 2,230 lines)*
