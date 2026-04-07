import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None):
        self.name = name
        self.faction_data = {"name": "Imperial Knights"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "10",
                "T": "10",
                "Sv": "2",
                "W": "12",
                "Ld": "7",
                "OC": "5",
                "base_size": "100mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(name: str, *, keywords=None, faction_keywords=None):
    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
    )
    return Unit(datasheet)


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    army_ik = Army.with_detachment("Imperial Knights", "Valourstrike Lance")
    army_ik.faction_id = "QI"
    army_enemy = Army.with_detachment("Enemy", "Other")
    army_enemy.faction_id = "EN"

    p1 = Player("IK", control=PlayerControl.LOCAL, army=army_ik)
    p2 = Player("Enemy", control=PlayerControl.REMOTE, army=army_enemy)
    game.add_player(p1)
    game.add_player(p2)
    game.current_player_index = 0
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    return game, army_ik, army_enemy, p1, p2


def _apply_enhancement(unit, *, enh_id: str, name: str) -> Enhancement:
    enhancement = Enhancement(
        id=str(enh_id),
        name=str(name),
        faction_id="QI",
        detachment="Valourstrike Lance",
        detachment_id="000010493",
        points=0,
        description="",
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)
    return enhancement


def _find_choose_quarry_request(game, ability_key: str):
    for req in list(game.decision_queue.list() or []):
        ctx = dict(getattr(req, "context", {}) or {})
        if req.decision_type != DECISION_CHOOSE_QUARRY:
            continue
        if str(ctx.get("ability", "") or "") != str(ability_key):
            continue
        return req
    return None


def _find_option_id_for_unit(request, unit) -> str:
    unit_id = str(get_entity_id(unit) or "")
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("target_unit_id", "") or "") == unit_id:
            return str(option.option_id)
    return ""


class TestImperialKnightsValourstrikeEnhancements(unittest.TestCase):
    def _setup_three_units(self):
        game, army_ik, army_enemy, p1, p2 = _build_game()
        source = _make_unit(
            "Knight Source",
            keywords=["IMPERIAL KNIGHTS", "VEHICLE"],
            faction_keywords=["IMPERIUM"],
        )
        target = _make_unit(
            "Knight Target",
            keywords=["IMPERIAL KNIGHTS", "VEHICLE"],
            faction_keywords=["IMPERIUM"],
        )
        enemy = _make_unit(
            "Enemy Unit",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        for unit in (source, target, enemy):
            unit.deployed = True
            set_reserve_status = getattr(unit, "set_reserve_status", None)
            if callable(set_reserve_status):
                set_reserve_status("deployed")
            else:
                unit.reserve_status = "deployed"

        source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        target.models[0].set_location(6.0, 0.0, 0.0, 0.0)
        enemy.models[0].set_location(12.0, 0.0, 0.0, 0.0)

        army_ik.add_unit(source)
        army_ik.add_unit(target)
        army_enemy.add_unit(enemy)
        game.map.units = [source, target, enemy]
        game.rebuild_entity_registry()
        return game, army_ik, army_enemy, p1, p2, source, target, enemy

    def test_iron_chalice_heals_three_when_honoured(self):
        game, army_ik, _army_enemy, p1, _p2, source, target, _enemy = self._setup_three_units()
        _apply_enhancement(source, enh_id="000010493002", name="Bearer of the Iron Chalice")

        army_ik.code_chivalric_honoured = True
        model = target.models[0]
        base_wounds = int(getattr(model, "_base_wounds", 0) or 0)
        model.wounds = int(model.wounds) - 5
        before = int(model.wounds)

        game.phase = BattleRoundPhases.MOVEMENT_PHASE
        game._on_phase_end_imperial_knights_enhancements(player=p1, phase=BattleRoundPhases.MOVEMENT_PHASE)
        req = _find_choose_quarry_request(game, "imperial_knights_iron_chalice")
        self.assertIsNotNone(req)

        invalid = resolve_decision_command(game, req, "invalid-option-id", player_id=p1.id)
        self.assertFalse(bool(getattr(invalid, "ok", False)))

        option_id = _find_option_id_for_unit(req, target)
        self.assertTrue(bool(option_id))
        applied = resolve_decision_command(game, req, option_id, player_id=p1.id)
        self.assertTrue(bool(getattr(applied, "ok", False)))
        self.assertEqual(int(model.wounds), min(base_wounds, before + 3))

    def test_evanescent_ion_grants_and_expires_stealth(self):
        game, _army_ik, _army_enemy, p1, p2, source, target, _enemy = self._setup_three_units()
        _apply_enhancement(source, enh_id="000010493003", name="Bearer of the Evanescent Ion")

        self.assertFalse(target.has_stealth())
        game.phase = BattleRoundPhases.MOVEMENT_PHASE
        game._on_phase_end_imperial_knights_enhancements(player=p1, phase=BattleRoundPhases.MOVEMENT_PHASE)

        req = _find_choose_quarry_request(game, "imperial_knights_evanescent_ion")
        self.assertIsNotNone(req)
        option_id = _find_option_id_for_unit(req, target)
        self.assertTrue(bool(option_id))
        applied = resolve_decision_command(game, req, option_id, player_id=p1.id)
        self.assertTrue(bool(getattr(applied, "ok", False)))
        self.assertTrue(target.has_stealth())

        game.current_player_index = 1
        game.phase = BattleRoundPhases.MOVEMENT_PHASE
        game._on_phase_start_imperial_knights_enhancements(player=p2, phase=BattleRoundPhases.MOVEMENT_PHASE)
        self.assertTrue(target.has_stealth())

        game.current_player_index = 0
        game.phase = BattleRoundPhases.MOVEMENT_PHASE
        game._on_phase_start_imperial_knights_enhancements(player=p1, phase=BattleRoundPhases.MOVEMENT_PHASE)
        self.assertFalse(target.has_stealth())

    def test_judicants_helm_grants_ignores_cover_for_ranged_until_phase_end(self):
        game, _army_ik, _army_enemy, p1, _p2, source, target, enemy = self._setup_three_units()
        _apply_enhancement(source, enh_id="000010493004", name="Bearer of the Judicant's Helm")

        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game._on_phase_start_imperial_knights_enhancements(player=p1, phase=BattleRoundPhases.SHOOTING_PHASE)
        req = _find_choose_quarry_request(game, "imperial_knights_judicants_helm")
        self.assertIsNotNone(req)
        option_id = _find_option_id_for_unit(req, target)
        self.assertTrue(bool(option_id))
        applied = resolve_decision_command(game, req, option_id, player_id=p1.id)
        self.assertTrue(bool(getattr(applied, "ok", False)))

        tsr = getattr(target, "special_rules", {}) or {}
        self.assertTrue(bool(tsr.get("imperial_knights_judicants_helm_ignores_cover_ranged")))

        parent = SimpleNamespace(
            name="Test Cannon",
            is_melee=lambda: False,
            is_ranged=lambda: True,
        )
        profile = WargearProfile(
            "Default",
            wargear_data={
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "10",
                "AP": "-2",
                "D": "3",
                "description": "",
            },
            parent_wargear=parent,
        )
        attack_instance = {"_aura_attack_mods": SimpleNamespace()}
        profile._hit_target_with_tracking(
            enemy,
            target.models[0],
            attack_instance,
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(bool(attack_instance.get("ignores_cover", False)))

        game._on_phase_end_cleanup(player=p1, phase=BattleRoundPhases.SHOOTING_PHASE)
        tsr_after = getattr(target, "special_rules", {}) or {}
        self.assertFalse(bool(tsr_after.get("imperial_knights_judicants_helm_ignores_cover_ranged")))

    def test_lancers_sigil_grants_charge_reroll_until_phase_end(self):
        game, _army_ik, _army_enemy, p1, _p2, source, target, _enemy = self._setup_three_units()
        _apply_enhancement(source, enh_id="000010493005", name="Bearer of the Lancer's Sigil")

        self.assertFalse(target.can_reroll_charge_roll())
        game.phase = BattleRoundPhases.CHARGE_PHASE
        game._on_phase_start_imperial_knights_enhancements(player=p1, phase=BattleRoundPhases.CHARGE_PHASE)
        req = _find_choose_quarry_request(game, "imperial_knights_lancers_sigil")
        self.assertIsNotNone(req)
        option_id = _find_option_id_for_unit(req, target)
        self.assertTrue(bool(option_id))
        applied = resolve_decision_command(game, req, option_id, player_id=p1.id)
        self.assertTrue(bool(getattr(applied, "ok", False)))
        self.assertTrue(target.can_reroll_charge_roll())

        game._on_phase_end_cleanup(player=p1, phase=BattleRoundPhases.CHARGE_PHASE)
        self.assertFalse(target.can_reroll_charge_roll())


if __name__ == "__main__":
    unittest.main()
