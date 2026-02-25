import types
import unittest

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


def _build_game(detachment_type: str = "Companions of Vehemence"):
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


def _make_melee_profile(*, ap: int = 0) -> WargearProfile:
    parent = types.SimpleNamespace(name="Astartes Blade", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        profile_name="Melee",
        wargear_data={
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": str(int(ap)),
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


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


def _first_alive_model(unit: Unit):
    for model in list(getattr(unit, "models", []) or []):
        if _model_is_alive(model):
            return model
    return None


class TestSpaceMarinesCompanionsOfVehemenceEnhancements(unittest.TestCase):
    def test_companions_of_vehemence_enhancement_descriptors_exist(self):
        expected = {
            "000010392002": ("Incendiary Animus", "melee_ap_bonus_for_bearer_unit"),
            "000010392003": ("Oathbound Exemplar", "advance_bonus_and_action_after_advance_for_bearer_unit"),
            "000010392004": ("Merciless Denunciation", "reroll_hit_rolls_for_bearer_unit_melee_attacks"),
            "000010392005": ("Zealous Vanguard", "grant_scouts_to_bearer_unit"),
        }
        for enhancement_id, (name, effect) in expected.items():
            desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
            self.assertIsNotNone(desc)
            self.assertEqual(str(getattr(desc, "name", "") or ""), name)
            self.assertEqual(str(getattr(desc, "effect", "") or ""), effect)

    def test_incendiary_animus_improves_bearer_unit_melee_ap(self):
        game, sm_army, enemy_army = _build_game()
        bearer_unit = _make_unit(
            "Chaplain and Retinue",
            keywords=["ADEPTUS ASTARTES", "INFANTRY", "CHARACTER"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=2,
            wounds=4,
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            model_count=1,
            wounds=4,
        )
        sm_army.add_unit(bearer_unit)
        enemy_army.add_unit(enemy)
        bearer_unit.deployed = True
        enemy.deployed = True
        game.map.units = [bearer_unit, enemy]
        game.rebuild_entity_registry()

        profile = _make_melee_profile(ap=0)
        attacker = bearer_unit.models[0]
        baseline_ap = int(profile.get_effective_ap(attacker, enemy))
        self.assertEqual(baseline_ap, 0)

        Enhancement(
            id="000010392002",
            name="Incendiary Animus",
            faction_id="SM",
            detachment="Companions of Vehemence",
            points=15,
            description="",
        ).apply_to_unit(bearer_unit)

        improved_ap = int(profile.get_effective_ap(attacker, enemy))
        self.assertEqual(improved_ap, -1)

        bearer = _bearer_model(bearer_unit)
        self.assertIsNotNone(bearer)
        bearer.take_damage(int(getattr(bearer, "wounds", 0) or 0), game_map=game.map)

        surviving_attacker = _first_alive_model(bearer_unit)
        self.assertIsNotNone(surviving_attacker)
        disabled_ap = int(profile.get_effective_ap(surviving_attacker, enemy))
        self.assertEqual(disabled_ap, 0)

    def test_oathbound_exemplar_adds_advance_bonus_and_allows_actions_after_advance(self):
        game, sm_army, _enemy_army = _build_game()
        bearer_unit = _make_unit(
            "Sword Brethren",
            keywords=["ADEPTUS ASTARTES", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=2,
            wounds=3,
        )
        sm_army.add_unit(bearer_unit)
        bearer_unit.deployed = True
        game.map.units = [bearer_unit]
        game.rebuild_entity_registry()

        Enhancement(
            id="000010392003",
            name="Oathbound Exemplar",
            faction_id="SM",
            detachment="Companions of Vehemence",
            points=20,
            description="",
        ).apply_to_unit(bearer_unit)

        modifiers = list(bearer_unit._collect_advance_roll_modifiers())
        self.assertIn((1, "Oathbound Exemplar"), modifiers)

        bearer_unit.round_state.advanced_this_round = True
        action_check = game._is_unit_eligible_to_start_action(bearer_unit)
        self.assertTrue(bool(action_check.get("valid")))

        bearer = _bearer_model(bearer_unit)
        self.assertIsNotNone(bearer)
        bearer.take_damage(int(getattr(bearer, "wounds", 0) or 0), game_map=game.map)

        modifiers_after = list(bearer_unit._collect_advance_roll_modifiers())
        self.assertNotIn((1, "Oathbound Exemplar"), modifiers_after)

        action_check_after = game._is_unit_eligible_to_start_action(bearer_unit)
        self.assertFalse(bool(action_check_after.get("valid")))

    def test_merciless_denunciation_grants_melee_hit_rerolls_for_bearer_unit(self):
        game, sm_army, _enemy_army = _build_game()
        bearer_unit = _make_unit(
            "Judiciar and Guard",
            keywords=["ADEPTUS ASTARTES", "INFANTRY", "CHARACTER"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=2,
            wounds=4,
        )
        sm_army.add_unit(bearer_unit)
        bearer_unit.deployed = True
        game.map.units = [bearer_unit]
        game.rebuild_entity_registry()

        Enhancement(
            id="000010392004",
            name="Merciless Denunciation",
            faction_id="SM",
            detachment="Companions of Vehemence",
            points=15,
            description="",
        ).apply_to_unit(bearer_unit)

        model = bearer_unit.models[0]
        melee_mods = bearer_unit.get_model_hit_reroll_modifiers(model=model, attack_type="melee")
        self.assertTrue(bool(melee_mods.get("reroll_hit_full")))
        self.assertTrue(
            any(
                "Merciless Denunciation" in reason
                for reason in list(melee_mods.get("reroll_hit_full_reasons", ()) or ())
            )
        )

        ranged_mods = bearer_unit.get_model_hit_reroll_modifiers(model=model, attack_type="ranged")
        self.assertFalse(bool(ranged_mods.get("reroll_hit_full")))

        bearer = _bearer_model(bearer_unit)
        self.assertIsNotNone(bearer)
        bearer.take_damage(int(getattr(bearer, "wounds", 0) or 0), game_map=game.map)

        surviving_model = _first_alive_model(bearer_unit)
        self.assertIsNotNone(surviving_model)
        melee_mods_after = bearer_unit.get_model_hit_reroll_modifiers(model=surviving_model, attack_type="melee")
        self.assertFalse(bool(melee_mods_after.get("reroll_hit_full")))

    def test_zealous_vanguard_grants_scouts_six_to_bearer_unit(self):
        game, sm_army, _enemy_army = _build_game()
        bearer_unit = _make_unit(
            "Marshal's Escort",
            keywords=["ADEPTUS ASTARTES", "INFANTRY", "CHARACTER"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=2,
            wounds=4,
        )
        sm_army.add_unit(bearer_unit)
        bearer_unit.deployed = True
        game.map.units = [bearer_unit]
        game.rebuild_entity_registry()

        Enhancement(
            id="000010392005",
            name="Zealous Vanguard",
            faction_id="SM",
            detachment="Companions of Vehemence",
            points=10,
            description="",
        ).apply_to_unit(bearer_unit)

        has_scout, distance = bearer_unit.has_scout()
        self.assertTrue(bool(has_scout))
        self.assertEqual(int(distance), 6)


if __name__ == "__main__":
    unittest.main()
