from __future__ import annotations

from unittest.mock import patch

from warhammer40k_ai.engine.decision_handlers.movement import _apply_select_movement_action
from warhammer40k_ai.engine.decision_kinds import DECISION_SELECT_MOVEMENT_ACTION
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(self, name: str, *, abilities=None, wargear=None, options=None, loadout: str | None = None):
        self.name = name
        self.faction_data = {"name": "Imperial Knights"}
        self.keywords = ["VEHICLE", "WALKER"]
        self.faction_keywords = ["IMPERIAL KNIGHTS"]
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 400}]
        self.datasheets_models = [
            {
                "M": "12",
                "T": "12",
                "Sv": "3",
                "W": "20",
                "Ld": "7",
                "OC": "8",
                "base_size": "100mm",
                "inv_sv": "5",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = list(wargear or [])
        self.datasheets_options = list(options or [{"description": "none"}])
        self.datasheets_abilities = list(abilities or [])
        self.loadout = loadout or "This model is equipped with: nothing"
        self.transport = ""


def _ram_jets_ability():
    return {
        "name": "Ram Jets",
        "description": (
            "Each time this unit is selected to make a Normal or Advance move, until the end of the phase, "
            'add D3" to the Move characteristic of this model.'
        ),
        "type": "Datasheet",
        "parameter": "",
    }


def _thundercharge_ability():
    return {
        "name": "Thundercharge",
        "description": (
            "If this model is equipped with a thundershock spear and a bellatus reaper chainsword, add 2 to "
            "the Attacks characteristic of melee weapons equipped by this model."
        ),
        "type": "Datasheet",
        "parameter": "",
    }


def _make_unit(name: str = "Knight Destrier", *, abilities=None) -> Unit:
    return Unit(_MockDatasheet(name, abilities=abilities))


def _make_mock_wargear_entry(name: str, *, wargear_type: str, range_value: str, attacks: str, bs_ws: str, strength: str, ap: str, damage: str, description: str = "") -> dict:
    return {
        "name": name,
        "type": wargear_type,
        "range": range_value,
        "A": attacks,
        "BS_WS": bs_ws,
        "S": strength,
        "AP": ap,
        "D": damage,
        "description": description,
    }


def _make_destrier_wargear_unit() -> Unit:
    return Unit(
        _MockDatasheet(
            "Knight Destrier",
            wargear=[
                _make_mock_wargear_entry(
                    "Chastiser gatling cannon",
                    wargear_type="Ranged",
                    range_value="24",
                    attacks="12",
                    bs_ws="3+",
                    strength="6",
                    ap="-1",
                    damage="2",
                    description="assault",
                ),
                _make_mock_wargear_entry(
                    "Frag bombard",
                    wargear_type="Ranged",
                    range_value="24",
                    attacks="D6+3",
                    bs_ws="3+",
                    strength="5",
                    ap="0",
                    damage="1",
                    description="assault, blast, rapid fire d6+3",
                ),
                _make_mock_wargear_entry(
                    "Questoris heavy stubber",
                    wargear_type="Ranged",
                    range_value="36",
                    attacks="3",
                    bs_ws="3+",
                    strength="4",
                    ap="0",
                    damage="1",
                    description="assault, rapid fire 3",
                ),
                _make_mock_wargear_entry(
                    "Bellatus reaper chainsword",
                    wargear_type="Melee",
                    range_value="Melee",
                    attacks="5",
                    bs_ws="3+",
                    strength="12",
                    ap="-3",
                    damage="D3+3",
                ),
                _make_mock_wargear_entry(
                    "Thundershock spear",
                    wargear_type="Melee",
                    range_value="Melee",
                    attacks="4",
                    bs_ws="3+",
                    strength="12",
                    ap="-3",
                    damage="D3+3",
                    description="lance",
                ),
            ],
            options=[
                {
                    "description": (
                        "This model’s chastiser gatling cannon can be replaced with one of the following:"
                        '<br><ul style="list-style-type:circle"><li>1 bellatus reaper chainsword*</li>'
                        "<li>1 thundershock spear*</li></ul>"
                    )
                },
                {
                    "description": (
                        "This model’s frag bombard can be replaced with one of the following:"
                        '<br><ul style="list-style-type:circle"><li>1 bellatus reaper chainsword*</li>'
                        "<li>1 thundershock spear*</li></ul>"
                    )
                },
                {
                    "description": (
                        "* A model cannot be equipped with more than one bellatus reaper chainsword or more than one "
                        "thundershock spear."
                    )
                },
            ],
            loadout=(
                "This model is equipped with: chastiser gatling cannon; frag bombard; "
                "questoris heavy stubber."
            ),
        )
    )


def _setup_game(unit: Unit) -> tuple[Game, Player]:
    ik_army = Army.with_detachment("Imperial Knights", detachment_type="Other")
    ik_army.faction_id = "IK"
    enemy_army = Army.with_detachment("Enemies", detachment_type="Other")
    enemy_army.faction_id = "SM"
    ik_player = Player("Knight", PlayerControl.REMOTE, army=ik_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[ik_player, enemy_player])
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game.current_player_index = 0
    unit.parent_army = ik_army
    ik_army.units = [unit]
    enemy_army.units = []
    game.map.units = [unit]
    game.rebuild_entity_registry()
    return game, ik_player


def _movement_request(unit: Unit, player: Player, *, action_type: str) -> tuple[DecisionRequest, DecisionResult]:
    option = DecisionOption.create(
        action_type.title(),
        payload={"unit_id": get_entity_id(unit), "action_type": action_type},
    )
    request = DecisionRequest.create(
        DECISION_SELECT_MOVEMENT_ACTION,
        "Select movement action",
        player_id=player.id,
        options=[option],
        context={"unit_id": get_entity_id(unit)},
    )
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=player.id,
        option_id=option.option_id,
        payload={},
    )
    return request, result


def _make_melee_wargear(name: str, *, attacks: str, strength: str, ap: str, damage: str, description: str = "") -> Wargear:
    return Wargear(
        {
            "name": name,
            "type": "Melee",
            "range": "Melee",
            "A": attacks,
            "BS_WS": "3+",
            "S": strength,
            "AP": ap,
            "D": damage,
            "description": description,
        }
    )


def test_ram_jets_applies_move_bonus_when_selected_to_move() -> None:
    unit = _make_unit(abilities=[_ram_jets_ability()])
    model = unit.models[0]
    game, player = _setup_game(unit)
    request, result = _movement_request(unit, player, action_type="move")

    with patch("warhammer40k_ai.engine.decision_handlers.movement.get_roll", return_value=2):
        _apply_select_movement_action(game, request, result)

    assert model.get_temporary_movement_bonus() == 2
    effect = next(
        (
            entry
            for key, entry in list(getattr(model, "_temporary_effects", {}).items())
            if str(key or "").startswith("selected_move_characteristic_bonus:")
        ),
        None,
    )
    assert isinstance(effect, dict)
    assert effect.get("expires_phase") == "MOVEMENT_PHASE"


def test_ram_jets_applies_before_prepare_advance() -> None:
    unit = _make_unit(abilities=[_ram_jets_ability()])
    model = unit.models[0]
    game, player = _setup_game(unit)
    request, result = _movement_request(unit, player, action_type="advance")
    captured: dict[str, int] = {}

    def _prepare_advance() -> int:
        captured["bonus"] = int(model.get_temporary_movement_bonus() or 0)
        return 6

    unit.prepare_advance = _prepare_advance

    with patch("warhammer40k_ai.engine.decision_handlers.movement.get_roll", return_value=3):
        _apply_select_movement_action(game, request, result)

    assert captured["bonus"] == 3
    assert model.get_temporary_movement_bonus() == 3


def test_thundercharge_adds_attacks_to_all_melee_weapons_when_both_named_weapons_are_equipped() -> None:
    unit = _make_unit(abilities=[_thundercharge_ability()])
    attacker = unit.models[0]
    attacker.set_location(0.0, 0.0, 0.0, 0.0)

    target = _make_unit("Target")
    target.models[0].set_location(1.0, 0.0, 0.0, 0.0)

    chainsword = _make_melee_wargear(
        "Bellatus reaper chainsword - strike",
        attacks="5",
        strength="12",
        ap="-3",
        damage="D3+3",
    )
    chainsword.add_profile(
        "sweep",
        {
            "name": "Bellatus reaper chainsword - sweep",
            "type": "Melee",
            "range": "Melee",
            "A": "10",
            "BS_WS": "3+",
            "S": "8",
            "AP": "-2",
            "D": "2",
            "description": "",
        },
    )
    spear = _make_melee_wargear(
        "Thundershock spear - strike",
        attacks="4",
        strength="12",
        ap="-3",
        damage="D3+3",
        description="lance",
    )
    feet = _make_melee_wargear(
        "Titanic feet",
        attacks="4",
        strength="7",
        ap="-1",
        damage="2",
    )
    attacker.wargear = [chainsword, spear, feet]

    chainsword_profile = chainsword.profiles["strike"]
    spear_profile = spear.profiles["strike"]
    feet_profile = next(iter(feet.profiles.values()))

    assert int(chainsword_profile.preview_attack_count(target, attacker, publish_roll_event=False).num_attacks) == 7
    assert int(spear_profile.preview_attack_count(target, attacker, publish_roll_event=False).num_attacks) == 6
    assert int(feet_profile.preview_attack_count(target, attacker, publish_roll_event=False).num_attacks) == 6


def test_thundercharge_requires_both_named_weapons() -> None:
    unit = _make_unit(abilities=[_thundercharge_ability()])
    attacker = unit.models[0]
    attacker.wargear = [
        _make_melee_wargear("Thundershock spear - strike", attacks="4", strength="12", ap="-3", damage="D3+3"),
        _make_melee_wargear("Titanic feet", attacks="4", strength="7", ap="-1", damage="2"),
    ]

    bonus, reasons = unit.get_equipped_wargear_melee_attacks_bonus(attacker)

    assert bonus == 0
    assert reasons == []


def test_destrier_wargear_footnote_blocks_duplicate_melee_replacement_without_losing_original_weapon() -> None:
    unit = _make_destrier_wargear_unit()
    model = unit.models[0]

    assert unit._wargear_constraints["max_counts"]["bellatus reaper chainsword"] == 1
    assert unit._wargear_constraints["max_counts"]["thundershock spear"] == 1

    first_option, second_option = unit.wargear_options
    unit.apply_wargear_option(first_option)
    unit.apply_wargear_option(second_option)

    equipped_names = [str(getattr(wg, "name", "") or "").lower() for wg in list(model.wargear or [])]

    assert equipped_names.count("bellatus reaper chainsword") == 1
    assert "frag bombard" in equipped_names
    assert "chastiser gatling cannon" not in equipped_names


def test_destrier_wargear_footnote_allows_one_bellatus_and_one_thundershock() -> None:
    unit = _make_destrier_wargear_unit()
    model = unit.models[0]

    first_option, second_option = unit.wargear_options
    unit.apply_wargear_option(first_option)
    second_option.wargear_to = [list(second_option.wargear_to[1])]
    unit.apply_wargear_option(second_option)

    equipped_names = [str(getattr(wg, "name", "") or "").lower() for wg in list(model.wargear or [])]

    assert equipped_names.count("bellatus reaper chainsword") == 1
    assert equipped_names.count("thundershock spear") == 1
    assert "frag bombard" not in equipped_names
    assert "chastiser gatling cannon" not in equipped_names
