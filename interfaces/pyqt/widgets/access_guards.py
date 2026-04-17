from __future__ import annotations

from interfaces.pyqt.contributions.common import normalize_role
from modules.usermanagement.role_policies import is_effective_qmb


def require_admin_or_qmb(usermanagement_service) -> object:
    user = usermanagement_service.get_current_user()
    if user is None:
        raise RuntimeError("Anmeldung erforderlich")
    role = normalize_role(user.role)
    if role != "ADMIN" and not is_effective_qmb(user):
        raise RuntimeError("Nur QMB oder ADMIN dürfen diesen Bereich nutzen")
    return user
