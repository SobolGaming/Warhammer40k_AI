import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
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
                "Sv": "3",
                "W": "2",
                "Ld": "7",
                "OC": "2",
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


def _make_ranged_profile(weapon) -> WargearProfile:
    return WargearProfile(
        "Profile",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=weapon,
    )


def _build_game():
    necron_army = Army.with_detachment("Necrons", "Obeisance Phalanx")
    necron_army.faction_id = "NEC"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    necron_player = Player("Necrons", control=PlayerControl.REMOTE, army=necron_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[necron_player, enemy_player])
    return game, necron_army, enemy_army, necron_player, enemy_player


def _worthy_foes_requests(game: Game):
    return [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
        and str((getattr(req, "context", {}) or {}).get("ability", "") or "").strip().lower() == "worthy_foes"
    ]


class TestNecronsObeisancePhalanxDetachment(unittest.TestCase):
    def test_worthy_foes_queues_command_phase_target_request(self):
        game, necron_army, enemy_army, necron_player, _enemy_player = _build_game()
        noble = _make_unit("Overlord", keywords=["NOBLE", "INFANTRY"], faction_keywords=["NECRONS"])
        enemy_a = _make_unit("Enemy A", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        enemy_b = _make_unit("Enemy B", keywords=["VEHICLE"], faction_keywords=["ENEMY"])

        necron_army.add_unit(noble)
        enemy_army.add_unit(enemy_a)
        enemy_army.add_unit(enemy_b)
        game.map.units = [noble, enemy_a, enemy_b]
        game.rebuild_entity_registry()

        mgr = necron_army.necrons_detachments
        mgr.on_command_phase_start(game=game, player=necron_player)

        requests = _worthy_foes_requests(game)
        self.assertEqual(len(requests), 1)
        request = requests[0]
        option_ids = {
            str((opt.payload or {}).get("target_unit_id", "") or "")
            for opt in list(request.options or [])
        }
        self.assertIn(str(get_entity_id(enemy_a)), option_ids)
        self.assertIn(str(get_entity_id(enemy_b)), option_ids)

    def test_worthy_foes_rejects_ineligible_target_payload(self):
        game, necron_army, enemy_army, necron_player, _enemy_player = _build_game()
        noble = _make_unit("Overlord", keywords=["NOBLE", "INFANTRY"], faction_keywords=["NECRONS"])
        enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])

        necron_army.add_unit(noble)
        enemy_army.add_unit(enemy)
        game.map.units = [noble, enemy]
        game.rebuild_entity_registry()

        mgr = necron_army.necrons_detachments
        mgr.on_command_phase_start(game=game, player=necron_player)
        request = _worthy_foes_requests(game)[0]
        option = list(request.options or [])[0]
        payload = dict(option.payload or {})
        payload["target_unit_id"] = str(get_entity_id(noble))
        option.payload = payload

        apply_result = resolve_decision_command(
            game,
            request,
            option.option_id,
            player_id=necron_player.id,
        )
        self.assertFalse(bool(apply_result.ok))

    def test_worthy_foes_selected_target_grants_plus_one_to_wound_for_eligible_units(self):
        game, necron_army, enemy_army, necron_player, _enemy_player = _build_game()
        noble = _make_unit("Overlord", keywords=["NOBLE", "INFANTRY"], faction_keywords=["NECRONS"])
        warriors = _make_unit("Warriors", keywords=["INFANTRY"], faction_keywords=["NECRONS"])
        enemy_selected = _make_unit("Enemy Selected", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        enemy_other = _make_unit("Enemy Other", keywords=["INFANTRY"], faction_keywords=["ENEMY"])

        necron_army.add_unit(noble)
        necron_army.add_unit(warriors)
        enemy_army.add_unit(enemy_selected)
        enemy_army.add_unit(enemy_other)
        game.map.units = [noble, warriors, enemy_selected, enemy_other]
        game.rebuild_entity_registry()

        mgr = necron_army.necrons_detachments
        mgr.on_command_phase_start(game=game, player=necron_player)
        request = _worthy_foes_requests(game)[0]
        chosen_option = next(
            opt
            for opt in list(request.options or [])
            if str((opt.payload or {}).get("target_unit_id", "") or "") == str(get_entity_id(enemy_selected))
        )
        resolve_decision_command(
            game,
            request,
            chosen_option.option_id,
            result_payload={"target_unit_id": str(get_entity_id(enemy_selected))},
            player_id=necron_player.id,
        )

        self.assertTrue(mgr.is_worthy_foe_target(enemy_selected))

        noble_weapon = SimpleNamespace(name="Hyperphase Blade", is_ranged=lambda: False, is_melee=lambda: True)
        noble.models[0].wargear = [noble_weapon]
        noble_profile = _make_ranged_profile(noble_weapon)
        vs_selected = noble_profile._wound_target_with_tracking(
            enemy_selected,
            noble.models[0],
            {},
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(bool(vs_selected.get("wound")))
        self.assertIn("Worthy Foes", " ".join(str(v) for v in list(vs_selected.get("modifiers", []) or [])))

        vs_other = noble_profile._wound_target_with_tracking(
            enemy_other,
            noble.models[0],
            {},
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(bool(vs_other.get("wound")))

        warrior_weapon = SimpleNamespace(name="Gauss Flayer", is_ranged=lambda: True, is_melee=lambda: False)
        warriors.models[0].wargear = [warrior_weapon]
        warrior_profile = _make_ranged_profile(warrior_weapon)
        warrior_vs_selected = warrior_profile._wound_target_with_tracking(
            enemy_selected,
            warriors.models[0],
            {},
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(bool(warrior_vs_selected.get("wound")))

    def test_worthy_foes_clears_at_next_command_phase_start(self):
        game, necron_army, enemy_army, necron_player, _enemy_player = _build_game()
        noble = _make_unit("Overlord", keywords=["NOBLE", "INFANTRY"], faction_keywords=["NECRONS"])
        enemy_a = _make_unit("Enemy A", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        enemy_b = _make_unit("Enemy B", keywords=["INFANTRY"], faction_keywords=["ENEMY"])

        necron_army.add_unit(noble)
        enemy_army.add_unit(enemy_a)
        enemy_army.add_unit(enemy_b)
        game.map.units = [noble, enemy_a, enemy_b]
        game.rebuild_entity_registry()

        mgr = necron_army.necrons_detachments
        mgr.on_command_phase_start(game=game, player=necron_player)
        request = _worthy_foes_requests(game)[0]
        chosen_option = next(
            opt
            for opt in list(request.options or [])
            if str((opt.payload or {}).get("target_unit_id", "") or "") == str(get_entity_id(enemy_a))
        )
        resolve_decision_command(
            game,
            request,
            chosen_option.option_id,
            result_payload={"target_unit_id": str(get_entity_id(enemy_a))},
            player_id=necron_player.id,
        )
        self.assertTrue(mgr.is_worthy_foe_target(enemy_a))

        mgr.on_command_phase_start(game=game, player=necron_player)
        self.assertFalse(mgr.is_worthy_foe_target(enemy_a))
        self.assertEqual(len(_worthy_foes_requests(game)), 1)


if __name__ == "__main__":
    unittest.main()
