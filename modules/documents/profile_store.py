from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .contracts import ControlClass, DocumentStatus, WorkflowProfile
from .errors import ValidationError


@dataclass
class WorkflowProfileStoreJSON:
    file_path: Path

    def load_all(self) -> dict[str, WorkflowProfile]:
        if not self.file_path.exists():
            raise ValidationError(f"workflow profiles file not found: {self.file_path}")
        raw = json.loads(self.file_path.read_text(encoding="utf-8"))
        profiles = raw.get("profiles", [])
        if not isinstance(profiles, list) or not profiles:
            raise ValidationError("workflow profiles must contain a non-empty 'profiles' list")
        resolved: dict[str, WorkflowProfile] = {}
        for item in profiles:
            profile = self._parse_profile(item)
            if profile.profile_id in resolved:
                raise ValidationError(f"duplicate workflow profile id: {profile.profile_id}")
            resolved[profile.profile_id] = profile
        return resolved

    def get(self, profile_id: str) -> WorkflowProfile:
        profiles = self.load_all()
        if profile_id not in profiles:
            raise ValidationError(f"unknown workflow profile: {profile_id}")
        return profiles[profile_id]

    @staticmethod
    def _parse_profile(item: dict) -> WorkflowProfile:
        phases = tuple(DocumentStatus(value) for value in item["phases"])
        profile = WorkflowProfile(
            profile_id=str(item["profile_id"]),
            label=str(item["label"]),
            phases=phases,
            four_eyes_required=bool(item["four_eyes_required"]),
            control_class=ControlClass(str(item.get("control_class", item.get("doc_type", "CONTROLLED")))),
            signature_required_transitions=tuple(str(v) for v in item.get("signature_required_transitions", [])),
            requires_editors=bool(item.get("requires_editors", True)),
            requires_reviewers=bool(item.get("requires_reviewers", True)),
            requires_approvers=bool(item.get("requires_approvers", True)),
            allows_content_changes=bool(item.get("allows_content_changes", True)),
            release_evidence_mode=str(item.get("release_evidence_mode", "WORKFLOW")),
        )
        if not profile.phases or profile.phases[0] != DocumentStatus.IN_PROGRESS:
            raise ValidationError(f"profile '{profile.profile_id}' must start with IN_PROGRESS")
        if profile.phases[-1] != DocumentStatus.APPROVED:
            raise ValidationError(f"profile '{profile.profile_id}' must end with APPROVED")
        return profile

