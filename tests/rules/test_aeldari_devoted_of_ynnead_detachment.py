import unittest
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CHOOSE_QUARRY,
    DECISION_CONFIRM_YES_NO,
    DECISION_MOVE_UNIT,
    DECISION_SELECT_OVERWATCH_SHOOTER,
)
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, BattleRoundPhases, Game
from warhammer40k_ai.roster.army import Army, ArmyValidationError
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.utility.model_base import Base, BaseType


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        datasheet_id: str | None = None,
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        wounds: int = 2,
    ):
        self.id = datasheet_id or name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{model_count} Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": str(wounds),
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
    datasheet_id: str | None = None,
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: int = 2,
):
    unit = Unit(
        _MockDatasheet(
            name,
            datasheet_id=datasheet_id,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
        )
    )
    unit._id = datasheet_id or name.lower().replace(" ", "-")
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _make_model(name: str, unit: Unit, *, x: float, y: float, wounds: int = 2) -> Model:
    model = Model(
        name=name,
        movement=6,
        toughness=4,
        save=3,
        wounds=wounds,
        leadership=7,
        objective_control=1,
        model_base=Base(BaseType.CIRCULAR, 1.0),
    )
    model.parent_unit = unit
    model.set_location(x, y, 0.0, 0.0)
    return model


def _find_request(game: Game, *, decision_type: str, ability: str | None = None):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "")) != str(decision_type):
            continue
        if ability is not None:
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "") != str(ability):
                continue
        return req
    return None


class TestAeldariDevotedOfYnneadDetachment(unittest.TestCase):
    def _build_game(self):
        aeldari_army = Army("Aeldari", detachment_type="Devoted of Ynnead")
        aeldari_army.faction_id = "AE"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "SM"
        aeldari_player = Player("Aeldari", PlayerControl.REMOTE, army=aeldari_army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[aeldari_player, enemy_player])
        return game, aeldari_army, enemy_army, aeldari_player, enemy_player

    def _make_yvraine_warlord(self, army: Army, *, x: float = 0.0, y: float = 0.0) -> Unit:
        yvraine = _make_unit(
            "Yvraine",
            datasheet_id="yvraine",
            keywords=["INFANTRY", "CHARACTER"],
            faction_keywords=["AELDARI", "ASURYANI", "YNNARI"],
            wounds=6,
        )
        yvraine.models = [_make_model("Yvraine", yvraine, x=x, y=y, wounds=6)]
        yvraine.is_warlord = True
        army.add_unit(yvraine)
        army.warlord = yvraine
        return yvraine

    def test_servants_of_the_whispering_god_requires_yvraine_or_yncarne_warlord(self):
        army = Army("Aeldari", detachment_type="Devoted of Ynnead")
        army.faction_id = "AE"

        non_named = _make_unit(
            "Guardian Squad",
            datasheet_id="guardian-squad",
            keywords=["INFANTRY"],
            faction_keywords=["AELDARI", "ASURYANI"],
        )
        non_named.models = [_make_model("Guardian", non_named, x=0.0, y=0.0)]
        non_named.is_warlord = True
        army.add_unit(non_named)
        army.warlord = non_named

        with self.assertRaises(ArmyValidationError):
            army.validate_detachment_rules()

        army_valid = Army("Aeldari", detachment_type="Devoted of Ynnead")
        army_valid.faction_id = "AE"
        self._make_yvraine_warlord(army_valid)
        try:
            army_valid.validate_detachment_rules()
        except ArmyValidationError as exc:
            self.fail(f"Unexpected Devoted of Ynnead validation error: {exc}")

    def test_lethal_reprisal_queues_and_applies_fights_first(self):
        game, aeldari_army, enemy_army, aeldari_player, enemy_player = self._build_game()
        game.phase = BattleRoundPhases.FIGHT_PHASE
        game.current_player_index = 0

        self._make_yvraine_warlord(aeldari_army)

        wounded = _make_unit(
            "Reavers",
            datasheet_id="reavers",
            keywords=["INFANTRY"],
            faction_keywords=["AELDARI", "ASURYANI"],
            model_count=2,
        )
        wounded.models = [_make_model("Reaver", wounded, x=5.0, y=0.0)]
        wounded.starting_model_count = 2
        aeldari_army.add_unit(wounded)

        enemy = _make_unit("Enemy", datasheet_id="enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        enemy.models = [_make_model("Enemy", enemy, x=20.0, y=0.0)]
        enemy_army.add_unit(enemy)

        game.map.units = [wounded, enemy]
        game.rebuild_entity_registry()

        game._on_phase_start_empowered_by_death(player=aeldari_player, phase=game.phase)

        request = _find_request(
            game,
            decision_type=DECISION_CHOOSE_QUARRY,
            ability="aeldari_strength_from_death_lethal_reprisal",
        )
        self.assertIsNotNone(request)

        option_id = None
        for opt in list(request.options or []):
            if str((opt.payload or {}).get("target_unit_id", "") or "") == str(get_entity_id(wounded) or ""):
                option_id = opt.option_id
                break
        self.assertIsNotNone(option_id)

        resolve_decision_command(game, request, option_id, player_id=aeldari_player.id)

        sr = dict(getattr(wounded, "special_rules", {}) or {})
        self.assertTrue(bool(sr.get("empowered_by_death_active", False)))
        self.assertEqual(str(sr.get("empowered_by_death_expires_phase", "")), "FIGHT_PHASE")
        self.assertIn("Strength from Death", str(sr.get("empowered_by_death_source", "")))

    def test_lethal_reprisal_invalid_choice_rejected(self):
        game, aeldari_army, enemy_army, aeldari_player, _enemy_player = self._build_game()
        game.phase = BattleRoundPhases.FIGHT_PHASE
        game.current_player_index = 0

        self._make_yvraine_warlord(aeldari_army)

        wounded = _make_unit(
            "Kabalites",
            datasheet_id="kabalites",
            keywords=["INFANTRY"],
            faction_keywords=["AELDARI", "ASURYANI"],
            model_count=2,
        )
        wounded.models = [_make_model("Kabalite", wounded, x=6.0, y=0.0)]
        wounded.starting_model_count = 2
        aeldari_army.add_unit(wounded)

        enemy = _make_unit("Enemy", datasheet_id="enemy-2", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        enemy.models = [_make_model("Enemy", enemy, x=18.0, y=0.0)]
        enemy_army.add_unit(enemy)

        game.map.units = [wounded, enemy]
        game.rebuild_entity_registry()

        game._on_phase_start_empowered_by_death(player=aeldari_player, phase=game.phase)
        request = _find_request(
            game,
            decision_type=DECISION_CHOOSE_QUARRY,
            ability="aeldari_strength_from_death_lethal_reprisal",
        )
        self.assertIsNotNone(request)
        result = resolve_decision_command(game, request, "invalid-option-id", player_id=aeldari_player.id)
        self.assertFalse(bool(getattr(result, "ok", False)))
        self.assertFalse(bool(getattr(wounded, "special_rules", {}).get("empowered_by_death_active")))

    def test_lethal_intent_records_and_queues_reactive_move(self):
        game, aeldari_army, enemy_army, aeldari_player, enemy_player = self._build_game()
        game.turn = 2
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 1

        self._make_yvraine_warlord(aeldari_army, x=15.0, y=0.0)

        destroyed = _make_unit(
            "Fallen",
            datasheet_id="fallen",
            keywords=["INFANTRY"],
            faction_keywords=["AELDARI", "ASURYANI"],
        )
        destroyed_model = _make_model("Fallen", destroyed, x=0.0, y=0.0)
        destroyed.models = [destroyed_model]
        aeldari_army.add_unit(destroyed)

        near = _make_unit(
            "Near Unit",
            datasheet_id="near-unit",
            keywords=["INFANTRY"],
            faction_keywords=["AELDARI", "ASURYANI"],
        )
        near.models = [_make_model("Near", near, x=4.0, y=0.0)]
        aeldari_army.add_unit(near)

        far = _make_unit(
            "Far Unit",
            datasheet_id="far-unit",
            keywords=["INFANTRY"],
            faction_keywords=["AELDARI", "ASURYANI"],
        )
        far.models = [_make_model("Far", far, x=20.0, y=0.0)]
        aeldari_army.add_unit(far)

        enemy = _make_unit("Shooter", datasheet_id="enemy-shooter", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        enemy.models = [_make_model("Shooter", enemy, x=30.0, y=0.0)]
        enemy_army.add_unit(enemy)

        game.map.units = [destroyed, near, far, enemy]
        game.rebuild_entity_registry()

        game._on_unit_destroyed_friendly_unit_destroyed_reposition(unit=destroyed, last_model=destroyed_model)
        game._on_phase_end_aeldari_strength_from_death_lethal_intent(player=enemy_player, phase=game.phase)

        request = _find_request(
            game,
            decision_type=DECISION_CHOOSE_QUARRY,
            ability="aeldari_strength_from_death_lethal_intent",
        )
        self.assertIsNotNone(request)

        option_payloads = [dict(getattr(opt, "payload", {}) or {}) for opt in list(request.options or [])]
        self.assertTrue(any(str(p.get("action", "") or "") == "skip" for p in option_payloads))
        target_ids = {str(p.get("target_unit_id", "") or "") for p in option_payloads}
        self.assertIn(str(get_entity_id(near) or ""), target_ids)
        self.assertNotIn(str(get_entity_id(far) or ""), target_ids)

        near_option = next(
            opt
            for opt in list(request.options or [])
            if str((opt.payload or {}).get("target_unit_id", "") or "") == str(get_entity_id(near) or "")
        )
        with patch("warhammer40k_ai.utility.dice.get_roll", return_value=4):
            resolve_decision_command(game, request, near_option.option_id, player_id=aeldari_player.id)

        move_req = _find_request(game, decision_type=DECISION_MOVE_UNIT)
        self.assertIsNotNone(move_req)
        move_ctx = dict(getattr(move_req, "context", {}) or {})
        self.assertEqual(str(move_ctx.get("reactive_move_kind", "")), "aeldari_strength_from_death_lethal_intent")
        self.assertEqual(int(move_ctx.get("max_distance", 0) or 0), 5)

    def test_lethal_surge_confirmation_flow_marks_engagement_range_move(self):
        game, aeldari_army, enemy_army, aeldari_player, _enemy_player = self._build_game()
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.turn = 3
        game.current_player_index = 1

        self._make_yvraine_warlord(aeldari_army, x=12.0, y=0.0)

        target = _make_unit(
            "Defenders",
            datasheet_id="defenders",
            keywords=["INFANTRY"],
            faction_keywords=["AELDARI", "ASURYANI"],
        )
        target.models = [_make_model("Defender", target, x=10.0, y=0.0)]
        aeldari_army.add_unit(target)

        attacker = _make_unit("Attacker", datasheet_id="attacker", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        attacker.models = [_make_model("Attacker", attacker, x=0.0, y=0.0)]
        enemy_army.add_unit(attacker)

        aeldari_army.battle_focus.tokens = 1

        game.map.units = [target, attacker]
        game.rebuild_entity_registry()

        game.event_system.publish(
            "unit_shooting_resolved",
            attacker_unit=attacker,
            hits_by_target={target: 1},
        )

        select_req = _find_request(game, decision_type=DECISION_SELECT_OVERWATCH_SHOOTER, ability="battle_focus")
        self.assertIsNotNone(select_req)
        option_id = None
        for opt in list(select_req.options or []):
            if str((opt.payload or {}).get("unit_id", "") or "") == str(get_entity_id(target) or ""):
                option_id = opt.option_id
                break
        self.assertIsNotNone(option_id)
        resolve_decision_command(game, select_req, option_id, player_id=aeldari_player.id)

        confirm_req = _find_request(
            game,
            decision_type=DECISION_CONFIRM_YES_NO,
            ability="aeldari_strength_from_death_lethal_surge",
        )
        self.assertIsNotNone(confirm_req)
        yes_option = next(opt for opt in list(confirm_req.options or []) if bool((opt.payload or {}).get("choice")) is True)
        with patch("warhammer40k_ai.utility.dice.get_roll", return_value=3):
            resolve_decision_command(game, confirm_req, yes_option.option_id, player_id=aeldari_player.id)

        move_req = _find_request(game, decision_type=DECISION_MOVE_UNIT)
        self.assertIsNotNone(move_req)
        move_ctx = dict(getattr(move_req, "context", {}) or {})
        self.assertEqual(str(move_ctx.get("reactive_move_kind", "")), "aeldari_strength_from_death_lethal_surge")
        self.assertTrue(bool(move_ctx.get("reactive_move_allow_engagement_range", False)))
        self.assertIn("Lethal Surge", str(move_ctx.get("reactive_move_source", "")))

        self.assertFalse(bool(aeldari_army.aeldari_detachments.devoted_of_ynnead_lethal_surge_available(target, game=game)))


if __name__ == "__main__":
    unittest.main()
