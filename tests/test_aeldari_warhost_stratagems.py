import unittest
from types import SimpleNamespace


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        keywords=None,
        faction_keywords=None,
        transport="",
    ):
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
        self.transport = transport


def _make_unit(name, *, keywords=None, transport=""):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        transport=transport,
    )
    return Unit(datasheet)


def _build_game():
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)

    army1 = Army("Aeldari", "Warhost")
    army1.faction_id = "AE"
    army2 = Army("Enemy", "Other")
    army2.faction_id = "EN"

    p1 = Player("P1", control=PlayerControl.LOCAL, army=army1)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army2)
    game.add_player(p1)
    game.add_player(p2)

    p1.command_points = 3
    p2.command_points = 3
    return game, p1, p2, army1, army2


class TestAeldariWarhostStratagems(unittest.TestCase):
    def test_blitzing_firepower_sets_crit_on_5_with_sustained(self):
        from warhammer40k_ai.units.wargear import Wargear
        from warhammer40k_ai.units import wargear as wargear_module

        game, p1, _p2, army1, army2 = _build_game()
        attacker = _make_unit("Blitzers", keywords=["ASURYANI", "INFANTRY"])
        target = _make_unit("Target", keywords=["INFANTRY"])
        army1.add_unit(attacker)
        army2.add_unit(target)

        attacker.deployed = True
        target.deployed = True
        attacker.models[0].set_location(5.0, 5.0, 0.0, 0.0)
        target.models[0].set_location(10.0, 5.0, 0.0, 0.0)
        game.map.place_unit(attacker)
        game.map.place_unit(target)

        phase = SimpleNamespace(name="SHOOTING_PHASE")
        game.event_system.publish("phase_start", player=p1, phase=phase)
        ok = p1.stratagems.use("BLITZING FIREPOWER", unit=attacker, phase_name="Shooting phase")
        self.assertTrue(ok)

        data = {
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "Sustained Hits 1",
            "type": "Ranged",
            "name": "Test Gun",
        }
        profile = Wargear(data).profiles["default"]

        attack_instance = {
            "crit_hit": False,
            "crit_wound": False,
            "mortal_wound": False,
            "below_half_distance": False,
            "damage": 0,
            "target_toughness_override": None,
        }

        original_roll = wargear_module.get_roll
        wargear_module.get_roll = lambda _d: 5
        try:
            result = profile._hit_target_with_tracking(target, attacker.models[0], attack_instance)
        finally:
            wargear_module.get_roll = original_roll

        self.assertTrue(result["hit"])
        self.assertTrue(attack_instance.get("crit_hit"))

    def test_blitzing_firepower_grants_sustained_hits(self):
        from warhammer40k_ai.units.wargear import Wargear
        from warhammer40k_ai.units import wargear as wargear_module

        game, p1, _p2, army1, army2 = _build_game()
        attacker = _make_unit("Blitzers", keywords=["ASURYANI", "INFANTRY"])
        target = _make_unit("Target", keywords=["INFANTRY"])
        army1.add_unit(attacker)
        army2.add_unit(target)

        attacker.deployed = True
        target.deployed = True
        attacker.models[0].set_location(5.0, 5.0, 0.0, 0.0)
        target.models[0].set_location(10.0, 5.0, 0.0, 0.0)
        game.map.place_unit(attacker)
        game.map.place_unit(target)

        phase = SimpleNamespace(name="SHOOTING_PHASE")
        game.event_system.publish("phase_start", player=p1, phase=phase)
        ok = p1.stratagems.use("BLITZING FIREPOWER", unit=attacker, phase_name="Shooting phase")
        self.assertTrue(ok)

        data = {
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
            "type": "Ranged",
            "name": "Test Gun",
        }
        profile = Wargear(data).profiles["default"]

        attack_instance = {
            "crit_hit": False,
            "crit_wound": False,
            "mortal_wound": False,
            "below_half_distance": False,
            "damage": 0,
            "target_toughness_override": None,
        }

        original_roll = wargear_module.get_roll
        wargear_module.get_roll = lambda _d: 6
        try:
            result = profile._hit_target_with_tracking(target, attacker.models[0], attack_instance)
        finally:
            wargear_module.get_roll = original_roll

        self.assertTrue(result["hit"])
        self.assertEqual(attack_instance.get("sustained_hit"), 1)
        self.assertTrue(any("Blitzing Firepower" in e for e in result.get("special_effects", [])))

    def test_feigned_retreat_allows_shoot_and_charge(self):
        game, p1, _p2, army1, _army2 = _build_game()
        unit = _make_unit("Warp Walker", keywords=["ASURYANI", "INFANTRY"])
        army1.add_unit(unit)
        unit.deployed = True

        phase = SimpleNamespace(name="MOVEMENT_PHASE")
        game.event_system.publish("phase_start", player=p1, phase=phase)
        unit.round_state.fell_back_this_round = True
        ok = p1.stratagems.use("FEIGNED RETREAT", unit=unit, phase_name="Movement phase", action="fall_back")
        self.assertTrue(ok)
        self.assertTrue(unit.has_fell_back_and_shoot())
        self.assertTrue(unit.can_charge_after_fall_back())

    def test_fire_and_fade_sets_restrictions(self):
        from warhammer40k_ai.engine.decision_kinds import DECISION_MOVE_UNIT

        game, p1, _p2, army1, _army2 = _build_game()
        unit = _make_unit("Dire Avengers", keywords=["ASURYANI", "INFANTRY"])
        army1.add_unit(unit)
        unit.deployed = True
        unit.round_state.shot_this_round = True

        phase = SimpleNamespace(name="SHOOTING_PHASE")
        game.event_system.publish("phase_start", player=p1, phase=phase)
        ok = p1.stratagems.use("FIRE AND FADE", unit=unit, phase_name="Shooting phase")
        self.assertTrue(ok)
        sr = unit.special_rules
        self.assertEqual(sr.get("fire_and_fade_no_charge_turn_owner"), p1.id)
        self.assertEqual(sr.get("fire_and_fade_no_embark_turn_owner"), p1.id)
        pending = [
            req
            for req in list(game.decision_queue.list() or [])
            if getattr(req, "decision_type", None) == DECISION_MOVE_UNIT
            and dict(getattr(req, "context", {}) or {}).get("reactive_move_kind") == "fire_and_fade"
        ]
        self.assertTrue(pending)

    def test_lightning_fast_reactions_sets_active(self):
        game, p1, p2, army1, _army2 = _build_game()
        unit = _make_unit("Howling Banshees", keywords=["ASURYANI", "INFANTRY"])
        army1.add_unit(unit)
        unit.deployed = True

        game.current_player_index = 1  # opponent's turn
        phase = SimpleNamespace(name="SHOOTING_PHASE")
        game.event_system.publish("phase_start", player=p2, phase=phase)
        ok = p1.stratagems.use("LIGHTNING-FAST REACTIONS", unit=unit, phase_name="Shooting phase")
        self.assertTrue(ok)
        self.assertTrue(unit.special_rules.get("lightning_fast_reactions_active"))

    def test_skyborne_sanctuary_embarks(self):
        game, p1, _p2, army1, _army2 = _build_game()
        transport = _make_unit(
            "Wave Serpent",
            keywords=["ASURYANI", "Transport"],
            transport="Transport Capacity 10",
        )
        unit = _make_unit("Guardians", keywords=["ASURYANI", "INFANTRY"])
        army1.add_unit(transport)
        army1.add_unit(unit)

        transport.deployed = True
        unit.deployed = True
        transport.models[0].set_location(10.0, 10.0, 0.0, 0.0)
        unit.models[0].set_location(10.0, 10.0, 0.0, 0.0)
        game.map.place_unit(transport)
        game.map.place_unit(unit)

        unit.round_state.charged_this_round = True
        unit.round_state.disembarked_this_round = True

        phase = SimpleNamespace(name="FIGHT_PHASE")
        game.event_system.publish("phase_start", player=p1, phase=phase)
        ok = p1.stratagems.use(
            "SKYBORNE SANCTUARY",
            unit=unit,
            transport_unit=transport,
            phase_name="Fight phase",
        )
        self.assertTrue(ok)
        self.assertIs(unit.embarked_in, transport)

    def test_webway_tunnel_sends_to_reserves(self):
        game, p1, p2, army1, _army2 = _build_game()
        unit = _make_unit("Rangers", keywords=["ASURYANI", "INFANTRY"])
        army1.add_unit(unit)
        unit.deployed = True
        unit.models[0].set_location(1.0, 10.0, 0.0, 0.0)
        game.map.place_unit(unit)

        game.current_player_index = 1  # opponent's turn
        phase = SimpleNamespace(name="FIGHT_PHASE")
        game.event_system.publish("phase_start", player=p2, phase=phase)
        ok = p1.stratagems.use("WEBWAY TUNNEL", unit=unit, phase_name="Fight phase")
        self.assertTrue(ok)
        self.assertEqual(unit.reserve_status, "strategic_reserves")
        self.assertNotIn(unit, game.map.units)


if __name__ == "__main__":
    unittest.main()
