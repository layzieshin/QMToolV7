from __future__ import annotations

import unittest

from qm_platform.runtime.capabilities import CapabilityRegistry
from qm_platform.runtime.container import RuntimeContainer
from qm_platform.runtime.lifecycle import LifecycleManager
from qm_platform.sdk.module_contract import ModuleContract


def _noop(_: object) -> None:
    return None


def _contract(
    module_id: str,
    required_capabilities: list[str],
    provided_capabilities: list[str],
) -> ModuleContract:
    return ModuleContract(
        module_id=module_id,
        version="1.0.0",
        min_platform_version="1.0.0",
        max_platform_version=None,
        required_ports=[],
        provided_ports=[],
        required_capabilities=required_capabilities,
        provided_capabilities=provided_capabilities,
        settings_contribution=None,
        license_tag=None,
        register=_noop,
        start=_noop,
        stop=_noop,
    )


class CapabilityRegistryTest(unittest.TestCase):
    def test_registry_prevents_duplicate_provider(self) -> None:
        reg = CapabilityRegistry()
        reg.register("m1", ["cap.a"])
        with self.assertRaises(ValueError):
            reg.register("m2", ["cap.a"])

    def test_lifecycle_checks_required_capabilities(self) -> None:
        lifecycle = LifecycleManager(RuntimeContainer())
        lifecycle.register(_contract("provider", [], ["cap.a"]))
        lifecycle.register(_contract("consumer", ["cap.a"], []))
        lifecycle.start()  # should not raise

    def test_lifecycle_fails_for_missing_capability(self) -> None:
        lifecycle = LifecycleManager(RuntimeContainer())
        lifecycle.register(_contract("consumer", ["cap.missing"], []))
        with self.assertRaises(RuntimeError):
            lifecycle.start()


if __name__ == "__main__":
    unittest.main()

