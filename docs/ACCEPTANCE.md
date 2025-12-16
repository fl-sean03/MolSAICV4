# MolSAIC V4 Acceptance — AS2 Hydration

Purpose
- Define clear verification criteria for correctness and determinism of the alumina AS2 hydration workspace.
- Criteria are CI‑friendly and based on artifacts and structured fields produced by [run.py](workspaces/alumina/alumina_AS2_hydration_v1/run.py:1).

Scope
- Workspace: [run.py](workspaces/alumina/alumina_AS2_hydration_v1/run.py:1)
- Config: [config.json](workspaces/alumina/alumina_AS2_hydration_v1/config.json:1)
- Core library entry points:
  - [msi2namd.run()](src/external/msi2namd.py:96)
  - [packmol.run()](src/external/packmol.py:48)
  - [pm2mdfcar.build()](src/pm2mdfcar/__init__.py:392)
  - [msi2lmp.run()](src/external/msi2lmp.py:70)
- Reference test: [tests/integration/test_hydration_workspaces.py](tests/integration/test_hydration_workspaces.py:1)

1) Artifacts Checks
- Required outputs under outputs/ (non‑zero size):
  - converted/AS2_hydrated.car
  - converted/AS2_hydrated.mdf
  - simulation/AS2_hydration.data
  - summary.json
- Optional but recommended to verify (non‑zero size):
  - AS2.pdb, AS2.psf
  - WAT.pdb, WAT.psf
- The workspace already enforces non‑emptiness at each step; acceptance re‑asserts presence post‑run.

2) Structural and Numeric Checks
- Cell c override:
  - cell.c in summary.json must equal config target_c (absolute tolerance 1e‑6).
  - Source of truth: cell is produced by [pm2mdfcar.build()](src/pm2mdfcar/__init__.py:392) with c := target_c.
- Counts congruency:
  - counts.atoms == counts.surface_atoms + 3 * counts.waters
  - counts.* fields are provided by [pm2mdfcar.build()](src/pm2mdfcar/__init__.py:392).
- Bonds parity (AS2 + replicated WAT):
  - The final bonds are composed as:
    - All AS2 template bonds preserved
    - Plus, for each water molecule, the WAT template bonds replicated
  - Therefore, counts.bonds == bonds_as2_template + counts.waters * bonds_wat_template
  - Note: Typical 3‑site water has 2 bonds per molecule; verify against your WAT.mdf if needed.
- LAMMPS header normalization (header‑only):
  - If run with normalize_z_to (set by [run.py](workspaces/alumina/alumina_AS2_hydration_v1/run.py:1)), the .data header has
    - zlo zhi = 0.0 and target_c
  - Implemented by [msi2lmp.run()](src/external/msi2lmp.py:70) as a header‑only rewrite.

3) Determinism and Reproducibility
- With identical inputs (templates, deck, prm, frc), identical config, and the same versions/paths of external executables:
  - outputs/converted/AS2_hydrated.{car,mdf} and outputs/simulation/AS2_hydration.data are re‑generated deterministically
  - summary.json structured fields (inputs, tools, counts, cell, outputs, warnings) match across runs except timestamps and durations
- CWD and PATH determinism:
  - [msi2namd.run()](src/external/msi2namd.py:98) and [msi2lmp.run()](src/external/msi2lmp.py:70) derive working directories from output prefixes/base names
  - [packmol.run()](src/external/packmol.py:48) writes to the current working directory; [run.py](workspaces/alumina/alumina_AS2_hydration_v1/run.py:1) runs it with cwd=outputs to ensure deck resolution is deterministic
  - Wrappers augment PATH with the executable directory for stable dynamic linking

4) CI‑Friendly Guidance
- Integration test: [tests/integration/test_as2_hydration.py](tests/integration/test_as2_hydration.py)
  - Skips automatically if required executables are not discoverable on PATH or via config overrides
  - Executes the workspace and enforces:
    - Presence and non‑zero size of converted CAR/MDF, LAMMPS .data, and summary.json
    - cell.c equals config target_c within 1e‑6
    - counts.atoms, counts.surface_atoms, counts.waters are sane and congruent
- Environment setup for CI:
  - Ensure Python can import this project (e.g., editable install from repo root: `pip install -e .`)
  - Provide executables via PATH or absolute paths in config.json; tests will skip rather than fail when they are missing

5) How to Verify Manually
- After: python [run.py](workspaces/alumina/alumina_AS2_hydration_v1/run.py:1) --config [config.json](workspaces/alumina/alumina_AS2_hydration_v1/config.json:1)
  - Check artifacts exist and are non‑zero in outputs/
  - Open outputs/summary.json and verify:
    - outputs.lmp_data_file path is present and file is non‑zero
    - cell.c equals inputs.target_c
    - counts.atoms == counts.surface_atoms + 3 * counts.waters
    - warnings list is empty or only contains expected Packmol structure warnings
  - Optional: inspect the .data header for "0.000000 target_c zlo zhi"

6) Acceptance Checklist
- [ ] outputs/converted/AS2_hydrated.car present and non‑zero
- [ ] outputs/converted/AS2_hydrated.mdf present and non‑zero
- [ ] outputs/simulation/AS2_hydration.data present and non‑zero
- [ ] outputs/summary.json present and non‑zero
- [ ] summary.cell.c equals config target_c (tolerance 1e‑6)
- [ ] summary.counts.atoms == summary.counts.surface_atoms + 3 * summary.counts.waters
- [ ] Bonds parity aligns with: bonds_as2_template + waters * bonds_wat_template
- [ ] Re‑run determinism confirmed: summary structured fields match (timestamps/durations excepted)
- [ ] CI: test [tests/integration/test_as2_hydration.py](tests/integration/test_as2_hydration.py) passes or is skipped when executables are unavailable