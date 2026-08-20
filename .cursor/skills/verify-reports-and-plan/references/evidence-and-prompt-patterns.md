# Evidence and Prompt Patterns

## Evidence matrix

| Area | Minimum evidence | Common false conclusion |
| --- | --- | --- |
| Git | branch, HEAD, base, status, staging, diff or commit paths | A clean commit means unrelated work was preserved |
| Tests | exact command, exit code, counts, skips, JUnit or log | A focused pass proves the full regression |
| Runtime | process boundary, environment, workspace, cleanup | TestClient proves real-process behavior |
| PR | PR head SHA, checks for that SHA, threads, policy state | Old green CI proves the new fix |
| Acceptance | required gates plus explicit human decision | Technical PASS means `Accepted` |
| Destructive work | target identity, guard, opt-in, run count, cleanup | A failed preflight performed or consumed a reset |

## Status rules

- `PASS`: every mandatory gate for this checkpoint is green.
- `FAILED`: a product, contract, test, or scenario assertion is red.
- `BLOCKED`: execution cannot safely continue because a prerequisite or environment is unavailable.
- `IN_PROGRESS`: valid work remains and no terminal status applies.
- `NOT RUN`: the step was never started or never reached. Use only when there is no primary evidence that the step ran. Never convert an observed result into `NOT RUN`, and never convert `NOT RUN` into pass or fail.
- `NOT_READY`: any mandatory parent condition is missing, red, blocked, or unaccepted.

When gates run in parallel or a report continues after an earlier failure:

- Stop starting further gates after the first mandatory red or blocked gate.
- Keep the parent checkpoint `FAILED` or `BLOCKED`.
- Report already-running gates with primary evidence by their actual observed outcomes.
- Document any fail-fast sequence violation separately from those outcomes.

## Bounded checkpoint template

```text
Checkpoint: <name>
Objective: <one outcome>

Verified start:
- repository/branch/head/base
- current formal status
- preserved foreign changes

Allowed scope:
- exact files or action category

Forbidden:
- unrelated product areas
- retries or policy weakening
- Git, PR, destructive, deployment, or acceptance actions not explicitly authorized

Steps:
1. Preflight
2. Smallest implementation or diagnosis
3. Focused verification
4. Required broader regression
5. Documentation and evidence update

Fail-fast:
- Stop starting further gates on the first red or blocked mandatory gate.
- Record the first error and keep the parent checkpoint FAILED or BLOCKED.
- Report later gates that already have primary evidence with their actual outcomes.
- Mark only never-started or never-reached steps NOT RUN.
- Document any fail-fast sequence violation separately.

Definition of Done:
- behavior and ownership contract
- exact green gates
- clean scoped diff or staging
- formal status and remaining limitations

Final report:
- branch, head, and divergence
- exact changed files and responsibilities
- commands, exit codes, counts, and evidence paths
- exclusions and new public surfaces
- next authorized action
```

## Authorization boundaries

Treat these as separate permissions:

1. edit implementation;
2. run destructive or externally visible operations;
3. stage;
4. commit;
5. push;
6. create or update a PR;
7. reply to or resolve review threads;
8. enable auto-merge or merge;
9. deploy;
10. mark formally accepted;
11. delete branches or clean worktrees.

When exact wording is required, quote one sentence that authorizes only the next action and explicitly excludes adjacent actions.

## Completion-report checklist

- Is every claimed file actually in the diff or commit?
- Are foreign dirty files still present and unstaged?
- Does the evidence belong to the reported SHA?
- Were failed attempts preserved rather than overwritten?
- Are skips and deselections explained?
- After first red, are unstarted later steps marked NOT RUN while already-run gates keep their observed outcomes?
- Is any fail-fast sequence violation documented separately from gate outcomes?
- Does the fix preserve service and API ownership?
- Are new routes, APIs, services, helpers, entrypoints, persistence paths, or user actions disclosed?
- Is the PR head current and are its checks terminal?
- Are review conversations resolved only with authorization?
- Is formal acceptance still separate from technical readiness?
