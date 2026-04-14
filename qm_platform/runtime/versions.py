from __future__ import annotations

from dataclasses import dataclass


PLATFORM_VERSION = "1.0.0"


def _parse(v: str) -> tuple[int, int, int]:
    parts = v.split(".")
    if len(parts) != 3:
        raise ValueError(f"invalid semver: {v}")
    return int(parts[0]), int(parts[1]), int(parts[2])


@dataclass(frozen=True)
class CompatibilityResult:
    ok: bool
    reason: str = ""


def is_platform_compatible(min_version: str, max_version: str | None, current_version: str = PLATFORM_VERSION) -> CompatibilityResult:
    cur = _parse(current_version)
    min_v = _parse(min_version)
    if cur < min_v:
        return CompatibilityResult(False, f"platform version {current_version} < min {min_version}")
    if max_version:
        max_v = _parse(max_version)
        if cur > max_v:
            return CompatibilityResult(False, f"platform version {current_version} > max {max_version}")
    return CompatibilityResult(True, "")

