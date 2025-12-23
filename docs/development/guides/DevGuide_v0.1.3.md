# DevGuide v0.1.3 — Symmetry-Correct Supercell Building & Explicit Bonding

**Status:** Draft / Specification  
**Milestone:** v0.1.3  
**Target:** CIF Ingester + Supercell Builder + Topological Validation

---

## 1. Objective

MolSAIC must support the generation of topologically correct supercells for periodic crystals and MOFs (e.g., CALF-20), starting from a CIF file. This requires expanding symmetry to a P1 unit cell, handling partial occupancy, and materializing bonds across periodic boundaries during replication.

---

## 2. Technical Specifications

### 2.1 USM Data Model (Bonds Representation A)
Bonds in USM must explicitly store periodic image shifts to preserve topology:
- `a1, a2`: Explicit atom IDs (must exist in the atoms table).
- `ix, iy, iz`: Integer shifts representing the image of `a2` relative to `a1`.
- **Invariant**: All bonds must be undirected and canonicalized such that `a1 < a2`. If `a1 == a2` (self-bond to image), then `(ix, iy, iz)` must be lexicographically positive.

### 2.2 CIF Ingester Enhancements (`src/usm/io/cif.py`)
The `load_cif` function will be upgraded to produce a "simulation-ready" P1 unit cell:
1.  **Symmetry Expansion**: Parse `_space_group_symop_operation_xyz` and apply them to all `_atom_site_*` entries to generate the full unit cell.
2.  **Disorder Policy (Rule D1)**: Drop atoms with `_atom_site_occupancy < 1.0` unless they are explicitly tagged as framework.
3.  **Bond Perception (Heuristic or CIF-based)**:
    - Prefer parsing `_geom_bond_*` and resolving symmetry codes (e.g., `3_556` -> operator 3, shift (0,0,1)).
    - Fallback: Geometric perception using Minimum Image Convention (MIC) and element-specific cutoffs.

### 2.3 Supercell Builder (`src/usm/ops/replicate.py`)
The `replicate_supercell` operator will implement the following algorithm:
1.  **Atom Replication**:
    - For each unit cell atom `u` and each tile `(tx, ty, tz)`:
    - `f_super = (f_unit + [tx, ty, tz]) / [nx, ny, nz]`
    - Maintain mapping: `map[(u_id, tx, ty, tz)] -> super_id`.
2.  **Bond Materialization (Policy P1: Closed Supercell)**:
    - For each unit bond `(i_u, j_u, dx, dy, dz)` and each tile `(tx, ty, tz)`:
    - `i_s = map[(i_u, tx, ty, tz)]`
    - `target_tile = (tx+dx, ty+dy, tz+dz)`
    - `j_s = map[(j_u, target_tile % n)]`
    - `new_shift = target_tile // n`
    - Add bond `(i_s, j_s, *new_shift)`.
3.  **Deduplication**: Canonicalize keys `(min(i,j), max(i,j), ...)` and drop duplicates.

### 2.4 Topological Validation (`src/usm/ops/topology.py`)
A new `validate_supercell` operator will provide a machine-readable JSON report:
- **Count Sanity**: `N_atoms_super == N_atoms_unit * volume_ratio`.
- **Bond Lengths**: Statistical summary and outlier detection (MIC distances).
- **Graph Connectedness**: Number of connected components (framework should be 1).
- **Metal Coordination**: Coordination number histograms (e.g., Zn in CALF-20 should be consistent).

---

## 3. Implementation Plan (Todo)

### Phase 1: Core & Ingester
1. [ ] Update `BONDS_DTYPES` in `src/usm/core/model.py` for explicit `ix, iy, iz`.
2. [ ] Implement symmetry expansion in `src/usm/io/cif.py`.
3. [ ] Implement Rule D1 (occupancy) in `src/usm/io/cif.py`.

### Phase 2: Supercell & Perception
4. [ ] Implement `perceive_periodic_bonds` in `src/usm/ops/topology.py` (MIC based).
5. [ ] Upgrade `replicate_supercell` in `src/usm/ops/replicate.py` with mapping-based materialization.

### Phase 3: Validation & NIST
6. [ ] Implement `validate_supercell` in `src/usm/ops/topology.py`.
7. [ ] Update NIST workspace to build 2x2x2 CALF-20 supercell from CIF.
8. [ ] Generate `v0.1.3_report.md`.

---

## 4. Acceptance Criteria
- **CALF-20 2x2x2**: Built from `2084733.cif` has correct atom count and 1 connected component.
- **Determinism**: Supercell artifacts are byte-identical across runs.
- **Round-trip**: Export to MDF and re-import preserves all bonds and coord logic.
