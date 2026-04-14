from __future__ import annotations


class DocumentWorkflowError(RuntimeError):
    pass


class InvalidTransitionError(DocumentWorkflowError):
    pass


class PermissionDeniedError(DocumentWorkflowError):
    pass


class ValidationError(DocumentWorkflowError):
    pass

