# Context reset / handoff: NIST CALF-20 `msi2lmp.exe` stall (from-scratch CVFF `.frc`)

Last updated: 2025-12-20

## 0) TL;DR

We reproduced a deterministic **stall/hang** in the real external binary `msi2lmp.exe` (v3.9.6 / 11 Sep 2014) when using the workspace-generated from-scratch CVFF `.frc` (`ff_cvff_min_bonded.frc`).

We proved the hang is **not** caused by stdin blocking (wrapper now forces `stdin=DEVNULL`) and **not** just stdout buffering (using `timeout + stdbuf` shows the tool prints up to `Reading forcefield file` then stops making progress).

We implemented **wrapper hardening** (stdin + deterministic timeout envelope) and began **builder iteration** (macro selection and equivalence layout changes), but the stall still persists for the from-scratch `.frc` at the time of this handoff.

Important datapoint: running the same CALF20 staged CAR/MDF with a large CVFF asset forcefield (`workspaces/forcefields/cvff_Base_MXenes.frc`) succeeds quickly and writes `CALF20.data`. So the tool + inputs can succeed; the issue is in our minimal from-scratch `.frc` semantics/compatibility.

## 1) Goals (Subtask 4 success criteria)

1. Identify what `msi2lmp.exe` is waiting on after `Reading forcefield file`.
2. Update from-scratch builder [`build_frc_cvff_minimal_bonded()`](src/upm/src/upm/build/frc_from_scratch.py:153) to include the required additional sections/rows **without reading any `.frc` from disk**.
3. Prove real-tool run completes and writes non-empty `CALF20.data` under workspace outputs.
4. Preserve determinism: two clean runs match sha256 for `ff_cvff_min_bonded.frc` and `CALF20.data` (and canonical JSON artifacts).

## 2) Key files / entry points

- Workspace runner: [`workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/run.py`](workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/run.py:1)
- Guarded runner: [`workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/tools/run_real_tool_guarded.py`](workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/tools/run_real_tool_guarded.py:1)
- External wrapper: [`external.msi2lmp.run()`](src/external/msi2lmp.py:203)
- From-scratch builder: [`build_frc_cvff_minimal_bonded()`](src/upm/src/upm/build/frc_from_scratch.py:153)
- Diagnostics recipe: [`docs/development/thrust-logs/msi2lmp_diagnostics_repro.md`](docs/development/thrust-logs/msi2lmp_diagnostics_repro.md:1)
- Standalone usage notes: [`docs/reference/msi2lmp_standalone_usage.md`](docs/reference/msi2lmp_standalone_usage.md:1)
- Contract addendum: [`docs/development/guides/DevGuide_CALF20_msi2lmp_frc_contract.md`](docs/development/guides/DevGuide_CALF20_msi2lmp_frc_contract.md:1)

## 3) What we reproduced (ground truth)

### 3.1 The stall signature with the from-scratch `.frc`

Using the doc’s hang-proof template (critical: output buffering exists):

```bash
cd workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/outputs/msi2lmp_run

timeout --preserve-status --signal=TERM --kill-after=1s 40s \
  stdbuf -oL -eL /home/sf2/LabWork/software/msi2lmp.exe CALF20 \
    -ignore -print 2 -class I -frc ../frc_files/ff_cvff_min_bonded.frc \
  </dev/null \
  >manual_stdout.txt \
  2>manual_stderr.txt

echo exit_code=$?
```

Observed:
- `exit_code=143` (killed by SIGTERM from timeout)
- stdout ends at `Reading forcefield file`
- stderr contains the connect warning and topology counts:
  - `WARNING inconsistent # of connects on atom 10 type C_MOF`
  - `Number of bonds, types = 14 6`, etc.

This matches the general hang description in [`msi2lmp_diagnostics_repro.md`](docs/development/thrust-logs/msi2lmp_diagnostics_repro.md:192), except that it now happens even with the “bonded minimal” file.

### 3.2 “stdin read hang” was ruled out

We changed the wrapper to force `stdin=subprocess.DEVNULL` in [`_run()`](src/external/msi2lmp.py:140). The hang persisted.

Conclusion: the stall is not interactive input; it’s internal tool work / resolution loop.

### 3.3 A known-good forcefield completes for CALF20

Manual run with the large CVFF asset `workspaces/forcefields/cvff_Base_MXenes.frc` completes and writes `CALF20.data`.

This is a crucial control: the tool can complete for this structure if the `.frc` semantics match its expectations.

## 4) Code changes made (so far)

### 4.1 Wrapper hardening (DONE)

File: [`src/external/msi2lmp.py`](src/external/msi2lmp.py:1)

Changes:
- In [`_run()`](src/external/msi2lmp.py:140), pass `stdin=subprocess.DEVNULL` so the tool cannot block on input.
- In [`run()`](src/external/msi2lmp.py:203), catch `subprocess.TimeoutExpired` and persist deterministic artifacts:
  - `stdout.txt`, `stderr.txt`, `result.json`
  - `status: "timeout"`
- Also persist a deterministic `result.json` on `CalledProcessError` (nonzero exit).

Note: wrapper capture of stdout/stderr is still limited because the external tool buffers and only flushes on exit; manual `stdbuf` runs are still required for “where it stops” evidence.

### 4.2 Builder changes attempted (IN PROGRESS / UNRESOLVED)

File: [`src/upm/src/upm/build/frc_from_scratch.py`](src/upm/src/upm/build/frc_from_scratch.py:1)

Builder defaults changed:
- `cvff_define` default changed from `cvff_nocross_nomorse` → `cvff` in [`build_frc_cvff_minimal_bonded()`](src/upm/src/upm/build/frc_from_scratch.py:153).
  - Rationale: CVFF assets and the diagnostics guide assume `#define cvff`.

Other modifications attempted:
- Equivalence row layout was tweaked trying to match the CVFF asset format.
- Added wildcard torsion/OOP rows (`* * * *`) as a potential escape hatch.

Status: none of these have yet removed the stall for the generated `ff_cvff_min_bonded.frc`.

### 4.3 Tests updated

File: [`src/upm/tests/test_build_frc_from_scratch_cvff_minimal_bonded.py`](src/upm/tests/test_build_frc_from_scratch_cvff_minimal_bonded.py:1)

- Updated expected macro string from `#define cvff_nocross_nomorse` to `#define cvff`.

Pytest note:
- The repo’s default `python` is miniconda Python 3.13, which segfaults at pytest startup in this environment.
- Running tests via `/usr/bin/python3` (Python 3.10) works.

## 5) What worked vs what didn’t

### Worked

- Using `timeout + stdbuf + </dev/null` as described in [`msi2lmp_diagnostics_repro.md`](docs/development/thrust-logs/msi2lmp_diagnostics_repro.md:87) reliably shows where the tool stops.
- Using the large CVFF `.frc` (`cvff_Base_MXenes.frc`) for the same CALF20 system completes and writes output.
- Wrapper hardening successfully prevents indefinite hangs from stalling the workspace forever and provides deterministic `result.json` on timeouts.

### Didn’t work

- Simply adding bonded sections (we already have the documented minimal set) did not fix the stall.
- Changing only `#define` macro to `cvff` did not fix the stall.
- Adjusting equivalence row token counts and adding wildcard torsion/OOP rows did not fix the stall (as of the last attempt).

## 6) Current obstacles / hypotheses

### 6.1 Output buffering can hide progress

Wrapper capture will typically be empty unless the process exits. Use manual `stdbuf` recipes for diagnosis.

### 6.2 Most likely root cause: missing *auto equivalence* / *wildcard matching* machinery

The successful big CVFF assets include sections such as:
- `#auto_equivalence\tcvff_auto` (seen in [`cvff_Base_MXenes.frc`](workspaces/forcefields/cvff_Base_MXenes.frc:573))

The from-scratch `.frc` currently emits only `#equivalence\tcvff`, not `#auto_equivalence`. The external tool prints “Trying Atom Equivalences if needed” when using the big `.frc`, suggesting it has additional fallback logic that our minimal file does not trigger.

Hypothesis: without `#auto_equivalence` (or a compatible equivalence format), `msi2lmp.exe` enters an internal search loop trying to resolve torsions/OOP.

### 6.3 Another likely mismatch: row formats

The CVFF asset formats often look like:
- `#quadratic_bond`: `t1 t2 k r0` (minimal demo) or `ver ref t1 t2 r0 k2` (asset)
- `#torsion_1` / `#out_of_plane`: `ver ref i j k l K n Phi0`

Our builder uses `ver ref ...` but may not match the numeric token ordering/semantics expected by this build.

## 7) Next steps (concrete)

1) Add minimal `#auto_equivalence\tcvff_auto` section from scratch
   - Use deterministic rows with "_" suffix conventions similar to CVFF assets (see [`cvff_Base_MXenes.frc`](workspaces/forcefields/cvff_Base_MXenes.frc:573)).
   - Keep it minimal: only map the emitted atom types + aliases.

2) Add wildcard-safe fallbacks in a way that the tool actually uses
   - Instead of only adding `* * * *` rows, ensure equivalence maps torsion/oop fields to a token that matches the wildcard rows.

3) Re-run real-tool verification
   - Use guarded runner:
     [`run_real_tool_guarded.py`](workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/tools/run_real_tool_guarded.py:1)
   - Also re-run manual `stdbuf` command to confirm the stopping point changes.

4) Once it succeeds, do determinism proof
   - Two clean real-tool runs; compare sha256 for:
     - `outputs/frc_files/ff_cvff_min_bonded.frc`
     - `outputs/msi2lmp_run/CALF20.data`
     - canonical JSON artifacts.

## 8) Tips / verification commands

### 8.1 Manual hang-proof command (authoritative)

Use the template in [`msi2lmp_diagnostics_repro.md`](docs/development/thrust-logs/msi2lmp_diagnostics_repro.md:87).

### 8.2 Quick success control

From the staged CWD:

```bash
/home/sf2/LabWork/software/msi2lmp.exe CALF20 -ignore -print 2 -class I -frc ../../../../forcefields/cvff_Base_MXenes.frc
```

This should complete and write `CALF20.data`.

### 8.3 Pytest environment gotcha

- `python` points to miniconda Python 3.13 in this environment (segfaults in pytest startup).
- Prefer running tests with `/usr/bin/python3`.

