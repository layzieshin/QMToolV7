from __future__ import annotations

import json
from pathlib import Path

from .contracts import ControlClass
from .errors import ValidationError
from .workflow_profile_store import (
    WorkflowProfileTransitionDefinition,
    WorkflowProfileVersionDefinition,
    _sha256_text,
    normalize_legacy_status,
)


class WorkflowProfileSeedReader:
    """Private bootstrap/upgrade reader. Not a runtime profile store."""

    def read(self, file_path: Path) -> dict[str, object]:
        if not file_path.exists():
            raise ValidationError(f"workflow profiles file not found: {file_path}")
        raw_text = file_path.read_text(encoding="utf-8")
        raw_sha256 = _sha256_text(raw_text)
        raw = json.loads(raw_text)
        profiles = raw.get("profiles", [])
        if not isinstance(profiles, list) or not profiles:
            raise ValidationError("workflow profiles must contain a non-empty 'profiles' list")
        parsed: list[WorkflowProfileVersionDefinition] = []
        seen_codes: set[str] = set()
        for item in profiles:
            if not isinstance(item, dict):
                raise ValidationError("workflow profile entries must be objects")
            profile = self._parse_profile(item)
            if profile.profile_code in seen_codes:
                raise ValidationError(f"duplicate workflow profile id: {profile.profile_code}")
            seen_codes.add(profile.profile_code)
            parsed.append(profile)
        semantic_payload = [item.semantic_payload() for item in sorted(parsed, key=lambda row: row.profile_code)]
        return {
            "profiles": tuple(parsed),
            "raw_sha256": raw_sha256,
            "semantic_sha256": _sha256_text(
                json.dumps(semantic_payload, sort_keys=True, separators=(",", ":"))
            ),
        }

    def _parse_profile(self, item: dict[str, object]) -> WorkflowProfileVersionDefinition:
        profile_code = str(item.get("profile_id", "")).strip()
        if not profile_code:
            raise ValidationError("profile_id is required")
        label = str(item.get("label", "")).strip()
        if not label:
            raise ValidationError(f"profile '{profile_code}' requires a label")
        try:
            control_class = ControlClass(str(item.get("control_class", "CONTROLLED")))
        except ValueError as exc:
            raise ValidationError(f"profile '{profile_code}' has invalid control_class") from exc

        raw_phases = [normalize_legacy_status(str(value)) for value in item.get("phases", [])]
        if not raw_phases:
            raise ValidationError(f"profile '{profile_code}' requires phases")
        # Legacy JSON starts with IN_PROGRESS (runtime editor phase). Relational model stores DRAFT.
        # Runtime reconstruction remaps DRAFT -> IN_PROGRESS at the adapter boundary.
        if raw_phases[0] == "IN_PROGRESS":
            raw_phases[0] = "DRAFT"
        if raw_phases[0] != "DRAFT" or raw_phases[-1] != "APPROVED":
            raise ValidationError(
                f"profile '{profile_code}' must start with DRAFT (legacy IN_PROGRESS) and end with APPROVED"
            )

        signature_required = set()
        for value in item.get("signature_required_transitions", []):
            edge = str(value).strip()
            if not edge:
                continue
            left, sep, right = edge.partition("->")
            if not sep:
                raise ValidationError(f"profile '{profile_code}' has invalid signature transition: {edge}")
            signature_required.add(f"{normalize_legacy_status(left)}->{normalize_legacy_status(right)}")

        profile_four_eyes = bool(item.get("four_eyes_required", False))
        transitions: list[WorkflowProfileTransitionDefinition] = []
        for index in range(len(raw_phases) - 1):
            from_status = raw_phases[index]
            to_status = raw_phases[index + 1]
            required_role = _role_for_transition(from_status, to_status)
            edge = f"{from_status}->{to_status}"
            four_eyes = bool(profile_four_eyes and to_status == "APPROVED")
            transitions.append(
                WorkflowProfileTransitionDefinition(
                    transition_no=index + 1,
                    from_status=from_status,
                    to_status=to_status,
                    required_role=required_role,
                    decision_policy="ONE_OF_POOL",
                    signature_required=edge in signature_required,
                    four_eyes_required=four_eyes,
                    revoke_if_changed=False,
                    deadline_seconds=None,
                    is_enabled=True,
                )
            )
        return WorkflowProfileVersionDefinition(
            profile_code=profile_code,
            label=label,
            control_class=control_class,
            release_evidence_mode=str(item.get("release_evidence_mode", "WORKFLOW")),
            requires_editors=bool(item.get("requires_editors", True)),
            requires_reviewers=bool(item.get("requires_reviewers", True)),
            requires_approvers=bool(item.get("requires_approvers", True)),
            allows_content_changes=bool(item.get("allows_content_changes", True)),
            transitions=tuple(transitions),
        )


def _role_for_transition(from_status: str, to_status: str) -> str:
    if from_status == "DRAFT":
        return "EDITOR"
    if from_status == "IN_REVIEW":
        return "REVIEWER"
    if from_status == "IN_APPROVAL":
        return "APPROVER"
    if to_status == "APPROVED":
        return "APPROVER"
    return "NONE"
