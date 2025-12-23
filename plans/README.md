# MOLSAIC Planning Documents

This directory contains **active and current planning documents** for the MOLSAIC project. Completed/historical plans are archived to [`docs/archive/`](../docs/archive/).

## Plan Index

### 🔄 Active (In Progress)

| File | Description | Status |
|------|-------------|--------|
| [`docs_reorganization_plan.md`](docs_reorganization_plan.md) | Documentation restructuring plan (currently executing) | Active |
| [`REFACTOR_PLAN.md`](REFACTOR_PLAN.md) | Max 500 LOC enforcement strategy for all source files | Active |

### ✅ Completed (Pending Archive)

These plans have been completed and can be moved to `docs/archive/` once verified.

| File | Description | Completed |
|------|-------------|-----------|
| [`phase13_cleanup_refactor.md`](phase13_cleanup_refactor.md) | FRC Builder cleanup and refactoring | 2025-12-22 |
| [`frc_builder_from_existing.md`](frc_builder_from_existing.md) | Build FRC by extracting params from existing files | 2025-12-22 |
| [`msi2lmp_minimal_frc_debug_plan.md`](msi2lmp_minimal_frc_debug_plan.md) | Find true minimum FRC structure for msi2lmp | 2025-12-22 |
| [`subtask5_deprecated_code_cleanup.md`](subtask5_deprecated_code_cleanup.md) | Clean up deprecated FRC builder code | 2024-12-21 |

### 📋 Ready for Implementation

These plans are fully designed and ready to be executed.

| File | Description |
|------|-------------|
| [`minimal_frc_builder_implementation.md`](minimal_frc_builder_implementation.md) | New minimal FRC builder architecture |
| [`minimal_frc_workspace_wiring.md`](minimal_frc_workspace_wiring.md) | Wire modular builder to NIST workspace |
| [`subtask2_frc_input_design.md`](subtask2_frc_input_design.md) | frc_input.py data model design |
| [`subtask3_frc_writer_design.md`](subtask3_frc_writer_design.md) | frc_writer.py implementation plan |
| [`subtask5b_msi2lmp_segfault_analysis.md`](subtask5b_msi2lmp_segfault_analysis.md) | msi2lmp segfault root cause and fix |

### 🗺️ Reference & Future Planning

These are ongoing reference materials or future planning documents.

| File | Description | Status |
|------|-------------|--------|
| [`v0.1_calf20_co2_diffusion_reference.md`](v0.1_calf20_co2_diffusion_reference.md) | v0.1 reference system: CALF-20 + CO₂ pipeline | Draft |
| [`extreme_validation_calf20_co2.md`](extreme_validation_calf20_co2.md) | Comprehensive validation for CALF-20 pipeline | Planning |
| [`phase14_unified_frc_builder.md`](phase14_unified_frc_builder.md) | Unified FRC builder architecture proposal | Planning |
| [`phase15_workspace_migration.md`](phase15_workspace_migration.md) | Migrate workspaces to new FRC Builder API | Planning |
| [`phase16_combined_mof_co2.md`](phase16_combined_mof_co2.md) | Combined MOF+CO2 workspace design | Planning |
| [`phase16_4_frc_validation.md`](phase16_4_frc_validation.md) | FRC parameter validation plan | Planning |
| [`phase18_bond_increments_remediation.md`](phase18_bond_increments_remediation.md) | Fix bond increments extraction | Planning |
| [`phase19_bond_connectivity_remediation.md`](phase19_bond_connectivity_remediation.md) | Fix bond connectivity in merged structures | Planning |
| [`migrate_frc_from_scratch.md`](migrate_frc_from_scratch.md) | Migration plan: delete frc_from_scratch.py | Planning |

## Archived Plans

Completed and historical planning documents are moved to:

- **[`docs/archive/cvff_base_minimization/`](../docs/archive/cvff_base_minimization/)** - 28 historical plan files from the CVFF base minimization thrust (Dec 2025)

## Naming Conventions

- `phaseNN_*.md` - Numbered phases of multi-step efforts
- `subtaskN_*.md` - Subtasks of larger implementation plans  
- `*_plan.md` or `*_design.md` - General planning/design documents
- `*_remediation.md` - Bug fix or issue remediation plans
- `*_validation.md` - Validation and testing plans

## Contributing

When creating new plans:

1. Use descriptive filenames following conventions above
2. Include a status field (Active, Completed, Planning, Draft)
3. Include completion date when finished
4. Move completed plans to `docs/archive/` periodically
