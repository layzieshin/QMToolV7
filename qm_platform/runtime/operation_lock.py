"""Installation-scoped exclusive operation lock (OPS00-C)."""
from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from qm_platform.runtime.paths import resolve_home_path, runtime_home


class OperationLockError(RuntimeError):
    """Raised when the exclusive operation lock cannot be acquired or released."""


def operation_lock_path(app_home: Path | None = None) -> Path:
    home = app_home if app_home is not None else runtime_home()
    return resolve_home_path(home, "storage/platform/operation.lock")


def is_operation_lock_held(app_home: Path | None = None) -> bool:
    return operation_lock_path(app_home).is_file()


class OperationLock:
    """Exclusive installation-scoped lock for backup/restore operations."""

    def __init__(self, app_home: Path | None = None) -> None:
        self._path = operation_lock_path(app_home)
        self._fd: int | None = None

    def acquire(self) -> None:
        if self._fd is not None:
            raise OperationLockError("operation lock already acquired in this context")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(str(self._path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
        except FileExistsError as exc:
            raise OperationLockError("exclusive operation lock already held") from exc
        os.write(fd, str(os.getpid()).encode("ascii"))
        self._fd = fd

    def release(self) -> None:
        if self._fd is None:
            return
        os.close(self._fd)
        self._fd = None
        try:
            self._path.unlink(missing_ok=True)
        except OSError as exc:
            raise OperationLockError("failed to release operation lock") from exc

    def __enter__(self) -> OperationLock:
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()


@contextmanager
def exclusive_operation_lock(app_home: Path | None = None) -> Iterator[OperationLock]:
    lock = OperationLock(app_home)
    lock.acquire()
    try:
        yield lock
    finally:
        lock.release()
