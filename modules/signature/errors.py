from __future__ import annotations


class SignatureError(RuntimeError):
    """Base class for signature module errors."""


class PdfReadError(SignatureError):
    pass


class InvalidPlacementError(SignatureError):
    pass


class PasswordRequiredError(SignatureError):
    pass


class PasswordInvalidError(SignatureError):
    pass


class SignatureImageRequiredError(SignatureError):
    pass


class CryptoSigningNotConfiguredError(SignatureError):
    pass


class SignatureTemplateError(SignatureError):
    pass


class SignatureAssetError(SignatureError):
    pass

