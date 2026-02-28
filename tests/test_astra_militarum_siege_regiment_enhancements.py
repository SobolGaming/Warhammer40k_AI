import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.rules.voice_of_command import ORDER_MOVE, ORDER_TAKE_COVER
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import AttackResult, WargearProfile
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Astra Militarum",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        objective_control: int = 1,
        toughness: int = 4,
        wounds: int = 4,
        move: int = 6,
    ):
        self.id = ""
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            faction_keywords = ["ASTRA MILITARUM"] if faction_name == "Astra Militarum" else [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": str(int(move)),
                "T": str(int(toughness)),
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": "7",
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
    faction_name: str = "Astra Militarum",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    objective_control: int = 1,
    toughness: int = 4,
    wounds: int = 4,
    move: int = 6,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            objective_control=objective_control,
            toughness=toughness,
            wounds=wounds,
            move=move,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    am_army = Army("Astra Militarum", "Siege Regiment")
    am_army.faction_id = "AM"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    am_player = Player("Astra Militarum", control=PlayerControl.REMOTE, army=am_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(am_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.attacker_index = 0
    game.defender_index = 1
    game.turn = 1
    return game, am_army, enemy_army, am_player, enemy_player


def _set_unit_position(unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        if not bool(getattr(model, "is_alive", False)):
            continue
        model.set_location(float(x) + float(idx) * 0.1, float(y), 0.0, 0.0)
    unit.position = (float(x), float(y), 0.0)
    unit.deployed = True
    unit.reserve_status = "deployed"


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str) -> None:
    Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="AM",
        detachment="Siege Regiment",
        points=20,
        description="",
    ).apply_to_unit(unit)


def _find_bearer_model(unit: Unit):
    bearer_id = str(getattr(unit, "special_rules", {}).get("enhancement_bearer_model_id", "") or "")
    for model in list(getattr(unit, "models", []) or []):
        if str(get_entity_id(model) or "") == bearer_id:
            return model
    return None


def _make_pistol_profile(attacks: str = "1") -> WargearProfile:
    parent = type(
        "_ParentWargear",
        (),
        {
            "name": "Legacy Pistol",
            "is_melee": staticmethod(lambda: False),
            "is_ranged": staticmethod(lambda: True),
        },
    )()
    return WargearProfile(
        "Pistol Profile",
        wargear_data={
            "range": "12",
            "A": str(attacks),
            "BS_WS": "4+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "[PISTOL]",
        },
        parent_wargear=parent,
    )


def _make_attack_result(attacker_name: str, target_name: str) -> AttackResult:
    return AttackResult(
        weapon_name="Legacy Pistol",
        attacker_name=attacker_name,
        target_unit_name=target_name,
        attacks_rolled=0,
        attacks_dice_expression="1",
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


class TestAstraMilitarumSiegeRegimentEnhancements(unittest.TestCase):
    def test_siege_regiment_enhancement_descriptors_exist(self):
        expected = {
            "000009857002": ("Eager Advance", "grant_scouts"),
            "000009857003": ("Flash Grenades", "prevent_fire_overwatch_against_bearer_unit"),
            "000009857004": ("Legacy Sidearm", "add_pistol_attacks"),
            "000009857005": ("Stalwart's Honours", "also_apply_take_cover_order"),
        }
        for enhancement_id, (name, effect) in expected.items():
            desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
            self.assertIsNotNone(desc)
            self.assertEqual(str(getattr(desc, "name", "") or ""), name)
            self.assertEqual(str(getattr(desc, "effect", "") or ""), effect)

    def test_eager_advance_grants_scouts_only_while_bearer_is_leading_and_alive(self):
        game, am_army, _enemy_army, _am_player, _enemy_player = _build_game()
        officer = _make_unit(
            "Siege Officer",
            keywords=["INFANTRY", "CHARACTER", "OFFICER"],
            faction_keywords=["ASTRA MILITARUM"],
        )
        bodyguard = _make_unit(
            "Infantry Squad",
            keywords=["INFANTRY", "REGIMENT"],
            faction_keywords=["ASTRA MILITARUM"],
        )
        am_army.add_unit(officer)
        am_army.add_unit(bodyguard)
        _set_unit_position(officer, 0.0, 0.0)
        _set_unit_position(bodyguard, 3.0, 0.0)
        game.map.units = [officer, bodyguard]
        game.rebuild_entity_registry()

        _apply_enhancement(officer, enhancement_id="000009857002", enhancement_name="Eager Advance")
        has_scout_before, scout_distance_before = bodyguard.has_scout()
        self.assertFalse(has_scout_before)
        self.assertEqual(float(scout_distance_before), 0.0)

        bodyguard.attached_leaders = [officer]
        officer.attached_to = bodyguard
        has_scout, scout_distance = bodyguard.has_scout()
        self.assertTrue(has_scout)
        self.assertEqual(float(scout_distance), 6.0)

        bearer = _find_bearer_model(officer)
        self.assertIsNotNone(bearer)
        bearer.take_damage(int(getattr(bearer, "wounds", 0) or 0), game_map=game.map)
        has_scout_after, scout_distance_after = bodyguard.has_scout()
        self.assertFalse(has_scout_after)
        self.assertEqual(float(scout_distance_after), 0.0)

    def test_flash_grenades_prevents_overwatch_only_while_bearer_alive(self):
        game, am_army, enemy_army, _am_player, _enemy_player = _build_game()
        source = _make_unit(
            "Siege Officer",
            keywords=["INFANTRY", "CHARACTER", "OFFICER"],
            faction_keywords=["ASTRA MILITARUM"],
            model_count=2,
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        am_army.add_unit(source)
        enemy_army.add_unit(enemy)
        _set_unit_position(source, 0.0, 0.0)
        _set_unit_position(enemy, 8.0, 0.0)
        game.map.units = [source, enemy]
        game.rebuild_entity_registry()

        _apply_enhancement(source, enhancement_id="000009857003", enhancement_name="Flash Grenades")
        self.assertTrue(source.is_overwatch_prevented_against(enemy, game=game))

        bearer = _find_bearer_model(source)
        self.assertIsNotNone(bearer)
        bearer.take_damage(int(getattr(bearer, "wounds", 0) or 0), game_map=game.map)
        self.assertFalse(source.is_overwatch_prevented_against(enemy, game=game))

    def test_legacy_sidearm_adds_attacks_for_bearer_pistol_only(self):
        game, am_army, enemy_army, _am_player, _enemy_player = _build_game()
        source = _make_unit(
            "Siege Officer",
            keywords=["INFANTRY", "CHARACTER", "OFFICER"],
            faction_keywords=["ASTRA MILITARUM"],
            model_count=2,
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        am_army.add_unit(source)
        enemy_army.add_unit(enemy)
        _set_unit_position(source, 0.0, 0.0)
        _set_unit_position(enemy, 10.0, 0.0)
        game.map.units = [source, enemy]
        game.rebuild_entity_registry()

        _apply_enhancement(source, enhancement_id="000009857004", enhancement_name="Legacy Sidearm")
        bearer = _find_bearer_model(source)
        self.assertIsNotNone(bearer)
        non_bearer = next(model for model in list(source.models) if model is not bearer)
        profile = _make_pistol_profile(attacks="1")

        bearer_result = _make_attack_result("Bearer", "Enemy Unit")
        bearer_info = profile._resolve_attack_count(
            enemy,
            bearer,
            bearer_result,
            publish_roll_event=False,
        )
        self.assertEqual(int(bearer_info.num_attacks), 3)

        non_bearer_result = _make_attack_result("Non Bearer", "Enemy Unit")
        non_bearer_info = profile._resolve_attack_count(
            enemy,
            non_bearer,
            non_bearer_result,
            publish_roll_event=False,
        )
        self.assertEqual(int(non_bearer_info.num_attacks), 1)

    def test_stalwarts_honours_also_applies_take_cover_when_ordering_led_unit(self):
        game, am_army, _enemy_army, _am_player, _enemy_player = _build_game()
        issuing_officer = _make_unit(
            "Command Officer",
            keywords=["INFANTRY", "CHARACTER", "OFFICER"],
            faction_keywords=["ASTRA MILITARUM"],
        )
        stalwart_leader = _make_unit(
            "Siege Leader",
            keywords=["INFANTRY", "CHARACTER", "OFFICER"],
            faction_keywords=["ASTRA MILITARUM"],
        )
        bodyguard = _make_unit(
            "Regiment Bodyguard",
            keywords=["INFANTRY", "REGIMENT"],
            faction_keywords=["ASTRA MILITARUM"],
        )
        am_army.add_unit(issuing_officer)
        am_army.add_unit(stalwart_leader)
        am_army.add_unit(bodyguard)
        _set_unit_position(issuing_officer, 0.0, 0.0)
        _set_unit_position(stalwart_leader, 3.0, 0.0)
        _set_unit_position(bodyguard, 3.0, 0.0)
        bodyguard.attached_leaders = [stalwart_leader]
        stalwart_leader.attached_to = bodyguard
        game.map.units = [issuing_officer, stalwart_leader, bodyguard]
        game.rebuild_entity_registry()

        issuing_officer.possible_abilities = [
            SimpleNamespace(name="Voice of Command", description=""),
            SimpleNamespace(
                name="Orders",
                description="This OFFICER can issue 1 Order to REGIMENT units within 6\".",
            ),
        ]
        _apply_enhancement(
            stalwart_leader,
            enhancement_id="000009857005",
            enhancement_name="Stalwart's Honours",
        )

        voice = am_army.voice_of_command
        voice._army_has_voice = lambda: True
        issued = voice.issue_order(
            game,
            issuing_officer,
            bodyguard,
            ORDER_MOVE.key,
            phase_name="COMMAND_PHASE",
        )
        self.assertTrue(issued)
        self.assertEqual(str(bodyguard.special_rules.get("voice_of_command_order_key", "") or ""), ORDER_MOVE.key)
        self.assertTrue(bool(bodyguard.special_rules.get("voice_of_command_take_cover_cap")))
        self.assertTrue(voice._attached_unit_has_order_key(bodyguard, ORDER_TAKE_COVER.key))

        voice.clear_order(bodyguard)
        voice.clear_order(stalwart_leader)
        bearer = _find_bearer_model(stalwart_leader)
        self.assertIsNotNone(bearer)
        bearer.take_damage(int(getattr(bearer, "wounds", 0) or 0), game_map=game.map)
        game.turn = 2

        issued_after_death = voice.issue_order(
            game,
            issuing_officer,
            bodyguard,
            ORDER_MOVE.key,
            phase_name="COMMAND_PHASE",
        )
        self.assertTrue(issued_after_death)
        self.assertFalse(bool(bodyguard.special_rules.get("voice_of_command_take_cover_cap")))
        self.assertFalse(voice._attached_unit_has_order_key(bodyguard, ORDER_TAKE_COVER.key))


if __name__ == "__main__":
    unittest.main()
