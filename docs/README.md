# MolSAIC V4 Documentation

MolSAIC V4 is a code-first Python repository for building and transforming atomistic structures with deterministic, reproducible workflows.

This repo is organized around:
- **Library modules** under `src/` (stable imports: `usm.*`, `external.*`, `pm2mdfcar.*`)
- **Workspaces** under `workspaces/` (plain `run.py` scripts + small configs, producing artifacts under `outputs/`)
- **Docs** under `docs/` (this folder)

## Start here

- Quickstart (end-to-end example): [QUICKSTART.md](QUICKSTART.md)
- Workspace contract + determinism conventions: [WORKFLOWS.md](WORKFLOWS.md)
- External wrapper contract (packmol/msi2namd/msi2lmp envelopes): [ADAPTER_CONTRACT.md](ADAPTER_CONTRACT.md)
- Acceptance criteria (AS2 hydration): [ACCEPTANCE.md](ACCEPTANCE.md)
- Alumina “ions in water” workflows: [ions-in-water-workflows.md](ions-in-water-workflows.md)

## Workspaces (entry points)

Workspaces are grouped by domain:

- Alumina: `workspaces/alumina/`
  - AS2 hydration: `workspaces/alumina/alumina_AS2_hydration_v1/`
  - AS2/AS5/AS10/AS12 ions pipelines: `workspaces/alumina/*_ions_v1/`
  - Case studies: `workspaces/alumina/cases/`
- MXenes: `workspaces/mxenes/`
  - Analysis: `workspaces/mxenes/analysis/`
  - Fluorination and hydrated systems: `workspaces/mxenes/fluorinated/`, `workspaces/mxenes/hydrated/`
- NIST: `workspaces/NIST/`
  - CIF import demo: `workspaces/NIST/nist_calf20_cif_import_v1/`

General convention:
- Run from the workspace directory (recommended):
  - `python run.py --config ./config.json`
- Artifacts are typically written under `outputs/` within the workspace directory.

## Manifests

Some workspaces emit a machine-readable `outputs/summary.json`. The schema used by multiple integration tests is:

- Manifest schema: [manifest.v1.schema.json](manifest.v1.schema.json)

## Submodules (USM + UPM)

This repo includes two submodules:
- **USM** at `src/usm/` (Unified Structure Model: structures + deterministic ops)
- **UPM** at `src/upm/` (Unified Parameter Model: parameter packages + CLI)

If you clone fresh, initialize submodules:
- `git submodule update --init --recursive`

UPM is a standalone package and is installed separately from the MolSAIC root:
- `python -m pip install -e ./src/upm`

## USM notes (submodule)

USM is the core “Unified Structure Model” library (data model + IO + deterministic ops). In this repo it is included as a git submodule at `src/usm/`.

- USM docs (in the USM repo / submodule): `src/usm/docs/`
- MolSAIC-specific USM notes we keep here:
  - USM improvement plan: [USM_IMPROVEMENT_PLAN.md](USM_IMPROVEMENT_PLAN.md)
  - General lattice support notes: [usm_enhancements/GENERAL_LATTICE_SUPPORT.md](usm_enhancements/GENERAL_LATTICE_SUPPORT.md)
  - LB_SF CAR/MDF demo notes: [usm_lb_sf_carmdf_v1.md](usm_lb_sf_carmdf_v1.md)
