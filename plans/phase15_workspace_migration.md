# Phase 15: Workspace Migration to New FRC Builder API

## Objective

Migrate two NIST workspaces from legacy FRC builder functions to the new unified `FRCBuilder` + `ParameterSource` architecture.

---

## Workspaces to Migrate

### 1. CO2_construct

**Location:** `workspaces/NIST/CO2_construct/`

**Current Usage:**
```python
from upm.build.frc_builders import build_frc_from_existing

build_frc_from_existing(
    termset=termset,
    source_frc_path=source_frc_path,
    out_path=minimal_frc_path,
    strict=True,
)
```

**Inputs:**
- CAR/MDF files: `inputs/CO2.car`, `inputs/CO2.mdf`
- Source FRC: `/home/sf2/LabWork/.../cvff_iff_ILs.frc`
- Atom types: `cdc` (C), `cdo` (O)
- Bond types: `[cdc, cdo]`
- Angle types: `[cdo, cdc, cdo]`

**New Architecture:**
```python
from upm.build import FRCBuilder, FRCBuilderConfig
from upm.build.parameter_sources import ExistingFRCSource

source = ExistingFRCSource(source_frc_path)
builder = FRCBuilder(termset, source, FRCBuilderConfig(strict=True))
builder.write(minimal_frc_path)
```

---

### 2. nist_calf20_msi2lmp_unbonded_v1

**Location:** `workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/`

**Current Usage:**
```python
from upm.build.frc_builders import build_frc_cvff_with_generic_bonded

build_frc_cvff_with_generic_bonded(
    termset=_read_json(termset_path),
    parameterset=_read_json(ps_path),
    out_path=ff_path
)
```

**Inputs:**
- CAR/MDF files: `inputs/CALF20.car`, `inputs/CALF20.mdf`
- ParameterSet: `inputs/parameterset.json` with LJ params for `C_MOF`, `H_MOF`, `N_MOF`, `O_MOF`, `Zn_MOF`

**New Architecture:**
```python
from upm.build import FRCBuilder, FRCBuilderConfig
from upm.build.parameter_sources import ChainedSource, ParameterSetSource, PlaceholderSource

# Build element map for PlaceholderSource
ps = _read_json(ps_path)
termset = _read_json(termset_path)
element_map = {at: ps["atom_types"].get(at, {}).get("element", "X") for at in termset["atom_types"]}

# Create source chain: ParameterSet for nonbond/atom info, Placeholder for bonded
source = ChainedSource([
    ParameterSetSource(ps),
    PlaceholderSource(element_map),
])

builder = FRCBuilder(termset, source, FRCBuilderConfig(strict=False))
builder.write(ff_path)
```

---

## Migration Strategy

### Step 1: Preserve Imports
Both workspaces have bootstrap logic that adds repo `src/` to `sys.path`. The new imports will work:
```python
from upm.build import FRCBuilder, FRCBuilderConfig
from upm.build.parameter_sources import ExistingFRCSource, ChainedSource, ParameterSetSource, PlaceholderSource
```

### Step 2: Minimal Code Changes
Focus on replacing only the FRC building section. Keep all other workspace logic unchanged.

### Step 3: Backward Compatibility Test
Run each workspace and compare outputs:
- FRC file should have same structure
- msi2lmp should produce equivalent .data files
- Validation reports should match or improve

---

## Risk Assessment

### CO2_construct
- **Risk Level:** Low
- **Key Concern:** `ExistingFRCSource` must correctly parse the source FRC and extract real parameters
- **Fallback:** The legacy `build_frc_from_existing()` still works via `_legacy.py`

### nist_calf20_msi2lmp_unbonded_v1
- **Risk Level:** Low-Medium
- **Key Concern:** `ChainedSource` must correctly chain `ParameterSetSource` -> `PlaceholderSource`
- **Key Concern:** LJ σ/ε → A/B conversion must be identical to legacy
- **Fallback:** The legacy `build_frc_cvff_with_generic_bonded()` still works via `_legacy.py`

---

## Validation Criteria

### Success for CO2_construct
1. ✅ `minimal.frc` is generated without errors
2. ✅ msi2lmp runs successfully on minimal.frc
3. ✅ Path A (minimal) and Path B (original) outputs are equivalent
4. ✅ `validation_report.json` shows `status: success`

### Success for nist_calf20_msi2lmp_unbonded_v1
1. ✅ `cvff_generic_bonded.frc` is generated without errors
2. ✅ msi2lmp runs successfully
3. ✅ `CALF20.data` is created with correct atom/bond counts
4. ✅ `validation_report.json` shows `counts_ok: true`

---

## Implementation Checklist

- [ ] Update CO2_construct/run.py
  - [ ] Add new imports
  - [ ] Replace build_frc_from_existing call with FRCBuilder + ExistingFRCSource
  - [ ] Test run
  - [ ] Verify outputs

- [ ] Update nist_calf20_msi2lmp_unbonded_v1/run.py
  - [ ] Add new imports
  - [ ] Replace build_frc_cvff_with_generic_bonded call with FRCBuilder + ChainedSource
  - [ ] Test run
  - [ ] Verify outputs

- [ ] Document any issues or behavior differences

---

## Rollback Plan

If migration causes issues:
1. Revert to legacy imports (still exported from `upm.build`)
2. Legacy functions are wrappers around new API, so they should work
3. Document any bugs for future fix

---

## Notes

- Both workspaces require msi2lmp executable at `/home/sf2/LabWork/software/msi2lmp.exe`
- If msi2lmp is not available, workspaces still validate FRC generation
- The new API provides better error messages via `MissingTypesError`
