"""Stable machine identity for license binding (offline, local only)."""
from __future__ import annotations

import hashlib
import sys
import uuid


def _windows_machine_guid() -> str | None:
    if sys.platform != "win32":
        return None
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
        guid = str(value).strip()
        return guid or None
    except OSError:
        return None


def _mac_node() -> int:
    return uuid.getnode()


def get_machine_id_source() -> str:
    if _windows_machine_guid() is not None:
        return "windows_machine_guid"
    return "fallback_mac_address"


def get_machine_id() -> str:
    """
    Stable machine identifier for license binding.

    Priority:
    1. Windows MachineGuid (stable across hostname changes)
    2. Fallback: MAC address node id only (no hostname — avoids spurious changes)
    """
    seed = _windows_machine_guid()
    if seed is None:
        seed = f"mac:{_mac_node():012x}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return f"qmt-{digest[:16]}"
