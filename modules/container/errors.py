from __future__ import annotations


class ContainerError(RuntimeError):
    """A stable, client-safe container module failure."""

    def __init__(self, code: str, **params: object) -> None:
        self.code = code
        self.params = params
        super().__init__(code)
