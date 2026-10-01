from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
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


def _invoke_hook(
    script: str,
    payload: str | bytes,
    *,
    state_path: Path,
    log_path: Path | None = None,
    env_overrides: dict[str, str] | None = None,
    text: bool | None = None,
    cwd: Path = ROOT,
) -> subprocess.CompletedProcess[str] | subprocess.CompletedProcess[bytes]:
    env = os.environ.copy()
    env["QMTOOL_WORKFLOW_STATE_PATH"] = str(state_path)
    if log_path is not None:
        env["QMTOOL_RUNTIME_LOG_PATH"] = str(log_path)
    if env_overrides:
        env.update(env_overrides)
    if text is None:
        text = isinstance(payload, str)
    return subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(HOOKS / script),
        ],
        cwd=cwd,
        input=payload,
        capture_output=True,
        text=text,
        env=env,
        check=False,
    )


def _expected_subagent_start_exit_code(
    payload: dict[str, Any],
    result: dict[str, Any],
) -> int:
    if "validation_mode" in payload:
        return 0
    permission = result.get("permission")
    if permission == "deny":
        return 2
    if permission == "allow":
        return 0
    return 0


def _assert_subagent_start_exit_code(
    completed: subprocess.CompletedProcess[str] | subprocess.CompletedProcess[bytes],
    payload: dict[str, Any],
    result: dict[str, Any],
) -> None:
    expected = _expected_subagent_start_exit_code(payload, result)
    detail = completed.stderr or completed.stdout
    if isinstance(detail, bytes):
        detail = detail.decode("utf-8", errors="replace")
    assert completed.returncode == expected, detail


def _run_hook(
    script: str,
    payload: dict[str, Any],
    *,
    state_path: Path,
    log_path: Path | None = None,
    env_overrides: dict[str, str] | None = None,
    cwd: Path = ROOT,
) -> dict[str, Any]:
    completed = _invoke_hook(
        script,
        json.dumps(payload),
        state_path=state_path,
        log_path=log_path,
        env_overrides=env_overrides,
        text=True,
        cwd=cwd,
    )
    output = completed.stdout.strip()
    assert output, f"{script} returned no JSON"
    result = json.loads(output)
    if script == "subagent-start.ps1":
        _assert_subagent_start_exit_code(completed, payload, result)
    else:
        assert completed.returncode == 0, completed.stderr
    return result


def _live_host_subagent_payload(**updates: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "hook_event_name": "subagentStart",
        "subagent_type": "checkpoint-reviewer",
        "model": "composer-2.5",
        "subagent_model": "composer-2.5",
        "subagent_id": "6c08bef5-635a-4265-b0c5-06e4806a9729",
        "tool_call_id": "tool-call-1",
        "parent_conversation_id": "parent-conversation-1",
        "is_parallel_worker": False,
        "task": "[ROLE:checkpoint-reviewer]\nReview",
    }
    payload.update(updates)
    return payload


def _pre_tool_use_task_payload(**updates: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "hook_event_name": "preToolUse",
        "tool_name": "Task",
        "tool_use_id": "tool-use-1",
        "conversation_id": "conversation-1",
        "model": "composer-2.5",
        "tool_input": {
            "prompt": "[ROLE:checkpoint-reviewer]\nReview",
            "model": "grok-4.7-high",
            "subagent_type": "checkpoint-reviewer",
        },
    }
    payload.update(updates)
    return payload


def _native_cursor_workspace_root(root: Path = ROOT) -> str:
    path_without_drive = str(root)[len(root.drive) :].replace("\\", "/")
    return f"/{root.drive[0].lower()}:{path_without_drive}"


def test_config_agents_skills_rules_and_worktree_contracts() -> None:
    config = _config()
    defaults = config["defaults"]
    assert config["profile"] == "cursor-first"
    assert config["version"] == 3
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
    steward = _read(AGENTS / "git-steward.md")
    assert "finalization commit" in steward
    assert "working_directory" in steward
    assert "does not imply push" in steward
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
    assert hooks["hooks"]["beforeShellExecution"][0]["matcher"] == "(?:[gG][iI][tT]|[gG][hH])"
    hooks_text = _read(CURSOR / "hooks.json")
    assert "(?i)" not in hooks_text

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


def test_hooks_json_pre_tool_use_task_guard_binding() -> None:
    hooks = json.loads(_read(CURSOR / "hooks.json"))
    pre_tool_use = hooks["hooks"]["preToolUse"]
    assert len(pre_tool_use) == 1
    entry = pre_tool_use[0]
    assert (
        entry["command"]
        == 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".cursor/hooks/subagent-start.ps1"; exit $LASTEXITCODE'
    )
    assert entry["matcher"] == "^Task$"
    assert entry["timeout"] == 10
    assert entry["failClosed"] is True

    subagent_start = hooks["hooks"]["subagentStart"]
    assert len(subagent_start) == 1
    assert (
        subagent_start[0]["command"]
        == 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".cursor/hooks/subagent-start.ps1"; exit $LASTEXITCODE'
    )
    assert subagent_start[0]["timeout"] == 10
    assert subagent_start[0]["failClosed"] is True

    git_guard = hooks["hooks"]["beforeShellExecution"][0]
    assert git_guard["timeout"] == 30
    assert git_guard["matcher"] == "(?:[gG][iI][tT]|[gG][hH])"
    assert git_guard["failClosed"] is True


def test_pre_tool_use_task_guard_normalizes_child_model_and_correlation(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "state.json"
    log_path = tmp_path / "subagent.log"

    allowed = _run_hook(
        "subagent-start.ps1",
        _pre_tool_use_task_payload(),
        state_path=state_path,
        log_path=log_path,
    )
    assert allowed["permission"] == "allow"

    denied = _run_hook(
        "subagent-start.ps1",
        _pre_tool_use_task_payload(
            tool_input={
                "prompt": "[ROLE:checkpoint-reviewer]\nReview",
                "model": "composer-2.5",
                "subagent_type": "checkpoint-reviewer",
            }
        ),
        state_path=state_path,
        log_path=log_path,
    )
    assert denied["permission"] == "deny"
    assert "grok-4.7-high" in denied["user_message"]

    parent_grok_child_composer = _run_hook(
        "subagent-start.ps1",
        _pre_tool_use_task_payload(
            model="grok-4.7-high",
            tool_input={
                "prompt": "[ROLE:checkpoint-reviewer]\nReview",
                "model": "composer-2.5",
                "subagent_type": "checkpoint-reviewer",
            },
        ),
        state_path=state_path,
        log_path=log_path,
    )
    assert parent_grok_child_composer["permission"] == "deny"

    untagged = _run_hook(
        "subagent-start.ps1",
        _pre_tool_use_task_payload(
            tool_input={
                "prompt": "plain helper without role marker",
                "subagent_type": "generalPurpose",
            }
        ),
        state_path=state_path,
        log_path=log_path,
    )
    assert untagged["permission"] == "allow"
    assert untagged["non_authoritative"] is True
    assert untagged["gate_budget_authority"] is False

    fail_closed_cases = [
        _pre_tool_use_task_payload(tool_input="not-an-object"),
        _pre_tool_use_task_payload(tool_input={"model": "grok-4.7-high"}),
        _pre_tool_use_task_payload(
            tool_input={
                "prompt": "[ROLE:checkpoint-reviewer]\nReview",
                "subagent_type": "checkpoint-reviewer",
            }
        ),
        _pre_tool_use_task_payload(tool_use_id=""),
        _pre_tool_use_task_payload(
            tool_input={
                "prompt": "[ROLE:checkpoint-reviewer]\nReview",
                "model": "grok-4.7-high",
                "subagent_type": "checkpoint-reviewer",
            },
            conversation_id="",
        ),
        _pre_tool_use_task_payload(
            tool_input={
                "prompt": "[role:checkpoint-reviewer]\nReview",
                "model": "grok-4.7-high",
                "subagent_type": "checkpoint-reviewer",
            }
        ),
    ]
    for payload in fail_closed_cases:
        result = _run_hook(
            "subagent-start.ps1",
            payload,
            state_path=state_path,
            log_path=log_path,
        )
        assert result["permission"] == "deny"

    records = [
        json.loads(line) for line in log_path.read_text(encoding="utf-8-sig").splitlines()
    ]
    event = next(record for record in records if record.get("event_name") == "preToolUse")
    assert event["subagent_model"] == "grok-4.7-high"
    assert event["tool_call_id"] == "tool-use-1"
    assert event["parent_conversation_id"] == "conversation-1"
    assert event["allowed"] is True


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
    assert untagged["non_authoritative"] is True
    assert untagged["gate_budget_authority"] is False

    records = [json.loads(line) for line in log_path.read_text(encoding="utf-8-sig").splitlines()]
    assert all(record["observation"] == "host_payload_decoded" for record in records[0::2])
    tagged_log = records[1]
    assert tagged_log["event_name"] == "subagentStart"
    assert tagged_log["subagent_model"] == "composer-2.5[fast=false]"
    assert tagged_log["allowed"] is True
    denied_log = records[3]
    assert denied_log["allowed"] is False
    untagged_log = records[5]
    assert untagged_log["role"] == "UNOBSERVED_INTERNAL_HELPER"
    assert untagged_log["actual_model"] == "inherit"
    assert "task_short" not in untagged_log
    assert untagged_log["allowed"] is True
    assert untagged_log["non_authoritative"] is True

    reviewer_task = "[ROLE:checkpoint-reviewer]\nReview"
    reviewer_identity = {"child_agent_id": "child-1", "task_id": "task-1"}

    legacy_xhigh = _run_hook(
        "subagent-start.ps1",
        {"task": reviewer_task, "subagent_model": "grok-4.7-xhigh", **reviewer_identity},
        state_path=state_path,
        log_path=log_path,
    )
    assert legacy_xhigh["permission"] == "deny"

    fast_denied = _run_hook(
        "subagent-start.ps1",
        {
            "task": reviewer_task,
            "subagent_model": "grok-4.7-xhigh-fast",
            **reviewer_identity,
        },
        state_path=state_path,
        log_path=log_path,
    )
    assert fast_denied["permission"] == "deny"

    missing_identity = _run_hook(
        "subagent-start.ps1",
        {"task": reviewer_task, "subagent_model": "grok-4.7-high"},
        state_path=state_path,
        log_path=log_path,
    )
    assert missing_identity["permission"] == "deny"

    ladder_high = _run_hook(
        "subagent-start.ps1",
        {"task": reviewer_task, "subagent_model": "grok-4.7-high", **reviewer_identity},
        state_path=state_path,
        log_path=log_path,
    )
    assert ladder_high["permission"] == "allow"

    ladder_rung2_without_history = _run_hook(
        "subagent-start.ps1",
        {
            "task": reviewer_task,
            "subagent_model": "cursor-grok-4.6-xhigh",
            **reviewer_identity,
        },
        state_path=state_path,
        log_path=log_path,
    )
    assert ladder_rung2_without_history["permission"] == "deny"

    ladder_history = [
        {
            "attempt": 1,
            "role": "checkpoint-reviewer",
            "requested_model": "grok-4.7-high",
            "result_category": "UNAVAILABLE",
            "agent_id": "agent-1",
            "signal": "explicit unavailability",
        }
    ]
    ladder_rung2 = _run_hook(
        "subagent-start.ps1",
        {
            "task": reviewer_task,
            "subagent_model": "cursor-grok-4.6-xhigh",
            "ladder_history": ladder_history,
            **reviewer_identity,
        },
        state_path=state_path,
        log_path=log_path,
    )
    assert ladder_rung2["permission"] == "allow"

    ladder_gpt_without_history = _run_hook(
        "subagent-start.ps1",
        {
            "task": reviewer_task,
            "subagent_model": "gpt-5.6-terra-high",
            **reviewer_identity,
        },
        state_path=state_path,
        log_path=log_path,
    )
    assert ladder_gpt_without_history["permission"] == "deny"

    random_gpt = _run_hook(
        "subagent-start.ps1",
        {
            "task": reviewer_task,
            "subagent_model": "gpt-5.6-sol",
            **reviewer_identity,
        },
        state_path=state_path,
        log_path=log_path,
    )
    assert random_gpt["permission"] == "deny"

    string_fast = _run_hook(
        "subagent-start.ps1",
        {
            "task": reviewer_task,
            "subagent_model": "grok-4.7-high",
            "model_params": {"fast": "true"},
            **reviewer_identity,
        },
        state_path=state_path,
        log_path=log_path,
    )
    assert string_fast["permission"] == "deny"


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
        command: str,
        env_overrides: dict[str, str] | None = None,
        cwd: Path = ROOT,
    ) -> dict[str, Any]:
        return _run_hook(
            "git-guard.ps1",
            {"command": command, "cwd": str(cwd), "sandbox": False},
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
    assert guard("git add expected.py", cwd=ROOT / "tests")["permission"] == "allow"
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
    gh_mock = tmp_path / "gh.cmd"
    gh_mock.write_text(
        f'@echo {{"headRefName":"{work_branch}",'
        '"headRefOid":"current-head","baseRefName":"main","state":"OPEN"}\n',
        encoding="utf-8",
    )
    mock_env = {"PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}"}
    assert (
        guard('gh pr comment 999 --body "@codex review"', mock_env)["permission"]
        == "allow"
    )
    reserved = json.loads(state_path.read_text(encoding="utf-8"))
    assert reserved["external_review"]["status"] == "PENDING"
    assert reserved["external_review"]["round"] == 1
    assert reserved["external_review"]["reviewed_head"] is None
    assert reserved["external_review"]["blocking_findings"] == []
    assert reserved["external_review"]["last_checked_at"]
    assert guard('gh pr comment 999 --body "@codex review"', mock_env)["permission"] == "deny"
    assert guard('gh.exe pr comment 999 --body "@codex review"', mock_env)["permission"] == "deny"
    _write_state(state_path, phase="FINAL_GIT")
    with ThreadPoolExecutor(max_workers=2) as executor:
        parallel = list(
            executor.map(
                lambda command: guard(command, mock_env),
                (
                    'gh pr comment 999 --body "@codex review"',
                    'gh.exe pr comment 999 --body "@codex review"',
                ),
            )
        )
    assert sorted(result["permission"] for result in parallel) == ["allow", "deny"]
    reserved = json.loads(state_path.read_text(encoding="utf-8"))
    assert reserved["external_review"]["status"] == "PENDING"
    assert reserved["external_review"]["round"] == 1
    assert guard('gh pr comment 999 --body "general comment"')["permission"] == "deny"
    assert guard('gh.exe pr comment 999 --body "general comment"')["permission"] == "deny"
    _write_state(state_path, phase="FINAL_GIT")
    assert guard('gh.exe pr comment 999 --body "@codex review"', mock_env)["permission"] == "allow"
    for metadata in (
        {"headRefName": "feature/other", "baseRefName": "main", "state": "OPEN"},
        {"headRefName": work_branch, "baseRefName": "other", "state": "OPEN"},
        {"headRefName": work_branch, "baseRefName": "main", "state": "CLOSED"},
    ):
        expected_state = _write_state(state_path, phase="FINAL_GIT")
        gh_mock.write_text(
            "@echo " + json.dumps({**metadata, "headRefOid": "current-head"}) + "\n",
            encoding="utf-8",
        )
        assert guard('gh pr comment 999 --body "@codex review"', mock_env)["permission"] == "deny"
        assert json.loads(state_path.read_text(encoding="utf-8")) == expected_state
    gh_mock.write_text(
        f'@echo {{"headRefName":"{work_branch}",'
        '"headRefOid":"current-head","baseRefName":"main","state":"OPEN"}\n',
        encoding="utf-8",
    )
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
            "round": 1,
            "reviewed_head": "old-head",
            "blocking_findings": [],
            "last_checked_at": "2026-08-22T00:00:00Z",
        },
    )
    assert guard('gh pr comment 999 --body "@codex review"', mock_env)["permission"] == "allow"
    reserved = json.loads(state_path.read_text(encoding="utf-8"))
    assert reserved["external_review"]["status"] == "PENDING"
    assert reserved["external_review"]["round"] == 2
    assert guard('gh pr comment 999 --body "@codex review"', mock_env)["permission"] == "deny"
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
    assert guard('gh pr comment 999 --body "@codex review"', mock_env)["permission"] == "deny"

    _write_state(
        state_path,
        phase="FINAL_GIT",
        gates={
            "full_regression_pass": True,
            "final_audit_pass": True,
            "ci_pass": True,
        },
    )
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


def _invoke_git_guard_ingress(
    payload: str | bytes,
    *,
    state_path: Path,
    text: bool | None = None,
) -> tuple[subprocess.CompletedProcess[str] | subprocess.CompletedProcess[bytes], dict[str, Any] | None]:
    if text is None:
        text = isinstance(payload, str)
    completed = _invoke_hook(
        "git-guard.ps1",
        payload,
        state_path=state_path,
        text=text,
    )
    output = completed.stdout.strip() if text else completed.stdout.decode("utf-8", errors="replace").strip()
    if not output:
        return completed, None
    return completed, json.loads(output)


def _hook_stderr_text(
    completed: subprocess.CompletedProcess[str] | subprocess.CompletedProcess[bytes],
) -> str:
    detail = completed.stderr
    if not detail:
        return ""
    if isinstance(detail, bytes):
        return detail.decode("utf-8", errors="replace")
    return detail


def test_git_guard_host_ingress_fail_closed(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    valid_read = {
        "command": "git status --short --branch",
        "cwd": str(ROOT),
        "sandbox": False,
    }
    completed, result = _invoke_git_guard_ingress(json.dumps(valid_read), state_path=state_path)
    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert result is not None
    assert result["permission"] == "allow"

    valid_write = _write_state(state_path, phase="CHECKPOINT_GIT")
    del valid_write
    completed, result = _invoke_git_guard_ingress(
        json.dumps(
            {
                "command": 'git commit -m "checkpoint"',
                "cwd": str(ROOT),
                "sandbox": False,
            }
        ),
        state_path=state_path,
    )
    assert completed.returncode == 0
    assert result is not None
    assert result["permission"] == "allow"

    deny_cases: list[tuple[bytes | str, bool | None, str]] = [
        (b"", False, "Hook payload was empty or unreadable."),
        (b"   \r\n", False, "Hook payload was empty or unreadable."),
        (b"{not-json", False, "Hook payload could not be parsed as JSON."),
        (b"\xef\xbb\xbf{", False, "Hook payload could not be parsed as JSON."),
        (json.dumps("scalar"), True, "Hook payload must be a JSON object."),
        (json.dumps([]), True, "Hook payload must be a JSON object."),
        (json.dumps({"cwd": str(ROOT)}), True, "Hook payload is missing command."),
        (json.dumps({"command": "git status"}), True, "Hook payload is missing cwd."),
    ]
    for payload, text, expected_reason in deny_cases:
        completed, result = _invoke_git_guard_ingress(payload, state_path=state_path, text=text)
        assert completed.returncode == 1, payload
        assert result is not None
        assert result["permission"] == "deny"
        assert result["user_message"] == expected_reason
        assert expected_reason in _hook_stderr_text(completed)

    utf16_payload = json.dumps(
        {"command": "git status", "cwd": str(ROOT), "sandbox": False}
    )
    utf16_bytes = b"\xff\xfe" + utf16_payload.encode("utf-16-le")
    completed, result = _invoke_git_guard_ingress(utf16_bytes, state_path=state_path, text=False)
    assert completed.returncode == 0
    assert result is not None
    assert result["permission"] == "allow"

    bom_payload = b"\xef\xbb\xbf" + json.dumps(
        {"command": "git status", "cwd": str(ROOT), "sandbox": False}
    ).encode("utf-8")
    completed, result = _invoke_git_guard_ingress(bom_payload, state_path=state_path, text=False)
    assert completed.returncode == 0
    assert result is not None
    assert result["permission"] == "allow"


def test_git_guard_denies_local_pr_review_and_mutating_review_apis(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    _write_state(state_path, phase="FINAL_GIT")

    def guard(command: str) -> dict[str, Any]:
        return _run_hook(
            "git-guard.ps1",
            {"command": command, "cwd": str(ROOT), "sandbox": False},
            state_path=state_path,
        )

    reviews = "repos/layzieshin/QMToolV7/pulls/30/reviews"
    pull = "repos/layzieshin/QMToolV7/pulls/30"
    embedded_foo = "repos/layzieshin/QMToolV7/repo-with-foo/pulls/30"
    guard_cases: list[tuple[str, str]] = [
        ("gh pr review 999 --approve", "deny"),
        ("gh pr review 999 --comment -b ok", "deny"),
        (f"gh api --method POST {reviews} -f event=APPROVE", "deny"),
        (
            "gh api repos/layzieshin/QMToolV7/pulls/30/reviews/1/dismissals --method PUT",
            "deny",
        ),
        (f"gh api {reviews} --method=POST -f event=APPROVE", "deny"),
        (f"gh api {reviews} -XPOST -f event=APPROVE", "deny"),
        (f"gh api {reviews} -fevent=APPROVE", "deny"),
        (f"gh api {reviews} -Fevent=APPROVE", "deny"),
        (f"gh api {reviews} -f event=APPROVE", "deny"),
        (f"gh api {reviews} -F event=APPROVE", "deny"),
        (f'gh api {reviews} -f"event=APPROVE"', "deny"),
        (f"gh api {reviews} -f'event=APPROVE'", "deny"),
        (f"gh api {reviews} -f`event=APPROVE`", "deny"),
        (f"gh api {reviews} -f=event=APPROVE", "deny"),
        (f"gh api {reviews} -f123=value", "deny"),
        (f"gh api {reviews} -f_field=value", "deny"),
        (f'gh api {reviews} -F"event=APPROVE"', "deny"),
        (f"gh api {reviews} -F'event=APPROVE'", "deny"),
        (f"gh api {reviews} -F`event=APPROVE`", "deny"),
        (f"gh api {reviews} -F=event=APPROVE", "deny"),
        (f"gh api {reviews} -F123=value", "deny"),
        (f"gh api {reviews} -F_field=value", "deny"),
        (f"gh api {reviews} -f", "deny"),
        (f"gh api {reviews} -F", "deny"),
        (f"gh api {reviews} --field event=APPROVE", "deny"),
        (f"gh api {reviews} --field=event=APPROVE", "deny"),
        (f"gh api {reviews} --raw-field event=APPROVE", "deny"),
        (f"gh api {reviews} --raw-field=event=APPROVE", "deny"),
        (f"gh api {reviews} --input payload.json", "deny"),
        (f"gh api {pull} --method GET", "allow"),
        (f"gh api {pull} --method=GET", "allow"),
        (f"gh api {pull} -XGET", "allow"),
        (f"gh api {pull} -X=GET", "allow"),
        (f"gh api {pull}", "allow"),
        (f"gh api {embedded_foo}", "allow"),
        (f"gh api {pull} -X=POST", "deny"),
        (f"gh api {pull} -X=TRACE", "deny"),
        (f"gh api {reviews} --method GET-FOO", "deny"),
        (f"gh api {reviews} --method=GET-FOO", "deny"),
        (f"gh api {pull} --method GET-FOO", "deny"),
        (f"gh api {pull} --method=GET-FOO", "deny"),
        (f"gh api {pull} -XGET-FOO", "deny"),
        (f"gh api {pull} -X GET-FOO", "deny"),
        (f"gh api {pull} -X=GET-FOO", "deny"),
        ('gh api repos/layzieshin/QMToolV7/pulls/30 --method "POST"', "deny"),
        (f'gh api {reviews} -X"POST" -f event=APPROVE', "deny"),
        (f"gh api {pull} --method GET --method POST", "deny"),
        (f"gh api {pull} --method", "deny"),
        (f"gh api {pull} -X", "deny"),
        (f"gh api {pull} --method GET --method=GET -XGET", "allow"),
    ]
    for command, expected in guard_cases:
        assert guard(command)["permission"] == expected, command
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


def test_w1_allowlist_includes_hooks_json() -> None:
    allowlist = _config()["external_codex_bound_review"]["w1_allowlist_paths"]
    assert len(allowlist) == 21
    assert ".cursor/hooks.json" in allowlist


def test_cost_profile_documents_grok_high_routine_reviews() -> None:
    cost_profile = _read(ROOT / "docs" / "AP-029_AGENT_WORKFLOW_COST_PROFILE.md")
    assert "grok-4.7-high" in cost_profile
    assert "runtime_reasoning=high" in cost_profile
    assert "R-COST-04" in cost_profile
    assert "`grok-4.7-high` with `runtime_reasoning=high` allowed" in cost_profile
    assert "W1-CORRECTIVE-WRITER" in cost_profile
    assert "exact 21 paths" in cost_profile
    assert ".cursor/hooks.json" in cost_profile


def test_subagent_hook_denies_malformed_role_markers(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    cases = [
        "prefix [ROLE:implementer]\nwork",
        "[ROLE:checkpoint-reviewer ]\nwork",
        "[ROLE:UNKNOWN-ROLE]\nwork",
        "[ROLE:UNOBSERVED_INTERNAL_HELPER]\nwork",
        "work\n[ROLE:implementer]",
        "[ROLE:implementer]\n[ROLE:checkpoint-reviewer]\nwork",
        "[role:implementer]\nwork",
        "[ROLE:Implementer]\nwork",
        "[ROLE:implementer\nwork",
        "[ROLE :implementer]\nwork",
        "[ROLE: implementer]\nwork",
        "[ROLE:\timplementer]\nwork",
    ]
    for task in cases:
        result = _run_hook(
            "subagent-start.ps1",
            {"task": task, "subagent_model": "composer-2.5[]"},
            state_path=state_path,
        )
        assert result["permission"] == "deny"


def test_subagent_hook_allows_untagged_helper_control(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    result = _run_hook(
        "subagent-start.ps1",
        {"task": "plain helper without role marker", "subagent_model": "inherit"},
        state_path=state_path,
    )
    assert result["permission"] == "allow"
    assert result["non_authoritative"] is True


def test_subagent_hook_native_identity_contradiction_denied(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    reviewer_task = "[ROLE:checkpoint-reviewer]\nReview"
    contradictory = {
        "hook_event_name": "subagentStart",
        "subagent_type": "checkpoint-reviewer",
        "task": reviewer_task,
        "subagent_model": "grok-4.7-high",
        "subagent_id": "native-child-1",
        "tool_call_id": "native-task-1",
        "parent_conversation_id": "parent-1",
        "is_parallel_worker": False,
        "child_agent_id": "other-child",
        "task_id": "native-task-1",
    }
    result = _run_hook("subagent-start.ps1", contradictory, state_path=state_path)
    assert result["permission"] == "deny"


def test_subagent_hook_native_identity_requires_native_fields(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    reviewer_task = "[ROLE:checkpoint-reviewer]\nReview"
    native_payload = {
        "hook_event_name": "subagentStart",
        "subagent_type": "checkpoint-reviewer",
        "task": reviewer_task,
        "subagent_model": "grok-4.7-high",
        "subagent_id": "native-child-1",
        "tool_call_id": "native-task-1",
        "parent_conversation_id": "parent-1",
        "is_parallel_worker": False,
    }
    allowed = _run_hook("subagent-start.ps1", native_payload, state_path=state_path)
    assert allowed["permission"] == "allow"

    required_fields = (
        "task",
        "subagent_type",
        "subagent_id",
        "tool_call_id",
        "parent_conversation_id",
        "subagent_model",
        "is_parallel_worker",
    )
    for field in required_fields:
        missing_native = dict(native_payload)
        del missing_native[field]
        denied = _run_hook("subagent-start.ps1", missing_native, state_path=state_path)
        assert denied["permission"] == "deny", field

    invalid_parallel = dict(native_payload)
    invalid_parallel["is_parallel_worker"] = "false"
    denied_parallel = _run_hook(
        "subagent-start.ps1", invalid_parallel, state_path=state_path
    )
    assert denied_parallel["permission"] == "deny"


def test_subagent_hook_live_host_utf8_bom_ingress(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    log_path = tmp_path / "subagent.log"
    payload = _live_host_subagent_payload()
    completed = _invoke_hook(
        "subagent-start.ps1",
        b"\xef\xbb\xbf" + json.dumps(payload).encode("utf-8"),
        state_path=state_path,
        log_path=log_path,
        text=False,
    )
    result = json.loads(completed.stdout.decode("utf-8").strip())
    assert result["permission"] == "deny"
    assert "grok-4.7-high" in result["user_message"]
    _assert_subagent_start_exit_code(completed, payload, result)

    lines = log_path.read_text(encoding="utf-8-sig").splitlines()
    ingress = json.loads(lines[0])
    assert ingress["observation"] == "host_payload_decoded"
    assert ingress["hook_event_name"] == "subagentStart"
    assert ingress["subagent_type"] == "checkpoint-reviewer"
    assert ingress["ingress_bytes"] == len(b"\xef\xbb\xbf" + json.dumps(payload).encode("utf-8"))


def test_subagent_hook_live_host_native_payload_shape(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    log_path = tmp_path / "subagent.log"
    payload = _live_host_subagent_payload(
        workspace_roots=[_native_cursor_workspace_root()],
        subagent_model="grok-4.7-high",
        model="grok-4.7-high",
    )
    completed = _invoke_hook(
        "subagent-start.ps1",
        json.dumps(payload).encode("utf-8"),
        state_path=state_path,
        log_path=log_path,
        text=False,
    )
    result = json.loads(completed.stdout.decode("utf-8").strip())
    assert result["permission"] == "allow"
    assert completed.returncode == 0, completed.stderr or completed.stdout
    _assert_subagent_start_exit_code(completed, payload, result)

    ingress = json.loads(log_path.read_text(encoding="utf-8-sig").splitlines()[0])
    assert ingress["model_field_present"] is True
    assert ingress["subagent_model_present"] is True
    assert ingress["subagent_id_present"] is True
    assert ingress["tool_call_id_present"] is True
    assert ingress["parent_conversation_id_present"] is True
    assert ingress["is_parallel_worker_present"] is True


def test_subagent_hook_native_workspace_root_drive_prefix_denies_unauthorized_model(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "state.json"
    log_path = tmp_path / "subagent.log"
    payload = _live_host_subagent_payload(
        workspace_roots=[_native_cursor_workspace_root()],
        subagent_model="composer-2.5",
        model="composer-2.5",
        parent_conversation_id="e426675b-3888-43d4-b7b3-da2444d00fba",
        subagent_id="4d01d1bf-2885-4f82-89b1-03a7438a04be",
    )
    completed = _invoke_hook(
        "subagent-start.ps1",
        json.dumps(payload).encode("utf-8"),
        state_path=state_path,
        log_path=log_path,
        text=False,
    )
    stdout = completed.stdout.decode("utf-8").strip()
    assert stdout, "expected deny JSON on stdout"
    result = json.loads(stdout)
    assert result["permission"] == "deny"
    assert "composer-2.5" in result["user_message"]
    assert completed.returncode == 2, completed.stderr or stdout
    _assert_subagent_start_exit_code(completed, payload, result)

    lines = log_path.read_text(encoding="utf-8-sig").splitlines()
    ingress = json.loads(lines[0])
    assert ingress["observation"] == "host_payload_decoded"
    event = json.loads(lines[1])
    assert event["workspace_match"] is True
    assert event["allowed"] is False
    assert event["parent_conversation_id"] == "e426675b-3888-43d4-b7b3-da2444d00fba"
    assert event["subagent_id"] == "4d01d1bf-2885-4f82-89b1-03a7438a04be"


def test_subagent_hook_malformed_workspace_root_fail_closed(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    malformed_root = f"\\{ROOT.drive[0].lower()}:{str(ROOT)[len(ROOT.drive) :]}"
    payload = _live_host_subagent_payload(
        workspace_roots=[malformed_root],
        subagent_model="composer-2.5",
        model="composer-2.5",
    )
    completed = _invoke_hook(
        "subagent-start.ps1",
        json.dumps(payload).encode("utf-8"),
        state_path=state_path,
        text=False,
    )
    assert completed.returncode != 0, completed.stderr or completed.stdout
    stdout = completed.stdout.decode("utf-8", errors="replace").strip()
    assert stdout, "expected generic deny JSON on stdout"
    result = json.loads(stdout)
    assert result["permission"] == "deny"
    assert result["user_message"] == (
        "Subagent enforcement could not be completed safely."
    )
    assert "NotSupportedException" not in stdout
    assert "composer-2.5" not in stdout
    assert malformed_root not in stdout


def test_subagent_hook_ingress_rejects_non_object_top_level(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    cases = [
        json.dumps("scalar-string"),
        json.dumps(42),
        json.dumps(True),
        json.dumps(None),
        json.dumps([]),
        json.dumps([{"task": "x"}]),
    ]
    for payload in cases:
        completed = _invoke_hook(
            "subagent-start.ps1",
            payload,
            state_path=state_path,
            text=True,
        )
        assert completed.returncode != 0, payload
        output = completed.stdout.strip()
        assert output, f"expected deny JSON for {payload}"
        result = json.loads(output)
        assert result["permission"] == "deny", payload


def test_subagent_hook_ingress_parse_failure_fail_closed(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    cases = [
        (b"", "empty"),
        (b"\xef\xbb\xbf   \r\n", "whitespace"),
        (b"{not-json", "malformed"),
        (b"\xef\xbb\xbf{", "bom-only-prefix"),
    ]
    for stdin_bytes, label in cases:
        completed = _invoke_hook(
            "subagent-start.ps1",
            stdin_bytes,
            state_path=state_path,
            text=False,
        )
        assert completed.returncode != 0, label
        output = completed.stdout.decode("utf-8", errors="replace").strip()
        assert output, f"{label}: expected deny JSON on stdout"
        result = json.loads(output)
        assert result["permission"] == "deny", label


def test_subagent_hook_model_params_effort_binding(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    reviewer_task = "[ROLE:checkpoint-reviewer]\nReview"
    identity = {"child_agent_id": "child-1", "task_id": "task-1"}
    wrong_effort = _run_hook(
        "subagent-start.ps1",
        {
            "task": reviewer_task,
            "subagent_model": "grok-4.7-high",
            "model_params": {"effort": "xhigh"},
            **identity,
        },
        state_path=state_path,
    )
    assert wrong_effort["permission"] == "deny"

    bound_effort = _run_hook(
        "subagent-start.ps1",
        {
            "task": reviewer_task,
            "subagent_model": "grok-4.7-high",
            "model_params": {"effort": "high", "fast": False},
            **identity,
        },
        state_path=state_path,
    )
    assert bound_effort["permission"] == "allow"

    array_effort = _run_hook(
        "subagent-start.ps1",
        {
            "task": reviewer_task,
            "subagent_model": "grok-4.7-high",
            "model_params": [
                {"id": "effort", "value": "high"},
                {"id": "fast", "value": False},
            ],
            **identity,
        },
        state_path=state_path,
    )
    assert array_effort["permission"] == "allow"

    for fast_value in (True, "false", 0):
        rejected = _run_hook(
            "subagent-start.ps1",
            {
                "task": reviewer_task,
                "subagent_model": "grok-4.7-high",
                "model_params": {"fast": fast_value},
                **identity,
            },
            state_path=state_path,
        )
        assert rejected["permission"] == "deny", repr(fast_value)


def test_subagent_hook_model_denial_matrix(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    task = "[ROLE:checkpoint-reviewer]\nReview"
    denied_models = [
        "",
        "auto",
        "inherit",
        "gpt-5.6-terra",
        "grok-4.7-xhigh-fast",
        "grok-4.7[effort=xhigh,fast=true]",
        "grok-4.7[effort=high,fast=false]",
    ]
    for model in denied_models:
        result = _run_hook(
            "subagent-start.ps1",
            {"task": task, "subagent_model": model},
            state_path=state_path,
        )
        assert result["permission"] == "deny", model


def _substitute_ladder_result(
    history: list[dict[str, Any]], attempt: int, result_category: str
) -> list[dict[str, Any]]:
    updated = [dict(entry) for entry in history]
    updated[attempt - 1]["result_category"] = result_category
    return updated


def _w1_diff_sha256() -> str:
    import hashlib

    allowlist = _config()["external_codex_bound_review"]["w1_allowlist_paths"]
    base_ref = _config()["external_codex_bound_review"]["base_ref"]
    diff = subprocess.run(
        ["git", "diff", base_ref, "--", *allowlist],
        cwd=ROOT,
        capture_output=True,
        check=True,
    ).stdout.decode("utf-8", errors="surrogateescape").replace("\r\n", "\n")
    return hashlib.sha256(diff.encode("utf-8")).hexdigest().upper()


def _isolated_codex_binding_repo(tmp_path: Path, *, extra_allowlist: tuple[str, ...] = ()) -> Path:
    repo = tmp_path / "binding-repo"
    repo.mkdir()
    config_path = ROOT / ".cursor/agent-system.json"
    allowlist = list(_config()["external_codex_bound_review"]["w1_allowlist_paths"])
    for relative in allowlist:
        source = ROOT / Path(relative)
        target = repo / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_file():
            shutil.copy2(source, target)
        else:
            target.write_text(f"placeholder for {relative}\n", encoding="utf-8")
    snapshot_src = ROOT / ".cursor/skills/execute-gated-macro/scripts/checkpoint_snapshot.py"
    snapshot_dst = repo / snapshot_src.relative_to(ROOT)
    snapshot_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(snapshot_src, snapshot_dst)
    shutil.copy2(config_path, repo / ".cursor/agent-system.json")
    _git(repo, "init", "-q", "-b", "feature/cursor-agent-system-v3")
    _git(repo, "config", "user.email", "tests@example.invalid")
    _git(repo, "config", "user.name", "Tests")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "binding base")
    base_sha = _git(repo, "rev-parse", "HEAD").stdout.strip()
    config = json.loads((repo / ".cursor/agent-system.json").read_text(encoding="utf-8"))
    config["external_codex_bound_review"]["base_ref"] = base_sha
    extended = sorted(set(allowlist) | set(extra_allowlist))
    config["external_codex_bound_review"]["w1_allowlist_paths"] = extended
    (repo / ".cursor/agent-system.json").write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _git(repo, "add", ".cursor/agent-system.json")
    _git(repo, "commit", "-q", "-m", "binding config")
    return repo


def _hook_workspace_fingerprint(repo: Path, allowlist: tuple[str, ...]) -> str:
    import uuid

    token = uuid.uuid4().hex[:8]
    output = f"build/pt/test-fingerprint-{token}.json"
    base_ref = json.loads((repo / ".cursor/agent-system.json").read_text(encoding="utf-8"))[
        "external_codex_bound_review"
    ]["base_ref"]
    snapshot = repo / ".cursor/skills/execute-gated-macro/scripts/checkpoint_snapshot.py"
    cmd = [
        sys.executable,
        str(snapshot),
        "--root",
        str(repo),
        "--checkpoint",
        "W1",
        "--phase",
        "hook-binding",
        "--output",
        output,
        "--base-ref",
        base_ref,
        "--fail-on-out-of-scope",
    ]
    for path in allowlist:
        cmd.extend(["--allow", path])
    completed = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr or completed.stdout
    payload = json.loads((repo / output).read_text(encoding="utf-8"))
    (repo / output).unlink(missing_ok=True)
    return str(payload["repository_state_sha256"])


def _repository_fingerprint(repo: Path, allowlist: tuple[str, ...]) -> str:
    return _hook_workspace_fingerprint(repo, allowlist)


def _allowlist_diff_sha256(repo: Path, allowlist: tuple[str, ...], base_ref: str) -> str:
    import hashlib

    diff = subprocess.run(
        ["git", "diff", base_ref, "--", *allowlist],
        cwd=repo,
        capture_output=True,
        check=False,
    ).stdout.decode("utf-8", errors="surrogateescape").replace("\r\n", "\n")
    return hashlib.sha256(diff.encode("utf-8")).hexdigest().upper()


def _workspace_repository_fingerprint() -> str:
    allowlist = tuple(_config()["external_codex_bound_review"]["w1_allowlist_paths"])
    return _repository_fingerprint(ROOT, allowlist)


def _complete_w1_ladder_history() -> list[dict[str, Any]]:
    rungs = _config()["review_model_fallback"]["roles"]["checkpoint-reviewer"]["ladder"]
    return [
        {
            "attempt": rung["attempt"],
            "role": "checkpoint-reviewer",
            "requested_model": rung["model"],
            "result_category": "UNAVAILABLE",
            "agent_id": f"agent-{rung['attempt']}",
            "signal": "explicit unavailability for test",
        }
        for rung in rungs
    ]


def _canonical_evidence_paths(evidence_attempt: str) -> tuple[Path, Path]:
    template = _config()["external_codex_bound_review"]["evidence_path_template"]
    rel_root = Path(template["root"]) / evidence_attempt
    contract = rel_root / template["contract_file"]
    manifest = rel_root / template["manifest_file"]
    return contract, manifest


def _is_safe_evidence_attempt_segment(segment: str) -> bool:
    value = segment.strip() if segment else ""
    if not value:
        return False
    if value in (".", ".."):
        return False
    if "/" in value or "\\" in value:
        return False
    if re.match(r"^[a-zA-Z]:", value):
        return False
    if value.startswith("\\\\"):
        return False
    if ".." in value:
        return False
    return bool(re.match(r"^[A-Za-z0-9._-]+$", value))


def _external_codex_handoff(
    tmp_path: Path,
    *,
    route: str = "critical_final_audit",
    binding_repo: Path | None = None,
    evidence_attempt: str | None = None,
    **updates: Any,
) -> dict[str, Any]:
    import hashlib

    if "evidence_attempt" in updates:
        evidence_attempt = str(updates.pop("evidence_attempt"))
    if evidence_attempt is None:
        evidence_attempt = f"test-handoff-{tmp_path.name}"
    rel_contract, rel_manifest = _canonical_evidence_paths(evidence_attempt)
    materialize_evidence = _is_safe_evidence_attempt_segment(evidence_attempt)
    if materialize_evidence:
        extra_allowlist = (rel_contract.as_posix(), rel_manifest.as_posix())
    else:
        safe_contract, safe_manifest = _canonical_evidence_paths(f"test-handoff-{tmp_path.name}")
        extra_allowlist = (safe_contract.as_posix(), safe_manifest.as_posix())
    repo = binding_repo or _isolated_codex_binding_repo(tmp_path, extra_allowlist=extra_allowlist)
    allowlist = tuple(
        json.loads((repo / ".cursor/agent-system.json").read_text(encoding="utf-8"))[
            "external_codex_bound_review"
        ]["w1_allowlist_paths"]
    )
    base_ref = json.loads((repo / ".cursor/agent-system.json").read_text(encoding="utf-8"))[
        "external_codex_bound_review"
    ]["base_ref"]
    if materialize_evidence:
        contract = repo / rel_contract
        manifest = repo / rel_manifest
        contract.parent.mkdir(parents=True, exist_ok=True)
        contract.write_text("contract body\n", encoding="utf-8")
        manifest.write_text('{"ok":true}\n', encoding="utf-8")
        _git(repo, "add", rel_contract.as_posix(), rel_manifest.as_posix())
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        )
        if status.stdout.strip():
            _git(repo, "commit", "-q", "-m", "binding evidence")
        contract_sha = hashlib.sha256(contract.read_bytes()).hexdigest().upper()
        manifest_sha = hashlib.sha256(manifest.read_bytes()).hexdigest().upper()
    else:
        contract_sha = "0" * 64
        manifest_sha = "0" * 64
    branch = _git(repo, "branch", "--show-current").stdout.strip()
    reviewed_head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    base_head = _git(repo, "rev-parse", base_ref).stdout.strip()
    workspace_fp = _hook_workspace_fingerprint(repo, allowlist)
    payload = {
        "agent_id": "codex-1",
        "task_id": "task-1",
        "external_host": "codex-chatgpt-authenticated",
        "separate_context": True,
        "read_only": True,
        "author_id": "author-1",
        "implementer_id": "impl-1",
        "reviewer_id": "reviewer-1",
        "package_id": "AGENT-COST-01",
        "checkpoint_id": "FINAL_AUDIT" if route == "critical_final_audit" else "W1",
        "review_need": "FINAL_AUDIT" if route == "critical_final_audit" else "CHECKPOINT_ESCALATION",
        "target_root": str(repo.resolve()),
        "branch": branch,
        "base_head": base_head,
        "reviewed_head": reviewed_head,
        "evidence_attempt": evidence_attempt,
        "contract_path": rel_contract.as_posix(),
        "contract_sha256": contract_sha,
        "diff_sha256": _allowlist_diff_sha256(repo, allowlist, base_ref),
        "evidence_manifest_path": rel_manifest.as_posix(),
        "evidence_manifest_sha256": manifest_sha,
        "pre_fingerprint": workspace_fp,
        "post_fingerprint": workspace_fp,
        "mutation_detected": False,
        "ladder_history": [] if route == "critical_final_audit" else _complete_w1_ladder_history(),
        "requested_model": "UNAVAILABLE",
        "observed_model": "UNAVAILABLE",
        "verdict": "PASS",
        "findings": [],
    }
    payload.update(updates)
    return payload


def _run_external_codex_hook(
    tmp_path: Path,
    handoff: dict[str, Any],
    *,
    mode: str = "EXTERNAL_CODEX_BOUND_REVIEW",
    binding_repo: Path | None = None,
) -> dict[str, Any]:
    repo = binding_repo or Path(str(handoff["target_root"]))
    return _run_hook(
        "subagent-start.ps1",
        {"validation_mode": mode, "handoff": handoff},
        state_path=tmp_path / "state.json",
        log_path=tmp_path / "subagent-start.log",
        cwd=repo,
    )


def test_external_codex_bound_review_hook_owner(tmp_path: Path) -> None:
    binding_repo = _isolated_codex_binding_repo(
        tmp_path,
        extra_allowlist=(
            _canonical_evidence_paths(f"test-handoff-{tmp_path.name}")[0].as_posix(),
            _canonical_evidence_paths(f"test-handoff-{tmp_path.name}")[1].as_posix(),
        ),
    )
    handoff = _external_codex_handoff(tmp_path, binding_repo=binding_repo)
    pre_payload = dict(handoff)
    for field in ("verdict", "findings", "requested_model", "observed_model"):
        pre_payload.pop(field, None)
    pre_ok = _run_external_codex_hook(
        tmp_path, pre_payload, mode="EXTERNAL_CODEX_PRE_HANDOFF", binding_repo=binding_repo
    )
    assert pre_ok["handoff"] == "PRE_HANDOFF_READY"
    assert pre_ok["status"] == "READY"
    ok = _run_external_codex_hook(tmp_path, handoff, binding_repo=binding_repo)
    assert ok["handoff"] == "HANDOFF_READY"
    assert ok["authenticates_origin"] is False
    assert ok["authenticates_serving_model"] is False

    critical_fields = _config()["external_codex_bound_review"]["bound_review_required_fields"]
    for field in critical_fields:
        missing = dict(handoff)
        del missing[field]
        result = _run_external_codex_hook(tmp_path, missing, binding_repo=binding_repo)
        assert result["handoff"] == "HANDOFF_INVALID", field

    invalid_cases = {
        "stale_head": {"reviewed_head": "0" * 40},
        "foreign_target": {"target_root": str(tmp_path)},
        "wrong_branch": {"branch": "feature/other"},
        "wrong_base": {"base_head": "0" * 40},
        "wrong_host": {"external_host": "cursor-internal"},
        "wrong_hash": {"contract_sha256": "0" * 64},
        "equal_author_reviewer": {"reviewer_id": "author-1"},
        "equal_implementer_reviewer": {"reviewer_id": "impl-1"},
        "mutation": {"mutation_detected": True},
        "fingerprint_mismatch": {"post_fingerprint": "other"},
        "external_fail": {"verdict": "FAIL"},
        "arbitrary_equal_fingerprints": {
            "pre_fingerprint": "fp",
            "post_fingerprint": "fp",
        },
        "pending_parent_capture": {
            "pre_fingerprint": "pending_parent_capture",
            "post_fingerprint": "pending_parent_capture",
        },
        "non_canonical_contract_path": {
            "contract_path": "build/agent-cost-01/w1/forged/contract.md",
        },
        "payload_selected_manifest": {
            "evidence_manifest_path": "build/agent-cost-01/w1/forged/manifest.json",
        },
        "string_boolean_mutation": {"mutation_detected": "false"},
    }
    for label, updates in invalid_cases.items():
        bad = _run_external_codex_hook(
            tmp_path,
            {**handoff, **updates},
            binding_repo=binding_repo,
        )
        assert bad["handoff"] == "HANDOFF_INVALID", label
        assert bad["status"] == "BLOCKED_HUMAN", label

    pre_with_verdict = dict(handoff)
    pre_with_verdict.pop("verdict", None)
    pre_with_verdict.pop("findings", None)
    pre_with_verdict.pop("requested_model", None)
    pre_with_verdict.pop("observed_model", None)
    pre_with_verdict["verdict"] = "PASS"
    pre_bad = _run_external_codex_hook(
        tmp_path,
        pre_with_verdict,
        mode="EXTERNAL_CODEX_PRE_HANDOFF",
        binding_repo=binding_repo,
    )
    assert pre_bad["handoff"] == "HANDOFF_INVALID"


def test_routing_critical_packages_define_external_review_routes() -> None:
    config = _config()
    assert "AGENT-COST-01" in config["routing"]["ag_packages_critical"]
    assert config["routing"]["critical_final_audit_host"] == "external-codex"
    bindings = config["external_codex_bound_review"]["review_route_bindings"]["AGENT-COST-01"]
    assert bindings["checkpoint_escalation"] == {
        "checkpoint_id": "W1",
        "review_need": "CHECKPOINT_ESCALATION",
        "ladder_role": "checkpoint-reviewer",
        "require_complete_ladder": True,
    }
    assert bindings["critical_final_audit"] == {
        "checkpoint_id": "FINAL_AUDIT",
        "review_need": "FINAL_AUDIT",
        "direct_external": True,
        "forbid_ladder_history": True,
    }


def test_external_codex_evidence_attempt_containment(tmp_path: Path) -> None:
    rel_contract, rel_manifest = _canonical_evidence_paths(f"test-handoff-{tmp_path.name}")
    binding_repo = _isolated_codex_binding_repo(
        tmp_path,
        extra_allowlist=(rel_contract.as_posix(), rel_manifest.as_posix()),
    )
    safe = _external_codex_handoff(tmp_path, binding_repo=binding_repo)
    assert _run_external_codex_hook(tmp_path, safe, binding_repo=binding_repo)["handoff"] == "HANDOFF_READY"
    for label, attempt in {
        "slash": "bad/segment",
        "backslash": r"bad\segment",
        "dotdot": "..",
        "nested": "a/b",
        "drive": "C:evil",
        "unc": r"\\server\share",
        "empty": "",
    }.items():
        attempt_root = tmp_path / f"case-{label}"
        attempt_root.mkdir(parents=True, exist_ok=True)
        bad = _run_external_codex_hook(
            attempt_root,
            _external_codex_handoff(attempt_root, evidence_attempt=attempt),
        )
        assert bad["handoff"] == "HANDOFF_INVALID", label


def test_external_codex_review_route_bindings(tmp_path: Path) -> None:
    binding_repo = _isolated_codex_binding_repo(
        tmp_path,
        extra_allowlist=(
            _canonical_evidence_paths(f"test-handoff-{tmp_path.name}")[0].as_posix(),
            _canonical_evidence_paths(f"test-handoff-{tmp_path.name}")[1].as_posix(),
        ),
    )
    handoff = _external_codex_handoff(tmp_path, binding_repo=binding_repo)
    escalation_handoff = _external_codex_handoff(
        tmp_path, route="checkpoint_escalation", binding_repo=binding_repo
    )
    escalation = _run_external_codex_hook(
        tmp_path,
        escalation_handoff,
        binding_repo=binding_repo,
    )
    assert escalation["handoff"] == "HANDOFF_READY"

    audit_handoff = _external_codex_handoff(tmp_path, binding_repo=binding_repo)
    final_audit = _run_external_codex_hook(
        tmp_path,
        audit_handoff,
        binding_repo=binding_repo,
    )
    assert final_audit["handoff"] == "HANDOFF_READY"

    route_mismatch = _run_external_codex_hook(
        tmp_path,
        {
            **escalation_handoff,
            "checkpoint_id": "W1",
            "review_need": "FINAL_AUDIT",
            "ladder_history": _complete_w1_ladder_history(),
        },
        binding_repo=binding_repo,
    )
    assert route_mismatch["handoff"] == "HANDOFF_INVALID"

    ladder_on_direct = _run_external_codex_hook(
        tmp_path,
        {
            **audit_handoff,
            "checkpoint_id": "FINAL_AUDIT",
            "review_need": "FINAL_AUDIT",
            "ladder_history": _complete_w1_ladder_history(),
        },
        binding_repo=binding_repo,
    )
    assert ladder_on_direct["handoff"] == "HANDOFF_INVALID"

    wrong_checkpoint = _run_external_codex_hook(
        tmp_path,
        {
            **escalation_handoff,
            "checkpoint_id": "W2",
            "review_need": "CHECKPOINT_ESCALATION",
        },
        binding_repo=binding_repo,
    )
    assert wrong_checkpoint["handoff"] == "HANDOFF_INVALID"

    missing_ladder = _run_external_codex_hook(
        tmp_path,
        {**escalation_handoff, "ladder_history": []},
        binding_repo=binding_repo,
    )
    assert missing_ladder["handoff"] == "HANDOFF_INVALID"

    substantive_fail = _run_external_codex_hook(
        tmp_path,
        {
            **escalation_handoff,
            "ladder_history": _substitute_ladder_result(
                _complete_w1_ladder_history(), 2, "FAIL_SUBSTANTIVE"
            ),
        },
        binding_repo=binding_repo,
    )
    assert substantive_fail["handoff"] == "HANDOFF_INVALID"

    wrong_ladder_model = _complete_w1_ladder_history()
    wrong_ladder_model[0] = {
        **wrong_ladder_model[0],
        "requested_model": "cursor-grok-4.6-xhigh",
    }
    wrong_model = _run_external_codex_hook(
        tmp_path,
        {**escalation_handoff, "ladder_history": wrong_ladder_model},
        binding_repo=binding_repo,
    )
    assert wrong_model["handoff"] == "HANDOFF_INVALID"
