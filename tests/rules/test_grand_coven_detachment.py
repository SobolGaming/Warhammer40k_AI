import pytest
from types import SimpleNamespace

from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.rules.thousand_sons_detachments import (
    IMBUED_MANIFESTATION,
    PSYCHIC_MAELSTROM,
    WRATH_OF_THE_IMMATERIUM,
)


class MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None, toughness: str = "4"):
        self.name = name
        self.faction_data = {"name": "Thousand Sons"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": str(toughness),
                "Sv": "4",
                "W": "3",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


def create_unit(name: str, *, keywords=None, faction_keywords=None, toughness: str = "4") -> Unit:
    ds = MockDatasheet(name, keywords=keywords, faction_keywords=faction_keywords, toughness=toughness)
    unit = Unit(ds)
    unit.deployed = True
    return unit


def make_psychic_profile(*, range_val: str = "18", strength: str = "4") -> WargearProfile:
    parent = SimpleNamespace(
        name="Psychic Weapon",
        is_melee=lambda: False,
        is_ranged=lambda: True,
    )
    data = {
        "range": str(range_val),
        "A": "1",
        "BS_WS": "3",
        "S": str(strength),
        "AP": "0",
        "D": "1",
        "description": "Psychic",
    }
    return WargearProfile("Profile", wargear_data=data, parent_wargear=parent)


def _aura_stub():
    return SimpleNamespace(
        hit=0,
        wound=0,
        reroll_hit_ones=False,
        reroll_wound_ones=False,
        reroll_hit_reasons=(),
        reroll_wound_reasons=(),
        target_toughness_delta=0,
        target_toughness_reasons=(),
        crit_wound_threshold=None,
        crit_wound_reasons=(),
    )


def test_grand_coven_selection_once_per_battle_and_round_expiry():
    army = Army.with_detachment("Thousand Sons", "Grand Coven")
    army.faction_id = "TS"
    mgr = army.thousand_sons_detachments

    assert mgr.select_grand_coven(IMBUED_MANIFESTATION, battle_round=1) is True
    assert mgr.select_grand_coven(IMBUED_MANIFESTATION, battle_round=1) is False

    available = [a.key for a in mgr.get_available_grand_coven_abilities()]
    assert IMBUED_MANIFESTATION.key not in available

    game = SimpleNamespace(turn=1)
    assert mgr.get_active_grand_coven(game=game).key == IMBUED_MANIFESTATION.key
    game.turn = 2
    assert mgr.get_active_grand_coven(game=game) is None


def test_imbued_manifestation_adds_psychic_range():
    army = Army.with_detachment("Thousand Sons", "Grand Coven")
    army.faction_id = "TS"
    army.player = SimpleNamespace(game=SimpleNamespace(turn=1))

    unit = create_unit("Rubric Marines", keywords=["THOUSAND SONS"])
    army.add_unit(unit)
    mgr = army.thousand_sons_detachments
    assert mgr.select_grand_coven(IMBUED_MANIFESTATION, battle_round=1)

    profile = make_psychic_profile(range_val="18")
    attacker = unit.models[0]
    assert profile._effective_range_max(attacker) == 24


def test_psychic_maelstrom_adds_wound_bonus():
    army = Army.with_detachment("Thousand Sons", "Grand Coven")
    army.faction_id = "TS"
    army.player = SimpleNamespace(game=SimpleNamespace(turn=1))

    attacker_unit = create_unit("Rubric Marines", keywords=["THOUSAND SONS"])
    target_unit = create_unit("Target", keywords=["INFANTRY"], toughness="4")
    army.add_unit(attacker_unit)
    army.add_unit(target_unit)

    mgr = army.thousand_sons_detachments
    assert mgr.select_grand_coven(PSYCHIC_MAELSTROM, battle_round=1)

    profile = make_psychic_profile(range_val="18", strength="4")
    attack_instance = {"_aura_attack_mods": _aura_stub()}
    wound_result = profile._wound_target_with_tracking(
        target_unit,
        attacker_unit.models[0],
        attack_instance,
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert wound_result["wound"] is True
    assert any("Psychic Maelstrom" in entry for entry in wound_result.get("modifiers", []))


def test_wrath_of_the_immaterium_grants_devastating_wounds():
    army = Army.with_detachment("Thousand Sons", "Grand Coven")
    army.faction_id = "TS"
    army.player = SimpleNamespace(game=SimpleNamespace(turn=1))

    attacker_unit = create_unit("Rubric Marines", keywords=["THOUSAND SONS"])
    target_unit = create_unit("Target", keywords=["INFANTRY"], toughness="4")
    army.add_unit(attacker_unit)
    army.add_unit(target_unit)

    mgr = army.thousand_sons_detachments
    assert mgr.select_grand_coven(WRATH_OF_THE_IMMATERIUM, battle_round=1)

    profile = make_psychic_profile(range_val="18", strength="4")
    attack_instance = {"_aura_attack_mods": _aura_stub()}

    hit_result = profile._hit_target_with_tracking(
        target_unit,
        attacker_unit.models[0],
        attack_instance,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert hit_result["hit"] is True

    wound_result = profile._wound_target_with_tracking(
        target_unit,
        attacker_unit.models[0],
        attack_instance,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert wound_result["wound"] is True
    assert attack_instance.get("mortal_wound") is True


def test_eldritch_vortex_of_etaph_adds_psychic_strength_and_damage_for_bearer():
    army = Army.with_detachment("Thousand Sons", "Grand Coven")
    army.faction_id = "TS"
    army.player = SimpleNamespace(game=SimpleNamespace(turn=1))

    attacker_unit = create_unit("Exalted Sorcerer", keywords=["THOUSAND SONS", "PSYKER"])
    target_unit = create_unit("Target", keywords=["INFANTRY"], toughness="5")
    army.add_unit(attacker_unit)
    army.add_unit(target_unit)

    Enhancement(
        id="000010193005",
        name="Eldritch Vortex of E'taph",
        faction_id="TS",
        detachment="Grand Coven",
        points=30,
        description="",
    ).apply_to_unit(attacker_unit)

    profile = make_psychic_profile(range_val="18", strength="4")
    attack_instance = {"_aura_attack_mods": _aura_stub()}

    wound_result = profile._wound_target_with_tracking(
        target_unit,
        attacker_unit.models[0],
        attack_instance,
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert wound_result["wound"] is True
    assert any("Eldritch Vortex of E'taph" in entry for entry in wound_result.get("modifiers", []))

    target_model = target_unit.models[0]
    before = int(target_model.wounds)
    profile._damage_target_with_tracking(
        target_model,
        attacker_unit.models[0],
        {"below_half_distance": False, "mortal_wound": False},
        game_map=None,
    )
    assert int(target_model.wounds) == before - 2
