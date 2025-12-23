# Thrust Logs

Thrust logs are detailed, chronological records of systematic debugging, optimization, or experimental development efforts. They provide a structured approach to complex problem-solving and preserve institutional knowledge for future reference.

---

## What is a Thrust Log?

A **thrust log** documents an intensive, focused effort to solve a complex problem or optimize a system. Unlike issue trackers or commit messages, thrust logs capture the full journey:

- **Hypotheses** tested
- **Experiments** run
- **Results** observed
- **Insights** gained
- **Final solution** implemented

---

## When to Use a Thrust Log

Create a thrust log when:

1. **Debugging a complex issue** - Multiple potential causes, requires systematic investigation
2. **Optimizing a system** - Need to explore the solution space methodically
3. **Exploring unknowns** - Working with unfamiliar tools or requirements
4. **Context handoff** - Need to transfer detailed context to a future developer (or your future self)

---

## Thrust Log Template

```markdown
# Thrust Log: {Feature/Problem Name}

## 1) Background and Motivation

- Prior state
- Current problem
- Goal

## 2) Hypothesis Set

- H1: {Hypothesis 1}
- H2: {Hypothesis 2}
- H3: {Hypothesis 3}

## 3) Experiment Log

| Exp | Configuration | Result | Status |
|-----|---------------|--------|--------|
| E01 | [description] | [outcome] | PASS/FAIL |
| E02 | [description] | [outcome] | PASS/FAIL |
| E03 | [description] | [outcome] | PASS/FAIL |

## 4) Findings

- What worked
- What didn't work
- Unexpected discoveries

## 5) Final Solution

- Summary of the solution
- Code changes made
- Tests added

## 6) Lessons Learned

- Key insights for future work
- Patterns to reuse
- Pitfalls to avoid
```

---

## Best Practices

### Structure

1. **Start with background** - Explain the problem so someone with no context can understand
2. **Explicit hypotheses** - Write down what you think might be wrong before testing
3. **Log every experiment** - Even failed experiments provide valuable information
4. **Update in real-time** - Add entries as you go, don't try to reconstruct later

### Content

- **Be specific** - Include exact commands, file paths, and error messages
- **Include timestamps** - Helps establish sequence and duration
- **Link to code** - Reference specific commits, files, or line numbers
- **Capture metrics** - Numbers tell the story: timing, sizes, counts

### Naming Convention

Use the format: `thrust_log_{topic}.md`

Examples:
- `thrust_log_cvff_base_minimization.md`
- `thrust_log_nist_calf20_msi2lmp_stall.md`
- `thrust_log_packmol_determinism.md`

---

## Example Experiment Log Entry

```markdown
### E14: skeleton_plus_mixed_equivalences

**Date**: 2024-11-15  
**Configuration**:
- Input: 28 entries (skeleton) + 4 entries (mixed equivalences)
- FRC sections: atom_types, equivalence, bond_increments, nonbond(9-6)
- Total: 32 entries, ~2.4KB

**Command**:
```bash
./msi2lmp -class I -frc ./ff_minimal.frc MXN 2>&1 | tee E14_output.txt
```

**Result**: SUCCESS
- msi2lmp completed in 0.3s
- Generated valid .data file (15,234 bytes)
- All atom types resolved correctly

**Analysis**:
This proves that skeleton + mixed equivalences is sufficient for successful 
parameter resolution. The equivalence table is not required when types are 
directly specified in the bonded sections.

**Status**: PASS ✓
```

---

## Reference

This methodology is derived from the [Iterative Development Playbook](../../workflows/ITERATIVE_DEVELOPMENT_PLAYBOOK.md), Section 4: "Documentation as First-Class Artifact".

---

## Thrust Logs in This Directory

*Files will be moved here as part of the documentation reorganization. Expected contents:*

- `thrust_log_cvff_base_minimization.md` - CVFF base FRC minimization experiments
- `thrust_log_nist_calf20_msi2lmp_stall.md` - msi2lmp stall investigation
- `msi2lmp_diagnostics_repro.md` - msi2lmp diagnostic reproduction steps
- `context_reset_handoff_nist_msi2lmp_nonbond_only.md` - Context handoff documentation
