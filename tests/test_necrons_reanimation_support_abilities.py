from __future__ import annotations

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


THEIR_NUMBER_IS_LEGION_TEXT = (
    "Each time this unit's Reanimation Protocols activate, you can re-roll the dice to see how many wounds are reanimated."
)

NANOSCARAB_REANIMATION_BEAM_TEXT = (
    "While a friendly NECRONS unit is within 3\" of this model, each time that unit's Reanimation Protocols activate, "
    "that unit reanimates an additional D3 wounds."
)

NANOSCARAB_PROJECTOR_TEXT = (
    "Once per battle round, when a friendly NECRONS unit within 3\" of the bearer activates its Reanimation Protocols, "
    "the bearer can use this ability. If it does, that unit reanimates 1 additional wound."
)

REPAIR_BARGE_TEXT = (
    "Once per turn, just after an enemy unit finishes making its attacks, if one or more friendly NECRON WARRIORS units "
    "within 3\" of this model lost one or more wounds as a result of those attacks, this model can use this ability. If "
    "it does, select one of those NECRON WARRIORS units; that unit's Reanimation Protocols activate. The same NECRON "
    "WARRIORS unit cannot be selected for this ability more than once per turn."
)


class _MockDatasheet:
    def __init__(self, name: str, *, abilities=None, keywords=None, faction_keywords=None):
        self.name = name
        self.faction_data = {"name": "Necrons"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "4",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _ability(name: str, description: str, *, type_name: str = "Datasheet") -> dict:
    return {
        "name": name,
        "description": description,
        "type": type_name,
        "parameter": "",
    }


def _make_unit(name: str, *, abilities=None, keywords=None, faction_keywords=None) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            abilities=abilities,
            keywords=keywords,
            faction_keywords=faction_keywords,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1
    game.phase = BattleRoundPhases.SHOOTING_PHASE

    necrons = Army("Necrons", "Detachment")
    necrons.faction_id = "NEC"
    enemy = Army("Enemy", "Detachment")
    enemy.faction_id = "EN"

    p1 = Player("Necron Player", control=PlayerControl.REMOTE, army=necrons)
    p2 = Player("Enemy Player", control=PlayerControl.REMOTE, army=enemy)
    game.add_player(p1)
    game.add_player(p2)
    return game, necrons, enemy, p1, p2


def _deploy(unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    set_reserve_status = getattr(unit, "set_reserve_status", None)
    if callable(set_reserve_status):
        set_reserve_status("deployed")
    else:
        unit.reserve_status = "deployed"
    unit.models[0].set_location(float(x), float(y), 0.0, 0.0)


def _find_repair_barge_request(game: Game):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        ctx = dict(getattr(request, "context", {}) or {})
        if str(ctx.get("ability", "") or "") != "repair_barge":
            continue
        return request
    return None


def _target_option_id(request, unit: Unit) -> str:
    target_id = str(get_entity_id(unit.get_attached_unit_root()) or "")
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("target_unit_id", "") or "") == target_id:
            return str(option.option_id)
    return ""


def test_their_number_is_legion_rerolls_reanimation_roll(monkeypatch):
    game, necrons, _enemy, _p1, _p2 = _build_game()
    warriors = _make_unit(
        "Necron Warriors",
        abilities=[
            _ability("Reanimation Protocols", "Reanimation Protocols."),
            _ability("Their Number is Legion", THEIR_NUMBER_IS_LEGION_TEXT),
        ],
        keywords=["NECRONS", "INFANTRY", "WARRIORS"],
        faction_keywords=["NECRONS"],
    )
    necrons.add_unit(warriors)
    _deploy(warriors, 0.0, 0.0)
    game.map.units = [warriors]
    game.rebuild_entity_registry()

    warriors.models[0].wounds = 1
    monkeypatch.setattr("warhammer40k_ai.units.unit.get_roll", lambda _spec: 3)
    result = warriors.apply_reanimation_protocols(1, roll_expr="D3", game_map=game.map, is_human=False, provider=None)

    assert int(result["healed"]) == 3
    assert int(warriors.models[0].wounds) == int(getattr(warriors.models[0], "_base_wounds", warriors.models[0].wounds))


def test_nanoscarab_reanimation_beam_adds_extra_d3(monkeypatch):
    game, necrons, _enemy, _p1, _p2 = _build_game()
    reanimator = _make_unit(
        "Canoptek Reanimator",
        abilities=[_ability("Nanoscarab Reanimation Beam (Aura)", NANOSCARAB_REANIMATION_BEAM_TEXT)],
        keywords=["NECRONS", "VEHICLE"],
        faction_keywords=["NECRONS"],
    )
    warriors = _make_unit(
        "Necron Warriors",
        abilities=[_ability("Reanimation Protocols", "Reanimation Protocols.")],
        keywords=["NECRONS", "INFANTRY", "WARRIORS"],
        faction_keywords=["NECRONS"],
    )
    necrons.add_unit(reanimator)
    necrons.add_unit(warriors)
    _deploy(reanimator, 0.0, 0.0)
    _deploy(warriors, 2.0, 0.0)
    game.map.units = [reanimator, warriors]
    game.rebuild_entity_registry()

    warriors.models[0].wounds = 1
    monkeypatch.setattr("warhammer40k_ai.units.unit.get_roll", lambda _spec: 2)
    result = warriors.apply_reanimation_protocols(1, roll_expr="D3", game_map=game.map, is_human=False, provider=None)

    assert int(result["healed"]) == 3
    assert int(warriors.models[0].wounds) == int(getattr(warriors.models[0], "_base_wounds", warriors.models[0].wounds))


def test_nanoscarab_projector_applies_once_per_battle_round():
    game, necrons, _enemy, _p1, _p2 = _build_game()
    bearer = _make_unit(
        "Technomancer",
        abilities=[_ability("Nanoscarab Projector", NANOSCARAB_PROJECTOR_TEXT)],
        keywords=["NECRONS", "INFANTRY", "CHARACTER"],
        faction_keywords=["NECRONS"],
    )
    warriors = _make_unit(
        "Necron Warriors",
        abilities=[_ability("Reanimation Protocols", "Reanimation Protocols.")],
        keywords=["NECRONS", "INFANTRY", "WARRIORS"],
        faction_keywords=["NECRONS"],
    )
    necrons.add_unit(bearer)
    necrons.add_unit(warriors)
    _deploy(bearer, 0.0, 0.0)
    _deploy(warriors, 2.0, 0.0)
    game.map.units = [bearer, warriors]
    game.rebuild_entity_registry()

    warriors.models[0].wounds = 1
    first = warriors.apply_reanimation_protocols(1, roll_expr="D3", game_map=game.map, is_human=False, provider=None)
    assert int(first["healed"]) == 2
    assert bool(bearer.models[0].has_used_once_per_battle_round("nanoscarab_projector"))

    warriors.models[0].wounds = 1
    second = warriors.apply_reanimation_protocols(1, roll_expr="D3", game_map=game.map, is_human=False, provider=None)
    assert int(second["healed"]) == 1


def test_repair_barge_queues_and_activates_reanimation(monkeypatch):
    game, necrons, enemy, p1, p2 = _build_game()
    game.current_player_index = 1  # Enemy turn

    ghost_ark = _make_unit(
        "Ghost Ark",
        abilities=[_ability("Repair Barge", REPAIR_BARGE_TEXT)],
        keywords=["NECRONS", "VEHICLE"],
        faction_keywords=["NECRONS"],
    )
    warriors = _make_unit(
        "Necron Warriors",
        abilities=[_ability("Reanimation Protocols", "Reanimation Protocols.")],
        keywords=["NECRONS", "INFANTRY", "WARRIORS"],
        faction_keywords=["NECRONS"],
    )
    enemy_unit = _make_unit(
        "Enemy Shooters",
        abilities=[],
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )

    necrons.add_unit(ghost_ark)
    necrons.add_unit(warriors)
    enemy.add_unit(enemy_unit)
    _deploy(ghost_ark, 0.0, 0.0)
    _deploy(warriors, 2.0, 0.0)
    _deploy(enemy_unit, 12.0, 0.0)
    game.map.units = [ghost_ark, warriors, enemy_unit]
    game.rebuild_entity_registry()

    game.event_system.publish(
        "shooting_targets_selected",
        attacking_unit=enemy_unit,
        target_units=[warriors],
    )
    warriors.models[0].wounds = 2
    game.event_system.publish(
        "unit_shooting_resolved",
        attacker_unit=enemy_unit,
        hits_by_target={warriors: 1},
    )

    request = _find_repair_barge_request(game)
    assert request is not None
    option_id = _target_option_id(request, warriors)
    assert option_id

    invalid = resolve_decision_command(game, request, "invalid-option-id", player_id=p1.id)
    assert not bool(getattr(invalid, "ok", False))

    request = _find_repair_barge_request(game)
    assert request is not None
    monkeypatch.setattr("warhammer40k_ai.utility.dice.get_roll", lambda _spec: 2)
    result = resolve_decision_command(game, request, option_id, player_id=p1.id)
    assert bool(getattr(result, "ok", False))
    assert int(warriors.models[0].wounds) == int(getattr(warriors.models[0], "_base_wounds", warriors.models[0].wounds))

    sr_source = dict(getattr(ghost_ark, "special_rules", {}) or {})
    used_by_model = dict(sr_source.get("repair_barge_model_used_turn_by_id", {}) or {})
    assert str(get_entity_id(ghost_ark.models[0]) or "") in used_by_model

    sr_target = dict(getattr(warriors, "special_rules", {}) or {})
    assert int(sr_target.get("repair_barge_selected_turn", -1)) == int(game.turn)
    assert str(sr_target.get("repair_barge_selected_turn_owner", "") or "") == str(p2.id)

    warriors.models[0].wounds = 1
    game.event_system.publish(
        "shooting_targets_selected",
        attacking_unit=enemy_unit,
        target_units=[warriors],
    )
    game.event_system.publish(
        "unit_shooting_resolved",
        attacker_unit=enemy_unit,
        hits_by_target={warriors: 1},
    )
    assert _find_repair_barge_request(game) is None
