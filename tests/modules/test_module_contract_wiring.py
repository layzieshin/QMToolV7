from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULES_ROOT = ROOT / "modules"


def _module_dirs_with_contract_and_wiring() -> list[Path]:
    return sorted(
        path
        for path in MODULES_ROOT.iterdir()
        if path.is_dir() and (path / "module.py").exists() and (path / "wiring.py").exists()
    )


def _required_ports(module_py: Path) -> set[str]:
    tree = ast.parse(module_py.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for keyword in node.keywords:
            if keyword.arg != "required_ports":
                continue
            if not isinstance(keyword.value, ast.List):
                raise AssertionError(f"{module_py.relative_to(ROOT)} uses non-literal required_ports")
            return {
                item.value
                for item in keyword.value.elts
                if isinstance(item, ast.Constant) and isinstance(item.value, str)
            }
    raise AssertionError(f"{module_py.relative_to(ROOT)} does not declare required_ports")


def _literal_port_arg(node: ast.Call) -> str | None:
    if not node.args:
        return None
    first = node.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value
    return None


def _is_container_method_call(node: ast.Call, method_name: str) -> bool:
    return (
        isinstance(node.func, ast.Attribute)
        and node.func.attr == method_name
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "container"
    )


def _test_has_matching_has_port(test: ast.AST, port: str) -> bool:
    for node in ast.walk(test):
        if not isinstance(node, ast.Call) or not _is_container_method_call(node, "has_port"):
            continue
        if _literal_port_arg(node) == port:
            return True
    return False


def _parent_map(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent
    return parents


def _is_optional_get_port(node: ast.Call, port: str, parents: dict[ast.AST, ast.AST]) -> bool:
    current: ast.AST = node
    while current in parents:
        parent = parents[current]
        if isinstance(parent, ast.IfExp) and parent.body is current:
            if _test_has_matching_has_port(parent.test, port):
                return True
        if isinstance(parent, ast.If) and current in parent.body:
            if _test_has_matching_has_port(parent.test, port):
                return True
        current = parent
    return False


def _hard_wiring_ports(wiring_py: Path) -> set[str]:
    tree = ast.parse(wiring_py.read_text(encoding="utf-8"))
    parents = _parent_map(tree)
    ports: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not _is_container_method_call(node, "get_port"):
            continue
        port = _literal_port_arg(node)
        if port is None:
            raise AssertionError(f"{wiring_py.relative_to(ROOT)} uses non-literal get_port")
        if not _is_optional_get_port(node, port, parents):
            ports.add(port)
    return ports


def test_module_wiring_hard_get_ports_are_declared_as_required_ports() -> None:
    violations: list[str] = []
    for module_dir in _module_dirs_with_contract_and_wiring():
        required = _required_ports(module_dir / "module.py")
        hard_ports = _hard_wiring_ports(module_dir / "wiring.py")
        missing = sorted(hard_ports - required)
        if missing:
            violations.append(f"{module_dir.name}: {missing}")

    assert violations == []
