import unittest

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.rules.stratagems import Stratagem
from warhammer40k_ai.units.unit import Unit


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Grey Knights",
        keywords=None,
        faction_keywords=None,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or ["GREY KNIGHTS"])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
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
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(name: str, *, faction_name: str = "Grey Knights", keywords=None, faction_keywords=None) -> Unit:
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
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1
    gk_army = Army("Grey Knights", "Hallowed Conclave")
    gk_army.faction_id = "GK"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    gk_player = Player("GK", control=PlayerControl.REMOTE, army=gk_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(gk_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    return game, gk_army, enemy_army, gk_player, enemy_player


def _apply_enhancement(unit: Unit) -> None:
    enhancement = Enhancement(
        id="000010352002",
        name="Eye of the Augurium",
        faction_id="GK",
        detachment="Hallowed Conclave",
        points=15,
        description="",
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)


def _overwatch_stratagem() -> Stratagem:
    return Stratagem(
        id="core_overwatch",
        name="Fire Overwatch",
        type="Core",
        description="",
        cp_cost=1,
        turn="Either",
        phase="Movement phase, Charge phase",
        detachment="",
        faction_id="",
    )


def _heroic_intervention_stratagem() -> Stratagem:
    return Stratagem(
        id="core_heroic_intervention",
        name="Heroic Intervention",
        type="Core",
        description="",
        cp_cost=1,
        turn="Either",
        phase="Charge phase",
        detachment="",
        faction_id="",
    )


class TestGreyKnightsHallowedConclaveEnhancements(unittest.TestCase):
    def test_eye_of_the_augurium_descriptor_and_apply_registration(self):
        desc = get_enhancement_tool_descriptor(enhancement_id="000010352002")
        self.assertIsNotNone(desc)
        self.assertEqual(str(getattr(desc, "name", "") or ""), "Eye of the Augurium")
        self.assertEqual(
            tuple(getattr(desc, "effect_params", {}).get("stratagems", ()) or ()),
            ("OVERWATCH", "FIRE OVERWATCH", "HEROIC INTERVENTION"),
        )
        by_name = get_enhancement_tool_descriptor(name="Eye of the Augurium")
        self.assertIsNotNone(by_name)
        self.assertEqual(str(getattr(by_name, "enhancement_id", "") or ""), "000010352002")

        _game, gk_army, _enemy_army, _gk_player, _enemy_player = _build_game()
        bearer = _make_unit(
            "Brotherhood Champion",
            keywords=["INFANTRY", "CHARACTER"],
            faction_keywords=["GREY KNIGHTS"],
        )
        gk_army.add_unit(bearer)
        _apply_enhancement(bearer)

        sr = dict(getattr(bearer, "special_rules", {}) or {})
        self.assertTrue(bool(sr.get("enhancement_eye_of_the_augurium", False)))
        self.assertEqual(
            tuple(sr.get("enhancement_eye_of_the_augurium_stratagems", ()) or ()),
            ("OVERWATCH", "FIRE OVERWATCH", "HEROIC INTERVENTION"),
        )
        self.assertEqual(str(sr.get("enhancement_eye_of_the_augurium_limit", "") or ""), "battle_round")
        rule = bearer.get_eye_of_the_augurium_stratagem_rule()
        self.assertIsInstance(rule, dict)
        self.assertEqual(str((rule or {}).get("source", "") or ""), "Eye of the Augurium")

    def test_eye_of_the_augurium_allows_fire_overwatch_repeat_for_zero_cp_once_per_battle_round(self):
        game, gk_army, _enemy_army, gk_player, _enemy_player = _build_game()
        bearer = _make_unit(
            "Brotherhood Champion",
            keywords=["INFANTRY", "CHARACTER"],
            faction_keywords=["GREY KNIGHTS"],
        )
        gk_army.add_unit(bearer)
        _apply_enhancement(bearer)

        stratagem = _overwatch_stratagem()
        gk_player.stratagems._used_this_turn["OVERWATCH"] = True

        gk_player.set_next_optional_decision("EYE_OF_THE_AUGURIUM_STRATAGEM_DISCOUNT", True)
        first = gk_player.apply_stratagem_cp_cost(stratagem, target_unit=bearer)
        self.assertFalse(bool(first.get("denied", False)))
        self.assertEqual(int(first.get("cost", -1)), 0)
        self.assertTrue(bool(first.get("eye_of_the_augurium_use", False)))
        self.assertEqual(str(bearer.special_rules.get("eye_of_the_augurium_used_battle_round", "") or ""), "1")

        gk_player.set_next_optional_decision("EYE_OF_THE_AUGURIUM_STRATAGEM_DISCOUNT", True)
        second = gk_player.apply_stratagem_cp_cost(stratagem, target_unit=bearer)
        self.assertTrue(bool(second.get("denied", False)))
        self.assertIn("already used this turn", str(second.get("reason", "") or "").lower())

        game.turn = 2
        gk_player.stratagems._used_this_turn["OVERWATCH"] = True
        gk_player.set_next_optional_decision("EYE_OF_THE_AUGURIUM_STRATAGEM_DISCOUNT", True)
        third = gk_player.apply_stratagem_cp_cost(stratagem, target_unit=bearer)
        self.assertFalse(bool(third.get("denied", False)))
        self.assertEqual(int(third.get("cost", -1)), 0)
        self.assertTrue(bool(third.get("eye_of_the_augurium_use", False)))
        self.assertEqual(str(bearer.special_rules.get("eye_of_the_augurium_used_battle_round", "") or ""), "2")

    def test_eye_of_the_augurium_allows_heroic_intervention_repeat_for_zero_cp(self):
        game, gk_army, _enemy_army, gk_player, _enemy_player = _build_game()
        bearer = _make_unit(
            "Brotherhood Champion",
            keywords=["INFANTRY", "CHARACTER"],
            faction_keywords=["GREY KNIGHTS"],
        )
        other = _make_unit(
            "Strike Squad",
            keywords=["INFANTRY"],
            faction_keywords=["GREY KNIGHTS"],
        )
        gk_army.add_unit(bearer)
        gk_army.add_unit(other)
        _apply_enhancement(bearer)

        manager = gk_player.stratagems
        manager._used_stratagems_this_phase.add("HEROIC INTERVENTION")
        manager._record_heroic_intervention_use(other)
        self.assertTrue(bool(manager._heroic_intervention_repeat_allowed(target_unit=bearer)))
        self.assertFalse(bool(manager._heroic_intervention_repeat_allowed(target_unit=other)))

        heroic = _heroic_intervention_stratagem()
        gk_player.set_next_optional_decision("EYE_OF_THE_AUGURIUM_STRATAGEM_DISCOUNT", True)
        applied = gk_player.apply_stratagem_cp_cost(heroic, target_unit=bearer)
        self.assertFalse(bool(applied.get("denied", False)))
        self.assertEqual(int(applied.get("cost", -1)), 0)
        self.assertTrue(bool(applied.get("eye_of_the_augurium_use", False)))
        self.assertEqual(str(bearer.special_rules.get("eye_of_the_augurium_used_battle_round", "") or ""), "1")
        self.assertFalse(bool(manager._heroic_intervention_repeat_allowed(target_unit=bearer)))

        game.turn = 2
        self.assertTrue(bool(manager._heroic_intervention_repeat_allowed(target_unit=bearer)))


if __name__ == "__main__":
    unittest.main()
