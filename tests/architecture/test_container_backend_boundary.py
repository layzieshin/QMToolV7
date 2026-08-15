from __future__ import annotations

from qm_platform.runtime.bootstrap import all_module_contracts, backend_module_contracts, core_module_contracts


def test_container_is_backend_only_and_exports_only_api_port():
    assert "container" not in [contract.module_id for contract in core_module_contracts()]
    contract = backend_module_contracts()[0]
    assert contract.module_id == "container"
    assert contract.provided_ports == ["container_api"]
    assert "container.blueprint.manage" in contract.provided_capabilities
    assert [contract.module_id for contract in all_module_contracts()][-1] == "container"
