# Refactor Plan: Max 500 LOC Enforcement

## Summary

This document outlines the refactoring strategy to ensure all source files in the MOLSAIC repository stay under 500 lines of code (LOC).

### Files Exceeding 500 Lines (Mandatory Targets)

| Rank | File Path | Current Lines | Target Split |
|------|-----------|---------------|--------------|
| 1 | `src/upm/src/upm/codecs/msi_frc.py` | 744 | 3 files |
| 2 | `src/external/msi2lmp.py` | 700 | 2-3 files |
| 3 | `src/usm/io/cif.py` | 699 | 2 files |
| 4 | `src/usm/io/mdf.py` | 505 | 2 files |

---

## Detailed Split Strategies

### 1. `src/upm/src/upm/codecs/msi_frc.py` (744 lines → 3 files)

**Current Structure Analysis:**
- Lines 1-42: Module docstring and imports
- Lines 44-98: `parse_frc_text()` - main public parsing API
- Lines 101-174: `read_frc()`, `write_frc()` - public file I/O API
- Lines 177-286: Internal parsing helpers - `_split_sections()`, `_coerce_unknown_sections()`, `_strip_inline_comment()`, `_is_ignorable_line()`
- Lines 289-523: Section parsers - `_parse_atom_types()`, `_parse_quadratic_bond()`, `_parse_quadratic_angle()`
- Lines 526-646: Nonbond parser and table builder - `_parse_nonbond_12_6()`, `_build_tables()`
- Lines 649-744: Export formatters - `_format_atom_types_section()`, `_format_quadratic_bond_section()`, `_format_quadratic_angle_section()`, `_format_nonbond_12_6_section_from_atom_types()`

**Proposed Split:**

```
src/upm/src/upm/codecs/
├── msi_frc.py          # Public API shim + re-exports (~100 lines)
├── _frc_parser.py      # Parsing logic (~320 lines)
└── _frc_writer.py      # Export/formatting logic (~280 lines)
```

| New File | Contents | Estimated Lines |
|----------|----------|-----------------|
| `msi_frc.py` | Public API: `parse_frc_text()`, `read_frc()`, `write_frc()`, re-exports | ~100 |
| `_frc_parser.py` | All `_parse_*` functions, `_split_sections()`, `_coerce_unknown_sections()`, `_build_tables()` | ~320 |
| `_frc_writer.py` | All `_format_*` functions, `_require_df()`, `_fmt_float()` | ~280 |

**Import Compatibility:**
- `from upm.codecs.msi_frc import parse_frc_text, read_frc, write_frc` - preserved
- Internal helpers use underscore-prefix convention to indicate private modules

---

### 2. `src/external/msi2lmp.py` (700 lines → 2-3 files)

**Current Structure Analysis:**
- Lines 1-47: Module docstring and imports
- Lines 49-132: Helper functions - `_frc_looks_cvff_labeled()`, `_build_msi2lmp_argv()`
- Lines 135-203: Execution helpers - `_augment_env()`, `_run()`, `_ensure_file()`, `_stage_file()`, `_sha256_file()`, `_write_result_json()`
- Lines 206-461: Main `run()` function - argument parsing, tool invocation, error handling
- Lines 462-700: Post-processing - `_parse_abc_from_car()`, `_normalize_data_file()` with header/atom Z normalization

**Proposed Split:**

```
src/external/
├── msi2lmp.py           # Public API: run() (~350 lines)
├── _msi2lmp_helpers.py  # Staging, env, argument building (~150 lines)
└── _lmp_normalize.py    # LAMMPS data file post-processing (~200 lines)
```

| New File | Contents | Estimated Lines |
|----------|----------|-----------------|
| `msi2lmp.py` | Public `run()` function (refactored), imports from helpers | ~350 |
| `_msi2lmp_helpers.py` | `_frc_looks_cvff_labeled()`, `_build_msi2lmp_argv()`, `_stage_file()`, `_sha256_file()`, `_write_result_json()`, `_run()` | ~150 |
| `_lmp_normalize.py` | `_parse_abc_from_car()`, `_normalize_data_file()` with all atom/header normalization logic | ~200 |

**Import Compatibility:**
- `from external.msi2lmp import run` - preserved
- Internal helpers moved to private modules

---

### 3. `src/usm/io/cif.py` (699 lines → 2 files)

**Current Structure Analysis:**
- Lines 1-41: Module docstring, imports, constants
- Lines 43-117: CIF parsing utilities - `_strip_quotes()`, `_parse_cif_number()`, `_cif_tokenize()`
- Lines 120-204: CIF structure parsing - `_CifLoop` dataclass, `_parse_cif()`, `_find_atom_site_loop()`
- Lines 207-287: Symmetry operations - `_infer_element_from_label()`, `_parse_symop_string()`, `_parse_symmetry_code()`
- Lines 290-582: `load_cif()` - main loading function with symmetry expansion
- Lines 585-699: `save_cif()` - CIF export function

**Proposed Split:**

```
src/usm/io/
├── cif.py               # Public API: load_cif(), save_cif() + re-exports (~250 lines)
└── _cif_parser.py       # CIF tokenizer, parser, symmetry utilities (~400 lines)
```

| New File | Contents | Estimated Lines |
|----------|----------|-----------------|
| `cif.py` | Public API: `load_cif()`, `save_cif()`, imports from parser | ~250 |
| `_cif_parser.py` | All parsing utilities: `_cif_tokenize()`, `_parse_cif()`, `_CifLoop`, symmetry functions, element inference | ~400 |

**Import Compatibility:**
- `from usm.io.cif import load_cif, save_cif` - preserved
- `from usm.io import cif` patterns preserved

---

### 4. `src/usm/io/mdf.py` (505 lines → 2 files)

**Current Structure Analysis:**
- Lines 1-41: Module docstring, imports, regex patterns
- Lines 43-102: Section splitting - `_split_sections()`, `_current_molecule_name_from_header()`, `_molecule_order()`
- Lines 105-240: Parsing - `_parse_atom_line()`, `_build_bonds_from_connections()`
- Lines 243-302: `load_mdf()` - main loading function
- Lines 306-504: `save_mdf()` and helpers - `_format_float_mdf()`, `_order_token()`, `_compose_connections_for_atom()`

**Proposed Split:**

```
src/usm/io/
├── mdf.py               # Public API: load_mdf(), save_mdf() (~300 lines)
└── _mdf_parser.py       # Parsing utilities, connection building (~200 lines)
```

| New File | Contents | Estimated Lines |
|----------|----------|-----------------|
| `mdf.py` | Public API: `load_mdf()`, `save_mdf()`, format helpers | ~300 |
| `_mdf_parser.py` | `_split_sections()`, `_parse_atom_line()`, `_build_bonds_from_connections()`, regex patterns | ~200 |

**Import Compatibility:**
- `from usm.io.mdf import load_mdf, save_mdf` - preserved

---

## Risk Assessment

### Circular Import Prevention

All proposed splits follow the principle of:
1. Private helper modules (`_*.py`) are imported by the public module
2. No cross-imports between helper modules
3. Types/dataclasses extracted to shared modules if needed

### Initialization Order

- No module-level initialization side effects in these files
- Safe to split without runtime behavior changes

### Performance Hotspots

- None of these files contain performance-critical tight loops
- Import overhead of split modules is negligible

---

## Implementation Order

Execute refactoring in order of file size (largest first):

1. **`msi_frc.py`** (744 → 3 files) - Largest, most complex
2. **`msi2lmp.py`** (700 → 2-3 files) - Second largest
3. **`cif.py`** (699 → 2 files) - Similar size to msi2lmp
4. **`mdf.py`** (505 → 2 files) - Smallest, simplest split

---

## Commit Strategy

Each file split should be a separate commit:

```
refactor(upm/codecs): split msi_frc.py into 3 modules
refactor(external): split msi2lmp.py into 3 modules  
refactor(usm/io): split cif.py into 2 modules
refactor(usm/io): split mdf.py into 2 modules
chore: add line-limit check script to CI
docs: add REFACTOR_MAP.md with file mappings
```

---

## Verification Checklist

After each file split:

- [ ] All existing imports still work
- [ ] Unit tests pass for that module
- [ ] Integration tests pass
- [ ] New file is ≤500 lines
- [ ] Public API unchanged
- [ ] No circular imports introduced

After all splits complete:

- [ ] Full test suite passes
- [ ] All source files ≤500 lines
- [ ] `scripts/check_max_lines.py` exits 0
- [ ] `REFACTOR_MAP.md` documents all changes
