"""Automation layer: generation gate, state transitions, worker flow."""

from core.automation.generation_gate import (
    evaluate_generation_eligibility,
    GateConfig,
)

__all__ = [
    "evaluate_generation_eligibility",
    "GateConfig",
]
