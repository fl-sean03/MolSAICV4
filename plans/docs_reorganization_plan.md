# Documentation Reorganization Plan

## Current State Analysis

### Problem Summary
Documentation is scattered across multiple locations without clear organization:

1. **Plans scattered**: 18+ files in `plans/` (root), 28 files in `docs/plans/cvff_base_minimization/`
2. **DevGuides mixed**: Contains guides, thrust logs, reports, and handoff docs all at same level
3. **Root docs/ flat**: No categorization - user docs mixed with dev docs mixed with reference
4. **No navigation**: No README.md to help users find what they need

### Current File Inventory

#### `docs/` Root (12 files - mixed purposes)
| File | Type | Purpose |
|------|------|---------|
| QUICKSTART.md | User Guide | Getting started with AS2 hydration |
| WORKFLOWS.md | User Guide | Code-first workflow pattern |
| ONBOARDING_USM_UPM_MOLSAIC.md | User Guide | Onboarding documentation |
| ACCEPTANCE.md | Reference | Acceptance criteria for AS2 |
| ADAPTER_CONTRACT.md | Reference | External adapter API contract |
| manifest.v1.schema.json | Reference | JSON schema file |
| MOLSAIC_FIT_AND_USAGE.md | Reference | MOLSAIC package documentation |
| USM_FIT_AND_USAGE.md | Reference | USM package documentation |
| msi2lmp_standalone_usage.md | Reference | msi2lmp usage guide |
| ions-in-water-workflows.md | Workflow | Ions workflow documentation |
| REPO_FIT_AND_MXENES_WORKFLOWS.md | Workflow | MXenes workflow documentation |
| ITERATIVE_DEVELOPMENT_PLAYBOOK.md | Methodology | Development methodology |

#### `docs/DevGuides/` (9 files - mixed purposes)
| File | Type | Purpose |
|------|------|---------|
| DevGuide_v0.1.1.md | Guide | Version 0.1.1 development guide |
| DevGuide_v0.1.2.md | Guide | Version 0.1.2 development guide |
| DevGuide_v0.1.3.md | Guide | Version 0.1.3 development guide |
| DevGuide_CALF20_msi2lmp_frc_contract.md | Guide | CALF20 FRC contract guide |
| v0.1.1_report.md | Report | Version 0.1.1 completion report |
| v0.1.2_report.md | Report | Version 0.1.2 completion report |
| thrust_log_cvff_base_minimization.md | Thrust Log | CVFF minimization debug log |
| thrust_log_nist_calf20_msi2lmp_stall.md | Thrust Log | msi2lmp stall debug log |
| msi2lmp_diagnostics_repro.md | Diagnostic | msi2lmp diagnostics |
| context_reset_handoff_nist_msi2lmp_nonbond_only.md | Handoff | Context reset handoff doc |

#### `docs/methods/` (2 files - well organized)
- MSI2LMP_FRC_REQUIREMENTS.md
- TERMSET_FRC_PIPELINE.md

#### `docs/plans/cvff_base_minimization/` (28 files)
Historical plan documents for CVFF base minimization thrust

#### `plans/` Root (18+ files - scattered)
Various plan documents at different stages of completion

---

## Proposed Structure

```
docs/
├── README.md                           # Navigation index
├── getting-started/                    # User onboarding
│   ├── QUICKSTART.md
│   ├── ONBOARDING_USM_UPM_MOLSAIC.md
│   └── WORKFLOWS.md
├── reference/                          # API and contract docs
│   ├── ADAPTER_CONTRACT.md
│   ├── ACCEPTANCE.md
│   ├── manifest.v1.schema.json
│   ├── MOLSAIC_FIT_AND_USAGE.md
│   ├── USM_FIT_AND_USAGE.md
│   └── msi2lmp_standalone_usage.md
├── workflows/                          # Workflow-specific guides
│   ├── ions-in-water-workflows.md
│   ├── REPO_FIT_AND_MXENES_WORKFLOWS.md
│   └── ITERATIVE_DEVELOPMENT_PLAYBOOK.md
├── development/                        # Developer documentation
│   ├── guides/                         # Version development guides
│   │   ├── DevGuide_v0.1.1.md
│   │   ├── DevGuide_v0.1.2.md
│   │   ├── DevGuide_v0.1.3.md
│   │   └── DevGuide_CALF20_msi2lmp_frc_contract.md
│   ├── reports/                        # Version completion reports
│   │   ├── v0.1.1_report.md
│   │   └── v0.1.2_report.md
│   └── thrust-logs/                    # Systematic debugging logs
│       ├── README.md                   # Thrust log methodology
│       ├── thrust_log_cvff_base_minimization.md
│       ├── thrust_log_nist_calf20_msi2lmp_stall.md
│       ├── msi2lmp_diagnostics_repro.md
│       └── context_reset_handoff_nist_msi2lmp_nonbond_only.md
├── methods/                            # Methods documentation (unchanged)
│   ├── MSI2LMP_FRC_REQUIREMENTS.md
│   └── TERMSET_FRC_PIPELINE.md
└── archive/                            # Historical plans (read-only reference)
    └── cvff_base_minimization/         # Moved from docs/plans/
        └── [28 files]

plans/                                  # Active plans only (root level)
├── README.md                           # Plan index and status
└── [active plan files]
```

---

## Implementation Tasks

### Subtask 1: Create Directory Structure
Create the new directory structure:
- `docs/getting-started/`
- `docs/reference/`
- `docs/workflows/`
- `docs/development/guides/`
- `docs/development/reports/`
- `docs/development/thrust-logs/`
- `docs/archive/`

### Subtask 2: Create Navigation README
Create `docs/README.md` with:
- Overview of documentation structure
- Links to key documents by category
- Quick navigation for common tasks

### Subtask 3: Move User Documentation
Move files to `docs/getting-started/`:
- QUICKSTART.md
- ONBOARDING_USM_UPM_MOLSAIC.md
- WORKFLOWS.md

### Subtask 4: Move Reference Documentation
Move files to `docs/reference/`:
- ADAPTER_CONTRACT.md
- ACCEPTANCE.md
- manifest.v1.schema.json
- MOLSAIC_FIT_AND_USAGE.md
- USM_FIT_AND_USAGE.md
- msi2lmp_standalone_usage.md

### Subtask 5: Move Workflow Documentation
Move files to `docs/workflows/`:
- ions-in-water-workflows.md
- REPO_FIT_AND_MXENES_WORKFLOWS.md
- ITERATIVE_DEVELOPMENT_PLAYBOOK.md

### Subtask 6: Reorganize DevGuides
Move DevGuides content to `docs/development/`:
- guides/ ← DevGuide_*.md files
- reports/ ← v0.1.*.report.md files
- thrust-logs/ ← thrust_log_*.md, diagnostics, handoff docs

### Subtask 7: Archive Historical Plans
Move `docs/plans/cvff_base_minimization/` to `docs/archive/cvff_base_minimization/`

### Subtask 8: Consolidate Root Plans
Review `plans/` root files:
- Keep active/in-progress plans
- Archive completed plans to `docs/archive/`
- Create `plans/README.md` index

### Subtask 9: Update Cross-References
Search and update internal links in all moved documents to reflect new paths

### Subtask 10: Cleanup Empty Directories
Remove empty `docs/DevGuides/` and `docs/plans/` after migration

---

## Benefits

1. **Discoverability**: Clear categories make it easy to find relevant docs
2. **Separation of Concerns**: User docs vs dev docs vs reference clearly separated
3. **Navigation**: README.md provides quick navigation
4. **Historical Context**: Archive preserves completed work without cluttering active docs
5. **Scalability**: Structure accommodates future documentation growth

---

## Risk Mitigation

- **Broken Links**: Subtask 9 addresses internal link updates
- **Git History**: Use `git mv` to preserve file history
- **External References**: Add redirects or update any external documentation pointing to old paths
