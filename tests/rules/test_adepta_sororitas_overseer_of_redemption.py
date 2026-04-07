from __future__ import annotations

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit


class _MockDatasheet:
    def __init__(
        self,
        *,
        abilities=None,
        faction_name: str = "Adepta Sororitas",
    ):
        self.id = "repentia-squad"
        self.name = "Repentia Squad"
        self.faction_data = {"name": faction_name}
        self.keywords = ["INFANTRY", "ADEPTA SORORITAS", "REPENTIA SQUAD"]
        self.faction_keywords = ["ADEPTA SORORITAS"]
        self.datasheets_unit_composition = [
            {"description": "1 Repentia Superior"},
            {"description": "1 Sisters Repentia"},
        ]
        self.datasheets_models_cost = [{"description": "2 models", "cost": 120}]
        self.datasheets_models = [
            {
                "name": "Repentia Superior",
                "M": "6",
                "T": "3",
                "Sv": "7",
                "W": "2",
                "Ld": "7",
                "OC": "1",
                "base_size": "28mm",
                "inv_sv": "0",
                "inv_sv_descr": "none",
            },
            {
                "name": "Sisters Repentia",
                "M": "6",
                "T": "3",
                "Sv": "7",
                "W": "1",
                "Ld": "7",
                "OC": "1",
                "base_size": "28mm",
                "inv_sv": "0",
                "inv_sv_descr": "none",
            },
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = (
            "The Repentia Superior is equipped with: bolt pistol; neural whips. "
            "Each Sister Repentia is equipped with: penitent eviscerator."
        )
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _build_repentia_unit() -> Unit:
    ability = {
        "name": "Overseer of Redemption",
        "description": (
            "While this unit contains a Repentia Superior model, each time a Sisters Repentia model "
            "in this unit makes a melee attack, you can re-roll the Hit roll and you can re-roll the Wound roll."
        ),
        "type": "Datasheet",
        "parameter": "",
    }
    return Unit(_MockDatasheet(abilities=[ability]))


def _find_model(unit: Unit, required: str, *, excluded: str = ""):
    required_low = str(required or "").strip().lower()
    excluded_low = str(excluded or "").strip().lower()
    for model in list(getattr(unit, "models", []) or []):
        name_low = str(getattr(model, "name", "") or "").strip().lower()
        if required_low and required_low not in name_low:
            continue
        if excluded_low and excluded_low in name_low:
            continue
        return model
    return None


def _attach_to_game(unit: Unit) -> None:
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    army = Army.with_detachment("Adepta Sororitas", "Champions of Faith")
    army.faction_id = "AS"
    enemy = Army.with_detachment("Enemy", "Other")
    enemy.faction_id = "EN"
    p1 = Player("P1", control=PlayerControl.REMOTE, army=army)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=enemy)
    game.add_player(p1)
    game.add_player(p2)
    army.add_unit(unit)
    game.map.units = [unit]
    game.rebuild_entity_registry()


def test_overseer_of_redemption_applies_to_sisters_repentia_melee_attacks():
    unit = _build_repentia_unit()
    _attach_to_game(unit)
    sisters_repentia = _find_model(unit, "repentia", excluded="superior")
    assert sisters_repentia is not None

    hit_mods = unit.get_unit_hit_reroll_modifiers("melee", attacker_model=sisters_repentia)
    wound_mods = unit.get_unit_wound_reroll_modifiers("melee", attacker_model=sisters_repentia)

    assert bool(hit_mods.get("reroll_hit_full", False))
    assert bool(wound_mods.get("reroll_wound_full", False))
    assert any("Overseer of Redemption" in str(reason) for reason in list(hit_mods.get("reroll_hit_full_reasons", ()) or ()))
    assert any(
        "Overseer of Redemption" in str(reason)
        for reason in list(wound_mods.get("reroll_wound_full_reasons", ()) or ())
    )

    ranged_hit_mods = unit.get_unit_hit_reroll_modifiers("ranged", attacker_model=sisters_repentia)
    ranged_wound_mods = unit.get_unit_wound_reroll_modifiers("ranged", attacker_model=sisters_repentia)
    assert not bool(ranged_hit_mods.get("reroll_hit_full", False))
    assert not bool(ranged_wound_mods.get("reroll_wound_full", False))


def test_overseer_of_redemption_does_not_apply_without_superior_or_for_superior_model():
    unit = _build_repentia_unit()
    _attach_to_game(unit)
    sisters_repentia = _find_model(unit, "repentia", excluded="superior")
    superior = _find_model(unit, "superior")
    assert sisters_repentia is not None
    assert superior is not None

    superior_hit_mods = unit.get_unit_hit_reroll_modifiers("melee", attacker_model=superior)
    superior_wound_mods = unit.get_unit_wound_reroll_modifiers("melee", attacker_model=superior)
    assert not bool(superior_hit_mods.get("reroll_hit_full", False))
    assert not bool(superior_wound_mods.get("reroll_wound_full", False))

    unit.models = [sisters_repentia]
    no_superior_hit_mods = unit.get_unit_hit_reroll_modifiers("melee", attacker_model=sisters_repentia)
    no_superior_wound_mods = unit.get_unit_wound_reroll_modifiers("melee", attacker_model=sisters_repentia)
    assert not bool(no_superior_hit_mods.get("reroll_hit_full", False))
    assert not bool(no_superior_wound_mods.get("reroll_wound_full", False))
