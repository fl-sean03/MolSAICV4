# Subtask 4A-1: CVFF Base Minimization Search

## Objective

Find the **minimum viable CVFF base content** that satisfies msi2lmp.exe parser requirements through systematic testing.

## Current Knowledge

| Test | Lines | Source | Result |
|------|-------|--------|--------|
| E0-E15 from-scratch | 118-318 | Generated | **STALL** |
| Asset preamble + CALF20 | ~200 | Truncated asset | **STALL** |
| Asset truncated + CALF20 | ~1000 | Truncated asset | **SEGFAULT (139)** |
| Full working asset | 5571 | cvff_Base_MXenes.frc | **PASS** ✓ |

**Gaps**:
1. No testing between 1000-5571 lines (truncation approach)
2. No explicit test of asset skeleton (all headers, no base data entries)

## Hypothesis

The msi2lmp.exe parser may require:
1. Complete section structure (all required sections present)
2. Valid section terminators/boundaries
3. Possibly: minimum content in certain sections (atom_types, equivalences, nonbond)

**Two competing hypotheses:**
- **H-Structure**: Parser needs just the structure (headers) → Skeleton approach works
- **H-Content**: Parser needs actual base type definitions → Need significant base content

## Test Strategy

### Phase 0: Skeleton Test (Critical - Tests Structure vs Content)

| Experiment | Approach | Description |
|------------|----------|-------------|
| **E21** | Asset Skeleton | ALL section headers from working asset, NO base data entries, ONLY CALF20 custom types |

**E21 Implementation:**
```
!BIOSYM forcefield 1
#version lines from asset...
#define sections from asset...

#atom_types cvff
> (headers from asset)
> C_MOF    12.011  C  0   # ONLY CALF20 - no base types like h, c, c', o, n
> H_MOF    1.008   H  0
> N_MOF    14.007  N  0
> O_MOF    15.999  O  0
> Zn_MOF   65.38   Zn 0

#equivalence cvff
> (headers from asset)
> C_MOF  C_MOF  ...  # ONLY CALF20 equivalences

... (all other sections with headers but ONLY CALF20 data) ...

#nonbond(12-6) cvff
> (headers from asset)
> C_MOF    epsilon  sigma
> H_MOF    ...
> (ONLY CALF20 nonbond params)
```

**If E21 PASSES:** Skeleton is sufficient, embed minimal structure (~500 lines)
**If E21 FAILS (expected based on E0-E15):** Base content required, proceed to Phase 1

### Phase 1: Section-Boundary Truncation (Binary Search)

| Experiment | Lines | After Section | Removes |
|------------|-------|---------------|---------|
| E16 | ~4668 | #nonbond(12-6) | bond_increments, references |
| E17 | ~4528 | #out_of_plane cvff_auto | + nonbond section |
| E18 | ~2669 | #angle-angle cvff | + all cvff_auto sections |
| E19 | ~767 | #hbond_definition | + all bonded sections |

### Phase 2: Minimal Viable Base Identification

Once we find the approximate threshold, identify:
1. Which sections are required
2. Minimum entries needed per section
3. Whether we can use empty/stub sections

## Execution Plan

### Step 1: Create truncation presets

Add to [`frc_from_scratch.py`](../src/upm/src/upm/build/frc_from_scratch.py):

```python
def create_asset_truncated_preset(termset: dict, parameterset: dict, max_lines: int) -> str:
    """Create a preset by truncating the working asset at a line count.
    
    This reads the working asset and truncates it at max_lines,
    then appends CALF20 custom types to each section.
    """
    asset_path = Path(__file__).parent.parent.parent.parent.parent.parent / \
                 "workspaces/forcefields/cvff_Base_MXenes.frc"
    with open(asset_path) as f:
        lines = f.readlines()[:max_lines]
    
    # Find and append to sections as needed
    # ... implementation details
    return "".join(lines)
```

### Step 2: Define experiment presets

```python
PRESET_E16_ASSET_3000 = "asset_truncated_3000"
PRESET_E17_ASSET_2000 = "asset_truncated_2000"  # or 4000 based on E16
PRESET_E18_ASSET_NARROW = "asset_truncated_XXX"  # TBD
```

### Step 3: Create shell script for experiments

Create `run_experiments_E16_E20.sh`:

```bash
#!/bin/bash
# Binary search minimization experiments

for exp in E16 E17 E18 E19 E20; do
    echo "Running $exp..."
    python run.py --frc_experiment_preset=$exp
done
```

### Step 4: Execute and document results

Record in `experiment_results_E16_E20.json`:

```json
{
  "E16": {
    "preset": "asset_truncated_3000",
    "lines": 3000,
    "exit_code": null,
    "result": null
  }
}
```

## Working Asset Section Analysis (cvff_Base_MXenes.frc)

**Exact section boundaries identified from file analysis:**

| Section | Start Line | End Line | Lines |
|---------|------------|----------|-------|
| Preamble + version | 1 | 18 | 18 |
| #define cvff_nocross_nomorse | 27 | 42 | 16 |
| #define cvff | 44 | 65 | 22 |
| #define cvff_nocross | 67 | 83 | 17 |
| #define cvff_nomorse | 85 | 106 | 22 |
| **#atom_types cvff** | 108 | 341 | 234 |
| **#equivalence cvff** | 343 | 571 | 229 |
| **#auto_equivalence cvff_auto** | 573 | 759 | 187 |
| #hbond_definition cvff | 761 | 766 | 6 |
| #morse_bond cvff | 768 | 918 | 151 |
| #quadratic_bond cvff | 920 | 1158 | 239 |
| #quadratic_angle cvff | 1160 | 1735 | 576 |
| #bond-bond cvff | 1737 | 1937 | 201 |
| #bond-angle cvff | 1939 | 2139 | 201 |
| #torsion_1 cvff | 2141 | 2294 | 154 |
| #angle-angle-torsion_1 cvff | 2296 | 2371 | 76 |
| #out_of_plane cvff | 2373 | 2430 | 58 |
| #out_of_plane-out_of_plane cvff | 2432 | 2469 | 38 |
| #angle-angle cvff | 2471 | 2668 | 198 |
| #morse_bond cvff_auto | 2670 | 3309 | 640 |
| #quadratic_bond cvff_auto | 3311 | 3950 | 640 |
| #quadratic_angle cvff_auto | 3952 | 4287 | 336 |
| #torsion_1 cvff_auto | 4289 | 4511 | 223 |
| #out_of_plane cvff_auto | 4513 | 4527 | 15 |
| **#nonbond(12-6) cvff** | 4529 | 4667 | 139 |
| #bond_increments cvff | 4669 | 5373 | 705 |
| #reference sections | 5375 | 5571 | 197 |

## Strategic Truncation Points

Based on section analysis, these are **safe truncation points** at section boundaries:

| Truncation ID | After Section | Line | Cumulative Lines |
|---------------|---------------|------|------------------|
| T1 | #hbond_definition | 767 | ~770 |
| T2 | #angle-angle cvff | 2669 | ~2670 |
| T3 | #out_of_plane cvff_auto | 4528 | ~4530 |
| T4 | #nonbond(12-6) cvff | 4668 | ~4670 |
| T5 | Full file | 5571 | 5571 ✓ PASS |

**Key insight**: The 1000-line truncation that caused SEGFAULT likely cut into the middle of `#quadratic_bond cvff` section (lines 920-1158), corrupting the section structure.

## Updated Binary Search Plan

Based on section boundaries, test at these strategic points:

| Experiment | Truncation | Lines | What's Removed | Hypothesis |
|------------|------------|-------|----------------|------------|
| E16 | T4 | ~4668 | bond_increments, references | Likely PASS |
| E17 | T3 | ~4528 | + nonbond section | Critical test |
| E18 | T2 | ~2669 | + all cvff_auto sections | May fail |
| E19 | T1 | ~767 | + all bonded sections | Likely fail |
| E20 | Based on results | TBD | Narrow down | Refine minimum |

## Success Criteria

1. Identify minimum line count that produces PASS
2. Identify which sections are required vs optional
3. Document findings in thrust log Section 15
4. Use minimal base for implementation (reduce from 5571 lines)

## Risk Mitigation

If binary search is inconclusive (parser needs specific section content, not just line count):
- Fallback to full 5571-line base (proven to work)
- Accept larger embedded base size (~160KB)
- Document as technical debt for future optimization

## Next Steps

1. Switch to Code mode to implement truncation presets
2. Run experiments E16-E20 (starting with E16 = T4)
3. Document results
4. Proceed with implementation using determined minimum
