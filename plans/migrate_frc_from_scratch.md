# Migration Plan: Delete frc_from_scratch.py

## 1. Overview

The old [`frc_from_scratch.py`](../src/upm/src/upm/build/frc_from_scratch.py) file (4000+ lines) contains legacy code from the CVFF minimization experiments. New modular files have been created:

- [`cvff_skeleton.py`](../src/upm/src/upm/build/cvff_skeleton.py) - Contains the canonical CVFF skeleton template
- [`frc_writer.py`](../src/upm/src/upm/build/frc_writer.py) - Contains formatting/writing functions
- [`frc_input.py`](../src/upm/src/upm/build/frc_input.py) - Contains data model classes and `build_frc_input()`
- [`cvff_minimal_base.py`](../src/upm/src/upm/build/cvff_minimal_base.py) - Contains the pruned CVFF base content

## 2. Import Dependency Analysis

### Files importing from frc_from_scratch.py:

| File | Imports | Disposition |
|------|---------|-------------|
| `test_build_frc_generic_bonded.py` | `generate_generic_bonded_params`, `build_frc_cvff_with_generic_bonded`, `MissingTypesError` | **KEEP** - Phase 11 tests |
| `test_build_frc_from_scratch_nonbond_only.py` | `MissingTypesError`, `build_frc_nonbond_only` | **KEEP** - CLI test |
| `test_build_frc_from_scratch_cvff_minimal_bonded.py` | `CvffFrcEmitOptions`, `build_frc_cvff_minimal_bonded`, `build_frc_cvff_with_embedded_base`, `build_frc_cvff_with_pruned_base`, `build_frc_cvff_from_skeleton`, `resolve_cvff_frc_experiment_preset` | **DELETE** - Deprecated experiment tests |
| `build_frc.py` (CLI) | `MissingTypesError`, `build_frc_nonbond_only` | **KEEP** - Update imports |
| `run.py` (NIST workspace) | `build_frc_cvff_with_minimal_base` | **KEEP** - Update imports |

## 3. Migration Strategy

### 3.1 Functions to Migrate to New Module (`frc_builders.py`)

Create a new file [`src/upm/src/upm/build/frc_builders.py`](../src/upm/src/upm/build/frc_builders.py) containing:

1. **`MissingTypesError`** - Exception class for missing atom types
2. **`build_frc_nonbond_only()`** - Nonbonded-only builder for CLI
3. **`build_frc_cvff_with_minimal_base()`** - Production builder for NIST workspace
4. **`generate_generic_bonded_params()`** - Generic bonded params generator (Phase 11)
5. **`build_frc_cvff_with_generic_bonded()`** - Builder with generic bonded (Phase 11)

### 3.2 Test File to Delete

**DELETE:** `test_build_frc_from_scratch_cvff_minimal_bonded.py`

This file tests deprecated experiment functionality:
- `CvffFrcEmitOptions` - experiment configuration
- `build_frc_cvff_minimal_bonded` - experiment builder with emit options
- `build_frc_cvff_with_embedded_base` - embedded base builder
- `build_frc_cvff_with_pruned_base` - pruned base builder
- `build_frc_cvff_from_skeleton` - skeleton-based builder
- `resolve_cvff_frc_experiment_preset` - preset resolver

These are all Phase 2-11 experiment artifacts that are superseded by the new modular architecture.

### 3.3 Files to Update Imports

1. **`build_frc.py`** (CLI):
   ```python
   # FROM:
   from upm.build.frc_from_scratch import MissingTypesError, build_frc_nonbond_only
   # TO:
   from upm.build.frc_builders import MissingTypesError, build_frc_nonbond_only
   ```

2. **`test_build_frc_from_scratch_nonbond_only.py`**:
   ```python
   # FROM:
   from upm.build.frc_from_scratch import MissingTypesError, build_frc_nonbond_only
   # TO:
   from upm.build.frc_builders import MissingTypesError, build_frc_nonbond_only
   ```

3. **`test_build_frc_generic_bonded.py`**:
   ```python
   # FROM:
   from upm.build.frc_from_scratch import (
       generate_generic_bonded_params,
       build_frc_cvff_with_generic_bonded,
       MissingTypesError,
   )
   # TO:
   from upm.build.frc_builders import (
       generate_generic_bonded_params,
       build_frc_cvff_with_generic_bonded,
       MissingTypesError,
   )
   ```

4. **`run.py`** (NIST workspace):
   ```python
   # FROM:
   from upm.build.frc_from_scratch import build_frc_cvff_with_minimal_base
   # TO:
   from upm.build.frc_builders import build_frc_cvff_with_minimal_base
   ```

### 3.4 Update `__init__.py`

Add exports for migrated items:
```python
from .frc_builders import (
    MissingTypesError,
    build_frc_nonbond_only,
    build_frc_cvff_with_minimal_base,
    generate_generic_bonded_params,
    build_frc_cvff_with_generic_bonded,
)
```

## 4. Functions Required in frc_builders.py

Based on analysis, these functions need to be extracted from `frc_from_scratch.py`:

### 4.1 MissingTypesError (lines 27-38)
Simple frozen dataclass exception.

### 4.2 build_frc_nonbond_only (lines 102-154)
Builds nonbonded-only `.frc` file. Used by CLI.

### 4.3 build_frc_cvff_with_minimal_base (lines 3097-3393)
Production builder that uses `CVFF_MINIMAL_BASE_CONTENT` and appends custom types.

### 4.4 generate_generic_bonded_params (lines 3979-4137)
Generates generic bonded parameters from termset/parameterset.

### 4.5 build_frc_cvff_with_generic_bonded (lines 4140-4280)
Builder that combines minimal base with generic bonded parameters.

### 4.6 Helper Functions Required
- `_lj_sigma_eps_to_ab()` - Already in `frc_input.py`
- `_fmt_float()` - Simple formatting function
- `_placeholder_bond_params()` - Already in `frc_input.py` (similar)
- `_placeholder_angle_params()` - Already in `frc_input.py` (similar)

## 5. Execution Steps

1. **Create `frc_builders.py`** with the 5 required functions plus helpers
2. **Delete `test_build_frc_from_scratch_cvff_minimal_bonded.py`**
3. **Update imports** in:
   - `src/upm/src/upm/cli/commands/build_frc.py`
   - `src/upm/tests/test_build_frc_from_scratch_nonbond_only.py`
   - `src/upm/tests/test_build_frc_generic_bonded.py`
   - `workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/run.py`
4. **Update `__init__.py`** to export migrated items
5. **Run tests**:
   ```bash
   python -m pytest src/upm/tests/test_build_frc*.py -v
   ```
6. **Delete `frc_from_scratch.py`**
7. **Verify NIST workspace**:
   ```bash
   cd workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1
   rm -rf outputs
   python run.py --config config.json
   ls -la outputs/msi2lmp_run/CALF20.data
   ```

## 6. Success Criteria

- [ ] All 4 files updated to not import from `frc_from_scratch.py`
- [ ] All tests pass: `python -m pytest src/upm/tests/test_build_frc*.py -v`
- [ ] `frc_from_scratch.py` deleted
- [ ] NIST workspace produces CALF20.data

## 7. Implementation Notes

### Code to Extract (approximately 300 lines needed)

From the 4000+ line file, only ~300 lines need to be preserved:
- `MissingTypesError`: 12 lines
- `build_frc_nonbond_only`: 52 lines
- `build_frc_cvff_with_minimal_base`: 296 lines
- `generate_generic_bonded_params`: 158 lines
- `build_frc_cvff_with_generic_bonded`: 140 lines
- Helpers: ~50 lines

Total: ~600-700 lines (vs 4000+ in original)

### Dependencies

The new `frc_builders.py` will import from:
- `.cvff_minimal_base` - `CVFF_MINIMAL_BASE_CONTENT`
- `.cvff_skeleton` - `CVFF_SKELETON`
- `.frc_input` - Data model classes if needed
- `.frc_writer` - `write_cvff_frc()` if needed
