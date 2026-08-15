from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import AbstractContextManager


class ContainerRepository(ABC):
    @abstractmethod
    def transaction(self) -> AbstractContextManager:
        raise NotImplementedError
