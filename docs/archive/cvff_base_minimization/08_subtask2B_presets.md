# Subtask 2B: Stall Failure Analysis and Combined Presets E11+

## 1. Executive Summary

All 10 single-factor experiments (E1-E10) **STALLED** when tested against `msi2lmp.exe`. This indicates the root cause is either:
1. A **combination of multiple factors** working together
2. A **factor not yet covered** in the H1-H6 hypothesis set
3. A **fundamental structural difference** between from-scratch `.frc` and working asset

This document captures the deep structural comparison between the working asset [`cvff_Base_MXenes.frc`](workspaces/forcefields/cvff_Base_MXenes.frc:1) and the from-scratch baseline, identifies new hypotheses (H7+), and designs combined presets (E11+) for testing.

## 2. Deep Structural Comparison

### 2.1 Preamble Line Differences

| Element | Working Asset | From-Scratch |
|---------|---------------|--------------|
| First line | `!BIOSYM forcefield          1` | `!BIOSYM forcefield` |
| Suffix | Has numeral `1` with 10 spaces | No numeral suffix |
| Version lines | 16 `#version cvff.frc X.X DD-Mon-YY` lines | None |

### 2.2 Macro Definition Structure

| Element | Working Asset | From-Scratch |
|---------|---------------|--------------|
| Number of macros | **FOUR** macros defined | **ONE** macro defined |
| Macro order | `cvff_nocross_nomorse` → `cvff` → `cvff_nocross` → `cvff_nomorse` | `cvff` only |
| Cross-terms in cvff | Yes: bond-bond, bond-angle, angle-angle-torsion_1, out_of_plane-out_of_plane, angle-angle | No cross-terms |

### 2.3 Macro Table Content Differences

**Working asset `cvff` macro table:**
```
 2.0  18    atom_types				cvff
 1.0   1    equivalence				cvff
 2.0  18    auto_equivalence     		cvff_auto
 1.0   1    hbond_definition			cvff
 2.0  18    morse_bond				cvff   cvff_auto
 2.0  18    quadratic_angle			cvff   cvff_auto
 2.0  18    torsion_1				cvff   cvff_auto
 2.0  18    out_of_plane			cvff   cvff_auto
 1.0   1    bond-bond				cvff
 1.0   1    bond-angle				cvff
 1.0   1    angle-angle-torsion_1		cvff
 1.0   1    out_of_plane-out_of_plane		cvff
 1.0   1    angle-angle				cvff
 1.0   1    nonbond(12-6)			cvff
```

**From-scratch macro table:**
```
   1.0   1    atom_types				cvff
   1.0   1    equivalence				cvff
   2.0  18    auto_equivalence				cvff_auto
   1.0   1    quadratic_bond				cvff
   1.0   1    morse_bond				cvff
   1.0   1    quadratic_angle				cvff
   1.0   1    torsion_1				cvff   cvff_auto
   1.0   1    out_of_plane				cvff   cvff_auto
   1.0   1    bond_increments				cvff
   1.0   1    nonbond(12-6)				cvff
```

**Key differences:**
1. Ver/ref in macro table: Asset uses `2.0 18` for atom_types and bonded sections; from-scratch uses `1.0 1`
2. Bond model: Asset's `cvff` has **only morse_bond**; from-scratch has **BOTH quadratic_bond AND morse_bond**
3. Cross-terms: Asset references cross-term sections; from-scratch has none
4. hbond_definition: Present in asset macro table but missing in from-scratch

### 2.4 HBond Definition Section

| Element | Working Asset | From-Scratch |
|---------|---------------|--------------|
| donors | `donors hn h* hspc htip` | `donors` (EMPTY) |
| acceptors | `acceptors o' o o* ospc otip` | `acceptors` (EMPTY) |

### 2.5 Description Lines

| Element | Working Asset | From-Scratch |
|---------|---------------|--------------|
| After `#atom_types` | `> Atom type definitions for any variant of cvff` | None |
| After `#equivalence` | `> Equivalence table for any variant of cvff` | None |
| Pattern | Most sections have `> Description...` | No description lines |

### 2.6 Auto-Equivalence Row Format

**Working asset:**
```
 2.0  18    h     h     h     h_       h_       h_        h_        h_           h_       h_
```
Uses suffixed types (e.g., `h_`) for automatic lookup columns.

**From-scratch:**
```
  2.0 18 C_MOF C_MOF C_MOF C_MOF C_MOF C_MOF C_MOF C_MOF C_MOF C_MOF
```
Uses the same source type for all columns (no suffixes).

## 3. New Hypotheses (H7-H11)

### H7 — Empty HBond Donors/Acceptors Causes Parsing Loop

- **Trigger**: `#hbond_definition` with empty `donors` and `acceptors` lines
- **Evidence**: Working asset has populated donor/acceptor lists; from-scratch leaves them empty
- **Why it could stall**: Parser may loop waiting for atom type tokens when lines are present but empty

### H8 — Macro Table Ver/Ref Mismatch

- **Trigger**: Using `1.0 1` in macro table for functions that should be `2.0 18`
- **Evidence**: Asset uses `2.0 18` for atom_types, auto_equivalence, and bonded terms in macro table; from-scratch uses `1.0 1`
- **Why it could stall**: Ver/ref in macro table may trigger different lookup paths

### H9 — Both Bond Models in Single Macro Table

- **Trigger**: Listing BOTH `quadratic_bond` AND `morse_bond` in the same macro definition
- **Evidence**: Asset's `cvff` macro only lists `morse_bond`; from-scratch lists both
- **Why it could stall**: Internal conflict between competing bond model assignment paths

### H10 — Missing Description Lines After Section Headers

- **Trigger**: Absence of `> Description text` lines after `#section label` headers
- **Evidence**: Working asset has description lines; from-scratch omits them
- **Why it could stall**: Parser may expect/consume description text differently

### H11 — Single Macro Definition vs Multiple Alternates

- **Trigger**: Only one `#define` macro vs four alternate definitions
- **Evidence**: Asset defines cvff_nocross_nomorse, cvff, cvff_nocross, cvff_nomorse; from-scratch only has cvff
- **Why it could stall**: Parser may need fallback macros for certain resolution paths

## 4. Combined Presets Design (E11-E15)

### E11 — Full Asset-Like Configuration

**Rationale**: Apply ALL asset-like settings simultaneously. If this passes, we have a working baseline to minimize from.

```python
CvffFrcEmitOptions(
    preamble_style="asset_like",
    emit_macro_table=True,
    macro_table_format="asset_tabs",
    header_label_separator="tab",
    header_trailing_space=False,
    section_order="asset_like",
    ver_ref_policy="normalize_2_0_18",
    emit_equivalence=True,
    emit_auto_equivalence=True,
    bond_model="morse_only",
    emit_wildcard_torsion=True,
    emit_wildcard_oop=True,
)
```

### E12 — cvff_nocross_nomorse Profile + Asset-Like Formatting

**Rationale**: Use the simpler `cvff_nocross_nomorse` macro (which matches our from-scratch structure more closely) with asset-like formatting.

```python
CvffFrcEmitOptions(
    cvff_define="cvff_nocross_nomorse",
    preamble_style="asset_like",
    emit_macro_table=True,
    macro_table_format="asset_tabs",
    header_label_separator="tab",
    section_order="asset_like",
    ver_ref_policy="normalize_2_0_18",
    bond_model="quadratic_only",
    emit_wildcard_torsion=True,
    emit_wildcard_oop=True,
)
```

### E13 — Structural Triple (preamble + section_order + ver_ref)

**Rationale**: Test the three most impactful structural factors together.

```python
CvffFrcEmitOptions(
    preamble_style="asset_like",
    section_order="asset_like",
    ver_ref_policy="normalize_2_0_18",
)
```

### E14 — Formatting Triple (preamble + macro_table_format + header)

**Rationale**: Test formatting factors that affect tokenization.

```python
CvffFrcEmitOptions(
    preamble_style="asset_like",
    emit_macro_table=True,
    macro_table_format="asset_tabs",
    header_label_separator="tab",
)
```

### E15 — Minimal Complexity (no wildcards + no auto_equivalence + morse_only)

**Rationale**: Reduce parameter resolution complexity to simplify the search space.

```python
CvffFrcEmitOptions(
    emit_auto_equivalence=False,
    emit_wildcard_torsion=False,
    emit_wildcard_oop=False,
    bond_model="morse_only",
)
```

## 5. Implementation Requirements

### 5.1 New Options Needed in CvffFrcEmitOptions

Based on the new hypotheses, consider adding:

1. **`emit_hbond_donors_acceptors: bool`** — Control whether to populate donors/acceptors (H7)
2. **`macro_table_ver_ref_style: Literal["current", "asset_like"]`** — Control ver/ref in macro table rows (H8)
3. **`emit_description_lines: bool`** — Add `> Description` after section headers (H10)

### 5.2 Presets to Add to CVFF_FRC_EXPERIMENT_PRESETS

```python
"E11": CvffFrcEmitOptions(
    preamble_style="asset_like",
    emit_macro_table=True,
    macro_table_format="asset_tabs",
    header_label_separator="tab",
    header_trailing_space=False,
    section_order="asset_like",
    ver_ref_policy="normalize_2_0_18",
    emit_equivalence=True,
    emit_auto_equivalence=True,
    bond_model="morse_only",
    emit_wildcard_torsion=True,
    emit_wildcard_oop=True,
),
"E12": CvffFrcEmitOptions(
    cvff_define="cvff_nocross_nomorse",
    preamble_style="asset_like",
    emit_macro_table=True,
    macro_table_format="asset_tabs",
    header_label_separator="tab",
    section_order="asset_like",
    ver_ref_policy="normalize_2_0_18",
    bond_model="quadratic_only",
    emit_wildcard_torsion=True,
    emit_wildcard_oop=True,
),
"E13": CvffFrcEmitOptions(
    preamble_style="asset_like",
    section_order="asset_like",
    ver_ref_policy="normalize_2_0_18",
),
"E14": CvffFrcEmitOptions(
    preamble_style="asset_like",
    emit_macro_table=True,
    macro_table_format="asset_tabs",
    header_label_separator="tab",
),
"E15": CvffFrcEmitOptions(
    emit_auto_equivalence=False,
    emit_wildcard_torsion=False,
    emit_wildcard_oop=False,
    bond_model="morse_only",
),
```

## 6. Execution Priority

1. **E11** (full asset-like) — Highest priority; if this passes, confirms combination theory
2. **E12** (nocross_nomorse) — Tests simpler macro profile
3. **E13** (structural triple) — Tests key structural factors
4. **E14** (formatting triple) — Tests tokenization factors
5. **E15** (minimal complexity) — Tests reduced parameter space

## 7. Success Criteria

1. At least ONE combined preset produces `exit_code=0` and non-empty `CALF20.data`
2. If E11 passes, perform A/B/A confirmation to prove determinism
3. Minimize the winning config to identify the essential factor combination
4. Document the confirmed hypothesis combination

## 8. Files to Modify

1. **Builder**: [`src/upm/src/upm/build/frc_from_scratch.py`](src/upm/src/upm/build/frc_from_scratch.py:708) — Add E11-E15 presets
2. **Thrust log**: [`docs/DevGuides/thrust_log_nist_calf20_msi2lmp_stall.md`](docs/DevGuides/thrust_log_nist_calf20_msi2lmp_stall.md:337) — Add Section 13 with this analysis
