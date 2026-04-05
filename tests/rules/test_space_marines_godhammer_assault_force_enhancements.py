import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command, resolve_decision_value
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


def _build_game(detachment_type: str = "Godhammer Assault Force"):
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


def _bearer_model(unit: Unit):
    bearer_id = str(getattr(unit, "special_rules", {}).get("enhancement_bearer_model_id", "") or "")
    for model in list(getattr(unit, "models", []) or []):
        if str(get_entity_id(model) or "") == bearer_id:
            return model
    for model in list(getattr(unit, "models", []) or []):
        if bool(getattr(model, "is_alive", False)):
            return model
    return None


def _make_melee_profile(*, attacks: int = 1, strength: int = 4, damage: int = 1) -> WargearProfile:
    parent = SimpleNamespace(name="Astartes Blade", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        profile_name="Melee",
        wargear_data={
            "range": "Melee",
            "A": str(int(attacks)),
            "BS_WS": "3+",
            "S": str(int(strength)),
            "AP": "0",
            "D": str(int(damage)),
            "description": "",
        },
        parent_wargear=parent,
    )


class TestSpaceMarinesGodhammerAssaultForceEnhancements(unittest.TestCase):
    def test_paragon_of_fury_adds_bearer_strength_and_disembark_damage(self):
        game, sm_army, enemy_army, _sm_player, _enemy_player = _build_game()
        bearer_unit = _make_unit(
            "Marshal",
            keywords=["ADEPTUS ASTARTES", "CHARACTER", "INFANTRY"],
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
            wounds=5,
        )
        sm_army.add_unit(bearer_unit)
        enemy_army.add_unit(enemy)
        bearer_unit.deployed = True
        enemy.deployed = True
        game.map.units = [bearer_unit, enemy]
        game.rebuild_entity_registry()

        Enhancement(
            id="000010400002",
            name="Paragon of Fury",
            faction_id="SM",
            detachment="Godhammer Assault Force",
            points=15,
            description="",
        ).apply_to_unit(bearer_unit)

        bearer = _bearer_model(bearer_unit)
        self.assertIsNotNone(bearer)
        melee_profile = _make_melee_profile(attacks=1, strength=4, damage=1)

        wound_result = melee_profile._wound_target_with_tracking(
            enemy,
            bearer,
            {},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(
            any(
                "+2S from Enhancement bearer (melee)" in str(reason)
                for reason in list(wound_result.get("modifiers", []) or [])
            )
        )

        base_damage = melee_profile._damage_target_with_tracking(
            enemy.models[0],
            bearer,
            {},
            game_map=game.map,
            allow_rerolls=False,
        )
        self.assertFalse(any("Paragon of Fury" in str(effect) for effect in list(base_damage.get("special_effects", []) or [])))

        bearer_unit.round_state.disembarked_this_round = True
        bearer_unit.round_state.disembarked_from_transport_id = "transport-1"
        boosted_damage = melee_profile._damage_target_with_tracking(
            enemy.models[0],
            bearer,
            {},
            game_map=game.map,
            allow_rerolls=False,
        )
        self.assertTrue(
            any("Paragon of Fury +1D" in str(effect) for effect in list(boosted_damage.get("special_effects", []) or []))
        )

    def test_battle_psalm_precentor_applies_minus_one_to_shock_and_awe_test(self):
        game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
        charger = _make_unit(
            "Crusader Squad",
            keywords=["ADEPTUS ASTARTES", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
            wounds=4,
        )
        target_a = _make_unit("Enemy A", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        target_b = _make_unit("Enemy B", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        sm_army.add_unit(charger)
        enemy_army.add_unit(target_a)
        enemy_army.add_unit(target_b)
        charger.deployed = True
        target_a.deployed = True
        target_b.deployed = True
        charger.round_state.disembarked_this_round = True
        charger.round_state.disembarked_from_transport_id = "transport-1"
        game.map.units = [charger, target_a, target_b]
        game.rebuild_entity_registry()

        Enhancement(
            id="000010400003",
            name="Battle-psalm Precentor",
            faction_id="SM",
            detachment="Godhammer Assault Force",
            points=20,
            description="",
        ).apply_to_unit(charger)

        captured = {}

        def _capture_battleshock(current_turn: int = 1):
            sr = getattr(target_a, "special_rules", {}) or {}
            captured["turn"] = int(current_turn)
            captured["modifier"] = int(sr.get("battle_shock_test_modifier", 0) or 0)
            captured["reasons"] = list(sr.get("battle_shock_test_modifier_reasons", []) or [])

        target_a.take_battle_shock_test = _capture_battleshock

        game.event_system.publish("charge_declared", unit=charger, target_units=[target_a, target_b])
        request = next(
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
            and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "shock_and_awe_battleshock"
        )
        option = next(
            opt
            for opt in list(getattr(request, "options", []) or [])
            if str((getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or "") == str(target_a.id)
        )
        value, apply_result = resolve_decision_value(game, request, option.option_id, player_id=sm_player.id)

        self.assertTrue(bool(getattr(apply_result, "ok", False)))
        self.assertEqual(int(captured.get("turn", 0) or 0), int(game.turn))
        self.assertEqual(int(captured.get("modifier", 0) or 0), -1)
        self.assertTrue(any("Battle-psalm Precentor" in str(reason) for reason in list(captured.get("reasons", []) or [])))
        self.assertEqual(int(value.get("test_modifier", 0) or 0), -1)

    def test_augury_servo_host_queues_target_and_applies_no_cover(self):
        game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
        source = _make_unit(
            "Techmarine",
            keywords=["ADEPTUS ASTARTES", "CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
            wounds=4,
        )
        target = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            model_count=1,
            wounds=4,
        )
        sm_army.add_unit(source)
        enemy_army.add_unit(target)
        source.deployed = True
        target.deployed = True
        source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        target.models[0].set_location(6.0, 0.0, 0.0, 0.0)
        game.map.units = [source, target]
        game.rebuild_entity_registry()

        Enhancement(
            id="000010400004",
            name="Augury Servo-host",
            faction_id="SM",
            detachment="Godhammer Assault Force",
            points=15,
            description="",
        ).apply_to_unit(source)

        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0
        game._on_phase_start_optional_abilities(player=sm_player, phase=game.phase)

        request = next(
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
            and str((getattr(req, "context", {}) or {}).get("ability_key", "") or "") == "godhammer_augury_servo_host"
        )
        self.assertEqual(str((request.context or {}).get("ability", "") or ""), "post_shoot_no_cover")

        option = next(
            opt
            for opt in list(getattr(request, "options", []) or [])
            if str((getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or "") == str(target.id)
        )
        result = resolve_decision_command(game, request, option.option_id, player_id=sm_player.id)
        self.assertTrue(bool(getattr(result, "ok", False)))

        sr = getattr(target, "special_rules", {}) or {}
        self.assertTrue(bool(sr.get("post_shoot_no_cover_active", False)))
        self.assertEqual(str(sr.get("post_shoot_no_cover_expires_phase", "") or ""), "SHOOTING_PHASE")
        self.assertIn("Augury Servo-host", str(sr.get("post_shoot_no_cover_source", "") or ""))

    def test_herald_of_sacred_slaughter_grants_scouts_to_starting_transport(self):
        game, sm_army, _enemy_army, _sm_player, _enemy_player = _build_game()
        bearer = _make_unit(
            "Marshal",
            keywords=["ADEPTUS ASTARTES", "CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
            wounds=4,
        )
        transport = _make_unit(
            "Impulsor",
            keywords=["Transport", "Dedicated Transport", "Vehicle"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
            wounds=10,
        )
        sm_army.add_unit(bearer)
        sm_army.add_unit(transport)
        transport.transport_capacity = 6

        Enhancement(
            id="000010400005",
            name="Herald of Sacred Slaughter",
            faction_id="SM",
            detachment="Godhammer Assault Force",
            points=20,
            description="",
        ).apply_to_unit(bearer)

        bearer.deployed = False
        transport.deployed = False
        bearer.embark(transport, game_map=game.map)

        has_scout, distance = transport.has_scout()
        self.assertTrue(bool(has_scout))
        self.assertEqual(float(distance or 0.0), 9.0)


if __name__ == "__main__":
    unittest.main()
