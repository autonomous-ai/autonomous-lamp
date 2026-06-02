"""Data models for perception processors."""

from dataclasses import dataclass
from enum import StrEnum

import numpy as np
import numpy.typing as npt


class FireHazardEnum(StrEnum):
    SMOKE = "smoke"
    FIRE = "fire"
    FIRE_ON_FURNITURE = "fire_on_furniture"
    SAFE = "safe"


@dataclass
class FireHazard:
    type: FireHazardEnum
    bbox: npt.NDArray[np.float32]
