from __future__ import annotations

from typing import Any

from .license_guard import LicenseGuard


class LicensedPortProxy:
    """Wraps a port/API object and enforces module license on every callable attribute."""

    def __init__(self, inner: Any, guard: LicenseGuard, module_tag: str) -> None:
        self._inner = inner
        self._guard = guard
        self._module_tag = module_tag

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._inner, name)
        if not callable(attr):
            return attr

        def guarded(*args: Any, **kwargs: Any) -> Any:
            self._guard.ensure_module_allowed(self._module_tag)
            return attr(*args, **kwargs)

        return guarded
