# Docs Canonical Index

This file defines document priority and decision authority for the repository.

## Entry points (start here)

- `AGENTS.md` — entry point for AI-assisted and human work (environment, architecture essentials, canonical links)
- `.cursor/rules/00-agent-workflow.mdc` — auto-loaded agent workflow + verification commands (single source of truth)
- `CONTRIBUTING.md` — developer entry point (setup + documentation map)

## P0 (canonical, decision-making)

- `README.md`
- `docs/GUI_SOURCE_OF_TRUTH.md`
- `docs/GUI_ARCHITECTURE_PROJECT.md`
- `docs/PYQT_CONTRIBUTIONS_REFERENCE.md`
- `docs/MODULES_DEVELOPER_GUIDE.md`
- `docs/MODULE_INTEGRATION_POLICY.md`
- `docs/ARCHITECTURE_REFACTOR_CANONICAL.md`
- `docs/OPERATIONS_CANONICAL.md`
- `docs/LICENSE_SPEC.md`
- `docs/TEST_SMOKE_GATES.md`

## P1 (important, domain/process detail)

- `docs/DOCUMENTS_ARCHITECTURE_CONTRACT.md`
- `docs/INCIDENT_MANAGEMENT_ARCHITECTURE_CONTRACT.md`
- `docs/DOCUMENTS_CLI_REFERENCE.md`
- `docs/DOCUMENTS_TEST_COVERAGE.md`
- `docs/MODULES_USER_GUIDE.md`
- `docs/QMToolV7_ENTWICKLUNG.md`

## P2 (legacy/history or roadmap support) — not for onboarding

These are historical/roadmap references. For onboarding use the entry points and P0 docs above.

- `docs/DEVGUIDE.md`
- `docs/AGENTS_PROJECT.md`
- `docs/CLI_FIRST_MIGRATION.md`
- `docs/RELEASE_READINESS.md`
- `docs/TRACK_B_CHANGE_SPEC.md`
- `docs/TRACK_B_SRP_PREP.md`
- `docs/SRP_REFACTOR_ROADMAP.md`
- `docs/UI_MVP.md`
- `docs/TAGESSTART.md`

## Rule

When documents disagree, P0 overrules P1 and P2.
For architecture refactor decisions, `docs/ARCHITECTURE_REFACTOR_CANONICAL.md` is authoritative; legacy roadmap docs in P2 are history only.
