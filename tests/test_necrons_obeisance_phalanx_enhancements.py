from __future__ import annotations

import unittest

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
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
                "M": "5",
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
            attached_to=attached_to,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    necron_army = Army("Necrons", "Obeisance Phalanx")
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
        detachment="Obeisance Phalanx",
        points=15,
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


class TestNecronsObeisancePhalanxEnhancements(unittest.TestCase):
    def test_obeisance_enhancement_descriptors_registered(self):
        expected = {
            "000008550002": ("Honourable Combatant", "opponent_loses_cp_on_enemy_character_unit_destroyed_by_bearer_unit"),
            "000008550003": ("Unflinching Will", "bearer_melee_weapons_precision_and_anti_infantry"),
            "000008550004": ("Warrior Noble", "bearer_unit_target_melee_hit_penalty"),
            "000008550005": ("Eternal Conqueror", "bearer_unit_hit_reroll_if_target_within_objective_range"),
        }
        for enhancement_id, (name, effect) in expected.items():
            descriptor = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
            self.assertIsNotNone(descriptor)
            self.assertEqual(str(getattr(descriptor, "name", "") or ""), name)
            self.assertEqual(str(getattr(descriptor, "effect", "") or ""), effect)

    def test_honourable_combatant_makes_opponent_lose_cp_when_bearer_unit_destroys_character(self):
        game, necron_army, enemy_army, _necron_player, enemy_player = _build_game()
        leader = _make_unit(
            "Overlord",
            "necron-overlord",
            keywords=["CHARACTER", "INFANTRY", "OVERLORD"],
            faction_keywords=["NECRONS"],
            attached_to=["necron-lychguard"],
        )
        bodyguard = _make_unit(
            "Lychguard",
            "necron-lychguard",
            keywords=["INFANTRY", "LYCHGUARD"],
            faction_keywords=["NECRONS"],
            model_count=2,
        )
        enemy_character = _make_unit(
            "Enemy Hero",
            "enemy-hero",
            faction_name="Enemy",
            keywords=["CHARACTER", "INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        enemy_character_b = _make_unit(
            "Enemy Hero B",
            "enemy-hero-b",
            faction_name="Enemy",
            keywords=["CHARACTER", "INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        necron_army.add_unit(leader)
        necron_army.add_unit(bodyguard)
        enemy_army.add_unit(enemy_character)
        enemy_army.add_unit(enemy_character_b)
        necron_army.configure_rule_managers(force=True)
        _attach_leader(bodyguard, leader)
        _apply_enhancement(
            leader,
            enhancement_id="000008550002",
            name="Honourable Combatant",
            description=(
                "OVERLORD model only. Each time the bearer's unit destroys an enemy CHARACTER unit, "
                "your opponent loses 1CP if they have any."
            ),
        )

        enemy_player.command_points = 3
        game.event_system.publish(
            "unit_destroyed",
            unit=enemy_character,
            destroyed_by_unit=bodyguard,
            destroyed_by_model=bodyguard.models[0],
        )
        self.assertEqual(int(enemy_player.command_points), 2)

        bearer = _bearer_model(leader)
        self.assertIsNotNone(bearer)
        bearer.take_damage(999)
        game.event_system.publish(
            "unit_destroyed",
            unit=enemy_character_b,
            destroyed_by_unit=bodyguard,
            destroyed_by_model=bodyguard.models[0],
        )
        self.assertEqual(int(enemy_player.command_points), 2)

    def test_unflinching_will_grants_precision_and_anti_infantry_to_bearer_melee_only(self):
        _game, necron_army, enemy_army, _necron_player, _enemy_player = _build_game()
        source = _make_unit(
            "Overlord",
            "necron-overlord",
            keywords=["CHARACTER", "INFANTRY", "OVERLORD"],
            faction_keywords=["NECRONS"],
            model_count=2,
        )
        enemy = _make_unit(
            "Enemy Infantry",
            "enemy-infantry",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        necron_army.add_unit(source)
        enemy_army.add_unit(enemy)
        necron_army.configure_rule_managers(force=True)
        _apply_enhancement(
            source,
            enhancement_id="000008550003",
            name="Unflinching Will",
            description="OVERLORD model only. The bearer's melee weapons have the [PRECISION] and [ANTI-INFANTRY 5+] abilities.",
        )

        bearer = _bearer_model(source)
        self.assertIsNotNone(bearer)
        other = next(model for model in list(source.models or []) if model is not bearer)

        bearer_bonus = source.get_attack_keyword_bonuses(target=enemy, attack_type="melee", model=bearer)
        other_bonus = source.get_attack_keyword_bonuses(target=enemy, attack_type="melee", model=other)
        self.assertTrue(bool(bearer_bonus.get("precision", False)))
        self.assertIn(("INFANTRY", 5), list(bearer_bonus.get("anti_specs", []) or []))
        self.assertFalse(bool(other_bonus.get("precision", False)))
        self.assertNotIn(("INFANTRY", 5), list(other_bonus.get("anti_specs", []) or []))

    def test_warrior_noble_applies_melee_target_hit_penalty_only_while_bearer_alive(self):
        _game, necron_army, _enemy_army, _necron_player, _enemy_player = _build_game()
        leader = _make_unit(
            "Overlord",
            "necron-overlord",
            keywords=["CHARACTER", "INFANTRY", "OVERLORD"],
            faction_keywords=["NECRONS"],
            attached_to=["necron-lychguard"],
        )
        bodyguard = _make_unit(
            "Lychguard",
            "necron-lychguard",
            keywords=["INFANTRY", "LYCHGUARD"],
            faction_keywords=["NECRONS"],
            model_count=2,
        )
        necron_army.add_unit(leader)
        necron_army.add_unit(bodyguard)
        necron_army.configure_rule_managers(force=True)
        _attach_leader(bodyguard, leader)
        _apply_enhancement(
            leader,
            enhancement_id="000008550004",
            name="Warrior Noble",
            description="OVERLORD model only. Each time a melee attack targets the bearer's unit, subtract 1 from the Hit roll.",
        )

        melee_penalty, melee_reasons = bodyguard.get_target_hit_roll_penalty("melee")
        ranged_penalty, _ranged_reasons = bodyguard.get_target_hit_roll_penalty("ranged")
        self.assertEqual(int(melee_penalty), 1)
        self.assertIn("-1 to hit from Warrior Noble", list(melee_reasons or ()))
        self.assertEqual(int(ranged_penalty), 0)

        bearer = _bearer_model(leader)
        self.assertIsNotNone(bearer)
        bearer.take_damage(999)
        dead_penalty, _dead_reasons = bodyguard.get_target_hit_roll_penalty("melee")
        self.assertEqual(int(dead_penalty), 0)

    def test_eternal_conqueror_grants_full_hit_rerolls_against_objective_targets_only_while_bearer_alive(self):
        game, necron_army, enemy_army, _necron_player, _enemy_player = _build_game()
        leader = _make_unit(
            "Overlord",
            "necron-overlord",
            keywords=["CHARACTER", "INFANTRY", "OVERLORD"],
            faction_keywords=["NECRONS"],
            attached_to=["necron-lychguard"],
        )
        bodyguard = _make_unit(
            "Lychguard",
            "necron-lychguard",
            keywords=["INFANTRY", "LYCHGUARD"],
            faction_keywords=["NECRONS"],
            model_count=2,
        )
        objective_target = _make_unit(
            "Objective Target",
            "objective-target",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        far_target = _make_unit(
            "Far Target",
            "far-target",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        necron_army.add_unit(leader)
        necron_army.add_unit(bodyguard)
        enemy_army.add_unit(objective_target)
        enemy_army.add_unit(far_target)
        necron_army.configure_rule_managers(force=True)
        _attach_leader(bodyguard, leader)
        _apply_enhancement(
            leader,
            enhancement_id="000008550005",
            name="Eternal Conqueror",
            description=(
                "OVERLORD model only. Each time a model in the bearer's unit makes an attack that targets an enemy unit "
                "within range of an objective marker, you can re-roll the Hit roll."
            ),
        )

        objective_target.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        far_target.models[0].set_location(12.0, 0.0, 0.0, 0.0)
        objective = Objective(
            name="Center Objective",
            category=ObjectiveCategory.PRIMARY,
            points=0,
            description="",
            conditions=lambda _g: False,
            location=ObjectivePoint(0.0, 0.0, 0.0, control_radius=3.0),
        )
        game.map.add_objective(objective)

        objective_mods = bodyguard.get_unit_hit_reroll_modifiers(
            "melee",
            target=objective_target,
            attacker_model=bodyguard.models[0],
        )
        far_mods = bodyguard.get_unit_hit_reroll_modifiers(
            "melee",
            target=far_target,
            attacker_model=bodyguard.models[0],
        )
        self.assertTrue(bool(objective_mods.get("reroll_hit_full", False)))
        self.assertFalse(bool(far_mods.get("reroll_hit_full", False)))

        bearer = _bearer_model(leader)
        self.assertIsNotNone(bearer)
        bearer.take_damage(999)
        after_death = bodyguard.get_unit_hit_reroll_modifiers(
            "melee",
            target=objective_target,
            attacker_model=bodyguard.models[0],
        )
        self.assertFalse(bool(after_death.get("reroll_hit_full", False)))


if __name__ == "__main__":
    unittest.main()
