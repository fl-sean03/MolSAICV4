# `msi2lmp.exe` diagnostics: minimal flags + deterministic repro (CALF-20)

Scope
- External binary: `/home/sf2/LabWork/software/msi2lmp.exe`
- Target workspace: `workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1`
- Primary failure modes for CALF-20 with a CVFF-labeled **nonbond-only** `.frc`:
  1) deterministic **error**: “forcefield name and class appear to be inconsistent”
  2) deterministic **stall/hang** after “Reading forcefield file” / parameter resolution

This document provides:
1) Minimal flag sets (“production” vs “debug”) that are stable and wrapper-compatible.
2) Deterministic manual reproduction that matches wrapper staging (CWD + `../frc_files`).
3) A hardened command template (`timeout` + `stdbuf` + `< /dev/null`) to prevent indefinite hangs.

---

## 1) Wrapper-equivalent staging (must match)

The deterministic wrapper [`external.msi2lmp.run()`](src/external/msi2lmp.py:203) uses:

- Working directory (CWD):
  - `workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/outputs/msi2lmp_run`
- Forcefield staging directory:
  - `workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/outputs/frc_files`
- CAR/MDF staging in the work dir:
  - `./CALF20.car` and `./CALF20.mdf`

So for manual reproduction, you must run from:

```bash
cd workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/outputs/msi2lmp_run
```

And refer to `.frc` as:

```bash
../frc_files/<something>.frc
```

---

## 2) Minimal flag sets

### 2.1 Production mode (minimal verbosity, consistent behavior)

Use this when you want the smallest argv surface area.

**Modern / CVFF-labeled `.frc`** (recommended when your `.frc` has `#define cvff` and section labels like `#atom_types\tcvff`):

```bash
/home/sf2/LabWork/software/msi2lmp.exe CALF20 -class I -frc ../frc_files/<ff>.frc
```

Optional (only if you need parity with “do not recenter” behavior): add `-nocenter`.

**Legacy / non-labeled `.frc`** (when `.frc` does NOT look CVFF-labeled):

```bash
/home/sf2/LabWork/software/msi2lmp.exe CALF20 -f <ff_stem_without_extension>
```

The wrapper’s auto-selection logic is implemented in [`_build_msi2lmp_argv()`](src/external/msi2lmp.py:77) using [`_frc_looks_cvff_labeled()`](src/external/msi2lmp.py:49).

### 2.2 Debug mode (prints topology + failure point)

Use this when diagnosing where resolution fails or when you need explicit topology inventories.

Recommended “max useful signal” flags:
- `-print 2` (observed to print atoms/types and full bond/angle/dihedral/oop listings)
- `-ignore` (turns the “name/class inconsistent” condition into a warning and proceeds further)

```bash
/home/sf2/LabWork/software/msi2lmp.exe CALF20 -ignore -print 2 -class I -frc ../frc_files/<ff>.frc
```

Observed output example for `-print 2` includes the topology counts (from captured runs):

```
Number of bonds, types =      14   6
Number of angles, types =      28  11
Number of dihedrals, types =      54  16
Number of out-of-planes, types =       5   3
```

---

## 3) Deterministic logging and hang-proofing template

`msi2lmp.exe` output can appear “missing” due to buffering (and a true hang will never exit).

Use this template to:
- force line buffering (`stdbuf -oL -eL`)
- prevent indefinite hangs (`timeout`)
- avoid accidental stdin reads (`< /dev/null`)
- capture stdout/stderr deterministically to files

```bash
timeout --preserve-status --signal=TERM --kill-after=1s 30s \
  stdbuf -oL -eL /home/sf2/LabWork/software/msi2lmp.exe CALF20 <ARGS...> \
  </dev/null \
  >stdout.txt \
  2>stderr.txt

echo "exit_code=$?"
```

Notes
- With `timeout --preserve-status --signal=TERM`, a hang typically yields:
  - `143` (= 128 + SIGTERM(15))
- If you omit `--preserve-status` and let `timeout` use its default behavior, a hang typically yields:
  - `124`
- Exit code `0` means success.
- Any other nonzero code indicates `msi2lmp.exe` failed fast (e.g., name/class inconsistent).

---

## 3.1) CALF-20 stall fix: guarantee coverage (generate a CVFF-labeled, bonded `.frc`)

### Symptom
Some `msi2lmp.exe` builds stall after the log line `Reading forcefield file` when given a *small / minimal* CVFF-labeled `.frc`, even if the expected section headers exist.

### Resolution strategy
For CALF-20, the robust approach is:
1) generate a CVFF-labeled `.frc` that includes both nonbonded and minimal bonded coverage
2) ensure the file contains the *first and only* occurrence of each relevant section header:
   - `#equivalence\tcvff`
   - `#atom_types\tcvff`
   - `#quadratic_bond\tcvff`
   - `#morse_bond\tcvff`
   - `#quadratic_angle\tcvff`
   - `#torsion_1\tcvff`
   - `#out_of_plane\tcvff`
   - `#bond_increments\tcvff`
   - `#nonbond(12-6)\tcvff`

Rationale:
- BIOSYM/Insight-era parsers may only honor the first occurrence of a repeated section header.
- Emitting each section exactly once avoids cases where appended “override” sections are ignored.

### Deterministic placeholders
Bonded rows are generated for **every TermSet key** and are filled with deterministic placeholder values when no real parameters are available.
This ensures tool completion/determinism, not physical accuracy.

Implementation: [`build_frc_cvff_minimal_bonded()`](src/upm/src/upm/build/frc_from_scratch.py:190)

---

## 4) Reproduction playbook (CALF-20)

### Preconditions

From repo root, ensure the NIST workspace outputs exist (or run the workspace once):

```bash
python workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/run.py --config workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/config.json
```

Manual reproduction uses the staged artifacts in:
- `workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/outputs/msi2lmp_run/`
- `workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/outputs/frc_files/`

### 4.1 Repro A — “forcefield name/class inconsistent” error

This reproduces the deterministic error for a non-labeled `.frc`.

```bash
cd workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/outputs/msi2lmp_run

timeout --preserve-status 10s \
  stdbuf -oL -eL /home/sf2/LabWork/software/msi2lmp.exe CALF20 \
    -class I -frc ../frc_files/ff_nonbond_only.frc \
  </dev/null \
  >repro_inconsistent_stdout.txt \
  2>repro_inconsistent_stderr.txt

echo "exit_code=$?"
sed -n '1,80p' repro_inconsistent_stderr.txt
```

Expected stderr includes:

```
Error  - forcefield name and class appear to be inconsistent
```

Note: the warning form also exists when `-ignore` is supplied:

```
WARNING- forcefield name and class appear to be inconsistent
```

### 4.2 Repro B — deterministic stall after reading forcefield / resolving parameters

This reproduces the deterministic hang/stall for a CVFF-labeled but still **nonbond-only** `.frc`.

```bash
cd workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/outputs/msi2lmp_run

timeout --preserve-status --signal=TERM --kill-after=1s 30s \
  stdbuf -oL -eL /home/sf2/LabWork/software/msi2lmp.exe CALF20 \
    -ignore -print 2 -class I -frc ../frc_files/ff_nonbond_only_cvff.frc \
  </dev/null \
  >repro_hang_stdout.txt \
  2>repro_hang_stderr.txt

echo "exit_code=$?"  # expected 124
tail -n +1 repro_hang_stdout.txt | sed -n '1,60p'
tail -n +1 repro_hang_stderr.txt | sed -n '1,60p'
```

Expected behavior
- `exit_code=143` (killed by SIGTERM from `timeout --preserve-status --signal=TERM ...`)
- stdout ends at:
  - `Reading forcefield file`
- stderr contains printed topology counts (from `-print 2`) and the warning:
  - `WARNING inconsistent # of connects on atom 10 type C_MOF`

Captured examples of this pattern exist in the workspace outputs:
- `.../outputs/msi2lmp_run/timed30_stdout.txt` (ends at “Reading forcefield file”)
- `.../outputs/msi2lmp_run/timed30_stderr.txt` (contains full `-print 2` listing)

---

## 5) Wrapper configuration (no code changes required)

The workspace runner [`main()`](workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/run.py:166) exposes wrapper controls via `config.json` params:

- `msi2lmp_forcefield_class` → pass `forcefield_class` (e.g., `"I"`)
- `msi2lmp_use_f_flag` → force legacy mode (`true`) or force modern mode (`false`)
- `msi2lmp_ignore` → pass `-ignore`
- `msi2lmp_print_level` → pass `-print N`

Example debug config snippet:

```json
{
  "params": {
    "timeout_s": 30,
    "msi2lmp_forcefield_class": "I",
    "msi2lmp_use_f_flag": false,
    "msi2lmp_ignore": true,
    "msi2lmp_print_level": 2
  }
}
```

---

## Appendix A — `msi2lmp.exe -h` output (to be captured)

This `msi2lmp.exe` build (v3.9.6 / 11 Sep 2014) does **not** treat `-h` as help.

Instead:
- Running with **no args** prints a one-line usage string.
- Running with `-h` treats `-h` as the `<rootname>` and tries to open `-h.car`.

### A.1 Usage output (invoked with no args)

Command:

```bash
/home/sf2/LabWork/software/msi2lmp.exe
```

Output:

```
usage: /home/sf2/LabWork/software/msi2lmp.exe <rootname> [-class <I|1|II|2>] [-frc <path to frc file>] [-print #] [-ignore] [-nocenter] [-oldstyle]
```

Supported flags implied by this usage string:
- `-class <I|1|II|2>`
- `-frc <path>`
- `-print <N>`
- `-ignore`
- `-nocenter`
- `-oldstyle`

### A.2 `-h` output (NOT help)

Command:

```bash
/home/sf2/LabWork/software/msi2lmp.exe -h
```

Output:

```

Running msi2lmp v3.9.6 / 11 Sep 2014

 Forcefield: Class I
 Forcefield file name: ../frc_files/cvff.frc
 Output is recentered around geometrical center
 Output contains style flag hints
 System translated by: 0 0 0
 Reading car file: -h.car
Cannot open -h.car
```

Implication: for deterministic docs and wrappers, treat "help/usage" as:

```bash
/home/sf2/LabWork/software/msi2lmp.exe
```

---

## Appendix B — Skeleton Builder (Minimal CVFF .frc Generation)

### B.1 Background

The CVFF base minimization thrust (see [`thrust_log_cvff_base_minimization.md`](thrust_log_cvff_base_minimization.md)) achieved a **97.8% reduction** in .frc file size (5571 → 120 lines) while maintaining msi2lmp.exe compatibility.

### B.2 Available Builders

| Function | Description | Output Lines |
|----------|-------------|--------------|
| `build_frc_cvff_with_embedded_base()` | Full CVFF base | ~5595 |
| `build_frc_cvff_with_minimal_base()` | M16 pruned base (81% reduction) | ~1081 |
| `build_frc_cvff_with_pruned_base(preset="M29")` | Ultimate minimum (97.8% reduction) | 120 |
| `build_frc_cvff_from_skeleton()` | Skeleton template (nonbond-only) | 120 |
| `build_frc_cvff_from_skeleton(include_bonded=True)` | Skeleton with bonded entries | ~332 |

### B.3 Skeleton Usage Example

```python
from upm.build.frc_from_scratch import build_frc_cvff_from_skeleton

# Load termset and parameterset from workspace
import json
with open("workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/outputs/termset.json") as f:
    termset = json.load(f)
with open("workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/outputs/parameterset.json") as f:
    parameterset = json.load(f)

# Generate skeleton .frc (120 lines, nonbond-only)
content = build_frc_cvff_from_skeleton(
    termset, parameterset,
    out_path="cvff_skeleton.frc"
)

# Or with bonded entries populated (~332 lines)
content = build_frc_cvff_from_skeleton(
    termset, parameterset,
    out_path="cvff_skeleton_bonded.frc",
    include_bonded=True
)
```

### B.4 msi2lmp.exe Invocation with Skeleton

The skeleton .frc requires `-ignore` flag because it uses placeholder parameters:

```bash
cd workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/outputs/msi2lmp_run

timeout --preserve-status 30s \
  /home/sf2/LabWork/software/msi2lmp.exe CALF20 \
    -class I -frc ../frc_files/cvff_skeleton.frc -ignore \
  </dev/null \
  >skeleton_stdout.txt \
  2>skeleton_stderr.txt

echo "exit_code=$?"  # expected 0
```

### B.5 Key Findings from Minimization Thrust

| Element | Required? | Notes |
|---------|-----------|-------|
| `!BIOSYM forcefield 1` header | **Yes** | Parser initialization |
| At least 1 `#define` block | **Yes** | Macro structure |
| `!` column headers | **Yes** | Field position detection (removing causes stall) |
| Section headers | **Yes** | Parser section detection |
| `#version` history | No | Cosmetic only |
| `>` description comments | No | Safely removable |
| 3 of 4 `#define` blocks | No | Only `cvff` block needed |
| Base entries in sections | No | Custom entries only needed |
| Cross-term sections | No | Not needed for `-class I` |
| cvff_auto sections | No | Redundant with `-class I` |
