# Triclinic MXene Supercell Support — Master Plan

## Context

We have a new MXene unit cell (`EXPT_TRI_UnitCell_100OH.{car,mdf}`) with hexagonal symmetry (a=b=6.101 A, c=19.86 A, gamma=120deg) and a new force field (`cvff_iff_MXENE_REV_v3_DIMFIX.frc`). The goal is to run it through the same bilayer+hydration pipeline as the existing orthogonal MXene workspaces: **unit cell -> 5nm supercell -> bilayer -> hydrate -> LAMMPS .data**.

Three blockers must be fixed in USM/MolSAIC before this pipeline can work:

1. **MDF periodic bond tokens (`%abc#d`) are discarded on parse** — supercell replication produces wrong bond topology
2. **LAMMPS normalization is orthogonal-only** — triclinic tilt factors lost
3. **New workspace pipeline** — wire everything together for the triclinic cell

---

## Phase 1: MDF Periodic Bond Parse & Write (Critical Path)

**Problem**: When `_mdf_parser.py:parse_target_token()` encounters a token like `XXXX_19:C%0-10#1`, it strips everything after `%` (line 189-190), discarding the periodic image shift. The bonds table `ix,iy,iz` columns (defined in `model.py`) are never populated and default to 0. This means `replicate_supercell()` (which correctly handles nonzero shifts) never knows about periodic bonds.

**Observed shift tokens** in the real MXene MDF (6 unique patterns):
- `%0-10#1` -> (0, -1, 0)
- `%010#1` -> (0, 1, 0)
- `%100#1` -> (1, 0, 0)
- `%-100#1` -> (-1, 0, 0)
- `%110#1` -> (1, 1, 0)
- `%-1-10#1` -> (-1, -1, 0)

### 1A: Parse `%abc#d` into (ix, iy, iz)

**File**: `src/usm/io/_mdf_parser.py` (247 -> ~310 lines)

Changes to `parse_target_token()` (line 177-201):
1. Before stripping `%`, extract the suffix text between `%` and `#` (or end of base)
2. New helper `_parse_periodic_shift(suffix: str) -> tuple[int, int, int]`:
   - Walk character-by-character: `-` means next char is negated digit, otherwise positive digit
   - Return `(ia, ib, ic)`
3. Return value becomes 8-tuple: `(label, idx, name, order_val, order_raw, ix, iy, iz)`

Changes to `build_bonds_from_connections()` (line 155-248):
4. Unpack new `ix, iy, iz` from `parse_target_token`
5. Populate `"ix": ix, "iy": iy, "iz": iz` in each bond dict (lines 230-241)
6. Change dedup key from `(a1, a2)` to `(a1, a2, ix, iy, iz)` — same atom pair can have distinct periodic bonds
7. When swapping `a1 > a2` (line 224-225), negate `ix, iy, iz`

### 1B: Write `%abc#d` from (ix, iy, iz)

**File**: `src/usm/io/mdf.py` (296 -> ~350 lines)

Changes to adjacency list construction (lines 228-238):
1. Include `(ix, iy, iz)` per neighbor: `adj_list[a1].append((a2, order, ix, iy, iz))`
2. For reverse direction `a2->a1`: negate shifts `(-ix, -iy, -iz)`

Changes to `_compose_connections_for_atom()` (lines 111-149):
3. Accept updated adj_list type with shift tuples
4. New helper `_encode_periodic_shift(ix, iy, iz) -> str`: encode each component as signed single digit, return `%abc#1` suffix
5. When `(ix, iy, iz) != (0, 0, 0)`, append the suffix to the connection token

**Default mode** (`write_normalized_connections=False`): Uses preserved `connections_raw` — no change needed. This path already works for non-replicated structures.

### 1C: Tests

**New file**: `tests/unit/test_mdf_periodic_bonds.py` (~180 lines)

| Test | What it validates |
|------|------------------|
| `test_parse_periodic_shift_all_patterns` | All 6 observed tokens + edge cases (000, multi-digit) |
| `test_encode_periodic_shift_roundtrip` | parse(encode(ix,iy,iz)) == (ix,iy,iz) for all combos in [-1,0,1]^3 |
| `test_load_mdf_populates_ix_iy_iz` | Load real MXene MDF, assert bonds with nonzero shifts exist |
| `test_load_mdf_periodic_bond_count` | Count of periodic bonds matches grep of `%` tokens |
| `test_mdf_roundtrip_normalized_connections` | Load -> save(write_normalized=True) -> reload, compare (a1,a2,ix,iy,iz) sets |
| `test_replicate_with_periodic_bonds_2x2x1` | Load MXene MDF+CAR, compose, replicate 2x2, verify bond count = 4x original, all shifts zero for interior |
| `test_replicate_then_save_mdf_roundtrip` | Full chain: load -> compose -> replicate 2x2 -> save MDF -> reload -> compare bond topology |

**Regression**: Run existing `test_mdf_formal_charge_tokens.py`, `test_pbc_replication.py`, `test_replicate_general.py` — must all still pass.

**Fixture**: Copy `EXPT_TRI_UnitCell_100OH.{car,mdf}` to `tests/fixtures/mxene_tri_unitcell/`

### 1D: Validation Criteria

- [ ] `pytest tests/unit/test_mdf_periodic_bonds.py -v` — all pass
- [ ] `pytest src/usm/tests/ -v` — no regressions
- [ ] `pytest tests/unit/ -v` — no regressions
- [ ] Manual: Load MXene MDF, inspect bonds DataFrame, confirm nonzero ix/iy/iz rows
- [ ] Manual: replicate 9x10x1, save MDF, reload, verify bond count = 90 * original internal bonds

---

## Phase 2: Triclinic LAMMPS Normalization

**Problem**: `_lmp_normalize.py:normalize_data_file()` only handles orthogonal box headers (`xlo xhi`). For gamma=120deg, LAMMPS requires tilt factors (`xy xz yz`) in the header.

### 2A: Parse cell angles from CAR

**File**: `src/external/_lmp_normalize.py` (191 -> ~280 lines)

1. Extend `parse_abc_from_car()` -> `parse_cell_from_car()` returning `(a, b, c, alpha, beta, gamma)` — the regex on line 21 already captures all 6 numbers, just extract indices 3-5
2. New helper `compute_lammps_tilt(a, b, c, alpha, beta, gamma) -> dict` with keys `lx, ly, lz, xy, xz, yz`:
   - `lx = a`
   - `xy = b * cos(gamma)`
   - `ly = sqrt(b^2 - xy^2)`
   - `xz = c * cos(beta)`
   - `yz = (b*c*cos(alpha) - xy*xz) / ly`
   - `lz = sqrt(c^2 - xz^2 - yz^2)`
3. New helper `is_triclinic(alpha, beta, gamma, tol=0.01) -> bool`
4. In `normalize_data_file()`:
   - New param `cell_angles: tuple[float,float,float] | None = None`
   - If triclinic: compute tilt factors, write LAMMPS triclinic header format (`0.0 lx xy xlo xhi xy` etc.)
   - Parse existing triclinic headers (3-number lines before `xlo xhi`) so msi2lmp output that already has tilt is handled
   - When `do_xy=True` with triclinic: use `lx` and `ly` instead of `a` and `b` for box extents

### 2B: Wire through msi2lmp.py

**File**: `src/external/msi2lmp.py` (~394 -> ~420 lines)

1. In post-processing section, call `parse_cell_from_car()` instead of `parse_abc_from_car()`
2. Pass `cell_angles=(alpha, beta, gamma)` to `normalize_data_file()`
3. No other changes needed — msi2lmp binary receives the CAR/MDF directly

### 2C: Tests

**New file**: `tests/unit/test_lmp_triclinic.py` (~120 lines)

| Test | What it validates |
|------|------------------|
| `test_compute_tilt_orthogonal` | alpha=beta=gamma=90 -> xy=xz=yz=0 |
| `test_compute_tilt_hexagonal` | gamma=120 -> xy = -b/2, xz=0, yz=0 |
| `test_compute_tilt_general_triclinic` | Known triclinic cell against hand-computed values |
| `test_parse_cell_from_car_all_angles` | Parse CAR with gamma=120, verify all 6 params |
| `test_normalize_writes_triclinic_header` | Mock LAMMPS file + hexagonal angles -> output has `xy xz yz` line |
| `test_normalize_orthogonal_unchanged` | gamma=90 -> no tilt line added (regression) |

### 2D: Validation Criteria

- [ ] `pytest tests/unit/test_lmp_triclinic.py -v` — all pass
- [ ] `pytest tests/unit/test_msi2lmp_argv_selection.py -v` — no regressions
- [ ] Manual: Run msi2lmp on the triclinic MXene supercell, inspect .data file header for correct tilt factors

---

## Phase 3: MXene Triclinic Workspace

**Depends on**: Phases 1 and 2

### 3A: Fixture Setup

**New dir**: `workspaces/mxenes/triclinic/mxene_tri_supercell_v1/`

- Copy `EXPT_TRI_UnitCell_100OH.{car,mdf}` to `inputs/`
- Copy `cvff_iff_MXENE_REV_v3_DIMFIX.frc` to `inputs/`
- Create `config.json`:
  ```json
  {
    "na": 9, "nb": 10, "nc": 1,
    "water_counts": [0, 50, 100, 155, 206],
    "frc_file": "inputs/cvff_iff_MXENE_REV_v3_DIMFIX.frc",
    "packmol_seed": 12345,
    "executables": { ... }
  }
  ```

### 3B: Workspace `run.py` Pipeline

**New file**: `workspaces/mxenes/triclinic/mxene_tri_supercell_v1/run.py` (~250 lines)

**Step 1** — Load & Compose:
- `load_car()` + `load_mdf()` -> `compose_on_keys()` (joins coords + topology with periodic bonds)

**Step 2** — Replicate supercell:
- `replicate_supercell(usm, na=9, nb=10, nc=1)` -> 6480 atoms
- Cell becomes: a=54.91, b=61.01, c=19.86, gamma=120

**Step 3** — Build bilayer:
- Unit cell already has 2 slabs (z=-4.53 to 4.53 and z=5.40 to 14.46)
- Shift top slab (z > ~5.0) upward by ~8 A to create water gap
- Increase c to ~48 A (slab + gap + slab + vacuum)

**Step 4** — Save dry supercell as CAR/MDF:
- `save_car(usm, ..., preserve_headers=False)` (new cell params)
- `save_mdf(usm, ..., write_normalized_connections=True)` (fresh bond tokens with `%abc#1`)

**Step 5** — msi2namd: Convert supercell + water template to PDB/PSF

**Step 6** — Packmol: For each water count, pack water in the interlayer gap
- Triclinic box: use inscribed rectangle of parallelogram for `inside box` constraint
- Or compute the actual Cartesian bounds from lattice vectors

**Step 7** — pm2mdfcar: Compose hydrated PDB + templates -> final CAR/MDF

**Step 8** — msi2lmp: Convert to LAMMPS with triclinic normalization

**Step 9** — Write summary.json manifest

### 3C: Integration Tests

**New file**: `tests/integration/test_triclinic_mxene_supercell.py` (~100 lines)

| Test | What it validates |
|------|------------------|
| `test_load_compose_replicate_roundtrip` | Load unit cell -> compose -> replicate 2x2x1 -> save CAR/MDF -> reload -> verify atom count, bond count, cell angles |
| `test_supercell_bond_topology_complete` | After 9x10x1 replication, verify no bonds with nonzero ix/iy/iz (all periodic bonds materialized in this large supercell... except the boundary ones) |
| `test_bilayer_z_separation` | After shifting top slab, verify min gap between slabs > 5 A |
| `test_msi2lmp_triclinic_output` | Run msi2lmp on supercell, verify LAMMPS file has correct tilt factors and atom count |

---

## Phase 4: Final Validation & Documentation

### 4A: End-to-End Smoke Test

Run the full workspace pipeline on the actual MXene unit cell:
1. 9x10x1 supercell (6480 atoms)
2. Bilayer with gap
3. Dry structure -> msi2lmp -> LAMMPS .data
4. Verify LAMMPS data file can be read by LAMMPS (`lmp -in test.in` with just `read_data`)
5. Hydrated structures for 5 water counts

### 4B: Documentation

**New file**: `docs/plans/TRICLINIC_MXENE_SUPERCELL_PLAN.md` — copy of this plan into the MolSAIC repo for project tracking

**Update**: `src/usm/docs/LIMITS.md` — document that MDF periodic bond tokens are now fully supported

### 4C: Regression Suite

Full test suite must pass:
```bash
pytest tests/ src/usm/tests/ -v --tb=short
```

---

## Dependency Graph

```
Phase 1A (parse %abc) ──┐
                        ├── Phase 1C (tests) ──┐
Phase 1B (write %abc) ──┘                      │
                                                ├── Phase 3 (workspace) ── Phase 4
Phase 2A (tilt factors) ──┐                     │
                          ├── Phase 2C (tests) ─┘
Phase 2B (wire msi2lmp) ──┘
```

**Phases 1 and 2 are independent** and can be worked in parallel. Phase 3 depends on both. Phase 4 depends on Phase 3.

---

## Files Modified (Summary)

| File | Phase | Change | Lines |
|------|-------|--------|-------|
| `src/usm/io/_mdf_parser.py` | 1A | Parse `%abc#d` -> ix,iy,iz | 247 -> ~310 |
| `src/usm/io/mdf.py` | 1B | Write `%abc#d` from ix,iy,iz | 296 -> ~350 |
| `src/external/_lmp_normalize.py` | 2A | Triclinic tilt factors | 191 -> ~280 |
| `src/external/msi2lmp.py` | 2B | Pass cell angles | 394 -> ~420 |

## Files Created (Summary)

| File | Phase | Purpose |
|------|-------|---------|
| `tests/unit/test_mdf_periodic_bonds.py` | 1C | MDF periodic bond tests |
| `tests/unit/test_lmp_triclinic.py` | 2C | LAMMPS triclinic tests |
| `tests/fixtures/mxene_tri_unitcell/*.{car,mdf}` | 1C | Test fixtures |
| `tests/integration/test_triclinic_mxene_supercell.py` | 3C | Integration tests |
| `workspaces/mxenes/triclinic/mxene_tri_supercell_v1/` | 3A-B | New workspace |
| `docs/plans/TRICLINIC_MXENE_SUPERCELL_PLAN.md` | 4B | Plan doc in repo |

## Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| msi2lmp binary can't handle triclinic CAR/MDF | High | Empirical test in Phase 3; fallback: rotate to LAMMPS convention before feeding |
| `%abc` has multi-digit shifts in other files | Low | Parser handles any digit; warn if abs > 1 |
| Atom name too long after replication suffix `_T_i_j_k` | Medium | Verify MDF column width (18 chars); truncate if needed |
| Packmol `inside box` doesn't respect skewed cell | Medium | Use inscribed rectangle; or rotate to orthogonal for packing step |
| Bond dedup key change affects non-periodic files | Low | Extra zeros in key are harmless; verify with regression tests |
