"""Installation-scoped exclusive operation lock (OPS00-C)."""
from __future__ import annotations

import os
import uuid
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
    # Any filesystem entry at the canonical path blocks a second operation.
    # This deliberately treats a stale legacy file as held as well as the
    # ownership directory used by current releases.
    return os.path.lexists(operation_lock_path(app_home))


class OperationLock:
    """Exclusive installation-scoped lock for backup/restore operations."""

    def __init__(self, app_home: Path | None = None) -> None:
        self._path = operation_lock_path(app_home)
        self._fd: int | None = None
        self._owner_path: Path | None = None

    def validate_held_for(self, app_home: Path | None = None) -> None:
        """Fail closed unless this instance is acquired for ``app_home``.

        A boolean flag, PID text, or path-only observation cannot satisfy this
        check: the live file descriptor, resolved lock path, and lock file
        must all agree.
        """
        if type(self) is not OperationLock:
            raise OperationLockError("held operation lock must be an OperationLock instance")
        if self._fd is None:
            raise OperationLockError("operation lock instance is not acquired")
        owner_path = self._owner_path
        if owner_path is None:
            raise OperationLockError("operation lock owner file is missing")
        try:
            descriptor_stat = os.fstat(self._fd)
        except OSError as exc:
            raise OperationLockError("operation lock file descriptor is invalid") from exc
        expected = operation_lock_path(app_home).resolve()
        actual = self._path.resolve()
        if actual != expected:
            raise OperationLockError("operation lock does not belong to this app home")
        if not self._path.is_dir():
            raise OperationLockError("operation lock ownership directory is missing")
        try:
            path_stat = owner_path.stat(follow_symlinks=False)
        except OSError as exc:
            raise OperationLockError("operation lock owner file is missing") from exc
        if not os.path.samestat(descriptor_stat, path_stat):
            raise OperationLockError(
                "operation lock file descriptor no longer matches the owner path"
            )

    def acquire(self) -> None:
        if self._fd is not None:
            raise OperationLockError("operation lock already acquired in this context")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._path.mkdir()
        except FileExistsError as exc:
            raise OperationLockError("exclusive operation lock already held") from exc
        token = f"{os.getpid()}-{uuid.uuid4().hex}"
        owner_path = self._path / f"owner-{uuid.uuid4().hex}.lock"
        fd: int | None = None
        try:
            fd = os.open(str(owner_path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
            os.write(fd, token.encode("ascii"))
        except Exception:
            if fd is not None:
                os.close(fd)
            try:
                owner_path.unlink(missing_ok=True)
                self._path.rmdir()
            except OSError:
                pass
            raise
        self._owner_path = owner_path
        assert fd is not None
        self._fd = fd

    def release(self) -> None:
        if self._fd is None:
            return
        fd = self._fd
        owner_path = self._owner_path
        identity_error: OperationLockError | None = None
        try:
            if owner_path is None:
                raise OperationLockError("operation lock owner file is missing")
            descriptor_stat = os.fstat(fd)
            path_stat = owner_path.stat(follow_symlinks=False)
            if not os.path.samestat(descriptor_stat, path_stat):
                raise OperationLockError(
                    "operation lock file descriptor no longer matches the owner path"
                )
        except (OSError, OperationLockError) as exc:
            identity_error = (
                exc
                if isinstance(exc, OperationLockError)
                else OperationLockError("operation lock owner identity is unavailable")
            )
        os.close(fd)
        self._fd = None
        self._owner_path = None
        if identity_error is not None:
            # Never unlink a path that is no longer proven to be this
            # instance's owner file.
            raise identity_error
        try:
            owner_path.unlink()
            self._path.rmdir()
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
