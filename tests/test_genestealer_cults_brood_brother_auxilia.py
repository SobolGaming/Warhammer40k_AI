from __future__ import annotations

from types import SimpleNamespace

import pytest

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army, ArmyValidationError
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.voice_of_command import VoiceOfCommandManager
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str,
        keywords: list[str] | None = None,
        faction_keywords: list[str] | None = None,
        points: int = 100,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": int(points)}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "4",
                "W": "2",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str,
    keywords: list[str] | None = None,
    faction_keywords: list[str] | None = None,
    points: int = 100,
    possible_abilities: list[str] | None = None,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            points=points,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    if possible_abilities:
        unit.possible_abilities = list(possible_abilities)
    return unit


def _build_game(
    detachment: str = "Brood Brother Auxilia",
    *,
    points_limit: int = 2000,
) -> tuple[Game, Army, Army, Player, Player]:
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    gsc_army = Army("Genestealer Cults", detachment, points_limit=points_limit)
    gsc_army.faction_id = "GC"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    p1 = Player("GSC", control=PlayerControl.REMOTE, army=gsc_army)
    p2 = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)
    return game, gsc_army, enemy_army, p1, p2


def _get_integrated_tactics_request(game: Game):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "") == "integrated_tactics":
            return req
    return None


def _target_option_id(request, target_unit: Unit | None) -> str:
    target_id = str(get_entity_id(target_unit) or "") if target_unit is not None else ""
    for opt in list(getattr(request, "options", []) or []):
        payload = dict(getattr(opt, "payload", {}) or {})
        if target_unit is None:
            if str(payload.get("action", "") or "") == "skip":
                return str(getattr(opt, "option_id", "") or "")
            continue
        if str(payload.get("target_unit_id", "") or "") == target_id:
            return str(getattr(opt, "option_id", "") or "")
    return ""


def test_integrated_tactics_queues_optional_choice_and_skip_clears_source_lock():
    game, gsc_army, enemy_army, gsc_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.turn = 2
    game.current_player_index = 0

    source = _make_unit(
        "Brood Brothers Squad",
        faction_name="Astra Militarum",
        keywords=["ASTRA MILITARUM", "INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    target_one = _make_unit("Enemy One", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    target_two = _make_unit("Enemy Two", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    gsc_army.add_unit(source)
    enemy_army.add_unit(target_one)
    enemy_army.add_unit(target_two)

    mgr = gsc_army.genestealer_cults_detachments
    mgr.integrated_tactics_target_candidates_for_unit = lambda *_args, **_kwargs: [target_one, target_two]
    mgr.integrated_tactics_target_eligible = lambda *_args, **_kwargs: True

    game._on_shooting_targets_selected_integrated_tactics(attacking_unit=source, target_units=[target_one, target_two])
    request = _get_integrated_tactics_request(game)
    assert request is not None
    assert bool((request.context or {}).get("optional")) is True
    assert str((request.context or {}).get("unit_id", "") or "") == str(get_entity_id(source) or "")

    target_option = _target_option_id(request, target_one)
    assert target_option
    resolve_decision_command(game, request, target_option, player_id=gsc_player.id)

    sr = dict(getattr(source, "special_rules", {}) or {})
    assert bool(sr.get("gsc_integrated_tactics_active")) is True
    assert str(sr.get("gsc_integrated_tactics_target_unit_id", "") or "") == str(get_entity_id(target_one) or "")

    game._on_shooting_targets_selected_integrated_tactics(attacking_unit=source, target_units=[target_one, target_two])
    request_skip = _get_integrated_tactics_request(game)
    assert request_skip is not None
    skip_option = _target_option_id(request_skip, None)
    assert skip_option
    resolve_decision_command(game, request_skip, skip_option, player_id=gsc_player.id)

    sr_after = dict(getattr(source, "special_rules", {}) or {})
    assert bool(sr_after.get("gsc_integrated_tactics_active")) is False
    assert str(sr_after.get("gsc_integrated_tactics_target_unit_id", "") or "") == ""


def test_integrated_tactics_target_lock_and_hit_bonus_apply_for_gsc_ranged_attacks():
    game, gsc_army, enemy_army, gsc_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.turn = 2
    game.current_player_index = 0

    source = _make_unit(
        "Brood Brothers Squad",
        faction_name="Astra Militarum",
        keywords=["ASTRA MILITARUM", "INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    gsc_attacker = _make_unit(
        "Neophyte Hybrids",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    locked_target = _make_unit("Locked Target", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    other_target = _make_unit("Other Target", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    gsc_army.add_unit(source)
    gsc_army.add_unit(gsc_attacker)
    enemy_army.add_unit(locked_target)
    enemy_army.add_unit(other_target)

    mgr = gsc_army.genestealer_cults_detachments
    outcome = mgr.apply_integrated_tactics_choice(
        source,
        target_unit=locked_target,
        game=None,
        player=gsc_player,
    )
    assert isinstance(outcome, dict)
    assert bool(mgr.integrated_tactics_target_locked_to(source, locked_target, game=game)) is True
    assert bool(mgr.integrated_tactics_target_locked_to(source, other_target, game=game)) is False

    bonus, source_name = mgr.integrated_tactics_hit_bonus(gsc_attacker.models[0], locked_target, game=game)
    assert int(bonus or 0) == 1
    assert "integrated tactics" in str(source_name or "").lower()

    am_bonus, _am_source_name = mgr.integrated_tactics_hit_bonus(source.models[0], locked_target, game=game)
    assert int(am_bonus or 0) == 0

    melee_profile = SimpleNamespace(is_melee=lambda: True)
    melee_bonus, _ = mgr.integrated_tactics_hit_bonus(
        gsc_attacker.models[0],
        locked_target,
        game=game,
        weapon_profile=melee_profile,
    )
    assert int(melee_bonus or 0) == 0

    game._on_phase_end_cleanup(player=gsc_player, phase=BattleRoundPhases.SHOOTING_PHASE)
    sr_after = dict(getattr(source, "special_rules", {}) or {})
    target_sr_after = dict(getattr(locked_target, "special_rules", {}) or {})
    assert bool(sr_after.get("gsc_integrated_tactics_active")) is False
    assert str(sr_after.get("gsc_integrated_tactics_target_unit_id", "") or "") == ""
    assert bool(target_sr_after.get("gsc_integrated_tactics_overlapping_fire_active")) is False


def test_brood_brothers_validation_enforces_cap_forbidden_units_and_warlord():
    game, gsc_army, enemy_army, _gsc_player, _enemy_player = _build_game(points_limit=1000)
    del game, enemy_army

    invalid_am_unit = _make_unit(
        "Brood Brothers Valkyrie",
        faction_name="Astra Militarum",
        keywords=["ASTRA MILITARUM", "AIRCRAFT"],
        faction_keywords=["ASTRA MILITARUM"],
        points=600,
    )
    gsc_unit = _make_unit(
        "Acolyte Hybrids",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    gsc_army.add_unit(invalid_am_unit)
    gsc_army.add_unit(gsc_unit)
    gsc_army.warlord = invalid_am_unit

    mgr = gsc_army.genestealer_cults_detachments
    errors = list(mgr.validate_detachment_rules() or [])
    text = "\n".join(str(msg or "") for msg in errors)
    assert "AIRCRAFT" in text
    assert "Incursion cap of 500" in text
    assert "must be your WARLORD" in text

    with pytest.raises(ArmyValidationError):
        gsc_army.validate_detachment_rules()


def test_brood_brothers_voice_of_command_loss_flags_units_and_disables_voice_check():
    _game, gsc_army, _enemy_army, _gsc_player, _enemy_player = _build_game()

    officer = _make_unit(
        "Brood Brothers Commander",
        faction_name="Astra Militarum",
        keywords=["ASTRA MILITARUM", "OFFICER", "INFANTRY"],
        faction_keywords=["ASTRA MILITARUM"],
        possible_abilities=["Voice of Command"],
    )
    gsc_unit = _make_unit(
        "Acolyte Hybrids",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    gsc_army.add_unit(officer)
    gsc_army.add_unit(gsc_unit)
    gsc_army.warlord = gsc_unit

    sr = dict(getattr(officer, "special_rules", {}) or {})
    sr["voice_of_command_order_key"] = "test_order"
    sr["voice_of_command_order_owner"] = "owner"
    sr["voice_of_command_order_source"] = "source"
    officer.special_rules = sr
    removed_sources: list[str] = []
    officer.remove_characteristic_modifiers_by_source = lambda source: removed_sources.append(str(source or ""))

    voc = VoiceOfCommandManager(gsc_army)
    assert bool(voc._unit_has_voice(officer)) is True

    mgr = gsc_army.genestealer_cults_detachments
    mgr.apply_brood_brothers_voice_of_command_loss()
    updated_sr = dict(getattr(officer, "special_rules", {}) or {})

    assert bool(updated_sr.get("gsc_brood_brothers_voice_of_command_lost")) is True
    assert "voice_of_command_order_key" not in updated_sr
    assert "voice_of_command_order_owner" not in updated_sr
    assert "voice_of_command_order_source" not in updated_sr
    assert removed_sources == ["voice_of_command:"]
    assert bool(voc._unit_has_voice(officer)) is False
