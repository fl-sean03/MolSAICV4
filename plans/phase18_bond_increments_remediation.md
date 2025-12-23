# Phase 18: Bond Increments Remediation Plan

## Problem Statement

The generated FRC file has incorrect `#bond_increments` values:
- **Expected:** cdc-cdo: `-0.03000 / +0.03000` (from original cvff_iff_ILs.frc)
- **Actual:** cdc-cdo: `0.00000 / 0.00000` (hardcoded defaults)

## Root Cause Analysis

The issue exists in multiple layers of the codebase:

### 1. `_frc_parser.py` - Does NOT parse bond_increments
The parser only handles:
- `#atom_types` → `_parse_atom_types()`
- `#quadratic_bond` → `_parse_quadratic_bond()`
- `#quadratic_angle` → `_parse_quadratic_angle()`
- `#nonbond(12-6)` → `_parse_nonbond_12_6()`

**Missing:** `#bond_increments` section parser

### 2. `_build_tables()` - No bond_increments table
The function builds tables for atom_types, bonds, and angles only.
No bond_increments DataFrame is created.

### 3. `filter_frc_tables()` - No bond_increments filtering
The filter function handles atom_types, bonds, and angles.
No filtering logic for bond_increments.

### 4. `_frc_from_existing.py` - Uses hardcoded defaults
```python
bond_increment_entries.append(format_skeleton_bond_increment_entry(t1, t2))
```
This calls the function with only t1, t2 - using default `delta_ij=0.0, delta_ji=0.0`.

## Remediation Steps

### Step 1: Add bond_increments parser to `_frc_parser.py`

Add new function:
```python
def _parse_bond_increments(lines: list[str]) -> list[dict[str, Any]]:
    """Parse #bond_increments section rows.
    
    Format: ver ref t1 t2 delta_ij delta_ji
    Example: 3.6  32  cdc  cdo  -0.03000  0.03000
    """
    rows: list[dict[str, Any]] = []
    for raw in lines:
        if _is_ignorable_line(raw):
            continue
        line = _strip_inline_comment(raw)
        if not line.strip():
            continue
        toks = line.split()
        if len(toks) < 4:
            continue  # Skip malformed rows
        
        # Find last two adjacent floats as delta_ij, delta_ji
        di_i: int | None = None
        dj_i: int | None = None
        for i in range(len(toks) - 2, -1, -1):
            try:
                float(toks[i])
                float(toks[i + 1])
            except Exception:
                continue
            di_i = i
            dj_i = i + 1
            break
        
        if di_i is None or di_i < 2:
            continue
            
        t1, t2 = toks[di_i - 2], toks[di_i - 1]
        delta_ij = float(toks[di_i])
        delta_ji = float(toks[dj_i])
        
        rows.append({
            "t1": t1,
            "t2": t2,
            "delta_ij": delta_ij,
            "delta_ji": delta_ji,
        })
    return rows
```

### Step 2: Update `_build_tables()` to include bond_increments

Add bond_increments_rows parameter and create DataFrame.

### Step 3: Update `msi_frc.py` to call the parser

Add bond_increments section detection in the main read_frc function.

### Step 4: Update `filter_frc_tables()` in `_frc_filters.py`

Add filtering logic for bond_increments by bond types.

### Step 5: Update `_frc_from_existing.py` to pass actual values

```python
# After filtering, get delta values from bond_increments table
if "bond_increments" in filtered_tables:
    bi_df = filtered_tables["bond_increments"]
    for _, row in bi_df.iterrows():
        t1, t2 = str(row["t1"]), str(row["t2"])
        delta_ij = float(row["delta_ij"])
        delta_ji = float(row["delta_ji"])
        bond_increment_entries.append(
            format_skeleton_bond_increment_entry(t1, t2, delta_ij, delta_ji)
        )
else:
    # Fallback: generate from bonds table with default 0.0 values
    for _, row in bonds_df.iterrows():
        bond_increment_entries.append(
            format_skeleton_bond_increment_entry(t1, t2)
        )
```

### Step 6: Add tests

Create test cases to verify bond_increments parsing works correctly.

### Step 7: Re-run workspaces and validate

1. Delete output directories
2. Re-run workspaces:
   - `workspaces/NIST/calf20_co2_combined_v1/`
   - `workspaces/NIST/CO2_construct/` (if exists)
3. Verify bond_increments in generated FRC files match source

## Workspaces to Re-run

| Workspace | Purpose |
|-----------|---------|
| `workspaces/NIST/calf20_co2_combined_v1/` | Combined MOF+CO2 - main validation target |
| `workspaces/NIST/CO2_construct/` | Pure CO2 workspace (if exists) |

## Validation Criteria

1. **CO2 bond_increments in generated FRC:**
   - `cdc-cdo: delta_ij=-0.03000, delta_ji=+0.03000`

2. **MOF bond_increments (placeholder):**
   - All MOF bonds: `delta_ij=0.0, delta_ji=0.0` (no charge transfer for placeholders)

3. **msi2lmp execution:**
   - Exit code 0
   - LAMMPS .data file generated with correct atom count

## Files to Modify

| File | Changes |
|------|---------|
| `src/upm/src/upm/codecs/_frc_parser.py` | Add `_parse_bond_increments()` |
| `src/upm/src/upm/codecs/msi_frc.py` | Detect and parse #bond_increments section |
| `src/upm/src/upm/build/_frc_filters.py` | Add bond_increments filtering |
| `src/upm/src/upm/build/_frc_from_existing.py` | Use actual delta values |
| `src/upm/tests/test_msi_frc_codec.py` | Add bond_increments tests |
