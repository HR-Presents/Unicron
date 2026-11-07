"""Curated model candidates with approximate GPU memory estimates."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelCandidate:
    model_id: str
    runtime: str
    parameters_b: float
    bits_per_weight: int
    served_name: str | None = None

    @property
    def estimated_vram_gib(self) -> float:
        weights = self.parameters_b * self.bits_per_weight / 8
        return round(weights * 1.15 + 1.5, 2)


CATALOG = (
    ModelCandidate("Qwen/Qwen3-1.7B", "vllm", 1.7, 16, "unicron-qwen"),
    ModelCandidate("Qwen/Qwen3-4B", "vllm", 4.0, 16),
    ModelCandidate("Qwen/Qwen3-8B", "llama_cpp", 8.0, 4),
)
