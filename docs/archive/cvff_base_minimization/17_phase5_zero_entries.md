# Phase 5: True Zero Entries Experiment (M23)

## 1) Executive Summary

This plan implements the M23 experiment to test **true zero entries** - keeping all section headers but with **0 data rows** in each section. This determines whether msi2lmp.exe needs ANY base entries, or just the section structure.

### Key Finding from Analysis

**Critical Bug Discovered**: The current implementation at [`_limit_section_entries()`](src/upm/src/upm/build/frc_from_scratch.py:1660) has:
```python
if max_entries <= 0:
    return section_lines  # Keeps ALL entries when 0!
```

This means `max_*=0` currently means "keep all entries", NOT "zero entries". A code fix is required.

### Baseline Context

| Metric | M22 (Baseline) | M23 (Target) |
|--------|----------------|--------------|
| Entry limit | 1 per section | 0 per section |
| FRC lines | 395 | ~?? (estimate: ~250-300) |
| Reduction | 92.9% | Expected: ~95%+ |
| Status | PASS | TO BE TESTED |

## 2) Design Decision: Sentinel Value Approach

### Option Analysis

| Option | Pros | Cons |
|--------|------|------|
| Use `-1` for zero entries | Non-breaking, additive | Less intuitive semantics |
| Change `0` to mean zero entries | More intuitive | Breaking change to all presets |
| Add explicit boolean flags | Most explicit | Too many new fields |

### Selected Approach: Use `-1` as sentinel for zero entries

```python
# Entry limits semantic:
# 0     = keep all entries (default, backwards compatible)
# N > 0 = keep first N entries
# -1    = zero entries (keep header/structure only)
```

## 3) Implementation Plan

### Step 1: Modify _limit_section_entries()

**File**: [`src/upm/src/upm/build/frc_from_scratch.py`](src/upm/src/upm/build/frc_from_scratch.py:1660)

**Current code** (lines 1683-1684):
```python
if max_entries <= 0:
    return section_lines
```

**New code**:
```python
# max_entries semantics:
# 0 = keep all entries (unchanged, backwards compatible)
# -1 = zero entries (keep header/structure only)
# N > 0 = keep first N entries
if max_entries == 0:
    return section_lines  # Keep all entries

# For -1 or any negative, treat as zero entries
if max_entries < 0:
    max_entries = 0  # Will emit header + structure only, no data lines
```

### Step 2: Modify Builder Logic

**File**: [`src/upm/src/upm/build/frc_from_scratch.py`](src/upm/src/upm/build/frc_from_scratch.py:1987)

**Current code** (lines 1987-1989):
```python
if max_entries > 0:
    section_lines = _limit_section_entries(section_lines, max_entries)
```

**New code**:
```python
# Call _limit_section_entries for any non-zero value
# - max_entries > 0: keep first N entries
# - max_entries < 0: keep zero entries (header only)
if max_entries != 0:
    section_lines = _limit_section_entries(section_lines, max_entries)
```

### Step 3: Add M23 Preset

**File**: [`src/upm/src/upm/build/frc_from_scratch.py`](src/upm/src/upm/build/frc_from_scratch.py:2263)

Add after M22 preset:
```python
# M23: True zero entries (0 entries per section, headers only)
# Tests: Does msi2lmp.exe require ANY base entries, or just section structure?
# If PASS: Structure-only is the absolute minimum
# If FAIL: M22 (1 entry per section) is the true minimum
"M23": CvffPruneOptions(
    include_cross_terms=False,
    include_cvff_auto=False,
    max_atom_types=-1,        # 0 entries (header only)
    max_equivalence=-1,
    max_morse_bond=-1,
    max_quadratic_bond=-1,
    max_quadratic_angle=-1,
    max_torsion=-1,
    max_out_of_plane=-1,
    max_nonbond=-1,
    max_bond_increments=-1,
),
```

### Step 4: Update CvffPruneOptions Docstring

Update the docstring to document the new `-1` sentinel:

```python
@dataclass(frozen=True)
class CvffPruneOptions:
    """Options for pruning CVFF base content during minimization experiments.
    
    Entry limit fields:
        0     = keep all entries (default, backwards compatible)
        N > 0 = keep first N entries
        -1    = zero entries (keep header/structure only)
    """
```

### Step 5: Create config_M23.json

**File**: `workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/config_M23.json`

```json
{
  "schema": "nist_calf20_msi2lmp_unbonded_v1.config.v0.1",
  "description": "M23: True zero entries experiment (headers only, 0 data rows)",
  "outputs_dir": "outputs_M23",
  "inputs": {
    "car": "inputs/CALF20.car",
    "mdf": "inputs/CALF20.mdf",
    "parameterset": "inputs/parameterset.json"
  },
  "params": {
    "frc_experiment_preset": "M23",
    "timeout_s": 30
  },
  "executables": {
    "msi2lmp": "../../../bin/msi2lmp.exe"
  }
}
```

### Step 6: Execute M23 Experiment

```bash
cd workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1
python run.py --config config_M23.json
```

### Step 7: Record and Analyze Results

Expected output patterns:

**If M23 PASSES (exit code 0)**:
- msi2lmp.exe only requires section STRUCTURE, not content
- M23 becomes the absolute minimum
- Final reduction: ~95%+ from original 5571 lines

**If M23 FAILS (exit code != 0)**:
- msi2lmp.exe requires at least 1 entry per section
- M22 (1 entry/section, 395 lines) is the true minimum
- Error will likely be validation or segfault

### Step 8: Update Thrust Log

**File**: [`docs/DevGuides/thrust_log_cvff_base_minimization.md`](docs/DevGuides/thrust_log_cvff_base_minimization.md)

Add new section:

```markdown
## 14) Phase 5 Results: True Zero Entries Experiment (M23)

**Executed**: 2025-12-20

### 14.1 M23 Configuration

| Field | Value | Description |
|-------|-------|-------------|
| include_cross_terms | False | Already removed in M04+ |
| include_cvff_auto | False | Already removed in M04+ |
| max_*_entries | -1 | Zero entries (header only) |

### 14.2 Results

| Preset | Configuration | FRC Lines | Exit Code | CALF20.data | Status |
|--------|---------------|-----------|-----------|-------------|--------|
| M22 (baseline) | 1 entry/section | 395 | 0 | 6856 bytes | PASS |
| M23 | 0 entries/section | ??? | ??? | ??? | ??? |

### 14.3 Conclusion

[If PASS]: **M23 is the absolute minimum** - msi2lmp.exe only requires section headers, not data entries. Final reduction: ~XX% from original.

[If FAIL]: **M22 is the true minimum** - msi2lmp.exe requires at least 1 entry per section for parser initialization.
```

## 4) Verification Checklist

- [ ] `_limit_section_entries()` handles -1 correctly (returns header only)
- [ ] Builder calls `_limit_section_entries()` for non-zero values
- [ ] M23 preset added to `CVFF_MINIMIZATION_PRESETS`
- [ ] config_M23.json created
- [ ] M23 experiment executed
- [ ] Results recorded: exit_code, frc_lines, CALF20.data status
- [ ] Thrust log updated with Phase 5 findings
- [ ] phase5_results.json created

## 5) Expected Section Header Structure (M23 Output)

With zero entries, each section should emit only:
- Header line: `#section_name\tcvff`
- Annotation lines: `>` description, `@type`, `@combination`
- Column header comments: `!Ver Ref ...`
- Empty line separator

Example for `#nonbond(12-6) cvff`:
```
#nonbond(12-6)	cvff

@type A-B
@combination geometric

> E = Aij/r^12 - Bij/r^6
> where  Aij = sqrt( Ai * Aj )
>        Bij = sqrt( Bi * Bj )

!Ver  Ref     I           A             B
!---- ---    ----    -----------   -----------
```
(No data rows - just structure)

## 6) Risk Assessment

| Risk | Mitigation |
|------|------------|
| Breaking existing presets | Using -1 sentinel preserves 0 = keep all behavior |
| msi2lmp parser crash | 30s timeout prevents infinite stall |
| Incorrect section structure | Verify header + annotations + comments preserved |

## 7) Success Criteria

1. **Code changes compile** - No syntax errors in modified Python
2. **Existing tests pass** - M01-M22 presets still work identically
3. **M23 executes** - Experiment runs to completion (PASS or FAIL)
4. **Results documented** - Thrust log updated with conclusion
5. **Absolute minimum determined** - Either M22 or M23 identified as final minimum
