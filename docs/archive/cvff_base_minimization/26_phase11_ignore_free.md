# Phase 11: msi2lmp.exe -ignore-free Operation Plan

**Date**: 2025-12-21
**Status**: ✅ COMPLETE
**Prerequisites**: Phase 10 complete (M29 validation confirmed -ignore requirement)

## 1) Executive Summary

Phase 10 validation confirmed that **M29 requires the `-ignore` flag** for nonbond-only workflows like CALF20. This phase explores options for supporting msi2lmp.exe operation **without** the `-ignore` flag.

### Key Finding from Phase 10

```
Error: Unable to find bond data for Zn_MO N_MOF
Exit Code: 12 (expected: 0)
CALF20.data: NOT CREATED
```

**Root cause**: M29's `max_*=-1` settings remove ALL base entries from bonded sections (bonds, angles, torsions, OOP), while the CALF20 parameterset only contains nonbond parameters (LJ epsilon/sigma, masses). Without bonded parameters, msi2lmp.exe fails when looking for bond data.

## 2) CALF20 Bonded Topology Analysis

From the MDF file, CALF20 requires the following bonded parameters:

### 2.1 Bond Types Required (6 types)
| Bond Pair | Atom Types | msi2lmp Truncated |
|-----------|------------|-------------------|
| Zn-N | Zn_MOF - N_MOF | Zn_MO - N_MOF |
| Zn-O | Zn_MOF - O_MOF | Zn_MO - O_MOF |
| N-C | N_MOF - C_MOF | N_MOF - C_MOF |
| N-N | N_MOF - N_MOF | N_MOF - N_MOF |
| C-O | C_MOF - O_MOF | C_MOF - O_MOF |
| C-H | C_MOF - H_MOF | C_MOF - H_MOF |

### 2.2 Angle Types Required (11 types)
Based on the topology (28 angles total):
- N-Zn-N, N-Zn-O, O-Zn-O
- Zn-N-C, Zn-N-N, N-N-C, C-N-C
- N-C-N, N-C-H, C-C-H
- Zn-O-C, O-C-O

### 2.3 Torsion Types Required (16 types)
Based on the topology (54 dihedrals total):
- Various 4-body combinations around the triazolate ring and carboxylate groups

### 2.4 OOP Types Required (3 types)
Based on the topology (5 out-of-plane centers):
- Planar centers on C atoms in triazolate ring

## 3) Options for -ignore-free Operation

### Option A: Use Full Embedded Base (Already Works)

**Function**: `build_frc_cvff_with_embedded_base()`
**Output Size**: ~5595 lines
**-ignore Required**: **NO** ✓

The full embedded base includes CVFF wildcard entries (`* *`, `* * *`, `* * * *`) that provide fallback parameters for any atom type combination. This already works without `-ignore`.

**Pros**:
- Already implemented and tested
- Maximum compatibility
- No additional development needed

**Cons**:
- Large file size (5595 lines vs 120 lines for M29)
- Includes many unused base entries

### Option B: Create M_BONDED Preset with Synthetic Generic Parameters

**Function**: New `build_frc_cvff_with_generic_bonded()`
**Output Size**: M29 base (~120 lines) + bonded entries (~30-50 lines) = ~150-170 lines
**-ignore Required**: **NO** (goal)

⚠️ **ANALYSIS FINDING**: CVFF does NOT have universal wildcards for bonds/angles!
- Torsions use `* X Y *` (wildcards only for first/last atoms)
- OOP uses `* X * *` (wildcards for peripheral atoms)
- Bonds and angles have NO universal wildcards

**Revised Approach**: Generate synthetic bonded parameters for custom types:
1. Parse MDF topology to find required bond/angle/torsion/OOP types
2. Generate generic parameters (e.g., from UFF or reasonable defaults)
3. Add these entries to the skeleton/M29 output

**Pros**:
- Smaller than full embedded base (150-170 lines vs 5595)
- Works without -ignore
- Only includes entries actually needed

**Cons**:
- Requires topology parsing
- Generic parameters may not be physically accurate
- More complex implementation

### Option C: Derive Bonded Parameters from Topology

**Function**: New `derive_bonded_parameters()` utility
**Output Size**: 120 lines + bonded entries (~30-50 additional lines)
**-ignore Required**: **NO** (goal)

Automatically derive required bonded parameters from:
1. Parse MDF topology to find all bond/angle/torsion/OOP types
2. Use generic forcefield parameters (UFF, DREIDING) as fallbacks
3. Allow user override with specific parameters

**Pros**:
- Minimal file size
- No unused entries
- Physically meaningful parameters (if using UFF/DREIDING)

**Cons**:
- Complex implementation
- Requires forcefield knowledge
- Parameters may not be accurate for specific chemistry

### Option D: User-Provided Bonded Parameters

**Function**: Existing builders with populated parameterset
**Output Size**: Depends on parameterset size
**-ignore Required**: **NO** (if all bonded params provided)

The user provides complete bonded parameters in the parameterset:
```python
parameterset = {
    "bonds": {
        ("Zn_MOF", "N_MOF"): {"k": 200.0, "r0": 2.1},
        # ... all 6 bond types
    },
    "angles": {
        ("N_MOF", "Zn_MOF", "N_MOF"): {"k": 50.0, "theta0": 109.5},
        # ... all 11 angle types
    },
    # ... torsions and OOP
}
```

**Pros**:
- Full control over parameters
- Most accurate (if user has correct values)
- No additional implementation needed

**Cons**:
- High burden on user
- Requires forcefield expertise
- Error-prone

## 4) Recommended Approach

### 4.1 Short-term (Use What Exists)

For immediate needs, use **Option A** (`build_frc_cvff_with_embedded_base()`):
- Already implemented and tested
- Works without `-ignore`
- Large file size is acceptable trade-off for compatibility

### 4.2 Medium-term (New Development)

Implement **Option B** (M_BONDED preset):
1. Analyze CVFF base to identify minimal wildcard entries
2. Create new preset that keeps only:
   - Skeleton metadata (like M29)
   - Wildcard entries for bonded sections
   - Custom types from parameterset
3. Test with CALF20 to verify -ignore-free operation
4. Document as the "balanced" option

### 4.3 Long-term (Advanced Features)

Consider **Option C** (automatic derivation) for advanced users:
- Parse MDF topology to identify required bonded types
- Integrate with UFF/DREIDING parameter databases
- Generate minimal, physically meaningful parameters

## 5) Revised Implementation Plan (Using Existing USM Termset)

### Key Discovery

The USM module already provides complete bonded topology information via `derive_termset_v0_1_2()`:
- `atom_types` - sorted list of unique atom types
- `bond_types` - canonicalized bond pairs
- `angle_types` - canonicalized angle triplets
- `dihedral_types` - canonicalized dihedral quadruplets (torsions)
- `improper_types` - canonicalized OOP quadruplets

**No need for a new MDF parser!** The termset already contains all required bonded types.

### Step 1: Create Generic Parameter Generator
Add function `generate_generic_bonded_params()` that:
- Takes termset as input
- Generates CVFF-formatted bond entries with generic parameters (e.g., k=300, r0=1.5)
- Generates CVFF-formatted angle entries with generic parameters (e.g., k=50, theta0=109.5)
- Generates CVFF-formatted torsion entries with generic parameters (e.g., k=0.5, n=2, phi0=180)
- Generates CVFF-formatted OOP entries with generic parameters (e.g., k=0.1)

### Step 2: Create Builder Function
Add `build_frc_cvff_with_generic_bonded()` that:
1. Uses skeleton/M29 base as starting point
2. Adds custom atom types from parameterset
3. Adds generic bonded parameters for all types in termset
4. Produces minimal, self-contained .frc file

### Step 3: Test with CALF20
```bash
cd workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/outputs/msi2lmp_run

# Generate generic bonded .frc
python -c "
from upm.build.frc_from_scratch import build_frc_cvff_with_generic_bonded
# Generate using termset and parameterset
"

# Test WITHOUT -ignore flag
timeout 30s /home/sf2/LabWork/software/msi2lmp.exe CALF20 \
    -class I -frc ../frc_files/cvff_generic_bonded.frc
# Note: NO -ignore flag - this is the goal!
```

### Step 4: Validate and Document
- Verify exit code 0 and CALF20.data creation
- Measure file size (~150-200 lines expected)
- Update documentation with new option

## 6) Decision Matrix

| Option | File Size | -ignore | Development | Accuracy | Recommendation |
|--------|-----------|---------|-------------|----------|----------------|
| A: Full Embedded Base | 5595 lines | Not needed | None | Good | **Use now** |
| B: M_BONDED | ~200-400 lines | Not needed | Medium | Acceptable | **Implement next** |
| C: Auto-derive | ~150-170 lines | Not needed | High | Variable | Future |
| D: User-provided | Variable | Not needed | None | Best (if correct) | Expert use |

## 7) Key Insight: When -ignore is Appropriate

The `-ignore` flag exists for a specific use case:
> **Allow msi2lmp.exe to proceed when bonded parameters are missing, using zeroed/ignored values.**

For **nonbond-only workflows** like CALF20 (which only uses LJ parameters for nonbond analysis), the `-ignore` flag is the **correct and intended usage**. The resulting LAMMPS data file will have:
- Correct atom types and coordinates
- Correct nonbond (LJ) parameters
- Zeroed bonded parameters (which are unused in nonbond-only simulations)

**Using -ignore is NOT a workaround** — it's the designed solution for this use case.

## 8) Conclusion

**For Phase 11**:
1. **Immediate**: Document that `-ignore` is correct for nonbond-only workflows
2. **Short-term**: Use `build_frc_cvff_with_embedded_base()` for -ignore-free needs
3. **Medium-term**: Implement M_BONDED preset for balanced size/compatibility
4. **Long-term**: Consider auto-derivation for advanced users

**Current Status**: The system works correctly. M29 with `-ignore` is the optimal choice for nonbond-only workflows, achieving 97.8% size reduction while maintaining full compatibility.
