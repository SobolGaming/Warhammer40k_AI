from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

DecisionProvider = Callable[..., Any]

DECISION_PROVIDER_NAMES: tuple[str, ...] = (
    "precision_allocation_provider",
    "damage_allocation_provider",
    "hazardous_allocation_provider",
    "reanimation_allocation_provider",
    "bodyguard_loss_provider",
    "roll_reroll_provider",
    "miracle_dice_provider",
    "miracle_dice_pool_reroll_provider",
    "aspect_shrine_provider",
    "leading_unmodified_six_provider",
    "model_unmodified_six_provider",
    "model_allocated_damage_zero_provider",
    "unit_mortal_wound_fnp_provider",
    "unit_psychic_attack_fnp_provider",
    "death_vision_of_sanguinius_provider",
    "hit_modifier_choice_provider",
    "skill_modifier_choice_provider",
    "move_modifier_choice_provider",
    "advance_modifier_choice_provider",
    "charge_modifier_choice_provider",
)


@dataclass
class DecisionPort:
    """Runtime-owned provider registry for human/AI/network choice hooks."""

    providers: dict[str, DecisionProvider | None] = field(default_factory=dict)

    def set_provider(self, name: str, provider: DecisionProvider | None) -> None:
        provider_name = _normalize_provider_name(name)
        self.providers[provider_name] = provider

    def get_provider(self, name: str) -> DecisionProvider | None:
        provider_name = _normalize_provider_name(name)
        return self.providers.get(provider_name)

    def install(self, providers: Mapping[str, DecisionProvider | None]) -> None:
        for name, provider in dict(providers or {}).items():
            self.set_provider(name, provider)

    def to_dict(self) -> dict[str, bool]:
        return {
            name: callable(provider)
            for name, provider in sorted(self.providers.items(), key=lambda item: item[0])
        }


def get_decision_provider(
    game: object | None,
    name: str,
    *,
    game_map: object | None = None,
) -> DecisionProvider | None:
    """Resolve a runtime decision provider from Game.decision_port only."""
    provider_name = _normalize_provider_name(name)
    resolved_game = game
    if resolved_game is None and game_map is not None:
        resolved_game = getattr(game_map, "game", None)
    return _provider_from_game(resolved_game, provider_name)


def _provider_from_game(game: object | None, provider_name: str) -> DecisionProvider | None:
    port = getattr(game, "decision_port", None) if game is not None else None
    getter = getattr(port, "get_provider", None)
    if not callable(getter):
        return None
    provider = getter(provider_name)
    return provider if callable(provider) else None


def _normalize_provider_name(name: str) -> str:
    provider_name = str(name or "").strip()
    if provider_name not in DECISION_PROVIDER_NAMES:
        raise ValueError(f"Unknown decision provider: {provider_name!r}")
    return provider_name
