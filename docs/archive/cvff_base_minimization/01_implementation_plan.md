# CVFF Base Minimization Implementation Plan

## Overview

This plan outlines the implementation of experiments to find the minimum viable CVFF `.frc` base for msi2lmp.exe compatibility with the CALF-20 system.

## Current State

- **Working solution**: E20 with full 5571-line embedded base → PASS (exit 0)
- **Goal**: Reduce to <2800 lines while maintaining functionality
- **Constraint**: Must not read any `.frc` from disk at runtime

## Implementation Architecture

### 1. Pruned Base Builder Function

Add to `frc_from_scratch.py`:

```python
@dataclass
class CvffPruneOptions:
    """Options for pruning CVFF base content."""
    
    # Section toggles (False = remove entire section)
    include_cross_terms: bool = True  # bond-bond, bond-angle, angle-angle-*, oop-oop
    include_cvff_auto: bool = True    # All cvff_auto labeled sections
    include_bond_increments: bool = True
    
    # Entry limits per section (0 = include all, N = keep first N entries)
    max_atom_types: int = 0
    max_equivalence: int = 0
    max_auto_equivalence: int = 0
    max_morse_bond: int = 0
    max_quadratic_bond: int = 0
    max_quadratic_angle: int = 0
    max_torsion: int = 0
    max_out_of_plane: int = 0
    max_nonbond: int = 0


def build_frc_cvff_with_pruned_base(
    termset: dict[str, Any],
    parameterset: dict[str, Any],
    out_path: str | Path,
    prune: CvffPruneOptions | None = None,
) -> str:
    """Build CVFF .frc with configurable base pruning for minimization experiments."""
```

### 2. Base Content Parser

Create utility to parse the embedded base into sections:

```python
def parse_embedded_base_sections(content: str) -> dict[str, list[str]]:
    """Parse embedded base into section name -> lines mapping."""
    sections = {}
    current_section = "preamble"
    current_lines = []
    
    for line in content.splitlines():
        if line.startswith("#") and not line.startswith("#version"):
            # Save previous section
            sections[current_section] = current_lines
            # Start new section
            current_section = line.split()[0]  # e.g., "#atom_types"
            current_lines = [line]
        else:
            current_lines.append(line)
    
    sections[current_section] = current_lines
    return sections
```

### 3. Experiment Preset Registry

Add M-series presets:

```python
CVFF_MINIMIZATION_PRESETS: dict[str, CvffPruneOptions] = {
    # Phase 1: Section-level removal
    "M01": CvffPruneOptions(include_bond_increments=False),
    "M02": CvffPruneOptions(include_cvff_auto=False),
    "M03": CvffPruneOptions(include_cross_terms=False, include_cvff_auto=False),
    "M04": CvffPruneOptions(
        include_cross_terms=False, 
        include_cvff_auto=False, 
        include_bond_increments=False
    ),
    
    # Phase 2: Entry-level pruning (after Phase 1 determines which sections are needed)
    "M10": CvffPruneOptions(
        include_cross_terms=False,
        include_cvff_auto=False,
        include_bond_increments=False,
        max_atom_types=100,  # Reduce from 233
    ),
    # ... more presets based on Phase 1 results
}
```

## Execution Phases

### Phase 1: Section-Level Pruning (Subtask 1)

**Objective**: Determine which sections can be removed entirely.

**Experiments**:
| ID | Configuration | Expected Lines |
|----|---------------|----------------|
| M01 | Remove bond_increments only | ~4668 |
| M02 | Remove all cvff_auto sections | ~2669 |
| M03 | Remove cross-terms + cvff_auto | ~2141 |
| M04 | M03 + remove bond_increments | ~2141 |
| M05 | Keep only essential sections | ~1500 |

**Essential sections hypothesis**:
- Preamble + #define blocks (required for parser)
- #atom_types cvff
- #equivalence cvff
- #hbond_definition cvff
- #morse_bond cvff (or #quadratic_bond cvff)
- #quadratic_angle cvff
- #torsion_1 cvff
- #out_of_plane cvff
- #nonbond(12-6) cvff

### Phase 2: Entry-Level Pruning (Subtask 2)

**Objective**: Reduce entry count within essential sections.

**Approach**: Binary search on each section.

**Example for #atom_types**:
```
Full: 233 entries → Test
Half: 116 entries → Test
Quarter: 58 entries → Test
...continue until failure
```

**Key insight from E21**: Skeleton with headers-only failed with validation error. This suggests some base entries ARE required, not just headers.

### Phase 3: Final Minimization (Subtask 3)

**Objective**: Produce and validate the minimal embedded base.

**Deliverables**:
1. Minimal `CVFF_MINIMAL_BASE_CONTENT` string
2. Updated `build_frc_cvff_with_minimal_base()` function
3. Determinism verification
4. Documentation update

## Test Strategy

### Per-Experiment Validation

```bash
# For each M-series experiment:
cd workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1

# Update config with experiment preset
# Run workspace
python run.py --config config_M01.json

# Check results
cat outputs_M01/msi2lmp_run/result.json
wc -l outputs_M01/frc_files/ff_exp_M01.frc
stat outputs_M01/msi2lmp_run/CALF20.data
```

### Determinism Verification

```bash
# Clean run 1
rm -rf outputs_minimal && python run.py --config config_minimal.json
sha256sum outputs_minimal/frc_files/*.frc outputs_minimal/msi2lmp_run/CALF20.data > run1.sha256

# Clean run 2
rm -rf outputs_minimal && python run.py --config config_minimal.json
sha256sum outputs_minimal/frc_files/*.frc outputs_minimal/msi2lmp_run/CALF20.data > run2.sha256

# Verify match
diff run1.sha256 run2.sha256
```

## Subtask Breakdown

### Subtask 1: Implement Pruned Base Builder + Phase 1 Experiments

**Scope**:
1. Add `CvffPruneOptions` dataclass
2. Add `parse_embedded_base_sections()` utility
3. Add `build_frc_cvff_with_pruned_base()` function
4. Add M01-M05 presets
5. Update workspace to handle M-series presets
6. Execute M01-M05 and record results
7. Update thrust log with Phase 1 findings

### Subtask 2: Phase 2 Entry-Level Pruning

**Scope**:
1. Based on Phase 1, identify required sections
2. Implement entry-level pruning in builder
3. Add M10-M19 presets for binary search
4. Execute experiments systematically
5. Document minimum entry counts per section

### Subtask 3: Final Minimization + Validation

**Scope**:
1. Create minimal base content string
2. Add `build_frc_cvff_with_minimal_base()` function
3. Add `CVFF_MINIMAL_BASE_CONTENT` constant
4. Execute M20+ final candidate tests
5. A/B/A verification
6. Determinism proof
7. Update documentation
8. Optionally make minimal base the default

## Risk Mitigation

### Risk: Validation error (exit 7) vs stall (exit 143)

The E16-E19 experiments showed that truncating sections prevents stalls but causes validation errors. This suggests:
- Some sections CAN be removed (structure preserved)
- Some content within remaining sections IS required

**Mitigation**: Track both exit code AND error message for each experiment.

### Risk: System-dependent minimum

The minimum viable base might be specific to CALF-20. Other systems with different atom types might need different base entries.

**Mitigation**: Document that the minimal base is validated for CALF-20 only; full base remains available for other systems.

## Success Criteria

1. ✅ M-series experiments produce clear PASS/FAIL results
2. ✅ Minimum viable base identified (<2800 lines target)
3. ✅ CALF20.data production verified with minimal base
4. ✅ Determinism confirmed (identical sha256 across runs)
5. ✅ Thrust log updated with complete experiment results
6. ✅ Minimal base builder function implemented and tested

## Timeline Estimate

- Subtask 1 (Phase 1): Implement builder + M01-M05 experiments ✅ COMPLETE
- Subtask 2 (Phase 2): Entry-level pruning M10-M16 (25%) ✅ COMPLETE
- Subtask 3 (Phase 3): Validation + minimal base creation ✅ COMPLETE
- Subtask 4 (Phase 4): Extended experiments M17-M22 (12.5% → 0%) 🔄 IN PROGRESS

## Phase 4: Extended Minimization (0-25% Entry Range)

### Objective

Test the complete range from 25% down to 0% entries to find the **absolute minimum viable base**.

### Experiment Matrix

| Preset | Entry % | Expected Lines | Configuration |
|--------|---------|----------------|---------------|
| M16 | 25% | 1057 | ✅ PASS (baseline) |
| M17 | 12.5% | ~600 | Half of M16 |
| M18 | 10% | ~500 | Uniform 10% |
| M19 | 5% | ~300 | Uniform 5% |
| M20 | 2.5% | ~200 | Uniform 2.5% |
| M21 | 1% | ~100 | Minimal non-zero |
| M22 | 0% | ~50 | Headers only (0 entries) |

### Entry Counts Per Section

| Section | Full | 25% | 12.5% | 10% | 5% | 2.5% | 1% | 0% |
|---------|------|-----|-------|-----|-----|------|-----|-----|
| atom_types | 233 | 58 | 29 | 23 | 12 | 6 | 2 | 0 |
| equivalence | 229 | 57 | 29 | 23 | 11 | 6 | 2 | 0 |
| morse_bond | 152 | 38 | 19 | 15 | 8 | 4 | 2 | 0 |
| quadratic_bond | 240 | 60 | 30 | 24 | 12 | 6 | 2 | 0 |
| quadratic_angle | 576 | 144 | 72 | 58 | 29 | 14 | 6 | 0 |
| torsion_1 | 154 | 39 | 19 | 15 | 8 | 4 | 2 | 0 |
| out_of_plane | 58 | 15 | 7 | 6 | 3 | 1 | 1 | 0 |
| nonbond | 139 | 35 | 17 | 14 | 7 | 3 | 1 | 0 |
| bond_increments | 902 | 225 | 113 | 90 | 45 | 23 | 9 | 0 |

### Success Criteria

1. Identify the exact minimum % that still produces valid CALF20.data
2. Determine if 0% (headers-only) works or fails
3. If 0% fails, use binary search between last PASS and first FAIL to find exact minimum
4. Document all results for completeness

### Implementation

Add M17-M22 presets to `CVFF_MINIMIZATION_PRESETS`:

```python
"M17": CvffPruneOptions(include_cross_terms=False, include_cvff_auto=False,
    max_atom_types=29, max_equivalence=29, max_morse_bond=19, max_quadratic_bond=30,
    max_quadratic_angle=72, max_torsion=19, max_out_of_plane=7, max_nonbond=17,
    max_bond_increments=113),  # 12.5%

"M18": CvffPruneOptions(...),  # 10%
"M19": CvffPruneOptions(...),  # 5%
"M20": CvffPruneOptions(...),  # 2.5%
"M21": CvffPruneOptions(...),  # 1%
"M22": CvffPruneOptions(include_cross_terms=False, include_cvff_auto=False,
    max_atom_types=1, max_equivalence=1, max_morse_bond=1, max_quadratic_bond=1,
    max_quadratic_angle=1, max_torsion=1, max_out_of_plane=1, max_nonbond=1,
    max_bond_increments=1),  # Near-0% (minimum 1 entry each)
```

*Ready to switch to Orchestrator mode for Phase 4 implementation.*
