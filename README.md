# MolSAIC V4 — code‑first library and minimal, deterministic workflows

MolSAIC V4 focuses on a simple, stable Python library and small, direct scripts you can run and version as you like. No plugin registries or YAML DAGs — just import functions, call thin wrappers for external tools when needed, and write artifacts in a predictable layout.

Highlights
- Minimal ceremony: use a tiny run.py or a notebook; configs are optional.
- Stable import surface: usm.*, external.*, pm2mdfcar.*.
- Deterministic behavior: stable table ordering, seeded tools, validated outputs.

Install (editable)
- From repository root:
  ```
  python -m pip install -e .
  ```
- Python 3.9+ (see [pyproject.toml](pyproject.toml))

Stable modules (entry points)
- USM IO and core:
  - [src/usm/io/car.py](src/usm/io/car.py)
  - [src/usm/io/mdf.py](src/usm/io/mdf.py)
  - [src/usm/io/pdb.py](src/usm/io/pdb.py)
  - [src/usm/core/model.py](src/usm/core/model.py)
- USM operations (selection, transforms, merge/compose, renumber, cell helpers):
  - [src/usm/ops/](src/usm/ops)
- Hydration composition:
  - [src/pm2mdfcar/__init__.py](src/pm2mdfcar/__init__.py)
- External tool adapters and wrappers:
  - [src/external/adapter.py](src/external/adapter.py)
  - [src/external/packmol.py](src/external/packmol.py)
  - [src/external/msi2namd.py](src/external/msi2namd.py)
  - [src/external/msi2lmp.py](src/external/msi2lmp.py)

Quickstart (library-first)
1) Read/edit/write a CAR file (no config required)
- Example sketch (Python):
  - Load a CAR into a USM instance (DataFrame tables)
  - Edit usm.atoms (e.g., select/filter/transform with pandas/numpy/usm.ops)
  - Save back to CAR (headers preserved when available) and/or MDF/PDB
- Files: [src/usm/io/car.py](src/usm/io/car.py), [src/usm/io/mdf.py](src/usm/io/mdf.py), [src/usm/io/pdb.py](src/usm/io/pdb.py), [src/usm/ops/](src/usm/ops)

2) Use external wrappers when needed
- Thin, deterministic wrappers around third‑party executables:
  - Packmol → hydrated PDB
  - msi2namd → PDB/PSF
  - msi2lmp → LAMMPS .data
- Files: [src/external/packmol.py](src/external/packmol.py), [src/external/msi2namd.py](src/external/msi2namd.py), [src/external/msi2lmp.py](src/external/msi2lmp.py), [src/external/adapter.py](src/external/adapter.py)
- Notes:
  - PATH is augmented with the executable’s directory for linker stability.
  - Wrappers enforce timeouts and validate that outputs are created and non‑empty.
  - A best‑effort tool_version is captured to aid reproducibility.

3) Compose hydrated systems (optional)
- Convert templates to PDB/PSF (msi2namd), pack waters/ions (Packmol), compose CAR/MDF (pm2mdfcar), then emit a LAMMPS .data (msi2lmp).
- Files: [src/pm2mdfcar/__init__.py](src/pm2mdfcar/__init__.py), [src/external/packmol.py](src/external/packmol.py), [src/external/msi2namd.py](src/external/msi2namd.py), [src/external/msi2lmp.py](src/external/msi2lmp.py)

USM design and data model (deeper docs)
- Overview and schema: [src/usm/docs/DESIGN.md](src/usm/docs/DESIGN.md), [src/usm/docs/DATA_MODEL.md](src/usm/docs/DATA_MODEL.md)
- Workflows and examples: [src/usm/docs/WORKFLOWS.md](src/usm/docs/WORKFLOWS.md), [src/usm/docs/EXAMPLES.md](src/usm/docs/EXAMPLES.md)
- Limits and performance: [src/usm/docs/LIMITS.md](src/usm/docs/LIMITS.md), [src/usm/docs/PERFORMANCE.md](src/usm/docs/PERFORMANCE.md)

Ions‑in‑water workflows (Packmol)
- Approach: ions are placed in the aqueous region (not embedded in slabs), matching per‑surface legacy totals while enabling mobility.
- Guide: [docs/ions-in-water-workflows.md](docs/ions-in-water-workflows.md)
- When per‑surface workspaces are present, they are typically:
  - workspaces/alumina/alumina_AS2_ions_v1, workspaces/alumina/alumina_AS5_ions_v1, workspaces/alumina/alumina_AS10_ions_v1, workspaces/alumina/alumina_AS12_ions_v1
- Expected outputs per run (under workspace outputs/):
  - hydrated PDB (Packmol), converted CAR/MDF (pm2mdfcar), LAMMPS .data (msi2lmp), summary.json, ion z‑histograms
  - Manifest schema (for validation when used): [docs/manifest.v1.schema.json](docs/manifest.v1.schema.json)

Determinism, manifests, and tests
- Determinism
  - Stable table ordering and renumbering
  - Seeded packing (Packmol) when a seed is provided
  - Consistent working directories and PATH behavior in wrappers
- Manifest schema
  - Optional summary.json for runs that choose to emit a manifest
  - Schema file: [docs/manifest.v1.schema.json](docs/manifest.v1.schema.json)
- Tests
  - Integration tests (hydration/ions variants):
    - [tests/integration/test_hydration_workspaces.py](tests/integration/test_hydration_workspaces.py)
    - [tests/integration/test_ions_workspaces.py](tests/integration/test_ions_workspaces.py)

Repository layout (current)
- Library: [src/](src)
  - USM core/IO/ops: [src/usm/](src/usm)
  - External wrappers: [src/external/](src/external)
  - Hydration compose op: [src/pm2mdfcar/](src/pm2mdfcar)
- Docs: [docs/](docs)
- Utility scripts: [scripts/](scripts)
- Tests: [tests/](tests)

Conventions
- No required config files — parse your own if desired.
- No required outputs/ or baselines/ structure — write artifacts where it makes sense for your job (workspaces commonly use an outputs/ subfolder).
- Keep imports within the stable surface usm.*, external.*, pm2mdfcar.* (avoid ad‑hoc sys.path edits).

Troubleshooting
- ModuleNotFoundError: usm/external/pm2mdfcar
  - Ensure editable install from repo root:
    ```
    python -m pip install -e .
    ```
- External executables not found (packmol, msi2namd, msi2lmp)
  - Provide absolute paths in your script/config, or make sure they are on PATH.
  - Wrapper behavior and helpers: [src/external/adapter.py](src/external/adapter.py)
- Parquet not installed (optional)
  - USM bundle I/O prefers Parquet but falls back to CSV automatically; install pyarrow for better performance.

Notes
- This README reflects MolSAIC V4. Older references and paths have been removed in favor of the simplified, code‑first model described here.
