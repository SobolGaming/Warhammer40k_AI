import unittest
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_SELECT_REALM_OF_CHAOS_UNITS
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "4",
                "W": "3",
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


def _make_unit(name: str, *, keywords=None, faction_keywords=None) -> Unit:
    unit = Unit(_MockDatasheet(name, keywords=keywords, faction_keywords=faction_keywords))
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _set_model_location(unit: Unit, *, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)


def _build_game(*, size: BattlefieldSize = BattlefieldSize.STRIKE_FORCE):
    am_army = Army.with_detachment("Astra Militarum", detachment_type="Siege Regiment")
    am_army.faction_id = "AM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "SM"

    am_player = Player("AM", control=PlayerControl.REMOTE, army=am_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game = Game(Battlefield(size), players=[am_player, enemy_player])
    return game, am_army, enemy_army, am_player, enemy_player


def _ability_requests(game: Game, decision_type: str, ability_key: str):
    return [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == str(decision_type or "")
        and str((getattr(req, "context", {}) or {}).get("ability", "") or "").strip().lower()
        == str(ability_key or "").strip().lower()
    ]


def _choose_option(request, *, payload_key: str, payload_value: str):
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get(payload_key, "") or "").strip().lower() == str(payload_value or "").strip().lower():
            return option
    raise AssertionError(f"Option not found for {payload_key}={payload_value}")


def _confirm_option(request):
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("action", "") or "").strip().lower() == "confirm":
            return option
    raise AssertionError("Confirm option not found.")


def _make_ranged_profile() -> WargearProfile:
    parent = type(
        "_ParentWargear",
        (),
        {
            "name": "Test Gun",
            "is_melee": staticmethod(lambda: False),
            "is_ranged": staticmethod(lambda: True),
        },
    )()
    return WargearProfile(
        "Profile",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": "4+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


class TestAstraMilitarumSiegeRegiment(unittest.TestCase):
    def test_artillery_support_mode_request_queued_on_battle_round_start(self):
        game, am_army, enemy_army, _am_player, _enemy_player = _build_game()
        friendly = _make_unit("Friendly", keywords=["ASTRA MILITARUM", "INFANTRY"], faction_keywords=["ASTRA MILITARUM"])
        enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ADEPTUS ASTARTES"])
        _set_model_location(friendly, x=0.0, y=0.0)
        _set_model_location(enemy, x=30.0, y=0.0)
        am_army.add_unit(friendly)
        enemy_army.add_unit(enemy)
        game.map.units = [friendly, enemy]
        game.rebuild_entity_registry()

        am_army.on_battle_round_start(1)

        requests = _ability_requests(game, DECISION_CHOOSE_QUARRY, "siege_regiment_artillery_support_mode")
        self.assertEqual(len(requests), 1)
        request = requests[0]
        self.assertEqual(request.player_id, am_army.player.id)
        self.assertEqual(int((request.context or {}).get("max_units", 0) or 0), 3)
        modes = {
            str((opt.payload or {}).get("artillery_support_mode", "") or "")
            for opt in list(request.options or [])
        }
        self.assertEqual(modes, {"creeping_barrage", "incendiary_bombardment", "smoke_shells"})

    def test_smoke_shells_selection_applies_stealth_until_next_round(self):
        game, am_army, enemy_army, am_player, _enemy_player = _build_game()
        friendly_a = _make_unit("Friendly A", keywords=["ASTRA MILITARUM", "INFANTRY"], faction_keywords=["ASTRA MILITARUM"])
        friendly_b = _make_unit("Friendly B", keywords=["ASTRA MILITARUM", "INFANTRY"], faction_keywords=["ASTRA MILITARUM"])
        enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ADEPTUS ASTARTES"])
        _set_model_location(friendly_a, x=0.0, y=0.0)
        _set_model_location(friendly_b, x=6.0, y=0.0)
        _set_model_location(enemy, x=30.0, y=0.0)
        am_army.add_unit(friendly_a)
        am_army.add_unit(friendly_b)
        enemy_army.add_unit(enemy)
        game.map.units = [friendly_a, friendly_b, enemy]
        game.rebuild_entity_registry()

        am_army.on_battle_round_start(1)
        mode_request = _ability_requests(game, DECISION_CHOOSE_QUARRY, "siege_regiment_artillery_support_mode")[0]
        smoke_option = _choose_option(mode_request, payload_key="artillery_support_mode", payload_value="smoke_shells")
        mode_result = resolve_decision_command(game, mode_request, smoke_option.option_id, player_id=am_player.id)
        self.assertTrue(bool(getattr(mode_result, "ok", False)))

        smoke_request = _ability_requests(game, DECISION_SELECT_REALM_OF_CHAOS_UNITS, "siege_regiment_smoke_shells")[0]
        confirm = _confirm_option(smoke_request)
        selected_id = str(get_entity_id(friendly_a) or "")
        selection_result = resolve_decision_command(
            game,
            smoke_request,
            confirm.option_id,
            result_payload={"unit_ids": [selected_id]},
            player_id=am_player.id,
        )
        self.assertTrue(bool(getattr(selection_result, "ok", False)))
        self.assertTrue(friendly_a.has_stealth())
        self.assertFalse(friendly_b.has_stealth())

        game.turn = 2
        am_army.on_battle_round_start(2)
        self.assertFalse(friendly_a.has_stealth())

    def test_incendiary_bombardment_scattered_blocks_cover(self):
        game, am_army, enemy_army, am_player, _enemy_player = _build_game()
        friendly = _make_unit("Friendly", keywords=["ASTRA MILITARUM", "INFANTRY"], faction_keywords=["ASTRA MILITARUM"])
        enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ADEPTUS ASTARTES"])
        _set_model_location(friendly, x=0.0, y=0.0)
        _set_model_location(enemy, x=30.0, y=0.0)
        am_army.add_unit(friendly)
        enemy_army.add_unit(enemy)
        game.map.units = [friendly, enemy]
        game.rebuild_entity_registry()

        am_army.on_battle_round_start(1)
        mode_request = _ability_requests(game, DECISION_CHOOSE_QUARRY, "siege_regiment_artillery_support_mode")[0]
        incendiary_option = _choose_option(
            mode_request,
            payload_key="artillery_support_mode",
            payload_value="incendiary_bombardment",
        )
        mode_result = resolve_decision_command(game, mode_request, incendiary_option.option_id, player_id=am_player.id)
        self.assertTrue(bool(getattr(mode_result, "ok", False)))

        selection_request = _ability_requests(
            game,
            DECISION_SELECT_REALM_OF_CHAOS_UNITS,
            "siege_regiment_incendiary_bombardment",
        )[0]
        confirm = _confirm_option(selection_request)
        selected_id = str(get_entity_id(enemy) or "")
        selection_result = resolve_decision_command(
            game,
            selection_request,
            confirm.option_id,
            result_payload={"unit_ids": [selected_id]},
            player_id=am_player.id,
        )
        self.assertTrue(bool(getattr(selection_result, "ok", False)))
        self.assertTrue(bool(enemy.special_rules.get("artillery_support_scattered_active")))

        profile = _make_ranged_profile()
        attack_instance = {
            "attacker_model": friendly.models[0],
            "attacker_unit": friendly,
            "benefit_of_cover": True,
            "benefit_of_cover_source": "RUINS",
        }
        save_result = profile._save_with_tracking(
            enemy.models[0],
            attack_instance,
            ap=0,
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(bool(save_result.get("saved")))
        self.assertTrue(bool(attack_instance.get("ignores_cover")))

    def test_creeping_barrage_overflow_resolves_one_unit_at_a_time_and_stops_at_cap(self):
        game, am_army, enemy_army, am_player, _enemy_player = _build_game(size=BattlefieldSize.STRIKE_FORCE)
        friendly = _make_unit("Friendly", keywords=["ASTRA MILITARUM", "INFANTRY"], faction_keywords=["ASTRA MILITARUM"])
        _set_model_location(friendly, x=0.0, y=0.0)
        am_army.add_unit(friendly)

        near_enemy = _make_unit("Near Enemy", keywords=["INFANTRY"], faction_keywords=["ADEPTUS ASTARTES"])
        far_enemies = [
            _make_unit(f"Far Enemy {idx}", keywords=["INFANTRY"], faction_keywords=["ADEPTUS ASTARTES"])
            for idx in range(1, 5)
        ]
        _set_model_location(near_enemy, x=8.0, y=0.0)
        _set_model_location(far_enemies[0], x=30.0, y=0.0)
        _set_model_location(far_enemies[1], x=40.0, y=0.0)
        _set_model_location(far_enemies[2], x=50.0, y=0.0)
        _set_model_location(far_enemies[3], x=60.0, y=0.0)
        enemy_army.add_unit(near_enemy)
        for enemy in far_enemies:
            enemy_army.add_unit(enemy)

        game.map.units = [friendly, near_enemy] + list(far_enemies)
        game.rebuild_entity_registry()

        am_army.on_battle_round_start(1)
        mode_request = _ability_requests(game, DECISION_CHOOSE_QUARRY, "siege_regiment_artillery_support_mode")[0]
        creeping_option = _choose_option(mode_request, payload_key="artillery_support_mode", payload_value="creeping_barrage")
        with patch("warhammer40k_ai.rules.astra_militarum_detachments.get_roll", side_effect=[5, 5, 5, 1]):
            mode_result = resolve_decision_command(game, mode_request, creeping_option.option_id, player_id=am_player.id)
            self.assertTrue(bool(getattr(mode_result, "ok", False)))

            chosen_order = [far_enemies[3], far_enemies[1], far_enemies[0]]
            for idx, unit in enumerate(chosen_order, start=1):
                requests = _ability_requests(
                    game,
                    DECISION_SELECT_REALM_OF_CHAOS_UNITS,
                    "siege_regiment_creeping_barrage_selection",
                )
                self.assertEqual(len(requests), 1)
                selection_request = requests[0]
                self.assertEqual(int((selection_request.context or {}).get("required_units", 0) or 0), 1)
                confirm = _confirm_option(selection_request)
                selection_result = resolve_decision_command(
                    game,
                    selection_request,
                    confirm.option_id,
                    result_payload={"unit_ids": [str(get_entity_id(unit) or "")]},
                    player_id=am_player.id,
                )
                self.assertTrue(bool(getattr(selection_result, "ok", False)))
                if idx < 3:
                    self.assertEqual(
                        len(
                            _ability_requests(
                                game,
                                DECISION_SELECT_REALM_OF_CHAOS_UNITS,
                                "siege_regiment_creeping_barrage_selection",
                            )
                        ),
                        1,
                    )

        for unit in chosen_order:
            self.assertTrue(bool(unit.special_rules.get("artillery_support_shaken_active")))
            effective_move = unit.get_effective_model_characteristic(unit.models[0], "movement")
            self.assertEqual(int(effective_move), 4)
            charge_mods = list(game.get_charge_roll_modifiers(unit, target_unit=friendly) or [])
            self.assertTrue(any(int(mod[0]) == -2 for mod in charge_mods))
        self.assertFalse(
            bool(
                _ability_requests(
                    game,
                    DECISION_SELECT_REALM_OF_CHAOS_UNITS,
                    "siege_regiment_creeping_barrage_selection",
                )
            )
        )
        self.assertFalse(bool(far_enemies[2].special_rules.get("artillery_support_shaken_active")))
        self.assertFalse(bool(near_enemy.special_rules.get("artillery_support_shaken_active")))

        game.turn = 2
        am_army.on_battle_round_start(2)
        self.assertFalse(bool(far_enemies[0].special_rules.get("artillery_support_shaken_active")))
        self.assertEqual(int(far_enemies[0].get_effective_model_characteristic(far_enemies[0].models[0], "movement")), 6)


if __name__ == "__main__":
    unittest.main()
