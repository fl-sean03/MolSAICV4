# Subtask 5b: msi2lmp Segfault Root Cause Analysis

**Status**: ROOT CAUSE IDENTIFIED - Ready for Implementation  
**Date**: 2025-12-21

## 1) Root Cause Identified

### The Problem

The `#hbond_definition` section in [`cvff_skeleton.py`](src/upm/src/upm/build/cvff_skeleton.py:53) references atom types that are NOT defined when using the new minimal builder:

```
#hbond_definition	cvff 

 1.0   1   distance      2.5000
 1.0   1   angle        90.0000
 1.0   1   donors        hn  h*  hspc   htip       <-- UNDEFINED TYPES!
 1.0   1   acceptors     o'  o   o*  ospc   otip   <-- UNDEFINED TYPES!
```

When msi2lmp.exe parses this file, it attempts to look up these H-bond donor/acceptor types (`hn`, `h*`, `hspc`, `htip`, `o'`, `o`, `o*`, `ospc`, `otip`) in the `#atom_types` table. Since the new builder only defines custom types from the termset (C_MOF, H_MOF, N_MOF, O_MOF, Zn_MOF), these lookups fail and cause a segmentation fault (exit code -11).

### Comparison: Old vs New Builder

| Aspect | Old Builder (`build_frc_cvff_with_minimal_base`) | New Builder (`build_minimal_cvff_frc`) |
|--------|--------------------------------------------------|----------------------------------------|
| Output Size | 1057 lines | 134 lines |
| Base Content | Uses 1033-line `CVFF_MINIMAL_BASE_CONTENT` | Uses 88-line `CVFF_SKELETON` template |
| Standard Types | 58+ standard CVFF types (h, hn, ho, c, cp, etc.) | Only custom types from termset |
| H-bond Types | All referenced types defined | Referenced types NOT defined |
| Result | Works with msi2lmp.exe | Segfault (exit -11) |

### Evidence

1. **Old builder FRC has these types defined** in `#atom_types`:
   - `h`, `hn`, `ho`, `h*`, `hspc`, `htip` (hydrogen types)
   - `o`, `o'`, `o*`, `ospc`, `otip` (oxygen types)

2. **New builder FRC only has**:
   - `C_MOF`, `H_MOF`, `N_MOF`, `O_MOF`, `Zn_MOF`, `Zn_MO` (alias)

3. **The `#hbond_definition` section references undefined types**, causing msi2lmp.exe to crash during lookup.

## 2) Solution

### Recommended Fix: Empty H-bond Definition

Modify the `#hbond_definition` section in [`cvff_skeleton.py`](src/upm/src/upm/build/cvff_skeleton.py) to remove references to undefined atom types:

**Before:**
```python
#hbond_definition	cvff 

 1.0   1   distance      2.5000
 1.0   1   angle        90.0000
 1.0   1   donors        hn  h*  hspc   htip
 1.0   1   acceptors     o'  o   o*  ospc   otip
```

**After:**
```python
#hbond_definition	cvff 

 1.0   1   distance      2.5000
 1.0   1   angle        90.0000
```

### Rationale

1. **Minimal Change**: Only removes the problematic lines, preserves section structure
2. **Safe for CALF20**: MOF systems typically don't use H-bond detection
3. **msi2lmp Compatible**: Section still exists with valid distance/angle parameters
4. **Reversible**: If H-bonding is needed, can add appropriate types later

### Alternative Approaches (Not Recommended)

1. **Add stub atom types for H-bond references**: Would increase file size and add unnecessary complexity
2. **Remove `#hbond_definition` entirely**: May cause parsing errors in msi2lmp.exe
3. **Use the old builder**: Defeats the purpose of the minimal builder refactor

## 3) Implementation Plan

### Step 1: Modify cvff_skeleton.py

File: [`src/upm/src/upm/build/cvff_skeleton.py`](src/upm/src/upm/build/cvff_skeleton.py)

Remove lines 57-58 (the donors/acceptors lines):
```python
 1.0   1   donors        hn  h*  hspc   htip
 1.0   1   acceptors     o'  o   o*  ospc   otip
```

### Step 2: Update run.py to Use New Builder

File: [`workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/run.py`](workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/run.py)

Change line 77:
```python
# FROM:
from upm.build.frc_from_scratch import build_frc_cvff_with_minimal_base

# TO:
from upm.build import build_minimal_cvff_frc
```

And line 266-270:
```python
# FROM:
build_frc_cvff_with_minimal_base(
    termset=json.loads(termset_path.read_text(encoding="utf-8")),
    parameterset=json.loads(parameterset_path.read_text(encoding="utf-8")),
    out_path=ff_path,
)

# TO:
build_minimal_cvff_frc(
    termset=json.loads(termset_path.read_text(encoding="utf-8")),
    parameterset=json.loads(parameterset_path.read_text(encoding="utf-8")),
    out_path=ff_path,
)
```

### Step 3: Test with msi2lmp.exe

```bash
cd workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1
python run.py --config config.json
echo "Exit code: $?"
```

## 4) Success Criteria

| Criterion | Expected |
|-----------|----------|
| Exit code | 0 |
| CALF20.data | Created and non-empty |
| FRC file size | ~130-150 lines (vs 1057 with old builder) |
| `-ignore` flag | Still required for topology validation |

## 5) Scope

### DO
- [x] Identify root cause
- [ ] Modify `cvff_skeleton.py` to fix H-bond definition
- [ ] Update `run.py` to use new builder
- [ ] Test with msi2lmp.exe
- [ ] Document results

### DO NOT
- Do NOT revert to using the old builder
- Do NOT add standard CVFF types to the minimal builder
- Do NOT modify other sections of the skeleton
