import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.phase import BattleRoundPhases


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        keywords=None,
        faction_keywords=None,
        toughness: int = 4,
        save: str = "3",
    ):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": str(int(toughness)),
                "Sv": str(save),
                "W": "2",
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


class _MockObjective:
    def __init__(self, objective_id: str, *, controller=None):
        self.id = str(objective_id)
        self.name = f"Objective {objective_id}"
        self.location = SimpleNamespace(
            id=str(objective_id),
            name=f"Objective {objective_id}",
            controlling_player=controller,
            removed=False,
        )
        self.controlling_player = controller


def _make_unit(name, *, keywords=None, faction_keywords=None, toughness: int = 4, save: str = "3"):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        toughness=toughness,
        save=save,
    )
    return Unit(datasheet)


def _build_game(detachment_type: str = "Reclamation Force"):
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)
    game.turn = 1
    game.phase = BattleRoundPhases.SHOOTING_PHASE

    sm_army = Army("Space Marines", detachment_type)
    sm_army.faction_id = "SM"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    sm_player = Player("Space Marines", control=PlayerControl.REMOTE, army=sm_army)
    enemy_player = Player("Enemy", control=PlayerControl.LOCAL, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 1

    return game, sm_player, enemy_player, sm_army, enemy_army


def _make_melee_profile():
    from warhammer40k_ai.units.wargear import WargearProfile

    parent = SimpleNamespace(name="Chainsword", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        profile_name="Melee",
        wargear_data={
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def _make_ranged_profile(*, strength: int = 6):
    from warhammer40k_ai.units.wargear import WargearProfile

    parent = SimpleNamespace(name="Bolt Rifle", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        profile_name="Ranged",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": str(int(strength)),
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


class TestSpaceMarinesReclamationForce(unittest.TestCase):
    def test_oath_of_reclamation_melee_ap_bonus_applies_vs_targets_on_objectives(self):
        game, _sm_player, _enemy_player, sm_army, enemy_army = _build_game("Reclamation Force")
        attacker = _make_unit(
            "Intercessor Squad",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        target = _make_unit(
            "Enemy Unit",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        sm_army.add_unit(attacker)
        enemy_army.add_unit(target)
        attacker.deployed = True
        target.deployed = True
        target.is_within_any_objective_range = lambda game_map=None: True
        game.rebuild_entity_registry()

        profile = _make_melee_profile()
        self.assertEqual(profile.get_effective_ap(attacker.models[0], target), -1)

    def test_oath_of_reclamation_wound_penalty_applies_when_strength_exceeds_toughness(self):
        game, sm_player, enemy_player, sm_army, enemy_army = _build_game("Reclamation Force")
        defended_unit = _make_unit(
            "Wardens of Ultramar",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            toughness=4,
        )
        attacker = _make_unit(
            "Enemy Shooters",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            toughness=4,
        )
        sm_army.add_unit(defended_unit)
        enemy_army.add_unit(attacker)
        defended_unit.deployed = True
        attacker.deployed = True

        objective = _MockObjective("obj-alpha", controller=sm_player)
        game.map.objectives = [objective]
        defended_unit.is_within_objective_range = lambda loc: str(getattr(loc, "id", "")) == "obj-alpha"

        game.rebuild_entity_registry()
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 1
        game.event_system.publish("phase_start", player=enemy_player, phase=BattleRoundPhases.SHOOTING_PHASE)

        profile = _make_ranged_profile(strength=6)
        wound_result = profile._wound_target_with_tracking(
            defended_unit,
            attacker.models[0],
            {"distance_to_target": 12.0},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )

        mods = [str(value or "") for value in list(wound_result.get("modifiers", []) or [])]
        self.assertTrue(any("Oath of Reclamation" in mod for mod in mods))

    def test_oath_of_reclamation_wound_penalty_applies_for_titus_keyword(self):
        game, sm_player, enemy_player, sm_army, enemy_army = _build_game("Reclamation Force")
        defended_unit = _make_unit(
            "Captain Titus",
            keywords=["INFANTRY", "TITUS"],
            faction_keywords=["ADEPTUS ASTARTES"],
            toughness=4,
        )
        attacker = _make_unit(
            "Enemy Shooters",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            toughness=4,
        )
        sm_army.add_unit(defended_unit)
        enemy_army.add_unit(attacker)
        defended_unit.deployed = True
        attacker.deployed = True

        objective = _MockObjective("obj-beta", controller=sm_player)
        game.map.objectives = [objective]
        defended_unit.is_within_objective_range = lambda loc: str(getattr(loc, "id", "")) == "obj-beta"

        game.rebuild_entity_registry()
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 1
        game.event_system.publish("phase_start", player=enemy_player, phase=BattleRoundPhases.SHOOTING_PHASE)

        profile = _make_ranged_profile(strength=4)
        wound_result = profile._wound_target_with_tracking(
            defended_unit,
            attacker.models[0],
            {"distance_to_target": 12.0},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )

        mods = [str(value or "") for value in list(wound_result.get("modifiers", []) or [])]
        self.assertTrue(any("Oath of Reclamation" in mod for mod in mods))


if __name__ == "__main__":
    unittest.main()
