# Subtask 2A: Experiment Execution Plan (E1-E10)

## 1. Execution Overview

For each preset E1-E10:
1. Create a temporary config file with the preset setting
2. Run the workspace runner to generate the `.frc` file
3. Execute `msi2lmp.exe` with the hang-proof template (40s timeout)
4. Record outcome (PASS/STALL/FAST-FAIL) and artifacts

## 2. Results JSON Schema

```json
{
  "schema": "experiment_results.v1",
  "timestamp": "ISO8601 UTC",
  "experiments": [
    {
      "preset": "E1",
      "hypothesis": "H6",
      "description": "preamble_style=asset_like",
      "exit_code": 0,
      "outcome": "PASS|STALL|FAST-FAIL",
      "calf20_data_size_bytes": 12345,
      "stdout_last_lines": ["..."],
      "stderr_last_lines": ["..."],
      "artifacts": {
        "frc_file": "ff_exp_E1.frc",
        "stdout_file": "manual_E1.stdout.txt",
        "stderr_file": "manual_E1.stderr.txt"
      }
    }
  ],
  "summary": {
    "total_experiments": 10,
    "pass_count": 0,
    "stall_count": 0,
    "fast_fail_count": 0,
    "first_pass_preset": null,
    "first_pass_hypothesis": null
  }
}
```

## 3. Outcome Classification Logic

```python
def classify_outcome(exit_code: int, data_path: Path) -> str:
    data_exists = data_path.exists() and data_path.stat().st_size > 0
    if exit_code == 0 and data_exists:
        return "PASS"
    elif exit_code == 143:  # SIGTERM from timeout
        return "STALL"
    else:
        return "FAST-FAIL"
```

## 4. Experiment Execution Commands

### Workspace paths
- **WORKSPACE_DIR**: `workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1`
- **MSI2LMP_RUN_DIR**: `workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/outputs/msi2lmp_run`
- **FRC_FILES_DIR**: `workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/outputs/frc_files`

### Per-Preset Execution Template

For each preset Exx:

```bash
# Step A: Clean outputs and create temp config
rm -rf workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/outputs

# Create config_exp_Exx.json with the preset
cat > workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/config_exp_Exx.json << 'EOF'
{
  "outputs_dir": "./outputs",
  "inputs": {
    "car": "inputs/CALF20.car",
    "mdf": "inputs/CALF20.mdf",
    "parameterset": "inputs/parameterset.json"
  },
  "executables": {
    "msi2lmp": "/home/sf2/LabWork/software/msi2lmp.exe"
  },
  "params": {
    "timeout_s": 600,
    "frc_experiment_preset": "Exx",
    "msi2lmp_ignore": true,
    "msi2lmp_print_level": 2
  }
}
EOF

# Step B: Generate .frc file via workspace runner
python workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/run.py \
  --config workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/config_exp_Exx.json

# Step C: Manual hang-proof run from outputs/msi2lmp_run
cd workspaces/NIST/nist_calf20_msi2lmp_unbonded_v1/outputs/msi2lmp_run && \
timeout --preserve-status --signal=TERM --kill-after=1s 40s \
  stdbuf -oL -eL /home/sf2/LabWork/software/msi2lmp.exe CALF20 \
    -ignore -print 2 -class I -frc ../frc_files/ff_exp_Exx.frc \
  </dev/null \
  >manual_Exx.stdout.txt \
  2>manual_Exx.stderr.txt; \
echo "Exx exit_code=$?"

# Step D: Check outcome
ls -la CALF20.data 2>/dev/null || echo "CALF20.data does not exist"
```

## 5. Preset Details

| Preset | Config Override | Tests Hypothesis |
|--------|----------------|------------------|
| E1 | `preamble_style=asset_like` | H6 - Front-matter |
| E2 | `emit_macro_table=False` | H1/H4 - Macro table |
| E3 | `macro_table_format=asset_tabs` | H4 - Formatting |
| E4 | `bond_model=morse_only` | H1 - Bond-model |
| E5 | `cvff_define=cvff_nocross_nomorse, bond_model=quadratic_only` | H1 - Bond-model |
| E6 | `section_order=asset_like` | H2 - Section ordering |
| E7 | `ver_ref_policy=normalize_2_0_18` | H3 - Ver/ref |
| E8 | `emit_auto_equivalence=False` | H5 - Equivalence |
| E9 | `emit_wildcard_torsion=False, emit_wildcard_oop=False` | H5 - Wildcards |
| E10 | `header_label_separator=space, header_trailing_space=True` | H4 - Headers |

## 6. Stop Condition

- **First PASS wins**: Stop detailed analysis when first PASS is found
- **All experiments run**: Execute all E1-E10 regardless to have complete data
- **If no PASS found**: Document all failures and expand hypothesis set

## 7. Artifacts to Capture

For each experiment:
- `outputs/frc_files/ff_exp_Exx.frc` - Generated forcefield file
- `outputs/msi2lmp_run/manual_Exx.stdout.txt` - Captured stdout
- `outputs/msi2lmp_run/manual_Exx.stderr.txt` - Captured stderr
- Exit code from `$?`
- `CALF20.data` size (if exists)

## 8. Success Metrics

1. All 10 experiments executed with captured outcomes
2. Results aggregated into `experiment_results.json`
3. First PASS preset identified (if any)
4. Hypothesis mapped for winning preset
5. Thrust log updated with results table
