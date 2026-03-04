from __future__ import annotations

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.rules.stratagems import Stratagem
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(self, name: str, *, faction_name: str, keywords=None, faction_keywords=None):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "10",
                "T": "10",
                "Sv": "3",
                "W": "12",
                "Ld": "6",
                "OC": "8",
                "base_size": "100mm",
                "inv_sv": "5",
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


def _make_unit(name: str, *, keywords=None, faction_keywords=None) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name="Imperial Knights",
            keywords=keywords,
            faction_keywords=faction_keywords,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game(detachment_type: str):
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1
    army_ik = Army("Imperial Knights", detachment_type)
    army_ik.faction_id = "QI"
    army_enemy = Army("Enemy", "Other")
    army_enemy.faction_id = "EN"
    ik_player = Player("IK", control=PlayerControl.LOCAL, army=army_ik)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=army_enemy)
    game.add_player(ik_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    return game, army_ik, ik_player


def _apply_enhancement(unit: Unit, *, enh_id: str, name: str, detachment: str, detachment_id: str) -> None:
    enhancement = Enhancement(
        id=str(enh_id),
        name=str(name),
        faction_id="QI",
        detachment=str(detachment),
        detachment_id=str(detachment_id),
        points=0,
        description="",
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)


def _tank_shock() -> Stratagem:
    return Stratagem(
        id="core_tank_shock",
        name="Tank Shock",
        type="Core",
        description="",
        cp_cost=1,
        turn="Your",
        phase="Charge phase",
        detachment="",
        faction_id="",
    )


def _counter_offensive() -> Stratagem:
    return Stratagem(
        id="core_counter_offensive",
        name="Counter-offensive",
        type="Core",
        description="",
        cp_cost=2,
        turn="Either",
        phase="Fight phase",
        detachment="",
        faction_id="",
    )


def test_imperial_knights_zero_cp_enhancement_descriptors_registered():
    vengeful = get_enhancement_tool_descriptor(enhancement_id="000010497005")
    assert vengeful is not None
    assert vengeful.name == "Vengeful Tread"
    assert tuple(vengeful.effect_params.get("stratagem_names", ()) or ()) == ("TANK SHOCK",)

    martial = get_enhancement_tool_descriptor(enhancement_id="000010506005")
    assert martial is not None
    assert martial.name == "Martial Tuition"
    assert tuple(martial.effect_params.get("stratagem_names", ()) or ()) == ("COUNTER-OFFENSIVE",)
    assert int(martial.effect_params.get("required_min_bondsman_targets", 0) or 0) == 2


def test_vengeful_tread_allows_tank_shock_zero_cp_once_per_turn_for_bearer_only():
    game, army_ik, ik_player = _build_game("Gate Warden Lance")
    bearer = _make_unit(
        "Knight Warden",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    other = _make_unit(
        "Knight Gallant",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    army_ik.add_unit(bearer)
    army_ik.add_unit(other)
    game.map.units = [bearer, other]
    game.rebuild_entity_registry()

    _apply_enhancement(
        bearer,
        enh_id="000010497005",
        name="Vengeful Tread",
        detachment="Gate Warden Lance",
        detachment_id="000010497",
    )

    stratagem = _tank_shock()
    preview_bearer = ik_player.preview_stratagem_cp_cost(
        stratagem,
        target_unit=bearer,
        assume_optional_discounts=True,
    )
    assert int(preview_bearer.get("cost", -1)) == 0

    preview_other = ik_player.preview_stratagem_cp_cost(
        stratagem,
        target_unit=other,
        assume_optional_discounts=True,
    )
    assert int(preview_other.get("cost", -1)) == 1

    ik_player.set_next_optional_decision("VENGEFUL_TREAD_TANK_SHOCK", True)
    first = ik_player.apply_stratagem_cp_cost(stratagem, target_unit=bearer)
    assert int(first.get("cost", -1)) == 0
    assert bool(first.get("vengeful_tread_tank_shock_use", False))

    ik_player.set_next_optional_decision("VENGEFUL_TREAD_TANK_SHOCK", True)
    second = ik_player.apply_stratagem_cp_cost(stratagem, target_unit=bearer)
    assert int(second.get("cost", -1)) == 1
    assert not bool(second.get("vengeful_tread_tank_shock_use", False))

    game.turn = 2
    ik_player.set_next_optional_decision("VENGEFUL_TREAD_TANK_SHOCK", True)
    third = ik_player.apply_stratagem_cp_cost(stratagem, target_unit=bearer)
    assert int(third.get("cost", -1)) == 0
    assert bool(third.get("vengeful_tread_tank_shock_use", False))


def test_martial_tuition_requires_two_bondsman_targets_and_matching_source():
    game, army_ik, ik_player = _build_game("Spearhead-At-Arms")
    bearer = _make_unit(
        "Knight Paladin",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE", "CHARACTER"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    armiger_a = _make_unit(
        "Armiger A",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE", "ARMIGER"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    armiger_b = _make_unit(
        "Armiger B",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE", "ARMIGER"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    armiger_c = _make_unit(
        "Armiger C",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE", "ARMIGER"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    army_ik.add_unit(bearer)
    army_ik.add_unit(armiger_a)
    army_ik.add_unit(armiger_b)
    army_ik.add_unit(armiger_c)
    game.map.units = [bearer, armiger_a, armiger_b, armiger_c]
    game.rebuild_entity_registry()

    _apply_enhancement(
        bearer,
        enh_id="000010506005",
        name="Martial Tuition",
        detachment="Spearhead-At-Arms",
        detachment_id="000010506",
    )

    source_id = str(get_entity_id(bearer) or "")
    armiger_a.special_rules = {
        "bondsman_active": True,
        "bondsman_source_unit_id": source_id,
    }
    stratagem = _counter_offensive()

    one_target_preview = ik_player.preview_stratagem_cp_cost(
        stratagem,
        target_unit=armiger_a,
        assume_optional_discounts=True,
    )
    assert int(one_target_preview.get("cost", -1)) == 2

    armiger_b.special_rules = {
        "bondsman_active": True,
        "bondsman_source_unit_id": source_id,
    }
    wrong_target_preview = ik_player.preview_stratagem_cp_cost(
        stratagem,
        target_unit=armiger_c,
        assume_optional_discounts=True,
    )
    assert int(wrong_target_preview.get("cost", -1)) == 2

    valid_preview = ik_player.preview_stratagem_cp_cost(
        stratagem,
        target_unit=armiger_a,
        assume_optional_discounts=True,
    )
    assert int(valid_preview.get("cost", -1)) == 0

    ik_player.set_next_optional_decision("MARTIAL_TUITION_COUNTER_OFFENSIVE", True)
    first = ik_player.apply_stratagem_cp_cost(stratagem, target_unit=armiger_a)
    assert int(first.get("cost", -1)) == 0
    assert bool(first.get("martial_tuition_counter_offensive_use", False))

    ik_player.set_next_optional_decision("MARTIAL_TUITION_COUNTER_OFFENSIVE", True)
    second = ik_player.apply_stratagem_cp_cost(stratagem, target_unit=armiger_a)
    assert int(second.get("cost", -1)) == 2
    assert not bool(second.get("martial_tuition_counter_offensive_use", False))

    game.turn = 2
    ik_player.set_next_optional_decision("MARTIAL_TUITION_COUNTER_OFFENSIVE", True)
    third = ik_player.apply_stratagem_cp_cost(stratagem, target_unit=armiger_a)
    assert int(third.get("cost", -1)) == 0
    assert bool(third.get("martial_tuition_counter_offensive_use", False))


def test_martial_tuition_does_not_allow_counter_offensive_repeat_this_phase():
    game, army_ik, ik_player = _build_game("Spearhead-At-Arms")
    bearer = _make_unit(
        "Knight Paladin",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE", "CHARACTER"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    armiger_a = _make_unit(
        "Armiger A",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE", "ARMIGER"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    armiger_b = _make_unit(
        "Armiger B",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE", "ARMIGER"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    army_ik.add_unit(bearer)
    army_ik.add_unit(armiger_a)
    army_ik.add_unit(armiger_b)
    game.map.units = [bearer, armiger_a, armiger_b]
    game.rebuild_entity_registry()

    _apply_enhancement(
        bearer,
        enh_id="000010506005",
        name="Martial Tuition",
        detachment="Spearhead-At-Arms",
        detachment_id="000010506",
    )

    source_id = str(get_entity_id(bearer) or "")
    armiger_a.special_rules = {
        "bondsman_active": True,
        "bondsman_source_unit_id": source_id,
    }
    armiger_b.special_rules = {
        "bondsman_active": True,
        "bondsman_source_unit_id": source_id,
    }

    ik_player.stratagems._used_stratagems_this_phase.add("COUNTER-OFFENSIVE")
    ik_player.set_next_optional_decision("MARTIAL_TUITION_COUNTER_OFFENSIVE", True)
    denied = ik_player.apply_stratagem_cp_cost(_counter_offensive(), target_unit=armiger_a)
    assert bool(denied.get("denied", False))
    assert "already used this phase" in str(denied.get("reason", "") or "").lower()
