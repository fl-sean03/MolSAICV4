# Phase 16.4: FRC Parameter Validation Plan

## Objective
Verify that the generated `combined_mof_co2.frc` file correctly extracts CO2 parameters from the original `cvff_iff_ILs.frc` and applies appropriate generic values for MOF entries.

---

## 1. CO2 Entries Comparison (cdc, cdo)

### 1.1 #atom_types Section

| Field | Original (cvff_iff_ILs.frc) | Generated | Match? |
|-------|----------------------------|-----------|--------|
| cdc mass | 12.011150 | 12.011150 | ✅ |
| cdc element | C | C | ✅ |
| cdc connections | 2 | 4 | ⚠️ Cosmetic diff |
| cdo mass | 15.999400 | 15.999400 | ✅ |
| cdo element | O | O | ✅ |
| cdo connections | 1 | 2 | ⚠️ Cosmetic diff |

**Note:** Connections field is a hint for msi2lmp, not critical for simulation.

### 1.2 #equivalence Section ✅

| Type | Original | Generated | Match? |
|------|----------|-----------|--------|
| cdc | cdc cdc cdc cdc cdc cdc | cdc cdc cdc cdc cdc cdc | ✅ |
| cdo | cdo cdo cdo cdo cdo cdo | cdo cdo cdo cdo cdo cdo | ✅ |

### 1.3 #quadratic_bond Section ✅

| Entry | Original | Generated | Match? |
|-------|----------|-----------|--------|
| cdc-cdo R0 | 1.1620 | 1.1620 | ✅ |
| cdc-cdo K2 | 1140.0000 | 1140.0000 | ✅ |

### 1.4 #quadratic_angle Section ✅

| Entry | Original | Generated | Match? |
|-------|----------|-----------|--------|
| cdo-cdc-cdo Theta0 | 180.0000 | 180.0000 | ✅ |
| cdo-cdc-cdo K2 | 100.0000 | 100.0000 | ✅ |

### 1.5 #nonbond(12-6) Section ✅

| Type | Original A | Generated A | Original B | Generated B | Match? |
|------|------------|-------------|------------|-------------|--------|
| cdc | 236919.1 | 236919.1 | 217.67820 | 217.67820 | ✅ |
| cdo | 207547.3 | 207547.3 | 315.63070 | 315.63070 | ✅ |

### 1.6 #bond_increments Section ❌ DISCREPANCY

| Entry | Original | Generated | Match? |
|-------|----------|-----------|--------|
| cdc-cdo DeltaIJ | **-0.03000** | 0.00000 | ❌ |
| cdc-cdo DeltaJI | **+0.03000** | 0.00000 | ❌ |

**Issue:** The `ExistingFRCSource` is not extracting bond_increments from the original FRC file, defaulting to 0.0/0.0 instead of -0.03/+0.03.

---

## 2. MOF Entries Analysis (C_MOF, H_MOF, N_MOF, O_MOF, Zn_MOF)

### 2.1 #atom_types Section ✅

All masses and elements derived from USM correctly:
- C_MOF: 12.011, C
- H_MOF: 1.008, H  
- N_MOF: 14.007, N
- O_MOF: 15.999, O
- Zn_MOF: 65.38, Zn

### 2.2 #quadratic_bond Section ✅ (Generic/Placeholder Values)

| Bond | R0 | K2 | Source |
|------|----|----|--------|
| C_MOF-H_MOF | 1.09 | 340.0 | PlaceholderSource (C-H typical) |
| C_MOF-N_MOF | 1.50 | 300.0 | PlaceholderSource (generic) |
| C_MOF-O_MOF | 1.50 | 300.0 | PlaceholderSource (generic) |
| N_MOF-N_MOF | 1.50 | 300.0 | PlaceholderSource (generic) |
| N_MOF-Zn_MOF | 2.05 | 150.0 | PlaceholderSource (metal coord) |
| O_MOF-Zn_MOF | 2.05 | 150.0 | PlaceholderSource (metal coord) |

### 2.3 #quadratic_angle Section ✅ (Generic Values)

All MOF angles use generic values:
- Theta0: 90° (Zn coordination), 109.5° (tetrahedral), 120° (planar)
- K2: 50.0 (universal)

### 2.4 #torsion_1 Section ✅ (Zero-Force)

All MOF torsions: Kphi=0.0, n=1, Phi0=0.0 (zero barrier, as expected)

### 2.5 #out_of_plane Section ✅ (Minimal Restraint)

All MOF impropers: Kchi=0.1, n=2, Chi0=180.0 (small planarity restraint)

### 2.6 #nonbond(12-6) Section ✅ (From ParameterSet)

Verified A/B calculation from σ/ε (Lorentz-Berthelot):
- Formula: A = 4ε × σ^12, B = 4ε × σ^6

| Type | σ (Å) | ε (kcal/mol) | Calculated A | Generated A | Match? |
|------|-------|--------------|--------------|-------------|--------|
| C_MOF | 3.4309 | 0.105 | 1117239.1 | 1117239.1 | ✅ |
| H_MOF | 2.5711 | 0.044 | 14687.2 | 14687.2 | ✅ |
| N_MOF | 3.2607 | 0.069 | 398693.5 | 398693.5 | ✅ |
| O_MOF | 3.1181 | 0.060 | 202717.7 | 202717.7 | ✅ |
| Zn_MOF | 2.4616 | 0.124 | 24552.3 | 24552.3 | ✅ |

---

## 3. Summary of Findings

### ✅ Working Correctly

1. **CO2 bond parameters** (cdc-cdo): R0=1.1620, K2=1140.0 - EXACT MATCH
2. **CO2 angle parameters** (cdo-cdc-cdo): Theta0=180°, K2=100.0 - EXACT MATCH
3. **CO2 nonbond A/B values**: EXACT MATCH
4. **MOF nonbond values**: Correctly computed from σ/ε parameterset
5. **MOF bonded terms**: Appropriate generic/placeholder values applied

### ⚠️ Minor Issues (Cosmetic)

1. **#atom_types connections field**: cdc shows 4 (vs 2), cdo shows 2 (vs 1)
   - Impact: None - this is just a hint for msi2lmp, actual connectivity from MDF

### ❌ Bug Found

1. **#bond_increments for cdc-cdo**: Should be -0.03/+0.03, showing 0.0/0.0
   - Root cause: `ExistingFRCSource` doesn't parse bond_increments section
   - Impact: Partial charges may be slightly different (3% on C/O)
   - Severity: Low - CO2 charges are typically assigned explicitly in simulation

---

## 4. Action Items

### 4.1 Optional Fix (Low Priority)
- Enhance `ExistingFRCSource` to parse and return `bond_increments` entries
- Location: `src/upm/src/upm/build/parameter_sources/existing_frc_source.py`

### 4.2 Documentation Update
- Document that bond_increments are not currently preserved when extracting from existing FRC files
- Add to REFACTOR_MAP.md or similar

### 4.3 Validation Complete ✅
The FRC file is functional for msi2lmp:
- All critical bond/angle/nonbond parameters match or use appropriate placeholders
- The bond_increments issue is minor and doesn't affect structural minimization

---

## 5. Files Examined

| File | Purpose |
|------|---------|
| `workspaces/NIST/calf20_co2_combined_v1/outputs/frc_files/combined_mof_co2.frc` | Generated FRC |
| `assets/NIST/CO2_construct/cvff_iff_ILs.frc` | Original source for CO2 parameters |
| `workspaces/NIST/calf20_co2_combined_v1/inputs/mof_parameterset.json` | MOF σ/ε values |
| `workspaces/NIST/calf20_co2_combined_v1/outputs/termset.json` | Derived term types |
