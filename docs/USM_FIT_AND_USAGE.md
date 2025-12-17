# USM architecture review — how it fits + how workspaces use it

This document describes the **USM (Unified Structure Model)** library in this repo: its core data model and invariants, I/O boundaries (CAR/MDF/PDB/CIF), key operations, and how repository workspaces (especially MXene hydration/pH pipelines) interact with USM vs external tools.

---

## 1) Big picture: where USM sits in this repo

USM is a **dependency-light, deterministic in-memory structure model** based on Pandas tables. It is designed to:

- provide a consistent schema for “atomic structures” (atoms, optional bonds/connectivity, and periodic cell metadata),
- perform deterministic structure edits and composition,
- read/write **Materials Studio** file formats (CAR/MDF) with **high-fidelity preservation** (headers/footers, connection tokens) where possible,
- bridge to other formats (e.g., PDB, CIF) where topology/metadata fidelity is lower by design.

### Architecture diagram (text)

```mermaid
flowchart LR
  subgraph Inputs
    CAR[CAR: coords + minimal labels]
    MDF[MDF: topology + connections]
    CIF[CIF: lattice + fractional sites]
    PDB[PDB: coords + residues]
  end

  subgraph USM["USM core (in-memory)"]
    ATOMS[atoms table]
    BONDS[bonds table (optional)]
    CELL[cell/PBC dict]
    META[provenance + preserved_text]
  end

  subgraph Ops
    COMPOSE[compose]
    SELECT[selection]
    XFORM[transforms]
    MERGE[merge/renumber]
    REPL[replicate]
    GRAFT[graft]
  end

  subgraph Outputs
    CARO[CAR]
    MDFO[MDF]
    PDBO[PDB]
    CIFO[CIF]
  end

  CAR -->|load| USM
  MDF -->|load| USM
  CIF -->|load| USM
  PDB -. minimal writer only .-> USM

  USM --> COMPOSE --> USM
  USM --> SELECT --> USM
  USM --> XFORM --> USM
  USM --> MERGE --> USM
  USM --> REPL --> USM
  USM --> GRAFT --> USM

  USM -->|save| CARO
  USM -->|save| MDFO
  USM -->|save| PDBO
  USM -->|save| CIFO
```

### Two repo usage styles

1. **USM-first pipelines**: load CAR/MDF into USM, perform deterministic edits, then export.
   - Example: the golden pipeline workspace [`workspaces/02_usm_upm_msi2lmp_pipeline/run.py`](workspaces/02_usm_upm_msi2lmp_pipeline/run.py:1) uses USM to load inputs (and derive downstream artifacts) before calling external wrappers.

2. **External-tool-first pipelines**: rely on external binaries for conversion/packing and only do targeted “boundary fixes” in Python.
   - Example: the MXene pH hydration workspace [`workspaces/mxenes/pH_systems/pH_all_hydrated_bilayer_v1/run.py`](workspaces/mxenes/pH_systems/pH_all_hydrated_bilayer_v1/run.py:1) uses external wrappers and `pm2mdfcar`, with a custom MDF/CAR identifier “de-dup” preflight.

---

## 2) USM core data model and invariants

USM is defined as a dataclass wrapping (primarily) Pandas DataFrames:

- [`USM`](src/usm/core/model.py:95)
- schema/type normalization and deterministic ID allocation: [`USM.__post_init__()`](src/usm/core/model.py:103)
- basic validation: [`USM.validate_basic()`](src/usm/core/model.py:140)

### 2.1 Tables and fields

#### Atoms table (required)

Canonical schema/dtypes are defined in [`ATOMS_DTYPES`](src/usm/core/model.py:9). Key required columns are listed in [`REQUIRED_ATOM_COLUMNS`](src/usm/core/model.py:58).

Core identity and geometry fields:

- `aid`: dense, deterministic row id (int32)
- `name`: atom name (string)
- `element`: element symbol (string)
- `atom_type`: force-field atom type (string) — important for downstream tools
- `charge`: partial charge (float32)
- `x`, `y`, `z`: Cartesian coordinates (float64, Å)
- `mol_label`, `mol_index`: Materials Studio “molecule”/record grouping (string/int32)
- `mol_block_name`: MDF `@molecule` name when available (string)

MDF preservation fields (nullable) are also part of the atoms schema, including:
- `formal_charge` (string token, can be `"1+"`)
- `connections_raw` (string): original MDF connection token text

See the schema definition block in [`src/usm/docs/DESIGN.md`](src/usm/docs/DESIGN.md:14).

#### Bonds table (optional)

Canonical schema/dtypes are defined in [`BONDS_DTYPES`](src/usm/core/model.py:38).

Important columns:
- `a1`, `a2`: atom endpoints (int32), with an invariant `a1 < a2` enforced in [`USM.__post_init__()`](src/usm/core/model.py:113)
- `order`: bond order (float32); MDF can supply fractional orders (e.g., 1.5 for aromatic)
- `source` / `order_raw`: provenance of how the bond was inferred/represented

#### Molecules table (optional)

Canonical schema/dtypes are defined in [`MOLECULES_DTYPES`](src/usm/core/model.py:50). It is not required for most workflows in this repo; several ops work with molecule identity derived from atom columns.

#### Cell and PBC metadata (dict)

USM stores periodic cell metadata in `USM.cell` with keys:
- `pbc` (bool)
- `a`, `b`, `c` (float)
- `alpha`, `beta`, `gamma` (float, degrees)
- `spacegroup` (string)

Default cell is created in [`USM.cell`](src/usm/core/model.py:99).

#### Provenance and preserved text (dicts)

USM separates:
- `USM.provenance`: structured metadata about where the structure came from (format, path, parsing notes)
- `USM.preserved_text`: raw header/footer lines and other text blocks for lossless-ish round-trips

Design intent is documented in [`src/usm/docs/DESIGN.md`](src/usm/docs/DESIGN.md:32).

### 2.2 “Valid structure” invariants (what USM enforces)

USM is intentionally permissive (to support partially specified formats like MDF-only), but enforces a few invariants:

1. **Atoms table must exist**  
   Enforced in [`USM.__post_init__()`](src/usm/core/model.py:103).

2. **Required atom columns exist**  
   Enforced in [`USM.validate_basic()`](src/usm/core/model.py:140).

3. **Deterministic `aid` allocation**  
   Regardless of input, `aid` is reassigned to `0..N-1` in [`USM.__post_init__()`](src/usm/core/model.py:103). Operations that change rows are expected to renumber deterministically (e.g., compose/graft/replicate do this explicitly).

4. **Coordinates may be NaN, but not infinite**  
   MDF files do not contain coordinates; USM permits NaN but rejects infinities in [`USM.validate_basic()`](src/usm/core/model.py:140).

5. **Bonds are normalized**  
   If bonds exist, endpoints are normalized to `a1 < a2` and assigned deterministic `bid` order in [`USM.__post_init__()`](src/usm/core/model.py:113).

These invariants matter because many downstream tools (notably Materials Studio-style connectivity and external wrappers) effectively rely on the identity tuple:
- `(mol_label, mol_index, name)`  
This is also the default composition join key in [`compose_on_keys()`](src/usm/ops/compose.py:13).

---

## 3) I/O boundaries: formats, preservation, and limitations

USM implements direct readers/writers (no subprocess) for CAR/MDF and minimal support for PDB and CIF.

The convenience import surface is in [`src/usm/io/__init__.py`](src/usm/io/__init__.py:1).

### 3.1 CAR (Materials Studio “archive”)

- Reader: [`load_car()`](src/usm/io/car.py:128)
- Writer: [`save_car()`](src/usm/io/car.py:187)

**What CAR provides (in USM terms):**
- `atoms`: coordinates (`x,y,z`), identity (`mol_label`, `mol_index`, `name`), plus `atom_type`, `element`, `charge`
- `cell`: parses `PBC=ON/OFF` and optionally a “PBC a b c α β γ” line (best-effort)
- `preserved_text`: header/footer lines, if present

**What CAR does not provide:**
- Topology/connectivity (no bonds) — bonds remain `None` after CAR load.

**Preservation behavior:**
- If preserving headers, writer emits stored header/footer byte-for-byte; otherwise synthesizes canonical header/footer in [`save_car()`](src/usm/io/car.py:187).

**Notable limitation:**
- CAR is not a topology carrier; for any workflow that needs connectivity preserved, CAR must be paired with MDF (see “compose” below).

### 3.2 MDF (Materials Studio topology)

- Reader: [`load_mdf()`](src/usm/io/mdf.py:243)
- Writer: [`save_mdf()`](src/usm/io/mdf.py:363)

**What MDF provides:**
- Atom identity + force-field typing: `mol_label`, `mol_index`, `name`, `element`, `atom_type`
- Charge + MDF metadata columns
- Topology in “connections” column:
  - stored losslessly in `connections_raw`
  - optionally inferred into a normalized `bonds` table via `_build_bonds_from_connections()` in [`src/usm/io/mdf.py`](src/usm/io/mdf.py:148)

**What MDF does not provide:**
- Cartesian coordinates: USM leaves `x,y,z` as NaN on load (explicitly noted in [`load_mdf()`](src/usm/io/mdf.py:243)).

**Preservation behavior:**
- Header/footer blocks are preserved when present (including `@column` and `@molecule` ordering) and stored into `preserved_text` in [`load_mdf()`](src/usm/io/mdf.py:243).
- `connections_raw` is retained per atom for lossless re-emission when desired.
- On save, MDF connections can be written in two modes:
  - **lossless token mode** (default): prefer `connections_raw` in [`_compose_connections_for_atom()`](src/usm/io/mdf.py:323)
  - **normalized mode**: regenerate connections from `usm.bonds` with `write_normalized_connections=True` in [`save_mdf()`](src/usm/io/mdf.py:363)

**Notable limitation (identity uniqueness):**
- Many workflows assume `{mol_label}_{mol_index}:{name}` is unique per atom. Ambiguity here breaks connectivity resolution (and can break external tools).
- This repo’s MXene bilayer hydration pipeline includes a regex-based de-dup preflight specifically to restore that uniqueness: [`_preflight_fix_nonbonded_terminations_mdf()`](workspaces/mxenes/pH_systems/pH_all_hydrated_bilayer_v1/run.py:99).

### 3.3 PDB (minimal writer)

- Writer: [`save_pdb()`](src/usm/io/pdb.py:69)

**What PDB export includes:**
- `ATOM` records with:
  - `serial = aid + 1`
  - `resName` derived from `mol_block_name` (or fallback `"RES"`)
  - `resSeq` derived from `mol_index`
- Optional `CRYST1` if `cell.pbc=True` and lattice params are finite in [`_compose_cryst1()`](src/usm/io/pdb.py:50)
- Optional `CONECT` derived from `usm.bonds` if `include_conect=True` in [`save_pdb()`](src/usm/io/pdb.py:69)

**What PDB export does not preserve well:**
- Materials Studio-specific identity (`mol_label`) and MDF topology tokens
- Full force-field typing fidelity (PDB has limited typing semantics)

### 3.4 CIF (minimal reader/writer)

- Reader: [`load_cif()`](src/usm/io/cif.py:223)
- Writer: [`save_cif()`](src/usm/io/cif.py:372)

**What CIF import supports (v0.1):**
- lattice parameters and fractional coordinates from an `atom_site` loop (no symmetry expansion)
- fractional → Cartesian conversion via lattice helpers (USM stores cartesian `x,y,z`)
- `cell.pbc=True` with a,b,c,α,β,γ populated

**Important limitations:**
- Symmetry expansion is intentionally not implemented; enabling it errors in [`load_cif()`](src/usm/io/cif.py:223).
- Bonds/connectivity are **not inferred from CIF**.
- Writer emits only a minimal `atom_site` loop and cannot encode MDF-style connectivity (explicitly noted in [`save_cif()`](src/usm/io/cif.py:372)).

---

## 4) Operations: main categories and where they live

USM operations are designed to be deterministic and schema-stable. The design doc enumerates the initial operation surface in [`src/usm/docs/DESIGN.md`](src/usm/docs/DESIGN.md:69), and the workflows doc provides practical playbooks in [`src/usm/docs/WORKFLOWS.md`](src/usm/docs/WORKFLOWS.md:1).

Below are the key categories relevant to this repo.

### 4.1 Compose (CAR + MDF join)

Purpose: combine coordinate-rich CAR with topology-rich MDF into a single USM structure.

- Operation: [`compose_on_keys()`](src/usm/ops/compose.py:13)

Key semantics:
- join keys default to `["mol_label","mol_index","name"]` via [`KEYS_DEFAULT`](src/usm/ops/compose.py:10)
- fills missing columns in “primary” from “secondary”
- prefers MDF bonds if available
- remaps bond endpoints to the new `aid` ordering after merge

This pattern is explicitly recommended in [`src/usm/docs/WORKFLOWS.md`](src/usm/docs/WORKFLOWS.md:6).

### 4.2 Replicate (supercell tiling)

Purpose: tile a periodic structure along lattice vectors.

- Operation: [`replicate_supercell()`](src/usm/ops/replicate.py:35)

Key semantics:
- requires `cell.pbc=True` and finite lattice parameters
- performs replication in fractional space (general triclinic)
- replicates bonds within each image and remaps endpoints deterministically
- scales `cell.a/b/c` by replication counts, preserving angles

### 4.3 Graft (host/guest placement and merge)

Purpose: place “guest” molecules onto “host” sites with orientation scanning and collision checks.

- Orchestrator: [`graft_guests()`](src/usm/ops/graft.py:171)
- Guest preparation: [`prepare_guest()`](src/usm/ops/graft.py:87)
- Configuration: [`PlacementConfig`](src/usm/ops/graft.py:47)

High-level mechanics:
- host sites define anchor positions and which host atoms to remove (`site.removal_aids`)
- guest is oriented by aligning an anchor axis to a surface normal, then scanning torsion angles
- collision screening uses minimum distances between host/guest atom sets
- accepted guests are merged back into host; `mol_index` is made unique; `aid` is renumbered deterministically

This operational playbook is captured in [`src/usm/docs/WORKFLOWS.md`](src/usm/docs/WORKFLOWS.md:20).

### 4.4 Merge/renumber/selection/transforms (supporting ops)

These categories are referenced by the design and graft implementation as key supporting operations:

- merge and renumber: imported and used in [`src/usm/ops/graft.py`](src/usm/ops/graft.py:24)
- selection by mask: imported and used in [`src/usm/ops/graft.py`](src/usm/ops/graft.py:27)

The intent and grouping are documented in [`src/usm/docs/DESIGN.md`](src/usm/docs/DESIGN.md:69) and [`src/usm/docs/WORKFLOWS.md`](src/usm/docs/WORKFLOWS.md:73).

---

## 5) How workspaces use USM in this repo

This section is intentionally **descriptive only** (current behavior), per project constraints.

### 5.1 Golden workspace: USM → UPM → external wrapper (msi2lmp)

Entry point: [`workspaces/02_usm_upm_msi2lmp_pipeline/run.py`](workspaces/02_usm_upm_msi2lmp_pipeline/run.py:1)  
Determinism test: [`tests/integration/test_golden_usm_upm_msi2lmp_pipeline.py`](tests/integration/test_golden_usm_upm_msi2lmp_pipeline.py:1)

**Usage pattern:**
1. Stage inputs into a deterministic `outputs_dir` subtree.
2. Load structure inputs using USM I/O:
   - `CAR` sanity read: [`workspaces/02_usm_upm_msi2lmp_pipeline/run.py`](workspaces/02_usm_upm_msi2lmp_pipeline/run.py:141)
   - `MDF` topology read: [`workspaces/02_usm_upm_msi2lmp_pipeline/run.py`](workspaces/02_usm_upm_msi2lmp_pipeline/run.py:141)
3. Derive requirements (from USM topology) and generate a minimal forcefield package (UPM).
4. Call the external wrapper for conversion:
   - wrapper is always invoked, but the integration test forces a missing executable and asserts the run is still deterministic.

**Key observation:**
- In this pipeline, USM is used as the **trusted topology carrier** (MDF is authoritative) and as a deterministic input to later packaging and wrapper steps.

### 5.2 MXenes hydration/pH pipelines: external-tool-first with targeted boundary fixes

Main example workspace:
- [`workspaces/mxenes/pH_systems/pH_all_hydrated_bilayer_v1/run.py`](workspaces/mxenes/pH_systems/pH_all_hydrated_bilayer_v1/run.py:1)
- Overview/readme: [`workspaces/mxenes/pH_systems/pH_all_hydrated_bilayer_v1/README.md`](workspaces/mxenes/pH_systems/pH_all_hydrated_bilayer_v1/README.md:1)

**Pipeline skeleton (per [`run_one()`](workspaces/mxenes/pH_systems/pH_all_hydrated_bilayer_v1/run.py:490)):**
1. Convert CAR/MDF → PDB/PSF using external wrapper calls (msi2namd).
2. Use packmol to generate a combined PDB (bilayer + water regions).
3. Use `pm2mdfcar` to build a composed CAR/MDF from the packed PDB plus templates.
4. Convert CAR/MDF → LAMMPS `.data` using `msi2lmp`.

**Where USM appears (currently):**
- USM is *not* directly invoked in this workspace. Structure composition/editing is handled by `pm2mdfcar` + external tools.

**USM-adjacent constraint surfaced in this pipeline (identity uniqueness):**
- The workspace includes a preflight “identifier de-dup” that rewrites MDF (and CAR in sync) to eliminate duplicate `{mol_label}_{mol_index}:{name}` identifiers across bilayer layers:
  - [`_preflight_fix_nonbonded_terminations_mdf()`](workspaces/mxenes/pH_systems/pH_all_hydrated_bilayer_v1/run.py:99)
- This constraint matches USM’s default compose key policy (identity triple) in [`compose_on_keys()`](src/usm/ops/compose.py:13).

**Related integration coverage:**
- Hydration workspace integration tests validate existing artifacts and optionally run workspaces when executables exist in [`tests/integration/test_hydration_workspaces.py`](tests/integration/test_hydration_workspaces.py:1). These tests are manifest- and artifact-focused; they do not directly test USM.

---

## 6) Typical USM call sequences used or implied in this repo

### 6.1 CAR+MDF composition (host or guest)

The canonical pattern (also recommended in [`src/usm/docs/WORKFLOWS.md`](src/usm/docs/WORKFLOWS.md:20)):

- Load coordinates: [`load_car()`](src/usm/io/car.py:128)
- Load topology: [`load_mdf()`](src/usm/io/mdf.py:243)
- Compose: [`compose_on_keys()`](src/usm/ops/compose.py:13)

### 6.2 Grafting workflow (USM-first edits)

The operational sequence described in [`src/usm/docs/WORKFLOWS.md`](src/usm/docs/WORKFLOWS.md:20) and implemented in [`graft_guests()`](src/usm/ops/graft.py:171):

- compose host
- detect sites (site model is referenced as [`Site`](src/usm/ops/graft.py:39))
- compose guest, optionally drop atoms via [`prepare_guest()`](src/usm/ops/graft.py:87)
- place and merge via [`graft_guests()`](src/usm/ops/graft.py:171)
- export CAR/MDF (often with normalized MDF connections via [`save_mdf()`](src/usm/io/mdf.py:363))

### 6.3 Deterministic “golden” pipeline pattern

The golden workspace is a compact example of:
- deterministic staging,
- USM-based topology read,
- deterministic manifests and wrapper envelopes.

See [`workspaces/02_usm_upm_msi2lmp_pipeline/run.py`](workspaces/02_usm_upm_msi2lmp_pipeline/run.py:1) and determinism checks in [`tests/integration/test_golden_usm_upm_msi2lmp_pipeline.py`](tests/integration/test_golden_usm_upm_msi2lmp_pipeline.py:1).

---

## 7) Limitations and gotchas (current behavior)

1. **Topology vs coordinates are split across MDF vs CAR**
   - MDF has topology; CAR has coordinates.
   - If you load only CAR, you will lose bonds/connectivity (by design).
   - Compose is the intended bridge: [`compose_on_keys()`](src/usm/ops/compose.py:13).

2. **Identity tuple uniqueness matters**
   - The default “atom key” used across the repo is `(mol_label, mol_index, name)`.
   - Ambiguity in these keys breaks deterministic joins and makes connectivity token resolution unreliable.
   - The MXene bilayer hydration workspace contains an explicit guardrail to restore uniqueness: [`_preflight_fix_nonbonded_terminations_mdf()`](workspaces/mxenes/pH_systems/pH_all_hydrated_bilayer_v1/run.py:99).

3. **MDF connections can be lossless or normalized**
   - Lossless mode preserves `connections_raw` (best for round-trip identity).
   - Normalized mode regenerates connections from `bonds` (best after topology edits).
   - See modes in [`save_mdf()`](src/usm/io/mdf.py:363).

4. **PDB/CIF are not topology-first formats in USM**
   - PDB writer is minimal and `CONECT` is optional in [`save_pdb()`](src/usm/io/pdb.py:69).
   - CIF import/export is minimal and does not attempt symmetry expansion nor bond inference in [`load_cif()`](src/usm/io/cif.py:223) and [`save_cif()`](src/usm/io/cif.py:372).

---

## 8) Code entry points (quick links)

### Core model
- [`src/usm/core/model.py`](src/usm/core/model.py:1)
  - [`USM`](src/usm/core/model.py:95)
  - [`USM.__post_init__()`](src/usm/core/model.py:103)
  - [`USM.validate_basic()`](src/usm/core/model.py:140)

### I/O
- CAR: [`load_car()`](src/usm/io/car.py:128), [`save_car()`](src/usm/io/car.py:187)
- MDF: [`load_mdf()`](src/usm/io/mdf.py:243), [`save_mdf()`](src/usm/io/mdf.py:363)
- PDB: [`save_pdb()`](src/usm/io/pdb.py:69)
- CIF: [`load_cif()`](src/usm/io/cif.py:223), [`save_cif()`](src/usm/io/cif.py:372)
- Aggregate imports: [`src/usm/io/__init__.py`](src/usm/io/__init__.py:1)

### Ops
- Compose: [`compose_on_keys()`](src/usm/ops/compose.py:13)
- Replicate: [`replicate_supercell()`](src/usm/ops/replicate.py:35)
- Graft: [`graft_guests()`](src/usm/ops/graft.py:171), [`prepare_guest()`](src/usm/ops/graft.py:87)

### Docs (upstream intent)
- Design: [`src/usm/docs/DESIGN.md`](src/usm/docs/DESIGN.md:1)
- Workflow playbooks: [`src/usm/docs/WORKFLOWS.md`](src/usm/docs/WORKFLOWS.md:1)

### Workspace examples
- Golden pipeline: [`workspaces/02_usm_upm_msi2lmp_pipeline/run.py`](workspaces/02_usm_upm_msi2lmp_pipeline/run.py:1)
- Golden determinism test: [`tests/integration/test_golden_usm_upm_msi2lmp_pipeline.py`](tests/integration/test_golden_usm_upm_msi2lmp_pipeline.py:1)
- MXene pH hydration: [`workspaces/mxenes/pH_systems/pH_all_hydrated_bilayer_v1/run.py`](workspaces/mxenes/pH_systems/pH_all_hydrated_bilayer_v1/run.py:1)