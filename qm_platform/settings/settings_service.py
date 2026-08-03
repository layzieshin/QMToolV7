from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from modules.usermanagement.contracts import UserContext

from .actors import ALLOWED_SYSTEM_ACTORS
from .errors import (
    BootstrapSettingImmutableError,
    BucketBIncompleteError,
    MissingRequiredSettingError,
    ResidualArchiveMissingError,
    ResidualPolicyReadonlyError,
    SettingsActorRequiredError,
    SettingsOverlapError,
    UnknownSettingKeyError,
)
from .expected_keys import expected_residual_keys_by_module, expected_technical_keys_by_module
from .governance_critical_keys import get_governance_critical_keys
from .key_classification import (
    SettingBucket,
    classify_key,
)
from .residual_store import ResidualSettingsStore
from .schema_validation import validate_technical_settings_payload
from .settings_registry import SettingsRegistry
from .sqlite_settings_repository import SqliteSettingsRepository


def _actor_id(actor: object) -> str:
    """Accept confirmed ``UserContext`` or explicit system/migration actor strings.

    Never invent an actor from legacy current_user payloads. Requires
    ``isinstance(actor, UserContext)`` and ``_server_confirmed is True``.
    """
    if isinstance(actor, str) and actor in ALLOWED_SYSTEM_ACTORS:
        return actor
    if (
        isinstance(actor, UserContext)
        and actor._server_confirmed is True
        and actor.user_id
        and actor.session_id
        and actor.request_id
    ):
        return str(actor.user_id)
    raise SettingsActorRequiredError(
        "settings writes require a confirmed UserContext (issue_user_context) "
        "or an explicit system/migration actor; legacy current_user and forged "
        "actors are not valid"
    )


@dataclass
class SettingsService:
    registry: SettingsRegistry
    repository: SqliteSettingsRepository | None = None
    residual: ResidualSettingsStore | None = None
    _persistence_ready: bool = field(default=False, init=False, repr=False)
    _cutover_completed: bool = field(default=False, init=False, repr=False)

    def attach_persistence(
        self,
        repository: SqliteSettingsRepository,
        residual: ResidualSettingsStore | None = None,
        *,
        require_residual_if_present: bool = True,
        cutover_completed: bool = False,
    ) -> None:
        self.repository = repository
        self.residual = residual
        self._cutover_completed = bool(cutover_completed)
        if residual is not None and residual.exists():
            residual.verify()
            self._assert_residual_complete()
        elif require_residual_if_present and residual is not None and residual.hash_path.is_file():
            residual.verify()
        self._assert_no_overlap()
        if self._cutover_completed:
            self.assert_bucket_b_complete()
        self._persistence_ready = True

    def _require_persistence(self) -> SqliteSettingsRepository:
        if not self._persistence_ready or self.repository is None:
            raise RuntimeError("settings persistence is not attached yet")
        return self.repository

    def _assert_no_overlap(self) -> None:
        if self.repository is None:
            return
        db_keys = self.repository.list_all_technical_keys()
        residual_keys = self.residual.list_policy_keys() if self.residual and self.residual.exists() else set()
        overlap = sorted(db_keys & residual_keys)
        if overlap:
            raise SettingsOverlapError(
                f"settings key present in both DB and residual: {overlap}"
            )

    def _assert_residual_complete(self) -> None:
        if self.residual is None or not self.residual.exists():
            return
        expected = expected_residual_keys_by_module(self.registry)
        if not expected:
            return
        schema_by_module = {
            module_id: (self.registry.get(module_id).schema or {})
            for module_id in expected
            if self.registry.get(module_id) is not None
        }
        self.residual.assert_complete_against_expected(
            expected,
            schema_by_module=schema_by_module,
        )

    def assert_bucket_b_complete(self) -> None:
        repository = self._require_persistence() if self._persistence_ready else self.repository
        if repository is None:
            raise RuntimeError("settings persistence is not attached yet")
        missing: list[str] = []
        for module_id, keys in expected_technical_keys_by_module(self.registry).items():
            loaded = repository.load_module_technical(module_id)
            for key in keys:
                if key not in loaded:
                    missing.append(f"{module_id}.{key}")
        if missing:
            raise BucketBIncompleteError(
                "platform_settings missing required Bucket-B keys after cutover: "
                + ", ".join(sorted(missing))
            )

    def _module_declares_residual_keys(self, module_id: str) -> bool:
        expected = expected_residual_keys_by_module(self.registry)
        return bool(expected.get(module_id))

    def _technical_defaults(self, module_id: str) -> dict[str, Any]:
        contribution = self.registry.get(module_id)
        if contribution is None:
            return {}
        out: dict[str, Any] = {}
        for key, value in (contribution.defaults or {}).items():
            if classify_key(module_id, key) == SettingBucket.TECHNICAL:
                out[key] = value
        return out

    def _residual_policy_values(self, module_id: str) -> dict[str, Any]:
        """Bucket C exclusively from residual JSON — never contribution defaults."""
        declares_c = self._module_declares_residual_keys(module_id)
        if self.residual is None or not self.residual.exists():
            if declares_c:
                raise ResidualArchiveMissingError(
                    f"residual archive required for Bucket-C settings of module {module_id}"
                )
            return {}
        return self.residual.load_policy_module(module_id)

    def get_module_settings(self, module_id: str) -> dict[str, Any]:
        if self._cutover_completed and self.repository is not None and self._persistence_ready:
            result = dict(self.repository.load_module_technical(module_id))
        else:
            result = dict(self._technical_defaults(module_id))
            if self.repository is not None and self._persistence_ready:
                result.update(self.repository.load_module_technical(module_id))
        result.update(self._residual_policy_values(module_id))
        return result

    def set_module_settings(
        self,
        module_id: str,
        values: dict[str, Any],
        *,
        actor: object,
        acknowledge_governance_change: bool = False,
        reason: str | None = None,
    ) -> None:
        contribution = self.registry.get(module_id)
        if contribution is None:
            raise KeyError(f"unknown module settings contribution: {module_id}")
        self.registry.validate_contribution(contribution)
        actor_id = _actor_id(actor)
        repository = self._require_persistence()

        if not isinstance(values, dict):
            raise UnknownSettingKeyError("settings payload must be an object")

        technical: dict[str, Any] = {}
        for key, value in values.items():
            bucket = classify_key(module_id, str(key))
            if bucket is SettingBucket.BOOTSTRAP:
                raise BootstrapSettingImmutableError(
                    f"bootstrap setting is immutable via SettingsService: {module_id}.{key}"
                )
            if bucket is SettingBucket.RESIDUAL_POLICY:
                raise ResidualPolicyReadonlyError(
                    f"residual policy setting is read-only: {module_id}.{key}"
                )
            if bucket is SettingBucket.TECHNICAL:
                technical[str(key)] = value
                continue
            raise UnknownSettingKeyError(f"unknown setting key: {module_id}.{key}")

        schema_props = ((contribution.schema or {}).get("properties") or {})
        required = [
            key
            for key in (contribution.schema or {}).get("required") or []
            if classify_key(module_id, str(key)) == SettingBucket.TECHNICAL
        ]
        missing = [key for key in required if key not in technical]
        if missing:
            raise MissingRequiredSettingError(
                f"missing required technical settings for {module_id}: {missing}"
            )
        if schema_props:
            for key in technical:
                if key not in schema_props:
                    raise UnknownSettingKeyError(f"unknown setting key: {module_id}.{key}")

        validate_technical_settings_payload(
            module_id,
            technical,
            contribution.schema or {},
        )

        governance_keys = get_governance_critical_keys(module_id)
        touched_governance_keys = sorted(set(technical) & set(governance_keys))
        if touched_governance_keys and not acknowledge_governance_change:
            raise ValueError(
                "governance_critical settings require explicit acknowledge flag "
                "and release change-control"
            )

        repository.replace_module_technical(
            module_id,
            technical,
            actor=actor_id,
            schema_version=int(contribution.schema_version),
            reason=reason,
        )
        self._assert_no_overlap()
