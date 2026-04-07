from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.battlefield.map import Map
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.aura_effects import get_aura_leadership_bonus


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        datasheet_id: str,
        keywords: list[str] | None = None,
        faction_keywords: list[str] | None = None,
        model_count: int = 1,
        movement: str = "10",
        toughness: str = "6",
        wounds: str = "10",
        leadership: str = "7",
        abilities: list[dict] | None = None,
    ) -> None:
        self.id = datasheet_id
        self.name = name
        self.faction_data = {"name": "Orks"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or ["ORKS"])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": movement,
                "T": toughness,
                "Sv": "3",
                "W": wounds,
                "Ld": leadership,
                "OC": "1",
                "base_size": "80mm",
                "inv_sv": "0",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    datasheet_id: str,
    *,
    keywords: list[str] | None = None,
    faction_keywords: list[str] | None = None,
    movement: str = "10",
    toughness: str = "6",
    wounds: str = "10",
    leadership: str = "7",
    abilities: list[dict] | None = None,
) -> Unit:
    datasheet = _MockDatasheet(
        name,
        datasheet_id=datasheet_id,
        keywords=keywords,
        faction_keywords=faction_keywords,
        movement=movement,
        toughness=toughness,
        wounds=wounds,
        leadership=leadership,
        abilities=abilities,
    )
    return Unit(datasheet)


def _make_ork_army() -> Army:
    army = Army.with_detachment("Orks", "War Horde")
    army.faction_id = "ORK"
    return army


def _make_enemy_army() -> Army:
    army = Army.with_detachment("Enemy", "Other")
    army.faction_id = "EN"
    return army


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
    )


def test_trophy_hunters_allows_charge_reroll():
    breaka_boyz = _make_unit(
        "Breaka Boyz",
        "orks-breaka-boyz",
        keywords=["INFANTRY"],
        abilities=[
            {
                "name": "Trophy Hunters",
                "description": "Each time this unit declares a charge, you can re-roll the Charge roll.",
                "type": "Datasheet",
                "parameter": "",
            }
        ],
    )

    assert breaka_boyz.can_reroll_charge_roll() is True


def test_wild_ride_registers_move_advance_charge_modifier_ignore_rule():
    squighog_boyz = _make_unit(
        "Squighog Boyz",
        "orks-squighog-boyz",
        keywords=["MOUNTED"],
        abilities=[
            {
                "name": "Wild Ride",
                "description": "You can ignore any or all modifiers to this unit's Move characteristic and to Advance and Charge rolls made for this unit.",
                "type": "Datasheet",
                "parameter": "",
            }
        ],
    )

    rule = squighog_boyz.get_move_advance_charge_modifier_ignore_rule()

    assert rule is not None
    assert str(rule.get("source", "")) == "Wild Ride"


def test_ramshackle_but_rugged_worsens_allocated_attack_ap():
    ork_army = _make_ork_army()
    enemy_army = _make_enemy_army()
    battlewagon = _make_unit(
        "Battlewagon",
        "orks-battlewagon",
        keywords=["VEHICLE", "TRANSPORT"],
        toughness="10",
        abilities=[
            {
                "name": "Ramshackle but Rugged",
                "description": "Each time an attack is allocated to this model, worsen the Armour Penetration characteristic of that attack by 1.",
                "type": "Datasheet",
                "parameter": "",
            }
        ],
    )
    attacker = _make_unit(
        "Enemy Unit",
        "enemy-attacker",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        toughness="4",
    )
    ork_army.add_unit(battlewagon)
    enemy_army.add_unit(attacker)

    parent = SimpleNamespace(name="Enemy Gun", is_melee=lambda: False, is_ranged=lambda: True)
    profile = WargearProfile(
        profile_name="Ranged",
        wargear_data={"range": "24", "A": "1", "BS_WS": "4+", "S": "6", "AP": "-2", "D": "1", "description": ""},
        parent_wargear=parent,
    )

    assert int(profile.get_effective_ap(attacker.models[0], battlewagon)) == -1


def test_dakkastorm_turns_successful_ranged_hits_into_critical_hits(monkeypatch):
    dakkajet = _make_unit(
        "Dakkajet",
        "orks-dakkajet",
        keywords=["VEHICLE", "AIRCRAFT"],
        abilities=[
            {
                "name": "Dakkastorm",
                "description": "Each time this model makes a ranged attack, every successful Hit roll scores a Critical Hit.",
                "type": "Datasheet",
                "parameter": "",
            }
        ],
    )
    target = _make_unit(
        "Enemy Target",
        "enemy-target",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        toughness="4",
    )

    parent = SimpleNamespace(name="Supa-shoota", is_melee=lambda: False, is_ranged=lambda: True)
    profile = WargearProfile(
        profile_name="Ranged",
        wargear_data={"range": "24", "A": "1", "BS_WS": "4+", "S": "6", "AP": "0", "D": "1", "description": ""},
        parent_wargear=parent,
    )
    attack_instance = {"_aura_attack_mods": _aura_stub()}

    from warhammer40k_ai.units import wargear as wargear_mod

    monkeypatch.setattr(wargear_mod, "get_roll", lambda _d: 4)
    hit_result = profile._hit_target_with_tracking(target, dakkajet.models[0], attack_instance)

    assert int(hit_result.get("crit_threshold", 0) or 0) == 4
    assert bool(attack_instance.get("crit_hit", False)) is True


def test_ramshackle_cover_registers_fortification_cover_rule():
    bossbunka = _make_unit(
        "Big'ed Bossbunka",
        "orks-biged-bossbunka-cover",
        keywords=["FORTIFICATION"],
        abilities=[
            {
                "name": "Ramshackle Cover",
                "description": "Each time a ranged attack is allocated to a model, if that model is not fully visible to every model in the attacking unit because of this FORTIFICATION, that model has the Benefit of Cover against that attack.",
                "type": "Datasheet",
                "parameter": "",
            }
        ],
    )

    rule = bossbunka.get_fortification_cover_rule()

    assert rule is not None
    assert str(rule.get("source", "")) == "Ramshackle Cover"


def test_shoutin_pole_improves_nearby_orks_leadership():
    ork_army = _make_ork_army()
    bossbunka = _make_unit(
        "Big'ed Bossbunka",
        "orks-biged-bossbunka",
        keywords=["FORTIFICATION"],
        abilities=[
            {
                "name": "Shoutin' Pole (Aura)",
                "description": "While a friendly ORKS unit is within 6\" of this FORTIFICATION, improve the Leadership characteristic of models in that unit by 1.",
                "type": "Datasheet",
                "parameter": "",
            }
        ],
    )
    boyz = _make_unit(
        "Boyz",
        "orks-boyz",
        keywords=["INFANTRY"],
        leadership="7",
    )
    ork_army.add_unit(bossbunka)
    ork_army.add_unit(boyz)

    bossbunka.deployed = True
    boyz.deployed = True
    bossbunka.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    boyz.models[0].set_location(5.0, 0.0, 0.0, 0.0)

    game_map = Map(60, 44)
    game_map.units = [bossbunka, boyz]

    assert int(get_aura_leadership_bonus(boyz, game_map=game_map)) == -1
