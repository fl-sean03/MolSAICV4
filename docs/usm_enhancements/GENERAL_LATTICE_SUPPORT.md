# USM Enhancement: General Lattice Support (triclinic/monoclinic/hexagonal) for wrap_to_cell and replicate_supercell

Status: Approved — Commit 1 in progress  
Owner: USM Core  
Impacts: Geometry ops, replication, tests, docs, workspace runner

Related source anchors:
- Transform wrap implementation target: [src/usm/ops/transform.py](src/usm/ops/transform.py:91)
- Replication implementation target: [src/usm/ops/replicate.py](src/usm/ops/replicate.py:34)
- New lattice helpers module: [src/usm/ops/lattice.py](src/usm/ops/lattice.py)
- Core model schema/types (no change expected): [src/usm/core/model.py](src/usm/core/model.py)
- Limits documentation (to update): [src/usm/docs/LIMITS.md](src/usm/docs/LIMITS.md:1)
- Workspace runner gating (to update): [workspaces/usm_lb_sf_carmdf_v1/run.py](workspaces/usm_lb_sf_carmdf_v1/run.py:276)

## 1) Background and Motivation

Current USM operations assume orthorhombic cells for wrapping and replication:
- wrap_to_cell only performs modulo wrapping when α=β=γ≈90°
- replicate_supercell tiles only via axis-aligned vectors from an orthorhombic assumption

This enhancement adds full triclinic support by introducing robust fractional coordinate transforms for arbitrary unit cells defined by (a, b, c, α, β, γ), and integrating these into wrap/replicate while preserving current behavior on orthorhombic cells.

## 2) Objectives

- Provide stable conversions between Cartesian and fractional coordinates for general lattices.
- Update wrap_to_cell to perform wrapping via fractional coordinates for any valid PBC cell.
- Update replicate_supercell to tile in fractional space for any valid cell; scale lengths a/b/c by na/nb/nc; preserve angles α/β/γ.
- Maintain determinism, numeric stability (float64), and orthorhombic performance characteristics.
- Add unit tests for monoclinic (β≠90°) and hexagonal (γ=120°) cells and property tests for round-trip xyz↔frac.
- Update the LB_SF_carmdf workspace runner to exercise wrap/replicate for both C1 and C2 when cell.pbc is True with finite params.
- Update docs to reflect general lattice support and acceptance criteria.

## 3) Design Overview

### 3.1 Lattice representation

We define a 3×3 lattice matrix A whose ROWS are the lattice vectors (a_vec, b_vec, c_vec) in Cartesian coordinates. With this convention:
- frac_to_xyz: R = F @ A
- xyz_to_frac: F = R @ A^{-1}

Angles are:
- α = angle(b, c)
- β = angle(a, c)
- γ = angle(a, b)

New lattice helper module:
- [src/usm/ops/lattice.py](src/usm/ops/lattice.py)

It provides:
- lattice matrix construction A from (a, b, c, α, β, γ)
- inverse lattice A^{-1} computation with guards
- frac→xyz and xyz→frac transforms that accept (3,) or (N,3) float64 arrays

Stability:
- float64 math
- explicit degeneracy guards for sin(γ)≈0, negative cz² due to round-off, and near-zero det(A)
- determinant thresholds scale-aware and absolute

### 3.2 Wrapping strategy

In [src/usm/ops/transform.py](src/usm/ops/transform.py:91), wrap_to_cell will:
- If cell.pbc is True and parameters are finite and produce a valid lattice:
  1) Compute A and A^{-1}
  2) Convert xyz→frac via A^{-1}
  3) Wrap frac into [0,1) by frac - floor(frac) componentwise
  4) Convert back frac→xyz via A
  5) Write xyz back (float64)
- If PBC is False or cell invalid/singular, act as a no-op (preserving current behavior)
- Preserve orthorhombic pathway semantics and results for α=β=γ=90°

### 3.3 Replication strategy

In [src/usm/ops/replicate.py](src/usm/ops/replicate.py:34), replicate_supercell will:
- Validate na, nb, nc are positive integers
- If PBC is False or cell invalid/singular, raise ValueError (keeping strong semantics)
- Precompute A and A^{-1}
- Convert all base xyz→frac
- For each image (i,j,k) in [0..na-1]×[0..nb-1]×[0..nc-1]:
  - frac_img = frac + (i, j, k) (broadcast)
  - xyz_img = frac_img @ A
- Concatenate images, create deterministic new aids, remap bonds per-image:
  - Build mapping (old_aid, image_index) → new_aid
  - Remap bond endpoints, normalize a1<a2, drop duplicates if any
- Update cell:
  - a*=na, b*=nb, c*=nc
  - α, β, γ preserved exactly
- Deterministic ordering preserved via nested loop order and stable concatenation/remap

## 4) Numerical Stability and Determinism

- All ops in float64
- Property tests target max abs difference for frac round-trip ≤ 1e-12
- Degeneracy guards:
  - sin(γ) threshold: 1e-12
  - negative cz² tolerance: clamp small negatives to 0; hard fail if below -1e-14
  - det(A) threshold: near-zero considered invalid (scale-aware and absolute checks)
- Deterministic ID assignment and concatenation order; consistent bond normalization

## 5) Implementation Plan and Commit Cadence

1) Commit 1: feat(lattice)
   - Add general lattice helpers in [src/usm/ops/lattice.py](src/usm/ops/lattice.py)
   - Export lattice_matrix, lattice_inverse, frac_to_xyz, xyz_to_frac
   - Include degeneracy guards and float64 coercion

2) Commit 1 tests
   - Property tests using seeded NumPy RNG (no Hypothesis)
   - Random valid cells and random frac/xyz; assert round-trip max abs diff ≤ 1e-12
   - Negative tests: near-singular/invalid parameter cases raise ValueError

3) Commit 2: feat(transform)
   - Update wrap_to_cell in [src/usm/ops/transform.py](src/usm/ops/transform.py:91) to general fractional wrapping with lattice helpers
   - Preserve no-op when PBC False or invalid cell
   - Preserve orthorhombic semantics

4) Commit 2 tests
   - Monoclinic cell (α=90°, β=100°, γ=90°): verify post-wrap fractional coordinates in [0,1) and xyz modulo-lattice preservation
   - Hexagonal cell (α=90°, β=90°, γ=120°): same checks

5) Commit 3: feat(replicate)
   - Update replicate_supercell in [src/usm/ops/replicate.py](src/usm/ops/replicate.py:34) to general fractional tiling via A and per-image remap
   - Scale cell lengths by na, nb, nc; preserve angles

6) Commit 3 tests
   - Replicate a small bonded structure under monoclinic and hexagonal cells
   - Assert:
     - atoms and bonds scale by na×nb×nc
     - a/b/c lengths scale correctly; α/β/γ unchanged
     - bonds remapped correctly; a1<a2 normalization; no duplicates

7) Commit 4: chore(workspace)
   - Update runner to always exercise wrap/replicate when cell.pbc True and finite params
     - Remove orthorhombic gating around [workspaces/usm_lb_sf_carmdf_v1/run.py](workspaces/usm_lb_sf_carmdf_v1/run.py:276)
   - Record replicated counts and updated cell in summary.json

8) Commit 5: docs
   - Update limits in [src/usm/docs/LIMITS.md](src/usm/docs/LIMITS.md:1) to reflect general lattice support
   - Add non-orthorhombic examples to [src/usm/docs/EXAMPLES.md](src/usm/docs/EXAMPLES.md:1) demonstrating wrap/replicate on monoclinic and hexagonal cells

## 6) Testing Strategy

- Property tests (Commit 1 tests)
  - Generate random valid triclinic cells:
    - a,b,c ∈ [1, 30], angles α,β,γ ∈ (10°, 170°) with additional constraints to avoid degeneracy (e.g., γ not near 0°/180°)
  - Generate random frac ∈ [-2, 3] and xyz via frac_to_xyz; then xyz_to_frac and compare to original frac (modulo integer shifts as appropriate)
  - Assert:
    - max abs(frac - xyz_to_frac(frac_to_xyz(frac))) ≤ 1e-12
    - max abs(xyz - frac_to_xyz(xyz_to_frac(xyz))) ≤ 1e-12
  - Invalid cells: sin(γ)≈0, negative cz² conditions, or det(A)≈0 → ValueError

- Functional tests (Commit 2/3 tests)
  - Monoclinic wrap: α=90°, β=100°, γ=90°
  - Hexagonal wrap: α=90°, β=90°, γ=120°
  - After wrap: all fracs in [0,1), xyz transformed correctly back
  - Replication: counts scale, lengths scale by na/nb/nc, angles identical

- Integration (workspace)
  - Update and run scenarios C1 and C2 in runner
  - Ensure replicated atoms = na×nb×nc × base, bonds scale accordingly
  - Validate updated cell lengths and preserved angles in summary outputs

## 7) Acceptance Criteria

- Unit/property tests:
  - All round-trip tests pass with max abs diff ≤ 1e-12
  - Monoclinic/hexagonal wrap/replicate tests pass with expected counts and geometry invariants

- Integration:
  - Workspace scenarios C1/C2 produce wrap/replicate outputs; cell lengths scaled, angles preserved
  - No regressions for orthorhombic scenarios; determinism preserved

- Documentation:
  - Limits updated to general lattice support
  - Examples for monoclinic and hexagonal cells added

- Commit discipline:
  - Logical commits per cadence with conventional commit messages

## 8) Performance Considerations

- Orthorhombic fast path:
  - Correctness first; an orthorhombic micro-optimization may be retained as a minor optimization if profiling indicates material impact
- Vectorization:
  - batched transforms (N,3) with matrix multiplication for efficiency
- Bonds and IDs:
  - mapping-based remap is linear and deterministic

## 9) Risks and Mitigations

- Near-singular cells:
  - Explicit guards and clear errors; tests cover boundary cases
- Floating-point drift:
  - float64 everywhere, strict tolerance ≤ 1e-12 for round-trip properties
- Deduplication of bonds:
  - Endpoint normalization and de-dup safeguard; deterministic tie-break (first wins)

## 10) Rollout and Backward Compatibility

- Orthorhombic behaviors remain identical within numeric tolerance
- No schema changes to USM tables
- Runner change broadens applicability (wrap/replicate not gated to orthorhombic)
- If regressions occur, the orthorhombic-only path can be toggled in the runner while fixes land

## 11) Current Status

- New lattice helpers added: [src/usm/ops/lattice.py](src/usm/ops/lattice.py)
- Next: add Commit 1 tests, then generalize wrap_to_cell and replicate_supercell per plan