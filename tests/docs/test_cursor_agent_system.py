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


def _sync_isolated_registry_base_refs(config: dict[str, Any], base_sha: str) -> None:
    bound = config.setdefault("external_codex_bound_review", {})
    bound["base_ref"] = base_sha
    bindings = bound.get("review_route_bindings") or {}
    for package_bindings in bindings.values():
        for record in package_bindings.values():
            record["base_ref"] = base_sha


def _prepare_final_audit_empty_diff_binding_repo(tmp_path: Path) -> Path:
    import hashlib

    binding_repo = _isolated_final_audit_binding_repo(tmp_path)
    config = json.loads((binding_repo / ".cursor/agent-system.json").read_text(encoding="utf-8"))
    _sync_isolated_registry_base_refs(config, "HEAD")
    (binding_repo / ".cursor/agent-system.json").write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _git(binding_repo, "add", ".cursor/agent-system.json")
    _git(binding_repo, "commit", "-q", "-m", "synthetic isolated registry base at symbolic HEAD")
    reviewed_head = _git(binding_repo, "rev-parse", "HEAD").stdout.strip()
    config = json.loads((binding_repo / ".cursor/agent-system.json").read_text(encoding="utf-8"))
    assert config["external_codex_bound_review"]["base_ref"] == "HEAD"
    for package_bindings in config["external_codex_bound_review"]["review_route_bindings"].values():
        for record in package_bindings.values():
            assert record["base_ref"] == "HEAD"
    assert _git(binding_repo, "rev-parse", "HEAD").stdout.strip() == reviewed_head
    assert _git(binding_repo, "diff", "HEAD", "HEAD").returncode == 0
    assert _git(binding_repo, "diff", "HEAD", "HEAD").stdout == ""
    assert (
        _git(binding_repo, "status", "--porcelain", "--untracked-files=no").stdout.strip()
        == ""
    )
    foreign_paths = _declared_foreign_rules(config=config)
    assert len(foreign_paths) == 3
    assert set(foreign_paths) == {".cursor/cli.json", "agent", "models"}
    for relative in foreign_paths:
        foreign_file = binding_repo / relative
        assert foreign_file.is_file(), relative
    empty_diff = hashlib.sha256(b"").hexdigest().upper()
    assert _full_diff_sha256(binding_repo, "HEAD") == empty_diff
    return binding_repo


def _install_review_route_bindings(
    config: dict[str, Any],
    bindings: dict[str, Any],
) -> None:
    existing = config.setdefault("external_codex_bound_review", {}).setdefault(
        "review_route_bindings", {}
    )
    existing.update(bindings)


def _foreign_package_two_checkpoint_bindings(*, base_ref: str) -> dict[str, Any]:
    allowlist = [".cursor/agent-system.json", ".cursor/hooks/subagent-start.ps1"]
    template = {
        "contract_file": "checkpoint-contract.md",
        "manifest_file": "context-manifest.json",
    }
    verify = ".venv/Scripts/python.exe -m pytest tests/docs -q"
    return {
        "NEWPKG-99": {
            "first_checkpoint": {
                "package_id": "NEWPKG-99",
                "checkpoint_id": "CP-ONE",
                "review_need": "CHECKPOINT_ESCALATION",
                "base_ref": base_ref,
                "allowlist_paths": allowlist,
                "evidence_path_template": {
                    "root": "build/newpkg-99/w1",
                    **template,
                },
                "verification_commands": [verify],
                "scope_mode": "dirty",
                "ladder_role": "checkpoint-reviewer",
                "require_complete_ladder": True,
            },
            "second_checkpoint": {
                "package_id": "NEWPKG-99",
                "checkpoint_id": "CP-TWO",
                "review_need": "CHECKPOINT_ESCALATION",
                "base_ref": base_ref,
                "allowlist_paths": allowlist,
                "evidence_path_template": {
                    "root": "build/newpkg-99/w2",
                    **template,
                },
                "verification_commands": [verify],
                "scope_mode": "dirty",
                "ladder_role": "checkpoint-reviewer",
                "require_complete_ladder": True,
            },
        }
    }


def _synthetic_w2_w3_route_bindings(*, base_ref: str) -> dict[str, Any]:
    allowlist = [".cursor/agent-system.json", ".cursor/hooks/subagent-start.ps1"]
    template = {
        "contract_file": "checkpoint-contract.md",
        "manifest_file": "context-manifest.json",
    }
    verify = ".venv/Scripts/python.exe -m pytest tests/docs -q"
    ladder = {
        "ladder_role": "checkpoint-reviewer",
        "require_complete_ladder": True,
    }
    return {
        "AGENT-COST-01": {
            "checkpoint_w2": {
                "package_id": "AGENT-COST-01",
                "checkpoint_id": "W2",
                "review_need": "CHECKPOINT_ESCALATION",
                "base_ref": base_ref,
                "allowlist_paths": allowlist,
                "evidence_path_template": {
                    "root": "build/agent-cost-01/w2-fixture",
                    **template,
                },
                "verification_commands": [verify],
                "scope_mode": "dirty",
                **ladder,
            },
            "checkpoint_w3": {
                "package_id": "AGENT-COST-01",
                "checkpoint_id": "W3",
                "review_need": "CHECKPOINT_ESCALATION",
                "base_ref": base_ref,
                "allowlist_paths": allowlist,
                "evidence_path_template": {
                    "root": "build/agent-cost-01/w3-fixture",
                    **template,
                },
                "verification_commands": [verify],
                "scope_mode": "dirty",
                **ladder,
            },
        }
    }


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


def _hook_result_json(result: dict[str, Any]) -> str:
    return json.dumps(result, indent=2, sort_keys=True)


def _assert_hook_result(
    result: dict[str, Any],
    *,
    handoff: str | None = None,
    status: str | None = None,
    reason: str | None = None,
    reason_contains: str | None = None,
) -> None:
    payload = _hook_result_json(result)
    if handoff is not None:
        assert result.get("handoff") == handoff, payload
    if status is not None:
        assert result.get("status") == status, payload
    if reason is not None:
        assert result.get("reason") == reason, payload
    if reason_contains is not None:
        assert reason_contains in str(result.get("reason", "")), payload


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
        "bindingRecord": None,
        "recovery_proposal_bound": False,
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


def _synthetic_foreign_cli_bytes() -> bytes:
    return b'{"fixture_only":"w3-prep-01-declared-foreign","never_from_root_cli":true}\n'


def _patch_fixture_foreign_bindings(config: dict[str, Any]) -> None:
    cli_bytes = _synthetic_foreign_cli_bytes()
    bindings = config["external_codex_bound_review"]["declared_foreign_bindings"]
    for binding in bindings:
        if binding["path"] == ".cursor/cli.json":
            binding["size"] = len(cli_bytes)
            binding["sha256"] = __import__("hashlib").sha256(cli_bytes).hexdigest()


def _materialize_declared_foreign(repo: Path, *, config: dict[str, Any] | None = None) -> None:
    active = config or json.loads((repo / ".cursor/agent-system.json").read_text(encoding="utf-8"))
    cli_bytes = _synthetic_foreign_cli_bytes()
    for binding in active["external_codex_bound_review"]["declared_foreign_bindings"]:
        target = repo / binding["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        if binding["path"] == ".cursor/cli.json":
            target.write_bytes(cli_bytes)
        else:
            target.write_bytes(b"")


def _declared_foreign_rules(*, config: dict[str, Any] | None = None) -> tuple[str, ...]:
    active = config or _config()
    return tuple(
        binding["path"]
        for binding in active["external_codex_bound_review"]["declared_foreign_bindings"]
    )


def _synthetic_repo_exclude_paths(repo: Path, *patterns: str) -> None:
    exclude_file = repo / ".git" / "info" / "exclude"
    exclude_file.parent.mkdir(parents=True, exist_ok=True)
    existing = exclude_file.read_text(encoding="utf-8") if exclude_file.is_file() else ""
    lines = [line for line in existing.splitlines() if line.strip()]
    known = set(lines)
    for pattern in patterns:
        normalized = Path(pattern).as_posix().rstrip("/")
        candidates = {normalized, f"{normalized}/"}
        for candidate in candidates:
            if candidate not in known:
                lines.append(candidate)
                known.add(candidate)
    exclude_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _isolated_codex_binding_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "binding-repo"
    repo.mkdir()
    config_path = ROOT / ".cursor/agent-system.json"
    allowlist = list(_config()["external_codex_bound_review"]["w1_allowlist_paths"])
    assert len(allowlist) == 21
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
    config = json.loads((repo / ".cursor/agent-system.json").read_text(encoding="utf-8"))
    _patch_fixture_foreign_bindings(config)
    (repo / ".cursor/agent-system.json").write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _git(repo, "init", "-q", "-b", "feature/cursor-agent-system-v3")
    _git(repo, "config", "user.email", "tests@example.invalid")
    _git(repo, "config", "user.name", "Tests")
    _synthetic_repo_exclude_paths(repo, "build/agent-cost-01/w1/")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "binding base")
    base_sha = _git(repo, "rev-parse", "HEAD").stdout.strip()
    config = json.loads((repo / ".cursor/agent-system.json").read_text(encoding="utf-8"))
    _sync_isolated_registry_base_refs(config, base_sha)
    (repo / ".cursor/agent-system.json").write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _git(repo, "add", ".cursor/agent-system.json")
    _git(repo, "commit", "-q", "-m", "binding config")
    return repo


def _isolated_final_audit_binding_repo(
    tmp_path: Path,
    *,
    prebase_out_of_scope: tuple[str, ...] = (),
) -> Path:
    repo = tmp_path / "final-audit-repo"
    repo.mkdir()
    allowlist = list(_config()["external_codex_bound_review"]["w3_allowlist_paths"])
    assert len(allowlist) == 35
    for relative in allowlist:
        source = ROOT / Path(relative)
        target = repo / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_file():
            shutil.copy2(source, target)
        else:
            target.write_text(f"placeholder for {relative}\n", encoding="utf-8")
    for relative in prebase_out_of_scope:
        rogue = repo / relative
        rogue.parent.mkdir(parents=True, exist_ok=True)
        rogue.write_text(f"out-of-scope fixture {relative}\n", encoding="utf-8")
    snapshot_src = ROOT / ".cursor/skills/execute-gated-macro/scripts/checkpoint_snapshot.py"
    snapshot_dst = repo / snapshot_src.relative_to(ROOT)
    snapshot_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(snapshot_src, snapshot_dst)
    shutil.copy2(ROOT / ".cursor/agent-system.json", repo / ".cursor/agent-system.json")
    config = json.loads((repo / ".cursor/agent-system.json").read_text(encoding="utf-8"))
    _patch_fixture_foreign_bindings(config)
    (repo / ".gitignore").write_text(
        "build/agent-cost-01/w3/\nbuild/pt/\n",
        encoding="utf-8",
    )
    (repo / ".cursor/agent-system.json").write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _git(repo, "init", "-q", "-b", "feature/cursor-agent-system-v3")
    _git(repo, "config", "user.email", "tests@example.invalid")
    _git(repo, "config", "user.name", "Tests")
    _synthetic_repo_exclude_paths(repo, "build/agent-cost-01/w3/")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "final audit baseline")
    base_sha = _git(repo, "rev-parse", "HEAD").stdout.strip()
    config = json.loads((repo / ".cursor/agent-system.json").read_text(encoding="utf-8"))
    _sync_isolated_registry_base_refs(config, base_sha)
    (repo / ".cursor/agent-system.json").write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _git(repo, "add", ".cursor/agent-system.json")
    _git(repo, "commit", "-q", "-m", "register final audit base")
    _materialize_declared_foreign(repo, config=config)
    return repo


def _final_audit_pre_payload(handoff: dict[str, Any]) -> dict[str, Any]:
    payload = dict(handoff)
    for field in ("verdict", "findings", "requested_model", "observed_model"):
        payload.pop(field, None)
    return payload


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


def _full_diff_sha256(repo: Path, base_ref: str) -> str:
    import hashlib

    diff = subprocess.run(
        ["git", "diff", base_ref, "HEAD"],
        cwd=repo,
        capture_output=True,
        check=False,
    ).stdout.decode("utf-8", errors="surrogateescape").replace("\r\n", "\n")
    return hashlib.sha256(diff.encode("utf-8")).hexdigest().upper()


def _manifest_build_allowlist(
    allowlist: tuple[str, ...],
    *,
    contract_path: str,
    manifest_path: str,
) -> tuple[str, ...]:
    excluded = {
        Path(contract_path).as_posix(),
        Path(manifest_path).as_posix(),
    }
    return tuple(path for path in allowlist if Path(path).as_posix() not in excluded)


def _build_route_manifest(
    repo: Path,
    *,
    package_id: str,
    checkpoint_id: str,
    contract_path: str,
    manifest_path: str,
    allowlist: tuple[str, ...],
    base_ref: str,
    verification_commands: tuple[str, ...],
) -> None:
    cmd = [
        sys.executable,
        str(ROOT / ".cursor/skills/execute-gated-macro/scripts/checkpoint_snapshot.py"),
        "manifest-build",
        "--root",
        str(repo),
        "--package-id",
        package_id,
        "--checkpoint-id",
        checkpoint_id,
        "--contract-path",
        contract_path,
        "--profile-path",
        ".cursor/agent-system.json",
        "--output",
        manifest_path,
        "--base-ref",
        base_ref,
    ]
    for verify in verification_commands:
        cmd.extend(["--verify-command", verify])
    for path in _manifest_build_allowlist(
        allowlist,
        contract_path=contract_path,
        manifest_path=manifest_path,
    ):
        cmd.extend(["--allow", path])
    completed = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr or completed.stdout


def _build_external_codex_context_manifest(
    repo: Path,
    *,
    contract_path: str,
    manifest_path: str,
    route: str,
    allowlist: tuple[str, ...],
    base_ref: str,
) -> None:
    checkpoint_id = "FINAL_AUDIT" if route == "critical_final_audit" else "W1"
    cmd = [
        sys.executable,
        str(ROOT / ".cursor/skills/execute-gated-macro/scripts/checkpoint_snapshot.py"),
        "manifest-build",
        "--root",
        str(repo),
        "--package-id",
        "AGENT-COST-01",
        "--checkpoint-id",
        checkpoint_id,
        "--contract-path",
        contract_path,
        "--profile-path",
        ".cursor/agent-system.json",
        "--output",
        manifest_path,
        "--base-ref",
        base_ref,
        "--verify-command",
        ".venv/Scripts/python.exe -m pytest tests/docs -q",
    ]
    for path in _manifest_build_allowlist(
        allowlist,
        contract_path=contract_path,
        manifest_path=manifest_path,
    ):
        cmd.extend(["--allow", path])
    completed = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr or completed.stdout


def _w3_prep_allowlist() -> tuple[str, ...]:
    return tuple(_config()["external_codex_bound_review"]["w3_allowlist_paths"])


W3_PREP_SOURCE_OWNERS: tuple[str, ...] = (
    ".cursor/agent-system.json",
    ".cursor/hooks/subagent-start.ps1",
    ".cursor/skills/execute-gated-macro/scripts/checkpoint_snapshot.py",
    ".cursor/skills/execute-gated-macro/references/checkpoint-protocol.md",
    "tests/docs/test_cursor_agent_system.py",
    "tests/docs/test_cursor_macro_workflow.py",
    "tests/docs/test_docs_consistency.py",
    "docs/AP-029_AGENT_WORKFLOW_COST_PROFILE.md",
    "docs/CURSOR_AUTONOMOUS_WORK_PACKAGE_SYSTEM.md",
)


def _hook_workspace_fingerprint(
    repo: Path,
    allowlist: tuple[str, ...],
    *,
    base_ref: str | None = None,
    scope_mode: str = "dirty",
    checkpoint: str = "W1",
    foreign: tuple[str, ...] = (),
) -> str:
    import uuid

    token = uuid.uuid4().hex[:8]
    output = f"build/pt/test-fingerprint-{token}.json"
    if base_ref is None:
        base_ref = json.loads((repo / ".cursor/agent-system.json").read_text(encoding="utf-8"))[
            "external_codex_bound_review"
        ]["base_ref"]
    snapshot = repo / ".cursor/skills/execute-gated-macro/scripts/checkpoint_snapshot.py"
    cmd = [
        sys.executable,
        str(snapshot),
        "snapshot",
        "--root",
        str(repo),
        "--checkpoint",
        checkpoint,
        "--phase",
        "hook-binding",
        "--output",
        output,
        "--base-ref",
        base_ref,
        "--scope-mode",
        scope_mode,
        "--fail-on-out-of-scope",
        "--fail-on-denial",
    ]
    for path in allowlist:
        cmd.extend(["--allow", path])
    for path in foreign:
        cmd.extend(["--foreign", path])
    completed = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr or completed.stdout
    payload = json.loads((repo / output).read_text(encoding="utf-8"))
    (repo / output).unlink(missing_ok=True)
    return str(payload["repository_state_sha256"])


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


def _route_evidence_template(route: str) -> dict[str, Any]:
    bound = _config()["external_codex_bound_review"]
    if route == "critical_final_audit":
        return bound["final_audit_evidence_path_template"]
    if route == "recovery_diagnosis":
        return bound["review_route_bindings"]["AGENT-COST-01"]["recovery_diagnosis"][
            "evidence_path_template"
        ]
    return bound["evidence_path_template"]


def _canonical_evidence_paths(
    evidence_attempt: str, *, route: str = "checkpoint_escalation"
) -> tuple[Path, Path]:
    template = _route_evidence_template(route)
    rel_root = Path(template["root"]) / evidence_attempt
    contract = rel_root / template["contract_file"]
    manifest = rel_root / template["manifest_file"]
    return contract, manifest


W3_FINAL_REWORK_001_FOCUSED_NODES: tuple[str, ...] = (
    "test_w3_final_review_route_bindings_self_contained",
    "test_w3_final_partial_registry_record_denies_route_preflight",
    "test_w3_final_foreign_package_two_checkpoint_pre_bound_positive",
    "test_w3_final_synthetic_w2_w3_route_pre_bound_positive",
    "test_w3_final_unregistered_checkpoint_denies_implementer_preflight",
    "test_w3_final_host_alias_without_role_cannot_bypass_implementer_preflight",
    "test_w3_final_pre_handoff_computes_binding_record_without_pass",
    "test_w3_final_bound_requires_authoritative_binding_record",
    "test_w3_final_bound_denies_missing_state_payload_authoritative_binding_record",
    "test_w3_final_bound_denies_missing_state_self_consistent_rewritten_evidence",
    "test_w3_final_bound_denies_mutated_contract_after_pre",
    "test_w3_final_bound_denies_self_consistent_manifest_rewrite_after_pre",
    "test_w3_final_bound_denies_payload_binding_record_override",
    "test_w3_final_recovery_diagnosis_denied_on_review_pre_path",
    "test_w3_final_recovery_diagnosis_denied_on_review_bound_path",
    "test_w3_final_recovery_pre_handoff_preserves_real_fail_counts",
    "test_w3_final_recovery_forged_zero_counters_denied",
    "test_w3_final_recovery_receipt_is_blocked_human_without_continue",
    "test_w3_final_recovery_receipt_requires_anchored_binding_record",
    "test_w3_final_manifest_validate_valid_false_denies",
    "test_w3_final_session_start_recovery_receipt_blocks_resume_instructions",
    "test_w3_final_session_start_recovery_diagnosis_binding_record_blocks_resume_before_diagnosis",
    "test_w3_final_session_start_recovery_diagnosis_binding_record_blocks_resume_after_diagnosis_result",
    "test_w3_final_session_start_normal_binding_record_still_resumes",
    "test_w1_escalation_route_still_uses_w1_allowlist_and_root",
    "test_final_audit_pre_handoff_accepts_clean_committed_candidate",
)


W3_FINAL_REWORK_001_FIX03_NODES: tuple[str, ...] = (
    "test_external_codex_bound_review_hook_owner",
    "test_external_codex_evidence_attempt_containment",
    "test_external_codex_review_route_bindings",
    "test_w1_escalation_route_still_uses_w1_allowlist_and_root",
    "test_final_audit_hook_denies_missing_base_ref",
    "test_final_audit_hook_empty_diff_success_not_git_failure",
    "test_w3_final_foreign_package_two_checkpoint_pre_bound_positive",
    "test_w3_final_synthetic_w2_w3_route_pre_bound_positive",
    "test_w3_final_bound_requires_authoritative_binding_record",
    "test_w3_final_bound_denies_mutated_contract_after_pre",
    "test_w3_final_bound_denies_mutated_contract_hash_mismatch_before_seal",
    "test_w3_final_recovery_receipt_is_blocked_human_without_continue",
    "test_w3_final_manifest_validate_valid_false_denies",
    "test_w3_final_manifest_validate_exit_nonzero_denies",
    "test_w3_final_manifest_validate_valid_false_exit0_double_denies",
    "test_w3_final_recovery_pre_denies_missing_persisted_context",
    "test_w3_final_recovery_receipt_denies_mismatched_persisted_branch",
    "test_w3_final_manifest_metadata_denies_smaller_allowlist_scope",
    "test_w3_final_manifest_metadata_denies_foreign_package_id",
    "test_w3_final_manifest_metadata_denies_foreign_checkpoint_id",
    "test_w3_final_manifest_metadata_denies_foreign_base_ref",
    "test_w3_final_bound_denies_reviewer_id_change_after_pre",
    "test_w3_final_recovery_pre_denies_missing_failed_evidence",
    "test_w3_final_recovery_pre_denies_passing_junit_as_failed_evidence",
    "test_w3_final_recovery_pre_denies_missing_persisted_counters",
)

W3_FINAL_REWORK_001_FIX04_NODES: tuple[str, ...] = (
    *W3_FINAL_REWORK_001_FIX03_NODES,
    "test_w3_final_pre_denies_binding_record_overwrite_on_review_pre",
    "test_w3_final_pre_denies_persisted_checkpoint_context_mismatch",
    "test_w3_final_bound_denies_persisted_checkpoint_context_mismatch",
    "test_w3_final_binding_record_pre_json_bound_roundtrip_positive",
    "test_w3_final_host_alias_without_role_cannot_bypass_implementer_preflight",
    "test_w3_final_implementer_subagent_type_without_state_denies",
    "test_w3_final_implementer_without_marker_unknown_checkpoint_denies",
    "test_w3_final_nonimplementer_helper_without_marker_stays_non_authoritative",
    "test_w3_final_recovery_pre_denies_mismatched_workspace_claims",
)


def _recovery_running_state_path(tmp_path: Path, **updates: Any) -> Path:
    state_path = tmp_path / "recovery-running-state.json"
    _write_running_state(state_path, **updates)
    return state_path


def _ensure_running_state_for_handoff(
    state_path: Path,
    handoff: dict[str, Any],
    **updates: Any,
) -> None:
    if state_path.exists():
        return
    defaults: dict[str, Any] = {
        "work_package": str(handoff.get("package_id", "AGENT-COST-01")),
        "checkpoint": str(handoff.get("checkpoint_id", "W1")),
        "work_branch": str(handoff.get("branch", "feature/cursor-agent-system-v3")),
    }
    for key, value in updates.items():
        defaults[key] = value
    _write_running_state(state_path, **defaults)


def _run_route_preflight(
    tmp_path: Path,
    repo: Path,
    *,
    package_id: str,
    checkpoint_id: str,
    review_need: str = "",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "validation_mode": "EXTERNAL_CODEX_ROUTE_PREFLIGHT",
        "package_id": package_id,
        "checkpoint_id": checkpoint_id,
    }
    if review_need:
        payload["review_need"] = review_need
    return _run_hook(
        "subagent-start.ps1",
        payload,
        state_path=tmp_path / "route-preflight-state.json",
        cwd=repo,
    )


def _running_workflow_state(**updates: Any) -> dict[str, Any]:
    state = {
        "status": "RUNNING",
        "work_package": "AGENT-COST-01",
        "base_branch": "main",
        "work_branch": "feature/cursor-agent-system-v3",
        "phase": "IMPLEMENT",
        "checkpoint": "W3-FINAL-REWORK-001",
        "rework_count": 2,
        "final_rework_count": 1,
        "regular_rework_count": 2,
        "exceptional_count": 6,
        "escalation_used": False,
        "human_gate": False,
        "last_green_commit": "4220c4c2597b50a3f701aa81682228dfce910048",
        "next_action": "implement W3-FINAL-REWORK-001",
        "updated_at": "2026-10-02T12:00:00Z",
        "work_package_path": "docs/AP-029_AGENT_WORKFLOW_COST_PROFILE.md",
        "execution_journal_path": "build/agent-cost-01/w3-final-rework-001/execution-journal.md",
        "final_report_path": None,
        "external_review": {
            "status": "NOT_REQUESTED",
            "round": 0,
            "reviewed_head": None,
            "blocking_findings": [],
            "last_checked_at": None,
            "bindingRecord": None,
            "recovery_proposal_bound": False,
        },
        "gates": {
            "full_regression_pass": False,
            "final_audit_pass": False,
            "ci_pass": False,
        },
    }
    state.update(updates)
    return state


def _write_running_state(path: Path, **updates: Any) -> dict[str, Any]:
    state = _running_workflow_state(**updates)
    path.write_text(json.dumps(state), encoding="utf-8")
    return state


def _run_implementer_pretool(
    tmp_path: Path,
    *,
    state_path: Path,
    prompt: str = "[ROLE:implementer]\nImplement W3-FINAL-REWORK-001",
    subagent_type: str = "implementer",
    **updates: Any,
) -> dict[str, Any]:
    tool_input: dict[str, Any] = {
        "prompt": prompt,
        "model": "composer-2.5",
        "subagent_type": subagent_type,
    }
    payload = _pre_tool_use_task_payload(tool_input=tool_input, **updates)
    return _run_hook(
        "subagent-start.ps1",
        payload,
        state_path=state_path,
        log_path=tmp_path / "implementer-pretool.log",
    )


def _coordinator_serialized_recovery_diagnosis_state(
    binding_record: dict[str, Any],
    *,
    next_action: str = "implement W3-FINAL-REWORK-001",
    recovery_proposal_bound: bool = False,
) -> dict[str, Any]:
    state = _running_workflow_state(next_action=next_action)
    external_review = dict(state["external_review"])
    external_review["bindingRecord"] = json.loads(json.dumps(binding_record))
    external_review["recovery_proposal_bound"] = recovery_proposal_bound
    state["external_review"] = external_review
    return state


def _write_state_binding_record(
    state_path: Path,
    binding_record: dict[str, Any],
    **updates: Any,
) -> dict[str, Any]:
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
    else:
        state = _running_workflow_state(**updates)
    for key, value in updates.items():
        state[key] = value
    external_review = dict(state.get("external_review") or _running_workflow_state()["external_review"])
    external_review["bindingRecord"] = binding_record
    state["external_review"] = external_review
    state_path.write_text(json.dumps(state), encoding="utf-8")
    return state


def _isolated_recovery_diagnosis_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "recovery-diagnosis-repo"
    repo.mkdir()
    route_record = _config()["external_codex_bound_review"]["review_route_bindings"]["AGENT-COST-01"][
        "recovery_diagnosis"
    ]
    allowlist = list(route_record["allowlist_paths"])
    assert len(allowlist) == 15
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
    gate_src = ROOT / ".cursor/tools/run-pytest-gate.ps1"
    gate_dst = repo / gate_src.relative_to(ROOT)
    gate_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(gate_src, gate_dst)
    shutil.copy2(ROOT / ".cursor/agent-system.json", repo / ".cursor/agent-system.json")
    config = json.loads((repo / ".cursor/agent-system.json").read_text(encoding="utf-8"))
    (repo / ".cursor/agent-system.json").write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _git(repo, "init", "-q", "-b", "feature/cursor-agent-system-v3")
    _git(repo, "config", "user.email", "tests@example.invalid")
    _git(repo, "config", "user.name", "Tests")
    (repo / ".gitignore").write_text(
        "build/agent-cost-01/w3-final-rework-001/\n"
        "build/pt/\n"
        ".cursor/skills/execute-gated-macro/scripts/checkpoint_snapshot.real.py\n",
        encoding="utf-8",
    )
    _synthetic_repo_exclude_paths(repo, "build/agent-cost-01/w3-final-rework-001/")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "recovery diagnosis base")
    base_sha = _git(repo, "rev-parse", "HEAD").stdout.strip()
    config = json.loads((repo / ".cursor/agent-system.json").read_text(encoding="utf-8"))
    _sync_isolated_registry_base_refs(config, base_sha)
    (repo / ".cursor/agent-system.json").write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _git(repo, "add", ".cursor/agent-system.json")
    _git(repo, "commit", "-q", "-m", "recovery diagnosis registry")
    return repo


def _write_synthetic_failed_junit(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '<?xml version="1.0" encoding="utf-8"?>'
        '<testsuites name="pytest tests">'
        '<testsuite name="pytest" errors="0" failures="1" skipped="0" tests="1" time="0.001">'
        '<testcase classname="tests.docs.test_cursor_agent_system" name="test_synthetic_failure" time="0.001">'
        '<failure message="synthetic failure for recovery evidence"/>'
        '</testcase></testsuite></testsuites>\n',
        encoding="utf-8",
    )


def _write_synthetic_passing_junit(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '<?xml version="1.0" encoding="utf-8"?>'
        '<testsuites name="pytest tests">'
        '<testsuite name="pytest" errors="0" failures="0" skipped="0" tests="1" time="0.001">'
        '<testcase classname="tests.docs.test_cursor_agent_system" name="test_synthetic_pass" time="0.001"/>'
        '</testsuite></testsuites>\n',
        encoding="utf-8",
    )


def _build_recovery_diagnosis_manifest(
    repo: Path,
    *,
    contract_path: str,
    manifest_path: str,
    allowlist: tuple[str, ...],
    base_ref: str,
) -> None:
    verify_command = (
        ".cursor/tools/run-pytest-gate.ps1 -GateId w3-final-rework-001-focused"
    )
    manifest_rel = Path(manifest_path)
    failed_junit = repo / manifest_rel.parent / "failed-junit.xml"
    _write_synthetic_failed_junit(failed_junit)
    failed_junit_rel = failed_junit.relative_to(repo).as_posix()
    cmd = [
        sys.executable,
        str(ROOT / ".cursor/skills/execute-gated-macro/scripts/checkpoint_snapshot.py"),
        "manifest-build",
        "--root",
        str(repo),
        "--package-id",
        "AGENT-COST-01",
        "--checkpoint-id",
        "W3-FINAL-REWORK-001",
        "--contract-path",
        contract_path,
        "--profile-path",
        ".cursor/agent-system.json",
        "--output",
        manifest_path,
        "--base-ref",
        base_ref,
        "--verify-command",
        verify_command,
        "--evidence",
        f"failed_review_junit={failed_junit_rel}",
    ]
    for path in _manifest_build_allowlist(
        allowlist,
        contract_path=contract_path,
        manifest_path=manifest_path,
    ):
        cmd.extend(["--allow", path])
    completed = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr or completed.stdout


def _recovery_diagnosis_handoff(
    tmp_path: Path,
    *,
    binding_repo: Path | None = None,
    evidence_attempt: str | None = None,
    **updates: Any,
) -> dict[str, Any]:
    import hashlib

    if evidence_attempt is None:
        evidence_attempt = f"recovery-{tmp_path.name}"
    rel_contract, rel_manifest = _canonical_evidence_paths(
        evidence_attempt, route="recovery_diagnosis"
    )
    repo = binding_repo or _isolated_recovery_diagnosis_repo(tmp_path)
    config = json.loads((repo / ".cursor/agent-system.json").read_text(encoding="utf-8"))
    route_record = config["external_codex_bound_review"]["review_route_bindings"]["AGENT-COST-01"][
        "recovery_diagnosis"
    ]
    allowlist = tuple(route_record["allowlist_paths"])
    assert len(allowlist) == 15
    base_ref = config["external_codex_bound_review"]["base_ref"]
    contract = repo / rel_contract
    manifest = repo / rel_manifest
    contract.parent.mkdir(parents=True, exist_ok=True)
    contract.write_text("recovery diagnosis contract\n", encoding="utf-8")
    _synthetic_repo_exclude_paths(repo, f"{rel_contract.parent.as_posix()}/")
    _build_recovery_diagnosis_manifest(
        repo,
        contract_path=rel_contract.as_posix(),
        manifest_path=rel_manifest.as_posix(),
        allowlist=allowlist,
        base_ref=base_ref,
    )
    contract_sha = hashlib.sha256(contract.read_bytes()).hexdigest().upper()
    manifest_sha = hashlib.sha256(manifest.read_bytes()).hexdigest().upper()
    branch = _git(repo, "branch", "--show-current").stdout.strip()
    reviewed_head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    base_head = _git(repo, "rev-parse", base_ref).stdout.strip()
    diff_sha = _allowlist_diff_sha256(repo, allowlist, base_ref)
    workspace_fp = _hook_workspace_fingerprint(repo, allowlist, base_ref=base_ref)
    payload = {
        "agent_id": "codex-recovery-1",
        "task_id": "recovery-task-1",
        "external_host": "codex-chatgpt-authenticated",
        "separate_context": True,
        "read_only": True,
        "author_id": "author-1",
        "implementer_id": "impl-1",
        "reviewer_id": "reviewer-1",
        "package_id": "AGENT-COST-01",
        "checkpoint_id": "W3-FINAL-REWORK-001",
        "review_need": "RECOVERY_DIAGNOSIS",
        "target_root": str(repo.resolve()),
        "branch": branch,
        "base_head": base_head,
        "reviewed_head": reviewed_head,
        "evidence_attempt": evidence_attempt,
        "contract_path": rel_contract.as_posix(),
        "contract_sha256": contract_sha,
        "diff_sha256": diff_sha,
        "evidence_manifest_path": rel_manifest.as_posix(),
        "evidence_manifest_sha256": manifest_sha,
        "pre_fingerprint": workspace_fp,
        "post_fingerprint": workspace_fp,
        "mutation_detected": False,
        "ladder_history": [],
        "regular_rework_count": 2,
        "exceptional_count": 6,
        "final_rework_count": 1,
    }
    payload.update(updates)
    return payload


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
    route: str = "checkpoint_escalation",
    binding_repo: Path | None = None,
    evidence_attempt: str | None = None,
    **updates: Any,
) -> dict[str, Any]:
    import hashlib

    if "evidence_attempt" in updates:
        evidence_attempt = str(updates.pop("evidence_attempt"))
    if evidence_attempt is None:
        evidence_attempt = f"test-handoff-{tmp_path.name}"
    rel_contract, rel_manifest = _canonical_evidence_paths(evidence_attempt, route=route)
    materialize_evidence = _is_safe_evidence_attempt_segment(evidence_attempt)
    repo = binding_repo or (
        _isolated_final_audit_binding_repo(tmp_path)
        if route == "critical_final_audit"
        else _isolated_codex_binding_repo(tmp_path)
    )
    config = json.loads((repo / ".cursor/agent-system.json").read_text(encoding="utf-8"))
    route_key = (
        "critical_final_audit" if route == "critical_final_audit" else "checkpoint_escalation"
    )
    route_record = config["external_codex_bound_review"]["review_route_bindings"]["AGENT-COST-01"][
        route_key
    ]
    allowlist = tuple(route_record["allowlist_paths"])
    base_ref = config["external_codex_bound_review"]["base_ref"]
    if materialize_evidence:
        contract = repo / rel_contract
        manifest = repo / rel_manifest
        contract.parent.mkdir(parents=True, exist_ok=True)
        contract.write_text("contract body\n", encoding="utf-8")
        _synthetic_repo_exclude_paths(repo, f"{rel_contract.parent.as_posix()}/")
        if route == "critical_final_audit":
            assert len(allowlist) == 35
            _materialize_declared_foreign(repo, config=config)
            _build_external_codex_context_manifest(
                repo,
                contract_path=rel_contract.as_posix(),
                manifest_path=rel_manifest.as_posix(),
                route=route,
                allowlist=allowlist,
                base_ref=base_ref,
            )
        else:
            assert len(allowlist) == 21
            verify_commands = tuple(route_record["verification_commands"])
            _build_route_manifest(
                repo,
                package_id="AGENT-COST-01",
                checkpoint_id="W1",
                contract_path=rel_contract.as_posix(),
                manifest_path=rel_manifest.as_posix(),
                allowlist=allowlist,
                base_ref=base_ref,
                verification_commands=verify_commands,
            )
        contract_sha = hashlib.sha256(contract.read_bytes()).hexdigest().upper()
        manifest_sha = hashlib.sha256(manifest.read_bytes()).hexdigest().upper()
    else:
        contract_sha = "0" * 64
        manifest_sha = "0" * 64
    branch = _git(repo, "branch", "--show-current").stdout.strip()
    reviewed_head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    base_head = _git(repo, "rev-parse", base_ref).stdout.strip()
    if route == "critical_final_audit":
        diff_sha = _full_diff_sha256(repo, base_ref)
        workspace_fp = _hook_workspace_fingerprint(
            repo,
            allowlist,
            base_ref=base_ref,
            scope_mode="committed_final_audit",
            checkpoint="FINAL_AUDIT",
            foreign=_declared_foreign_rules(config=config),
        )
    else:
        diff_sha = _allowlist_diff_sha256(repo, allowlist, base_ref)
        workspace_fp = _hook_workspace_fingerprint(repo, allowlist, base_ref=base_ref)
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
        "diff_sha256": diff_sha,
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
    env_overrides: dict[str, str] | None = None,
    state_path: Path | None = None,
) -> dict[str, Any]:
    repo = binding_repo or Path(str(handoff["target_root"]))
    return _run_hook(
        "subagent-start.ps1",
        {"validation_mode": mode, "handoff": handoff},
        state_path=state_path or tmp_path / "state.json",
        log_path=tmp_path / "subagent-start.log",
        cwd=repo,
        env_overrides=env_overrides,
    )


def _anchor_pre_binding_record(
    tmp_path: Path,
    handoff: dict[str, Any],
    binding_repo: Path,
    state_path: Path,
    **state_updates: Any,
) -> dict[str, Any]:
    if not state_path.exists():
        defaults: dict[str, Any] = {
            "work_package": str(handoff.get("package_id", "AGENT-COST-01")),
            "checkpoint": str(handoff.get("checkpoint_id", "W1")),
            "work_branch": str(handoff.get("branch", "feature/cursor-agent-system-v3")),
        }
        defaults.update(state_updates)
        _write_running_state(state_path, **defaults)
    pre = _run_external_codex_hook(
        tmp_path,
        _final_audit_pre_payload(handoff),
        mode="EXTERNAL_CODEX_PRE_HANDOFF",
        binding_repo=binding_repo,
        state_path=state_path,
    )
    assert pre["handoff"] == "PRE_HANDOFF_READY", _hook_result_json(pre)
    record = pre["bindingRecord"]
    assert record.get("manifest_sha256")
    assert len(str(record["manifest_sha256"])) == 64
    _write_state_binding_record(state_path, record)
    return pre


def _run_bound_after_anchored_pre(
    tmp_path: Path,
    handoff: dict[str, Any],
    binding_repo: Path,
    state_path: Path,
    **state_updates: Any,
) -> dict[str, Any]:
    _anchor_pre_binding_record(
        tmp_path,
        handoff,
        binding_repo,
        state_path,
        **state_updates,
    )
    return _run_external_codex_hook(
        tmp_path,
        handoff,
        binding_repo=binding_repo,
        state_path=state_path,
    )


def _find_route_record(
    config: dict[str, Any],
    package_id: str,
    checkpoint_id: str,
) -> dict[str, Any]:
    package_bindings = config["external_codex_bound_review"]["review_route_bindings"][package_id]
    for record in package_bindings.values():
        if record["checkpoint_id"] == checkpoint_id:
            return record
    raise KeyError(f"no route record for {package_id}/{checkpoint_id}")


def _isolated_generic_registry_repo(
    tmp_path: Path,
    *,
    extra_bindings: dict[str, Any],
) -> Path:
    repo = tmp_path / "generic-registry-repo"
    repo.mkdir()
    allowlist_paths: set[str] = set()
    for package_bindings in extra_bindings.values():
        for record in package_bindings.values():
            allowlist_paths.update(record["allowlist_paths"])
    for relative in sorted(allowlist_paths):
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
    shutil.copy2(ROOT / ".cursor/agent-system.json", repo / ".cursor/agent-system.json")
    config = json.loads((repo / ".cursor/agent-system.json").read_text(encoding="utf-8"))
    _install_review_route_bindings(config, extra_bindings)
    (repo / ".cursor/agent-system.json").write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _git(repo, "init", "-q", "-b", "feature/cursor-agent-system-v3")
    _git(repo, "config", "user.email", "tests@example.invalid")
    _git(repo, "config", "user.name", "Tests")
    _synthetic_repo_exclude_paths(
        repo,
        "build/newpkg-99/",
        "build/agent-cost-01/w2-fixture/",
        "build/agent-cost-01/w3-fixture/",
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "generic registry base")
    base_sha = _git(repo, "rev-parse", "HEAD").stdout.strip()
    config = json.loads((repo / ".cursor/agent-system.json").read_text(encoding="utf-8"))
    _sync_isolated_registry_base_refs(config, base_sha)
    (repo / ".cursor/agent-system.json").write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _git(repo, "add", ".cursor/agent-system.json")
    _git(repo, "commit", "-q", "-m", "generic registry bindings")
    return repo


def _registry_route_handoff(
    tmp_path: Path,
    *,
    binding_repo: Path,
    package_id: str,
    checkpoint_id: str,
    evidence_attempt: str,
    **updates: Any,
) -> dict[str, Any]:
    import hashlib

    config = json.loads((binding_repo / ".cursor/agent-system.json").read_text(encoding="utf-8"))
    record = _find_route_record(config, package_id, checkpoint_id)
    template = record["evidence_path_template"]
    rel_contract = Path(template["root"]) / evidence_attempt / template["contract_file"]
    rel_manifest = Path(template["root"]) / evidence_attempt / template["manifest_file"]
    allowlist = tuple(record["allowlist_paths"])
    base_ref = config["external_codex_bound_review"]["base_ref"]
    contract = binding_repo / rel_contract
    manifest = binding_repo / rel_manifest
    contract.parent.mkdir(parents=True, exist_ok=True)
    contract.write_text(f"contract for {package_id}/{checkpoint_id}\n", encoding="utf-8")
    _synthetic_repo_exclude_paths(binding_repo, f"{rel_contract.parent.as_posix()}/")
    _build_route_manifest(
        binding_repo,
        package_id=package_id,
        checkpoint_id=checkpoint_id,
        contract_path=rel_contract.as_posix(),
        manifest_path=rel_manifest.as_posix(),
        allowlist=allowlist,
        base_ref=base_ref,
        verification_commands=tuple(record["verification_commands"]),
    )
    branch = _git(binding_repo, "branch", "--show-current").stdout.strip()
    reviewed_head = _git(binding_repo, "rev-parse", "HEAD").stdout.strip()
    base_head = _git(binding_repo, "rev-parse", base_ref).stdout.strip()
    diff_sha = _allowlist_diff_sha256(binding_repo, allowlist, base_ref)
    workspace_fp = _hook_workspace_fingerprint(binding_repo, allowlist, base_ref=base_ref)
    if record.get("forbid_ladder_history") or record.get("direct_external"):
        ladder_history: list[dict[str, Any]] = []
    else:
        ladder_history = _complete_w1_ladder_history()
    payload = {
        "agent_id": f"codex-{package_id.lower()}",
        "task_id": f"task-{checkpoint_id.lower()}",
        "external_host": "codex-chatgpt-authenticated",
        "separate_context": True,
        "read_only": True,
        "author_id": "author-1",
        "implementer_id": "impl-1",
        "reviewer_id": "reviewer-1",
        "package_id": package_id,
        "checkpoint_id": checkpoint_id,
        "review_need": record["review_need"],
        "target_root": str(binding_repo.resolve()),
        "branch": branch,
        "base_head": base_head,
        "reviewed_head": reviewed_head,
        "evidence_attempt": evidence_attempt,
        "contract_path": rel_contract.as_posix(),
        "contract_sha256": hashlib.sha256(contract.read_bytes()).hexdigest().upper(),
        "diff_sha256": diff_sha,
        "evidence_manifest_path": rel_manifest.as_posix(),
        "evidence_manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest().upper(),
        "pre_fingerprint": workspace_fp,
        "post_fingerprint": workspace_fp,
        "mutation_detected": False,
        "ladder_history": ladder_history,
        "requested_model": "UNAVAILABLE",
        "observed_model": "UNAVAILABLE",
        "verdict": "PASS",
        "findings": [],
    }
    payload.update(updates)
    return payload


def _run_final_audit_pre_handoff(
    tmp_path: Path,
    handoff: dict[str, Any],
    binding_repo: Path,
    *,
    env_overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    return _run_external_codex_hook(
        tmp_path,
        _final_audit_pre_payload(handoff),
        mode="EXTERNAL_CODEX_PRE_HANDOFF",
        binding_repo=binding_repo,
        env_overrides=env_overrides,
    )


def _rebind_final_audit_handoff(handoff: dict[str, Any], binding_repo: Path) -> None:
    config = json.loads((binding_repo / ".cursor/agent-system.json").read_text(encoding="utf-8"))
    allowlist = tuple(config["external_codex_bound_review"]["w3_allowlist_paths"])
    base_ref = config["external_codex_bound_review"]["base_ref"]
    handoff["branch"] = _git(binding_repo, "branch", "--show-current").stdout.strip()
    handoff["reviewed_head"] = _git(binding_repo, "rev-parse", "HEAD").stdout.strip()
    handoff["base_head"] = _git(binding_repo, "rev-parse", base_ref).stdout.strip()
    handoff["diff_sha256"] = _full_diff_sha256(binding_repo, base_ref)
    workspace_fp = _hook_workspace_fingerprint(
        binding_repo,
        allowlist,
        base_ref=base_ref,
        scope_mode="committed_final_audit",
        checkpoint="FINAL_AUDIT",
        foreign=_declared_foreign_rules(config=config),
    )
    handoff["pre_fingerprint"] = workspace_fp
    handoff["post_fingerprint"] = workspace_fp


def _handoff_manifest_path(binding_repo: Path, handoff: dict[str, Any]) -> Path:
    return binding_repo / handoff["evidence_manifest_path"]


def _read_handoff_manifest(binding_repo: Path, handoff: dict[str, Any]) -> dict[str, Any]:
    return json.loads(_handoff_manifest_path(binding_repo, handoff).read_text(encoding="utf-8"))


def _write_handoff_manifest(
    binding_repo: Path,
    handoff: dict[str, Any],
    manifest: dict[str, Any],
) -> None:
    import hashlib

    path = _handoff_manifest_path(binding_repo, handoff)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    handoff["evidence_manifest_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _commit_config_base_ref(binding_repo: Path, base_ref: str) -> None:
    config = json.loads((binding_repo / ".cursor/agent-system.json").read_text(encoding="utf-8"))
    config["external_codex_bound_review"]["base_ref"] = base_ref
    _sync_isolated_registry_base_refs(config, base_ref)
    (binding_repo / ".cursor/agent-system.json").write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _git(binding_repo, "add", ".cursor/agent-system.json")
    _git(binding_repo, "commit", "-q", "-m", "update base ref")


def _install_manifest_validate_double(repo: Path, *, mode: str) -> None:
    script = repo / ".cursor/skills/execute-gated-macro/scripts/checkpoint_snapshot.py"
    real_script = script.with_suffix(".real.py")
    if not real_script.exists():
        shutil.copy2(script, real_script)
    real_path = str(real_script).replace("\\", "\\\\")
    if mode == "valid_false_exit0":
        body = f'''import json
import subprocess
import sys

REAL = r"{real_path}"

def main() -> int:
    if len(sys.argv) >= 2 and sys.argv[1] == "manifest-validate":
        print(json.dumps({{"valid": False, "reasons": ["test_double_valid_false"]}}, indent=2, sort_keys=True))
        return 0
    return subprocess.call([sys.executable, REAL, *sys.argv[1:]])

if __name__ == "__main__":
    raise SystemExit(main())
'''
    elif mode == "exit2_empty_stdout":
        body = f'''import subprocess
import sys

REAL = r"{real_path}"

def main() -> int:
    if len(sys.argv) >= 2 and sys.argv[1] == "manifest-validate":
        return 2
    return subprocess.call([sys.executable, REAL, *sys.argv[1:]])

if __name__ == "__main__":
    raise SystemExit(main())
'''
    else:
        raise ValueError(f"unsupported manifest validate double mode: {mode}")
    script.write_text(body, encoding="utf-8")
    _synthetic_repo_exclude_paths(
        repo,
        ".cursor/skills/execute-gated-macro/scripts/checkpoint_snapshot.real.py",
    )


def _git_shim_env(
    tmp_path: Path,
    *,
    mode: str,
) -> dict[str, str]:
    shim_dir = tmp_path / "git-shim"
    shim_dir.mkdir(exist_ok=True)
    real_git = shutil.which("git")
    if not real_git:
        raise RuntimeError("git executable not found for shim")
    launcher = shim_dir / "git_shim.py"
    launcher.write_text(
        f"""import subprocess
import sys

REAL = r"{real_git.replace(chr(92), chr(92) * 2)}"
MODE = "{mode}"

def _rest(args: list[str]) -> list[str]:
    if len(args) >= 2 and args[0] == "-C":
        return args[2:]
    return args

def _fail() -> None:
    print("synthetic git shim failure", file=sys.stderr)
    raise SystemExit(2)

args = sys.argv[1:]
rest = _rest(args)
if MODE == "final_diff":
    if len(rest) >= 3 and rest[0] == "diff" and rest[-1] == "HEAD":
        _fail()
elif MODE == "foreign_cached":
    if len(rest) >= 3 and rest[0] == "diff" and rest[1] == "--cached" and rest[2] == "--name-only":
        _fail()
elif MODE == "foreign_unstaged":
    if rest[:2] == ["diff", "--name-only"]:
        _fail()
elif MODE == "foreign_untracked":
    if rest[:3] == ["ls-files", "--others", "--exclude-standard"]:
        _fail()
else:
    raise SystemExit(f"unknown git shim mode: {{MODE}}")
raise SystemExit(subprocess.call([REAL, *args]))
""",
        encoding="utf-8",
    )
    if os.name == "nt":
        wrapper = shim_dir / "git.ps1"
        wrapper.write_text(
            f'& "{sys.executable}" "{launcher}" @args\n'
            f"exit $LASTEXITCODE\n",
            encoding="utf-8",
        )
    else:
        wrapper = shim_dir / "git"
        wrapper.write_text(
            f'#!/usr/bin/env python3\nimport runpy\nrunpy.run_path(r"{launcher}", run_name="__main__")\n',
            encoding="utf-8",
        )
        wrapper.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = str(shim_dir) + os.pathsep + env.get("PATH", "")
    return env


def _same_length_foreign_cli_mutation(original: bytes) -> bytes:
    mutated = bytearray(original)
    for index, byte in enumerate(mutated):
        if byte in (ord("a"), ord("z"), ord("0")):
            mutated[index] = byte + 1
            break
    else:
        mutated[0] = (mutated[0] + 1) % 256
    assert len(mutated) == len(original)
    return bytes(mutated)


def test_external_codex_bound_review_hook_owner(tmp_path: Path) -> None:
    binding_repo = _isolated_codex_binding_repo(tmp_path)
    handoff = _external_codex_handoff(tmp_path, binding_repo=binding_repo)
    state_path = tmp_path / "hook-owner-state.json"
    pre_ok = _anchor_pre_binding_record(tmp_path, handoff, binding_repo, state_path)
    assert pre_ok["status"] == "READY"
    ok = _run_external_codex_hook(
        tmp_path,
        handoff,
        binding_repo=binding_repo,
        state_path=state_path,
    )
    assert ok["handoff"] == "HANDOFF_READY"
    assert ok["authenticates_origin"] is False
    assert ok["authenticates_serving_model"] is False

    critical_fields = _config()["external_codex_bound_review"]["bound_review_required_fields"]
    for field in critical_fields:
        missing = dict(handoff)
        del missing[field]
        invalid_state = tmp_path / f"missing-{field}-state.json"
        _anchor_pre_binding_record(tmp_path, handoff, binding_repo, invalid_state)
        result = _run_external_codex_hook(
            tmp_path,
            missing,
            binding_repo=binding_repo,
            state_path=invalid_state,
        )
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
        invalid_state = tmp_path / f"invalid-{label}-state.json"
        _anchor_pre_binding_record(tmp_path, handoff, binding_repo, invalid_state)
        bad = _run_external_codex_hook(
            tmp_path,
            {**handoff, **updates},
            binding_repo=binding_repo,
            state_path=invalid_state,
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
    escalation = bindings["checkpoint_escalation"]
    assert escalation["checkpoint_id"] == "W1"
    assert escalation["review_need"] == "CHECKPOINT_ESCALATION"
    assert escalation["ladder_role"] == "checkpoint-reviewer"
    assert escalation["require_complete_ladder"] is True
    assert escalation["package_id"] == "AGENT-COST-01"
    assert escalation["allowlist_paths"]
    final_audit = bindings["critical_final_audit"]
    assert final_audit["checkpoint_id"] == "FINAL_AUDIT"
    assert final_audit["review_need"] == "FINAL_AUDIT"
    assert final_audit["direct_external"] is True
    assert final_audit["forbid_ladder_history"] is True
    recovery = bindings["recovery_diagnosis"]
    assert recovery["review_need"] == "RECOVERY_DIAGNOSIS"
    assert recovery["purpose"] == "diagnosis"


def test_external_codex_evidence_attempt_containment(tmp_path: Path) -> None:
    rel_contract, rel_manifest = _canonical_evidence_paths(f"test-handoff-{tmp_path.name}")
    binding_repo = _isolated_codex_binding_repo(tmp_path)
    safe = _external_codex_handoff(tmp_path, binding_repo=binding_repo)
    state_path = tmp_path / "containment-state.json"
    assert (
        _run_bound_after_anchored_pre(
            tmp_path,
            safe,
            binding_repo,
            state_path,
        )["handoff"]
        == "HANDOFF_READY"
    )
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
    binding_repo = _isolated_codex_binding_repo(tmp_path)
    escalation_handoff = _external_codex_handoff(
        tmp_path, route="checkpoint_escalation", binding_repo=binding_repo
    )
    escalation_state = tmp_path / "escalation-bound-state.json"
    escalation = _run_bound_after_anchored_pre(
        tmp_path,
        escalation_handoff,
        binding_repo,
        escalation_state,
        checkpoint="W1",
    )
    assert escalation["handoff"] == "HANDOFF_READY"

    audit_repo = _isolated_final_audit_binding_repo(tmp_path)
    audit_handoff = _external_codex_handoff(
        tmp_path, route="critical_final_audit", binding_repo=audit_repo
    )
    audit_state = tmp_path / "final-audit-bound-state.json"
    final_audit = _run_bound_after_anchored_pre(
        tmp_path,
        audit_handoff,
        audit_repo,
        audit_state,
        checkpoint="FINAL_AUDIT",
    )
    assert final_audit["handoff"] == "HANDOFF_READY"

    _anchor_pre_binding_record(
        tmp_path,
        escalation_handoff,
        binding_repo,
        tmp_path / "route-mismatch-state.json",
        checkpoint="W1",
    )
    route_mismatch = _run_external_codex_hook(
        tmp_path,
        {
            **escalation_handoff,
            "checkpoint_id": "W1",
            "review_need": "FINAL_AUDIT",
            "ladder_history": _complete_w1_ladder_history(),
        },
        binding_repo=binding_repo,
        state_path=tmp_path / "route-mismatch-state.json",
    )
    assert route_mismatch["handoff"] == "HANDOFF_INVALID"

    _anchor_pre_binding_record(
        tmp_path,
        audit_handoff,
        audit_repo,
        tmp_path / "ladder-on-direct-state.json",
        checkpoint="FINAL_AUDIT",
    )
    ladder_on_direct = _run_external_codex_hook(
        tmp_path,
        {
            **audit_handoff,
            "checkpoint_id": "FINAL_AUDIT",
            "review_need": "FINAL_AUDIT",
            "ladder_history": _complete_w1_ladder_history(),
        },
        binding_repo=audit_repo,
        state_path=tmp_path / "ladder-on-direct-state.json",
    )
    assert ladder_on_direct["handoff"] == "HANDOFF_INVALID"

    _anchor_pre_binding_record(
        tmp_path,
        escalation_handoff,
        binding_repo,
        tmp_path / "wrong-checkpoint-state.json",
        checkpoint="W1",
    )
    wrong_checkpoint = _run_external_codex_hook(
        tmp_path,
        {
            **escalation_handoff,
            "checkpoint_id": "W2",
            "review_need": "CHECKPOINT_ESCALATION",
        },
        binding_repo=binding_repo,
        state_path=tmp_path / "wrong-checkpoint-state.json",
    )
    assert wrong_checkpoint["handoff"] == "HANDOFF_INVALID"

    _anchor_pre_binding_record(
        tmp_path,
        escalation_handoff,
        binding_repo,
        tmp_path / "missing-ladder-state.json",
        checkpoint="W1",
    )
    missing_ladder = _run_external_codex_hook(
        tmp_path,
        {**escalation_handoff, "ladder_history": []},
        binding_repo=binding_repo,
        state_path=tmp_path / "missing-ladder-state.json",
    )
    assert missing_ladder["handoff"] == "HANDOFF_INVALID"

    _anchor_pre_binding_record(
        tmp_path,
        escalation_handoff,
        binding_repo,
        tmp_path / "substantive-fail-state.json",
        checkpoint="W1",
    )
    substantive_fail = _run_external_codex_hook(
        tmp_path,
        {
            **escalation_handoff,
            "ladder_history": _substitute_ladder_result(
                _complete_w1_ladder_history(), 2, "FAIL_SUBSTANTIVE"
            ),
        },
        binding_repo=binding_repo,
        state_path=tmp_path / "substantive-fail-state.json",
    )
    assert substantive_fail["handoff"] == "HANDOFF_INVALID"

    wrong_ladder_model = _complete_w1_ladder_history()
    wrong_ladder_model[0] = {
        **wrong_ladder_model[0],
        "requested_model": "cursor-grok-4.6-xhigh",
    }
    _anchor_pre_binding_record(
        tmp_path,
        escalation_handoff,
        binding_repo,
        tmp_path / "wrong-model-state.json",
        checkpoint="W1",
    )
    wrong_model = _run_external_codex_hook(
        tmp_path,
        {**escalation_handoff, "ladder_history": wrong_ladder_model},
        binding_repo=binding_repo,
        state_path=tmp_path / "wrong-model-state.json",
    )
    assert wrong_model["handoff"] == "HANDOFF_INVALID"


def test_external_codex_config_declares_w3_final_audit_route_fields() -> None:
    contract = _config()["external_codex_bound_review"]
    assert contract["base_ref"] == "4bedcc84cd81a46b6e8802a3a6b2296f9f5f9d5c"
    assert len(contract["w3_allowlist_paths"]) == 35
    assert contract["final_audit_evidence_path_template"]["root"] == "build/agent-cost-01/w3"
    assert contract["evidence_path_template"]["root"] == "build/agent-cost-01/w1"
    bindings = contract["declared_foreign_bindings"]
    assert {item["path"] for item in bindings} == {".cursor/cli.json", "agent", "models"}


def test_final_audit_canonical_evidence_paths_use_w3_root() -> None:
    contract, manifest = _canonical_evidence_paths("attempt-001", route="critical_final_audit")
    assert contract.as_posix() == "build/agent-cost-01/w3/attempt-001/checkpoint-contract.md"
    assert manifest.as_posix() == "build/agent-cost-01/w3/attempt-001/context-manifest.json"
    w1_contract, _ = _canonical_evidence_paths("attempt-001", route="checkpoint_escalation")
    assert w1_contract.as_posix().startswith("build/agent-cost-01/w1/")


def test_final_audit_pre_handoff_accepts_clean_committed_candidate(tmp_path: Path) -> None:
    binding_repo = _isolated_final_audit_binding_repo(tmp_path)
    handoff = _external_codex_handoff(
        tmp_path, route="critical_final_audit", binding_repo=binding_repo
    )
    result = _run_external_codex_hook(
        tmp_path,
        _final_audit_pre_payload(handoff),
        mode="EXTERNAL_CODEX_PRE_HANDOFF",
        binding_repo=binding_repo,
    )
    assert result["handoff"] == "PRE_HANDOFF_READY"


def test_final_audit_denies_dirty_tracked_allowlist_path(tmp_path: Path) -> None:
    binding_repo = _isolated_final_audit_binding_repo(tmp_path)
    handoff = _external_codex_handoff(
        tmp_path, route="critical_final_audit", binding_repo=binding_repo
    )
    dirty_owner = binding_repo / ".cursor/agent-system.json"
    dirty_owner.write_text(dirty_owner.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    result = _run_external_codex_hook(
        tmp_path,
        _final_audit_pre_payload(handoff),
        mode="EXTERNAL_CODEX_PRE_HANDOFF",
        binding_repo=binding_repo,
    )
    assert result["handoff"] == "HANDOFF_INVALID"
    assert "dirty_tracked_or_index" in result["reason"]
    assert ".cursor/agent-system.json" in result["reason"]


def test_final_audit_denies_noncanonical_evidence_root_override(tmp_path: Path) -> None:
    binding_repo = _isolated_final_audit_binding_repo(tmp_path)
    handoff = _external_codex_handoff(
        tmp_path, route="critical_final_audit", binding_repo=binding_repo
    )
    pre_payload = _final_audit_pre_payload(handoff)
    pre_payload["contract_path"] = "build/agent-cost-01/w1/forged/checkpoint-contract.md"
    result = _run_external_codex_hook(
        tmp_path, pre_payload, mode="EXTERNAL_CODEX_PRE_HANDOFF", binding_repo=binding_repo
    )
    assert result["handoff"] == "HANDOFF_INVALID"
    assert "contract path not canonical" in result["reason"]


def test_final_audit_foreign_exact_match_accepts_untracked_hashes(tmp_path: Path) -> None:
    binding_repo = _isolated_final_audit_binding_repo(tmp_path)
    handoff = _external_codex_handoff(
        tmp_path, route="critical_final_audit", binding_repo=binding_repo
    )
    result = _run_external_codex_hook(
        tmp_path,
        _final_audit_pre_payload(handoff),
        mode="EXTERNAL_CODEX_PRE_HANDOFF",
        binding_repo=binding_repo,
    )
    assert result["handoff"] == "PRE_HANDOFF_READY"


def test_final_audit_foreign_child_path_denied(tmp_path: Path) -> None:
    binding_repo = _isolated_final_audit_binding_repo(tmp_path)
    handoff = _external_codex_handoff(
        tmp_path, route="critical_final_audit", binding_repo=binding_repo
    )
    (binding_repo / "agent").unlink(missing_ok=True)
    child = binding_repo / "agent/nested.txt"
    child.parent.mkdir(parents=True, exist_ok=True)
    child.write_text("child\n", encoding="utf-8")
    result = _run_external_codex_hook(
        tmp_path,
        _final_audit_pre_payload(handoff),
        mode="EXTERNAL_CODEX_PRE_HANDOFF",
        binding_repo=binding_repo,
    )
    assert result["handoff"] == "HANDOFF_INVALID"
    assert "foreign child" in result["reason"]


def test_w1_escalation_route_still_uses_w1_allowlist_and_root(tmp_path: Path) -> None:
    rel_contract, rel_manifest = _canonical_evidence_paths(
        f"test-handoff-{tmp_path.name}", route="checkpoint_escalation"
    )
    binding_repo = _isolated_codex_binding_repo(tmp_path)
    handoff = _external_codex_handoff(
        tmp_path, route="checkpoint_escalation", binding_repo=binding_repo
    )
    assert handoff["contract_path"].startswith("build/agent-cost-01/w1/")
    state_path = tmp_path / "w1-escalation-state.json"
    result = _run_bound_after_anchored_pre(
        tmp_path,
        handoff,
        binding_repo,
        state_path,
        checkpoint="W1",
    )
    assert result["handoff"] == "HANDOFF_READY"


def test_w3_prep_negative_prehandoff_denies_dirty_allowlist_owner(tmp_path: Path) -> None:
    binding_repo = _isolated_final_audit_binding_repo(tmp_path)
    handoff = _external_codex_handoff(
        tmp_path, route="critical_final_audit", binding_repo=binding_repo
    )
    dirty_owner = binding_repo / ".cursor/agent-system.json"
    dirty_owner.write_text(dirty_owner.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    result = _run_external_codex_hook(
        tmp_path,
        _final_audit_pre_payload(handoff),
        mode="EXTERNAL_CODEX_PRE_HANDOFF",
        binding_repo=binding_repo,
    )
    assert result["handoff"] == "HANDOFF_INVALID"
    assert "dirty_tracked_or_index" in result["reason"]
    assert ".cursor/agent-system.json" in result["reason"]
    assert "foreign path hash mismatch" not in result["reason"]


def test_final_audit_snapshot_denies_missing_base_ref(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "tests@example.invalid")
    _git(repo, "config", "user.name", "Tests")
    (repo / "allowed.txt").write_text("v1\n", encoding="utf-8")
    _git(repo, "add", "allowed.txt")
    _git(repo, "commit", "-q", "-m", "only")
    output = "build/pt/final-audit-missing-base.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / ".cursor/skills/execute-gated-macro/scripts/checkpoint_snapshot.py"),
            "snapshot",
            "--root",
            str(repo),
            "--checkpoint",
            "FINAL_AUDIT",
            "--phase",
            "missing-base",
            "--output",
            output,
            "--allow",
            "allowed.txt",
            "--base-ref",
            "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
            "--scope-mode",
            "committed_final_audit",
            "--fail-on-denial",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 2
    payload = json.loads((repo / output).read_text(encoding="utf-8"))
    assert payload["denial_reasons"]
    assert str(payload["denial_reasons"][0]).startswith("base_failure:")


def test_final_audit_denies_committed_out_of_scope_path(tmp_path: Path) -> None:
    binding_repo = _isolated_final_audit_binding_repo(tmp_path)
    handoff = _external_codex_handoff(
        tmp_path, route="critical_final_audit", binding_repo=binding_repo
    )
    rogue = binding_repo / "rogue-product.txt"
    rogue.write_text("forbidden\n", encoding="utf-8")
    _git(binding_repo, "add", "rogue-product.txt")
    _git(binding_repo, "commit", "-q", "-m", "out of scope")
    result = _run_external_codex_hook(
        tmp_path,
        _final_audit_pre_payload(handoff),
        mode="EXTERNAL_CODEX_PRE_HANDOFF",
        binding_repo=binding_repo,
    )
    assert result["handoff"] == "HANDOFF_INVALID"
    assert "rogue-product.txt" in result["reason"]
    assert result["reason"].startswith("out-of-scope repository mutation:")


def test_final_audit_snapshot_records_rename_both_sides(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "tests@example.invalid")
    _git(repo, "config", "user.name", "Tests")
    old = repo / "old-name.txt"
    old.write_text("v1\n", encoding="utf-8")
    _git(repo, "add", "old-name.txt")
    _git(repo, "commit", "-q", "-m", "base")
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    _git(repo, "mv", "old-name.txt", "new-name.txt")
    _git(repo, "commit", "-q", "-m", "rename")
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / ".cursor/skills/execute-gated-macro/scripts/checkpoint_snapshot.py"),
            "snapshot",
            "--root",
            str(repo),
            "--checkpoint",
            "FINAL_AUDIT",
            "--phase",
            "rename",
            "--output",
            "build/pt/final-rename.json",
            "--allow",
            "old-name.txt",
            "--allow",
            "new-name.txt",
            "--base-ref",
            base,
            "--scope-mode",
            "committed_final_audit",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads((repo / "build/pt/final-rename.json").read_text(encoding="utf-8"))
    assert set(payload["committed_paths"]) == {"old-name.txt", "new-name.txt"}


def test_final_audit_snapshot_denies_rename_out_of_scope_side(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "tests@example.invalid")
    _git(repo, "config", "user.name", "Tests")
    old = repo / "old-name.txt"
    old.write_text("v1\n", encoding="utf-8")
    _git(repo, "add", "old-name.txt")
    _git(repo, "commit", "-q", "-m", "base")
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    _git(repo, "mv", "old-name.txt", "new-name.txt")
    _git(repo, "commit", "-q", "-m", "rename")
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / ".cursor/skills/execute-gated-macro/scripts/checkpoint_snapshot.py"),
            "snapshot",
            "--root",
            str(repo),
            "--checkpoint",
            "FINAL_AUDIT",
            "--phase",
            "rename-deny",
            "--output",
            "build/pt/final-rename-deny.json",
            "--allow",
            "old-name.txt",
            "--base-ref",
            base,
            "--scope-mode",
            "committed_final_audit",
            "--fail-on-out-of-scope",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 2
    payload = json.loads((repo / "build/pt/final-rename-deny.json").read_text(encoding="utf-8"))
    assert "new-name.txt" in payload["out_of_scope_paths"]


def test_final_audit_foreign_staged_file_denied(tmp_path: Path) -> None:
    binding_repo = _isolated_final_audit_binding_repo(tmp_path)
    handoff = _external_codex_handoff(
        tmp_path, route="critical_final_audit", binding_repo=binding_repo
    )
    (binding_repo / "agent").unlink(missing_ok=True)
    staged = binding_repo / "agent"
    staged.write_bytes(b"")
    _git(binding_repo, "add", "agent")
    result = _run_external_codex_hook(
        tmp_path,
        _final_audit_pre_payload(handoff),
        mode="EXTERNAL_CODEX_PRE_HANDOFF",
        binding_repo=binding_repo,
    )
    assert result["handoff"] == "HANDOFF_INVALID"
    assert result["reason"] == "foreign path staged denied: agent"


def test_final_audit_pre_handoff_rejects_forged_full_diff(tmp_path: Path) -> None:
    binding_repo = _isolated_final_audit_binding_repo(tmp_path)
    handoff = _external_codex_handoff(
        tmp_path, route="critical_final_audit", binding_repo=binding_repo
    )
    pre_payload = _final_audit_pre_payload(handoff)
    pre_payload["diff_sha256"] = "0" * 64
    result = _run_external_codex_hook(
        tmp_path,
        pre_payload,
        mode="EXTERNAL_CODEX_PRE_HANDOFF",
        binding_repo=binding_repo,
    )
    assert result["handoff"] == "HANDOFF_INVALID"
    assert result["reason"] == "stale diff"


def test_final_audit_foreign_missing_expected_binding_denied(tmp_path: Path) -> None:
    binding_repo = _isolated_final_audit_binding_repo(tmp_path)
    handoff = _external_codex_handoff(
        tmp_path, route="critical_final_audit", binding_repo=binding_repo
    )
    (binding_repo / "agent").unlink(missing_ok=True)
    result = _run_external_codex_hook(
        tmp_path,
        _final_audit_pre_payload(handoff),
        mode="EXTERNAL_CODEX_PRE_HANDOFF",
        binding_repo=binding_repo,
    )
    assert result["handoff"] == "HANDOFF_INVALID"
    assert "missing expected foreign binding" in result["reason"]


def test_final_audit_accepts_w2_only_committed_owner_in_full_diff(tmp_path: Path) -> None:
    binding_repo = _isolated_final_audit_binding_repo(tmp_path)
    w2_owner = binding_repo / ".cursor/hooks/git-guard.ps1"
    w2_owner.write_text(w2_owner.read_text(encoding="utf-8") + "# w2-only\n", encoding="utf-8")
    _git(binding_repo, "add", ".cursor/hooks/git-guard.ps1")
    _git(binding_repo, "commit", "-q", "-m", "w2-only owner")
    handoff = _external_codex_handoff(
        tmp_path, route="critical_final_audit", binding_repo=binding_repo
    )
    result = _run_external_codex_hook(
        tmp_path,
        _final_audit_pre_payload(handoff),
        mode="EXTERNAL_CODEX_PRE_HANDOFF",
        binding_repo=binding_repo,
    )
    assert result["handoff"] == "PRE_HANDOFF_READY"


def test_final_audit_rejects_stale_w1_only_diff_hash(tmp_path: Path) -> None:
    import hashlib

    binding_repo = _isolated_final_audit_binding_repo(tmp_path)
    w2_owner = binding_repo / ".cursor/hooks/git-guard.ps1"
    w2_owner.write_text(w2_owner.read_text(encoding="utf-8") + "# w2-only\n", encoding="utf-8")
    _git(binding_repo, "add", ".cursor/hooks/git-guard.ps1")
    _git(binding_repo, "commit", "-q", "-m", "w2-only owner")
    handoff = _external_codex_handoff(
        tmp_path, route="critical_final_audit", binding_repo=binding_repo
    )
    pre_payload = _final_audit_pre_payload(handoff)
    w1_allowlist = tuple(_config()["external_codex_bound_review"]["w1_allowlist_paths"])
    w1_only_diff = subprocess.run(
        ["git", "diff", handoff["base_head"], "--", *w1_allowlist],
        cwd=binding_repo,
        capture_output=True,
        check=False,
    ).stdout.decode("utf-8", errors="surrogateescape").replace("\r\n", "\n")
    assert w1_only_diff != subprocess.run(
        ["git", "diff", handoff["base_head"]],
        cwd=binding_repo,
        capture_output=True,
        check=False,
    ).stdout.decode("utf-8", errors="surrogateescape").replace("\r\n", "\n")
    pre_payload["diff_sha256"] = hashlib.sha256(w1_only_diff.encode("utf-8")).hexdigest().upper()
    result = _run_external_codex_hook(
        tmp_path,
        pre_payload,
        mode="EXTERNAL_CODEX_PRE_HANDOFF",
        binding_repo=binding_repo,
    )
    assert result["handoff"] == "HANDOFF_INVALID"
    assert result["reason"] == "stale diff"


def test_final_audit_foreign_hash_mismatch_denied(tmp_path: Path) -> None:
    binding_repo = _isolated_final_audit_binding_repo(tmp_path)
    handoff = _external_codex_handoff(
        tmp_path, route="critical_final_audit", binding_repo=binding_repo
    )
    cli = binding_repo / ".cursor/cli.json"
    original = cli.read_bytes()
    cli.write_bytes(_same_length_foreign_cli_mutation(original))
    result = _run_external_codex_hook(
        tmp_path,
        _final_audit_pre_payload(handoff),
        mode="EXTERNAL_CODEX_PRE_HANDOFF",
        binding_repo=binding_repo,
    )
    assert result["handoff"] == "HANDOFF_INVALID"
    assert "foreign path hash mismatch" in result["reason"]


def test_final_audit_foreign_committed_file_denied(tmp_path: Path) -> None:
    binding_repo = _isolated_final_audit_binding_repo(tmp_path)
    handoff = _external_codex_handoff(
        tmp_path, route="critical_final_audit", binding_repo=binding_repo
    )
    _git(binding_repo, "add", "agent")
    _git(binding_repo, "commit", "-q", "-m", "commit foreign")
    result = _run_external_codex_hook(
        tmp_path,
        _final_audit_pre_payload(handoff),
        mode="EXTERNAL_CODEX_PRE_HANDOFF",
        binding_repo=binding_repo,
    )
    assert result["handoff"] == "HANDOFF_INVALID"
    assert "foreign path must remain untracked" in result["reason"]


def test_final_audit_snapshot_denies_extra_untracked_out_of_scope(tmp_path: Path) -> None:
    binding_repo = _isolated_final_audit_binding_repo(tmp_path)
    config = json.loads((binding_repo / ".cursor/agent-system.json").read_text(encoding="utf-8"))
    allowlist = config["external_codex_bound_review"]["w3_allowlist_paths"]
    base_ref = config["external_codex_bound_review"]["base_ref"]
    (binding_repo / "rogue-untracked.txt").write_text("unexpected\n", encoding="utf-8")
    output = "build/pt/final-audit-extra-untracked.json"
    cmd = [
        sys.executable,
        str(ROOT / ".cursor/skills/execute-gated-macro/scripts/checkpoint_snapshot.py"),
        "snapshot",
        "--root",
        str(binding_repo),
        "--checkpoint",
        "FINAL_AUDIT",
        "--phase",
        "extra-untracked",
        "--output",
        output,
        "--base-ref",
        base_ref,
        "--scope-mode",
        "committed_final_audit",
        "--fail-on-out-of-scope",
        "--fail-on-denial",
    ]
    for path in allowlist:
        cmd.extend(["--allow", path])
    for path in _declared_foreign_rules(config=config):
        cmd.extend(["--foreign", path])
    completed = subprocess.run(
        cmd,
        cwd=binding_repo,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 2
    payload = json.loads((binding_repo / output).read_text(encoding="utf-8"))
    assert "rogue-untracked.txt" in payload["out_of_scope_paths"]


def test_final_audit_snapshot_denies_committed_out_of_scope_deletion(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "tests@example.invalid")
    _git(repo, "config", "user.name", "Tests")
    allowed = repo / "allowed.txt"
    allowed.write_text("v1\n", encoding="utf-8")
    rogue = repo / "rogue-committed.txt"
    rogue.write_text("forbidden\n", encoding="utf-8")
    _git(repo, "add", "allowed.txt", "rogue-committed.txt")
    _git(repo, "commit", "-q", "-m", "base")
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    _git(repo, "rm", "rogue-committed.txt")
    _git(repo, "commit", "-q", "-m", "delete out-of-scope path")
    output = "build/pt/final-audit-deletion.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / ".cursor/skills/execute-gated-macro/scripts/checkpoint_snapshot.py"),
            "snapshot",
            "--root",
            str(repo),
            "--checkpoint",
            "FINAL_AUDIT",
            "--phase",
            "deletion",
            "--output",
            output,
            "--allow",
            "allowed.txt",
            "--base-ref",
            base,
            "--scope-mode",
            "committed_final_audit",
            "--fail-on-out-of-scope",
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 2
    payload = json.loads((repo / output).read_text(encoding="utf-8"))
    assert "rogue-committed.txt" in payload["out_of_scope_paths"]


def test_final_audit_hook_denies_missing_base_ref(tmp_path: Path) -> None:
    binding_repo = _isolated_final_audit_binding_repo(tmp_path)
    handoff = _external_codex_handoff(
        tmp_path, route="critical_final_audit", binding_repo=binding_repo
    )
    invalid_base = "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
    _commit_config_base_ref(binding_repo, invalid_base)
    handoff["reviewed_head"] = _git(binding_repo, "rev-parse", "HEAD").stdout.strip()
    handoff["base_head"] = invalid_base
    result = _run_final_audit_pre_handoff(tmp_path, handoff, binding_repo)
    _assert_hook_result(
        result,
        handoff="HANDOFF_INVALID",
        reason="git rev-parse base failed for final audit binding",
    )


def test_final_audit_hook_denies_non_ancestor_base(tmp_path: Path) -> None:
    binding_repo = _isolated_final_audit_binding_repo(tmp_path)
    handoff = _external_codex_handoff(
        tmp_path, route="critical_final_audit", binding_repo=binding_repo
    )
    _git(binding_repo, "checkout", "--orphan", "disconnected-head")
    (binding_repo / ".orphan-root").write_text("orphan\n", encoding="utf-8")
    _git(binding_repo, "add", ".orphan-root")
    _git(binding_repo, "commit", "-q", "-m", "orphan root")
    result = _run_final_audit_pre_handoff(tmp_path, handoff, binding_repo)
    assert result["handoff"] == "HANDOFF_INVALID"
    assert result["reason"] == "base ref is not an ancestor of HEAD"


def test_final_audit_hook_denies_git_diff_binding_failure(tmp_path: Path) -> None:
    binding_repo = _isolated_final_audit_binding_repo(tmp_path)
    handoff = _external_codex_handoff(
        tmp_path, route="critical_final_audit", binding_repo=binding_repo
    )
    shim_env = _git_shim_env(tmp_path, mode="final_diff")
    result = _run_final_audit_pre_handoff(
        tmp_path,
        handoff,
        binding_repo,
        env_overrides=shim_env,
    )
    assert result["handoff"] == "HANDOFF_INVALID"
    assert result["reason"] == "git diff failed for final audit binding"


def test_final_audit_hook_empty_diff_success_not_git_failure(tmp_path: Path) -> None:
    import hashlib

    binding_repo = _prepare_final_audit_empty_diff_binding_repo(tmp_path)
    config = json.loads((binding_repo / ".cursor/agent-system.json").read_text(encoding="utf-8"))
    assert config["external_codex_bound_review"]["base_ref"] == "HEAD"
    empty_diff = hashlib.sha256(b"").hexdigest().upper()
    assert _full_diff_sha256(binding_repo, "HEAD") == empty_diff
    handoff = _external_codex_handoff(
        tmp_path, route="critical_final_audit", binding_repo=binding_repo
    )
    _rebind_final_audit_handoff(handoff, binding_repo)
    assert handoff["diff_sha256"] == empty_diff
    result = _run_final_audit_pre_handoff(tmp_path, handoff, binding_repo)
    _assert_hook_result(result, handoff="PRE_HANDOFF_READY")
    assert "git diff failed" not in result["reason"]
    assert "dirty_tracked_or_index" not in result["reason"]


def test_final_audit_foreign_git_query_failure_denied(tmp_path: Path) -> None:
    binding_repo = _isolated_final_audit_binding_repo(tmp_path)
    handoff = _external_codex_handoff(
        tmp_path, route="critical_final_audit", binding_repo=binding_repo
    )
    shim_env = _git_shim_env(tmp_path, mode="foreign_cached")
    result = _run_final_audit_pre_handoff(
        tmp_path,
        handoff,
        binding_repo,
        env_overrides=shim_env,
    )
    assert result["handoff"] == "HANDOFF_INVALID"
    assert result["reason"] == "git diff --cached failed for foreign binding"


def test_final_audit_hook_denies_additional_untracked_allowlist_path(tmp_path: Path) -> None:
    binding_repo = _isolated_final_audit_binding_repo(tmp_path)
    handoff = _external_codex_handoff(
        tmp_path, route="critical_final_audit", binding_repo=binding_repo
    )
    _git(binding_repo, "rm", "--cached", ".cursor/hooks.json")
    result = _run_final_audit_pre_handoff(tmp_path, handoff, binding_repo)
    assert result["handoff"] == "HANDOFF_INVALID"
    assert result["reason"] == "foreign binding add denied: .cursor/hooks.json"


def test_final_audit_foreign_fourth_path_add_denied(tmp_path: Path) -> None:
    binding_repo = _isolated_final_audit_binding_repo(tmp_path)
    handoff = _external_codex_handoff(
        tmp_path, route="critical_final_audit", binding_repo=binding_repo
    )
    forged = binding_repo / ".cursor/forged-foreign.json"
    forged.write_text('{"fixture_only":true}\n', encoding="utf-8")
    result = _run_final_audit_pre_handoff(tmp_path, handoff, binding_repo)
    assert result["handoff"] == "HANDOFF_INVALID"
    assert "foreign binding add denied: .cursor/forged-foreign.json" in result["reason"]


def test_final_audit_handoff_declared_foreign_bindings_override_denied(tmp_path: Path) -> None:
    binding_repo = _isolated_final_audit_binding_repo(tmp_path)
    handoff = _external_codex_handoff(
        tmp_path, route="critical_final_audit", binding_repo=binding_repo
    )
    for field in (
        "declared_foreign_bindings",
        "declared_foreign_paths",
        "foreign_bindings",
        "foreign_override",
        "foreign_rules",
    ):
        payload = _final_audit_pre_payload(handoff)
        payload[field] = [{"path": "forged-foreign.txt"}]
        result = _run_external_codex_hook(
            tmp_path,
            payload,
            mode="EXTERNAL_CODEX_PRE_HANDOFF",
            binding_repo=binding_repo,
        )
        assert result["handoff"] == "HANDOFF_INVALID"
        assert result["reason"] == f"foreign binding override denied: {field}"


def test_final_audit_manifest_foreign_binding_add_denied(tmp_path: Path) -> None:
    binding_repo = _isolated_final_audit_binding_repo(tmp_path)
    handoff = _external_codex_handoff(
        tmp_path, route="critical_final_audit", binding_repo=binding_repo
    )
    manifest = _read_handoff_manifest(binding_repo, handoff)
    manifest["declared_foreign_bindings"] = list(manifest["declared_foreign_bindings"]) + [
        {
            "path": "forged-foreign.txt",
            "size": 0,
            "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "index_state": "untracked",
            "index_entry": None,
        }
    ]
    _write_handoff_manifest(binding_repo, handoff, manifest)
    result = _run_final_audit_pre_handoff(tmp_path, handoff, binding_repo)
    assert result["handoff"] == "HANDOFF_INVALID"
    assert "manifest foreign binding add denied: forged-foreign.txt" in result["reason"]


def test_final_audit_manifest_foreign_binding_drop_denied(tmp_path: Path) -> None:
    binding_repo = _isolated_final_audit_binding_repo(tmp_path)
    handoff = _external_codex_handoff(
        tmp_path, route="critical_final_audit", binding_repo=binding_repo
    )
    manifest = _read_handoff_manifest(binding_repo, handoff)
    manifest["declared_foreign_bindings"] = [
        item for item in manifest["declared_foreign_bindings"] if item["path"] != "agent"
    ]
    _write_handoff_manifest(binding_repo, handoff, manifest)
    result = _run_final_audit_pre_handoff(tmp_path, handoff, binding_repo)
    assert result["handoff"] == "HANDOFF_INVALID"
    assert "manifest foreign binding drop denied: agent" in result["reason"]


def test_final_audit_manifest_foreign_binding_replace_denied(tmp_path: Path) -> None:
    binding_repo = _isolated_final_audit_binding_repo(tmp_path)
    handoff = _external_codex_handoff(
        tmp_path, route="critical_final_audit", binding_repo=binding_repo
    )
    manifest = _read_handoff_manifest(binding_repo, handoff)
    for item in manifest["declared_foreign_bindings"]:
        if item["path"] == "agent":
            item["path"] = "forged-agent-alias"
    _write_handoff_manifest(binding_repo, handoff, manifest)
    result = _run_final_audit_pre_handoff(tmp_path, handoff, binding_repo)
    assert result["handoff"] == "HANDOFF_INVALID"
    assert "manifest foreign binding drop denied: agent" in result["reason"]


def test_final_audit_manifest_foreign_binding_missing_index_entry_denied(tmp_path: Path) -> None:
    binding_repo = _isolated_final_audit_binding_repo(tmp_path)
    handoff = _external_codex_handoff(
        tmp_path, route="critical_final_audit", binding_repo=binding_repo
    )
    manifest = _read_handoff_manifest(binding_repo, handoff)
    for item in manifest["declared_foreign_bindings"]:
        if item["path"] == "models":
            del item["index_entry"]
    _write_handoff_manifest(binding_repo, handoff, manifest)
    result = _run_final_audit_pre_handoff(tmp_path, handoff, binding_repo)
    assert result["handoff"] == "HANDOFF_INVALID"
    assert result["reason"] == "manifest foreign binding missing field index_entry: models"


def test_final_audit_manifest_foreign_binding_missing_size_zero_denied(tmp_path: Path) -> None:
    binding_repo = _isolated_final_audit_binding_repo(tmp_path)
    handoff = _external_codex_handoff(
        tmp_path, route="critical_final_audit", binding_repo=binding_repo
    )
    manifest = _read_handoff_manifest(binding_repo, handoff)
    for item in manifest["declared_foreign_bindings"]:
        if item["path"] == "agent":
            assert item["size"] == 0
            del item["size"]
    _write_handoff_manifest(binding_repo, handoff, manifest)
    result = _run_final_audit_pre_handoff(tmp_path, handoff, binding_repo)
    assert result["handoff"] == "HANDOFF_INVALID"
    assert result["reason"] == "manifest foreign binding missing field size: agent"


def test_final_audit_manifest_foreign_binding_null_size_zero_denied(tmp_path: Path) -> None:
    binding_repo = _isolated_final_audit_binding_repo(tmp_path)
    handoff = _external_codex_handoff(
        tmp_path, route="critical_final_audit", binding_repo=binding_repo
    )
    manifest = _read_handoff_manifest(binding_repo, handoff)
    for item in manifest["declared_foreign_bindings"]:
        if item["path"] == "models":
            assert item["size"] == 0
            item["size"] = None
    _write_handoff_manifest(binding_repo, handoff, manifest)
    result = _run_final_audit_pre_handoff(tmp_path, handoff, binding_repo)
    assert result["handoff"] == "HANDOFF_INVALID"
    assert result["reason"] == "manifest foreign binding missing field size: models"


def test_final_audit_manifest_foreign_binding_missing_index_state_denied(tmp_path: Path) -> None:
    binding_repo = _isolated_final_audit_binding_repo(tmp_path)
    handoff = _external_codex_handoff(
        tmp_path, route="critical_final_audit", binding_repo=binding_repo
    )
    manifest = _read_handoff_manifest(binding_repo, handoff)
    for item in manifest["declared_foreign_bindings"]:
        if item["path"] == "agent":
            del item["index_state"]
    _write_handoff_manifest(binding_repo, handoff, manifest)
    result = _run_final_audit_pre_handoff(tmp_path, handoff, binding_repo)
    assert result["handoff"] == "HANDOFF_INVALID"
    assert result["reason"] == "manifest foreign binding missing field index_state: agent"


def test_final_audit_manifest_foreign_binding_hash_mismatch_denied(tmp_path: Path) -> None:
    binding_repo = _isolated_final_audit_binding_repo(tmp_path)
    handoff = _external_codex_handoff(
        tmp_path, route="critical_final_audit", binding_repo=binding_repo
    )
    manifest = _read_handoff_manifest(binding_repo, handoff)
    for item in manifest["declared_foreign_bindings"]:
        if item["path"] == ".cursor/cli.json":
            item["sha256"] = "0" * 64
    _write_handoff_manifest(binding_repo, handoff, manifest)
    result = _run_final_audit_pre_handoff(tmp_path, handoff, binding_repo)
    assert result["handoff"] == "HANDOFF_INVALID"
    assert "manifest foreign binding hash mismatch: .cursor/cli.json" in result["reason"]


def test_final_audit_manifest_foreign_binding_index_entry_mismatch_denied(tmp_path: Path) -> None:
    binding_repo = _isolated_final_audit_binding_repo(tmp_path)
    handoff = _external_codex_handoff(
        tmp_path, route="critical_final_audit", binding_repo=binding_repo
    )
    manifest = _read_handoff_manifest(binding_repo, handoff)
    for item in manifest["declared_foreign_bindings"]:
        if item["path"] == "agent":
            item["index_entry"] = "100644 deadbeefdeadbeefdeadbeefdeadbeefdeadbeef 0\tagent"
    _write_handoff_manifest(binding_repo, handoff, manifest)
    result = _run_final_audit_pre_handoff(tmp_path, handoff, binding_repo)
    assert result["handoff"] == "HANDOFF_INVALID"
    assert "manifest foreign binding index_entry mismatch: agent" in result["reason"]


def test_final_audit_hook_denies_committed_out_of_scope_deletion(tmp_path: Path) -> None:
    binding_repo = _isolated_final_audit_binding_repo(
        tmp_path,
        prebase_out_of_scope=("rogue-deletion-target.txt",),
    )
    handoff = _external_codex_handoff(
        tmp_path, route="critical_final_audit", binding_repo=binding_repo
    )
    _git(binding_repo, "rm", "rogue-deletion-target.txt")
    _git(binding_repo, "commit", "-q", "-m", "delete rogue")
    result = _run_final_audit_pre_handoff(tmp_path, handoff, binding_repo)
    assert result["handoff"] == "HANDOFF_INVALID"
    assert result["reason"] == "out-of-scope repository mutation: rogue-deletion-target.txt"


def test_final_audit_hook_denies_rename_out_of_scope_old_path(tmp_path: Path) -> None:
    binding_repo = _isolated_final_audit_binding_repo(
        tmp_path,
        prebase_out_of_scope=("legacy-out-of-scope.txt",),
    )
    handoff = _external_codex_handoff(
        tmp_path, route="critical_final_audit", binding_repo=binding_repo
    )
    _git(binding_repo, "mv", "legacy-out-of-scope.txt", "legacy-renamed-out-of-scope.txt")
    _git(binding_repo, "commit", "-q", "-m", "rename legacy")
    result = _run_final_audit_pre_handoff(tmp_path, handoff, binding_repo)
    assert result["handoff"] == "HANDOFF_INVALID"
    assert "legacy-out-of-scope.txt" in result["reason"]
    assert result["reason"].startswith("out-of-scope repository mutation:")


def test_final_audit_foreign_staged_index_denied(tmp_path: Path) -> None:
    binding_repo = _isolated_final_audit_binding_repo(tmp_path)
    handoff = _external_codex_handoff(
        tmp_path, route="critical_final_audit", binding_repo=binding_repo
    )
    _git(binding_repo, "add", "agent")
    result = _run_final_audit_pre_handoff(tmp_path, handoff, binding_repo)
    assert result["handoff"] == "HANDOFF_INVALID"
    assert "foreign path staged denied: agent" in result["reason"]


def test_final_audit_manifest_records_exact_three_foreign_bindings(tmp_path: Path) -> None:
    binding_repo = _isolated_final_audit_binding_repo(tmp_path)
    handoff = _external_codex_handoff(
        tmp_path, route="critical_final_audit", binding_repo=binding_repo
    )
    manifest = _read_handoff_manifest(binding_repo, handoff)
    bindings = manifest["declared_foreign_bindings"]
    assert {item["path"] for item in bindings} == {".cursor/cli.json", "agent", "models"}
    assert len(bindings) == 3
    by_path = {item["path"]: item for item in bindings}
    cli = by_path[".cursor/cli.json"]
    agent = by_path["agent"]
    models = by_path["models"]
    for item in bindings:
        assert "path" in item
        assert "size" in item
        assert "sha256" in item
        assert "index_state" in item
        assert "index_entry" in item
        assert item["index_state"] == "untracked"
        assert item["index_entry"] is None
    assert agent["size"] == 0
    assert models["size"] == 0
    assert cli["size"] > 0
    result = _run_final_audit_pre_handoff(tmp_path, handoff, binding_repo)
    assert result["handoff"] == "PRE_HANDOFF_READY"
    assert result["reason"] == "workspace-derived pre-handoff binding valid"


def test_w3_final_review_route_bindings_self_contained() -> None:
    config = _config()
    bindings = config["external_codex_bound_review"]["review_route_bindings"]["AGENT-COST-01"]
    required = {
        "package_id",
        "checkpoint_id",
        "review_need",
        "base_ref",
        "allowlist_paths",
        "evidence_path_template",
        "verification_commands",
        "scope_mode",
    }
    for route_key, record in bindings.items():
        assert required.issubset(record.keys()), route_key
        assert record["allowlist_paths"], route_key
        assert record["verification_commands"], route_key
        assert record["evidence_path_template"]["root"], route_key
    recovery = bindings["recovery_diagnosis"]
    assert recovery["purpose"] == "diagnosis"
    assert len(recovery["allowlist_paths"]) == 15


def test_w3_final_partial_registry_record_denies_route_preflight(tmp_path: Path) -> None:
    repo = _isolated_recovery_diagnosis_repo(tmp_path)
    config = json.loads((repo / ".cursor/agent-system.json").read_text(encoding="utf-8"))
    partial = dict(config["external_codex_bound_review"]["review_route_bindings"]["AGENT-COST-01"][
        "recovery_diagnosis"
    ])
    del partial["package_id"]
    config["external_codex_bound_review"]["review_route_bindings"]["AGENT-COST-01"][
        "recovery_diagnosis"
    ] = partial
    (repo / ".cursor/agent-system.json").write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    result = _run_route_preflight(
        tmp_path,
        repo,
        package_id="AGENT-COST-01",
        checkpoint_id="W3-FINAL-REWORK-001",
    )
    assert result["permission"] == "deny"
    assert result["status"] == "BLOCKED_HUMAN"
    assert "partial registry record missing package_id" in result["reason"]


def test_w3_final_foreign_package_two_checkpoint_pre_bound_positive(
    tmp_path: Path,
) -> None:
    repo = _isolated_generic_registry_repo(
        tmp_path,
        extra_bindings=_foreign_package_two_checkpoint_bindings(base_ref="pending"),
    )
    for checkpoint_id in ("CP-ONE", "CP-TWO"):
        evidence_attempt = f"newpkg-{checkpoint_id.lower()}-{tmp_path.name}"
        handoff = _registry_route_handoff(
            tmp_path,
            binding_repo=repo,
            package_id="NEWPKG-99",
            checkpoint_id=checkpoint_id,
            evidence_attempt=evidence_attempt,
        )
        state_path = tmp_path / f"newpkg-{checkpoint_id}-state.json"
        result = _run_bound_after_anchored_pre(
            tmp_path,
            handoff,
            repo,
            state_path,
            checkpoint=checkpoint_id,
            work_package="NEWPKG-99",
        )
        assert result["handoff"] == "HANDOFF_READY", checkpoint_id
        assert result["status"] == "CONTINUE", checkpoint_id


def test_w3_final_synthetic_w2_w3_route_pre_bound_positive(tmp_path: Path) -> None:
    repo = _isolated_generic_registry_repo(
        tmp_path,
        extra_bindings=_synthetic_w2_w3_route_bindings(base_ref="pending"),
    )
    for checkpoint_id in ("W2", "W3"):
        evidence_attempt = f"synthetic-{checkpoint_id.lower()}-{tmp_path.name}"
        handoff = _registry_route_handoff(
            tmp_path,
            binding_repo=repo,
            package_id="AGENT-COST-01",
            checkpoint_id=checkpoint_id,
            evidence_attempt=evidence_attempt,
        )
        state_path = tmp_path / f"synthetic-{checkpoint_id}-state.json"
        result = _run_bound_after_anchored_pre(
            tmp_path,
            handoff,
            repo,
            state_path,
            checkpoint=checkpoint_id,
        )
        assert result["handoff"] == "HANDOFF_READY", checkpoint_id
        assert result["status"] == "CONTINUE", checkpoint_id


def test_w3_final_unregistered_checkpoint_denies_implementer_preflight(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "running-state.json"
    _write_running_state(state_path, checkpoint="CP-UNREGISTERED")
    denied = _run_implementer_pretool(tmp_path, state_path=state_path)
    assert denied["permission"] == "deny"
    assert "EXTERNAL_CODEX_ROUTE_PREFLIGHT" in denied["user_message"]
    assert "no exact registry record for checkpoint" in denied["user_message"]


def test_w3_final_host_alias_without_role_cannot_bypass_implementer_preflight(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "running-state.json"
    _write_running_state(state_path)
    bypass_attempt = _run_implementer_pretool(
        tmp_path,
        state_path=state_path,
        prompt="plain helper without role marker",
        subagent_type="implementer",
        child_agent_id="child-1",
        task_id="task-1",
    )
    assert bypass_attempt["permission"] == "deny"
    assert "EXTERNAL_CODEX_ROUTE_PREFLIGHT" in bypass_attempt["user_message"]
    assert "[ROLE:implementer]" in bypass_attempt["user_message"]

    state_path = tmp_path / "running-state-canonical.json"
    _write_running_state(state_path)
    allowed = _run_implementer_pretool(tmp_path, state_path=state_path)
    assert allowed["permission"] == "allow"
    assert "non_authoritative" not in allowed


def test_w3_final_pre_handoff_computes_binding_record_without_pass(tmp_path: Path) -> None:
    evidence_attempt = f"pre-binding-{tmp_path.name}"
    binding_repo = _isolated_codex_binding_repo(tmp_path)
    handoff = _external_codex_handoff(
        tmp_path,
        binding_repo=binding_repo,
        evidence_attempt=evidence_attempt,
    )
    pre_payload = dict(handoff)
    for field in ("verdict", "findings", "requested_model", "observed_model"):
        pre_payload.pop(field, None)
    state_path = tmp_path / "pre-state.json"
    _write_running_state(
        state_path,
        checkpoint="W1",
        rework_count=2,
        regular_rework_count=2,
        exceptional_count=6,
        final_rework_count=1,
    )
    result = _run_external_codex_hook(
        tmp_path,
        pre_payload,
        mode="EXTERNAL_CODEX_PRE_HANDOFF",
        binding_repo=binding_repo,
        state_path=state_path,
    )
    assert result["handoff"] == "PRE_HANDOFF_READY"
    assert result["status"] == "READY"
    assert "bindingRecord" in result
    assert result["bindingRecord"]["package_id"] == "AGENT-COST-01"
    assert result["bindingRecord"]["manifest_sha256"]
    assert "verdict" not in result


def test_w3_final_bound_requires_authoritative_binding_record(tmp_path: Path) -> None:
    evidence_attempt = f"bound-binding-{tmp_path.name}"
    rel_contract, rel_manifest = _canonical_evidence_paths(evidence_attempt)
    binding_repo = _isolated_codex_binding_repo(tmp_path)
    handoff = _external_codex_handoff(
        tmp_path, binding_repo=binding_repo, evidence_attempt=evidence_attempt
    )
    state_path = tmp_path / "bound-state.json"
    missing = _run_external_codex_hook(
        tmp_path, handoff, binding_repo=binding_repo, state_path=state_path
    )
    assert missing["handoff"] == "HANDOFF_INVALID"
    assert missing["reason"] == "missing authoritative bindingRecord"

    pre_payload = dict(handoff)
    for field in ("verdict", "findings", "requested_model", "observed_model"):
        pre_payload.pop(field, None)
    state_path = tmp_path / "bound-state.json"
    _ensure_running_state_for_handoff(state_path, handoff, checkpoint="W1")
    pre = _run_external_codex_hook(
        tmp_path,
        pre_payload,
        mode="EXTERNAL_CODEX_PRE_HANDOFF",
        binding_repo=binding_repo,
        state_path=state_path,
    )
    assert pre["handoff"] == "PRE_HANDOFF_READY", _hook_result_json(pre)
    assert pre["bindingRecord"]["manifest_sha256"]
    _write_state_binding_record(state_path, pre["bindingRecord"])
    ok = _run_external_codex_hook(
        tmp_path,
        handoff,
        binding_repo=binding_repo,
        state_path=state_path,
    )
    assert ok["handoff"] == "HANDOFF_READY"


def test_w3_final_bound_denies_missing_state_payload_authoritative_binding_record(
    tmp_path: Path,
) -> None:
    evidence_attempt = f"missing-state-payload-{tmp_path.name}"
    rel_contract, rel_manifest = _canonical_evidence_paths(evidence_attempt)
    binding_repo = _isolated_codex_binding_repo(tmp_path)
    handoff = _external_codex_handoff(
        tmp_path, binding_repo=binding_repo, evidence_attempt=evidence_attempt
    )
    pre_payload = dict(handoff)
    for field in ("verdict", "findings", "requested_model", "observed_model"):
        pre_payload.pop(field, None)
    pre = _run_external_codex_hook(
        tmp_path,
        pre_payload,
        mode="EXTERNAL_CODEX_PRE_HANDOFF",
        binding_repo=binding_repo,
    )
    assert pre["handoff"] == "PRE_HANDOFF_READY"
    missing_state = tmp_path / "missing-state-payload-state.json"
    result = _run_external_codex_hook(
        tmp_path,
        {**handoff, "authoritative_binding_record": pre["bindingRecord"]},
        binding_repo=binding_repo,
        state_path=missing_state,
    )
    assert result["handoff"] == "HANDOFF_INVALID"
    assert result["reason"] == "payload binding record override denied"


def test_w3_final_bound_denies_missing_state_self_consistent_rewritten_evidence(
    tmp_path: Path,
) -> None:
    evidence_attempt = f"missing-state-evidence-{tmp_path.name}"
    rel_contract, rel_manifest = _canonical_evidence_paths(evidence_attempt)
    binding_repo = _isolated_codex_binding_repo(tmp_path)
    handoff = _external_codex_handoff(
        tmp_path, binding_repo=binding_repo, evidence_attempt=evidence_attempt
    )
    missing_state = tmp_path / "missing-state-evidence-state.json"
    result = _run_external_codex_hook(
        tmp_path,
        handoff,
        binding_repo=binding_repo,
        state_path=missing_state,
    )
    assert result["handoff"] == "HANDOFF_INVALID"
    assert result["reason"] == "missing authoritative bindingRecord"


def test_w3_final_bound_denies_mutated_contract_after_pre(tmp_path: Path) -> None:
    evidence_attempt = f"mutate-contract-{tmp_path.name}"
    rel_contract, rel_manifest = _canonical_evidence_paths(evidence_attempt)
    binding_repo = _isolated_codex_binding_repo(tmp_path)
    handoff = _external_codex_handoff(
        tmp_path, binding_repo=binding_repo, evidence_attempt=evidence_attempt
    )
    pre_payload = dict(handoff)
    for field in ("verdict", "findings", "requested_model", "observed_model"):
        pre_payload.pop(field, None)
    state_path = tmp_path / "mutate-contract-state.json"
    _ensure_running_state_for_handoff(state_path, handoff, checkpoint="W1")
    pre = _run_external_codex_hook(
        tmp_path,
        pre_payload,
        mode="EXTERNAL_CODEX_PRE_HANDOFF",
        binding_repo=binding_repo,
        state_path=state_path,
    )
    assert pre["handoff"] == "PRE_HANDOFF_READY"
    anchored_record = dict(pre["bindingRecord"])
    _write_state_binding_record(state_path, anchored_record)
    contract_path = binding_repo / handoff["contract_path"]
    manifest_path = binding_repo / handoff["evidence_manifest_path"]
    contract_path.write_text(contract_path.read_text(encoding="utf-8") + "mutated\n", encoding="utf-8")
    config = json.loads((binding_repo / ".cursor/agent-system.json").read_text(encoding="utf-8"))
    route_record = config["external_codex_bound_review"]["review_route_bindings"]["AGENT-COST-01"][
        "checkpoint_escalation"
    ]
    allowlist = tuple(route_record["allowlist_paths"])
    base_ref = config["external_codex_bound_review"]["base_ref"]
    verify_commands = tuple(route_record["verification_commands"])
    _build_route_manifest(
        binding_repo,
        package_id="AGENT-COST-01",
        checkpoint_id="W1",
        contract_path=handoff["contract_path"],
        manifest_path=handoff["evidence_manifest_path"],
        allowlist=allowlist,
        base_ref=base_ref,
        verification_commands=verify_commands,
    )
    import hashlib

    persisted = json.loads(state_path.read_text(encoding="utf-8"))["external_review"]["bindingRecord"]
    handoff["contract_sha256"] = hashlib.sha256(contract_path.read_bytes()).hexdigest().upper()
    handoff["evidence_manifest_sha256"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest().upper()
    assert persisted["contract_sha256"] == anchored_record["contract_sha256"]
    assert persisted["manifest_sha256"] == anchored_record["manifest_sha256"]
    assert persisted["contract_sha256"] != handoff["contract_sha256"]
    assert persisted["manifest_sha256"] != handoff["evidence_manifest_sha256"]
    result = _run_external_codex_hook(
        tmp_path,
        handoff,
        binding_repo=binding_repo,
        state_path=state_path,
    )
    _assert_hook_result(
        result,
        handoff="HANDOFF_INVALID",
        reason="bindingRecord identity mismatch: contract_sha256",
    )


def test_w3_final_bound_denies_mutated_contract_hash_mismatch_before_seal(
    tmp_path: Path,
) -> None:
    evidence_attempt = f"mutate-contract-hash-{tmp_path.name}"
    binding_repo = _isolated_codex_binding_repo(tmp_path)
    handoff = _external_codex_handoff(
        tmp_path, binding_repo=binding_repo, evidence_attempt=evidence_attempt
    )
    pre_payload = dict(handoff)
    for field in ("verdict", "findings", "requested_model", "observed_model"):
        pre_payload.pop(field, None)
    state_path = tmp_path / "mutate-contract-hash-state.json"
    _ensure_running_state_for_handoff(state_path, handoff, checkpoint="W1")
    pre = _run_external_codex_hook(
        tmp_path,
        pre_payload,
        mode="EXTERNAL_CODEX_PRE_HANDOFF",
        binding_repo=binding_repo,
        state_path=state_path,
    )
    _write_state_binding_record(state_path, pre["bindingRecord"])
    contract_path = binding_repo / handoff["contract_path"]
    contract_path.write_text(contract_path.read_text(encoding="utf-8") + "mutated\n", encoding="utf-8")
    result = _run_external_codex_hook(
        tmp_path,
        handoff,
        binding_repo=binding_repo,
        state_path=state_path,
    )
    _assert_hook_result(
        result,
        handoff="HANDOFF_INVALID",
        reason="contract hash mismatch",
    )


def test_w3_final_bound_denies_self_consistent_manifest_rewrite_after_pre(
    tmp_path: Path,
) -> None:
    evidence_attempt = f"mutate-manifest-{tmp_path.name}"
    rel_contract, rel_manifest = _canonical_evidence_paths(evidence_attempt)
    binding_repo = _isolated_codex_binding_repo(tmp_path)
    handoff = _external_codex_handoff(
        tmp_path, binding_repo=binding_repo, evidence_attempt=evidence_attempt
    )
    pre_payload = dict(handoff)
    for field in ("verdict", "findings", "requested_model", "observed_model"):
        pre_payload.pop(field, None)
    state_path = tmp_path / "mutate-manifest-state.json"
    _ensure_running_state_for_handoff(state_path, handoff, checkpoint="W1")
    pre = _run_external_codex_hook(
        tmp_path,
        pre_payload,
        mode="EXTERNAL_CODEX_PRE_HANDOFF",
        binding_repo=binding_repo,
        state_path=state_path,
    )
    assert pre["handoff"] == "PRE_HANDOFF_READY"
    anchored_record = dict(pre["bindingRecord"])
    _write_state_binding_record(state_path, anchored_record)
    manifest_path = binding_repo / handoff["evidence_manifest_path"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["route"] = "forged-route"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    import hashlib

    persisted = json.loads(state_path.read_text(encoding="utf-8"))["external_review"]["bindingRecord"]
    handoff["evidence_manifest_sha256"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest().upper()
    assert persisted["manifest_sha256"] == anchored_record["manifest_sha256"]
    assert persisted["contract_sha256"] == anchored_record["contract_sha256"]
    assert persisted["manifest_sha256"] != handoff["evidence_manifest_sha256"]
    result = _run_external_codex_hook(
        tmp_path,
        handoff,
        binding_repo=binding_repo,
        state_path=state_path,
    )
    _assert_hook_result(
        result,
        handoff="HANDOFF_INVALID",
        reason="bindingRecord identity mismatch: manifest_sha256",
    )


def test_w3_final_bound_denies_payload_binding_record_override(tmp_path: Path) -> None:
    evidence_attempt = f"override-binding-{tmp_path.name}"
    rel_contract, rel_manifest = _canonical_evidence_paths(evidence_attempt)
    binding_repo = _isolated_codex_binding_repo(tmp_path)
    handoff = _external_codex_handoff(
        tmp_path, binding_repo=binding_repo, evidence_attempt=evidence_attempt
    )
    pre_payload = dict(handoff)
    for field in ("verdict", "findings", "requested_model", "observed_model"):
        pre_payload.pop(field, None)
    pre = _run_external_codex_hook(
        tmp_path,
        pre_payload,
        mode="EXTERNAL_CODEX_PRE_HANDOFF",
        binding_repo=binding_repo,
    )
    state_path = tmp_path / "override-binding-state.json"
    _write_state_binding_record(state_path, pre["bindingRecord"], checkpoint="W1")
    forged = dict(pre["bindingRecord"])
    forged["attempt"] = "forged-attempt"
    result = _run_external_codex_hook(
        tmp_path,
        {**handoff, "authoritative_binding_record": forged},
        binding_repo=binding_repo,
        state_path=state_path,
    )
    assert result["handoff"] == "HANDOFF_INVALID"
    assert result["reason"] == "payload binding record override denied"


def test_w3_final_recovery_diagnosis_denied_on_review_pre_path(tmp_path: Path) -> None:
    binding_repo = _isolated_recovery_diagnosis_repo(tmp_path)
    handoff = _recovery_diagnosis_handoff(tmp_path, binding_repo=binding_repo)
    injected = dict(handoff)
    injected["verdict"] = "PASS"
    result = _run_external_codex_hook(
        tmp_path,
        injected,
        mode="EXTERNAL_CODEX_PRE_HANDOFF",
        binding_repo=binding_repo,
    )
    assert result["handoff"] == "HANDOFF_INVALID"
    assert result["reason"] == "recovery diagnosis token denied on review path"


def test_w3_final_recovery_diagnosis_denied_on_review_bound_path(tmp_path: Path) -> None:
    binding_repo = _isolated_recovery_diagnosis_repo(tmp_path)
    handoff = _recovery_diagnosis_handoff(tmp_path, binding_repo=binding_repo)
    result = _run_external_codex_hook(
        tmp_path,
        {**handoff, "handoff": "HANDOFF_READY", "verdict": "PASS"},
        binding_repo=binding_repo,
    )
    assert result["handoff"] == "HANDOFF_INVALID"
    assert result["reason"] == "recovery diagnosis token denied on review path"


def test_w3_final_recovery_pre_handoff_preserves_real_fail_counts(tmp_path: Path) -> None:
    binding_repo = _isolated_recovery_diagnosis_repo(tmp_path)
    handoff = _recovery_diagnosis_handoff(tmp_path, binding_repo=binding_repo)
    state_path = tmp_path / "recovery-count-state.json"
    _write_running_state(
        state_path,
        regular_rework_count=2,
        exceptional_count=6,
        final_rework_count=1,
    )
    result = _run_external_codex_hook(
        tmp_path,
        handoff,
        mode="EXTERNAL_CODEX_RECOVERY_PRE_HANDOFF",
        binding_repo=binding_repo,
        state_path=state_path,
    )
    assert result["handoff"] == "RECOVERY_DIAGNOSIS_READY"
    assert result["status"] == "READY"
    assert result["bindingRecord"]["regular_rework_count"] == 2
    assert result["bindingRecord"]["exceptional_count"] == 6
    assert result["bindingRecord"]["final_rework_count"] == 1
    assert "verdict" not in result


def test_w3_final_recovery_forged_zero_counters_denied(tmp_path: Path) -> None:
    binding_repo = _isolated_recovery_diagnosis_repo(tmp_path)
    handoff = _recovery_diagnosis_handoff(
        tmp_path,
        binding_repo=binding_repo,
        regular_rework_count=0,
        exceptional_count=0,
        final_rework_count=0,
    )
    state_path = tmp_path / "recovery-forged-count-state.json"
    _write_running_state(
        state_path,
        regular_rework_count=2,
        exceptional_count=6,
        final_rework_count=1,
    )
    result = _run_external_codex_hook(
        tmp_path,
        handoff,
        mode="EXTERNAL_CODEX_RECOVERY_PRE_HANDOFF",
        binding_repo=binding_repo,
        state_path=state_path,
    )
    assert result["handoff"] == "HANDOFF_INVALID"
    assert result["status"] == "BLOCKED_HUMAN"
    assert result["reason"] == "persisted counter mismatch regular_rework_count"


def test_w3_final_recovery_receipt_is_blocked_human_without_continue(tmp_path: Path) -> None:
    binding_repo = _isolated_recovery_diagnosis_repo(tmp_path)
    handoff = _recovery_diagnosis_handoff(tmp_path, binding_repo=binding_repo)
    state_path = _recovery_running_state_path(tmp_path)
    pre = _run_external_codex_hook(
        tmp_path,
        handoff,
        mode="EXTERNAL_CODEX_RECOVERY_PRE_HANDOFF",
        binding_repo=binding_repo,
        state_path=state_path,
    )
    assert pre["handoff"] == "RECOVERY_DIAGNOSIS_READY", _hook_result_json(pre)
    assert pre["bindingRecord"]["manifest_sha256"]
    _write_state_binding_record(state_path, pre["bindingRecord"])
    receipt = _run_external_codex_hook(
        tmp_path,
        {**handoff, "result_kind": "RECOVERY_PROPOSAL"},
        mode="EXTERNAL_CODEX_RECOVERY_RECEIPT",
        binding_repo=binding_repo,
        state_path=state_path,
    )
    _assert_hook_result(receipt, handoff="RECOVERY_PROPOSAL_BOUND", status="BLOCKED_HUMAN")
    assert receipt["handoff"] != "HANDOFF_READY"
    assert receipt["status"] != "CONTINUE"


def test_w3_final_recovery_receipt_requires_anchored_binding_record(tmp_path: Path) -> None:
    binding_repo = _isolated_recovery_diagnosis_repo(tmp_path)
    handoff = _recovery_diagnosis_handoff(tmp_path, binding_repo=binding_repo)
    state_path = _recovery_running_state_path(tmp_path)
    missing = _run_external_codex_hook(
        tmp_path,
        {**handoff, "result_kind": "RECOVERY_PROPOSAL"},
        mode="EXTERNAL_CODEX_RECOVERY_RECEIPT",
        binding_repo=binding_repo,
        state_path=state_path,
    )
    _assert_hook_result(
        missing,
        handoff="HANDOFF_INVALID",
        reason="missing authoritative bindingRecord",
    )


def test_w3_final_manifest_validate_valid_false_denies(tmp_path: Path) -> None:
    import hashlib

    evidence_attempt = f"valid-false-{tmp_path.name}"
    rel_contract, rel_manifest = _canonical_evidence_paths(
        evidence_attempt, route="recovery_diagnosis"
    )
    repo = _isolated_recovery_diagnosis_repo(tmp_path)
    handoff = _recovery_diagnosis_handoff(
        tmp_path,
        binding_repo=repo,
        evidence_attempt=evidence_attempt,
    )
    manifest = repo / rel_manifest
    manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    manifest_payload["package_id"] = "FORGED-PACKAGE"
    manifest.write_text(json.dumps(manifest_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    handoff["evidence_manifest_sha256"] = hashlib.sha256(manifest.read_bytes()).hexdigest().upper()
    state_path = _recovery_running_state_path(tmp_path)
    result = _run_external_codex_hook(
        tmp_path,
        handoff,
        mode="EXTERNAL_CODEX_RECOVERY_PRE_HANDOFF",
        binding_repo=repo,
        state_path=state_path,
    )
    _assert_hook_result(
        result,
        handoff="HANDOFF_INVALID",
        reason_contains="manifest-validate valid=false",
    )


def test_w3_final_manifest_validate_exit_nonzero_denies(tmp_path: Path) -> None:
    evidence_attempt = f"valid-false-exit2-{tmp_path.name}"
    repo = _isolated_recovery_diagnosis_repo(tmp_path)
    _install_manifest_validate_double(repo, mode="exit2_empty_stdout")
    handoff = _recovery_diagnosis_handoff(
        tmp_path,
        binding_repo=repo,
        evidence_attempt=evidence_attempt,
    )
    state_path = _recovery_running_state_path(tmp_path)
    result = _run_external_codex_hook(
        tmp_path,
        handoff,
        mode="EXTERNAL_CODEX_RECOVERY_PRE_HANDOFF",
        binding_repo=repo,
        state_path=state_path,
    )
    _assert_hook_result(
        result,
        handoff="HANDOFF_INVALID",
        reason="manifest-validate exit 2",
    )


def test_w3_final_manifest_validate_valid_false_exit0_double_denies(tmp_path: Path) -> None:
    evidence_attempt = f"valid-false-exit0-{tmp_path.name}"
    repo = _isolated_recovery_diagnosis_repo(tmp_path)
    _install_manifest_validate_double(repo, mode="valid_false_exit0")
    handoff = _recovery_diagnosis_handoff(
        tmp_path,
        binding_repo=repo,
        evidence_attempt=evidence_attempt,
    )
    state_path = _recovery_running_state_path(tmp_path)
    result = _run_external_codex_hook(
        tmp_path,
        handoff,
        mode="EXTERNAL_CODEX_RECOVERY_PRE_HANDOFF",
        binding_repo=repo,
        state_path=state_path,
    )
    _assert_hook_result(
        result,
        handoff="HANDOFF_INVALID",
        reason_contains="manifest-validate valid=false",
    )


def test_w3_final_recovery_pre_denies_missing_persisted_context(tmp_path: Path) -> None:
    binding_repo = _isolated_recovery_diagnosis_repo(tmp_path)
    handoff = _recovery_diagnosis_handoff(tmp_path, binding_repo=binding_repo)
    result = _run_external_codex_hook(
        tmp_path,
        handoff,
        mode="EXTERNAL_CODEX_RECOVERY_PRE_HANDOFF",
        binding_repo=binding_repo,
        state_path=tmp_path / "missing-recovery-context-state.json",
    )
    _assert_hook_result(
        result,
        handoff="HANDOFF_INVALID",
        reason="missing persisted recovery context",
    )


def test_w3_final_recovery_receipt_denies_mismatched_persisted_branch(tmp_path: Path) -> None:
    binding_repo = _isolated_recovery_diagnosis_repo(tmp_path)
    handoff = _recovery_diagnosis_handoff(tmp_path, binding_repo=binding_repo)
    state_path = _recovery_running_state_path(tmp_path)
    pre = _run_external_codex_hook(
        tmp_path,
        handoff,
        mode="EXTERNAL_CODEX_RECOVERY_PRE_HANDOFF",
        binding_repo=binding_repo,
        state_path=state_path,
    )
    _write_state_binding_record(state_path, pre["bindingRecord"], work_branch="feature/wrong-branch")
    result = _run_external_codex_hook(
        tmp_path,
        {**handoff, "result_kind": "RECOVERY_PROPOSAL"},
        mode="EXTERNAL_CODEX_RECOVERY_RECEIPT",
        binding_repo=binding_repo,
        state_path=state_path,
    )
    _assert_hook_result(
        result,
        handoff="HANDOFF_INVALID",
        reason="persisted branch mismatch",
    )


def test_w3_final_manifest_metadata_denies_smaller_allowlist_scope(tmp_path: Path) -> None:
    import hashlib

    evidence_attempt = f"smaller-scope-{tmp_path.name}"
    rel_contract, rel_manifest = _canonical_evidence_paths(evidence_attempt)
    binding_repo = _isolated_codex_binding_repo(tmp_path)
    handoff = _external_codex_handoff(
        tmp_path, binding_repo=binding_repo, evidence_attempt=evidence_attempt
    )
    manifest_path = binding_repo / handoff["evidence_manifest_path"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["allowlist"] = manifest["allowlist"][:5]
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    handoff["evidence_manifest_sha256"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest().upper()
    pre_payload = dict(handoff)
    for field in ("verdict", "findings", "requested_model", "observed_model"):
        pre_payload.pop(field, None)
    result = _run_external_codex_hook(
        tmp_path,
        pre_payload,
        mode="EXTERNAL_CODEX_PRE_HANDOFF",
        binding_repo=binding_repo,
    )
    _assert_hook_result(
        result,
        handoff="HANDOFF_INVALID",
        reason_contains="manifest-validate valid=false",
    )


def test_w3_final_manifest_metadata_denies_foreign_package_id(tmp_path: Path) -> None:
    import hashlib

    evidence_attempt = f"foreign-package-{tmp_path.name}"
    binding_repo = _isolated_codex_binding_repo(tmp_path)
    handoff = _external_codex_handoff(
        tmp_path, binding_repo=binding_repo, evidence_attempt=evidence_attempt
    )
    manifest_path = binding_repo / handoff["evidence_manifest_path"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["package_id"] = "FORGED-PACKAGE"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    handoff["evidence_manifest_sha256"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest().upper()
    pre_payload = dict(handoff)
    for field in ("verdict", "findings", "requested_model", "observed_model"):
        pre_payload.pop(field, None)
    result = _run_external_codex_hook(
        tmp_path,
        pre_payload,
        mode="EXTERNAL_CODEX_PRE_HANDOFF",
        binding_repo=binding_repo,
    )
    _assert_hook_result(
        result,
        handoff="HANDOFF_INVALID",
        reason_contains="manifest-validate valid=false",
    )


def test_w3_final_manifest_metadata_denies_foreign_checkpoint_id(tmp_path: Path) -> None:
    import hashlib

    evidence_attempt = f"foreign-checkpoint-{tmp_path.name}"
    binding_repo = _isolated_codex_binding_repo(tmp_path)
    handoff = _external_codex_handoff(
        tmp_path, binding_repo=binding_repo, evidence_attempt=evidence_attempt
    )
    manifest_path = binding_repo / handoff["evidence_manifest_path"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["checkpoint_id"] = "FORGED-CHECKPOINT"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    handoff["evidence_manifest_sha256"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest().upper()
    pre_payload = dict(handoff)
    for field in ("verdict", "findings", "requested_model", "observed_model"):
        pre_payload.pop(field, None)
    result = _run_external_codex_hook(
        tmp_path,
        pre_payload,
        mode="EXTERNAL_CODEX_PRE_HANDOFF",
        binding_repo=binding_repo,
    )
    _assert_hook_result(
        result,
        handoff="HANDOFF_INVALID",
        reason_contains="manifest-validate valid=false",
    )


def test_w3_final_manifest_metadata_denies_foreign_base_ref(tmp_path: Path) -> None:
    import hashlib

    evidence_attempt = f"foreign-base-{tmp_path.name}"
    binding_repo = _isolated_codex_binding_repo(tmp_path)
    handoff = _external_codex_handoff(
        tmp_path, binding_repo=binding_repo, evidence_attempt=evidence_attempt
    )
    manifest_path = binding_repo / handoff["evidence_manifest_path"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["base_ref"] = "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    handoff["evidence_manifest_sha256"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest().upper()
    pre_payload = dict(handoff)
    for field in ("verdict", "findings", "requested_model", "observed_model"):
        pre_payload.pop(field, None)
    result = _run_external_codex_hook(
        tmp_path,
        pre_payload,
        mode="EXTERNAL_CODEX_PRE_HANDOFF",
        binding_repo=binding_repo,
    )
    _assert_hook_result(
        result,
        handoff="HANDOFF_INVALID",
        reason_contains="manifest-validate valid=false",
    )


def test_w3_final_bound_denies_reviewer_id_change_after_pre(tmp_path: Path) -> None:
    evidence_attempt = f"reviewer-change-{tmp_path.name}"
    binding_repo = _isolated_codex_binding_repo(tmp_path)
    handoff = _external_codex_handoff(
        tmp_path, binding_repo=binding_repo, evidence_attempt=evidence_attempt
    )
    pre_payload = dict(handoff)
    for field in ("verdict", "findings", "requested_model", "observed_model"):
        pre_payload.pop(field, None)
    state_path = tmp_path / "reviewer-change-state.json"
    _ensure_running_state_for_handoff(state_path, handoff, checkpoint="W1")
    pre = _run_external_codex_hook(
        tmp_path,
        pre_payload,
        mode="EXTERNAL_CODEX_PRE_HANDOFF",
        binding_repo=binding_repo,
        state_path=state_path,
    )
    _write_state_binding_record(state_path, pre["bindingRecord"])
    bound_handoff = dict(handoff)
    bound_handoff["reviewer_id"] = "reviewer-forged"
    result = _run_external_codex_hook(
        tmp_path,
        bound_handoff,
        binding_repo=binding_repo,
        state_path=state_path,
    )
    _assert_hook_result(
        result,
        handoff="HANDOFF_INVALID",
        reason="bindingRecord identity mismatch: reviewer_id",
    )


def test_w3_final_recovery_pre_denies_missing_failed_evidence(tmp_path: Path) -> None:
    binding_repo = _isolated_recovery_diagnosis_repo(tmp_path)
    handoff = _recovery_diagnosis_handoff(tmp_path, binding_repo=binding_repo)
    manifest_path = binding_repo / handoff["evidence_manifest_path"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["evidence_paths"] = {}
    manifest["evidence_sha256"] = {}
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    import hashlib

    handoff["evidence_manifest_sha256"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest().upper()
    state_path = _recovery_running_state_path(tmp_path)
    result = _run_external_codex_hook(
        tmp_path,
        handoff,
        mode="EXTERNAL_CODEX_RECOVERY_PRE_HANDOFF",
        binding_repo=binding_repo,
        state_path=state_path,
    )
    _assert_hook_result(
        result,
        handoff="HANDOFF_INVALID",
        reason="recovery failed evidence key missing: failed_review_junit",
    )


def test_w3_final_recovery_pre_denies_passing_junit_as_failed_evidence(tmp_path: Path) -> None:
    binding_repo = _isolated_recovery_diagnosis_repo(tmp_path)
    handoff = _recovery_diagnosis_handoff(tmp_path, binding_repo=binding_repo)
    failed_junit = binding_repo / Path(handoff["evidence_manifest_path"]).parent / "failed-junit.xml"
    _write_synthetic_passing_junit(failed_junit)
    manifest_path = binding_repo / handoff["evidence_manifest_path"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    import hashlib

    manifest["evidence_sha256"]["failed_review_junit"] = hashlib.sha256(
        failed_junit.read_bytes()
    ).hexdigest()
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    handoff["evidence_manifest_sha256"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest().upper()
    state_path = _recovery_running_state_path(tmp_path)
    result = _run_external_codex_hook(
        tmp_path,
        handoff,
        mode="EXTERNAL_CODEX_RECOVERY_PRE_HANDOFF",
        binding_repo=binding_repo,
        state_path=state_path,
    )
    _assert_hook_result(
        result,
        handoff="HANDOFF_INVALID",
        reason="recovery failed evidence is not a failed junit",
    )


def test_w3_final_pre_denies_binding_record_overwrite_on_review_pre(
    tmp_path: Path,
) -> None:
    evidence_attempt = f"pre-overwrite-{tmp_path.name}"
    binding_repo = _isolated_codex_binding_repo(tmp_path)
    handoff = _external_codex_handoff(
        tmp_path, binding_repo=binding_repo, evidence_attempt=evidence_attempt
    )
    pre_payload = dict(handoff)
    for field in ("verdict", "findings", "requested_model", "observed_model"):
        pre_payload.pop(field, None)
    state_path = tmp_path / "pre-overwrite-state.json"
    _ensure_running_state_for_handoff(state_path, handoff, checkpoint="W1")
    pre = _run_external_codex_hook(
        tmp_path,
        pre_payload,
        mode="EXTERNAL_CODEX_PRE_HANDOFF",
        binding_repo=binding_repo,
        state_path=state_path,
    )
    assert pre["handoff"] == "PRE_HANDOFF_READY"
    _write_state_binding_record(state_path, pre["bindingRecord"])
    forged_pre = dict(pre_payload)
    forged_pre["reviewer_id"] = "reviewer-forged"
    result = _run_external_codex_hook(
        tmp_path,
        forged_pre,
        mode="EXTERNAL_CODEX_PRE_HANDOFF",
        binding_repo=binding_repo,
        state_path=state_path,
    )
    _assert_hook_result(
        result,
        handoff="HANDOFF_INVALID",
        reason_contains="bindingRecord overwrite denied",
    )


def test_w3_final_bound_denies_persisted_checkpoint_context_mismatch(
    tmp_path: Path,
) -> None:
    evidence_attempt = f"bound-context-{tmp_path.name}"
    binding_repo = _isolated_codex_binding_repo(tmp_path)
    handoff = _external_codex_handoff(
        tmp_path, binding_repo=binding_repo, evidence_attempt=evidence_attempt
    )
    pre_payload = dict(handoff)
    for field in ("verdict", "findings", "requested_model", "observed_model"):
        pre_payload.pop(field, None)
    state_path = tmp_path / "bound-context-state.json"
    _ensure_running_state_for_handoff(state_path, handoff, checkpoint="W1")
    pre = _run_external_codex_hook(
        tmp_path,
        pre_payload,
        mode="EXTERNAL_CODEX_PRE_HANDOFF",
        binding_repo=binding_repo,
        state_path=state_path,
    )
    assert pre["handoff"] == "PRE_HANDOFF_READY"
    _write_state_binding_record(
        state_path,
        pre["bindingRecord"],
        checkpoint="W3-FINAL-REWORK-001",
    )
    result = _run_external_codex_hook(
        tmp_path,
        handoff,
        binding_repo=binding_repo,
        state_path=state_path,
    )
    _assert_hook_result(
        result,
        handoff="HANDOFF_INVALID",
        reason="persisted checkpoint_id mismatch",
    )


def test_w3_final_binding_record_pre_json_bound_roundtrip_positive(
    tmp_path: Path,
) -> None:
    evidence_attempt = f"roundtrip-{tmp_path.name}"
    binding_repo = _isolated_codex_binding_repo(tmp_path)
    handoff = _external_codex_handoff(
        tmp_path, binding_repo=binding_repo, evidence_attempt=evidence_attempt
    )
    pre_payload = dict(handoff)
    for field in ("verdict", "findings", "requested_model", "observed_model"):
        pre_payload.pop(field, None)
    state_path = tmp_path / "roundtrip-state.json"
    _ensure_running_state_for_handoff(state_path, handoff, checkpoint="W1")
    pre = _run_external_codex_hook(
        tmp_path,
        pre_payload,
        mode="EXTERNAL_CODEX_PRE_HANDOFF",
        binding_repo=binding_repo,
        state_path=state_path,
    )
    assert pre["handoff"] == "PRE_HANDOFF_READY"
    record_persisted = json.loads(json.dumps(pre["bindingRecord"]))
    _write_state_binding_record(state_path, record_persisted)
    bound = _run_external_codex_hook(
        tmp_path,
        handoff,
        binding_repo=binding_repo,
        state_path=state_path,
    )
    assert bound["handoff"] == "HANDOFF_READY"
    assert bound["status"] == "CONTINUE"


def test_w3_final_implementer_without_marker_unknown_checkpoint_denies(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "running-state.json"
    _write_running_state(state_path, checkpoint="CP-UNREGISTERED")
    denied = _run_implementer_pretool(
        tmp_path,
        state_path=state_path,
        prompt="plain helper without role marker",
        subagent_type="implementer",
        child_agent_id="child-1",
        task_id="task-1",
    )
    assert denied["permission"] == "deny"
    assert "EXTERNAL_CODEX_ROUTE_PREFLIGHT" in denied["user_message"]
    assert "no exact registry record for checkpoint" in denied["user_message"]


def test_w3_final_nonimplementer_helper_without_marker_stays_non_authoritative(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "running-state.json"
    _write_running_state(state_path)
    allowed = _run_implementer_pretool(
        tmp_path,
        state_path=state_path,
        prompt="plain helper without role marker",
        subagent_type="generalPurpose",
        child_agent_id="child-1",
        task_id="task-1",
    )
    assert allowed["permission"] == "allow"
    assert allowed["non_authoritative"] is True
    assert allowed["gate_budget_authority"] is False


def test_w3_final_pre_denies_persisted_checkpoint_context_mismatch(
    tmp_path: Path,
) -> None:
    evidence_attempt = f"pre-context-{tmp_path.name}"
    binding_repo = _isolated_codex_binding_repo(tmp_path)
    handoff = _external_codex_handoff(
        tmp_path, binding_repo=binding_repo, evidence_attempt=evidence_attempt
    )
    pre_payload = dict(handoff)
    for field in ("verdict", "findings", "requested_model", "observed_model"):
        pre_payload.pop(field, None)
    state_path = tmp_path / "pre-context-state.json"
    _write_running_state(
        state_path,
        checkpoint="W3-FINAL-REWORK-001",
        regular_rework_count=2,
        exceptional_count=6,
        final_rework_count=1,
    )
    result = _run_external_codex_hook(
        tmp_path,
        pre_payload,
        mode="EXTERNAL_CODEX_PRE_HANDOFF",
        binding_repo=binding_repo,
        state_path=state_path,
    )
    _assert_hook_result(
        result,
        handoff="HANDOFF_INVALID",
        reason="persisted checkpoint_id mismatch",
    )


def test_w3_final_implementer_subagent_type_without_state_denies(
    tmp_path: Path,
) -> None:
    denied = _run_implementer_pretool(
        tmp_path,
        state_path=tmp_path / "missing-state.json",
        prompt="plain helper without role marker",
        subagent_type="implementer",
        child_agent_id="child-1",
        task_id="task-1",
    )
    assert denied["permission"] == "deny"
    assert "EXTERNAL_CODEX_ROUTE_PREFLIGHT" in denied["user_message"]
    assert "missing RUNNING workflow state" in denied["user_message"]


def test_w3_final_recovery_pre_denies_mismatched_workspace_claims(
    tmp_path: Path,
) -> None:
    cases = (
        ("branch", "feature/wrong-branch", "wrong branch", {"work_branch": "feature/wrong-branch"}),
        ("target_root", "C:/foreign/workspace/root", "foreign target", {}),
        (
            "reviewed_head",
            "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
            "stale head",
            {},
        ),
        (
            "base_head",
            "cafebabecafebabecafebabecafebabecafebabe",
            "wrong base",
            {},
        ),
        (
            "diff_sha256",
            "DEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEF",
            "stale diff",
            {},
        ),
        (
            "pre_fingerprint",
            "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            "pre fingerprint not workspace-derived",
            {},
        ),
        (
            "post_fingerprint",
            "fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210",
            "post fingerprint not workspace-derived",
            {},
        ),
    )
    for field, forged_value, reason, state_updates in cases:
        case_root = tmp_path / f"case-{field}"
        case_root.mkdir(parents=True, exist_ok=True)
        binding_repo = _isolated_recovery_diagnosis_repo(case_root)
        handoff = _recovery_diagnosis_handoff(case_root, binding_repo=binding_repo)
        handoff[field] = forged_value
        state_path = _recovery_running_state_path(case_root, **state_updates)
        result = _run_external_codex_hook(
            case_root,
            handoff,
            mode="EXTERNAL_CODEX_RECOVERY_PRE_HANDOFF",
            binding_repo=binding_repo,
            state_path=state_path,
        )
        _assert_hook_result(
            result,
            handoff="HANDOFF_INVALID",
            reason=reason,
        )


def test_w3_final_recovery_pre_denies_missing_persisted_counters(tmp_path: Path) -> None:
    binding_repo = _isolated_recovery_diagnosis_repo(tmp_path)
    handoff = _recovery_diagnosis_handoff(tmp_path, binding_repo=binding_repo)
    state_path = tmp_path / "missing-counter-state.json"
    state = _running_workflow_state(
        regular_rework_count=2,
        exceptional_count=6,
    )
    del state["final_rework_count"]
    state_path.write_text(json.dumps(state), encoding="utf-8")
    result = _run_external_codex_hook(
        tmp_path,
        handoff,
        mode="EXTERNAL_CODEX_RECOVERY_PRE_HANDOFF",
        binding_repo=binding_repo,
        state_path=state_path,
    )
    _assert_hook_result(
        result,
        handoff="HANDOFF_INVALID",
        reason="missing persisted recovery counter final_rework_count",
    )


W3_FINAL_REWORK_001_FIX08_NODES: tuple[str, ...] = (
    "test_session_start_injects_only_active_compact_context",
    "test_w3_final_session_start_recovery_receipt_blocks_resume_instructions",
    "test_w3_final_session_start_recovery_diagnosis_binding_record_blocks_resume_before_diagnosis",
    "test_w3_final_session_start_recovery_diagnosis_binding_record_blocks_resume_after_diagnosis_result",
    "test_w3_final_session_start_normal_binding_record_still_resumes",
)


def test_w3_final_session_start_recovery_diagnosis_binding_record_blocks_resume_before_diagnosis(
    tmp_path: Path,
) -> None:
    binding_repo = _isolated_recovery_diagnosis_repo(tmp_path)
    handoff = _recovery_diagnosis_handoff(tmp_path, binding_repo=binding_repo)
    state_path = _recovery_running_state_path(tmp_path)
    pre = _run_external_codex_hook(
        tmp_path,
        handoff,
        mode="EXTERNAL_CODEX_RECOVERY_PRE_HANDOFF",
        binding_repo=binding_repo,
        state_path=state_path,
    )
    assert pre["handoff"] == "RECOVERY_DIAGNOSIS_READY"
    serialized = _coordinator_serialized_recovery_diagnosis_state(
        pre["bindingRecord"],
        next_action="Resume implement W3-FINAL-REWORK-001",
        recovery_proposal_bound=False,
    )
    state_path.write_text(json.dumps(serialized), encoding="utf-8")
    result = _run_hook(
        "session-start.ps1",
        {"session_id": "test", "composer_mode": "agent"},
        state_path=state_path,
    )
    context = result["additional_context"]
    assert "RECOVERY_DIAGNOSIS_READY" in context
    assert "RECOVERY_PROPOSAL_BOUND" not in context
    assert "Do not issue Resume, Implement, or Commit instructions" in context
    assert "BLOCKED_HUMAN" in context
    assert "Resume the persisted workflow" not in context
    assert "Next Action:" not in context


def test_w3_final_session_start_recovery_diagnosis_binding_record_blocks_resume_after_diagnosis_result(
    tmp_path: Path,
) -> None:
    binding_repo = _isolated_recovery_diagnosis_repo(tmp_path)
    handoff = _recovery_diagnosis_handoff(tmp_path, binding_repo=binding_repo)
    state_path = _recovery_running_state_path(tmp_path)
    pre = _run_external_codex_hook(
        tmp_path,
        handoff,
        mode="EXTERNAL_CODEX_RECOVERY_PRE_HANDOFF",
        binding_repo=binding_repo,
        state_path=state_path,
    )
    assert pre["handoff"] == "RECOVERY_DIAGNOSIS_READY"
    _write_state_binding_record(state_path, pre["bindingRecord"])
    receipt = _run_external_codex_hook(
        tmp_path,
        {**handoff, "result_kind": "RECOVERY_PROPOSAL"},
        mode="EXTERNAL_CODEX_RECOVERY_RECEIPT",
        binding_repo=binding_repo,
        state_path=state_path,
    )
    _assert_hook_result(receipt, handoff="RECOVERY_PROPOSAL_BOUND", status="BLOCKED_HUMAN")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["external_review"]["bindingRecord"]["review_need"] == "RECOVERY_DIAGNOSIS"
    state["next_action"] = "Continue: commit recovery proposal and resume workflow"
    state["external_review"]["recovery_proposal_bound"] = False
    state_path.write_text(json.dumps(state), encoding="utf-8")
    result = _run_hook(
        "session-start.ps1",
        {"session_id": "test", "composer_mode": "agent"},
        state_path=state_path,
    )
    context = result["additional_context"]
    assert "RECOVERY_DIAGNOSIS_READY" in context
    assert "RECOVERY_PROPOSAL_BOUND" not in context
    assert "Continue: commit recovery proposal and resume workflow" not in context
    assert "Resume the persisted workflow" not in context
    assert "Next Action:" not in context


def test_w3_final_session_start_normal_binding_record_still_resumes(tmp_path: Path) -> None:
    binding_repo = _isolated_codex_binding_repo(tmp_path)
    handoff = _external_codex_handoff(tmp_path, binding_repo=binding_repo)
    state_path = tmp_path / "normal-binding-session-state.json"
    pre = _anchor_pre_binding_record(tmp_path, handoff, binding_repo, state_path)
    assert pre["bindingRecord"]["review_need"] == "CHECKPOINT_ESCALATION"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["external_review"]["recovery_proposal_bound"] = False
    state_path.write_text(json.dumps(state), encoding="utf-8")
    result = _run_hook(
        "session-start.ps1",
        {"session_id": "test", "composer_mode": "agent"},
        state_path=state_path,
    )
    context = result["additional_context"]
    assert "RECOVERY_DIAGNOSIS_READY" not in context
    assert "RECOVERY_PROPOSAL_BOUND" not in context
    assert "Resume the persisted workflow" in context
    assert "Next Action:" in context


def test_w3_final_session_start_recovery_receipt_blocks_resume_instructions(tmp_path: Path) -> None:
    state_path = tmp_path / "recovery-session-state.json"
    _write_running_state(
        state_path,
        external_review={
            "status": "NOT_REQUESTED",
            "round": 0,
            "reviewed_head": None,
            "blocking_findings": [],
            "last_checked_at": None,
            "bindingRecord": None,
            "recovery_proposal_bound": True,
        },
    )
    result = _run_hook(
        "session-start.ps1",
        {"session_id": "test", "composer_mode": "agent"},
        state_path=state_path,
    )
    context = result["additional_context"]
    assert "RECOVERY_PROPOSAL_BOUND" in context
    assert "Do not issue Resume, Implement, or Commit instructions" in context
    assert "BLOCKED_HUMAN" in context
    assert "Resume the persisted workflow" not in context
