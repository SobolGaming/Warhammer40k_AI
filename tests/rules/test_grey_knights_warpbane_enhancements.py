import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.deployment import DeploymentManager
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.units.status_effects import BattleShockEffect
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        keywords=None,
        faction_keywords=None,
        abilities=None,
    ):
        self.name = name
        self.faction_data = {"name": "Grey Knights"}
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


def _make_unit(name, *, keywords=None, faction_keywords=None, abilities=None):
    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        abilities=abilities,
    )
    return Unit(datasheet)


def _build_game():
    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)
    game.turn = 1

    army_gk = Army("Grey Knights", "Warpbane Task Force")
    army_gk.faction_id = "GK"
    army_enemy = Army("Enemy", "Other")
    army_enemy.faction_id = "EN"

    p1 = Player("GK", control=PlayerControl.LOCAL, army=army_gk)
    p2 = Player("Enemy", control=PlayerControl.REMOTE, army=army_enemy)
    game.add_player(p1)
    game.add_player(p2)
    game.current_player_index = 0
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    return game, army_gk, army_enemy, p1, p2


def _apply_enhancement(unit, *, enh_id: str, name: str) -> Enhancement:
    enhancement = Enhancement(
        id=str(enh_id),
        name=str(name),
        faction_id="GK",
        detachment="Warpbane Task Force",
        detachment_id="000009777",
        points=0,
        description="",
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)
    return enhancement


def _setup_deployment_zones(game, friendly_player, enemy_player):
    dm = DeploymentManager(game, mission_name="Crucible of Battle")
    zones = dm.create_deployment_zones()
    defender_zone = next(z for z in zones if z.get("zone_type") == "defender")
    attacker_zone = next(z for z in zones if z.get("zone_type") == "attacker")
    game.deployment_zones = {
        friendly_player.id: defender_zone,
        enemy_player.id: attacker_zone,
    }


def _find_point_wholly_in_deployment_zone(game, model_base, player_id: str):
    for x in range(1, 60):
        for y in range(1, 44):
            if game.is_position_wholly_in_deployment_zone(float(x), float(y), model_base, player_id):
                return float(x), float(y)
    return None


class TestGreyKnightsWarpbaneEnhancements(unittest.TestCase):
    def test_mandulian_reliquary_adds_oc_when_not_battle_shocked(self):
        _game, army_gk, _army_enemy, _p1, _p2 = _build_game()
        bearer_unit = _make_unit(
            "Brotherhood Champion",
            keywords=["INFANTRY", "CHARACTER"],
            faction_keywords=["GREY KNIGHTS"],
        )
        army_gk.add_unit(bearer_unit)
        _apply_enhancement(
            bearer_unit,
            enh_id="000009777002",
            name="Mandulian Reliquary",
        )

        bearer_model = bearer_unit.models[0]
        self.assertEqual(
            int(bearer_unit.get_effective_model_characteristic(bearer_model, "objective_control")),
            4,
        )

        bearer_unit.status_effects = [BattleShockEffect()]
        self.assertEqual(
            int(bearer_unit.get_effective_model_characteristic(bearer_model, "objective_control")),
            1,
        )

    def test_phial_of_the_abyss_grants_stealth(self):
        _game, army_gk, _army_enemy, _p1, _p2 = _build_game()
        unit = _make_unit(
            "Strike Squad",
            keywords=["INFANTRY"],
            faction_keywords=["GREY KNIGHTS"],
        )
        army_gk.add_unit(unit)

        self.assertFalse(unit.has_stealth())
        _apply_enhancement(
            unit,
            enh_id="000009777004",
            name="Phial of the Abyss",
        )
        self.assertTrue(unit.has_stealth())

    def test_radiant_champion_adds_mortal_wound_when_bearer_wholly_within_hallowed_ground(self):
        game, army_gk, army_enemy, p1, p2 = _build_game()
        _setup_deployment_zones(game, p1, p2)

        attacker = _make_unit(
            "Paladin Squad",
            keywords=["INFANTRY"],
            faction_keywords=["GREY KNIGHTS"],
        )
        target = _make_unit(
            "Enemy Unit",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army_gk.add_unit(attacker)
        army_enemy.add_unit(target)
        game.map.units = [attacker, target]
        game.rebuild_entity_registry()

        _apply_enhancement(
            attacker,
            enh_id="000009777003",
            name="Radiant Champion",
        )
        self.assertTrue(bool(attacker.special_rules.get("enhancement_bearer_melee_precision")))

        attacker_model = attacker.models[0]
        in_zone = _find_point_wholly_in_deployment_zone(game, attacker_model.model_base, p1.id)
        self.assertIsNotNone(in_zone)
        attacker_model.set_location(in_zone[0], in_zone[1], 0.0, 0.0)
        target.models[0].set_location(in_zone[0] + 1.0, in_zone[1], 0.0, 0.0)

        parent = SimpleNamespace(name="Nemesis Force Weapon", is_melee=lambda: True, is_ranged=lambda: False)
        profile = WargearProfile(
            profile_name="Melee",
            wargear_data={
                "range": "Melee",
                "A": "1",
                "BS_WS": "3+",
                "S": "6",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=parent,
        )

        attack_instance = {"_aura_attack_mods": SimpleNamespace()}
        wound_result = profile._wound_target_with_tracking(
            target,
            attacker_model,
            attack_instance,
            roll_value=5,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(bool(wound_result.get("wound")))
        self.assertEqual(int(attack_instance.get("successful_wound_extra_mortal_wounds", 0) or 0), 1)

        attacker_model.set_location(30.0, 22.0, 0.0, 0.0)
        attack_instance_2 = {"_aura_attack_mods": SimpleNamespace()}
        profile._wound_target_with_tracking(
            target,
            attacker_model,
            attack_instance_2,
            roll_value=5,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertEqual(int(attack_instance_2.get("successful_wound_extra_mortal_wounds", 0) or 0), 0)

    def test_paragon_of_sanctity_queues_choose_quarry_and_marks_target_for_phase(self):
        game, army_gk, army_enemy, p1, _p2 = _build_game()
        source = _make_unit(
            "Grand Master",
            keywords=["INFANTRY", "CHARACTER"],
            faction_keywords=["GREY KNIGHTS"],
        )
        target = _make_unit(
            "Strike Squad",
            keywords=["INFANTRY"],
            faction_keywords=["GREY KNIGHTS"],
        )
        enemy = _make_unit(
            "Enemy Unit",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        source.models[0].set_location(5.0, 5.0, 0.0, 0.0)
        target.models[0].set_location(10.0, 5.0, 0.0, 0.0)
        enemy.models[0].set_location(20.0, 5.0, 0.0, 0.0)
        source.deployed = True
        target.deployed = True
        enemy.deployed = True

        army_gk.add_unit(source)
        army_gk.add_unit(target)
        army_enemy.add_unit(enemy)
        game.map.units = [source, target, enemy]
        game.rebuild_entity_registry()

        _apply_enhancement(
            source,
            enh_id="000009777005",
            name="Paragon of Sanctity",
        )

        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game._on_phase_start_optional_abilities(player=p1, phase=BattleRoundPhases.SHOOTING_PHASE)

        requests = [
            r
            for r in list(game.decision_queue.list() or [])
            if r.decision_type == DECISION_CHOOSE_QUARRY
            and str((r.context or {}).get("ability", "")) == "paragon_of_sanctity"
        ]
        self.assertEqual(len(requests), 1)
        request = requests[0]
        payloads = [dict(opt.payload or {}) for opt in list(request.options or [])]
        self.assertTrue(any(str(p.get("action", "")) == "skip" for p in payloads))

        target_option = next(
            opt
            for opt in list(request.options or [])
            if str((opt.payload or {}).get("target_unit_id", "") or "") == str(get_entity_id(target) or "")
        )

        invalid = resolve_decision_command(game, request, "invalid-option-id", player_id=p1.id)
        self.assertFalse(bool(getattr(invalid, "ok", False)))

        applied = resolve_decision_command(game, request, target_option.option_id, player_id=p1.id)
        self.assertTrue(bool(getattr(applied, "ok", False)))

        target_sr = getattr(target, "special_rules", {}) or {}
        self.assertTrue(bool(target_sr.get("paragon_of_sanctity_hallowed_ground_active")))
        self.assertEqual(int(target_sr.get("paragon_of_sanctity_hallowed_ground_turn", 0) or 0), int(game.turn))
        self.assertEqual(
            str(target_sr.get("paragon_of_sanctity_hallowed_ground_phase", "") or "").strip().upper(),
            "SHOOTING_PHASE",
        )
        self.assertTrue(source.has_used_unit_once_per_battle("paragon_of_sanctity"))
        self.assertTrue(army_gk.grey_knights_detachments.unit_within_hallowed_ground(target, game=game))

        game._on_phase_start_optional_abilities(player=p1, phase=BattleRoundPhases.SHOOTING_PHASE)
        requests_after = [
            r
            for r in list(game.decision_queue.list() or [])
            if r.decision_type == DECISION_CHOOSE_QUARRY
            and str((r.context or {}).get("ability", "")) == "paragon_of_sanctity"
        ]
        self.assertEqual(len(requests_after), 0)


if __name__ == "__main__":
    unittest.main()
