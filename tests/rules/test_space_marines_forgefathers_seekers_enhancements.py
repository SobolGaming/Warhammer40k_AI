import unittest

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import AttackResult, Wargear


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
        self.datasheets_abilities = []
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
        )
    )


def _build_game(detachment_type: str = "Forgefather's Seekers"):
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


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    bodyguard.attached_leaders = [leader]
    leader.attached_to = bodyguard
    for unit in (bodyguard, leader):
        invalidate = getattr(unit, "_invalidate_ability_cache", None)
        if callable(invalidate):
            invalidate()


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str) -> None:
    Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="SM",
        detachment="Forgefather's Seekers",
        points=15,
        description="",
    ).apply_to_unit(unit)


def _make_profile(*, is_melee: bool, attacks: str = "1", strength: str = "4", damage: str = "1", description: str = ""):
    data = {
        "name": "Test Weapon",
        "type": "Melee" if is_melee else "Ranged",
        "range": "Melee" if is_melee else "24",
        "A": str(attacks),
        "BS_WS": "3+",
        "S": str(strength),
        "AP": "0",
        "D": str(damage),
        "description": str(description or ""),
    }
    return Wargear(data).profiles["default"]


def _make_attack_result(profile, attacker, target_unit):
    return AttackResult(
        weapon_name=profile.name,
        attacker_name=getattr(attacker, "name", "Attacker"),
        target_unit_name=getattr(target_unit, "name", "Target"),
        attacks_rolled=0,
        attacks_dice_expression=str(profile.attacks),
        attacks_dice_rolls=[],
        attacks_special_modifiers=[],
        hit_results=[],
        wound_results=[],
        save_results=[],
        damage_results=[],
        hazardous_roll=None,
        hazardous_damage=0,
        total_hits=0,
        total_wounds=0,
        total_saves_failed=0,
        total_damage_dealt=0,
        models_killed=0,
    )


class TestSpaceMarinesForgefathersSeekersEnhancements(unittest.TestCase):
    def test_forgefathers_enhancement_descriptors_exist(self):
        expected = {
            "000010368002": ("Immolator", "bearer_unit_torrent_attacks_bonus"),
            "000010368003": ("War-tempered Artifice", "bearer_melee_strength_bonus"),
            "000010368004": ("Forged in Battle", "leading_unit_unmodified_six_once_per_turn"),
            "000010368005": (
                "Adamantine Mantle",
                "bearer_allocated_damage_reduction_with_melta_torrent_set_one",
            ),
        }
        for enhancement_id, (name, effect) in expected.items():
            desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
            self.assertIsNotNone(desc)
            self.assertEqual(str(getattr(desc, "name", "") or ""), name)
            self.assertEqual(str(getattr(desc, "effect", "") or ""), effect)

    def test_immolator_adds_one_attack_to_torrent_weapons_in_bearer_unit_while_bearer_alive(self):
        _game, sm_army, enemy_army = _build_game()
        leader = _make_unit(
            "Captain",
            keywords=["CHARACTER", "INFANTRY"],
            attached_to=["INFANTRY_BODYGUARD"],
        )
        bodyguard = _make_unit("Intercessor Squad", keywords=["INFANTRY"])
        enemy = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        sm_army.add_unit(leader)
        sm_army.add_unit(bodyguard)
        enemy_army.add_unit(enemy)
        _attach_leader(bodyguard, leader)
        _apply_enhancement(leader, enhancement_id="000010368002", enhancement_name="Immolator")

        torrent_profile = _make_profile(is_melee=False, attacks="1", description="Torrent")
        attack_result = _make_attack_result(torrent_profile, bodyguard.models[0], enemy)
        count_live = torrent_profile._resolve_attack_count(
            enemy,
            bodyguard.models[0],
            attack_result,
            publish_roll_event=False,
        )
        self.assertEqual(int(count_live.num_attacks), 2)

        leader.models[0].wounds = 0
        attack_result_dead = _make_attack_result(torrent_profile, bodyguard.models[0], enemy)
        count_dead = torrent_profile._resolve_attack_count(
            enemy,
            bodyguard.models[0],
            attack_result_dead,
            publish_roll_event=False,
        )
        self.assertEqual(int(count_dead.num_attacks), 1)

    def test_war_tempered_artifice_applies_plus_three_strength_to_bearer_melee_weapons(self):
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
            enhancement_id="000010368003",
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

    def test_forged_in_battle_adds_once_per_turn_hit_or_save_unmodified_six_spec(self):
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
            enhancement_id="000010368004",
            enhancement_name="Forged in Battle",
        )

        specs = list(bodyguard.leading_unmodified_six_specs() or [])
        forged = [s for s in specs if str(s.get("source", "") or "") == "Forged in Battle"]
        self.assertEqual(len(forged), 1)
        spec = forged[0]
        self.assertEqual(str(spec.get("usage_limit", "") or ""), "turn")
        self.assertEqual(tuple(spec.get("allowed_roll_types", ()) or ()), ("hit", "save"))

    def test_adamantine_mantle_reduces_damage_and_sets_melta_to_one_for_bearer(self):
        _game, sm_army, enemy_army = _build_game()
        bearer_unit = _make_unit("Captain", keywords=["CHARACTER", "INFANTRY"], wounds=12)
        attacker_unit = _make_unit("Enemy", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        sm_army.add_unit(bearer_unit)
        enemy_army.add_unit(attacker_unit)
        _apply_enhancement(
            bearer_unit,
            enhancement_id="000010368005",
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
        melta_profile._damage_target_with_tracking(
            target,
            attacker,
            {"mortal_wound": False},
            game_map=None,
        )
        self.assertEqual(int(base_wounds - int(target.wounds)), 1)


if __name__ == "__main__":
    unittest.main()
