# Alumina surfaces with ions in water (Packmol-based pipelines)

This document describes the new “ions-in-water” workflows for alumina surfaces that place ions into the water region using Packmol, instead of embedding ions in the slab templates. These workflows reproduce legacy ion totals per surface while allowing ions to distribute freely within the aqueous layer.

## Surfaces covered

- AS2 (legacy ions: Cl- only)
- AS5 (legacy ions: Cl- only)
- AS10 (legacy ions: Na+ only)
- AS12 (legacy ions: Na+ only)

Ion counts are derived from the original templates (CAR/MDF) per surface:
- AS2: NA=0, CL=22
- AS5: NA=0, CL=10
- AS10: NA=10, CL=0
- AS12: NA=18, CL=0

The template directory contains:
- assets/AluminaSurfaces/templates/AS{2,5,10,12}.{car,mdf}
- assets/AluminaSurfaces/templates/WAT.{car,mdf}
- assets/AluminaSurfaces/templates/NA.{car,mdf} (one-atom ion template)
- assets/AluminaSurfaces/templates/CL.{car,mdf} (one-atom ion template)
- assets/AluminaSurfaces/packmol/packmol_AS{2,5,10,12}.inp (canonical water-box geometry and water count)
- assets/AluminaSurfaces/prm_files/parameters.prm (CHARMM-style)
- assets/AluminaSurfaces/frc_files/*.frc (forcefield inputs; not a committed dependency for CALF-20 “from scratch” flows)

## Workflow overview

Per-surface workspaces (one each):

- [workspaces/alumina/alumina_AS2_ions_v1](workspaces/alumina/alumina_AS2_ions_v1:1)
- [workspaces/alumina/alumina_AS5_ions_v1](workspaces/alumina/alumina_AS5_ions_v1:1)
- [workspaces/alumina/alumina_AS10_ions_v1](workspaces/alumina/alumina_AS10_ions_v1:1)
- [workspaces/alumina/alumina_AS12_ions_v1](workspaces/alumina/alumina_AS12_ions_v1:1)

Each workspace/run.py performs:

1) msi2namd: Convert ASx and WAT templates to PDB/PSF using parameters.prm
2) Prepare ion PDBs: single-atom PDBs for NA and CL (generated programmatically)
3) Packmol: Build hydrated structure by fixing slab and packing waters + ions inside the canonical top water box (dimensions and water count taken from assets’ packmol deck)
4) pm2mdfcar: Compose final CAR/MDF from the packed PDB with c := target_c (header/meta emitted)
5) msi2lmp: Convert CAR/MDF to LAMMPS .data, normalizing headers (XY/Z) to target cell, uniformly shifting z so min(z)=0
6) Validation: Emit ion z-distribution histogram (JSON/CSV) for quick visual inspection of ion dispersion in the water region

Notes:
- Ion counts default to the legacy totals embedded in the original slab templates (per surface). You can override via config.ions.counts_override.
- When an ion count is zero, the Packmol deck generation skips that ion’s structure block to avoid STOP 171 errors.
- Packmol determinism is enabled via a seed (config.packmol_seed).

## How to run

From repository root, each workspace has a config.json specifying executables and inputs.

Examples:
- AS2:  python3 workspaces/alumina/alumina_AS2_ions_v1/run.py --config config.json
- AS5:  python3 workspaces/alumina/alumina_AS5_ions_v1/run.py --config config.json
- AS10: python3 workspaces/alumina/alumina_AS10_ions_v1/run.py --config config.json
- AS12: python3 workspaces/alumina/alumina_AS12_ions_v1/run.py --config config.json

Outputs are written under workspaces/alumina/alumina_ASX_ions_v1/outputs/.

Key artifacts per run:
- outputs/hydrated_ASX_ions.pdb
- outputs/converted/ASX_hydrated.{car,mdf}
- outputs/simulation/ASX_ions_hydration.data
- outputs/summary.json
- outputs/ion_z_histogram.{json,csv}
- outputs/packmol_ASX_ions.inp (generated deck with ‘seed’ injected)

## Summary manifest

Each run writes outputs/summary.json that includes:
- started_at/finished_at timestamps (UTC ISO)
- inputs (templates/prm/frc, packmol deck, residue names, target_c)
- params (packmol_seed, salt_molarity when present)
- tools (resolved executable paths)
- tool_versions (best-effort version capture of msi2namd/packmol/msi2lmp)
- durations_s (msi2namd surface/water, packmol, pm2mdfcar, msi2lmp)
- outputs (paths to PDB/PSF, CAR/MDF, .data, packmol deck, outputs dir)
- counts (total atoms if available, waters from deck, ion counts used)
- cell (c equals target_c; a/b/angles filled when available)
- warnings (non-fatal notes, e.g., parquet optional dependency, missing PBC in one-atom ion templates)

The manifest conforms to docs/manifest.v1.schema.json (jsonschema validation used in tests).

## Ion validation (z-distribution)

After composition, each run emits:
- outputs/ion_z_histogram.json
- outputs/ion_z_histogram.csv

These files give simple binned counts vs. z for ‘na+’ and ‘cl-’ within the water box z-range. The goal is to verify ions are interspersed in the water region (broad distribution), not concentrated exclusively at the slab.

Quick check:
- Inspect the CSV: increasing bin centers across z; counts for the present ion species (nonzero in several bins)
- For AS2/AS5 (Cl- only), check cl- counts; for AS10/AS12 (Na+ only), check na+ counts.

## Determinism

The Packmol seed (config.packmol_seed) is injected into the deck for reproducible packing. When RUN_DETERMINISM=1 is set for integration tests, structured fields in summary.json are compared across runs for equality.

## Integration tests

Added tests/integration/test_ions_workspaces.py:
- Validates committed summary.json files against docs/manifest.v1.schema.json
- Optionally runs full pipelines if RUN_INTEGRATION=1 and executables are available
- Optionally checks determinism if RUN_DETERMINISM=1

Common pytest notes:
- You may register the “integration” mark in pytest.ini to silence PytestUnknownMarkWarning

Example pytest.ini:
  [pytest]
  markers =
      integration: marks tests that are integration (deselect with -m "not integration")

## Troubleshooting

- Packmol STOP 171: Previously could occur when an ion count was zero. The deck generator now omits ‘structure’ blocks for zero-count species, avoiding the error.
- Optional parquet dependency warnings in pm2mdfcar: harmless; CSV fallbacks are used.
- PBC parsing warnings for one-atom ion templates (NA/CL): expected; one-atom CARs do not carry meaningful PBC; full-system CAR/MDF has PBC set to target cell.

## Configuration knobs

- target_c: Final cell length along z (e.g., 81.397 Å)
- executables/executables_profiles/selected_profile: Tool resolution and profiles
- packmol_seed: RNG seed for deterministic packing
- ions.counts_override: Optional override of ion totals ({"NA": n, "CL": n}); by default, per-surface legacy totals from slab templates are used
- warnings_policy.escalate_missing_structures: Raise error on missing structure files in Packmol deck preflight validation

## Findings snapshot (legacy totals)

- AS2 (pH8–9): Cl− only → 22
- AS5 (pH8–9): Cl− only → 10
- AS10 (~pH11.5): Na+ only → 10
- AS12 (~pH11.5): Na+ only → 18

These totals are reproduced by placing ions into the water region via Packmol, enabling study of mobile ions in solution instead of fixed slab-bound ions.
