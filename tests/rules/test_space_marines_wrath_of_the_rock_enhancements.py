import unittest
from types import SimpleNamespace
from unittest.mock import patch

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
        faction_name: str = "Space Marines",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        objective_control: int = 1,
        wounds: int = 4,
        toughness: int = 4,
        leadership: int = 7,
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
                "T": str(int(toughness)),
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": str(int(leadership)),
                "OC": str(int(objective_control)),
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
    objective_control: int = 1,
    wounds: int = 4,
    toughness: int = 4,
    leadership: int = 7,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            objective_control=objective_control,
            wounds=wounds,
            toughness=toughness,
            leadership=leadership,
        )
    )


def _build_game(detachment_type: str = "Wrath of the Rock"):
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    sm_army = Army("Space Marines", detachment_type)
    sm_army.faction_id = "SM"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", control=PlayerControl.REMOTE, army=sm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    return game, sm_army, enemy_army


def _make_melee_profile(*, strength: int = 5, ap: int = -1, damage: int = 1):
    parent = SimpleNamespace(name="Relic Blade", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        profile_name="Melee",
        wargear_data={
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": str(int(strength)),
            "AP": str(int(ap)),
            "D": str(int(damage)),
            "description": "",
        },
        parent_wargear=parent,
    )


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


def _bearer_model(unit: Unit):
    bearer_id = str(getattr(unit, "special_rules", {}).get("enhancement_bearer_model_id", "") or "")
    for model in list(getattr(unit, "models", []) or []):
        entity_id = str(get_entity_id(model) or "").strip()
        local_id = str(getattr(model, "id", getattr(model, "_id", "")) or "").strip()
        if bearer_id and bearer_id in {entity_id, local_id}:
            return model
    for model in list(getattr(unit, "models", []) or []):
        alive = getattr(model, "is_alive", False)
        if bool(alive() if callable(alive) else alive):
            return model
    return None


class TestSpaceMarinesWrathOfTheRockEnhancements(unittest.TestCase):
    def test_wrath_of_the_rock_enhancement_descriptors_exist(self):
        expected = {
            "000010155002": ("Tempered in Battle (Aura)", "aura_reroll_battleshock_and_leadership_tests"),
            "000010155003": ("Ancient Weapons", "bearer_melee_strength_ap_damage_bonus"),
            "000010155004": ("Deathwing Assault", "strategic_reserves_setup_round_bonus_for_deep_strike"),
            "000010155005": ("Lord of the Ravenwing", "bearer_unit_reroll_advance_and_charge"),
        }
        for enhancement_id, (name, effect) in expected.items():
            desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
            self.assertIsNotNone(desc)
            self.assertEqual(str(getattr(desc, "name", "") or ""), name)
            self.assertEqual(str(getattr(desc, "effect", "") or ""), effect)

    def test_tempered_in_battle_grants_nearby_rerolls_for_battleshock_and_leadership(self):
        game, sm_army, _enemy_army = _build_game()
        source_unit = _make_unit(
            "Deathwing Chaplain",
            keywords=["CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
            wounds=5,
            leadership=7,
        )
        target_unit = _make_unit(
            "Intercessors",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
            wounds=4,
            leadership=7,
        )
        sm_army.add_unit(source_unit)
        sm_army.add_unit(target_unit)
        source_unit.deployed = True
        target_unit.deployed = True
        game.map.units = [source_unit, target_unit]
        game.rebuild_entity_registry()

        Enhancement(
            id="000010155002",
            name="Tempered in Battle (Aura)",
            faction_id="SM",
            detachment="Wrath of the Rock",
            points=25,
            description="",
        ).apply_to_unit(source_unit)

        bearer = _bearer_model(source_unit)
        self.assertIsNotNone(bearer)
        bearer.set_location(0.0, 0.0, 0.0, 0.0)
        target_unit.models[0].set_location(2.0, 0.0, 0.0, 0.0)

        mgr = sm_army.space_marines_detachments
        near_sources = mgr.wrath_of_the_rock_tempered_in_battle_reroll_sources(target_unit, game=game)
        self.assertIn("Tempered in Battle (Aura)", near_sources)

        with patch(
            "warhammer40k_ai.units.unit_mixins.state_attachment_mixin.get_roll",
            side_effect=[11, 6],
        ):
            self.assertTrue(bool(target_unit.pass_leadership_check()))

        target_unit.models[0].set_location(20.0, 0.0, 0.0, 0.0)
        far_sources = mgr.wrath_of_the_rock_tempered_in_battle_reroll_sources(target_unit, game=game)
        self.assertEqual(far_sources, [])
        with patch("warhammer40k_ai.units.unit_mixins.state_attachment_mixin.get_roll", return_value=11):
            self.assertFalse(bool(target_unit.pass_leadership_check()))

    def test_ancient_weapons_improves_bearer_melee_strength_ap_and_damage(self):
        game, sm_army, enemy_army = _build_game()
        source_unit = _make_unit(
            "Deathwing Captain",
            keywords=["CHARACTER", "DEATHWING", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
            wounds=6,
            leadership=6,
        )
        target_unit = _make_unit(
            "Enemy Elite",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            model_count=1,
            wounds=5,
            toughness=7,
            leadership=7,
        )
        sm_army.add_unit(source_unit)
        enemy_army.add_unit(target_unit)
        source_unit.deployed = True
        target_unit.deployed = True
        game.map.units = [source_unit, target_unit]
        game.rebuild_entity_registry()

        Enhancement(
            id="000010155003",
            name="Ancient Weapons",
            faction_id="SM",
            detachment="Wrath of the Rock",
            points=30,
            description="",
        ).apply_to_unit(source_unit)

        bearer = _bearer_model(source_unit)
        self.assertIsNotNone(bearer)
        profile = _make_melee_profile(strength=5, ap=-1, damage=1)

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=4):
            wound_result = profile._wound_target_with_tracking(
                target_unit,
                bearer,
                {"_aura_attack_mods": _aura_stub()},
            )
        self.assertTrue(bool(wound_result.get("wound")))
        self.assertIn("+2S from Enhancement bearer (melee)", list(wound_result.get("modifiers", []) or []))

        effective_ap = int(profile.get_effective_ap(bearer, target_unit))
        self.assertEqual(effective_ap, -2)

        damage_result = profile._damage_target_with_tracking(
            target_unit.models[0],
            bearer,
            {},
            game_map=game.map,
        )
        self.assertIn(
            "Enhancement bearer +1D (melee)",
            list(damage_result.get("special_effects", []) or []),
        )

    def test_wrath_of_the_rock_deathwing_assault_allows_first_turn_reserves_arrival(self):
        game, sm_army, _enemy_army = _build_game()
        unit = _make_unit(
            "Deathwing Knights",
            keywords=["DEATHWING", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
            wounds=4,
        )
        sm_army.add_unit(unit)
        unit.deployed = False
        unit.set_reserve_status("strategic_reserves")
        unit._started_in_reserves = True
        unit.has_deep_strike = lambda: True
        game.map.units = []
        game.rebuild_entity_registry()

        Enhancement(
            id="000010155004",
            name="Deathwing Assault",
            faction_id="SM",
            detachment="Wrath of the Rock",
            points=25,
            description="",
        ).apply_to_unit(unit)

        self.assertEqual(int(unit._strategic_reserves_round_bonus() or 0), 1)
        self.assertTrue(bool(unit.can_arrive_from_reserves(current_turn=1)))

        unit.has_deep_strike = lambda: False
        self.assertEqual(int(unit._strategic_reserves_round_bonus() or 0), 0)

    def test_lord_of_the_ravenwing_grants_advance_and_charge_rerolls(self):
        _game, sm_army, _enemy_army = _build_game()
        unit = _make_unit(
            "Ravenwing Captain",
            keywords=["CHARACTER", "RAVENWING", "MOUNTED"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
            wounds=6,
        )
        sm_army.add_unit(unit)
        unit.deployed = True

        Enhancement(
            id="000010155005",
            name="Lord of the Ravenwing",
            faction_id="SM",
            detachment="Wrath of the Rock",
            points=20,
            description="",
        ).apply_to_unit(unit)

        self.assertTrue(bool(unit.can_reroll_advance_roll()))
        self.assertTrue(bool(unit.can_reroll_charge_roll()))


if __name__ == "__main__":
    unittest.main()
