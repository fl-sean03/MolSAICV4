# MolSAIC V4 Quickstart — AS2 Hydration

Purpose
- Fast path to run the alumina AS2 hydration workspace end‑to‑end and verify outputs.
- Pattern is code‑first: a plain Python script [run.py](workspaces/alumina/alumina_AS2_hydration_v1/run.py:1) orchestrates small library functions and thin wrappers over external tools.

Core entry points
- [msi2namd.run()](src/external/msi2namd.py:96) → AS2 and WAT PDB/PSF
- [packmol.run()](src/external/packmol.py:46) → hydrated PDB
- [pm2mdfcar.build()](src/pm2mdfcar/__init__.py:392) → CAR and MDF with c override
- [msi2lmp.run()](src/external/msi2lmp.py:68) → LAMMPS .data

1) Prerequisites
- Python 3.9+
- External executables installed and on PATH or provided as absolute paths in config:
  - msi2namd
  - packmol
  - msi2lmp
- OS: Linux or compatible environment for the executables above

2) Install and import
- Editable install (recommended):
  - From repository root:
    - pip install -e .
- After install, scripts import usm.*, external.*, and pm2mdfcar.* directly (no PYTHONPATH hacks).

3) Configure the workspace
- Configuration file: [config.json](workspaces/alumina/alumina_AS2_hydration_v1/config.json:1)
- Keys (defaults shown in the file):
  - outputs_dir: "./outputs"
    - Workspace writes artifacts under this directory; subfolders: converted/, simulation/
  - templates_dir: path to AS2/WAT template CAR/MDF directory
  - packmol_deck: path to the Packmol deck (.inp)
  - parameters_prm: CHARMM‑style .prm used by msi2namd
  - frc_file: .frc used by msi2lmp
  - residue_surface: "AS2" (1–4 chars enforced)
  - residue_water: "WAT" (1–4 chars enforced)
  - target_c: numeric cell c to write into CAR/MDF and normalized header in .data
  - executables: optional overrides for msi2namd, packmol, msi2lmp
    - Each may be a program name on PATH or an absolute/relative file path
  - executables_profiles: optional profiles map (e.g., "local", "container") each with msi2namd/packmol/msi2lmp paths
  - selected_profile: pick a profile from executables_profiles; explicit "executables" keys override profile values
  - timeouts_s: per‑tool timeouts in seconds
  - packmol_seed: optional integer RNG seed for Packmol determinism
  - warnings_policy: { "escalate_missing_structures": false } to fail when deck references missing structures
  - validate_manifest: set true to validate outputs/summary.json against [manifest.v1.schema.json](docs/manifest.v1.schema.json:1)
- Relative path resolution
  - Paths are resolved relative to the workspace directory first, then the current working directory at runtime

4) Verify required executables
- Check presence on PATH:
  - which msi2namd || echo "msi2namd not found"
  - which packmol || echo "packmol not found"
  - which msi2lmp || echo "msi2lmp not found"
- If missing, set absolute paths in config.json under "executables"
- The wrappers augment PATH at runtime to include the executable directory

5) Run the workspace
- From the workspace directory:
  - cd workspaces/alumina/alumina_AS2_hydration_v1
  - python run.py --config ./config.json
- Notes on working directories and outputs
  - Step 1 and 2 ([msi2namd.run()](src/external/msi2namd.py:96)) write AS2.* and WAT.* next to outputs_dir
  - Step 3 ([packmol.run()](src/external/packmol.py:46)) runs with cwd=outputs_dir so a deck that uses structure AS2.pdb and structure WAT.pdb resolves correctly
  - Step 4 ([pm2mdfcar.build()](src/pm2mdfcar/__init__.py:392)) writes converted/AS2_hydrated.{car,mdf}
  - Step 5 ([msi2lmp.run()](src/external/msi2lmp.py:68)) writes simulation/AS2_hydration.data

6) Inspect expected outputs
- Under outputs/:
  - AS2.pdb, AS2.psf
  - WAT.pdb, WAT.psf
  - Hydrated PDB from Packmol (file name defined by the deck)
  - converted/AS2_hydrated.car
  - converted/AS2_hydrated.mdf
  - simulation/AS2_hydration.data
  - summary.json (run manifest)
- Mapping to steps:
  - msi2namd → AS2.* and WAT.* via [msi2namd.run()](src/external/msi2namd.py:96)
  - packmol → hydrated PDB via [packmol.run()](src/external/packmol.py:46)
  - pm2mdfcar → CAR/MDF via [pm2mdfcar.build()](src/pm2mdfcar/__init__.py:392)
  - msi2lmp → .data via [msi2lmp.run()](src/external/msi2lmp.py:68)

7) Interpret summary.json
- Location: outputs/summary.json
- Fields:
  - inputs: resolved paths and parameters (templates_dir, parameters_prm, frc_file, packmol_deck, residues, target_c)
  - params: run parameters (packmol_seed, normalize_xy, normalize_z_to)
  - tools: resolved executable paths; tool_profile when profiles used
  - tool_versions: version strings for each external tool (best effort)
  - timings: per‑step durations in seconds
  - outputs: absolute paths to artifacts listed above
  - counts: totals from [pm2mdfcar.build()](src/pm2mdfcar/__init__.py:392) including atoms, surface_atoms, waters, bonds
  - cell: numeric a, b, c, alpha, beta, gamma with c set to target_c
  - warnings: aggregated from composition plus Packmol deck structure warnings
- Quick checks:
  - outputs.lmp_data_file exists and non‑zero
  - cell.c equals config target_c
  - counts.atoms equals counts.surface_atoms + 3*counts.waters

8) Troubleshooting
- ModuleNotFoundError: No module named usm/external/pm2mdfcar
  - Ensure editable install from repo root:
    - pip install -e .
  - See: [README.md](README.md:1)
- Executable not found errors
  - Provide absolute paths in config.json under "executables"
  - Ensure executable bit is set and the file is compatible with your OS
- Packmol created no output or deck warnings
  - Check outputs/ for hydrated PDB; if missing, inspect summary.json warnings and ensure deck structure paths match cwd=outputs
- Empty or missing artifacts
  - The workspace validates outputs are non‑empty at each step; failures will appear on stderr and in logs
- Timeouts
  - Increase timeouts_s in config.json for long runs or slow machines