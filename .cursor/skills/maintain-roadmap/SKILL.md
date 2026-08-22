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
3. For broad factual discovery, invoke the custom agent with a task beginning
   `[ROLE:repo-explorer]`; use no more than three independent parallel explorations.
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

If the proposal changes an established architecture, security/trust model, persistence technology,
transport model, or central framework, create or update an existing-style `docs/AP-*_ADR.md`
proposal containing current state, problem, insufficiency, meaningful alternatives, recommendation,
impacts, affected modules/contracts, data/migration and compatibility consequences, test/rollout
strategy, risks, and roadmap effects. Set runtime state to `BLOCKED_HUMAN` with `human_gate=true`.
Do not implement or let the stop hook continue.

Normal design choices inside established architecture remain autonomous. Never start the prepared
work package; the user starts it separately with `/execute-work-package`.
