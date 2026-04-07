import types
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.battlefield.map import Map
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Emperor's Children",
        faction_keywords=None,
        keywords=None,
        model_count: int = 1,
        movement: int = 6,
        leadership: int = 7,
        objective_control: int = 1,
        wounds: int = 2,
    ):
        self.id = ""
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            if faction_name == "Emperor's Children":
                faction_keywords = ["EMPEROR'S CHILDREN"]
            else:
                faction_keywords = [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": str(int(movement)),
                "T": "4",
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
    faction_name: str = "Emperor's Children",
    faction_keywords=None,
    keywords=None,
    movement: int = 6,
    leadership: int = 7,
    objective_control: int = 1,
    wounds: int = 2,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            faction_keywords=faction_keywords,
            keywords=keywords,
            movement=movement,
            leadership=leadership,
            objective_control=objective_control,
            wounds=wounds,
        )
    )


def _attach_leader(leader: Unit, bodyguard: Unit) -> None:
    bodyguard.attached_leaders = [leader]
    leader.attached_to = bodyguard
    leader.can_be_attached_to = [bodyguard.name]
    bodyguard._invalidate_ability_cache()
    leader._invalidate_ability_cache()


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


def _make_melee_profile():
    parent = SimpleNamespace(name="Blade", is_melee=lambda: True, is_ranged=lambda: False)
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


class TestEmperorsChildrenSlaaneshsChosenEnhancements(unittest.TestCase):
    def test_eager_to_prove_grants_charge_reroll_and_favoured_move_bonus(self):
        army = Army.with_detachment("Emperor's Children", detachment_type="Slaanesh's Chosen")
        army.faction_id = "EC"

        leader = _make_unit("Lord Exultant", keywords=["Character", "Infantry"], wounds=6)
        bodyguard = _make_unit("Noise Marines", keywords=["Infantry"], wounds=2)
        army.add_unit(leader)
        army.add_unit(bodyguard)
        _attach_leader(leader, bodyguard)

        Enhancement(
            id="000010018002",
            name="Eager to Prove",
            faction_id="EC",
            detachment="Slaanesh's Chosen",
            points=15,
            description="",
        ).apply_to_unit(leader)

        mgr = army.emperors_children
        mgr.favoured_champions_unit_id = ""
        self.assertEqual(int(bodyguard.get_effective_model_characteristic(bodyguard.models[0], "movement")), 6)

        mgr.favoured_champions_unit_id = str(bodyguard._id)
        self.assertEqual(int(bodyguard.get_effective_model_characteristic(bodyguard.models[0], "movement")), 8)

        target = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["Infantry"],
        )
        self.assertTrue(bodyguard.can_reroll_charge_roll(target_unit=target))

    def _setup_repulsed_by_weakness(self, *, favoured: bool):
        ec_army = Army.with_detachment("Emperor's Children", detachment_type="Slaanesh's Chosen")
        ec_army.faction_id = "EC"
        enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
        enemy_army.faction_id = "EN"

        trapper = _make_unit("Trapper", keywords=["Character", "Infantry"], wounds=6)
        runner = _make_unit(
            "Runner",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["Infantry"],
            wounds=6,
        )
        ec_army.add_unit(trapper)
        enemy_army.add_unit(runner)

        Enhancement(
            id="000010018003",
            name="Repulsed by Weakness",
            faction_id="EC",
            detachment="Slaanesh's Chosen",
            points=25,
            description="",
        ).apply_to_unit(trapper)

        trapper.deployed = True
        runner.deployed = True
        runner.models[0].set_location(10.0, 10.0, 0.0, 0.0)
        trapper.models[0].set_location(10.5, 10.0, 0.0, 0.0)

        if favoured:
            ec_army.emperors_children.favoured_champions_unit_id = str(trapper._id)
        else:
            ec_army.emperors_children.favoured_champions_unit_id = ""

        game_map = Map(60, 44)
        game_map.units = [runner, trapper]
        return runner, game_map

    def test_repulsed_by_weakness_forces_desperate_escape(self):
        runner, game_map = self._setup_repulsed_by_weakness(favoured=False)
        called = {"count": 0, "modifier": None}

        def _fake(self, game_map=None, *, roll_modifier=0, reason=None):
            called["count"] += 1
            called["modifier"] = int(roll_modifier or 0)
            return 0

        runner.take_desperate_escape_test = types.MethodType(_fake, runner)
        result = runner.fall_back((14.0, 10.0, 0.0), [], game_map)
        self.assertTrue(result)
        self.assertEqual(int(called["count"]), 1)
        self.assertEqual(int(called["modifier"]), 0)

    def test_repulsed_by_weakness_applies_favoured_penalty(self):
        runner, game_map = self._setup_repulsed_by_weakness(favoured=True)
        called = {"count": 0, "modifier": None}

        def _fake(self, game_map=None, *, roll_modifier=0, reason=None):
            called["count"] += 1
            called["modifier"] = int(roll_modifier or 0)
            return 0

        runner.take_desperate_escape_test = types.MethodType(_fake, runner)
        result = runner.fall_back((14.0, 10.0, 0.0), [], game_map)
        self.assertTrue(result)
        self.assertEqual(int(called["count"]), 1)
        self.assertEqual(int(called["modifier"]), -1)

    def test_proud_and_vainglorious_rerolls_leadership_and_battleshock_tests(self):
        game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
        army = Army.with_detachment("Emperor's Children", detachment_type="Slaanesh's Chosen")
        army.faction_id = "EC"
        enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
        enemy_army.faction_id = "EN"
        player = Player("P1", control=PlayerControl.REMOTE, army=army)
        enemy_player = Player("P2", control=PlayerControl.REMOTE, army=enemy_army)
        game.add_player(player)
        game.add_player(enemy_player)

        unit = _make_unit("Lord Exultant", keywords=["Character", "Infantry"], leadership=7, wounds=6)
        army.add_unit(unit)
        unit.deployed = True
        game.map.units = [unit]

        Enhancement(
            id="000010018004",
            name="Proud and Vainglorious",
            faction_id="EC",
            detachment="Slaanesh's Chosen",
            points=20,
            description="",
        ).apply_to_unit(unit)

        with patch("warhammer40k_ai.units.unit_mixins.state_attachment_mixin.get_roll", side_effect=[11, 6]):
            self.assertTrue(unit.pass_leadership_check())

        # Exercise local/manual battle-shock resolution path (not authoritative network dice flow).
        player.game = None
        with patch("warhammer40k_ai.units.unit_mixins.state_attachment_mixin.get_roll", side_effect=[11, 6]):
            unit.take_battle_shock_test(current_turn=1)
        self.assertFalse(unit.is_battle_shocked())

    def test_proud_and_vainglorious_adds_oc_when_favoured_champions(self):
        army = Army.with_detachment("Emperor's Children", detachment_type="Slaanesh's Chosen")
        army.faction_id = "EC"

        leader = _make_unit("Lord Exultant", keywords=["Character", "Infantry"], wounds=6)
        bodyguard = _make_unit("Noise Marines", keywords=["Infantry"], objective_control=1, wounds=2)
        army.add_unit(leader)
        army.add_unit(bodyguard)
        _attach_leader(leader, bodyguard)

        Enhancement(
            id="000010018004",
            name="Proud and Vainglorious",
            faction_id="EC",
            detachment="Slaanesh's Chosen",
            points=20,
            description="",
        ).apply_to_unit(leader)

        mgr = army.emperors_children
        mgr.favoured_champions_unit_id = ""
        self.assertEqual(int(bodyguard.get_effective_model_characteristic(bodyguard.models[0], "objective_control")), 1)

        mgr.favoured_champions_unit_id = str(bodyguard._id)
        self.assertEqual(int(bodyguard.get_effective_model_characteristic(bodyguard.models[0], "objective_control")), 2)

    def test_slayer_of_champions_grants_precision_and_character_target_strength_ap_bonus(self):
        army = Army.with_detachment("Emperor's Children", detachment_type="Slaanesh's Chosen")
        army.faction_id = "EC"
        attacker_unit = _make_unit("Lord Exultant", keywords=["Character", "Infantry"], wounds=6)
        army.add_unit(attacker_unit)

        Enhancement(
            id="000010018005",
            name="Slayer of Champions",
            faction_id="EC",
            detachment="Slaanesh's Chosen",
            points=15,
            description="",
        ).apply_to_unit(attacker_unit)

        target_character = _make_unit(
            "Enemy Character Unit",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["Character", "Infantry"],
            wounds=6,
        )
        target_other = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["Infantry"],
            wounds=6,
        )

        profile = _make_melee_profile()
        attacker_model = attacker_unit.models[0]

        attack_instance = {"_aura_attack_mods": _aura_stub()}
        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=4):
            profile._hit_target_with_tracking(target_character, attacker_model, attack_instance)
        self.assertTrue(bool(attack_instance.get("bonus_precision", False)))

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=4):
            wound_character = profile._wound_target_with_tracking(
                target_character,
                attacker_model,
                {"_aura_attack_mods": _aura_stub()},
            )
            wound_other = profile._wound_target_with_tracking(
                target_other,
                attacker_model,
                {"_aura_attack_mods": _aura_stub()},
            )

        self.assertTrue(any("Slayer of Champions" in str(m) for m in list(wound_character.get("modifiers", []) or [])))
        self.assertFalse(any("Slayer of Champions" in str(m) for m in list(wound_other.get("modifiers", []) or [])))
        self.assertEqual(int(profile.get_effective_ap(attacker_model, target_character)), -1)
        self.assertEqual(int(profile.get_effective_ap(attacker_model, target_other)), 0)


if __name__ == "__main__":
    unittest.main()
