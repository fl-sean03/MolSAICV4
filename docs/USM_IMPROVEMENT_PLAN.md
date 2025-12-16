USM Improvement Plan — Implementation, Validation, and Rollout

Status
- This document is the master plan for implementing robustness and capability upgrades to USM.
- It covers design, step-by-step implementation guides, validation and test plans, and rollout with commit cadence.

Context and Goals
USM already provides deterministic CAR/MDF I/O, a unified schema, composition of CAR coordinates with MDF bonds, and a set of core operations. On the LB_SF_carmdf datasets we demonstrated:
- Exact CAR xyz numeric equality after round-trip
- Lossless MDF header preservation and connections_raw round-trips
- Correct bonding via composition for MDFs with connections
- Deterministic transforms and orthorhombic replication

We will now:
- Add general lattice support (triclinic/monoclinic/hexagonal) to wrap and replicate
- Finalize bundle load + integrate bundles in workflows
- Harden MDF writer formatting for formal_charge
- Add composition coverage diagnostics
- Expand MDF round-trip numeric checks
- Enrich PDB exporter
- Ensure multi-generation text stability
- Fuzz MDF connections parsing
- Bake in determinism gates and run performance probes

Reference Implementation Anchors
- CAR I/O: [load_car()](src/usm/io/car.py:128), [save_car()](src/usm/io/car.py:187)
- MDF I/O: [load_mdf()](src/usm/io/mdf.py:243), [save_mdf()](src/usm/io/mdf.py:378)
- PDB I/O: [save_pdb()](src/usm/io/pdb.py:69)
- Core model: [USM](src/usm/core/model.py:89)
- Compose: [compose_on_keys()](src/usm/ops/compose.py:13)
- Transforms: [translate()](src/usm/ops/transform.py:26), [rotate()](src/usm/ops/transform.py:62), [wrap_to_cell()](src/usm/ops/transform.py:91)
- Replicate: [replicate_supercell()](src/usm/ops/replicate.py:34)
- MDF bonds build: [_build_bonds_from_connections()](src/usm/io/mdf.py:148)
- Bundle I/O: save [save_bundle()](src/usm/bundle/io.py:42), load [load_bundle()](src/usm/bundle/io.py:118) (to be implemented)

Roadmap Overview (Phased)
P0 — Highest Value, Lowest Risk
1. General lattice support for wrap_to_cell and replicate_supercell
2. MDF writer formal_charge formatting robustness
3. Composition coverage diagnostics

P1 — Cross-cutting Stability
4. Bundle load implementation and runner integration
5. MDF numeric-field round-trip checks (runner + unit tests)

P2 — Interop/Quality
6. PDB exporter enhancements (CONECT, MODEL)
7. Multi-generation writer stability
8. MDF connections parsing fuzz/property tests

P3 — CI and Performance
9. Determinism harness and CI gates
10. Performance/scale probes
11. Documentation refresh and example overhauls

Detailed Design and Implementation Guides

1) General Lattice Support (wrap/replicate)
Motivation
- Current [wrap_to_cell()](src/usm/ops/transform.py:91) and [replicate_supercell()](src/usm/ops/replicate.py:34) support orthorhombic cells only (angles ~ 90°). We will support general cells, enabling wrap/replicate for hexagonal (gamma=120°), monoclinic (beta ≠ 90°), triclinic.

Design
- Add lattice utilities for Cartesian ↔ Fractional transforms:
  - Construct 3x3 cell matrix A from (a, b, c, α, β, γ)
  - Inverse cell matrix A⁻¹
  - xyz_to_frac = A⁻¹ · xyz
  - frac_to_xyz = A · frac
- wrap_to_cell:
  - Given usm.cell with finite a,b,c,alpha,beta,gamma and pbc=True:
    - Compute frac = xyz_to_frac(xyz)
    - Bring each component into [0,1) via frac -= floor(frac)
    - xyz_wrapped = frac_to_xyz(frac)
- replicate_supercell:
  - Iterate i ∈ [0..na-1], j ∈ [0..nb-1], k ∈ [0..nc-1] in fractional space:
    - frac_img = frac_orig + (i, j, k)
    - xyz_img = frac_to_xyz(frac_img)
  - Preserve angles; scale cell lengths a*=na, b*=nb, c*=nc.

Implementation Notes
- New lattice helpers module (small, no new dependency). Place in [src/usm/ops/cell.py](src/usm/ops/cell.py:1) or a new submodule (e.g., usm/geom/lattice.py) with a stable API.
- Validate numeric stability in double precision; avoid singular/degenerate cell detection by checking sin/cos combos for angle sets.

Acceptance Criteria
- Unit Tests:
  - Synthetic monoclinic and hexagonal cells:
    - wrap_to_cell ensures frac in [0,1) and coords recomposed
    - replicate_supercell yields counts scaled by na×nb×nc; a/b/c scaled; angles preserved
  - Randomized cells in sane ranges (angles (40..140)°, lengths (1..100) Å) pass frac→xyz→frac tests within 1e-12.
- Integration:
  - C1 (PbI2_sup) and C2 (R-2-FMBA_PbI4) now support wrap/replicate; runner summary includes these outputs.

2) MDF Writer — formal_charge Robustness
Motivation
- [save_mdf()](src/usm/io/mdf.py:378) currently right-aligns formal_charge into a fixed-width field that may truncate tokens like "1/2+".

Design
- Replace strict width for formal_charge with a widened or dynamically spaced field so it prints intact. Ensure neighboring columns retain their spacing.

Implementation Notes
- The MDF atom line is assembled near [save_mdf()](src/usm/io/mdf.py:378). Adjust:
  - formal_charge = str(val) without width, pad or separate with a space
  - Keep element, atom_type, charge_group fields aligned.

Acceptance Criteria
- Unit Test:
  - MDF with formal_charge tokens ["0", "1+", "2-", "1/2+"] -> load→save(preserve_headers=False)→load; tokens must be identical.

3) Composition Coverage Diagnostics
Motivation
- [compose_on_keys()](src/usm/ops/compose.py:13) silently joins on keys ["mol_label","mol_index","name"]. Mismatches can produce partial composition.

Design
- Compute coverage metrics:
  - matched_count
  - left_only_count (primary-only)
  - right_only_count (secondary-only)
- Policy:
  - "silent" (default), "warn" (log metrics in provenance or runner), "error_below_coverage" with threshold (e.g., ≥95% matched).
- Output:
  - Record metrics in provenance.parse_notes or return a compose_report dict to the caller.

Implementation Notes
- After building sec_trim and merging, compute set operations over key tuples. Append parse_notes succinctly to preserve provenance semantics.

Acceptance Criteria
- Unit Test: Partial-overlap fixtures assert metrics and behavior under policy settings.
- Runner: Incorporate metrics into scenario summary.json; visible and queryable.

4) Bundle I/O — load_bundle implementation and runner integration
Motivation
- The docs reference bundles; [save_bundle()](src/usm/bundle/io.py:42) exists, [load_bundle()](src/usm/bundle/io.py:118) is NotImplementedError.

Design
- Bundle folder:
  - atoms/bonds/molecules parquet or csv
  - manifest.json with schema and metadata (cell, provenance, preserved_text)
- load_bundle:
  - Read tables via pyarrow/fastparquet; if unavailable, csv fallback
  - Reconstitute USM with dtypes coerced by [USM.__post_init__](src/usm/core/model.py:98)
  - Restore cell/provenance/preserved_text from manifest

Acceptance Criteria
- Unit tests:
  - save→load equality for tables and metadata
  - CSV fallback path coverage
- Runner:
  - Optional save and reload step with structural equality check in summary.

5) MDF Numeric-Field Round-Trip Checks
Motivation
- We currently assert headers and connections_raw equality. We should also check numeric field stability (charge, occupancy, xray_temp_factor, flags).

Design
- Runner Enhancement:
  - After MDF RT, compute per-column diffs (max_abs_diff, exact_equal boolean) with tolerances per field
  - Add fail-fast when diffs exceed tolerance (configurable)

Acceptance Criteria
- Unit tests for exact or near-exact numeric RT for small fixtures
- Runner summary contains per-column diff metrics; mdf_roundtrip_ok fails when exceeding thresholds

6) PDB Exporter Enhancements
Motivation
- [save_pdb()](src/usm/io/pdb.py:69) is minimal. For downstream compatibility, optionally include CONECT and MODEL/ENDMDL.

Design
- Opt-in parameters:
  - include_conect=True → write CONECT from usm.bonds
  - include_model=True → wrap ATOM records in MODEL/ENDMDL
- CRYST1:
  - Continue emitting for any valid cell (not limited to orthorhombic)

Acceptance Criteria
- Unit tests assert presence and correct formatting of CRYST1, CONECT, MODEL blocks when enabled.

7) Multi-Generation Writer Stability
Motivation
- Beyond single round-trip, we want writer stability across generations.

Design
- Add runner mode:
  - CAR: load→save car_gen2, load car_gen2 → save car_gen3; compare atom-line text sections for exact equality
  - MDF: same with normalized connections enabled (write_normalized_connections=True)

Acceptance Criteria
- Unit tests with golden text comparators
- Runner flags: car_text_stable_across_generations / mdf_text_stable_across_generations

8) MDF Connections Parsing — Fuzz and Property Tests
Motivation
- [_build_bonds_from_connections()](src/usm/io/mdf.py:148) must be robust to token variations.

Design
- Expand tests to include:
  - Fully-qualified tokens, order tokens, “%” suffixes, whitespace, case variations
  - Duplicate connections; ensure dedup and a1<a2 invariant
  - Unresolvable tokens should be skipped without exceptions

Acceptance Criteria
- Unit/property tests cover a diverse corpus; all invariants hold; no exceptions on malformed tokens.

9) Determinism Harness and CI
Motivation
- Make determinism a gating property to prevent regressions.

Design
- Determinism test:
  - Run operations twice; compare atoms/bonds tables and metadata equality
- CI:
  - Add job that builds/runs deterministic tests; failure blocks merge

Acceptance Criteria
- Repeated pipeline runs produce identical tables and metadata; CI gate enforced.

10) Performance and Scale Probes
Motivation
- Validate O(N) behaviors and provide practical guidance.

Design
- Script for replicate/transform/select/compose timings and memory; measure bundle I/O with Parquet vs CSV
- Report thresholds and recommendations in [docs/PERFORMANCE.md](src/usm/docs/PERFORMANCE.md:9)

Acceptance Criteria
- Document the results; add perf regression alerts if desired.

11) Documentation and Examples
Updates
- [docs/API.md](src/usm/docs/API.md:3): reflect general lattice support and bundle load
- [docs/EXAMPLES.md](src/usm/docs/EXAMPLES.md:1): add non-orthorhombic wrap/replicate example and composition coverage example
- [docs/LIMITS.md](src/usm/docs/LIMITS.md:1): update lattice support scope
- New: mini-tutorials and troubleshooting for coverage mismatches and bundle workflows

Cross-Cutting Validation Matrix

Unit Tests
- USM model dtype normalization: [USM.__post_init__](src/usm/core/model.py:98)
- CAR/MDF/PDB I/O:
  - CAR: load/save/load numeric equality and multi-gen stability
  - MDF: header preservation, normalized connections optional mode, numeric columns RT
  - PDB: CRYST1, CONECT, MODEL formatting

Property/Fuzz Tests
- Lattice frac↔xyz conversion numeric stability
- MDF connections token parsing

Integration Tests
- Workspace reruns with updated runner checks
- Compose coverage metrics and policies

Determinism
- Run pipelines twice comparing full tables equality; CI gating

Performance
- Replicate scale-out and bundle I/O timings documented

Rollout Plan and Commit Cadence

Baseline commit (now)
- Commit current workspace and runner changes:
  - docs/usm_lb_sf_carmdf_v1.md
  - workspaces/other/usm_lb_sf_carmdf_v1/run.py (with exact xyz metrics)
  - workspaces/other/usm_lb_sf_carmdf_v1/config.json
  - outputs generated (if tracked, optional)
- Commit message (example):
  - chore(workspace): add USM LB_SF_carmdf demo with exact CAR xyz RT metrics; docs scaffold

P0 PRs (in order)
1. feat(lattice): general wrap/replicate for triclinic cells
   - + unit/integration tests; runner updates to exercise C1/C2
   - commit per logical sub-step (helpers → wrap → replicate → tests)
2. fix(mdf): preserve formal_charge tokens like 1/2+; widen field
   - + unit tests for token RT
3. feat(compose): coverage diagnostics and policy hooks
   - + runner logs coverage metrics

P1 PRs
4. feat(bundle): implement load_bundle; integrate into runner; + tests
5. feat(mdf-rt): numeric-field checks and runner metrics

P2 PRs
6. feat(pdb): optional CONECT/MODEL; + unit tests
7. test(io-stability): multi-generation writer stability; golden tests
8. test(mdf-conns): fuzz/property tests

P3 PRs
9. ci(determinism): determinism harness and CI gate
10. perf: performance probe scripts and documentation
11. docs: refresh all docs and examples

Post-Deployment Monitoring
- Keep runner metrics as guardrails in CI (json outputs validated by a simple schema).
- Watch determinism and numeric-field thresholds for regressions.

Appendix A: Triclinic Cell Formulas
Given (a,b,c) and (α,β,γ) in degrees, construct the cell matrix A whose columns are a⃗, b⃗, c⃗:
- α = angle between b⃗ and c⃗
- β = angle between a⃗ and c⃗
- γ = angle between a⃗ and b⃗

Let:
- ax = a, ay = 0, az = 0
- bx = b cos γ, by = b sin γ, bz = 0
- cx = c cos β
- cy = c (cos α − cos β cos γ) / sin γ
- cz = sqrt(c^2 − cx^2 − cy^2)

Then:
- A = [[ax, bx, cx],
       [ay, by, cy],
       [az, bz, cz]]

Fractional f → Cartesian r: r = A f
Cartesian r → Fractional f: f = A⁻¹ r

Appendix B: Runner Metrics (current and planned)
Already present
- CAR: car_xyz_exact_equal, car_xyz_max_abs_diff, car_xyz_per_axis_max_abs_diff, car_xyz_nonzero_count
Planned additions
- MDF per-column max_abs_diff for charge, occupancy, xray_temp_factor, flags
- Compose coverage: matched_count, left_only_count, right_only_count, coverage_ratio
- Writer stability: car_text_stable_across_generations, mdf_text_stable_across_generations
- Bundle: bundle_roundtrip_ok (tables + metadata equal)

End of Plan