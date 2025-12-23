# Subtask 6: M23 Structure Analysis and Full Demonstration Plan

## 1) Overview

M23 achieved the **absolute minimum .frc file at 386 lines** with 0 base entries per section. This plan documents the line breakdown analysis and execution steps for the full demonstration.

## 2) M23 Configuration Analysis

### 2.1 Preset Definition (from `frc_from_scratch.py:2287`)

```python
"M23": CvffPruneOptions(
    include_cross_terms=False,    # Removes bond-bond, bond-angle, angle-angle, etc.
    include_cvff_auto=False,      # Removes all cvff_auto sections
    max_atom_types=-1,            # 0 entries (header only)
    max_equivalence=-1,
    max_morse_bond=-1,
    max_quadratic_bond=-1,
    max_quadratic_angle=-1,
    max_torsion=-1,
    max_out_of_plane=-1,
    max_nonbond=-1,
    max_bond_increments=-1,
)
```

### 2.2 Sentinel Value Semantics

- `max_*=0` → "keep all entries" (no limit)
- `max_*=-1` → "zero entries" (keep header/structure only, no data rows)
- `max_*>0` → "keep N entries"

## 3) Predicted Line Breakdown (386 lines)

Based on analysis of the embedded base structure and CALF20 types:

| Category | Lines | Description |
|----------|-------|-------------|
| **Preamble** | ~18 | `!BIOSYM` header + `#version` lines (1-18) |
| **Blank/Structural** | ~8 | Empty lines between sections |
| **#define blocks** | ~78 | 4 CVFF macro definitions (cvff, cvff_nocross, cvff_nomorse, cvff_nocross_nomorse) |
| **Section headers** | ~10 | One header line per section |
| **Section comments** | ~30 | `>` annotation + `!` column headers per section |
| **Base entries** | 0 | M23 removes all base entries |
| **CALF20 custom types** | ~220+ | atom_types, equivalence, nonbond, bond_increments |

### 3.1 Sections Retained in M23

These sections have **headers only** (no base data entries):

1. `#atom_types cvff` 
2. `#equivalence cvff`
3. `#hbond_definition cvff`
4. `#morse_bond cvff`
5. `#quadratic_bond cvff`
6. `#quadratic_angle cvff`
7. `#torsion_1 cvff`
8. `#out_of_plane cvff`
9. `#nonbond(12-6) cvff`
10. `#bond_increments cvff`

### 3.2 Sections Removed (by prune options)

**Cross-terms** (`include_cross_terms=False`):
- `#bond-bond cvff`
- `#bond-angle cvff`
- `#angle-angle-torsion_1 cvff`
- `#out_of_plane-out_of_plane cvff`
- `#angle-angle cvff`

**cvff_auto sections** (`include_cvff_auto=False`):
- `#morse_bond cvff_auto`
- `#quadratic_bond cvff_auto`
- `#quadratic_angle cvff_auto`
- `#torsion_1 cvff_auto`
- `#out_of_plane cvff_auto`

## 4) CALF20 Custom Types (appended)

From CALF20 termset:
- **5 atom types**: C_MOF, H_MOF, N_MOF, O_MOF, Zn_MOF (+ 5 aliases for msi2lmp truncation = 10 total)
- **6 bond types** → 24 expanded rows (aliases + reverse ordering)
- **11 angle types** → 44 expanded rows
- **16 dihedral types** → 64 expanded rows  
- **6 improper types** → ~144 expanded rows (permutations)

## 5) Execution Plan

### Step 1: Run M23 Workspace
```bash
cd workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1
python run.py --config config_M23.json
```

### Step 2: Create Demo Output Directory
```bash
mkdir -p outputs_M23_demo
```

### Step 3: Copy Artifacts
```bash
cp -r outputs/* outputs_M23_demo/
```

### Step 4: Analyze Line Breakdown
```bash
wc -l outputs_M23_demo/frc_files/cvff_M23.frc
head -150 outputs_M23_demo/frc_files/cvff_M23.frc
```

### Step 5: Verify msi2lmp Output
Check `outputs_M23_demo/msi2lmp_run/result.json` for:
- Exit code: 0
- Status: "ok"
- CALF20.data created

## 6) Further Reduction Opportunities

### 6.1 Can #define blocks be removed? (78 lines)

**Hypothesis**: msi2lmp.exe may only need ONE `#define cvff` block, not all 4 variants.

**Test**: Create M24 with only `#define cvff` block (remove cvff_nocross, cvff_nomorse, cvff_nocross_nomorse).

**Potential savings**: ~60 lines

### 6.2 Can preamble be minimized? (18 lines)

**Hypothesis**: #version lines may not be required.

**Test**: Create M25 with minimal preamble (only `!BIOSYM` + `#define cvff`).

**Potential savings**: ~15 lines

### 6.3 Theoretical Absolute Minimum

If both reductions work:
- Current M23: 386 lines
- Remove extra #define blocks: ~326 lines
- Remove #version lines: ~311 lines

**Theoretical minimum**: ~300-320 lines

## 7) Success Criteria

1. ✅ M23 produces valid CALF20.data
2. ✅ Line count is 386
3. ✅ SHA256 matches previous M23 runs
4. ✅ Exit code 0 from msi2lmp.exe
5. ✅ All artifacts saved to `outputs_M23_demo/`

## 8) Output Locations

| Artifact | Path |
|----------|------|
| M23 .frc file | `outputs_M23_demo/frc_files/cvff_M23.frc` |
| LAMMPS data | `outputs_M23_demo/msi2lmp_run/CALF20.data` |
| Run manifest | `outputs_M23_demo/run_manifest.json` |
| Validation report | `outputs_M23_demo/validation_report.json` |
| msi2lmp result | `outputs_M23_demo/msi2lmp_run/result.json` |

---

*Plan created: 2025-12-20*
