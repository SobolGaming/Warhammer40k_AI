from __future__ import annotations

import unittest

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        datasheet_id: str,
        faction_name: str = "Necrons",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        movement: int = 5,
        attached_to=None,
    ) -> None:
        self.id = datasheet_id
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            faction_keywords = ["NECRONS"] if faction_name == "Necrons" else [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": str(int(movement)),
                "T": "5",
                "Sv": "3",
                "W": "4",
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
        self.transport = ""
        self.attached_to = list(attached_to or [])
        self.attached_to_names = []


def _make_unit(
    name: str,
    datasheet_id: str,
    *,
    faction_name: str = "Necrons",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    movement: int = 5,
    attached_to=None,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            datasheet_id=datasheet_id,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            movement=movement,
            attached_to=attached_to,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _build_game(*, size: BattlefieldSize = BattlefieldSize.STRIKE_FORCE):
    game = Game(Battlefield(size))
    necron_army = Army("Necrons", "Hypercrypt Legion")
    necron_army.faction_id = "NEC"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    necron_player = Player("Necrons", control=PlayerControl.LOCAL, army=necron_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(necron_player)
    game.add_player(enemy_player)
    game.turn = 1
    return game, necron_army, enemy_army, necron_player, enemy_player


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    leader.attach_to_unit(bodyguard)


def _apply_enhancement(unit: Unit, *, enhancement_id: str, name: str, description: str) -> None:
    enhancement = Enhancement(
        id=enhancement_id,
        name=name,
        faction_id="NEC",
        detachment="Hypercrypt Legion",
        points=20,
        description=description,
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)


def _bearer_model(unit: Unit):
    getter = getattr(unit, "_get_enhancement_bearer_model", None)
    if callable(getter):
        bearer = getter()
        if bearer is not None:
            return bearer
    models = list(getattr(unit, "models", []) or [])
    return models[0] if models else None


class TestNecronsHypercryptLegionEnhancements(unittest.TestCase):
    def test_hypercrypt_enhancement_descriptors_registered(self):
        expected = {
            "000008554002": ("Dimensional Overseer", "hyperphasing_selection_cap_bonus"),
            "000008554003": ("Arisen Tyrant", "bearer_unit_hit_reroll_ones_or_full_if_set_up_this_turn"),
            "000008554004": ("Hyperspatial Transfer Node", "bearer_unit_advance_no_roll_move_bonus"),
            "000008554005": ("Osteoclave Fulcrum", "grant_deep_strike_to_bearer_unit_models"),
        }
        for enhancement_id, (name, effect) in expected.items():
            descriptor = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
            self.assertIsNotNone(descriptor)
            self.assertEqual(str(getattr(descriptor, "name", "") or ""), name)
            self.assertEqual(str(getattr(descriptor, "effect", "") or ""), effect)

    def test_dimensional_overseer_increases_hyperphasing_cap_on_battlefield_and_in_strategic_reserves(self):
        game, necron_army, _enemy_army, _necron_player, _enemy_player = _build_game()
        bearer_unit = _make_unit(
            "Overlord",
            "necron-overlord",
            keywords=["CHARACTER", "INFANTRY"],
            faction_keywords=["NECRONS"],
        )
        necron_army.add_unit(bearer_unit)
        necron_army.configure_rule_managers(force=True)
        _apply_enhancement(
            bearer_unit,
            enhancement_id="000008554002",
            name="Dimensional Overseer",
            description=(
                "NECRONS model only. While the bearer is on the battlefield or in Strategic Reserves, "
                "add one to the number of units from your army that you can select for the Hyperphasing rule."
            ),
        )

        manager = necron_army.necrons_detachments
        self.assertEqual(manager.hyperphasing_end_of_opponent_turn_max_units(game=game), 3)

        bearer_unit.deployed = False
        bearer_unit.reserve_status = "strategic_reserves"
        self.assertEqual(manager.hyperphasing_end_of_opponent_turn_max_units(game=game), 3)

        bearer = _bearer_model(bearer_unit)
        self.assertIsNotNone(bearer)
        bearer.take_damage(999)
        self.assertEqual(manager.hyperphasing_end_of_opponent_turn_max_units(game=game), 2)

    def test_arisen_tyrant_grants_hit_reroll_ones_and_full_rerolls_if_set_up_this_turn(self):
        _game, necron_army, enemy_army, _necron_player, _enemy_player = _build_game()
        leader = _make_unit(
            "Overlord",
            "necron-overlord",
            keywords=["CHARACTER", "INFANTRY"],
            faction_keywords=["NECRONS"],
            attached_to=["necron-warriors"],
        )
        bodyguard = _make_unit(
            "Necron Warriors",
            "necron-warriors",
            keywords=["INFANTRY"],
            faction_keywords=["NECRONS"],
            model_count=2,
        )
        enemy = _make_unit(
            "Enemy Unit",
            "enemy-unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        necron_army.add_unit(leader)
        necron_army.add_unit(bodyguard)
        enemy_army.add_unit(enemy)
        necron_army.configure_rule_managers(force=True)
        _apply_enhancement(
            leader,
            enhancement_id="000008554003",
            name="Arisen Tyrant",
            description=(
                "NECRONS model only. Each time a model in the bearer's unit makes an attack, re-roll a Hit roll of 1. "
                "If the bearer's unit was set up on the battlefield this turn, you can re-roll the Hit roll instead."
            ),
        )
        _attach_leader(bodyguard, leader)

        base_mods = bodyguard.get_unit_hit_reroll_modifiers(
            "ranged",
            target=enemy,
            attacker_model=bodyguard.models[0],
        )
        self.assertIn(1, tuple(base_mods.get("reroll_hit_values", ()) or ()))
        self.assertFalse(bool(base_mods.get("reroll_hit_full", False)))

        bodyguard.arrived_from_reserves_this_turn = True
        full_mods = bodyguard.get_unit_hit_reroll_modifiers(
            "ranged",
            target=enemy,
            attacker_model=bodyguard.models[0],
        )
        self.assertTrue(bool(full_mods.get("reroll_hit_full", False)))

        bearer = _bearer_model(leader)
        self.assertIsNotNone(bearer)
        bearer.take_damage(999)
        after_death = bodyguard.get_unit_hit_reroll_modifiers(
            "ranged",
            target=enemy,
            attacker_model=bodyguard.models[0],
        )
        self.assertNotIn(1, tuple(after_death.get("reroll_hit_values", ()) or ()))
        self.assertFalse(bool(after_death.get("reroll_hit_full", False)))

    def test_hyperspatial_transfer_node_grants_fixed_advance_while_bearer_alive(self):
        _game, necron_army, _enemy_army, _necron_player, _enemy_player = _build_game()
        leader = _make_unit(
            "Chronomancer",
            "necron-chronomancer",
            keywords=["CHARACTER", "INFANTRY"],
            faction_keywords=["NECRONS"],
            attached_to=["necron-warriors"],
        )
        bodyguard = _make_unit(
            "Necron Warriors",
            "necron-warriors",
            keywords=["INFANTRY"],
            faction_keywords=["NECRONS"],
            model_count=2,
        )
        necron_army.add_unit(leader)
        necron_army.add_unit(bodyguard)
        necron_army.configure_rule_managers(force=True)
        _attach_leader(bodyguard, leader)
        _apply_enhancement(
            leader,
            enhancement_id="000008554004",
            name="Hyperspatial Transfer Node",
            description=(
                "NECRONS model only. Each time the bearer's unit Advances, do not make an Advance roll for it. "
                "Instead, until the end of the phase, add 6\" to the Move characteristic of models in the bearer's unit."
            ),
        )

        effect = bodyguard._get_advance_no_roll_effect()
        self.assertIsNotNone(effect)
        self.assertEqual(int(effect.get("distance", 0) or 0), 6)

        bearer = _bearer_model(leader)
        self.assertIsNotNone(bearer)
        bearer.take_damage(999)
        self.assertIsNone(bodyguard._get_advance_no_roll_effect())

    def test_osteoclave_fulcrum_grants_deep_strike_while_bearer_alive(self):
        _game, necron_army, _enemy_army, _necron_player, _enemy_player = _build_game()
        leader = _make_unit(
            "Chronomancer",
            "necron-chronomancer",
            keywords=["CHARACTER", "INFANTRY"],
            faction_keywords=["NECRONS"],
            attached_to=["necron-warriors"],
        )
        bodyguard = _make_unit(
            "Necron Warriors",
            "necron-warriors",
            keywords=["INFANTRY"],
            faction_keywords=["NECRONS"],
            model_count=2,
        )
        necron_army.add_unit(leader)
        necron_army.add_unit(bodyguard)
        necron_army.configure_rule_managers(force=True)
        _attach_leader(bodyguard, leader)
        _apply_enhancement(
            leader,
            enhancement_id="000008554005",
            name="Osteoclave Fulcrum",
            description="NECRONS model only. Models in the bearer's unit have the Deep Strike ability.",
        )

        self.assertTrue(bodyguard.has_deep_strike())

        bearer = _bearer_model(leader)
        self.assertIsNotNone(bearer)
        bearer.take_damage(999)
        self.assertFalse(bodyguard.has_deep_strike())


if __name__ == "__main__":
    unittest.main()
