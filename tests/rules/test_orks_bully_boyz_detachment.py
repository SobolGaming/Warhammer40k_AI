import unittest
from types import SimpleNamespace


class _DummyPlayer:
    def __init__(self, name="Player"):
        self.name = name
        self.id = name
        self.control = SimpleNamespace(name="REMOTE")
        self.game = None

    def has_control(self):
        return False


class _DummyArmy:
    def __init__(self, *, faction_id="ORK", detachment_type="Bully Boyz"):
        self.faction_id = faction_id
        self.detachment_type = detachment_type
        self.player = _DummyPlayer()
        self.units = []
        self.orks_detachments = None
        self.waaagh = None


class _DummyUnit:
    def __init__(
        self,
        name: str,
        army: _DummyArmy,
        *,
        keywords=None,
        faction_keywords=None,
        deployed=True,
        reserve_status="deployed",
        embarked_in=None,
    ):
        self.name = name
        self.parent_army = army
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.deployed = bool(deployed)
        self.reserve_status = str(reserve_status or "deployed")
        self.embarked_in = embarked_in
        self.possible_abilities = [SimpleNamespace(name="Waaagh!")]
        self.models = []

    def get_parent_army(self):
        return self.parent_army

    @property
    def is_embarked(self):
        return self.embarked_in is not None

    def is_alive(self):
        return True

    def is_in_reserves(self):
        return str(self.reserve_status or "").strip().lower() != "deployed"

    def has_any_keyword(self, keyword: str) -> bool:
        token = str(keyword or "").strip().upper()
        if not token:
            return False
        values = [str(k or "").strip().upper() for k in (self.keywords + self.faction_keywords)]
        return token in set(values)

    def get_attached_unit_members(self):
        return [self]


class TestOrksBullyBoyzDetachment(unittest.TestCase):
    def _make_game(self, player, turn=1):
        game = SimpleNamespace(
            turn=int(turn),
            phase=SimpleNamespace(name="COMMAND_PHASE"),
            event_system=SimpleNamespace(publish=lambda *_a, **_k: None),
        )
        game.get_current_player = lambda: player
        player.game = game
        return game

    def test_second_waaagh_requires_warboss_presence(self):
        from warhammer40k_ai.rules.orks_detachments import OrksDetachmentManager

        army = _DummyArmy(detachment_type="Bully Boyz")
        mgr = OrksDetachmentManager(army)
        army.orks_detachments = mgr

        boyz = _DummyUnit("Boyz", army, keywords=["ORKS", "BOYZ"])
        army.units = [boyz]
        self.assertFalse(mgr.can_call_second_waaagh(player=army.player))

        warboss = _DummyUnit("Warboss", army, keywords=["ORKS", "WARBOSS"])
        army.units = [boyz, warboss]
        self.assertTrue(mgr.can_call_second_waaagh(player=army.player))

        trukk = _DummyUnit("Trukk", army, keywords=["ORKS", "TRANSPORT"], deployed=True)
        embarked_warboss = _DummyUnit(
            "Warboss In Mega Armour",
            army,
            keywords=["ORKS", "WARBOSS"],
            deployed=False,
            embarked_in=trukk,
        )
        army.units = [boyz, trukk, embarked_warboss]
        self.assertTrue(mgr.can_call_second_waaagh(player=army.player))

    def test_da_boss_is_watchin_second_waaagh_scope(self):
        from warhammer40k_ai.rules.orks_detachments import OrksDetachmentManager
        from warhammer40k_ai.rules.waaagh import WaaaghManager

        army = _DummyArmy(detachment_type="Bully Boyz")
        player = army.player
        game = self._make_game(player, turn=1)

        warboss = _DummyUnit("Warboss", army, keywords=["ORKS", "WARBOSS"])
        nobz = _DummyUnit("Nobz", army, keywords=["ORKS", "NOBZ"])
        meganobz = _DummyUnit("Meganobz", army, keywords=["ORKS", "MEGANOBZ"])
        boyz = _DummyUnit("Boyz", army, keywords=["ORKS", "BOYZ"])
        army.units = [warboss, nobz, meganobz, boyz]

        army.orks_detachments = OrksDetachmentManager(army)
        army.waaagh = WaaaghManager(army)

        self.assertTrue(army.waaagh.can_call_now(game=game, player=player))
        self.assertTrue(army.waaagh.call_waaagh(game=game, player=player))
        self.assertEqual(army.waaagh.calls_this_battle, 1)
        self.assertEqual(army.waaagh.active_scope, "all")
        self.assertTrue(army.waaagh.unit_is_affected(boyz, game=game))

        self.assertFalse(army.waaagh.can_call_now(game=game, player=player))

        game.turn = 2
        army.waaagh.on_command_phase_start(game=game, player=player)
        self.assertFalse(army.waaagh.active)
        self.assertTrue(army.waaagh.can_call_now(game=game, player=player))

        self.assertTrue(army.waaagh.call_waaagh(game=game, player=player))
        self.assertEqual(army.waaagh.calls_this_battle, 2)
        self.assertEqual(army.waaagh.active_scope, "bully_boyz_restricted")
        self.assertTrue(army.waaagh.unit_is_affected(warboss, game=game))
        self.assertTrue(army.waaagh.unit_is_affected(nobz, game=game))
        self.assertTrue(army.waaagh.unit_is_affected(meganobz, game=game))
        self.assertFalse(army.waaagh.unit_is_affected(boyz, game=game))

    def test_second_waaagh_unavailable_without_warboss(self):
        from warhammer40k_ai.rules.orks_detachments import OrksDetachmentManager
        from warhammer40k_ai.rules.waaagh import WaaaghManager

        army = _DummyArmy(detachment_type="Bully Boyz")
        player = army.player
        game = self._make_game(player, turn=1)

        warboss = _DummyUnit("Warboss", army, keywords=["ORKS", "WARBOSS"])
        boyz = _DummyUnit("Boyz", army, keywords=["ORKS", "BOYZ"])
        army.units = [warboss, boyz]

        army.orks_detachments = OrksDetachmentManager(army)
        army.waaagh = WaaaghManager(army)

        self.assertTrue(army.waaagh.call_waaagh(game=game, player=player))
        game.turn = 2
        army.waaagh.on_command_phase_start(game=game, player=player)

        army.units = [boyz]
        self.assertFalse(army.waaagh.can_call_now(game=game, player=player))


if __name__ == "__main__":
    unittest.main()
