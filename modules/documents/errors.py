from __future__ import annotations


class DocumentWorkflowError(RuntimeError):
    pass


class InvalidTransitionError(DocumentWorkflowError):
    pass


class PermissionDeniedError(DocumentWorkflowError):
    pass


class ValidationError(DocumentWorkflowError):
    pass


class SignatureTransitionError(ValidationError):
    pass


class DocumentsFeatureUnavailableError(DocumentWorkflowError):
    """Raised when a path is intentionally outside the reduced J04-M0 scope."""

    pass


class DocumentConflictError(DocumentWorkflowError):
    """Raised when a mutation is based on a stale document version state."""

    def __init__(self, current_state: object) -> None:
        super().__init__("document version changed since it was loaded")
        self.current_state = current_state


class HeaderConflictError(DocumentWorkflowError):
    def __init__(self, current_header: object) -> None:
        super().__init__("document header changed since it was loaded")
        self.current_header = current_header


class CommentConflictError(DocumentWorkflowError):
    def __init__(self, current_comment: object) -> None:
        super().__init__("comment changed since it was loaded")
        self.current_comment = current_comment

