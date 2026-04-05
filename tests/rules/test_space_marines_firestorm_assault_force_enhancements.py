import unittest

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Space Marines",
        keywords=None,
        faction_keywords=None,
        toughness: int = 4,
        wounds: int = 6,
        attached_to=None,
        abilities=None,
    ):
        self.id = ""
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            faction_keywords = ["ADEPTUS ASTARTES"] if faction_name == "Space Marines" else [str(faction_name).upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": str(int(toughness)),
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
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = list(attached_to or [])
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Space Marines",
    keywords=None,
    faction_keywords=None,
    toughness: int = 4,
    wounds: int = 6,
    attached_to=None,
    abilities=None,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            toughness=toughness,
            wounds=wounds,
            attached_to=attached_to,
            abilities=abilities,
        )
    )


def _build_game(detachment_type: str = "Firestorm Assault Force"):
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


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    bodyguard.attached_leaders = [leader]
    leader.attached_to = bodyguard
    for unit in (bodyguard, leader):
        invalidate = getattr(unit, "_invalidate_ability_cache", None)
        if callable(invalidate):
            invalidate()


def _detach_leader(bodyguard: Unit, leader: Unit) -> None:
    bodyguard.attached_leaders = []
    leader.attached_to = None
    for unit in (bodyguard, leader):
        invalidate = getattr(unit, "_invalidate_ability_cache", None)
        if callable(invalidate):
            invalidate()


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str) -> None:
    Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="SM",
        detachment="Firestorm Assault Force",
        points=15,
        description="",
    ).apply_to_unit(unit)


def _make_profile(*, is_melee: bool, strength: str = "4", damage: str = "1", description: str = ""):
    data = {
        "name": "Test Weapon",
        "type": "Melee" if is_melee else "Ranged",
        "range": "Melee" if is_melee else "24",
        "A": "1",
        "BS_WS": "3+",
        "S": str(strength),
        "AP": "0",
        "D": str(damage),
        "description": str(description or ""),
    }
    return Wargear(data).profiles["default"]


class TestSpaceMarinesFirestormAssaultForceEnhancements(unittest.TestCase):
    def test_firestorm_enhancement_descriptors_exist(self):
        expected = {
            "000008482002": (
                "Champion of Humanity",
                "ignore_characteristic_and_roll_modifiers_except_save_while_leading",
            ),
            "000008482003": ("War-tempered Artifice", "bearer_melee_strength_bonus"),
            "000008482004": ("Forged in Battle", "leading_unit_unmodified_six_once_per_turn"),
            "000008482005": (
                "Adamantine Mantle",
                "bearer_allocated_damage_reduction_with_melta_torrent_set_one",
            ),
        }
        for enhancement_id, (name, effect) in expected.items():
            desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
            self.assertIsNotNone(desc)
            self.assertEqual(str(getattr(desc, "name", "") or ""), name)
            self.assertEqual(str(getattr(desc, "effect", "") or ""), effect)

    def test_champion_of_humanity_enables_hit_and_wound_modifier_ignore_while_leading(self):
        _game, sm_army, enemy_army = _build_game()
        leader = _make_unit(
            "Captain",
            keywords=["CHARACTER", "TACTICUS", "INFANTRY"],
            attached_to=["INFANTRY_BODYGUARD"],
        )
        bodyguard = _make_unit("Intercessor Squad", keywords=["INFANTRY"])
        enemy = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        sm_army.add_unit(leader)
        sm_army.add_unit(bodyguard)
        enemy_army.add_unit(enemy)
        _attach_leader(bodyguard, leader)
        _apply_enhancement(
            leader,
            enhancement_id="000008482002",
            enhancement_name="Champion of Humanity",
        )

        self.assertTrue(bool(bodyguard._firestorm_champion_of_humanity_ignore_modifiers_active(kind="move")))
        self.assertTrue(bool(bodyguard._firestorm_champion_of_humanity_ignore_modifiers_active(kind="advance")))
        self.assertTrue(bool(bodyguard._firestorm_champion_of_humanity_ignore_modifiers_active(kind="charge")))

        profile = _make_profile(is_melee=False)
        hit_rule = profile._ignore_hit_modifier_rule(bodyguard.models[0], target_unit=enemy)
        wound_rule = profile._ignore_wound_modifier_rule(bodyguard.models[0])
        self.assertIsNotNone(hit_rule)
        self.assertIsNotNone(wound_rule)
        self.assertIn("Champion of Humanity", str(hit_rule.get("name", "") or ""))
        self.assertIn("Champion of Humanity", str(wound_rule.get("name", "") or ""))

    def test_champion_of_humanity_inactive_when_bearer_not_leading(self):
        _game, sm_army, _enemy_army = _build_game()
        leader = _make_unit("Captain", keywords=["CHARACTER", "TACTICUS", "INFANTRY"])
        sm_army.add_unit(leader)
        _apply_enhancement(
            leader,
            enhancement_id="000008482002",
            enhancement_name="Champion of Humanity",
        )

        self.assertFalse(bool(leader._firestorm_champion_of_humanity_ignore_modifiers_active(kind="move")))
        profile = _make_profile(is_melee=False)
        self.assertIsNone(profile._ignore_hit_modifier_rule(leader.models[0], target_unit=None))
        self.assertIsNone(profile._ignore_wound_modifier_rule(leader.models[0]))

    def test_war_tempered_artifice_is_bearer_only_melee_strength_plus_three(self):
        _game, sm_army, enemy_army = _build_game()
        leader = _make_unit(
            "Captain",
            keywords=["CHARACTER", "INFANTRY"],
            attached_to=["INFANTRY_BODYGUARD"],
        )
        bodyguard = _make_unit("Intercessor Squad", keywords=["INFANTRY"])
        enemy = _make_unit("Enemy Elite", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"], toughness=7)
        sm_army.add_unit(leader)
        sm_army.add_unit(bodyguard)
        enemy_army.add_unit(enemy)
        _attach_leader(bodyguard, leader)
        _apply_enhancement(
            leader,
            enhancement_id="000008482003",
            enhancement_name="War-tempered Artifice",
        )

        melee = _make_profile(is_melee=True, strength="4", damage="1")
        bearer_wound = melee._wound_target_with_tracking(
            enemy,
            leader.models[0],
            {"distance_to_target": 1.0},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        other_wound = melee._wound_target_with_tracking(
            enemy,
            bodyguard.models[0],
            {"distance_to_target": 1.0},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(bool(bearer_wound.get("wound", False)))
        self.assertFalse(bool(other_wound.get("wound", False)))
        self.assertTrue(any("+3S from Enhancement bearer" in str(m) for m in list(bearer_wound.get("modifiers", []) or [])))

    def test_forged_in_battle_registers_once_per_turn_hit_or_save_unmodified_six_spec(self):
        _game, sm_army, _enemy_army = _build_game()
        leader = _make_unit(
            "Captain",
            keywords=["CHARACTER", "INFANTRY"],
            attached_to=["INFANTRY_BODYGUARD"],
        )
        bodyguard = _make_unit("Intercessor Squad", keywords=["INFANTRY"])
        sm_army.add_unit(leader)
        sm_army.add_unit(bodyguard)
        _attach_leader(bodyguard, leader)
        _apply_enhancement(
            leader,
            enhancement_id="000008482004",
            enhancement_name="Forged in Battle",
        )

        specs = list(bodyguard.leading_unmodified_six_specs() or [])
        forged = [s for s in specs if str(s.get("source", "") or "") == "Forged in Battle"]
        self.assertEqual(len(forged), 1)
        spec = forged[0]
        self.assertEqual(str(spec.get("usage_limit", "") or ""), "turn")
        self.assertEqual(tuple(spec.get("allowed_roll_types", ()) or ()), ("hit", "save"))
        self.assertTrue(bool(spec.get("requires_bearer_leading")))

        _detach_leader(bodyguard, leader)
        specs_detached = list(bodyguard.leading_unmodified_six_specs() or [])
        self.assertFalse(any(str(s.get("source", "") or "") == "Forged in Battle" for s in specs_detached))

    def test_adamantine_mantle_reduces_damage_and_sets_melta_or_torrent_to_one_for_bearer(self):
        _game, sm_army, enemy_army = _build_game()
        bearer_unit = _make_unit("Captain", keywords=["CHARACTER", "INFANTRY"], wounds=12)
        attacker_unit = _make_unit("Enemy", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        sm_army.add_unit(bearer_unit)
        enemy_army.add_unit(attacker_unit)
        _apply_enhancement(
            bearer_unit,
            enhancement_id="000008482005",
            enhancement_name="Adamantine Mantle",
        )

        target = bearer_unit.models[0]
        attacker = attacker_unit.models[0]
        base_wounds = int(target.wounds)

        normal_profile = _make_profile(is_melee=True, strength="6", damage="4")
        normal_profile._damage_target_with_tracking(
            target,
            attacker,
            {"mortal_wound": False},
            game_map=None,
        )
        self.assertEqual(int(base_wounds - int(target.wounds)), 3)

        target.wounds = base_wounds
        melta_profile = _make_profile(is_melee=False, strength="8", damage="4", description="Melta 2")
        melta_result = melta_profile._damage_target_with_tracking(
            target,
            attacker,
            {"mortal_wound": False},
            game_map=None,
        )
        self.assertEqual(int(base_wounds - int(target.wounds)), 1)
        self.assertTrue(any("Adamantine Mantle: Damage set to 1" in str(e) for e in list(melta_result.get("special_effects", []) or [])))


if __name__ == "__main__":
    unittest.main()
