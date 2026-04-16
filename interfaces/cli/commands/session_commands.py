from __future__ import annotations

from qm_platform.runtime import bootstrap as runtime_bootstrap

from interfaces.cli.bootstrap import build_container


def cmd_login(username: str, password: str) -> int:
    container = build_container()
    lifecycle = runtime_bootstrap.register_core_modules(container)
    lifecycle.start()
    service = container.get_port("usermanagement_service")
    user = service.login(username, password)
    if user is None:
        print("BLOCKED: invalid credentials")
        return 3
    print(f"OK: authenticated as '{user.username}' with role '{user.role}'")
    return 0


def cmd_logout() -> int:
    container = build_container()
    lifecycle = runtime_bootstrap.register_core_modules(container)
    lifecycle.start()
    service = container.get_port("usermanagement_service")
    service.logout()
    print("OK: logged out")
    return 0

