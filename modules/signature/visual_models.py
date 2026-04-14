from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class LabelPosition(str, Enum):
    ABOVE = "above"
    BELOW = "below"
    OFF = "off"


@dataclass(frozen=True)
class SignaturePlacement:
    page_index: int = 0
    x: float = 72 * 4
    y: float = 72 * 1.5
    target_width: float = 100.0


@dataclass
class LabelOffsets:
    name_above: float = 6.0
    name_below: float = 12.0
    date_above: float = 18.0
    date_below: float = 24.0
    x_offset: float = 0.0
