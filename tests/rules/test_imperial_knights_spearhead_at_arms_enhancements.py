from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str,
        keywords=None,
        faction_keywords=None,
    ):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
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


def _make_unit(
    name: str,
    *,
    faction_name: str,
    keywords=None,
    faction_keywords=None,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    ik_army = Army("Imperial Knights", detachment_type="Spearhead-At-Arms")
    ik_army.faction_id = "QI"
    enemy_army = Army("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    ik_player = Player("IK", PlayerControl.REMOTE, army=ik_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ik_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    return game, ik_army, enemy_army


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str) -> None:
    enhancement = Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="QI",
        detachment="Spearhead-At-Arms",
        points=0,
        description="",
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)


def _mark_bondsman_targets(source_unit: Unit, *targets: Unit) -> None:
    source_id = str(get_entity_id(source_unit) or "")
    for target in list(targets or []):
        sr = dict(getattr(target, "special_rules", {}) or {})
        sr["bondsman_active"] = True
        sr["bondsman_source_unit_id"] = source_id
        target.special_rules = sr


def _ranged_profile() -> WargearProfile:
    parent = SimpleNamespace(name="Test Cannon", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        "Test Cannon",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "10",
            "AP": "-2",
            "D": "3",
            "description": "",
        },
        parent_wargear=parent,
    )


def _melee_profile() -> WargearProfile:
    parent = SimpleNamespace(name="Test Blade", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        "Test Blade",
        wargear_data={
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": "10",
            "AP": "-2",
            "D": "3",
            "description": "",
        },
        parent_wargear=parent,
    )


def test_spearhead_enhancement_descriptors_registered():
    expected = {
        "000010506002": ("Mentor's Pride", "bondsman_armigers_reroll_hit_ones_while_two_or_more_are_affected"),
        "000010506003": ("Fables of Nightmare", "bondsman_armigers_gain_precision_while_two_or_more_are_affected"),
        "000010506004": ("Tales of Heroism", "bondsman_armigers_ignore_hit_and_wound_modifiers_while_two_or_more_are_affected"),
    }
    for enhancement_id, (name, effect) in expected.items():
        desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert desc is not None
        assert str(getattr(desc, "name", "") or "") == name
        assert str(getattr(desc, "effect", "") or "") == effect


def test_mentors_pride_grants_bondsman_armigers_reroll_hit_ones():
    game, ik_army, enemy_army = _build_game()
    source = _make_unit(
        "Knight Paladin",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    armiger_a = _make_unit(
        "Armiger A",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE", "ARMIGER"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    armiger_b = _make_unit(
        "Armiger B",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE", "ARMIGER"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    enemy = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    for unit in (source, armiger_a, armiger_b):
        ik_army.add_unit(unit)
    enemy_army.add_unit(enemy)
    game.map.units = [source, armiger_a, armiger_b, enemy]
    game.rebuild_entity_registry()
    _apply_enhancement(source, enhancement_id="000010506002", enhancement_name="Mentor's Pride")
    _mark_bondsman_targets(source, armiger_a, armiger_b)

    result = _ranged_profile()._hit_target_with_tracking(
        enemy,
        armiger_a.models[0],
        {},
        roll_value=1,
        allow_rerolls=False,
        log_roll=False,
    )

    assert any("Mentor's Pride" in str(reason or "") for reason in list(result.get("reroll_value_reasons", []) or []))


def test_fables_of_nightmare_grants_precision_to_bondsman_armiger_melee_attacks():
    game, ik_army, enemy_army = _build_game()
    source = _make_unit(
        "Knight Paladin",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    armiger_a = _make_unit(
        "Armiger A",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE", "ARMIGER"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    armiger_b = _make_unit(
        "Armiger B",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE", "ARMIGER"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    enemy = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    for unit in (source, armiger_a, armiger_b):
        ik_army.add_unit(unit)
    enemy_army.add_unit(enemy)
    game.map.units = [source, armiger_a, armiger_b, enemy]
    game.rebuild_entity_registry()
    _apply_enhancement(source, enhancement_id="000010506003", enhancement_name="Fables of Nightmare")
    _mark_bondsman_targets(source, armiger_a, armiger_b)

    attack_instance = {}
    _melee_profile()._hit_target_with_tracking(
        enemy,
        armiger_a.models[0],
        attack_instance,
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )

    assert bool(attack_instance.get("bonus_precision", False))


def test_tales_of_heroism_grants_ignore_hit_and_wound_modifier_rules():
    game, ik_army, enemy_army = _build_game()
    source = _make_unit(
        "Knight Paladin",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    armiger_a = _make_unit(
        "Armiger A",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE", "ARMIGER"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    armiger_b = _make_unit(
        "Armiger B",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE", "ARMIGER"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    enemy = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    for unit in (source, armiger_a, armiger_b):
        ik_army.add_unit(unit)
    enemy_army.add_unit(enemy)
    game.map.units = [source, armiger_a, armiger_b, enemy]
    game.rebuild_entity_registry()
    _apply_enhancement(source, enhancement_id="000010506004", enhancement_name="Tales of Heroism")
    _mark_bondsman_targets(source, armiger_a, armiger_b)

    profile = _melee_profile()
    hit_rule = profile._ignore_hit_modifier_rule(armiger_a.models[0], target_unit=enemy)
    wound_rule = profile._ignore_wound_modifier_rule(armiger_a.models[0])

    assert isinstance(hit_rule, dict)
    assert isinstance(wound_rule, dict)
    assert str(hit_rule.get("name", "") or "") == "Tales of Heroism"
    assert str(wound_rule.get("name", "") or "") == "Tales of Heroism"
    assert bool(hit_rule.get("allow_hit", False))
    assert bool(wound_rule.get("allow_wound", False))
