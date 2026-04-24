from __future__ import annotations

from typing import Optional
import logging

from .event_bus import append_action

logger = logging.getLogger(__name__)


def _resolve_unit_root(unit) -> Optional[object]:
    if unit is None:
        return None
    try:
        root = unit.get_attached_unit_root()
    except AttributeError:
        root = unit
    return root


def _bump_effect_generation(root: object, reason: str, *, player: object = None, game: object = None) -> None:
    if game is not None:
        game_map = getattr(game, "map", None)
        bump = getattr(game_map, "bump_state_generation", None)
        if callable(bump):
            bump(reason)
            return
    if player is not None:
        game = getattr(player, "game", None)
        game_map = getattr(game, "map", None)
        bump = getattr(game_map, "bump_state_generation", None)
        if callable(bump):
            bump(reason)
            return
    get_army = getattr(root, "get_parent_army", None)
    army = get_army() if callable(get_army) else getattr(root, "parent_army", None)
    player = getattr(army, "player", None)
    game = getattr(player, "game", None)
    game_map = getattr(game, "map", None)
    bump = getattr(game_map, "bump_state_generation", None)
    if callable(bump):
        bump(reason)


def apply_flickering_reality_effect(
    unit,
    roll: int,
    *,
    game=None,
    player=None,
    source: str = "Flickering Reality",
) -> Optional[object]:
    root = _resolve_unit_root(unit)
    if root is None:
        return None
    if player is None:
        try:
            player = root.get_parent_army().player
        except AttributeError:
            player = None
    if game is None and player is not None:
        try:
            game = getattr(player, "game", None)
        except AttributeError:
            game = None

    sr = getattr(root, "special_rules", None)
    if not isinstance(sr, dict):
        sr = {}
    try:
        roll_val = int(roll)
    except (TypeError, ValueError):
        logger.warning("Invalid Flickering Reality roll %r; coercing to 0.", roll, exc_info=True)
        roll_val = int(roll or 0)
    sr["flickering_reality_active"] = True
    sr["flickering_reality_hit_roll"] = roll_val
    sr["flickering_reality_expires_phase"] = "FIGHT_PHASE"
    try:
        sr["flickering_reality_turn_owner"] = str(getattr(player, "id", "") or "")
        sr["flickering_reality_turn"] = int(getattr(game, "turn", 0) or 0) if game is not None else 0
    except (TypeError, ValueError, AttributeError):
        logger.warning("Failed to annotate Flickering Reality timing metadata.", exc_info=True)
    sr["flickering_reality_source"] = str(source or "Flickering Reality").strip() or "Flickering Reality"
    root.special_rules = sr
    _bump_effect_generation(root, "active_rule_effect_changed", player=player, game=game)
    if player is not None:
        try:
            append_action(player, f"{root.name}: Flickering Reality active (hits on {roll_val} end attacks).")
        except (AttributeError, TypeError):
            logger.warning("Failed to append Flickering Reality action log.", exc_info=True)
    return root


def apply_pyrogenesis_effect(
    unit,
    strength_bonus: int,
    ap_bonus: int,
    *,
    phase_key: str,
    game=None,
    player=None,
    source: str = "Pyrogenesis",
) -> Optional[object]:
    root = _resolve_unit_root(unit)
    if root is None:
        return None
    if player is None:
        try:
            player = root.get_parent_army().player
        except AttributeError:
            player = None
    if game is None and player is not None:
        try:
            game = getattr(player, "game", None)
        except AttributeError:
            game = None

    sr = getattr(root, "special_rules", None)
    if not isinstance(sr, dict):
        sr = {}
    try:
        s_bonus = int(strength_bonus)
    except (TypeError, ValueError):
        logger.warning("Invalid Pyrogenesis strength bonus %r; coercing to 0.", strength_bonus, exc_info=True)
        s_bonus = int(strength_bonus or 0)
    try:
        a_bonus = int(ap_bonus)
    except (TypeError, ValueError):
        logger.warning("Invalid Pyrogenesis AP bonus %r; coercing to 0.", ap_bonus, exc_info=True)
        a_bonus = int(ap_bonus or 0)
    sr["pyrogenesis_active"] = True
    sr["pyrogenesis_strength_bonus"] = s_bonus
    sr["pyrogenesis_ap_bonus"] = a_bonus
    sr["pyrogenesis_expires_phase"] = str(phase_key or "").strip().upper() or "SHOOTING_PHASE"
    try:
        sr["pyrogenesis_turn_owner"] = str(getattr(player, "id", "") or "")
        sr["pyrogenesis_turn"] = int(getattr(game, "turn", 0) or 0) if game is not None else 0
    except (TypeError, ValueError, AttributeError):
        logger.warning("Failed to annotate Pyrogenesis timing metadata.", exc_info=True)
    sr["pyrogenesis_source"] = str(source or "Pyrogenesis").strip() or "Pyrogenesis"
    root.special_rules = sr
    _bump_effect_generation(root, "active_rule_effect_changed", player=player, game=game)
    if player is not None:
        try:
            if a_bonus:
                append_action(player, f"{root.name}: Pyrogenesis active (+{s_bonus}S, AP improved by {a_bonus}).")
            else:
                append_action(player, f"{root.name}: Pyrogenesis active (+{s_bonus}S).")
        except (AttributeError, TypeError):
            logger.warning("Failed to append Pyrogenesis action log.", exc_info=True)
    return root
