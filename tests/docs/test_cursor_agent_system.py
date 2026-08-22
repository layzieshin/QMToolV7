from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CURSOR = ROOT / ".cursor"
CONFIG = CURSOR / "agent-system.json"
AGENTS = CURSOR / "agents"
HOOKS = CURSOR / "hooks"
RUNTIME_TEMPLATE = CURSOR / "runtime" / "workflow-state.template.json"
POWERSHELL = "powershell.exe"

ROLE_NAMES = {
    "roadmap-architect",
    "repo-explorer",
    "implementer",
    "checkpoint-reviewer",
    "escalation-reviewer",
    "git-steward",
    "plan-challenger",
    "external-review-triager",
}
SKILL_NAMES = {"maintain-roadmap", "execute-work-package", "apply-agent-profile"}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _config() -> dict[str, Any]:
    return json.loads(_read(CONFIG))


def _frontmatter_value(text: str, key: str) -> str:
    match = re.search(rf"(?m)^{re.escape(key)}:\s*(.+?)\s*$", text)
    assert match, f"missing frontmatter {key}"
    return match.group(1).strip()


def _observed_work_branch() -> str:
    completed = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    branch = completed.stdout.strip()
    assert branch, "git branch --show-current returned no branch name"
    return branch


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )


def _make_behind_main(root: Path) -> tuple[Path, Path]:
    remote = root / "remote.git"
    seed = root / "seed"
    work = root / "work"
    root.mkdir()
    _git(root, "init", "--bare", "--initial-branch=main", str(remote))
    _git(root, "init", "--initial-branch=main", str(seed))
    _git(seed, "config", "user.email", "tests@example.invalid")
    _git(seed, "config", "user.name", "Tests")
    (seed / "tracked.txt").write_text("base\n", encoding="utf-8")
    _git(seed, "add", "tracked.txt")
    _git(seed, "commit", "-m", "base")
    _git(seed, "remote", "add", "origin", str(remote))
    _git(seed, "push", "-u", "origin", "main")
    _git(root, "clone", "--branch", "main", str(remote), str(work))
    _git(work, "config", "user.email", "tests@example.invalid")
    _git(work, "config", "user.name", "Tests")
    (seed / "tracked.txt").write_text("remote ahead\n", encoding="utf-8")
    _git(seed, "add", "tracked.txt")
    _git(seed, "commit", "-m", "remote ahead")
    _git(seed, "push", "origin", "main")
    _git(work, "fetch", "origin")
    return work, seed


def _write_state(path: Path, **updates: Any) -> dict[str, Any]:
    state = json.loads(_read(RUNTIME_TEMPLATE))
    state.update(
        {
            "status": "RUNNING",
            "work_package": "WP-TEST",
            "base_branch": "main",
            "work_branch": _observed_work_branch(),
            "phase": "IMPLEMENT",
            "checkpoint": "CP-1",
            "work_package_path": "docs/WP-TEST.md",
            "execution_journal_path": "docs/WP-TEST.md",
            "next_action": "implement CP-1",
        }
    )
    state.update(updates)
    path.write_text(json.dumps(state), encoding="utf-8")
    return state


def _run_hook(
    script: str,
    payload: dict[str, Any],
    *,
    state_path: Path,
    log_path: Path | None = None,
    env_overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    env = os.environ.copy()
    env["QMTOOL_WORKFLOW_STATE_PATH"] = str(state_path)
    if log_path is not None:
        env["QMTOOL_RUNTIME_LOG_PATH"] = str(log_path)
    if env_overrides:
        env.update(env_overrides)
    completed = subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(HOOKS / script),
        ],
        cwd=ROOT,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    output = completed.stdout.strip()
    assert output, f"{script} returned no JSON"
    return json.loads(output)


def test_config_agents_skills_rules_and_worktree_contracts() -> None:
    config = _config()
    defaults = config["defaults"]
    assert config["profile"] == "balanced"
    assert defaults == {
        "max_checkpoint_reworks": 2,
        "max_final_audit_reworks": 2,
        "max_escalation_reviews": 1,
        "max_reviewer_verification_passes": 1,
        "max_parallel_workers": 3,
        "stop_hook_loop_limit": 8,
        "local_only": True,
        "architecture_change_requires_human": True,
        "auto_merge_after_all_gates": True,
    }
    assert set(config["roles"]) == ROLE_NAMES
    planning = config["planning_quality"]
    assert planning == {
        "enabled": True,
        "automatic_challenge_risk_levels": ["HIGH"],
        "max_plan_challenge_rounds": 1,
        "max_scope_correction_rounds": 1,
        "require_requirement_traceability": True,
        "require_risk_to_evidence": True,
        "require_integration_scenario_for_interacting_checkpoints": True,
    }
    external = config["external_review"]
    assert external == {
        "enabled": True,
        "provider": "github-codex",
        "required_when_available": True,
        "unavailability_blocks_merge": False,
        "max_review_rounds": 2,
        "max_rework_batches": 2,
        "max_review_requests_per_round": 1,
        "max_triage_passes_per_round": 1,
        "wait_seconds": 300,
        "poll_interval_seconds": 30,
        "statuses": [
            "NOT_REQUESTED",
            "PENDING",
            "PASS",
            "FINDINGS",
            "STALE",
            "BOUNDED_COMPLETE",
            "UNAVAILABLE",
            "LIMIT_REACHED",
            "DISABLED",
        ],
        "review_author_logins": [
            "chatgpt-codex-connector",
            "chatgpt-codex-connector[bot]",
        ],
    }

    agent_paths = set(AGENTS.glob("*.md"))
    assert {path.stem for path in agent_paths} == ROLE_NAMES
    for role, definition in config["roles"].items():
        text = _read(AGENTS / f"{role}.md")
        assert _frontmatter_value(text, "name") == role
        assert _frontmatter_value(text, "model") == definition["model"]
        assert "Responsibilities" in text
        assert "Non-responsibilities" in text
        assert "Input contract" in text
        assert "Output contract" in text
        assert "Stop conditions" in text
        assert f"[ROLE:{role}]" in text

    for skill in SKILL_NAMES:
        text = _read(CURSOR / "skills" / skill / "SKILL.md")
        assert _frontmatter_value(text, "name") == skill
        assert _frontmatter_value(text, "disable-model-invocation") == "true"

    execute_skill = _read(CURSOR / "skills" / "execute-work-package" / "SKILL.md")
    assert "/execute-gated-macro` is the single checkpoint-execution owner" in execute_skill
    assert "create a finalization commit" in execute_skill
    assert "Never leave FINAL_PASS documents only in the worktree" in execute_skill
    for required in (
        "Requirement Traceability",
        "Risk-to-Evidence",
        "Package Integration Scenario",
        "checkpoint-contract.md",
        "contract_sha256",
        "SCOPE_CORRECTION_REQUIRED",
        "external-review-triager",
        "LIMIT_REACHED",
        "@codex address that feedback",
        "BOUNDED_COMPLETE",
    ):
        assert required in execute_skill
    reviewer = _read(AGENTS / "checkpoint-reviewer.md")
    assert "$verify-reports-and-plan" in reviewer
    assert "configured focused verification-pass budget" in reviewer
    assert "non-blocking follow-up" in reviewer
    assert "realistic security/data-integrity bypass" in reviewer
    assert "checkpoint-contract.md" in reviewer
    assert "Moving Goalposts" in reviewer
    assert "Scope Corrections" in reviewer
    assert "finalization commit" in _read(AGENTS / "git-steward.md")
    challenger = _read(AGENTS / "plan-challenger.md")
    assert _frontmatter_value(challenger, "readonly") == "true"
    assert "PLAN_CHALLENGE_PASS" in challenger
    assert "PLAN_REVISION_REQUIRED" in challenger
    triager = _read(AGENTS / "external-review-triager.md")
    assert _frontmatter_value(triager, "readonly") == "true"
    assert "CONFIRMED_BLOCKING" in triager
    assert "FALSE_POSITIVE" in triager
    assert "Never edit source" in triager

    rule = _read(CURSOR / "rules" / "02-autonomous-work-package.mdc")
    assert _frontmatter_value(rule, "alwaysApply") == "true"
    assert "only normative source for workflow limits" in rule
    assert "immutable checkpoint contract" in rule
    assert "Plan Challenge" in rule
    assert "Package Integration" in rule
    assert "bounded optional external reviewer" in rule
    assert "non-blocking follow-up" in rule
    assert "git-steward" in rule
    assert "HUMAN_GATE" in rule

    hooks = json.loads(_read(CURSOR / "hooks.json"))
    assert hooks["version"] == 1
    assert hooks["hooks"]["stop"][0]["loop_limit"] == defaults["stop_hook_loop_limit"]
    assert hooks["hooks"]["beforeShellExecution"][0]["failClosed"] is True
    assert hooks["hooks"]["beforeShellExecution"][0]["matcher"] == "(?i)(git|gh)"

    worktrees = json.loads(_read(CURSOR / "worktrees.json"))
    assert worktrees == {"setup-worktree-windows": "setup-worktree-windows.ps1"}
    assert (CURSOR / worktrees["setup-worktree-windows"]).is_file()

    workflow_rule = _read(CURSOR / "rules" / "00-agent-workflow.mdc")
    assert "implementation-plan approval" in workflow_rule
    assert "Only the HUMAN_GATEs" in workflow_rule
    git_rule = _read(CURSOR / "rules" / "01-git-workflow.mdc")
    assert "git pull --ff-only" in git_rule
    assert "zero-ahead" not in git_rule
    assert "Do not add flags" in git_rule

    roadmap_skill = _read(CURSOR / "skills" / "maintain-roadmap" / "SKILL.md")
    for required in (
        "planning_risk_level",
        "Requirement Traceability",
        "Risk-to-Evidence",
        "Package Integration Scenario",
        "[ROLE:plan-challenger]",
    ):
        assert required in roadmap_skill

    gitignore = _read(ROOT / ".gitignore")
    assert ".cursor/runtime/workflow-state.json" in gitignore
    assert ".cursor/runtime/*.log" in gitignore


def test_numeric_workflow_limits_are_config_owned_and_projections_do_not_drift() -> None:
    config = _config()
    defaults = config["defaults"]
    hooks = json.loads(_read(CURSOR / "hooks.json"))
    assert hooks["hooks"]["stop"][0]["loop_limit"] == defaults["stop_hook_loop_limit"]

    explanatory_paths = [
        CURSOR / "rules" / "00-agent-workflow.mdc",
        CURSOR / "rules" / "02-autonomous-work-package.mdc",
        CURSOR / "skills" / "maintain-roadmap" / "SKILL.md",
        CURSOR / "skills" / "execute-work-package" / "SKILL.md",
        CURSOR / "skills" / "execute-gated-macro" / "SKILL.md",
        CURSOR / "skills" / "execute-gated-macro" / "references" / "checkpoint-protocol.md",
        ROOT / "docs" / "CURSOR_AUTONOMOUS_WORK_PACKAGE_SYSTEM.md",
    ]
    combined = "\n".join(_read(path) for path in explanatory_paths)
    for stale_phrase in (
        "at most two normal checkpoint reworks",
        "at most two remediation rounds",
        "at most two final-audit reworks",
        "more than three parallel workers",
        "follow-up limit is eight",
    ):
        assert stale_phrase not in combined
    assert combined.count(".cursor/agent-system.json") >= 5

    models = {role: definition["model"] for role, definition in config["roles"].items()}
    for role, expected in models.items():
        assert _frontmatter_value(_read(AGENTS / f"{role}.md"), "model") == expected


def test_session_start_injects_only_active_compact_context(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    _write_state(state_path, rework_count=1, human_gate=False)
    active = _run_hook(
        "session-start.ps1",
        {"session_id": "test", "composer_mode": "agent"},
        state_path=state_path,
    )
    context = active["additional_context"]
    assert "WP-TEST" in context
    assert "CP-1" in context
    assert "Rework Count: 1" in context
    assert "Resume the persisted workflow" in context
    assert "External Review:" not in context
    assert len(context) < 1500

    _write_state(
        state_path,
        phase="FINAL_GIT",
        external_review={
            "status": "PENDING",
            "round": 1,
            "reviewed_head": None,
            "blocking_findings": [],
            "last_checked_at": None,
        },
    )
    final_git = _run_hook(
        "session-start.ps1",
        {"session_id": "test", "composer_mode": "agent"},
        state_path=state_path,
    )
    assert "External Review: PENDING (round 1)" in final_git["additional_context"]
    assert "blocking_findings" not in final_git["additional_context"]
    assert len(final_git["additional_context"]) < 1500

    _write_state(state_path, status="IDLE")
    idle = _run_hook(
        "session-start.ps1",
        {"session_id": "test", "composer_mode": "agent"},
        state_path=state_path,
    )
    assert idle == {}


def test_stop_watchdog_respects_completion_gate_and_manual_stop(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"

    _write_state(state_path)
    completed = _run_hook(
        "workflow-watchdog.ps1",
        {"status": "completed", "loop_count": 0},
        state_path=state_path,
    )
    assert "followup_message" in completed

    _write_state(state_path, status="BLOCKED_HUMAN", human_gate=True)
    blocked = _run_hook(
        "workflow-watchdog.ps1",
        {"status": "completed", "loop_count": 0},
        state_path=state_path,
    )
    assert blocked == {}

    _write_state(state_path)
    aborted = _run_hook(
        "workflow-watchdog.ps1",
        {"status": "aborted", "loop_count": 0},
        state_path=state_path,
    )
    assert aborted == {}

    _write_state(state_path, status="DONE")
    done = _run_hook(
        "workflow-watchdog.ps1",
        {"status": "completed", "loop_count": 0},
        state_path=state_path,
    )
    assert done == {}


def test_subagent_model_gate_allows_match_denies_mismatch_and_ignores_untagged(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "state.json"
    log_path = tmp_path / "subagent.log"

    allowed = _run_hook(
        "subagent-start.ps1",
        {
            "task": "[ROLE:implementer]\nImplement CP-1",
            "subagent_model": "composer-2.5[fast=false]",
        },
        state_path=state_path,
        log_path=log_path,
    )
    assert allowed["permission"] == "allow"

    denied = _run_hook(
        "subagent-start.ps1",
        {
            "task": "[ROLE:implementer]\nImplement CP-1",
            "subagent_model": "gpt-5.6-sol",
        },
        state_path=state_path,
        log_path=log_path,
    )
    assert denied["permission"] == "deny"
    assert "composer-2.5[]" in denied["user_message"]

    untagged = _run_hook(
        "subagent-start.ps1",
        {"task": "ordinary internal helper", "subagent_model": "inherit"},
        state_path=state_path,
        log_path=log_path,
    )
    assert untagged["permission"] == "allow"

    lines = log_path.read_text(encoding="utf-8-sig").splitlines()
    assert len(lines) == 3
    assert json.loads(lines[0])["role"] == "implementer"
    untagged_log = json.loads(lines[2])
    assert untagged_log["role"] == "UNTAGGED"
    assert untagged_log["actual_model"] == "inherit"
    assert untagged_log["task_short"] == "ordinary internal helper"
    assert untagged_log["allowed"] is True


def test_git_guard_safe_ff_only_matrix(tmp_path: Path) -> None:
    state_path = tmp_path / "unused-state.json"

    def guard(repo: Path, command: str) -> dict[str, Any]:
        return _run_hook(
            "git-guard.ps1",
            {"command": command, "cwd": str(repo), "sandbox": False},
            state_path=state_path,
        )

    work, _ = _make_behind_main(tmp_path / "allow")
    assert guard(work, "git pull --ff-only")["permission"] == "allow"
    assert guard(work, "git pull --ff-only origin main")["permission"] == "allow"
    _git(work, "merge", "--ff-only", "origin/main")
    assert guard(work, "git pull --ff-only")["permission"] == "allow"
    for command in (
        "git pull",
        "git pull --rebase",
        "git pull --ff-only --quiet",
        f'git -C "{work}" pull --ff-only',
        f'Set-Location "{work}"; git pull --ff-only',
    ):
        assert guard(work, command)["permission"] == "deny"

    dirty, _ = _make_behind_main(tmp_path / "dirty")
    (dirty / "untracked.txt").write_text("dirty\n", encoding="utf-8")
    assert guard(dirty, "git pull --ff-only")["permission"] == "deny"

    staged, _ = _make_behind_main(tmp_path / "staged")
    (staged / "staged.txt").write_text("staged\n", encoding="utf-8")
    _git(staged, "add", "staged.txt")
    assert guard(staged, "git pull --ff-only")["permission"] == "deny"

    ahead, _ = _make_behind_main(tmp_path / "ahead")
    _git(ahead, "merge", "--ff-only", "origin/main")
    (ahead / "local.txt").write_text("ahead\n", encoding="utf-8")
    _git(ahead, "add", "local.txt")
    _git(ahead, "commit", "-m", "local ahead")
    assert guard(ahead, "git pull --ff-only")["permission"] == "deny"

    diverged, seed = _make_behind_main(tmp_path / "diverged")
    (diverged / "local.txt").write_text("local\n", encoding="utf-8")
    _git(diverged, "add", "local.txt")
    _git(diverged, "commit", "-m", "local divergent")
    (seed / "remote.txt").write_text("remote\n", encoding="utf-8")
    _git(seed, "add", "remote.txt")
    _git(seed, "commit", "-m", "remote divergent")
    _git(seed, "push", "origin", "main")
    _git(diverged, "fetch", "origin")
    assert guard(diverged, "git pull --ff-only")["permission"] == "deny"

    feature, _ = _make_behind_main(tmp_path / "feature")
    _git(feature, "switch", "-c", "feature/test")
    assert guard(feature, "git pull --ff-only")["permission"] == "deny"

    wrong_upstream, _ = _make_behind_main(tmp_path / "wrong-upstream")
    _git(wrong_upstream, "branch", "--set-upstream-to=origin/main", "main")
    remote_url = _git(wrong_upstream, "remote", "get-url", "origin").stdout.strip()
    _git(wrong_upstream, "remote", "add", "other", remote_url)
    _git(wrong_upstream, "fetch", "other", "main")
    _git(wrong_upstream, "branch", "--set-upstream-to=other/main", "main")
    assert guard(wrong_upstream, "git pull --ff-only")["permission"] == "deny"


def test_git_guard_policy_matrix(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    work_branch = _observed_work_branch()

    def guard(
        command: str, env_overrides: dict[str, str] | None = None
    ) -> dict[str, Any]:
        return _run_hook(
            "git-guard.ps1",
            {"command": command, "cwd": str(ROOT), "sandbox": False},
            state_path=state_path,
            env_overrides=env_overrides,
        )

    assert guard("git status")["permission"] == "allow"
    assert guard("git worktree list")["permission"] == "allow"
    assert guard(f'git -C "{ROOT}" status')["permission"] == "allow"
    assert guard("git branch")["permission"] == "allow"
    assert guard("git branch --show-current")["permission"] == "allow"
    assert guard("git branch unauthorized")["permission"] == "deny"
    assert guard("gh api repos/layzieshin/QMToolV7/pulls/30")["permission"] == "allow"
    assert guard("gh api repos/layzieshin/QMToolV7/pulls/30/reviews")["permission"] == "allow"
    assert guard("gh api repos/layzieshin/QMToolV7/pulls/30/comments")["permission"] == "allow"
    assert guard("gh.exe pr view 30")["permission"] == "allow"
    assert guard("gh.exe pr frobnicate 30")["permission"] == "deny"
    assert (
        guard(
            "gh api --method PUT repos/layzieshin/QMToolV7/pulls/30/merge"
        )["permission"]
        == "deny"
    )

    _write_state(state_path, phase="IMPLEMENT")
    assert guard('git commit -m "wrong phase"')["permission"] == "deny"
    assert guard("git add expected.py")["permission"] == "deny"
    assert guard("git fetch origin")["permission"] == "deny"

    _write_state(state_path, phase="CHECKPOINT_GIT")
    assert guard('git commit -m "WP-TEST CP-1"')["permission"] == "allow"
    assert guard("git add expected.py")["permission"] == "allow"
    assert (
        guard('Set-Location "I:\\OtherRepo"; git add expected.py')["permission"]
        == "deny"
    )

    _write_state(state_path, status="IDLE", phase="CHECKPOINT_GIT")
    assert guard('git commit -m "idle"')["permission"] == "deny"

    _write_state(state_path, phase="CHECKPOINT_GIT")
    assert guard('git -C "I:\\OtherRepo" push origin HEAD')["permission"] == "deny"
    assert (
        guard(f'git -C "{ROOT}" -C "{ROOT}" commit -m "probe"')["permission"]
        == "deny"
    )
    assert (
        guard(f'git --no-pager -C "{ROOT}" commit -m "probe"')["permission"]
        == "deny"
    )
    assert (
        guard(f'git --no-pager -C "{ROOT}" push origin HEAD')["permission"]
        == "deny"
    )
    assert guard("git push origin main")["permission"] == "deny"
    assert guard("git push origin HEAD:refs/heads/main")["permission"] == "deny"
    assert guard("git push origin HEAD:refs/heads/other")["permission"] == "deny"
    assert (
        guard(
            f"git push origin other:{work_branch}"
        )["permission"]
        == "deny"
    )
    assert (
        guard(f"git push origin :{work_branch}")["permission"]
        == "deny"
    )
    assert guard("git push --force origin HEAD")["permission"] == "deny"
    assert guard("git push -u origin HEAD")["permission"] == "allow"
    assert (
        guard(f"git push origin {work_branch}")["permission"]
        == "allow"
    )
    assert guard("git clean -fd")["permission"] == "deny"
    assert guard("git reset --mixed HEAD~1")["permission"] == "deny"
    assert guard("git tag unsafe-tag")["permission"] == "deny"
    assert guard("git update-ref refs/heads/unsafe HEAD")["permission"] == "deny"

    _write_state(
        state_path,
        phase="CHECKPOINT_GIT",
        work_branch="feature/different-work-package",
    )
    assert guard('git commit -m "wrong branch"')["permission"] == "deny"

    _write_state(
        state_path,
        phase="FINAL_GIT",
        gates={
            "full_regression_pass": False,
            "final_audit_pass": False,
            "ci_pass": False,
        },
    )
    assert guard("gh pr merge 999 --squash")["permission"] == "deny"

    _write_state(state_path, phase="FINAL_GIT")
    assert (
        guard('gh pr comment 999 --body "@codex review"')["permission"]
        == "allow"
    )
    assert guard('gh pr comment 999 --body "general comment"')["permission"] == "deny"
    assert guard('gh.exe pr comment 999 --body "general comment"')["permission"] == "deny"
    assert guard('gh.exe pr comment 999 --body "@codex review"')["permission"] == "allow"
    _write_state(
        state_path,
        phase="FINAL_GIT",
        external_review={
            "status": "PENDING",
            "round": 1,
            "reviewed_head": None,
            "blocking_findings": [],
            "last_checked_at": None,
        },
    )
    assert guard('gh pr comment 999 --body "@codex review"')["permission"] == "deny"
    _write_state(
        state_path,
        phase="FINAL_GIT",
        external_review={
            "status": "STALE",
            "round": 2,
            "reviewed_head": "old-head",
            "blocking_findings": [],
            "last_checked_at": "2026-08-22T00:00:00Z",
        },
    )
    assert guard('gh pr comment 999 --body "@codex review"')["permission"] == "deny"

    _write_state(
        state_path,
        phase="FINAL_GIT",
        gates={
            "full_regression_pass": True,
            "final_audit_pass": True,
            "ci_pass": True,
        },
    )
    gh_mock = tmp_path / "gh.cmd"
    gh_mock.write_text(
        f'@echo {{"headRefName":"{work_branch}",'
        '"headRefOid":"current-head","baseRefName":"main","state":"OPEN"}\n',
        encoding="utf-8",
    )
    mock_env = {"PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}"}
    for red_gate in ("full_regression_pass", "final_audit_pass", "ci_pass"):
        gates = {
            "full_regression_pass": True,
            "final_audit_pass": True,
            "ci_pass": True,
        }
        gates[red_gate] = False
        _write_state(
            state_path,
            phase="FINAL_GIT",
            gates=gates,
            external_review={
                "status": "PASS",
                "round": 1,
                "reviewed_head": "current-head",
                "blocking_findings": [],
                "last_checked_at": "2026-08-22T00:00:00Z",
            },
        )
        assert guard("gh pr merge 999 --squash", mock_env)["permission"] == "deny"
        assert guard("gh.exe pr merge 999 --squash", mock_env)["permission"] == "deny"
    _write_state(
        state_path,
        phase="FINAL_GIT",
        human_gate=True,
        gates={
            "full_regression_pass": True,
            "final_audit_pass": True,
            "ci_pass": True,
        },
        external_review={
            "status": "PASS",
            "round": 1,
            "reviewed_head": "current-head",
            "blocking_findings": [],
            "last_checked_at": "2026-08-22T00:00:00Z",
        },
    )
    assert guard("gh pr merge 999 --squash", mock_env)["permission"] == "deny"

    for status in ("NOT_REQUESTED", "PENDING", "FINDINGS", "STALE"):
        _write_state(
            state_path,
            phase="FINAL_GIT",
            gates={
                "full_regression_pass": True,
                "final_audit_pass": True,
                "ci_pass": True,
            },
            external_review={
                "status": status,
                "round": 1,
                "reviewed_head": "current-head",
                "blocking_findings": [],
                "last_checked_at": "2026-08-22T00:00:00Z",
            },
        )
        assert guard("gh pr merge 999 --squash", mock_env)["permission"] == "deny"

    _write_state(
        state_path,
        phase="FINAL_GIT",
        gates={
            "full_regression_pass": True,
            "final_audit_pass": True,
            "ci_pass": True,
        },
        external_review={
            "status": "PASS",
            "round": 1,
            "reviewed_head": "old-head",
            "blocking_findings": [],
            "last_checked_at": "2026-08-22T00:00:00Z",
        },
    )
    assert guard("gh pr merge 999 --squash", mock_env)["permission"] == "deny"

    _write_state(
        state_path,
        phase="FINAL_GIT",
        gates={
            "full_regression_pass": True,
            "final_audit_pass": True,
            "ci_pass": True,
        },
        external_review={
            "status": "PASS",
            "round": 1,
            "reviewed_head": "current-head",
            "blocking_findings": ["unresolved-current-head-finding"],
            "last_checked_at": "2026-08-22T00:00:00Z",
        },
    )
    assert guard("gh pr merge 999 --squash", mock_env)["permission"] == "deny"

    for status in ("PASS", "UNAVAILABLE", "LIMIT_REACHED", "DISABLED"):
        _write_state(
            state_path,
            phase="FINAL_GIT",
            gates={
                "full_regression_pass": True,
                "final_audit_pass": True,
                "ci_pass": True,
            },
            external_review={
                "status": status,
                "round": 1,
                "reviewed_head": "current-head" if status == "PASS" else None,
                "blocking_findings": [],
                "last_checked_at": "2026-08-22T00:00:00Z",
            },
        )
        assert guard("gh pr merge 999 --squash", mock_env)["permission"] == "allow"
        if status == "PASS":
            assert guard("gh.exe pr merge 999 --squash", mock_env)["permission"] == "allow"
    for invalid in (
        {"round": 1, "reviewed_head": None, "blocking_findings": []},
        {"round": 2, "reviewed_head": "old-head", "blocking_findings": []},
        {"round": 2, "reviewed_head": None, "blocking_findings": ["still open"]},
    ):
        _write_state(
            state_path,
            phase="FINAL_GIT",
            gates={
                "full_regression_pass": True,
                "final_audit_pass": True,
                "ci_pass": True,
            },
            external_review={
                "status": "BOUNDED_COMPLETE",
                "last_checked_at": "2026-08-22T00:00:00Z",
                **invalid,
            },
        )
        assert guard("gh pr merge 999 --squash", mock_env)["permission"] == "deny"
    _write_state(
        state_path,
        phase="FINAL_GIT",
        gates={
            "full_regression_pass": True,
            "final_audit_pass": True,
            "ci_pass": True,
        },
        external_review={
            "status": "BOUNDED_COMPLETE",
            "round": 2,
            "reviewed_head": None,
            "blocking_findings": [],
            "last_checked_at": "2026-08-22T00:00:00Z",
        },
    )
    assert guard("gh pr merge 999 --squash", mock_env)["permission"] == "allow"
    assert guard("gh pr merge 999 --merge", mock_env)["permission"] == "deny"
    assert guard("gh pr merge 999 --admin")["permission"] == "deny"

    gh_mock.write_text(
        '@echo {"headRefName":"feature/other","headRefOid":"current-head",'
        '"baseRefName":"main","state":"OPEN"}\n',
        encoding="utf-8",
    )
    assert guard("gh pr merge 999 --squash", mock_env)["permission"] == "deny"


def test_workflow_lifecycle_dry_run_uses_only_declared_state_contract(tmp_path: Path) -> None:
    config = _config()
    declared_phases = set(config["workflow_contract"]["phases"])
    lifecycle = [
        "PLAN",
        "IMPLEMENT",
        "REVIEW",
        "CHECKPOINT_GIT",
        "FULL_REGRESSION",
        "FINAL_AUDIT",
        "FINAL_GIT",
    ]
    assert set(lifecycle) <= declared_phases
    template = json.loads(_read(RUNTIME_TEMPLATE))
    assert template["external_review"] == {
        "status": "NOT_REQUESTED",
        "round": 0,
        "reviewed_head": None,
        "blocking_findings": [],
        "last_checked_at": None,
    }

    state_path = tmp_path / "dry-run.json"
    for phase in lifecycle:
        state = _write_state(state_path, phase=phase, next_action=f"simulate {phase}")
        observed = json.loads(state_path.read_text(encoding="utf-8"))
        assert observed == state
        assert observed["status"] == "RUNNING"

    final = _write_state(
        state_path,
        status="DONE",
        phase="FINAL_GIT",
        next_action=None,
        gates={
            "full_regression_pass": True,
            "final_audit_pass": True,
            "ci_pass": True,
        },
        external_review={
            "status": "PASS",
            "round": 1,
            "reviewed_head": "final-head",
            "blocking_findings": [],
            "last_checked_at": "2026-08-22T00:00:00Z",
        },
    )
    assert final["status"] in config["workflow_contract"]["statuses"]
    state_path.unlink()
    assert not state_path.exists()
