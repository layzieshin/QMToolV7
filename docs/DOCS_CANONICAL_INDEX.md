# Docs Canonical Index

This file defines document priority and decision authority for the repository.

## Entry points (start here)

- `AGENTS.md` — entry point for AI-assisted and human work (environment, architecture essentials, canonical links)
- `.cursor/rules/00-agent-workflow.mdc` — auto-loaded agent workflow + verification commands (single source of truth)
- `CONTRIBUTING.md` — developer entry point (setup + documentation map)
- `docs/AP-029_WEB_POSTGRES_TRANSITION_PLAN.md` — active Web/PostgreSQL transition steering (P1)

## P0 (canonical, decision-making)

- `README.md`
- `docs/GUI_SOURCE_OF_TRUTH.md`
- `docs/GUI_ARCHITECTURE_PROJECT.md`
- `docs/WEBCLIENT_UX_SPECIFICATION.md` — binding product UX for WEB01 and later webclient work
- `docs/MODULES_DEVELOPER_GUIDE.md`
- `docs/MODULE_INTEGRATION_POLICY.md`
- `docs/ARCHITECTURE_REFACTOR_CANONICAL.md`
- `docs/OPERATIONS_CANONICAL.md`
- `docs/DATABASE_EVOLUTION_POLICY.md`
- `docs/LICENSE_SPEC.md`
- `docs/TEST_SMOKE_GATES.md`

## P1 (important, domain/process detail)

- `docs/AGENT_INSTRUCTION_BOOTSTRAP_PROMPT.md` — generic Codex-first bootstrap prompt for new repos
- `docs/CURSOR_AUTONOMOUS_WORK_PACKAGE_SYSTEM.md` — local Cursor-native work-package operation guide
- `docs/MASTER_ORCHESTRATION_ROADMAP.md` — active work-package steering (planning only; P0 architecture docs win on boundaries)
- `docs/AP-029_WEB_POSTGRES_TRANSITION_PLAN.md` — Web/PostgreSQL target architecture and executable checkpoint ledger
- `docs/WEBCLIENT_UX_CONTRACT_GAP_MATRIX.md` — current support, WEB01 blockers, deferred UX targets, and historical disposition
- `docs/DOCUMENTS_ARCHITECTURE_CONTRACT.md`
- `docs/INCIDENT_MANAGEMENT_ARCHITECTURE_CONTRACT.md`
- `docs/DOCUMENTS_CLI_REFERENCE.md`
- `docs/DOCUMENTS_TEST_COVERAGE.md`
- `docs/MODULES_USER_GUIDE.md`
- `docs/QMToolV7_ENTWICKLUNG.md`
- `docs/AP-027_DATABASE_EVOLUTION_FOUNDATION.md`

## P2 (legacy/history or roadmap support) — not for onboarding

These are historical/roadmap references. For onboarding use the entry points and P0 docs above.

- `docs/PYQT_CONTRIBUTIONS_REFERENCE.md` — frozen PyQt contribution inventory (no new contributions)
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
For the Web/PostgreSQL transition order, `docs/AP-029_WEB_POSTGRES_TRANSITION_PLAN.md` steers checkpoints; P0 docs win on binding architecture boundaries.
