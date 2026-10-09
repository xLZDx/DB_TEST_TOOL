# Database Testing Tool — Multi-Project Repository

This repository contains database testing and automation projects, engineering materials, and supporting utilities. It is **not a single installable package**; inspect the relevant subproject before running software.

## Directory guide

- `db-testing-tool/` — database testing and QA automation materials.
- `IntelliTest/` and `Click_it/` — separate tooling components with their own READMEs.
- `CDSTestAutomationWPF - Source Code/` — a WPF-related application source tree.
- `PP_BOT/`, `TMZ/`, and `Presentation/` — additional historical or supporting modules.
- `.github/` and `.claude/` — repository automation and agent-related configuration.

## Getting started

Choose a subproject first. Read its own README, requirements, and configuration files. For example:

- [Click_it/README.md](Click_it/README.md)
- [IntelliTest/README.md](IntelliTest/README.md)
- [Database tool portable documentation](db-testing-tool/portable/README.txt)

Some large assets and documents may be stored as **Git LFS pointers**. A pointer file does not contain the underlying application or documentation. Obtain approved assets through Git LFS if needed.

## Safe verification

Use disposable database instances and least-privilege test accounts. Do not execute destructive SQL, import production credentials, or treat a repository script as safe for live databases without an explicit, reviewed test plan.

No universal build or release command is asserted here, because the subprojects have different toolchains and readiness levels.

## Language policy

All newly authored GitHub documentation, code commentary, issue/PR descriptions, and commits must be in English. Preserve database object names, SQL identifiers, sample data contracts, and historical evidence without semantic modification.
