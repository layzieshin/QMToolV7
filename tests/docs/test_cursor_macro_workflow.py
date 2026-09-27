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

    assert ".cursor/agent-system.json" in skill
    assert "configured checkpoint-rework budget" in skill
    assert "checkpoint-contract.md" in skill
    assert "contract_sha256" in skill
    assert "SCOPE_CORRECTION_REQUIRED" in skill
    assert "Never run Codex after individual AP-029 subcheckpoints" in skill
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
    assert "Immutable checkpoint contract" in protocol
    assert "Scope correction" in protocol
    assert "no text in this protocol creates a separate budget" in protocol

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


def _pilot00_review_policy() -> dict[str, str]:
    text = _read(PROTOCOL)
    start = "<!-- PILOT00_ORCHESTRATOR_REVIEW_START -->"
    end = "<!-- PILOT00_ORCHESTRATOR_REVIEW_END -->"
    body = text.split(start, 1)[1].split(end, 1)[0]
    fields: dict[str, str] = {}
    for raw in body.splitlines():
        line = raw.strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip()
    return fields


def classify_pilot00_orchestrator_review(facts: dict[str, Any]) -> dict[str, str]:
    """PILOT00-only substitute. Not a native runtime or control-plane profile."""

    policy = _pilot00_review_policy()
    packages = set(policy["scope_packages"].split())
    rejected = {
        "label": "REJECTED",
        "verdict": "FAIL",
        "evidence_profile": "UNVERIFIED",
        "runtime_attested": "false",
        "control_plane_pinned": "false",
    }

    def block(reason: str) -> dict[str, str]:
        return {**rejected, "reason": reason}

    if facts.get("native_role_result") != "UNAVAILABLE":
        return block("native role was not explicitly UNAVAILABLE")
    if facts.get("package") not in packages:
        return block("wrong package")
    if facts.get("authorization_source") != policy["known_authorization"]:
        return block("unknown authorization")
    if policy.get("target_source") != "frozen_checkpoint_contract" or "expected_target" in policy:
        return block("foreign target")
    frozen_target = str(facts.get("contract_target_root") or "")
    actual_target = str(facts.get("target_root") or "")
    if not frozen_target or actual_target != frozen_target:
        return block("foreign target")
    if not facts.get("separate_reviewer") or not facts.get("separate_context"):
        return block("not a separate reviewer")
    author = str(facts.get("author_id") or "")
    reviewer = str(facts.get("reviewer_id") or "")
    implementer = str(facts.get("implementer_id") or "")
    if not author or not reviewer or author == reviewer:
        return block("same author")
    if not implementer or implementer == reviewer:
        return block("same implementer")
    consumed = facts.get("substitute_attempts_for_role_need")
    limit_text = policy.get("max_substitutes_per_role_need")
    if isinstance(consumed, bool) or not isinstance(consumed, int) or not str(limit_text).isdigit():
        return block("substitute already used")
    if consumed < 0 or consumed >= int(limit_text):
        return block("substitute already used")
    if facts.get("mutation_detected") or facts.get("pre_fingerprint") != facts.get("post_fingerprint"):
        return block("mutation")
    if not facts.get("pre_fingerprint") or not facts.get("post_fingerprint"):
        return block("mutation")
    if facts.get("contradictory_metadata"):
        return block("contradictory metadata")
    if facts.get("human_gate_open") and facts.get("verdict") == "PASS":
        return block("open human gate as PASS")
    if not facts.get("agent_id") or not facts.get("readonly"):
        return block("missing separate reviewer evidence")
    if "requested_model" not in facts or "observed_model" not in facts:
        return block("contradictory metadata")
    if facts.get("contract_sha256") != facts.get("expected_contract_sha256"):
        return block("contradictory metadata")
    if facts.get("diff_sha256") != facts.get("expected_diff_sha256"):
        return block("contradictory metadata")
    if facts.get("label") != policy["label"]:
        return block("wrong label")
    if facts.get("claims_runtime_attested") or facts.get("claims_control_plane"):
        return block("false runtime attestation")
    if facts.get("verdict") != "PASS":
        return block("verdict is not PASS")
    return {
        "label": "INDEPENDENT_ORCHESTRATOR_REVIEW",
        "verdict": "PASS",
        "reason": "substitute evidence complete",
        "evidence_profile": "INDEPENDENT_ORCHESTRATOR_REVIEW",
        "runtime_attested": "false",
        "control_plane_pinned": "false",
    }


def _valid_orchestrator_review() -> dict[str, Any]:
    policy = _pilot00_review_policy()
    return {
        "native_role_result": "UNAVAILABLE",
        "package": "PILOT00-AUTONOMY-AMENDMENT",
        "authorization_source": policy["known_authorization"],
        "target_root": r"I:\Projekte\QMToolV7\build\worktrees\ap-029-pilot00",
        "contract_target_root": r"I:\Projekte\QMToolV7\build\worktrees\ap-029-pilot00",
        "separate_reviewer": True,
        "separate_context": True,
        "author_id": "author-1",
        "implementer_id": "implementer-1",
        "reviewer_id": "orchestrator-review-9",
        "substitute_attempts_for_role_need": 0,
        "mutation_detected": False,
        "pre_fingerprint": "pre",
        "post_fingerprint": "pre",
        "contradictory_metadata": False,
        "human_gate_open": False,
        "agent_id": "task-real-1",
        "readonly": True,
        "requested_model": "gpt-5.6-terra",
        "observed_model": "UNAVAILABLE",
        "contract_sha256": "contract",
        "expected_contract_sha256": "contract",
        "diff_sha256": "diff",
        "expected_diff_sha256": "diff",
        "label": "INDEPENDENT_ORCHESTRATOR_REVIEW",
        "claims_runtime_attested": False,
        "claims_control_plane": False,
        "verdict": "PASS",
    }


def test_pilot00_orchestrator_review_accepts_one_separate_readonly_report() -> None:
    policy = _pilot00_review_policy()
    assert policy["label"] == "INDEPENDENT_ORCHESTRATOR_REVIEW"
    assert policy["runtime_attestation"] == "false"
    assert policy["global_relaxation"] == "false"
    assert policy["target_source"] == "frozen_checkpoint_contract"
    assert "expected_target" not in policy
    assert "INDEPENDENT_ORCHESTRATOR_REVIEW" in _read(SKILL)
    assert "INDEPENDENT_ORCHESTRATOR_REVIEW" in _read(PROTOCOL)
    assert "INDEPENDENT_ORCHESTRATOR_REVIEW" in _read(WORKFLOW)
    result = classify_pilot00_orchestrator_review(_valid_orchestrator_review())
    assert result["verdict"] == "PASS"
    assert result["evidence_profile"] == "INDEPENDENT_ORCHESTRATOR_REVIEW"
    assert result["evidence_profile"] != "RUNTIME_ATTESTED"
    assert result["evidence_profile"] != "CONTROL_PLANE_PINNED"
    assert result["runtime_attested"] == "false"


def test_pilot00_orchestrator_review_accepts_later_package_frozen_target() -> None:
    facts = _valid_orchestrator_review()
    facts["package"] = "PILOT00-SETTINGS-PG"
    later_target = r"I:\Projekte\QMToolV7\build\worktrees\ap-029-settings-pg"
    assert later_target != facts["contract_target_root"]
    facts["target_root"] = later_target
    facts["contract_target_root"] = later_target
    result = classify_pilot00_orchestrator_review(facts)
    assert result["verdict"] == "PASS"
    assert result["evidence_profile"] == "INDEPENDENT_ORCHESTRATOR_REVIEW"


def test_pilot00_orchestrator_review_rejects_forbidden_cases() -> None:
    cases = {
        "same author": {"author_id": "same", "reviewer_id": "same"},
        "not a separate reviewer": {"separate_reviewer": False},
        "mutation": {"mutation_detected": True, "post_fingerprint": "changed"},
        "contradictory metadata": {"contradictory_metadata": True},
        "wrong package": {"package": "WEB01"},
        "unknown authorization": {"authorization_source": "unknown-order.md"},
        "open human gate as PASS": {"human_gate_open": True},
        "foreign target": {"target_root": "I:\\Projekte\\QMToolV7"},
        "same implementer": {"implementer_id": "orchestrator-review-9"},
        "substitute already used": {"substitute_attempts_for_role_need": 1},
    }
    for needle, changes in cases.items():
        facts = _valid_orchestrator_review()
        facts.update(changes)
        result = classify_pilot00_orchestrator_review(facts)
        assert result["verdict"] == "FAIL", needle
        assert needle in result["reason"]
        assert result["evidence_profile"] != "RUNTIME_ATTESTED"
        assert result["evidence_profile"] != "CONTROL_PLANE_PINNED"
    missing_attempt = _valid_orchestrator_review()
    del missing_attempt["substitute_attempts_for_role_need"]
    missing_result = classify_pilot00_orchestrator_review(missing_attempt)
    assert missing_result["verdict"] == "FAIL"
    assert "substitute already used" in missing_result["reason"]
    missing_implementer = _valid_orchestrator_review()
    del missing_implementer["implementer_id"]
    missing_implementer_result = classify_pilot00_orchestrator_review(missing_implementer)
    assert missing_implementer_result["verdict"] == "FAIL"
    assert "same implementer" in missing_implementer_result["reason"]
