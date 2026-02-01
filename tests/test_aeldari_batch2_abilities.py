from types import SimpleNamespace

import pytest


class _MockDatasheet:
    def __init__(self, name, *, ability_name=None, ability_desc=None, model_count=1):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Test"}
        self.keywords = ["INFANTRY"]
        self.faction_keywords = ["TEST"]
        self.datasheets_unit_composition = [{"description": f"{model_count} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{model_count} models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "3",
                "Sv": "5",
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
        if ability_desc:
            self.datasheets_abilities.append(
                {
                    "name": ability_name or name,
                    "description": ability_desc,
                    "type": "Datasheet",
                    "parameter": "",
                }
            )
        self.loadout = "This model is equipped with: nothing"
        self.attached_to = []


def _make_unit(name, *, ability_name=None, ability_desc=None, model_count=1):
    from warhammer40k_ai.units.unit import Unit

    return Unit(_MockDatasheet(name, ability_name=ability_name, ability_desc=ability_desc, model_count=model_count))


def _build_game():
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)

    army1 = Army("Army1", detachment_type="Detachment1")
    army1.faction_id = "A1"
    army2 = Army("Army2", detachment_type="Detachment2")
    army2.faction_id = "A2"

    p1 = Player("P1", control=PlayerControl.LOCAL, army=army1)
    p2 = Player("P2", control=PlayerControl.LOCAL, army=army2)
    game.add_player(p1)
    game.add_player(p2)
    return game, army1, army2


def test_extreme_mobility_ignores_vertical_distance_for_move_types():
    from warhammer40k_ai.utility.calcs import measure_path_distance

    ability = (
        "Each time this unit makes a Normal, Advance, Fall Back or Charge move, ignore any vertical distance "
        "when determining the total distance models in this unit can be moved during that move."
    )
    unit = _make_unit("Shining Spears", ability_name="Extreme Mobility", ability_desc=ability)

    path = [(0.0, 0.0, 0.0), (0.0, 6.0, 5.0)]
    for movement_type in ("move", "advance", "fall_back", "charge"):
        dist = measure_path_distance(path, unit, movement_type=movement_type)
        assert abs(dist - 6.0) < 1e-6


def test_runes_of_fortune_charge_roll_penalty():
    ability = (
        "Each time an enemy unit declares a charge, if one or more units with this ability are selected as a target "
        "of that charge, subtract 2 from the Charge roll."
    )
    target = _make_unit("Warlock", ability_name="Runes of Fortune (Psychic)", ability_desc=ability)
    charger = _make_unit("Charger")

    game, army1, army2 = _build_game()
    army1.add_unit(charger)
    army2.add_unit(target)
    game.map.units = [charger, target]

    mods = list(game.get_charge_roll_modifiers(charger, target_unit=target) or [])
    assert any(val == -2 and "Runes of Fortune" in source for val, source in mods)


def test_harassment_fire_unit_post_shoot_suppression():
    from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_POST_SHOOT_SUPPRESSION_TARGET
    from warhammer40k_ai.utility.decision_utils import resolve_decision_command

    ability = (
        "In your Shooting phase, after this unit has shot, select one enemy unit hit by one or more of those attacks. "
        "Until the start of your next turn, that enemy unit is suppressed. While a unit is suppressed, each time a model "
        "in that unit makes an attack, subtract 1 from the Hit roll."
    )
    attacker = _make_unit("Vyper", ability_name="Harassment Fire", ability_desc=ability, model_count=2)
    target = _make_unit("Target")

    game, army1, army2 = _build_game()
    army1.add_unit(attacker)
    army2.add_unit(target)
    game.map.units = [attacker, target]
    from warhammer40k_ai.engine.game import BattleRoundPhases

    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_idx = 0
    game.rebuild_entity_registry()

    game._on_unit_shooting_resolved_post_shoot_suppression(
        attacker_unit=attacker,
        hits_by_target={target: 2},
        hit_models_by_target={},
    )

    pending = list(game.decision_queue.list() or [])
    assert pending
    req = pending[0]
    assert req.decision_type == DECISION_CHOOSE_POST_SHOOT_SUPPRESSION_TARGET

    option_id = req.options[0].option_id
    resolve_decision_command(game, req, option_id, player_id=game.players[0].id)

    assert bool(target.special_rules.get("post_shoot_suppressed_active")) is True


def test_battleshock_aura_modifies_leadership_test(monkeypatch):
    ability = (
        "While an enemy unit is within 9\" of this model, subtract 1 from Battle-shock and Leadership tests taken "
        "for that unit."
    )
    aura_unit = _make_unit("Hemlock", ability_name="Mindshock Pod (Aura, Psychic)", ability_desc=ability)
    target = _make_unit("Target")

    game, army1, army2 = _build_game()
    army1.add_unit(aura_unit)
    army2.add_unit(target)
    game.map.units = [aura_unit, target]

    aura_unit.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    target.models[0].set_location(8.0, 0.0, 0.0, 0.0)

    monkeypatch.setattr("warhammer40k_ai.units.unit.get_roll", lambda _expr: 8)

    assert target.pass_leadership_check() is True

    aura_unit.models[0].set_location(20.0, 0.0, 0.0, 0.0)
    assert target.pass_leadership_check() is False
