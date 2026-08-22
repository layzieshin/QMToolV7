---
name: maintain-roadmap
description: Update the existing QMTool master roadmap or prepare the next work package from user-provided direction while preserving P0 architecture and the established flat AP/ADR structure.
disable-model-invocation: true
---

# Maintain Roadmap

Manual invocation only: `/maintain-roadmap <direction or requirement>`.

1. Read `docs/DOCS_CANONICAL_INDEX.md`, `docs/MASTER_ORCHESTRATION_ROADMAP.md`, the active
   transition plan, relevant P0 architecture documents, existing related `docs/AP-*` files, and
   `.cursor/agent-system.json`.
2. Find the existing owner and status. Do not create a second roadmap, ADR directory, or work
   package hierarchy.
3. For broad factual discovery, invoke `[ROLE:repo-explorer]` only where needed and observe the
   parallel-worker limit in `.cursor/agent-system.json`.
4. Invoke a fresh custom agent with `[ROLE:roadmap-architect]`. Give it the user's direction,
   authoritative documents, repository facts, dependencies, risks, and explicit instruction not to
   edit source code.
5. Validate its proposal against P0, current roadmap ordering, dependencies, and existing AP naming.
6. Update only the existing master/transition roadmap and the appropriate flat `docs/AP-*` package
   documents.

Every implementation package contains vertical checkpoints with:

- goal and concrete use case;
- in scope and out of scope;
- architecture invariants;
- acceptance criteria;
- planned tests/evidence;
- dependencies and risks;
- expected affected areas.

## Planning quality

Use `planning_quality` in `.cursor/agent-system.json` as the normative policy.

1. Classify the package `LOW`, `MEDIUM`, or `HIGH`. It is at least `HIGH` when it affects auth or
   roles, a security/trust boundary, productive persistence, migration/cutover or possible data
   loss, public API/transport, schema/ownership, concurrency/CAS/ETag, backup/restore, secrets,
   deployment/update/rollback, central composition/bootstrap, or strongly interacting critical
   subsystems. Diff size alone does not determine risk.
2. Add Requirement Traceability for fachliche behavior, roles, visible UI, persistence semantics,
   public APIs, fachlich visible errors, migration/cutover, audit, and security/trust decisions.
   Cite a confirmed user decision, requirement ID, AP/ADR, P0 decision, or established contract.
   Pure private implementation details do not need traceability. If material alternatives remain
   without a confirmed source, return `HUMAN_GATE`; do not guess.
3. Add a compact Risk-to-Evidence matrix with failure mode, impact, risk level, mitigation,
   acceptance criterion/test/evidence, and checkpoint. Every HIGH risk must have a complete
   `risk -> mitigation -> criterion/test -> evidence` chain before READY.
4. Identify relevant cross-checkpoint seams and define one package-wide observable integration
   scenario for interacting checkpoints. Use `N/A` only for a documentary or genuinely independent
   package and explain why.
5. Record `planning_risk_level`, `plan_challenge_status`, traceability, Risk-to-Evidence, seams,
   and the Package Integration Scenario in the owning AP/evidence structure.
6. For configured automatic risk levels—or an explicitly justified unusually complex MEDIUM
   package—invoke one fresh `[ROLE:plan-challenger]`. On revision, send the same plan and all
   findings once to a fresh `[ROLE:roadmap-architect]`; record each finding as adopted with its
   change or rejected with authoritative evidence. Do not start another challenger loop. An
   unresolved material fachliche/architecture conflict is a `HUMAN_GATE`.

For an already `IN_PROGRESS` package, keep authorized and completed checkpoints unchanged. Apply
new contract/evidence protections prospectively from the next not-started checkpoint; never
retroactively challenge or reopen PG00 or another completed checkpoint.

If the proposal changes an established architecture, security/trust model, persistence technology,
transport model, or central framework, create or update an existing-style `docs/AP-*_ADR.md`
proposal containing current state, problem, insufficiency, meaningful alternatives, recommendation,
impacts, affected modules/contracts, data/migration and compatibility consequences, test/rollout
strategy, risks, and roadmap effects. Set runtime state to `BLOCKED_HUMAN` with `human_gate=true`.
Do not implement or let the stop hook continue.

Normal design choices inside established architecture remain autonomous. Never start the prepared
work package; the user starts it separately with `/execute-work-package`.
