"""Shared immutable model route representation."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelRoute:
    endpoint: str
    model: str
    generation: int
