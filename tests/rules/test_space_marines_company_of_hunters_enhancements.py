import unittest

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Space Marines",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        wounds: int = 4,
    ):
        self.id = ""
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            faction_keywords = ["ADEPTUS ASTARTES"] if faction_name == "Space Marines" else [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
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
    faction_name: str = "Space Marines",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: int = 4,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
        )
    )


def _build_game(detachment_type: str = "Company of Hunters"):
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    sm_army = Army.with_detachment("Space Marines", detachment_type)
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", control=PlayerControl.REMOTE, army=sm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    return game, sm_army, enemy_army


def _model_is_alive(model) -> bool:
    alive_attr = getattr(model, "is_alive", False)
    return bool(alive_attr() if callable(alive_attr) else alive_attr)


def _bearer_model(unit: Unit):
    bearer_id = str(getattr(unit, "special_rules", {}).get("enhancement_bearer_model_id", "") or "")
    for model in list(getattr(unit, "models", []) or []):
        if str(get_entity_id(model) or "") == bearer_id:
            return model
    for model in list(getattr(unit, "models", []) or []):
        if _model_is_alive(model):
            return model
    return None


class TestSpaceMarinesCompanyOfHuntersEnhancements(unittest.TestCase):
    def test_company_of_hunters_enhancement_descriptors_exist(self):
        expected = {
            "000008778002": ("Master-crafted Weapon", "grant_precision_to_bearer_melee_weapons"),
            "000008778003": ("Mounted Strategist", "reroll_advance_and_charge_rolls_for_bearer_unit"),
            "000008778004": (
                "Master of Manoeuvre",
                "ignore_strategic_reserves_points_limit_and_add_setup_round_for_bearer_unit",
            ),
            "000008778005": ("Recon Hunter", "grant_scouts_to_bearer_unit"),
        }
        for enhancement_id, (name, effect) in expected.items():
            desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
            self.assertIsNotNone(desc)
            self.assertEqual(str(getattr(desc, "name", "") or ""), name)
            self.assertEqual(str(getattr(desc, "effect", "") or ""), effect)

    def test_master_crafted_weapon_grants_precision_to_bearer_melee_weapons(self):
        game, sm_army, _enemy_army = _build_game()
        bearer_unit = _make_unit(
            "Ravenwing Champion",
            keywords=["ADEPTUS ASTARTES", "MOUNTED", "CHARACTER"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
        )
        sm_army.add_unit(bearer_unit)
        bearer_unit.deployed = True
        game.map.units = [bearer_unit]
        game.rebuild_entity_registry()

        Enhancement(
            id="000008778002",
            name="Master-crafted Weapon",
            faction_id="SM",
            detachment="Company of Hunters",
            points=15,
            description="",
        ).apply_to_unit(bearer_unit)

        sr = getattr(bearer_unit, "special_rules", {})
        self.assertTrue(bool(sr.get("enhancement_master_crafted_weapon")))
        self.assertTrue(bool(sr.get("enhancement_bearer_melee_precision")))

    def test_mounted_strategist_grants_reroll_advance_and_charge_while_bearer_alive(self):
        game, sm_army, _enemy_army = _build_game()
        bearer_unit = _make_unit(
            "Ravenwing Knights",
            keywords=["ADEPTUS ASTARTES", "MOUNTED"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=2,
            wounds=4,
        )
        sm_army.add_unit(bearer_unit)
        bearer_unit.deployed = True
        game.map.units = [bearer_unit]
        game.rebuild_entity_registry()

        self.assertFalse(bool(bearer_unit.can_reroll_advance_roll()))
        self.assertFalse(bool(bearer_unit.can_reroll_charge_roll()))

        Enhancement(
            id="000008778003",
            name="Mounted Strategist",
            faction_id="SM",
            detachment="Company of Hunters",
            points=20,
            description="",
        ).apply_to_unit(bearer_unit)

        self.assertTrue(bool(bearer_unit.can_reroll_advance_roll()))
        self.assertTrue(bool(bearer_unit.can_reroll_charge_roll()))

        bearer = _bearer_model(bearer_unit)
        self.assertIsNotNone(bearer)
        bearer.take_damage(int(getattr(bearer, "wounds", 0) or 0), game_map=game.map)

        self.assertFalse(bool(bearer_unit.can_reroll_advance_roll()))
        self.assertFalse(bool(bearer_unit.can_reroll_charge_roll()))

    def test_master_of_manoeuvre_exempts_strategic_points_and_grants_round_bonus(self):
        game, sm_army, _enemy_army = _build_game()
        sm_army.points_limit = 200
        reserve_unit = _make_unit(
            "Ravenwing Command Squad",
            keywords=["ADEPTUS ASTARTES", "MOUNTED", "CHARACTER"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=2,
            wounds=4,
        )
        line_unit = _make_unit(
            "Intercessors",
            keywords=["ADEPTUS ASTARTES", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
            wounds=4,
        )
        sm_army.add_unit(reserve_unit)
        sm_army.add_unit(line_unit)
        reserve_unit.deployed = True
        line_unit.deployed = True
        game.map.units = [reserve_unit, line_unit]
        game.rebuild_entity_registry()

        reserve_id = str(get_entity_id(reserve_unit) or "")
        line_id = str(get_entity_id(line_unit) or "")
        decisions = {
            reserve_id: "strategic_reserves",
            line_id: "deploy",
        }
        before = sm_army.validate_reserves_decisions(decisions)
        self.assertFalse(bool(before.get("valid")))
        self.assertTrue(any("Strategic Reserves" in str(err) for err in list(before.get("errors", []) or [])))

        Enhancement(
            id="000008778004",
            name="Master of Manoeuvre",
            faction_id="SM",
            detachment="Company of Hunters",
            points=15,
            description="",
        ).apply_to_unit(reserve_unit)

        after = sm_army.validate_reserves_decisions(decisions)
        self.assertTrue(bool(after.get("valid")))
        self.assertEqual(int(after.get("strategic_points", 0) or 0), 0)

        reserve_unit.reserve_status = "strategic_reserves"
        reserve_unit._started_in_reserves = True
        self.assertTrue(bool(reserve_unit.can_arrive_from_reserves(1)))
        self.assertEqual(int(reserve_unit.get_strategic_reserves_setup_turn(current_turn=1)), 2)

    def test_recon_hunter_grants_scouts_nine_to_bearer_unit(self):
        game, sm_army, _enemy_army = _build_game()
        bearer_unit = _make_unit(
            "Ravenwing Outriders",
            keywords=["ADEPTUS ASTARTES", "MOUNTED"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=2,
            wounds=4,
        )
        sm_army.add_unit(bearer_unit)
        bearer_unit.deployed = True
        game.map.units = [bearer_unit]
        game.rebuild_entity_registry()

        Enhancement(
            id="000008778005",
            name="Recon Hunter",
            faction_id="SM",
            detachment="Company of Hunters",
            points=10,
            description="",
        ).apply_to_unit(bearer_unit)

        has_scout, distance = bearer_unit.has_scout()
        self.assertTrue(bool(has_scout))
        self.assertEqual(int(distance), 9)


if __name__ == "__main__":
    unittest.main()
