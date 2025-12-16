# DevGuide_v0.1.1 — MolSAIC (USM + UPM + External Wrappers + Workspaces)

Owner: Heinz Lab / MolSAIC Team  
Audience: MolSAIC team (junior devs included; strong coders, limited working memory)  
Goal: **v0.1.1 integrated milestone** that upgrades UPM capability and proves the full end-to-end MolSAIC pipeline deterministically.

**Starting point:** MolSAIC monorepo with `src/usm/` and `src/upm/` as submodules (or vendored), `src/external/` wrappers, and `workspaces/` pipelines.

---

## 0) The architecture in one picture

```
MolSAIC (repo)
  ├─ workspaces/          <- “pipelines”: plain run.py scripts that produce outputs/
  ├─ src/usm/             <- structures: atoms+bonds+cell, deterministic ops, I/O
  ├─ src/upm/             <- parameters: versioned FF packages, validate, export
  └─ src/external/        <- wrappers around executables (packmol, msi2lmp, ...)
```

MolSAIC’s whole point is **code-first, deterministic pipelines built from small composable blocks** (USM + UPM + thin external wrappers), executed as simple `workspaces/*/run.py` scripts.

---

## 1) v0.1.1 outcome (what “done” means)

### 1.1 Primary outcome: one “golden” integrated pipeline demo

A new workspace must run end-to-end, deterministically:

**USM (CAR+MDF) → Requirements → UPM minimal .frc → external/msi2lmp → LAMMPS data + manifest**

Deliverables from the workspace:
- `outputs/` contains:
  - `structure.usm_bundle/` (optional but recommended)
  - `requirements.json`
  - `ff_minimal.frc`
  - `msi2lmp/` run folder (stdout/stderr captured)
  - `lammps.data` (or whatever `msi2lmp` emits)
  - `run_manifest.json` (hashes + versions + command lines)

The workspace must be runnable via:
```bash
python workspaces/02_usm_upm_msi2lmp_pipeline/run.py
```

### 1.2 Secondary outcome: UPM feature bump required for real systems

UPM must support (at minimum):
- **Angles** end-to-end: parse/validate/resolve/export `#quadratic_angle`
- **Requirements derivation** without hand-editing:
  - from a standalone `structure.json` (toy schema) inside UPM
  - and from a USM object via a MolSAIC-side adapter (no hard dependency inside UPM)
- **Missing-term modes**:
  - default: hard error
  - debug: `--allow-missing` writes `missing.json` and continues
  - `--force` can exit 0 even if missing (rare; use intentionally)
- **Unknown-section handling**:
  - preserve unknown `.frc` sections on import
  - export policy is explicit:
    - default: omit raw/unknown sections
    - optional: `--include-raw` re-emits them deterministically

### 1.3 Determinism requirements (non-negotiable)

- Stable ordering for all derived topology (bond/angle/dihedral enumeration).
- Stable float formatting in `.frc` export (one formatting strategy, used everywhere).
- All tool wrappers write a versioned, hashed “result envelope”.
- All workspaces write an explicit manifest of inputs/outputs and tool versions.

---

## 2) Scope boundaries (what belongs where)

### 2.1 USM responsibilities
- Structure normalization (CAR/MDF/CIF/PDB-ish) → one schema (atoms, optional bonds, cell)
- Deterministic structural ops and bundling
- **Charges live here** (structure side)
- **Derive topology requirements** from a structure for downstream parameter selection:
  - Produce a `requirements.json` (v0.1 schema) from `atoms.atom_type` + optional `bonds` (and derived angles)
  - This must be deterministic (stable ordering, canonical keys)
  - This must remain **UPM-independent** (USM outputs plain JSON/dicts; no `import upm`)

### 2.2 UPM responsibilities
- Force-field packages (versioned bundles + manifest + raw section preservation)
- Parsing/export of supported `.frc` sections (v0.1.1 adds angles)
- Resolver to create minimal `.frc` given Requirements
- CLI for import/validate/export/derive-req (UPM can remain standalone)

### 2.3 MolSAIC responsibilities
- Orchestration: call USM to derive `requirements.json`, then call UPM resolver/export
- External wrappers (msi2lmp, packmol, etc.) with deterministic envelopes
- Workspaces as the only “workflow engine”
- Cross-repo integration tests (workspace regression)

**Design rule:** Avoid duplicating UPM’s parameter logic in MolSAIC. Avoid duplicating USM’s topology-derivation logic in MolSAIC. MolSAIC orchestrates: **USM → Requirements → UPM minimal `.frc` → external tool**.

---

## 3) Repository layout changes (v0.1.1)

### 3.1 MolSAIC
Add:
- `workspaces/02_usm_upm_msi2lmp_pipeline/`
  - `run.py`
  - `config.json` (optional; recommended)
  - `outputs/` (created at runtime)
- `src/external/msi2lmp.py` wrapper improvements (see section 7)

Notes:
- MolSAIC no longer owns a USM→Requirements “bridge” module. Requirements derivation is implemented inside USM (see 3.3).

### 3.2 UPM submodule
Update:
- add angle support in codec + tables + resolver
- add Requirements derivation utilities (from toy structure JSON)
- add missing-term flags + include-raw export option

### 3.3 USM submodule
Add:
- `src/usm/ops/requirements.py` (or similar) providing a deterministic helper, e.g.:
  - `derive_requirements_v0_1(structure) -> dict`
  - `write_requirements_json(structure, path) -> None`

No mandatory *core* API changes required if USM already provides:
- `atoms` table with `atom_type`
- `bonds` table with `a1`, `a2`
- deterministic IDs

If USM lacks bonds (e.g., CAR-only), requirements derivation must degrade cleanly (emit `bond_types=[]`, `angle_types=[]`).

---

## 4) v0.1.1 work plan (short, self-contained thrusts)

Each thrust must:
- touch a small set of files
- include tests
- include “how to validate” commands
- assume only prior thrusts are completed

### Thrust A — USM: derive Requirements JSON from a USM structure
**Goal:** In USM, implement a deterministic helper that takes a USM structure and writes `requirements.json` (v0.1 schema).

Rationale (why USM, not MolSAIC):
- Requirements derivation is purely *structure/topology* derived (atom types + bonds + implied angles), so it belongs with USM’s deterministic topology utilities.
- It must remain UPM-independent to keep USM reusable as a standalone structures library.
- MolSAIC workspaces should orchestrate by calling USM for `requirements.json`, then UPM for minimal `.frc`.

**Files (USM):**
- `src/usm/ops/requirements.py` (new)
- tests in USM (new file under `src/usm`’s test suite if present; otherwise add MolSAIC-level integration coverage)

**USM helper behavior:**
Inputs:
- `structure.atoms` with `atom_type`
- `structure.bonds` with `a1`, `a2` (optional)

Outputs:
- Requirements JSON (v0.1 schema)
  - `atom_types`: unique atom types in the structure
  - `bond_types`: derived from bond endpoints’ atom types, canonicalized `(t1<=t2)`
  - `angle_types`: derived from bond graph (v0.1.1 requires this)
  - `dihedral_types`: optional; can remain empty in v0.1.1 unless needed immediately

**Angle enumeration algorithm (deterministic):**
1. Build adjacency lists from bonds (ensure undirected, deduped, neighbors sorted).
2. For each central atom `j`:
   - let `N = sorted(neighbors[j])`
   - for all pairs `(i,k)` with indices `p<q`:
     - angle triple is `(type[i], type[j], type[k])` with endpoints canonicalized (`t1<=t3`)
3. Store as unique set, then output as sorted list.

**Validation:**
- Unit test with a small synthetic USM-like structure (3–5 atoms) verifies derived bond + angle tuples and ordering determinism.

Commands (USM tests):
```bash
pytest -q  # in the USM submodule context
```

---

### Thrust B — UPM: extend canonical tables + validators for angles
**Goal:** Add `angles` table as first-class in UPM (CSV/parquet bundles + validation).

**UPM files:**
- `src/upm/core/tables.py`
- `src/upm/core/validate.py`
- `tests/test_tables_validation.py` (update/add)

**Rules:**
- `angles` key: (`t1`, `t2`, `t3`) with endpoints canonicalized so `t1 <= t3`
- deterministic sorting: `t1,t2,t3`

Validation:
```bash
pytest -q  # in UPM submodule context
```

---

### Thrust C — UPM: parse/export `#quadratic_angle` in MSI `.frc` codec
**Goal:** Support `#quadratic_angle` in `.frc` import/export.

**UPM files:**
- `src/upm/codecs/msi_frc.py`
- `tests/test_msi_frc_codec.py` (update)
- `tests/test_frc_import_export_roundtrip.py` (update)

**Import requirements:**
- Detect `#quadratic_angle` section
- Parse rows into angles table
- Preserve unknown sections as before

**Export requirements:**
- When `mode=full`, emit the section if table non-empty
- When `mode=minimal`, emit only required rows (from resolved subset)
- Stable formatting; stable section order (atom_types, bonds, angles, nonbond)

Validation:
```bash
pytest -q
python workspaces/00_quickcheck_import_export/run.py  # if UPM has workspaces
```

---

### Thrust D — UPM: resolver enforces angles when present in Requirements
**Goal:** Extend minimal resolver to include angles.

**UPM files:**
- `src/upm/core/resolve.py`
- `tests/test_resolve_minimal_subset.py` (update)

Rules:
- Default: missing required angles -> hard error
- `--allow-missing` behavior added in next thrust (E)

Validation:
```bash
pytest -q
```

---

### Thrust E — UPM: implement allow-missing/force + missing.json report
**Goal:** Make debugging migration painless while keeping correctness by default.

**UPM changes:**
- CLI `export-frc` accepts:
  - `--allow-missing`
  - `--force`
  - `--missing-report <path>` (default: alongside output `.frc` as `missing.json`)
- Resolver returns `ResolvedFF` + missing lists instead of raising immediately when `allow_missing=True`.

**Policy:**
- default: raise `MissingTermsError` (same as v0.1.0)
- allow-missing:
  - write the `.frc` anyway
  - write `missing.json` with missing atom types, bonds, angles
  - exit code:
    - non-zero unless `--force` is set

Validation:
- Unit tests around missing behavior
- CLI smoke (optional)

---

### Thrust F — UPM: explicit unknown-section export policy (`--include-raw`)
**Goal:** Stop ambiguity: raw preserved sections are either omitted or intentionally included.

**UPM changes:**
- `.frc` exporter gets flag: `include_raw: bool = False`
- If `include_raw=True`, append raw sections in deterministic order:
  - preserve original section order as encountered on import
  - preserve raw lines byte-for-byte

Validation:
- Round-trip tests ensure unknown sections survive when include_raw used.

---

### Thrust G — UPM: standalone Requirements derivation from toy structure JSON
**Goal:** UPM remains standalone; demos don’t require USM.

**UPM files:**
- `src/upm/io/requirements.py` (extend)
- new CLI command `upm derive-req --structure structure.json --out requirements.json`
- tests: `tests/test_requirements_io.py` (extend)

Toy structure schema:
```json
{
  "atoms": [{"aid":0,"atom_type":"c3"}, ...],
  "bonds": [{"a1":0,"a2":1}, ...]
}
```

Output requirements:
- atom_types, bond_types, angle_types derived deterministically

Validation:
```bash
pytest -q
```

---

### Thrust H — MolSAIC: external wrapper hardening for `msi2lmp`
**Goal:** Make external runs reproducible and debuggable.

**Wrapper contract (`src/external/msi2lmp.py`):**
- Inputs:
  - working dir
  - root name or file paths as needed
  - `-f` frc path
- Behavior:
  - creates a deterministic working directory
  - captures stdout/stderr to files
  - records tool version (`msi2lmp --version` if available, else hash of binary path + timestamp)
  - validates expected outputs exist
  - returns a result envelope (paths + hashes + commandline)

Validation:
- Unit test can be “dry-run only” if executable not present:
  - wrapper builds commandline correctly
  - creates working dir and writes manifest even when tool missing (but flags missing tool)

---

### Thrust I — MolSAIC: create the integrated golden workspace
**Goal:** Prove the full architecture and create the regression anchor.

**Workspace path:**
- `workspaces/02_usm_upm_msi2lmp_pipeline/run.py`

Inputs (choose one consistent source):
- `assets/` in MolSAIC root:
  - `ethanol.car`, `ethanol.mdf` (or any small example)
  - `cvff_IFF_metal_oxides_v2.frc`

Outputs:
- `outputs/run_manifest.json` includes:
  - sha256 of inputs
  - UPM package manifest hash/version
  - requirements.json hash
  - minimal.frc hash
  - external tool command line + captured output hashes

Validation:
```bash
python workspaces/02_usm_upm_msi2lmp_pipeline/run.py
```

---

## 5) MolSAIC v0.1.1 “golden workspace” spec (exact behavior)

### 5.1 Workspace steps
1. Ensure `outputs/` exists (create if missing).
2. Import `.frc` into a local package cache:
   - option A: use UPM CLI via subprocess (simple, black-box)
   - option B: call UPM library functions directly (preferred)
3. Load CAR+MDF via USM into a USM object.
4. Generate Requirements JSON via USM requirements helper (Thrust A).
5. Call UPM resolver/export minimal `.frc`:
   - default: hard error if missing
   - optionally support debug flags via workspace config
6. Run external `msi2lmp` wrapper:
   - in a subdir `outputs/msi2lmp_run/`
7. Produce `run_manifest.json` with hashes of everything relevant.

### 5.2 Workspace config (recommended)
`workspaces/02.../config.json` fields:
- `package_name`, `package_version`
- `include_raw_sections` (bool)
- `allow_missing` (bool) and `force` (bool)
- external tool path override

---

## 6) UPM CLI/API updates (v0.1.1)

### 6.1 New/updated commands
- `upm import-frc ...` (same)
- `upm validate ...` (same)
- `upm export-frc ...`
  - add flags:
    - `--include-raw`
    - `--allow-missing`
    - `--force`
    - `--missing-report <path>`
- `upm derive-req --structure structure.json --out requirements.json` (new)

### 6.2 Public API (library)
- `upm.io.requirements.read_requirements_json(path)`
- `upm.io.requirements.requirements_from_structure_json(path)`  (new)
- `upm.core.resolve.resolve_minimal(tables, req, allow_missing=False)` (updated signature OK)

---

## 7) External wrapper “result envelope” (MolSAIC standard)

Every external tool wrapper must return a dict (or dataclass) like:

```json
{
  "tool": "msi2lmp",
  "cmd": ["msi2lmp", "ethanol", "-c", "2", "-f", "ff_minimal.frc"],
  "workdir": "outputs/msi2lmp_run",
  "stdout_path": ".../stdout.txt",
  "stderr_path": ".../stderr.txt",
  "outputs": [{"path":".../lammps.data","sha256":"..."}],
  "tool_version": "..."
}
```

If the tool is missing:
- wrapper must still write a `result.json` in workdir
- must set `"status": "missing_tool"` and not pretend success

---

## 8) CI / testing strategy (MolSAIC-level)

### 8.1 Unit tests in submodules
- UPM: `pytest -q` green
- USM: existing tests remain green

### 8.2 MolSAIC integration tests
Add a lightweight test that:
- imports the example `.frc` (codec sanity)
- loads a tiny CAR/MDF fixture (or stubs USM if needed)
- runs requirements bridge and checks determinism

If `msi2lmp` is not available in CI:
- the golden workspace test should skip the external run, but still verify:
  - requirements generation
  - minimal `.frc` export
  - manifest generation

---

## 9) Versioning

Target versions:
- UPM: v0.1.1 (feature bump)
- USM: unchanged unless required
- MolSAIC: v0.1.1 (integration milestone)

Manifest fields should include:
- `molsaiс_version`
- `usm_version`
- `upm_version`
If submodules aren’t packaged with versions, record git commit SHAs instead.

---

## 10) “Definition of Done” checklist

### UPM
- [ ] `#quadratic_angle` supported in parse/export
- [ ] resolver can enforce angles
- [ ] `derive-req` works for toy structure JSON (angles derived)
- [ ] `export-frc` supports `--include-raw`, `--allow-missing`, `--force`
- [ ] tests green

### MolSAIC
- [ ] USM → Requirements bridge produces deterministic output
- [ ] `external/msi2lmp` wrapper produces deterministic result envelope
- [ ] golden workspace produces required outputs + manifest

---

## 11) Notes on “what next after v0.1.1”

Once v0.1.1 is green:
- v0.2: dihedrals + torsions (`#torsion_1`) end-to-end
- v0.3: equivalence maps + cross terms (IFF reality)
- v0.4+: CHARMM `.prm` via ParmEd as a separate codec module
- MatterStack integration: promote workspace outputs into evidence bundles and campaign artifacts

---

End of DevGuide_v0.1.1
