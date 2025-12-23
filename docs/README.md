# MOLSAIC Documentation

Welcome to the MOLSAIC documentation. This guide is organized by audience and purpose to help you find what you need quickly.

---

## 📁 Documentation Structure

| Directory | Audience | Purpose |
|-----------|----------|---------|
| [`getting-started/`](getting-started/) | New Users | Onboarding, quickstart guides, workflow introductions |
| [`reference/`](reference/) | All Users | API contracts, schemas, package usage guides |
| [`workflows/`](workflows/) | Users | Workflow-specific guides and methodology |
| [`development/`](development/) | Developers | Development guides, reports, and debugging logs |
| [`methods/`](methods/) | All | Technical methodology documentation |
| [`archive/`](archive/) | Reference | Historical plans and completed project documentation |

---

## 🚀 Quick Navigation

### Getting Started

New to MOLSAIC? Start here:

1. **[Quickstart Guide](getting-started/QUICKSTART.md)** - Get up and running with AS2 hydration
2. **[Onboarding Guide](getting-started/ONBOARDING_USM_UPM_MOLSAIC.md)** - Complete onboarding for USM/UPM/MOLSAIC
3. **[Workflows Overview](getting-started/WORKFLOWS.md)** - Understand the code-first workflow pattern

### Understanding Workflows

Working on a specific workflow?

- **[Ions in Water](workflows/ions-in-water-workflows.md)** - Ion solvation simulations
- **[MXenes Workflows](workflows/REPO_FIT_AND_MXENES_WORKFLOWS.md)** - MXene structure preparation
- **[Development Playbook](workflows/ITERATIVE_DEVELOPMENT_PLAYBOOK.md)** - Iterative development methodology

### Reference Documentation

Looking for technical details?

- **[Adapter Contract](reference/ADAPTER_CONTRACT.md)** - External adapter API specification
- **[Acceptance Criteria](reference/ACCEPTANCE.md)** - AS2 acceptance criteria
- **[MOLSAIC Package](reference/MOLSAIC_FIT_AND_USAGE.md)** - MOLSAIC package documentation
- **[USM Package](reference/USM_FIT_AND_USAGE.md)** - USM package documentation
- **[msi2lmp Usage](reference/msi2lmp_standalone_usage.md)** - Standalone msi2lmp usage guide

### Development

Contributing to MOLSAIC?

- **[Development Guides](development/guides/)** - Version-specific development guides
- **[Reports](development/reports/)** - Version completion reports
- **[Thrust Logs](development/thrust-logs/)** - Systematic debugging and optimization logs

### Methods

Technical methodology:

- **[MSI2LMP FRC Requirements](methods/MSI2LMP_FRC_REQUIREMENTS.md)** - FRC file requirements for msi2lmp
- **[Termset FRC Pipeline](methods/TERMSET_FRC_PIPELINE.md)** - FRC generation pipeline methodology

---

## 📂 Directory Details

### `getting-started/`

User onboarding and introductory documentation. Start here if you're new to the project.

### `reference/`

API contracts, JSON schemas, and package usage documentation. Normative reference for how components work together.

### `workflows/`

Workflow-specific guides explaining how to accomplish specific tasks (e.g., ion solvation, MXene preparation).

### `development/`

Developer documentation organized into:

- **`guides/`** - Development guides for specific versions or features
- **`reports/`** - Completion reports for milestones
- **`thrust-logs/`** - Detailed experiment logs for debugging and optimization efforts (see [Thrust Log Methodology](development/thrust-logs/README.md))

### `methods/`

Technical methodology documentation explaining the "how" and "why" of key processes.

### `archive/`

Historical documentation for completed projects. Read-only reference for context on past decisions.

---

## 🔗 Related Resources

- **[Root README](../README.md)** - Project overview
- **[Active Plans](../plans/)** - Current development plans
- **[Tests](../tests/)** - Test suite documentation

---

*This documentation follows a structure organized by audience (user vs developer) and purpose (getting started, reference, workflows). For the documentation reorganization plan, see [`plans/docs_reorganization_plan.md`](../plans/docs_reorganization_plan.md).*
