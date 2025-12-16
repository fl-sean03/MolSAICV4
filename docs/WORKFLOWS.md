# MolSAIC V4 Workflows — Code‑First Pattern and Workspace Contract

Goal
- Explain the V4 workflow pattern and the workspace contract using the alumina AS2 hydration workspace as a concrete example.
- Show deterministic conventions for CWD and PATH handling, step mapping, and how to customize inputs and extend to similar systems.

Primary references
- Workspace entry: [run.py](workspaces/alumina/alumina_AS2_hydration_v1/run.py:1)
- Config defaults: [config.json](workspaces/alumina/alumina_AS2_hydration_v1/config.json:1)
- External wrappers: [msi2namd.run()](src/external/msi2namd.py:96), [packmol.run()](src/external/packmol.py:46), [msi2lmp.run()](src/external/msi2lmp.py:68)
- Composition op: [pm2mdfcar.build()](src/pm2mdfcar/__init__.py:392)

1) V4 Pattern
- Code‑first: workspaces are plain Python scripts that import a small, deterministic library surface and call external executables via thin wrappers.
- Minimal configuration: each workspace has a small JSON file with paths, parameters, and executable hints.
- Single run command: invoke run.py with a config, and all artifacts are written under outputs/.

Workspace contract
- Layout inside each workspace directory:
  - run.py: the orchestrator script, e.g., [run.py](workspaces/alumina/alumina_AS2_hydration_v1/run.py:1)
  - config.json: inputs, parameters, executables, timeouts, and outputs_dir
  - outputs/: created on first run, with standardized subfolders
    - outputs/converted: CAR and MDF produced by composition
    - outputs/simulation: final LAMMPS .data and related simulation artifacts
    - outputs/summary.json: machine‑readable manifest of inputs, tools, timings, counts, cell, outputs, warnings
- Behavior guarantees:
  - Deterministic processing: stable ordering, explicit cwd, consistent staging, and validation that required outputs are present and non‑empty.
  - No hidden global state: the script resolves all paths and writes locally under outputs/.

2) Deterministic Conventions and Environment Handling
- Working directory discipline:
  - [msi2namd.run()](src/external/msi2namd.py:98)
    - Derives its working directory from the parent of output_prefix.
    - Stages CAR and MDF inputs into that working directory if needed.
  - [packmol.run()](src/external/packmol.py:48)
    - Uses the current working directory as the output directory.
    - The workspace temporarily chdir’s into outputs/ to ensure deck structure paths resolve correctly.
  - [msi2lmp.run()](src/external/msi2lmp.py:70)
    - Derives its working directory from base_name, i.e., the directory containing the CAR and MDF.
- PATH augmentation:
  - Each wrapper prepends the executable’s directory to PATH to mitigate dynamic linker issues at runtime.
- Input staging and validation:
  - Wrappers check for missing inputs and fail fast with clear exceptions.
  - Outputs are validated for existence and non‑zero size before returning.
- Timeouts:
  - Each wrapper enforces a timeout (configurable via timeouts_s in [config.json](workspaces/alumina/alumina_AS2_hydration_v1/config.json:1)) and raises on expiry.

3) Step Semantics and Mapping
- Step 1: AS2 PDB and PSF
  - Call: [msi2namd.run()](src/external/msi2namd.py:96)
  - Inputs: AS2.mdf, AS2.car, parameters.prm, residue tag such as AS2
  - Output: outputs/AS2.pdb and outputs/AS2.psf
  - Determinism: inputs staged into the derived working directory; outputs validated.
- Step 2: WAT PDB and PSF
  - Call: [msi2namd.run()](src/external/msi2namd.py:96)
  - Inputs: WAT.mdf, WAT.car, parameters.prm, residue tag such as WAT
  - Output: outputs/WAT.pdb and outputs/WAT.psf
- Step 3: Hydration packing with Packmol
  - Call: [packmol.run()](src/external/packmol.py:46)
  - Invocation detail: workspace temporarily sets cwd=outputs/ during the call so deck structure lines resolve to outputs/AS2.pdb and outputs/WAT.pdb
  - Output: hydrated PDB file as named in the deck (e.g., hydrated_AS2.pdb)
  - Determinism: set packmol_seed in config to inject "seed N" into the deck; Packmol reads the deck via stdin (seekable file handle)
  - Warnings policy: missing structure files are collected as 'warnings'; set warnings_policy.escalate_missing_structures=true to fail early
- Step 4: Compose CAR and MDF with numeric PBC c
  - Call: [pm2mdfcar.build()](src/pm2mdfcar/__init__.py:392)
  - Behavior:
    - Deterministic output order: AS2 atoms in template order, then waters ordered by residue index, each as O, H, H
    - Bonds: preserves AS2 bonds from the AS2 template and replicates WAT bonds for each water; deduplicates and sorts
    - Cell: copies a, b, and angles from AS2 template, overrides c with target_c
  - Output: outputs/converted/AS2_hydrated.car and .mdf
- Step 5: LAMMPS .data via msi2lmp
  - Call: [msi2lmp.run()](src/external/msi2lmp.py:68)
  - Behavior:
    - Runs in the directory containing AS2_hydrated.car and .mdf
    - Produces a .data, then moves or renames it to outputs/simulation/AS2_hydration.data
    - Optional header‑only normalization sets zlo zhi to 0 and target_c when normalize_z_to is provided
  - Output: outputs/simulation/AS2_hydration.data

Mermaid
flowchart LR
  A[run.py workspace] --> B[msi2namd AS2]
  A --> C[msi2namd WAT]
  B --> D[AS2 PDB PSF]
  C --> E[WAT PDB PSF]
  D --> F[packmol]
  E --> F
  F --> G[hydrated PDB]
  G --> H[pm2mdfcar build]
  H --> I[AS2_hydrated CAR MDF]
  I --> J[msi2lmp run]
  J --> K[LAMMPS data]
  K --> L[summary json]

4) Customizing Inputs and Parameters
- Templates and decks:
  - templates_dir: directory containing AS2.car AS2.mdf WAT.car WAT.mdf
  - packmol_deck: Packmol deck path; ensure structure lines refer to AS2.pdb and WAT.pdb as they will exist under outputs/
- Residue names:
  - residue_surface and residue_water must be 1–4 characters (validated by run.py prior to calls)
- target_c:
  - Numeric cell c value written into CAR and MDF by [pm2mdfcar.build()](src/pm2mdfcar/__init__.py:392) and used for header normalization by [msi2lmp.run()](src/external/msi2lmp.py:70)
- Executables and timeouts:
  - executables in config.json can override PATH discovery; timeouts_s adjusts per‑tool timeouts
- CWD and deck expectations:
  - Because [packmol.run()](src/external/packmol.py:48) writes to cwd, the workspace ensures cwd=outputs during the call. Author your deck with relative structure names to those outputs.

5) Extending the Pattern to Similar Systems
- Start with the workspace template:
  - [run.py](workspaces/_template/run.py:1) and [config.json](workspaces/_template/config.json:1)
- Swap templates:
  - Point templates_dir to the appropriate CAR and MDF pair for the target surface; ensure the water template matches your intended water model
- Adjust the Packmol deck:
  - Update target_box and structure counts; keep output filename under outputs to align with cwd behavior
- Tune parameters:
  - Update residue labels, target_c, and forcefield file paths
- Keep the contract:
  - Maintain outputs/ structure and write a summary.json with inputs, tools, timings, outputs, counts, cell, and warnings as done by [run.py](workspaces/alumina/alumina_AS2_hydration_v1/run.py:1)

6) Wrapper Behaviors and Assumptions Summary
- [msi2namd.run()](src/external/msi2namd.py:96)
  - Stages inputs into working directory; uses output_prefix to determine cwd and output names; augments PATH; validates outputs
- [packmol.run()](src/external/packmol.py:46)
  - Consumes the deck via stdin (seekable), writes to cwd; supports seed injection for determinism and warnings escalation; aggregates non‑fatal warnings
- [pm2mdfcar.build()](src/pm2mdfcar/__init__.py:392)
  - Deterministic atom ordering and bond construction; numeric PBC with c override; returns counts and cell for acceptance checks
- [msi2lmp.run()](src/external/msi2lmp.py:68)
  - Runs in CAR/MDF directory; renames or moves .data to the requested output_prefix; optional header‑only z normalization

7) Summary.json as Workflow Contract
- Written by the workspace after all validations:
  - inputs: resolved paths and parameters used
  - params: packmol_seed and normalization flags (normalize_xy, normalize_z_to)
  - tools: discovered or configured executable paths; tool_profile when profiles are used
  - tool_versions: version strings for external tools (best effort capture)
  - timings: durations for each step
  - outputs: absolute paths to artifacts
  - counts and cell: provided by [pm2mdfcar.build()](src/pm2mdfcar/__init__.py:392)
  - warnings: union of composition warnings and Packmol deck structure warnings
- Consumers can rely on summary.json to verify acceptance and to feed downstream automation.