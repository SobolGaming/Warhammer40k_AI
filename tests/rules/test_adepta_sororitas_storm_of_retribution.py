from __future__ import annotations

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Adepta Sororitas",
        abilities=None,
        keywords=None,
        faction_keywords=None,
    ):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            faction_keywords = ["ADEPTA SORORITAS"] if faction_name == "Adepta Sororitas" else [str(faction_name).upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": name,
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "0",
                "inv_sv_descr": "none",
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
    *,
    faction_name: str = "Adepta Sororitas",
    abilities=None,
    keywords=None,
    faction_keywords=None,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            abilities=abilities,
            keywords=keywords,
            faction_keywords=faction_keywords,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    sororitas_army = Army("Adepta Sororitas", "Champions of Faith")
    sororitas_army.faction_id = "AS"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    p1 = Player("Sororitas", control=PlayerControl.REMOTE, army=sororitas_army)
    p2 = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)
    game.current_player_index = 0
    return game, sororitas_army, enemy_army


def test_storm_of_retribution_rerolls_and_conditional_target_bonus():
    game, sororitas_army, enemy_army = _build_game()
    retributor = _make_unit(
        "Retributor Squad",
        abilities=[
            {
                "name": "Storm of Retribution",
                "description": (
                    "Each time a model in this unit makes a ranged attack, re-roll a Hit roll of 1 and re-roll a Wound roll of 1. "
                    "If such an attack targets an enemy unit that has destroyed one or more Adepta Sororitas units from your army "
                    "during the battle, add 1 to the Hit roll and add 1 to the Wound roll as well."
                ),
                "type": "Datasheet",
                "parameter": "",
            }
        ],
        keywords=["INFANTRY", "ADEPTA SORORITAS"],
    )
    fallen_sisters = _make_unit(
        "Battle Sisters Squad",
        keywords=["INFANTRY", "ADEPTA SORORITAS"],
    )
    enemy_killer = _make_unit(
        "Enemy Killer",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    enemy_other = _make_unit(
        "Enemy Other",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )

    sororitas_army.add_unit(retributor)
    sororitas_army.add_unit(fallen_sisters)
    enemy_army.add_unit(enemy_killer)
    enemy_army.add_unit(enemy_other)
    game.map.units = [retributor, fallen_sisters, enemy_killer, enemy_other]
    game.rebuild_entity_registry()

    shooter_model = retributor.models[0]

    hit_mods_before = retributor.get_unit_hit_reroll_modifiers("ranged", target=enemy_killer, attacker_model=shooter_model)
    wound_mods_before = retributor.get_unit_wound_reroll_modifiers(
        "ranged",
        target=enemy_killer,
        attacker_model=shooter_model,
    )
    assert bool(hit_mods_before.get("reroll_hit_ones", False))
    assert bool(wound_mods_before.get("reroll_wound_ones", False))
    assert int(hit_mods_before.get("hit", 0) or 0) == 0
    assert int(wound_mods_before.get("wound", 0) or 0) == 0

    melee_hit_mods = retributor.get_unit_hit_reroll_modifiers("melee", target=enemy_killer, attacker_model=shooter_model)
    melee_wound_mods = retributor.get_unit_wound_reroll_modifiers(
        "melee",
        target=enemy_killer,
        attacker_model=shooter_model,
    )
    assert not bool(melee_hit_mods.get("reroll_hit_ones", False))
    assert not bool(melee_wound_mods.get("reroll_wound_ones", False))

    game._on_unit_destroyed_rules(
        unit=fallen_sisters,
        destroyed_by_unit=enemy_killer,
        destroyed_by_model=enemy_killer.models[0],
        destroyed_by_weapon_profile=None,
    )

    hit_mods_bonus = retributor.get_unit_hit_reroll_modifiers("ranged", target=enemy_killer, attacker_model=shooter_model)
    wound_mods_bonus = retributor.get_unit_wound_reroll_modifiers(
        "ranged",
        target=enemy_killer,
        attacker_model=shooter_model,
    )
    assert int(hit_mods_bonus.get("hit", 0) or 0) == 1
    assert int(wound_mods_bonus.get("wound", 0) or 0) == 1
    assert bool(hit_mods_bonus.get("reroll_hit_ones", False))
    assert bool(wound_mods_bonus.get("reroll_wound_ones", False))

    hit_mods_other = retributor.get_unit_hit_reroll_modifiers("ranged", target=enemy_other, attacker_model=shooter_model)
    wound_mods_other = retributor.get_unit_wound_reroll_modifiers(
        "ranged",
        target=enemy_other,
        attacker_model=shooter_model,
    )
    assert int(hit_mods_other.get("hit", 0) or 0) == 0
    assert int(wound_mods_other.get("wound", 0) or 0) == 0
