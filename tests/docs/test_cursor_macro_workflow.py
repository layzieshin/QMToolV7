from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
AGENT = ROOT / ".cursor" / "agents" / "checkpoint-reviewer.md"
SKILL_ROOT = ROOT / ".cursor" / "skills" / "execute-gated-macro"
SKILL = SKILL_ROOT / "SKILL.md"
PROTOCOL = SKILL_ROOT / "references" / "checkpoint-protocol.md"
SNAPSHOT = SKILL_ROOT / "scripts" / "checkpoint_snapshot.py"
AP029_PLAN = ROOT / "docs" / "AP-029_WEB_POSTGRES_TRANSITION_PLAN.md"
ROADMAP = ROOT / "docs" / "MASTER_ORCHESTRATION_ROADMAP.md"
WORKFLOW = ROOT / ".cursor" / "rules" / "00-agent-workflow.mdc"
GIT_WORKFLOW = ROOT / ".cursor" / "rules" / "01-git-workflow.mdc"
AGENTS = ROOT / "AGENTS.md"

REQUIRED_FRONTMATTER_MODEL = "gpt-5.6-terra"
REQUIRED_TASK_MODEL = "gpt-5.6-terra"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def classify_reviewer_evidence_profile(facts: dict[str, Any]) -> dict[str, str]:
    """Pure classifier mirroring D15. Used by contract tests; not a product API."""

    configured = str(facts.get("configured_model") or "")
    requested = str(facts.get("requested_model") or "")
    observed_model = facts.get("observed_runtime_model")
    observed_reasoning = facts.get("observed_reasoning")
    agent_id = str(facts.get("agent_id") or "").strip()
    separate_context = bool(facts.get("separate_context"))
    uses_verify = bool(facts.get("uses_verify_reports_and_plan"))
    readonly = bool(facts.get("readonly"))
    contradictory = bool(facts.get("contradictory_metadata"))
    fallback_msg = bool(facts.get("fallback_or_substitution_message"))
    instantiated = bool(facts.get("agent_instantiated"))

    def blocked(reason: str) -> dict[str, str]:
        return {
            "evidence_profile": "UNVERIFIED",
            "gate_e": "BLOCKED",
            "reason": reason,
            "observed_runtime_model": (
                "UNAVAILABLE"
                if observed_model in (None, "", "UNAVAILABLE")
                else str(observed_model)
            ),
            "observed_reasoning": (
                "UNAVAILABLE"
                if observed_reasoning in (None, "", "UNAVAILABLE")
                else str(observed_reasoning)
            ),
        }

    if not instantiated or not agent_id or not separate_context:
        return blocked("missing agent instantiation, agent_id, or separate context")
    if configured != REQUIRED_FRONTMATTER_MODEL:
        return blocked("configured_model mismatch")
    if requested != REQUIRED_TASK_MODEL:
        return blocked("requested_model mismatch")
    if not uses_verify or not readonly:
        return blocked("missing verify-reports-and-plan or readonly")

    # Mutation proof is fail-closed (D15): key must be an explicit bool; fingerprints required.
    if "mutation_detected" not in facts or not isinstance(facts.get("mutation_detected"), bool):
        return blocked("missing mutation proof")
    pre_raw = facts.get("pre_fingerprint")
    post_raw = facts.get("post_fingerprint")
    if pre_raw in (None, "") or post_raw in (None, ""):
        return blocked("missing mutation proof")
    pre_fp = str(pre_raw)
    post_fp = str(post_raw)
    if facts["mutation_detected"] is True:
        return blocked("reviewer mutation detected")
    if post_fp != "pending_parent_capture" and pre_fp != post_fp:
        return blocked("reviewer mutation detected")

    if contradictory or fallback_msg:
        return blocked("contradictory or fallback/substitution metadata")
    model_observed = observed_model not in (None, "", "UNAVAILABLE")
    reasoning_observed = observed_reasoning not in (None, "", "UNAVAILABLE")
    allowed_models = {REQUIRED_FRONTMATTER_MODEL, REQUIRED_TASK_MODEL}
    allowed_reasoning = {"medium", "standard", "default", "terra"}

    # Exactly one observed field is fail-closed partial metadata (D15 / GOV01-R5).
    if model_observed != reasoning_observed:
        return blocked("partial runtime metadata")

    if model_observed and reasoning_observed:
        model_ok = str(observed_model) in allowed_models
        reasoning_ok = str(observed_reasoning).lower() in allowed_reasoning
        if not model_ok or not reasoning_ok:
            return blocked("observed runtime metadata contradicts required configuration")
        return {
            "evidence_profile": "RUNTIME_ATTESTED",
            "gate_e": "CONTINUE",
            "reason": "observed runtime metadata matches required configuration",
            "observed_runtime_model": str(observed_model),
            "observed_reasoning": str(observed_reasoning),
        }

    # Both unavailable: CONTROL_PLANE_PINNED may continue when the pin is complete.
    return {
        "evidence_profile": "CONTROL_PLANE_PINNED",
        "gate_e": "CONTINUE",
        "reason": "local control-plane pin fully proven; runtime metadata UNAVAILABLE",
        "observed_runtime_model": "UNAVAILABLE",
        "observed_reasoning": "UNAVAILABLE",
    }


def test_qmtool_reviewer_and_macro_skill_contracts() -> None:
    agent = _read(AGENT)
    skill = _read(SKILL)
    protocol = _read(PROTOCOL)
    workflow = _read(WORKFLOW)

    assert f"model: {REQUIRED_FRONTMATTER_MODEL}" in agent
    assert "readonly: true" in agent
    assert "[ROLE:checkpoint-reviewer]" in agent
    assert "$verify-reports-and-plan" in agent
    assert "overall verdict exactly" in agent
    assert "`PASS`" in agent
    assert "`FAIL`" in agent
    assert "MINIMAL_REWORK_ORDER" in agent
    assert "Never edit source" in agent
    assert "evidence_profile" in agent
    assert "observed_runtime_model" in agent
    assert "CONTROL_PLANE_PINNED" in agent
    assert "PARENT_CAPTURE_REQUIRED" in agent

    assert "at most two remediation rounds" in skill
    normalized_skill = " ".join(skill.split())
    assert "separate context" in normalized_skill
    assert "post-review" in skill
    assert "CONTROL_PLANE_PINNED" in skill
    assert REQUIRED_TASK_MODEL in skill
    assert "do not start another gate" in protocol
    assert "already-running gates" in protocol
    assert "`NOT RUN` only" in protocol
    assert "evidence_profile" in protocol
    assert REQUIRED_TASK_MODEL in protocol

    for contract in (agent, skill, protocol, workflow):
        normalized = " ".join(contract.split()).lower()
        assert "never ask the user to copy, paste, forward or relay" in normalized
    normalized_workflow = " ".join(workflow.split()).lower()
    assert "explicitly authorized ap-029 macro" in normalized_workflow
    assert "execute-gated-macro" in normalized_workflow
    assert "do not invoke" in normalized_workflow and "checkpoint-reviewer" in normalized_workflow
    assert "complete work report" in workflow
    assert "fresh reviewer Task" in workflow
    assert "one consolidated report" in protocol
    assert "does not need shell access" in protocol


def test_local_commit_is_included_in_implementation_authorization() -> None:
    git_workflow = _read(GIT_WORKFLOW)
    agents = _read(AGENTS)
    skill = _read(SKILL)
    protocol = _read(PROTOCOL)

    normalized_git = " ".join(git_workflow.split())
    assert "includes authorization for the corresponding local commit" in normalized_git
    assert "does not apply to analysis, review, diagnosis, status" in normalized_git
    assert "Do not ask for a second commit confirmation" in normalized_git
    assert "Never commit directly on `main`" in git_workflow
    assert "Do not use `git add .`" in git_workflow

    assert "local feature-branch commit" in agents
    assert "unless the user opts out" in agents
    assert "unless the user explicitly opts out" in skill
    assert "unless the user explicitly opts out" in protocol
    for contract in (git_workflow, agents, skill, protocol):
        assert "Push" in contract or "push" in contract
        assert "separate" in contract.lower()


def test_reviewer_evidence_profile_runtime_attested() -> None:
    result = classify_reviewer_evidence_profile(
        {
            "agent_instantiated": True,
            "agent_id": "abc-123",
            "separate_context": True,
            "configured_model": REQUIRED_FRONTMATTER_MODEL,
            "requested_model": REQUIRED_TASK_MODEL,
            "observed_runtime_model": "gpt-5.6-terra",
            "observed_reasoning": "standard",
            "uses_verify_reports_and_plan": True,
            "readonly": True,
            "pre_fingerprint": "aa",
            "post_fingerprint": "aa",
            "mutation_detected": False,
            "contradictory_metadata": False,
            "fallback_or_substitution_message": False,
        }
    )
    assert result["evidence_profile"] == "RUNTIME_ATTESTED"
    assert result["gate_e"] == "CONTINUE"
    assert result["observed_runtime_model"] == "gpt-5.6-terra"


def test_reviewer_evidence_profile_control_plane_pinned() -> None:
    result = classify_reviewer_evidence_profile(
        {
            "agent_instantiated": True,
            "agent_id": "abc-123",
            "separate_context": True,
            "configured_model": REQUIRED_FRONTMATTER_MODEL,
            "requested_model": REQUIRED_TASK_MODEL,
            "observed_runtime_model": "UNAVAILABLE",
            "observed_reasoning": "UNAVAILABLE",
            "uses_verify_reports_and_plan": True,
            "readonly": True,
            "pre_fingerprint": "aa",
            "post_fingerprint": "aa",
            "mutation_detected": False,
            "contradictory_metadata": False,
            "fallback_or_substitution_message": False,
        }
    )
    assert result["evidence_profile"] == "CONTROL_PLANE_PINNED"
    assert result["gate_e"] == "CONTINUE"
    assert result["observed_runtime_model"] == "UNAVAILABLE"
    assert result["observed_reasoning"] == "UNAVAILABLE"
    assert "runtime-attested" not in result["reason"].lower()


def test_reviewer_evidence_profile_blocks_on_missing_mutation_proof() -> None:
    """Absent mutation_detected or fingerprints must BLOCK (fail-closed D15)."""
    base = {
        "agent_instantiated": True,
        "agent_id": "abc-123",
        "separate_context": True,
        "configured_model": REQUIRED_FRONTMATTER_MODEL,
        "requested_model": REQUIRED_TASK_MODEL,
        "observed_runtime_model": "UNAVAILABLE",
        "observed_reasoning": "UNAVAILABLE",
        "uses_verify_reports_and_plan": True,
        "readonly": True,
        "contradictory_metadata": False,
        "fallback_or_substitution_message": False,
    }
    missing_key = classify_reviewer_evidence_profile(
        {**base, "pre_fingerprint": "aa", "post_fingerprint": "aa"}
    )
    assert missing_key["gate_e"] == "BLOCKED"
    assert "missing mutation proof" in missing_key["reason"]

    empty_fp = classify_reviewer_evidence_profile(
        {
            **base,
            "pre_fingerprint": "",
            "post_fingerprint": "aa",
            "mutation_detected": False,
        }
    )
    assert empty_fp["gate_e"] == "BLOCKED"
    assert "missing mutation proof" in empty_fp["reason"]

    pending_ok = classify_reviewer_evidence_profile(
        {
            **base,
            "pre_fingerprint": "aa",
            "post_fingerprint": "pending_parent_capture",
            "mutation_detected": False,
        }
    )
    assert pending_ok["gate_e"] == "CONTINUE"
    assert pending_ok["evidence_profile"] == "CONTROL_PLANE_PINNED"


def test_reviewer_evidence_profile_blocks_on_observed_model_mismatch() -> None:
    result = classify_reviewer_evidence_profile(
        {
            "agent_instantiated": True,
            "agent_id": "abc-123",
            "separate_context": True,
            "configured_model": REQUIRED_FRONTMATTER_MODEL,
            "requested_model": REQUIRED_TASK_MODEL,
            "observed_runtime_model": "some-other-model",
            "observed_reasoning": "xhigh",
            "uses_verify_reports_and_plan": True,
            "readonly": True,
            "pre_fingerprint": "aa",
            "post_fingerprint": "aa",
            "mutation_detected": False,
            "contradictory_metadata": False,
            "fallback_or_substitution_message": False,
        }
    )
    assert result["evidence_profile"] == "UNVERIFIED"
    assert result["gate_e"] == "BLOCKED"
    assert "contradicts" in result["reason"]


def test_reviewer_evidence_profile_blocks_on_observed_reasoning_mismatch() -> None:
    result = classify_reviewer_evidence_profile(
        {
            "agent_instantiated": True,
            "agent_id": "abc-123",
            "separate_context": True,
            "configured_model": REQUIRED_FRONTMATTER_MODEL,
            "requested_model": REQUIRED_TASK_MODEL,
            "observed_runtime_model": "gpt-5.6-terra",
            "observed_reasoning": "low",
            "uses_verify_reports_and_plan": True,
            "readonly": True,
            "pre_fingerprint": "aa",
            "post_fingerprint": "aa",
            "mutation_detected": False,
            "contradictory_metadata": False,
            "fallback_or_substitution_message": False,
        }
    )
    assert result["gate_e"] == "BLOCKED"


def test_reviewer_evidence_profile_blocks_on_missing_agent_id() -> None:
    result = classify_reviewer_evidence_profile(
        {
            "agent_instantiated": True,
            "agent_id": "",
            "separate_context": True,
            "configured_model": REQUIRED_FRONTMATTER_MODEL,
            "requested_model": REQUIRED_TASK_MODEL,
            "observed_runtime_model": "UNAVAILABLE",
            "observed_reasoning": "UNAVAILABLE",
            "uses_verify_reports_and_plan": True,
            "readonly": True,
            "pre_fingerprint": "aa",
            "post_fingerprint": "aa",
            "mutation_detected": False,
            "contradictory_metadata": False,
            "fallback_or_substitution_message": False,
        }
    )
    assert result["gate_e"] == "BLOCKED"
    assert "agent_id" in result["reason"]


def test_reviewer_evidence_profile_blocks_on_missing_separate_context() -> None:
    result = classify_reviewer_evidence_profile(
        {
            "agent_instantiated": True,
            "agent_id": "abc-123",
            "separate_context": False,
            "configured_model": REQUIRED_FRONTMATTER_MODEL,
            "requested_model": REQUIRED_TASK_MODEL,
            "observed_runtime_model": "UNAVAILABLE",
            "observed_reasoning": "UNAVAILABLE",
            "uses_verify_reports_and_plan": True,
            "readonly": True,
            "pre_fingerprint": "aa",
            "post_fingerprint": "aa",
            "mutation_detected": False,
            "contradictory_metadata": False,
            "fallback_or_substitution_message": False,
        }
    )
    assert result["gate_e"] == "BLOCKED"
    assert "separate context" in result["reason"]


def test_reviewer_evidence_profile_blocks_on_task_model_mismatch() -> None:
    result = classify_reviewer_evidence_profile(
        {
            "agent_instantiated": True,
            "agent_id": "abc-123",
            "separate_context": True,
            "configured_model": REQUIRED_FRONTMATTER_MODEL,
            "requested_model": "inherit",
            "observed_runtime_model": "UNAVAILABLE",
            "observed_reasoning": "UNAVAILABLE",
            "uses_verify_reports_and_plan": True,
            "readonly": True,
            "pre_fingerprint": "aa",
            "post_fingerprint": "aa",
            "mutation_detected": False,
            "contradictory_metadata": False,
            "fallback_or_substitution_message": False,
        }
    )
    assert result["gate_e"] == "BLOCKED"
    assert "requested_model" in result["reason"]


def test_reviewer_evidence_profile_blocks_on_mutation() -> None:
    result = classify_reviewer_evidence_profile(
        {
            "agent_instantiated": True,
            "agent_id": "abc-123",
            "separate_context": True,
            "configured_model": REQUIRED_FRONTMATTER_MODEL,
            "requested_model": REQUIRED_TASK_MODEL,
            "observed_runtime_model": "UNAVAILABLE",
            "observed_reasoning": "UNAVAILABLE",
            "uses_verify_reports_and_plan": True,
            "readonly": True,
            "pre_fingerprint": "aa",
            "post_fingerprint": "bb",
            "mutation_detected": True,
            "contradictory_metadata": False,
            "fallback_or_substitution_message": False,
        }
    )
    assert result["gate_e"] == "BLOCKED"
    assert "mutation" in result["reason"]


def test_reviewer_evidence_profile_blocks_on_partial_model_only() -> None:
    """Model available and reasoning UNAVAILABLE → BLOCKED (partial runtime metadata)."""
    result = classify_reviewer_evidence_profile(
        {
            "agent_instantiated": True,
            "agent_id": "abc-123",
            "separate_context": True,
            "configured_model": REQUIRED_FRONTMATTER_MODEL,
            "requested_model": REQUIRED_TASK_MODEL,
            "observed_runtime_model": "gpt-5.6-terra",
            "observed_reasoning": "UNAVAILABLE",
            "uses_verify_reports_and_plan": True,
            "readonly": True,
            "pre_fingerprint": "aa",
            "post_fingerprint": "aa",
            "mutation_detected": False,
            "contradictory_metadata": False,
            "fallback_or_substitution_message": False,
        }
    )
    assert result["gate_e"] == "BLOCKED"
    assert result["evidence_profile"] == "UNVERIFIED"
    assert "partial runtime metadata" in result["reason"]
    assert result["evidence_profile"] != "CONTROL_PLANE_PINNED"


def test_reviewer_evidence_profile_blocks_on_partial_reasoning_only() -> None:
    """Reasoning available and model UNAVAILABLE → BLOCKED (partial runtime metadata)."""
    result = classify_reviewer_evidence_profile(
        {
            "agent_instantiated": True,
            "agent_id": "abc-123",
            "separate_context": True,
            "configured_model": REQUIRED_FRONTMATTER_MODEL,
            "requested_model": REQUIRED_TASK_MODEL,
            "observed_runtime_model": "UNAVAILABLE",
            "observed_reasoning": "xhigh",
            "uses_verify_reports_and_plan": True,
            "readonly": True,
            "pre_fingerprint": "aa",
            "post_fingerprint": "aa",
            "mutation_detected": False,
            "contradictory_metadata": False,
            "fallback_or_substitution_message": False,
        }
    )
    assert result["gate_e"] == "BLOCKED"
    assert "partial runtime metadata" in result["reason"]
    assert result["evidence_profile"] != "CONTROL_PLANE_PINNED"


def test_macro_skill_disallows_implicit_invocation() -> None:
    yaml_text = _read(SKILL_ROOT / "agents" / "openai.yaml")
    assert "allow_implicit_invocation: false" in yaml_text
    assert "allow_implicit_invocation: true" not in yaml_text


def test_reviewer_evidence_profile_forbids_false_runtime_attested_claim() -> None:
    result = classify_reviewer_evidence_profile(
        {
            "agent_instantiated": True,
            "agent_id": "abc-123",
            "separate_context": True,
            "configured_model": REQUIRED_FRONTMATTER_MODEL,
            "requested_model": REQUIRED_TASK_MODEL,
            "observed_runtime_model": "UNAVAILABLE",
            "observed_reasoning": "UNAVAILABLE",
            "uses_verify_reports_and_plan": True,
            "readonly": True,
            "pre_fingerprint": "aa",
            "post_fingerprint": "aa",
            "mutation_detected": False,
            "contradictory_metadata": False,
            "fallback_or_substitution_message": False,
        }
    )
    assert result["evidence_profile"] == "CONTROL_PLANE_PINNED"
    assert result["evidence_profile"] != "RUNTIME_ATTESTED"
    assert result["observed_runtime_model"] == "UNAVAILABLE"


def test_d15_r23_consistency_across_plan_roadmap_agent_skill() -> None:
    plan = _read(AP029_PLAN)
    roadmap = _read(ROADMAP)
    agent = _read(AGENT)
    skill = _read(SKILL)

    assert "### D15" in plan
    assert "RUNTIME_ATTESTED" in plan
    assert "CONTROL_PLANE_PINNED" in plan
    assert "UNVERIFIED" in plan
    assert "R23" in plan
    assert "Laufzeitmodell-Metadaten" in plan or "Laufzeitmodell" in plan

    # Roadmap must not contradict D15 profiles once mentioned; at minimum plan owns D15.
    assert "ausschliesslich GOV01" in roadmap or "ausschließlich GOV01" in roadmap
    assert "CONTROL_PLANE_PINNED" in skill
    assert "[ROLE:checkpoint-reviewer]" in agent
    assert f"model: {REQUIRED_FRONTMATTER_MODEL}" in agent
    assert REQUIRED_TASK_MODEL in skill


def test_checkpoint_snapshot_records_allowed_diff_and_hash(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "tests@example.invalid")
    _git(repo, "config", "user.name", "Tests")
    tracked = repo / "tracked.txt"
    tracked.write_text("before\n", encoding="utf-8")
    _git(repo, "add", "tracked.txt")
    _git(repo, "commit", "-q", "-m", "baseline")
    tracked.write_text("after\n", encoding="utf-8")

    output = "build/ap-029-test/snapshot.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(SNAPSHOT),
            "--root",
            str(repo),
            "--checkpoint",
            "TEST",
            "--phase",
            "before-review",
            "--output",
            output,
            "--allow",
            "tracked.txt",
            "--base-ref",
            "HEAD",
            "--fail-on-out-of-scope",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads((repo / output).read_text(encoding="utf-8"))
    assert payload["allowed_changed_paths"] == ["tracked.txt"]
    assert payload["out_of_scope_paths"] == []
    assert len(payload["repository_state_sha256"]) == 64
    assert payload["files"][0]["sha256"]
    assert payload["files"][0]["unstaged"] is True

    first_fingerprint = payload["repository_state_sha256"]
    (repo / output).unlink()
    _git(repo, "add", "tracked.txt")
    completed = subprocess.run(
        [
            sys.executable,
            str(SNAPSHOT),
            "--root",
            str(repo),
            "--checkpoint",
            "TEST",
            "--phase",
            "post-stage",
            "--output",
            output,
            "--allow",
            "tracked.txt",
            "--base-ref",
            "HEAD",
            "--fail-on-out-of-scope",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    staged_payload = json.loads((repo / output).read_text(encoding="utf-8"))
    assert staged_payload["repository_state_sha256"] != first_fingerprint
    assert staged_payload["files"][0]["staged"] is True
    assert staged_payload["files"][0]["unstaged"] is False


def test_checkpoint_snapshot_fails_closed_on_out_of_scope_path(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "tests@example.invalid")
    _git(repo, "config", "user.name", "Tests")
    (repo / "allowed.txt").write_text("baseline\n", encoding="utf-8")
    _git(repo, "add", "allowed.txt")
    _git(repo, "commit", "-q", "-m", "baseline")
    (repo / "unexpected.txt").write_text("foreign\n", encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(SNAPSHOT),
            "--root",
            str(repo),
            "--checkpoint",
            "TEST",
            "--phase",
            "before",
            "--output",
            "build/ap-029-test/snapshot.json",
            "--allow",
            "allowed.txt",
            "--base-ref",
            "HEAD",
            "--fail-on-out-of-scope",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    payload = json.loads(
        (repo / "build" / "ap-029-test" / "snapshot.json").read_text(encoding="utf-8")
    )
    assert payload["out_of_scope_paths"] == ["unexpected.txt"]
