import unittest
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
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


def _build_game(detachment_type: str = "Bastion Task Force"):
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
    return game, sm_army, enemy_army, sm_player, enemy_player


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    leader.can_be_attached_to = [bodyguard.name]
    leader.attached_to = bodyguard
    bodyguard.attached_leaders = [leader]
    bodyguard._ability_cache = {}
    leader._ability_cache = {}


def _bearer_model(unit: Unit):
    bearer_id = str(getattr(unit, "special_rules", {}).get("enhancement_bearer_model_id", "") or "")
    for model in list(getattr(unit, "models", []) or []):
        if str(get_entity_id(model) or "") == bearer_id:
            return model
    for model in list(getattr(unit, "models", []) or []):
        if bool(getattr(model, "is_alive", False)):
            return model
    return None


def _make_melee_profile(ap: int = 0) -> WargearProfile:
    parent = SimpleNamespace(name="Astartes Chainsword", is_melee=lambda: True, is_ranged=lambda: False)
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


def _make_ranged_profile() -> WargearProfile:
    parent = SimpleNamespace(name="Bolt Rifle", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        profile_name="Ranged",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


class TestSpaceMarinesBastionTaskForceEnhancements(unittest.TestCase):
    def test_eye_of_the_primarch_grants_ranged_precision_to_bearer_and_battleline_models(self):
        game, sm_army, enemy_army, _sm_player, _enemy_player = _build_game()
        bodyguard = _make_unit(
            "Intercessors",
            keywords=["INFANTRY", "BATTLELINE"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=2,
            wounds=3,
        )
        leader = _make_unit(
            "Captain",
            keywords=["CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
            wounds=6,
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            model_count=1,
            wounds=6,
        )
        sm_army.add_unit(bodyguard)
        sm_army.add_unit(leader)
        enemy_army.add_unit(enemy)
        bodyguard.deployed = True
        leader.deployed = True
        enemy.deployed = True
        _attach_leader(bodyguard, leader)
        game.map.units = [bodyguard, leader, enemy]
        game.rebuild_entity_registry()

        Enhancement(
            id="000010676002",
            name="Eye of the Primarch",
            faction_id="SM",
            detachment="Bastion Task Force",
            points=20,
            description="",
        ).apply_to_unit(leader)

        battleline_model = bodyguard.models[0]
        bearer = _bearer_model(leader)
        self.assertIsNotNone(bearer)

        battleline_ranged_bonus = bodyguard.get_model_weapon_keyword_bonuses(
            attack_type="ranged",
            model=battleline_model,
            weapon_name="Bolt Rifle",
            target=enemy,
        )
        self.assertTrue(bool((battleline_ranged_bonus or {}).get("precision", False)))

        bearer_ranged_bonus = leader.get_model_weapon_keyword_bonuses(
            attack_type="ranged",
            model=bearer,
            weapon_name="Bolt Pistol",
            target=enemy,
        )
        self.assertTrue(bool((bearer_ranged_bonus or {}).get("precision", False)))

        battleline_melee_bonus = bodyguard.get_model_weapon_keyword_bonuses(
            attack_type="melee",
            model=battleline_model,
            weapon_name="Close Combat Weapon",
            target=enemy,
        )
        self.assertFalse(bool((battleline_melee_bonus or {}).get("precision", False)))

        bearer.take_damage(int(getattr(bearer, "wounds", 0) or 0), game_map=game.map)
        after_bearer_death = bodyguard.get_model_weapon_keyword_bonuses(
            attack_type="ranged",
            model=battleline_model,
            weapon_name="Bolt Rifle",
            target=enemy,
        )
        self.assertFalse(bool((after_bearer_death or {}).get("precision", False)))

    def test_hero_of_the_chapter_grants_battleline_while_bearer_leads(self):
        game, sm_army, _enemy_army, _sm_player, _enemy_player = _build_game()
        bodyguard = _make_unit(
            "Sternguard",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=2,
            wounds=3,
        )
        leader = _make_unit(
            "Captain",
            keywords=["CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
            wounds=6,
        )
        sm_army.add_unit(bodyguard)
        sm_army.add_unit(leader)
        bodyguard.deployed = True
        leader.deployed = True
        _attach_leader(bodyguard, leader)
        game.map.units = [bodyguard, leader]
        game.rebuild_entity_registry()

        Enhancement(
            id="000010676003",
            name="Hero of the Chapter",
            faction_id="SM",
            detachment="Bastion Task Force",
            points=10,
            description="",
        ).apply_to_unit(leader)

        self.assertTrue(bodyguard.has_keyword("BATTLELINE"))
        self.assertTrue(bodyguard.can_shoot_after_advance(_make_ranged_profile()))

        bearer = _bearer_model(leader)
        self.assertIsNotNone(bearer)
        bearer.take_damage(int(getattr(bearer, "wounds", 0) or 0), game_map=game.map)
        self.assertFalse(bodyguard.has_keyword("BATTLELINE"))
        self.assertFalse(bodyguard.can_shoot_after_advance(_make_ranged_profile()))

    def test_blades_of_valour_improves_melee_ap_for_bearer_and_battleline_models(self):
        game, sm_army, enemy_army, _sm_player, _enemy_player = _build_game()
        bodyguard = _make_unit(
            "Intercessors",
            keywords=["INFANTRY", "BATTLELINE"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=2,
            wounds=3,
        )
        leader = _make_unit(
            "Captain",
            keywords=["CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
            wounds=6,
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            model_count=1,
            wounds=6,
        )
        sm_army.add_unit(bodyguard)
        sm_army.add_unit(leader)
        enemy_army.add_unit(enemy)
        bodyguard.deployed = True
        leader.deployed = True
        enemy.deployed = True
        _attach_leader(bodyguard, leader)
        game.map.units = [bodyguard, leader, enemy]
        game.rebuild_entity_registry()

        Enhancement(
            id="000010676004",
            name="Blades of Valour",
            faction_id="SM",
            detachment="Bastion Task Force",
            points=25,
            description="",
        ).apply_to_unit(leader)

        melee_profile = _make_melee_profile(ap=0)
        battleline_model = bodyguard.models[0]
        bearer = _bearer_model(leader)
        self.assertIsNotNone(bearer)

        battleline_ap = int(melee_profile.get_effective_ap(attacker=battleline_model, target=enemy) or 0)
        bearer_ap = int(melee_profile.get_effective_ap(attacker=bearer, target=enemy) or 0)
        self.assertEqual(battleline_ap, -1)
        self.assertEqual(bearer_ap, -1)

        bearer.take_damage(int(getattr(bearer, "wounds", 0) or 0), game_map=game.map)
        after_bearer_death_ap = int(melee_profile.get_effective_ap(attacker=battleline_model, target=enemy) or 0)
        self.assertEqual(after_bearer_death_ap, 0)

    def test_bombast_omnivox_refunds_cp_with_battleline_bonus(self):
        game, sm_army, _enemy_army, sm_player, _enemy_player = _build_game()
        unit = _make_unit(
            "Captain",
            keywords=["CHARACTER", "INFANTRY", "BATTLELINE"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
            wounds=6,
        )
        sm_army.add_unit(unit)
        unit.deployed = True
        game.map.units = [unit]
        game.rebuild_entity_registry()

        Enhancement(
            id="000010676005",
            name="Bombast Omnivox",
            faction_id="SM",
            detachment="Bastion Task Force",
            points=15,
            description="",
        ).apply_to_unit(unit)

        sm_player.command_points = 1
        sm_player._pending_stratagem_target_unit_id = str(get_entity_id(unit) or "")
        sm_player._pending_stratagem_name = "Rapid Fire"
        with patch("warhammer40k_ai.utility.dice.get_roll", return_value=3):
            ok = bool(sm_player.spend_command_points(1, reason="Stratagem: Rapid Fire", source="stratagem"))
        self.assertTrue(ok)
        self.assertEqual(int(sm_player.command_points or 0), 1)

        bearer = _bearer_model(unit)
        self.assertIsNotNone(bearer)
        bearer.take_damage(int(getattr(bearer, "wounds", 0) or 0), game_map=game.map)

        sm_player.command_points = 1
        sm_player._pending_stratagem_target_unit_id = str(get_entity_id(unit) or "")
        sm_player._pending_stratagem_name = "Rapid Fire"
        with patch("warhammer40k_ai.utility.dice.get_roll", return_value=6):
            ok_after_death = bool(sm_player.spend_command_points(1, reason="Stratagem: Rapid Fire", source="stratagem"))
        self.assertTrue(ok_after_death)
        self.assertEqual(int(sm_player.command_points or 0), 0)


if __name__ == "__main__":
    unittest.main()
