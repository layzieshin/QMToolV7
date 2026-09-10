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
    def __init__(
        self,
        message: str,
        *,
        field_errors: list[dict[str, str]] | None = None,
    ) -> None:
        super().__init__(message)
        self.field_errors = field_errors


class SignatureAssetError(SignatureError):
    pass

