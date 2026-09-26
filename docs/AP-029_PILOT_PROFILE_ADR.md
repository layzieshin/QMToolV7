# ADR proposal: limited pilot profile `linux-rootless-synthetic`

Status: Proposed (not P0)
Decision status: `PROPOSED / HUMAN_DECISION_REQUIRED`
Valid as proposal from: 2026-09-26
Canonical index: `docs/DOCS_CANONICAL_INDEX.md`
Transition steering: `docs/AP-029_WEB_POSTGRES_TRANSITION_PLAN.md`
Preparation owner: `docs/AP-029_PILOT00_LINUX_PREPARATION.md`
Supersedes nothing until a human accepts this proposal.

P0 operations still say Windows Server first. This file does not amend that
decision. It asks for one additional, bounded pilot profile.

## Context

PILOT00 is the current checkpoint and remains `TODO / NOT RUN`. The existing
unversioned package `build/ap-029-pilot00/PILOT00_WORK_PACKAGE.md` is a Windows
SCM/ACL/reboot contract in status `READY_FOR_HUMAN_ENVIRONMENT_FREEZE`. Its
SHA256 at planning start `8fa8d0a7f6957ef7f532560ed35826b9f9a7be29` is
`48EBFE9F4170EC93B60E807F953133463EFD8747CDD118EB4D8866DB99F0CE8D`. That file
stays unchanged.

Later user direction is a synthetic PDF-first browser pilot on an already
prepared Ubuntu 24.04 rootless Docker host (`servinglunatix`, LAN
`192.168.0.4`), not a new Windows VM. That direction is a profile change. The
completed SSH and rootless setup is infrastructure evidence. It is not
architecture acceptance, not deployment, and not a PILOT00 PASS.

Verified code gaps that any accepted profile still has to close are recorded in
the preparation owner: platform settings still open SQLite at backend start,
sealed backups do not cover signature assets or the signature master key, and
there is no qualified Linux release or pilot target guard.

## Decision proposed

Add a bounded profile id `linux-rootless-synthetic` for PILOT00 only.

If a human accepts it:

- The pilot client stays the existing webclient. PostgreSQL stays the only
  productive datastore. Data stays synthetic and greenfield. PDF-first stays.
  CONV00, PyQt, Kubernetes, a new VM, and a new agent platform stay out of the
  pilot.
- Windows Server remains the decided production option in
  `docs/OPERATIONS_CANONICAL.md`. Its SCM, ACL, certificate-store, and reboot
  gates stay `NOT RUN`. They are not relabeled as passed.
- A Linux result qualifies only `linux-rootless-synthetic`. It is not a Windows readiness PASS, and a Windows PASS would not be a Linux PASS.
- The Windows SCM adapter is replaced, for this profile only, by an explicit
  container/service contract around the existing `python -m src.backend`
  owner. No second server is introduced.
- Package order stays: signature recovery before the target recovery adapter;
  settings cutover, service release, signature recovery, and the target
  recovery adapter before a durable pilot instance. Build-only release checks
  may precede target mutation.
- External module calls from new operator or test adapters stay on
  `modules/<name>/api.py`. No runtime DDL, no dual-write, and no SQLite
  product fallback.

If a human rejects it, PILOT00 continues under the unchanged Windows package.
The rootless host remains an unused precondition, not a failed Windows gate.

## Consequences

Acceptance is a P0-adjacent operations amendment and needs an explicit human
decision before product implementation. This planning package does not grant
that acceptance.

Rejection blocks Linux implementation and does not block keeping the Windows
package as the pilot contract.

Either outcome leaves PILOT01 blocked until PILOT00 has passed and a separate
human live-data decision exists.

## Non-decisions

This proposal does not choose the LAN name, TLS termination, license file,
backup location, tester names, RPO/RTO, or screenreader tool. Those stay in
the preparation owner with their own latest safe gates.
