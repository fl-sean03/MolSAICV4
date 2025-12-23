# DevGuide_v0.1.2 — MolSAIC TermSet + ParameterSet bridge + UPM from-scratch `.frc` builder (nonbonded-only)

**Goal (v0.1.2):** Add a **coordinate-free, deterministic bridge** from **USM structures** to **UPM parameter export**, using two explicit artifacts:

- **TermSet**: structure-derived *typed interaction inventory* (no numeric parameters)
- **ParameterSet**: numeric per-atom-type assignments (mass + LJ; no charges)

Then implement a **from-scratch** UPM builder that consumes `(TermSet, ParameterSet, mode=nonbonded_only)` and outputs a valid MSI-style `.frc` containing **only** `#atom_types` and `#nonbond(12-6)`.

This milestone is explicitly designed for **rigid-framework / nonbond-only** workflows, while keeping TermSet extensible for future flexible bonded terms.

---

## The architecture in one picture

```
MolSAIC (repo)
  ├─ workspaces/
  │    └─ 03_termset_parameterset_to_frc_nonbond_only/
  │         ├─ run.py
  │         ├─ config.json
  │         └─ outputs/
  ├─ src/usm/ (submodule)
  │    └─ ops/
  │         ├─ termset.py          <- NEW: derive + write TermSet
  │         └─ parameterset.py     <- NEW: derive + write ParameterSet (optional)
  ├─ src/upm/ (submodule)
  │    ├─ io/
  │    │    ├─ termset.py          <- NEW: read TermSet JSON
  │    │    └─ parameterset.py     <- NEW: read ParameterSet JSON
  │    ├─ build/
  │    │    └─ frc_from_scratch.py <- NEW: build `.frc` from TermSet + ParameterSet
  │    └─ cli/
  │         └─ commands/
  │              └─ build_frc.py   <- NEW: `upm build-frc`
  └─ tests/
       ├─ unit/
       └─ integration/
```

**Key boundary:** Charges remain on the **structure side** (USM atoms). v0.1.2 does **not** add any charge logic to UPM.

## Implementation notes (repo-tailored)

These are the repo-specific “gotchas” and best practices that make v0.1.2 run reliably in CI and on fresh machines.

1) **Use the workspace bootstrap pattern to avoid environment shadowing**

- Workspaces should be directly runnable via `python workspaces/.../run.py` without editable installs.
- Follow the self-bootstrapping pattern (add repo `src/` roots to `sys.path`) so the workspace imports the repo code even if an older `molsaic`/`upm` is installed in the environment.
- Reference implementation: [`_bootstrap_repo_src_on_path()`](workspaces/03_termset_parameterset_to_frc_nonbond_only/run.py:27)

2) **Determinism is enforced as byte-stability + hash-based artifacts**

- JSON artifacts must be written with pinned serialization (`indent=2`, `sort_keys=True`, newline) and deterministic ordering.
- Workspace manifests must avoid absolute paths and timestamps, and should include SHA256 checksums of produced artifacts.
- Reference helpers: [`write_json_stable()`](src/molsaic/manifest_utils.py:27), [`sha256_file()`](src/molsaic/manifest_utils.py:12)

3) **UPM MSI `.frc` codec constraints: nonbond directives are required**

- For `#nonbond(12-6)` sections, UPM requires both directives to appear:
  - `@type A-B`
  - `@combination geometric`
- This is enforced by the parser in [`_parse_nonbond_12_6()`](src/upm/src/upm/codecs/msi_frc.py:530).

---

## Repo-tailored notes (important)

1) The USM schema already includes per-atom parameter columns used for this milestone:

- `mass_amu`, `lj_sigma_angstrom`, `lj_epsilon_kcal_mol` in [`ATOMS_DTYPES`](src/usm/core/model.py:9)

2) UPM’s MSI `.frc` pipeline validates that `lj_a` and `lj_b` are non-null for every exported `atom_type`.
This comes from [`validate_atom_types()`](src/upm/src/upm/core/validate.py:148).
Implication: the nonbond-only builder must emit nonbonded params for *all* TermSet atom types.

3) Workspace execution should follow the v0.1.1 “self-bootstrapping” pattern to avoid Python environment shadowing.
Use the bootstrap utility pattern from [`_bootstrap_repo_src_on_path()`](workspaces/02_usm_upm_msi2lmp_pipeline/run.py:29) so `python run.py` works even without editable installs.

---

## Scope

### In-scope
1. **USM → TermSet export**
   - Deterministically derive **unique** `atom_types`, `bond_types`, `angle_types`, `dihedral_types`, `improper_types` from a USM object.
   - Store optional **counts** per term key for sanity checks.
   - Export stable JSON (`indent=2`, `sort_keys=True`, newline) with deterministic ordering.

2. **USM → ParameterSet export (optional)**
   - If per-atom parameter columns exist and are complete/consistent within each `atom_type`, derive per-type:
     - `mass_amu`
     - `lj_sigma_angstrom`
     - `lj_epsilon_kcal_mol`
     - (optional) `element` (if consistent)
   - If missing or inconsistent for any type: raise a deterministic error and/or write a “missing/ambiguous types” report (see below).

3. **UPM from-scratch `.frc` builder (nonbonded-only)**
   - Validate ParameterSet covers all TermSet atom types.
   - Convert `(sigma, epsilon)` → `(A, B)` for MSI `#nonbond(12-6)` with `@combination geometric`.
   - Emit `.frc` with only:
     - `#atom_types upm`
     - `#nonbond(12-6) upm`
   - Deterministic ordering + deterministic float formatting.

4. **Workspace demo + tests**
   - No external input files required; workspace generates a tiny USM object in code.
   - Unit tests for derivation + builder.
   - Integration determinism test (run workspace twice; byte-equality on outputs).

### Explicitly out-of-scope (v0.1.2)
- Any bonded parameter export (bonds/angles/dihedrals/impropers coefficients).
- Any `.prm` generation.
- Any dependency on Materials Studio files, Packmol, `msi2lmp`, or external executables.
- Any changes to the v0.1.1 golden pipeline (keep it passing).

---

## Terminology (use this consistently)

- **TermSet** (structure-derived): “What terms exist in the structure if we wanted to parameterize it?”
  - No numbers.
  - Coordinate-free.
  - Small (unique keys, optional counts), even for large systems.

- **ParameterSet** (authoring/assignment): “What numeric values do we assign to each atom type?”
  - Numbers only (mass + LJ in v0.1.2).
  - Still coordinate-free.
  - Can be derived from USM if USM has complete per-atom parameter fields.

---

## Data contracts

### Contract A — TermSet JSON (`molsaic.termset.v0.1.2`)
**File:** `termset.json`

**Fields (required):**
- `schema`: `"molsaic.termset.v0.1.2"`
- `atom_types`: list[str] (sorted, unique)
- `bond_types`: list[[t1,t2]] where `t1 <= t2` (sorted unique)
- `angle_types`: list[[t1,t2,t3]] canonicalized with endpoints `t1 <= t3` (sorted unique)
- `dihedral_types`: list[[t1,t2,t3,t4]] canonicalized by lexicographic min of (forward, reverse) (sorted unique)
- `improper_types`: list[[t1,t2,t3,t4]] canonicalized with `t2` as central and peripheral sorted (`t1 <= t3 <= t4`) (sorted unique)

**Fields (optional, but recommended):**
- `counts`: dict with per-term-key counts (deterministic key encoding)
- `provenance`: dict (sha256 of a USM bundle if available, git commits if available)

**Deterministic key encoding (for counts):**
- bonds: `"t1|t2"`
- angles: `"t1|t2|t3"`
- dihedrals: `"t1|t2|t3|t4"`
- impropers: `"t1|t2|t3|t4"`

### Contract B — ParameterSet JSON (`upm.parameterset.v0.1.2`)
**File:** `parameterset.json`

**Fields (required):**
- `schema`: `"upm.parameterset.v0.1.2"`
- `atom_types`: object mapping `atom_type -> { mass_amu, lj_sigma_angstrom, lj_epsilon_kcal_mol }`

**Fields (optional):**
- `atom_types[*].element`: string
- `provenance`: dict (source, git, notes)
- `units`: explicit units block (defaults assumed if omitted)

### Contract C — `.frc` output (UPM from-scratch)
**File:** `ff_nonbond_only.frc`

**Sections emitted (fixed order):**
1. `#atom_types upm`
2. `#nonbond(12-6) upm` with:
   - `@type A-B`
   - `@combination geometric`
   - rows containing per-type `A` and `B`

**Conversion (LJ 12-6):**
- Given sigma (Å), epsilon (kcal/mol):
  - `A = 4 * epsilon * sigma^12`
  - `B = 4 * epsilon * sigma^6`

**Float formatting:**
- Use a single shared formatter for all numeric emission:
  - Recommended: reuse UPM’s existing stable float formatter [`_fmt_float()`](src/upm/src/upm/codecs/msi_frc.py:662) (currently `"%.8g"`), or explicitly pin the builder to a single `%.Ng` format and test byte-stability.
  - Determinism is more important than “pretty” formatting.

Note on section headers

UPM’s parser accepts header suffixes (e.g., `#atom_types upm`) because it uses the first token as the section key.
However, UPM’s built-in writer currently emits `#atom_types` / `#nonbond(12-6)` without suffix.
For v0.1.2, either:

- (A) Write `.frc` manually with `#atom_types upm` and `#nonbond(12-6) upm` (preferred if you want explicit provenance in output)
- (B) Build canonical tables and call [`write_frc()`](src/upm/src/upm/codecs/msi_frc.py:108) (preferred if you want to reuse the codec’s formatting and ordering)

---

## Canonicalization rules (MUST match across USM + UPM)

### Bonds
- key = `(t1, t2)` with `t1 <= t2`

### Angles
- key = `(t1, t2, t3)` where endpoints are canonical:
  - if `t1 > t3`, reverse to `(t3, t2, t1)`

### Dihedrals
- candidate forward: `(t1, t2, t3, t4)`
- candidate reverse: `(t4, t3, t2, t1)`
- choose `min(forward, reverse)` lexicographically

### Impropers (generic)
In v0.1.2, implement a conservative canonicalization:
- assume `t2` is the “central” type in the generated order
- sort the remaining three peripheral types `(t1, t3, t4)` ascending
- key becomes `(p1, t2, p2, p3)` with `p1 <= p2 <= p3`

> Note: This is a placeholder canonicalization intended for inventory consistency, not force-field semantics. For real improper support later, we may need chemistry-aware central selection.

---

## Implementation plan (self-contained thrusts)

### Thrust A — USM: TermSet derivation + JSON writer

**Add files:**
- `src/usm/ops/termset.py`
- `src/usm/tests/test_termset_derivation.py`

**Public API:**
- `derive_termset_v0_1_2(structure) -> dict`
- `write_termset_json(termset: dict, path: str) -> str`
- Convenience:
  - `export_termset_json(usm, path) -> str` (derive + write)

**Derivation algorithm (deterministic):**
1. Atom types:
   - unique sorted from `structure.atoms["atom_type"]`

2. Bonds:
   - assume `structure.bonds` table exists with columns `a1`, `a2` (aid indices)
   - for each bond:
     - map endpoints to `atom_type`
     - canonicalize `(t1,t2)` with `t1<=t2`
   - unique + sorted

3. Angles (from adjacency):
   - build adjacency lists from `usm.bonds`
   - for each central atom `j`:
     - get sorted unique neighbor aids: `neighbors(j)`
     - for each unordered pair `(i,k)` with `i < k`:
       - types `(ti, tj, tk)`
       - canonicalize endpoints (`ti <= tk`)
   - unique + sorted

4. Dihedrals (from adjacency, best-effort):
   - for each bond `(j,k)`:
     - for each neighbor `i` of `j` where `i != k`:
       - for each neighbor `l` of `k` where `l != j`:
         - types `(ti, tj, tk, tl)`
         - canonicalize by min(forward, reverse)
   - unique + sorted
   - (Optionally compute counts as number of occurrences; keep deterministic)

5. Impropers (best-effort):
   - for each atom `j` with degree >= 3:
     - choose all triples `(i,k,l)` from neighbors
     - types `(ti, tj, tk, tl)`
     - canonicalize with `tj` central and peripherals sorted
   - unique + sorted

**JSON determinism requirements:**
- `json.dumps(..., sort_keys=True, indent=2)`
- file ends with `\n`
- lists already sorted; don’t rely on `sort_keys` for list order.

**Acceptance tests (USM):**
- deterministic under bond row order changes
- deterministic under atom row order changes (after renumbering)
- expected canonicalization for a small hand-built structure

---

### Thrust B — USM: ParameterSet derivation + JSON writer (optional export)

**Add files:**
- `src/usm/ops/parameterset.py`
- `src/usm/tests/test_parameterset_derivation.py`

**Public API:**
- `derive_parameterset_v0_1_2(usm) -> dict`
- `write_parameterset_json(pset: dict, path: str) -> str`
- Convenience:
  - `export_parameterset_json(usm, path) -> str`

**Rules:**
- ParameterSet can only be derived if, for every `atom_type` present:
  - `mass_amu` is present and identical across atoms of that type (within tolerance)
  - `lj_sigma_angstrom` is present and identical across atoms of that type
  - `lj_epsilon_kcal_mol` is present and identical across atoms of that type
- Optional `element` is included only if consistent across atoms of that type.

Implementation recommendation (repo-tailored):

- Treat the input as *duck-typed*: require `.atoms` DataFrame and optional `.bonds` DataFrame, so this works for both [`usm.core.model.USM`](src/usm/core/model.py:94) and any “USM-like” structure object.
- When emitting `.frc`, if element is unavailable you must still emit a token in the `#atom_types` row; choose a deterministic placeholder (e.g., `"X"`) and record that in notes.

**Deterministic error reporting:**
Create a typed error:
- `ParameterSetDerivationError(missing_types=[...], inconsistent_types=[...], details={...})`
- ensure lists are sorted for deterministic messages.

**Tests:**
- missing optional columns -> deterministic error listing missing types
- inconsistent values within a type -> deterministic error
- successful derivation -> stable JSON bytes

---

### Thrust C — UPM: IO for TermSet + ParameterSet

**Add files:**
- `src/upm/src/upm/io/termset.py`
- `src/upm/src/upm/io/parameterset.py`
- `src/upm/tests/test_termset_parameterset_io.py`

**Public API:**
- `read_termset_json(path) -> TermSet` (dataclass or validated dict)
- `read_parameterset_json(path) -> ParameterSet`
- minimal schema validation:
  - required fields exist
  - types are correct
  - keys canonicalized (UPM re-checks invariants and errors if violated)

---

### Thrust D — UPM: from-scratch `.frc` builder (nonbonded-only)

**Add files:**
- `src/upm/src/upm/build/frc_from_scratch.py`
- `src/upm/tests/test_build_frc_from_scratch.py`

**Public API:**
- `build_frc_nonbond_only(termset: TermSet, pset: ParameterSet, *, out_path: str, include_comments: bool=True) -> str`
- `make_tables_nonbond_only(termset, pset) -> dict[str, pd.DataFrame]` (optional, if you prefer reusing existing codec writer)

**Validation rules:**
- every `atom_type` in `termset.atom_types` must exist in `pset.atom_types`
- numeric fields must be finite and:
  - `mass_amu > 0`
  - `sigma > 0` (allow small positive; reject 0)
  - `epsilon >= 0` (allow 0 if you want “purely repulsive” off; default reject if you prefer strict)

**Deterministic missing report:**
- Raise `MissingTypesError(missing_atom_types=[sorted list])`

**Output writer rules:**
- atom types rows sorted by atom_type
- nonbond rows sorted by atom_type
- deterministic header and section formatting
- numeric formatting uses `UPM_FLOAT_FMT="%.10g"`

**Builder output must be re-importable by UPM MSI `.frc` codec** (roundtrip check in tests):
- Write `.frc`
- Re-import with existing `msi_frc` parser
- Compare canonical tables to expected.

Repo-tailored best practice:

- Ensure the builder always emits the two required directives inside `#nonbond(12-6)`:
  - `@type A-B`
  - `@combination geometric`

These are enforced by the parser in [`_parse_nonbond_12_6()`](src/upm/src/upm/codecs/msi_frc.py:530).

---

### Thrust E — UPM CLI: `upm build-frc`

**Add file:**
- `src/upm/src/upm/cli/commands/build_frc.py`
- register command in `src/upm/src/upm/cli/main.py`

**Command:**
```
upm build-frc \
  --termset path/to/termset.json \
  --parameters path/to/parameterset.json \
  --mode nonbonded-only \
  --out outputs/ff_nonbond_only.frc
```

v0.1.2 supports only `--mode nonbonded-only` (error otherwise).

---

### Thrust F — MolSAIC workspace: end-to-end demo (no external files)

**Add workspace:**
- `workspaces/03_termset_parameterset_to_frc_nonbond_only/`
  - `run.py`
  - `config.json`
  - `README.md` (short)

**Workspace behavior (deterministic):**
1. Construct a tiny USM object in code:
   - atoms: 6–12 atoms with `atom_type`, `element`, and (optionally) mass/LJ columns filled
   - bonds: a small graph that yields angles + dihedrals (even if unused in builder)
   - cell: simple orthorhombic cell (optional)

2. Export:
   - `outputs/termset.json` via USM Thrust A
   - `outputs/parameterset.json` via:
     - if config says `derive_from_usm=true`, call USM Thrust B
     - else, write a manual ParameterSet dict inside `run.py` (still deterministic)

3. Call UPM:
   - either via Python import (preferred) or subprocess `upm build-frc`
   - produce `outputs/ff_nonbond_only.frc`

4. Write a deterministic `run_manifest.json` (same policies as v0.1.1):
   - no absolute paths
   - no timestamps
   - include sha256 of outputs

**Workspace acceptance:**
- Running `python run.py` twice yields byte-identical:
  - `termset.json`
  - `parameterset.json` (if derived, must be deterministic)
  - `ff_nonbond_only.frc`
  - `run_manifest.json`

---

### Thrust G — Tests (unit + integration determinism)

**USM unit tests**
- `src/usm/tests/test_termset_derivation.py`
- `src/usm/tests/test_parameterset_derivation.py`

**UPM unit tests**
- `src/upm/tests/test_termset_parameterset_io.py`
- `src/upm/tests/test_build_frc_from_scratch.py`

**MolSAIC integration test**
- `tests/integration/test_workspace_03_termset_parameterset_determinism.py`

**Integration test pattern (same as v0.1.1):**
- run the workspace twice into two temp dirs
- assert byte-equality on outputs
- parse JSON and assert dict equality (sanity)
- ensure `.frc` can be re-imported by UPM codec

---

## Developer notes (important edge cases)

1. **TermSet must stay small**
   - store unique keys + counts, not per-instance terms.
   - do not dump full bond lists.

2. **ParameterSet must stay per-type**
   - do not store per-atom values.
   - enforce consistency (or error).

3. **Keep v0.1.1 pipeline intact**
   - do not rename existing Requirements or golden workspace artifacts.
   - v0.1.2 adds new features; it does not replace v0.1.1.

4. **No external executables**
   - All tests and workspaces must run in CI without MSI tools.

---

## Acceptance Tests (must all pass)

### AT1 — USM TermSet derivation determinism
- For a fixed USM, permuting bond row order and atom row order yields identical `termset.json` bytes.

### AT2 — USM ParameterSet derivation correctness
- Missing columns or missing values yields deterministic `ParameterSetDerivationError` with sorted lists.
- Inconsistent per-type values yields deterministic error.
- Complete consistent columns yields deterministic JSON output.

### AT3 — UPM from-scratch builder correctness
- Missing ParameterSet entries for any TermSet type yields deterministic `MissingTypesError`.
- Successful build emits `.frc` containing only required sections and directives.

### AT4 — Roundtrip via UPM MSI codec
- `.frc` produced by builder re-imports and matches expected canonical tables.

### AT5 — Workspace determinism regression
- `workspaces/03.../run.py` run twice yields byte-identical key outputs and manifest.

---

## Completion checklist

- [ ] USM: `ops/termset.py` implemented + tests green
- [ ] USM: `ops/parameterset.py` implemented + tests green
- [ ] UPM: IO modules for TermSet/ParameterSet implemented + tests green
- [ ] UPM: builder implemented + tests green
- [ ] UPM: CLI command registered + smoke-tested
- [ ] Workspace 03 added + deterministic manifest
- [ ] Integration determinism test added and green
- [ ] `pytest -q` passes in the monorepo

---

## Deliverables (what the developer should produce)

1. New code in USM + UPM as listed above.
2. A runnable workspace:
   - `python workspaces/03_termset_parameterset_to_frc_nonbond_only/run.py`
3. A new integration test proving determinism.
4. A short v0.1.2 implementation report (same style as v0.1.0/v0.1.1 reports) after completion.
