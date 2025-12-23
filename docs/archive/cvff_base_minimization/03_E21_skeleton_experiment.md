# E21 Skeleton Experiment Implementation Plan

## Objective

Test whether msi2lmp.exe v3.9.6 requires actual base type content (H-Content hypothesis) or just the structural headers from a working .frc file (H-Structure hypothesis).

## Key Insight from Context Analysis

### Working Asset Structure (`cvff_Base_MXenes.frc` - 5571 lines)

```
Lines 1-18:     Preamble + version lines
Lines 27-42:   #define cvff_nocross_nomorse macro block
Lines 44-65:   #define cvff macro block  
Lines 67-83:   #define cvff_nocross macro block
Lines 85-105:  #define cvff_nomorse macro block

Lines 108-341:   #atom_types cvff (233 base types)
Lines 343-571:   #equivalence cvff (229 entries)
Lines 573-759:   #auto_equivalence cvff_auto (187 entries)
Lines 761-766:   #hbond_definition cvff (5 lines)
Lines 768-918:   #morse_bond cvff (151 entries)
Lines 920-1158:  #quadratic_bond cvff (239 entries)
Lines 1160-1735: #quadratic_angle cvff (576 entries)
Lines 2141-2294: #torsion_1 cvff (154 entries)
Lines 2373-2430: #out_of_plane cvff (58 entries)
Lines 4529-4667: #nonbond(12-6) cvff (139 entries)
```

### CALF20 TermSet Summary

- 5 atom types: C_MOF, H_MOF, N_MOF, O_MOF, Zn_MOF
- 6 bond types
- 11 angle types
- 16 dihedral types
- 6 improper types

## E21 Skeleton Approach

Extract EXACT headers from the working asset but populate each section with ONLY CALF20 types:

```
!BIOSYM forcefield          1

#version cvff.frc  1.2  13-Dec-90
... (all 17 version lines from asset) ...

#define cvff
... (exact macro table from asset) ...

#atom_types  cvff

> Atom type definitions for any variant of cvff
> Masses from CRC 1973/74 pages B-250.

!Ver  Ref  Type    Mass      Element  Connections   Comment
!---- ---  ----  ----------  -------  -----------------------------------------
 2.0  18   C_MOF  12.011     C        4  UPM CALF20
 2.0  18   H_MOF   1.008     H        1  UPM CALF20
 2.0  18   N_MOF  14.007     N        3  UPM CALF20
 2.0  18   O_MOF  15.999     O        2  UPM CALF20
 2.0  18   Zn_MOF 65.38      Zn       6  UPM CALF20

#equivalence  cvff

... (exact column headers from asset) ...
 1.0   1    C_MOF  C_MOF  C_MOF  C_MOF  C_MOF  C_MOF
 1.0   1    H_MOF  H_MOF  H_MOF  H_MOF  H_MOF  H_MOF
 ... (ONLY CALF20 types) ...

... (continue for all sections) ...
```

## Implementation Details

### Step 1: Create E21 Builder Function

Add to [`frc_from_scratch.py`](../src/upm/src/upm/build/frc_from_scratch.py):

```python
def build_frc_e21_asset_skeleton(
    termset: dict[str, Any],
    parameterset: dict[str, Any],
    *,
    out_path: str | Path,
) -> str:
    """Build CVFF .frc with asset skeleton headers but ONLY CALF20 types.
    
    E21 hypothesis test: Does msi2lmp.exe require base type content,
    or just the structural headers from a working .frc file?
    
    This function:
    1. Copies the exact preamble + version lines from cvff_Base_MXenes.frc
    2. Copies the exact #define macro blocks from the asset
    3. For each section, copies exact headers (incl. column header comments)
    4. Populates section data with ONLY CALF20 types from termset/parameterset
    """
```

### Step 2: Asset Header Extraction

The function will extract these exact headers from the asset:

| Section | Header Line | Description Lines | Column Headers |
|---------|-------------|-------------------|----------------|
| atom_types | `#atom_types\tcvff` | 2 lines | 2 lines |
| equivalence | `#equivalence\tcvff ` | 1 line | 4 lines |
| auto_equivalence | `#auto_equivalence\tcvff_auto` | 0 lines | 4 lines |
| hbond_definition | `#hbond_definition\tcvff ` | 0 lines | 0 lines |
| morse_bond | `#morse_bond\tcvff ` | 1 line | 2 lines |
| quadratic_bond | `#quadratic_bond\tcvff ` | 1 line | 2 lines |
| quadratic_angle | `#quadratic_angle\tcvff ` | 1 line | 2 lines |
| torsion_1 | `#torsion_1\tcvff ` | 1 line | 2 lines |
| out_of_plane | `#out_of_plane\tcvff ` | 1 line | 2 lines |
| nonbond(12-6) | `#nonbond(12-6)\tcvff ` | directives + 2 lines | 2 lines |

### Step 3: Add E21 to Preset Registry

```python
# In CVFF_FRC_EXPERIMENT_PRESETS:
"E21": "ASSET_SKELETON",  # Special marker for skeleton approach
```

### Step 4: Update resolve_cvff_frc_experiment_preset

Handle E21 as a special case that triggers the skeleton builder path.

## Section-by-Section Data Population

### #atom_types cvff
- Use exact column format from asset line 113-114
- Populate with: C_MOF, H_MOF, N_MOF, O_MOF, Zn_MOF
- Include mass, element, connections from parameterset

### #equivalence cvff
- Use exact column format from asset lines 347-350
- Populate with CALF20 types self-mapping to themselves

### #auto_equivalence cvff_auto
- Use exact column format from asset lines 575-579
- Populate with CALF20 types with 10-column format

### #quadratic_bond cvff
- Use placeholder parameters for 6 bond types

### #quadratic_angle cvff
- Use placeholder parameters for 11 angle types

### #torsion_1 cvff
- Use placeholder parameters for 16 dihedral types
- Include wildcard fallback

### #out_of_plane cvff
- Use placeholder parameters for 6 improper types
- Include wildcard fallback

### #nonbond(12-6) cvff
- Use exact directives: `@type A-B` and `@combination geometric`
- Convert LJ sigma/epsilon to A/B form for 5 atom types

## Expected Outcome

**If E21 PASSES (exit_code=0, CALF20.data > 0 bytes):**
- H-Structure hypothesis confirmed
- Skeleton approach is viable
- Minimal base is just headers + CALF20 types (~200 lines)
- Major victory for minimization goal

**If E21 FAILS (exit_code=143 timeout or 139 segfault, CALF20.data=0):**
- H-Content hypothesis confirmed
- Parser requires actual base type definitions
- Must proceed to truncation experiments E16-E19
- Need to find minimum viable base content

## Execution Command

```bash
cd workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1

# Update config.json to set frc_experiment_preset to E21
# Then run:
python run.py --config config.json
```

## Files to Modify

1. [`src/upm/src/upm/build/frc_from_scratch.py`](../src/upm/src/upm/build/frc_from_scratch.py)
   - Add `build_frc_e21_asset_skeleton()` function
   - Add E21 to `CVFF_FRC_EXPERIMENT_PRESETS`
   - Update `resolve_cvff_frc_experiment_preset()` to handle E21

2. [`workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/run.py`](../workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/run.py)
   - May need to handle E21 special case if skeleton builder has different signature

## Success Criteria

- [x] E21 preset implemented and runnable
- [ ] Experiment executed with clear PASS/FAIL result
- [ ] Results documented in experiment_results_E21.json
- [ ] Recommendation provided for next steps

## Risk Mitigation

If E21 shows unexpected behavior (partial output, different error):
- Document exact stdout/stderr
- Compare with E0-E15 behavior patterns
- May indicate intermediate hypothesis between H-Structure and H-Content
