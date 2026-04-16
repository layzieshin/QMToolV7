from interfaces.cli.parsers.documents_parsers import register_documents_parsers
from interfaces.cli.parsers.runtime_parsers import register_runtime_parsers
from interfaces.cli.parsers.session_parsers import register_session_parsers
from interfaces.cli.parsers.settings_parsers import register_settings_parsers
from interfaces.cli.parsers.signature_parsers import register_signature_parsers, add_sign_layout_args
from interfaces.cli.parsers.training_parsers import register_training_parsers
from interfaces.cli.parsers.users_parsers import register_users_parsers

__all__ = [
    "register_documents_parsers",
    "register_runtime_parsers",
    "register_session_parsers",
    "register_settings_parsers",
    "register_signature_parsers",
    "register_training_parsers",
    "register_users_parsers",
    "add_sign_layout_args",
]

