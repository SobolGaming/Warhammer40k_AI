import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_SELECT_REALM_OF_CHAOS_UNITS
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army, ArmyValidationError
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None, cost: int = 100, wounds: int = 4):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": int(cost)}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "8",
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "2",
                "base_size": "60mm",
                "inv_sv": "4",
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


def _make_unit(name: str, *, keywords=None, faction_keywords=None, cost: int = 100, wounds: int = 4) -> Unit:
    unit = Unit(_MockDatasheet(name, keywords=keywords, faction_keywords=faction_keywords, cost=cost, wounds=wounds))
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _set_model_location(unit: Unit, *, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)


def _make_ranged_profile(weapon, *, ap: int = 0) -> WargearProfile:
    return WargearProfile(
        "Profile",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": str(int(ap)),
            "D": "1",
            "description": "",
        },
        parent_wargear=weapon,
    )


def _build_game():
    necron_army = Army.with_detachment("Necrons", "Pantheon of Woe")
    necron_army.faction_id = "NEC"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    necron_player = Player("Necrons", control=PlayerControl.REMOTE, army=necron_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[necron_player, enemy_player])
    return game, necron_army, enemy_army, necron_player, enemy_player


def _cosmic_distortion_requests(game: Game):
    return [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_SELECT_REALM_OF_CHAOS_UNITS
        and str((getattr(req, "context", {}) or {}).get("ability", "") or "").strip().lower()
        == "cosmic_distortion_phase_surge"
    ]


class TestNecronsPantheonOfWoeDetachment(unittest.TestCase):
    def test_cosmic_distortion_queues_phase_start_multiselect_request(self):
        game, necron_army, enemy_army, necron_player, _enemy_player = _build_game()
        monster_a = _make_unit("C'tan Shard of the Deceiver", keywords=["MONSTER"], faction_keywords=["NECRONS"])
        monster_b = _make_unit("Transcendent C'tan", keywords=["MONSTER"], faction_keywords=["NECRONS"])
        infantry = _make_unit("Necron Warriors", keywords=["INFANTRY"], faction_keywords=["NECRONS"])
        enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])

        _set_model_location(monster_a, x=0.0, y=0.0)
        _set_model_location(monster_b, x=6.0, y=0.0)
        _set_model_location(infantry, x=12.0, y=0.0)
        _set_model_location(enemy, x=30.0, y=30.0)

        necron_army.add_unit(monster_a)
        necron_army.add_unit(monster_b)
        necron_army.add_unit(infantry)
        enemy_army.add_unit(enemy)
        game.map.units = [monster_a, monster_b, infantry, enemy]
        game.rebuild_entity_registry()

        game._on_phase_start_optional_abilities(player=necron_player, phase=BattleRoundPhases.SHOOTING_PHASE)

        requests = _cosmic_distortion_requests(game)
        self.assertEqual(len(requests), 1)
        request = requests[0]
        ctx = dict(getattr(request, "context", {}) or {})
        allowed_ids = set(str(v) for v in list(ctx.get("allowed_unit_ids") or []))
        self.assertEqual(int(ctx.get("max_units", 0) or 0), 2)
        self.assertIn(str(get_entity_id(monster_a)), allowed_ids)
        self.assertIn(str(get_entity_id(monster_b)), allowed_ids)
        self.assertNotIn(str(get_entity_id(infantry)), allowed_ids)
        self.assertTrue(any(str((opt.payload or {}).get("action", "")) == "confirm" for opt in list(request.options or [])))
        self.assertTrue(any(str((opt.payload or {}).get("action", "")) == "skip" for opt in list(request.options or [])))

    def test_cosmic_distortion_selected_unit_takes_mortals_and_grants_ap_bonus_within_nine(self):
        game, necron_army, enemy_army, necron_player, _enemy_player = _build_game()
        source_monster = _make_unit("Transcendent C'tan", keywords=["MONSTER"], faction_keywords=["NECRONS"], wounds=8)
        attacker_unit = _make_unit("Immortals", keywords=["INFANTRY"], faction_keywords=["NECRONS"])
        enemy_target = _make_unit("Enemy Target", keywords=["INFANTRY"], faction_keywords=["ENEMY"], wounds=6)

        _set_model_location(source_monster, x=0.0, y=0.0)
        _set_model_location(attacker_unit, x=2.0, y=0.0)
        _set_model_location(enemy_target, x=10.0, y=0.0)

        necron_army.add_unit(source_monster)
        necron_army.add_unit(attacker_unit)
        enemy_army.add_unit(enemy_target)
        game.map.units = [source_monster, attacker_unit, enemy_target]
        game.rebuild_entity_registry()

        weapon = SimpleNamespace(name="Gauss Blaster", is_ranged=lambda: True, is_melee=lambda: False)
        attacker_model = attacker_unit.models[0]
        attacker_model.wargear = [weapon]
        profile = _make_ranged_profile(weapon, ap=0)

        baseline_ap = int(profile.get_effective_ap(attacker_model, enemy_target))
        self.assertEqual(baseline_ap, 0)

        initial_wounds = int(source_monster.models[0].wounds)
        game._on_phase_start_optional_abilities(player=necron_player, phase=BattleRoundPhases.SHOOTING_PHASE)
        request = _cosmic_distortion_requests(game)[0]
        confirm_option = next(
            opt for opt in list(request.options or []) if str((opt.payload or {}).get("action", "")) == "confirm"
        )
        result = resolve_decision_command(
            game,
            request,
            confirm_option.option_id,
            result_payload={"unit_ids": [str(get_entity_id(source_monster))]},
            player_id=necron_player.id,
        )
        self.assertTrue(bool(getattr(result, "ok", False)))
        self.assertEqual(int(source_monster.models[0].wounds), int(initial_wounds - 3))

        surged_ap = int(profile.get_effective_ap(attacker_model, enemy_target))
        self.assertEqual(surged_ap, -1)

    def test_pantheon_of_woe_applies_mandatory_necrodermal_binding_surcharges(self):
        army = Army.with_detachment("Necrons", "Pantheon of Woe")
        army.faction_id = "NEC"

        expected_costs = {
            "C'tan Shard of the Deceiver": 140,
            "C'tan Shard of the Nightbringer": 130,
            "C'tan Shard of the Void Dragon": 120,
            "Transcendent C'tan": 125,
        }
        for name, expected in expected_costs.items():
            unit = _make_unit(name, keywords=["MONSTER"], faction_keywords=["NECRONS"], cost=100)
            army.add_unit(unit)
            self.assertEqual(int(unit.get_unit_cost()), int(expected))

        warriors = _make_unit("Necron Warriors", keywords=["INFANTRY"], faction_keywords=["NECRONS"], cost=100)
        army.add_unit(warriors)
        self.assertEqual(int(warriors.get_unit_cost()), 100)

    def test_necrodermal_binding_surcharge_counts_toward_points_limit(self):
        army = Army.with_detachment("Necrons", "Pantheon of Woe", points_limit=130)
        army.faction_id = "NEC"
        deceiver = _make_unit("C'tan Shard of the Deceiver", keywords=["MONSTER"], faction_keywords=["NECRONS"], cost=100)
        army.add_unit(deceiver)
        with self.assertRaises(ArmyValidationError):
            army.validate_points_limit()


if __name__ == "__main__":
    unittest.main()
