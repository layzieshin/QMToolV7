from __future__ import annotations


class TrainingError(RuntimeError):
    pass


class TrainingValidationError(TrainingError):
    pass


class TrainingPermissionError(TrainingError):
    pass
