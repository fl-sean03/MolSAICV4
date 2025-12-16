# MolSAIC V4 — deterministic, code-first workflows for atomistic structures

MolSAIC (Molecular/Materials Structure Assembly, I/O, and Composition) is a **Python codebase for building, transforming, and validating atomistic structures** using a small, stable library surface plus **plain Python “workspaces”** (simple `run.py` scripts) that produce reproducible artifacts.

The V4 philosophy is intentionally simple:

- **Code-first** orchestration (no plugin registries, no DAG engines, no required YAML).
- **Determinism-first** behavior (stable ordering, explicit working directories, validated outputs).
- **Composable building blocks** (structure model + parameter packages + thin wrappers for external tools).

---

## What MolSAIC is (and what it isn’t)

**MolSAIC is:**
- A set of **deterministic primitives** for structure I/O and structure manipulation.
- A set of **thin, testable wrappers** around third-party executables (e.g., Packmol / MSI converters).
- A collection of **workspace examples** that demonstrate end-to-end pipelines with reproducible outputs.

**MolSAIC is not:**
- A workflow engine or registry-driven framework.
- A monolithic “do everything” chemistry stack.
- A replacement for full crystallography suites (those can be layered on top and converted into MolSAIC structures).

---

## Core building blocks (extensibility model)

MolSAIC V4 is organized around a few intentionally small packages:

### 1) USM — Unified Structure Model (structure + deterministic ops)
USM is the structure kernel: a dependency-light Python library that represents **atoms + bonds + periodic cell**, provides deterministic operations, and reads/writes common structure formats.

- In this repo, USM is included as a **git submodule** at `src/usm/`.
- Docs live in the USM submodule: `src/usm/docs/`.

Key entry points (examples):
- CAR/MDF/PDB I/O: `src/usm/io/`
- Deterministic ops (select/transform/replicate/merge/compose/...): `src/usm/ops/`
- Core data model: `src/usm/core/model.py`

### 2) External adapters — deterministic envelopes around executables
MolSAIC provides wrappers for third-party tools with a consistent “result envelope”:
- deterministic CWD
- PATH augmentation for linker stability
- output existence + non-empty validation
- best-effort tool version capture

See:
- Contract: `docs/ADAPTER_CONTRACT.md`
- Helpers: `src/external/adapter.py`
- Wrappers: `src/external/packmol.py`, `src/external/msi2namd.py`, `src/external/msi2lmp.py`

### 3) Workspace pipelines — simple scripts you can version and customize
Workspaces are plain directories under `workspaces/` containing:
- `run.py` (the orchestrator)
- `config.json` (small, explicit config)
- `outputs/` (generated artifacts; typically contains `summary.json`)

This model keeps pipelines **transparent** and **easy to fork** without framework lock-in.

Start here (canonical):
- Quickstart (end-to-end example): `docs/QUICKSTART.md`
- Workspace contract + determinism conventions: `docs/WORKFLOWS.md`
- External wrapper contract: `docs/ADAPTER_CONTRACT.md`
- Acceptance criteria (AS2 hydration): `docs/ACCEPTANCE.md`
- Alumina “ions in water” workflows: `docs/ions-in-water-workflows.md`
- Manifest schema: `docs/manifest.v1.schema.json`

Workspaces (entry points)
- Alumina: `workspaces/alumina/`
  - AS2 hydration: `workspaces/alumina/alumina_AS2_hydration_v1/`
  - AS2/AS5/AS10/AS12 ions pipelines: `workspaces/alumina/*_ions_v1/`
  - Case studies: `workspaces/alumina/cases/`
- MXenes: `workspaces/mxenes/`
  - Analysis: `workspaces/mxenes/analysis/`
  - Fluorination and hydrated systems: `workspaces/mxenes/fluorinated/`, `workspaces/mxenes/hydrated/`
- NIST: `workspaces/NIST/`
  - CIF import demo: `workspaces/NIST/nist_calf20_cif_import_v1/`

### 4) UPM — Unified Parameter Model (versioned force-field packages)
UPM is a **standalone** Python library + CLI for managing, validating, and exporting **force-field parameter packages** (starting with Materials Studio / BIOSYM-style `*.frc` used by `msi2lmp`).

- In this repo, UPM is included as a **git submodule** at `src/upm/` with its own `pyproject.toml`.
- UPM is intentionally **installed separately** from the MolSAIC root package.

See: `src/upm/README.md`

---

## Getting started

### Clone (with submodules)
If you’re cloning fresh, initialize submodules (USM + UPM):

```bash
git clone git@github.com:fl-sean03/MolSAICV4.git
cd MolSAICV4
git submodule update --init --recursive
```

### Install MolSAIC (editable)
From repository root:

```bash
python -m pip install -e .
```

### Run a workspace (example: alumina AS2 hydration)
```bash
cd workspaces/alumina/alumina_AS2_hydration_v1
python run.py --config ./config.json
```

- End-to-end guide: `docs/QUICKSTART.md`
- Deterministic conventions and step mapping: `docs/WORKFLOWS.md`

### Install UPM (optional; separate package)
UPM has its own packaging metadata and Python requirement (see `src/upm/pyproject.toml`).

From repository root:

```bash
python -m pip install -e ./src/upm
```

---

## Reproducibility and determinism

MolSAIC V4 emphasizes determinism for both library operations and workflows:

- Stable table ordering and renumbering in structure operations.
- Seed capture where applicable (e.g., Packmol seed injection).
- Deterministic working directories for external tools (no implicit global state).
- Validation that required outputs are created and non-empty.
- Optional `outputs/summary.json` manifests for machine-consumable run summaries.

Key docs:
- External adapter contract: `docs/ADAPTER_CONTRACT.md`
- Manifest schema: `docs/manifest.v1.schema.json`

---

## Repository layout (high level)

- `src/`
  - `src/molsaic/` — small shared utilities (workspace helpers, etc.)
  - `src/usm/` — USM submodule (structure model + I/O + ops)
  - `src/external/` — external tool adapter contract + wrappers
  - `src/pm2mdfcar/` — composition utilities used by hydration/ions workspaces
  - `src/upm/` — UPM standalone package (separate install)
- `docs/` — MolSAIC V4 documentation
- `workspaces/` — runnable pipelines and analysis scripts
- `tests/` — unit + integration tests

---

## Contributing / extending MolSAIC

The intended extension points are straightforward:

1) **Add a new workspace**
- Copy the workspace template and customize inputs/steps.
- Write artifacts under `outputs/` and (optionally) a manifest `summary.json`.
- Document it in `docs/` if it becomes a canonical workflow.

2) **Add a new external adapter**
- Follow the envelope contract in `docs/ADAPTER_CONTRACT.md`.
- Implement `run(...)->dict` returning a deterministic result (argv/cwd/outputs/stderr/stdout/duration/version).
- Add unit tests that validate schema keys and output validation behavior.

3) **Extend structure capabilities**
- Extend USM (in the USM repo/submodule) for new I/O formats or deterministic operations.
- Keep project-specific policies in workspaces, not in USM core.

---

## License / status

This repository is under active development. The V4 docs under `docs/` reflect the current code-first architecture and are intended to be the canonical reference for MolSAIC V4.
