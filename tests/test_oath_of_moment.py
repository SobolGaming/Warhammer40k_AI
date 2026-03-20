import unittest
from types import SimpleNamespace


class _RegistryStub:
    def __init__(self, units, player=None):
        self._units = {str(getattr(u, "_id", "")): u for u in units}
        self._players = {}
        if player is not None:
            pid = str(getattr(player, "id", "") or "")
            if pid:
                self._players[pid] = player

    def get(self, entity_id: str, *, kind: str):
        if kind == "unit":
            return self._units.get(str(entity_id))
        if kind == "player":
            return self._players.get(str(entity_id))
        return None


class _GameStub:
    def __init__(self, *, enemies, units, player=None):
        from warhammer40k_ai.engine.decisions import DecisionQueue

        self.is_authoritative = True
        self.decision_queue = DecisionQueue()
        self.entity_registry = _RegistryStub(units, player=player)
        self._enemies = list(enemies or [])

    def request_decision(self, request):
        self.decision_queue.add(request)

    def get_enemy_units(self, _player):
        return list(self._enemies)


class TestOathOfMoment(unittest.TestCase):
    def test_codex_detachment_includes_bastion_and_orbital_faction_pack_detachments(self):
        from warhammer40k_ai.roster.army import Army

        expectations = {
            "Bastion Task Force": True,
            "Orbital Assault Force": True,
            "Shadowmark Talon": False,
        }
        for detachment_name, expected in expectations.items():
            with self.subTest(detachment=detachment_name):
                army = Army("Space Marines", detachment_name)
                army.faction_id = "SM"
                army.configure_rule_managers(force=True)
                mgr = getattr(army, "space_marines_detachments", None)
                self.assertIsNotNone(mgr)
                self.assertEqual(bool(mgr.is_codex_detachment()), bool(expected))

    def test_oath_command_phase_clears_and_selects_target(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.rules.oath_of_moment import OathOfMomentManager

        class _Round:
            remained_stationary_this_round = False
            charged_this_round = False

        class _Unit:
            def __init__(self, name: str, keywords=None):
                self.name = name
                self._id = name
                self.toughness = 5
                self.round_state = _Round()
                self.models = []
                self.special_rules = {}
                self._keywords = set((keywords or []))
                self._army = None
                self.embarked_in = None

            def set_army(self, army):
                self._army = army

            def get_parent_army(self):
                return self._army

            def get_attached_unit_root(self):
                return self

            def is_alive(self):
                return True

            @property
            def is_embarked(self):
                return self.embarked_in is not None

            def has_any_keyword(self, keyword: str) -> bool:
                return keyword.strip().upper() in {k.upper() for k in self._keywords}

        enemy_unit = _Unit("Enemy1")
        old_unit = _Unit("OldTarget")

        player = SimpleNamespace(
            name="P1",
            id="P1",
            control=SimpleNamespace(name="REMOTE"), has_control=lambda: False,
            _choose_optional_value=lambda *_a, **_k: None,
        )
        army = Army("Space Marines", "Gladius Task Force")
        army.faction_id = "SM"
        player.get_army = lambda: army
        army.player = player

        for u in (enemy_unit, old_unit):
            u.set_army(army)

        mgr = OathOfMomentManager(army)
        army.oath_of_moment = mgr

        # Pre-seed a stale target that should be cleared/replaced.
        mgr.set_target(old_unit)
        self.assertEqual(mgr.oathOfMomentTargetUnitId, old_unit._id)

        game = _GameStub(enemies=[enemy_unit], units=[enemy_unit, old_unit], player=player)
        mgr.on_command_phase_start(game=game, player=player)

        from warhammer40k_ai.engine.decision_dispatcher import dispatch_decision
        from warhammer40k_ai.engine.decisions import DecisionResult

        req = game.decision_queue.peek()
        self.assertIsNotNone(req)
        option = next(
            opt for opt in req.options if opt.payload.get("target_unit_id") == getattr(enemy_unit, "_id", None)
        )
        result = DecisionResult(decision_id=req.decision_id, player_id=player.id, option_id=option.option_id, payload={})
        apply_result = dispatch_decision(game, req, result)
        self.assertTrue(apply_result.ok)

        self.assertEqual(mgr.oathOfMomentTargetUnitId, enemy_unit._id)

    def test_oath_reroll_hit_and_wound_bonus(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.engine.event.system import EventSystem
        from warhammer40k_ai.units.model import Model
        from warhammer40k_ai.utility.model_base import Base, BaseType
        from warhammer40k_ai.units.wargear import WargearProfile
        from warhammer40k_ai.rules.oath_of_moment import OathOfMomentManager

        # Minimal game/player/army wiring for roll_made publish calls
        game = SimpleNamespace(event_system=EventSystem(), map=None)
        player = SimpleNamespace(name="P1", id="P1", control=SimpleNamespace(name="LOCAL"), has_control=lambda: True, game=game)
        army = Army("Space Marines", "Gladius Task Force")
        army.faction_id = "SM"
        army.player = player

        class _Round:
            remained_stationary_this_round = False
            charged_this_round = False

        class _Unit:
            def __init__(self, name: str, keywords=None):
                self.name = name
                self._id = name
                self.toughness = 5
                self.round_state = _Round()
                self.models = []
                self.special_rules = {}
                self._keywords = set((keywords or []))
                self.embarked_in = None

            def get_parent_army(self):
                return army

            def get_attached_unit_root(self):
                return self

            def is_alive(self):
                return True

            @property
            def is_embarked(self):
                return self.embarked_in is not None

            def has_any_keyword(self, keyword: str) -> bool:
                return keyword.strip().upper() in {k.upper() for k in self._keywords}

            def get_models_for_wound_allocation(self):
                return self.models

        attacker_unit = _Unit("Intercessors", keywords=["ADEPTUS ASTARTES"])
        target_unit = _Unit("Target")
        army.units = [attacker_unit]

        mgr = OathOfMomentManager(army)
        army.oath_of_moment = mgr
        mgr.set_target(target_unit)

        attacker_model = Model(
            name="Marine",
            movement=6,
            toughness=4,
            save=3,
            wounds=2,
            leadership=6,
            objective_control=2,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        attacker_model.parent_unit = attacker_unit

        target_model = Model(
            name="Enemy",
            movement=6,
            toughness=5,
            save=3,
            wounds=2,
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        target_model.parent_unit = target_unit
        target_unit.models = [target_model]

        melee_parent = SimpleNamespace(name="Test Weapon", is_melee=lambda: True)
        prof = WargearProfile(
            profile_name="Melee",
            wargear_data={
                "range": "Melee",
                "A": "1",
                "BS_WS": "4+",
                "S": "5",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=melee_parent,
        )

        # Provide aura mods to avoid importing aura system
        aura_stub = SimpleNamespace(
            hit=0,
            wound=0,
            reroll_hit_ones=False,
            reroll_wound_ones=False,
            reroll_hit_reasons=(),
            reroll_wound_reasons=(),
            target_toughness_delta=0,
            target_toughness_reasons=(),
        )

        from warhammer40k_ai.units import wargear as wargear_mod
        seq = iter([
            2, 5,  # hit roll fail then reroll success (4+)
            4,     # wound roll (S==T => 4+; +1 from Oath makes it 3+)
        ])
        old_get_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _s: next(seq)
        try:
            attack_instance = {"_aura_attack_mods": aura_stub}
            hit_res = prof._hit_target_with_tracking(target_unit, attacker_model, attack_instance)
            self.assertEqual(int(hit_res["roll"]), 5)
            self.assertTrue(any("Oath of Moment" in x for x in hit_res.get("special_effects", [])))

            wound_res = prof._wound_target_with_tracking(target_unit, attacker_model, attack_instance)
            self.assertTrue(any("Oath of Moment" in x for x in wound_res.get("modifiers", [])))
        finally:
            wargear_mod.get_roll = old_get_roll

    def test_oath_excludes_embarked_targets(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.rules.oath_of_moment import OathOfMomentManager

        class _Unit:
            def __init__(self, name: str):
                self.name = name
                self._id = name
                self.embarked_in = None

            def get_attached_unit_root(self):
                return self

            @property
            def is_embarked(self):
                return self.embarked_in is not None

            def is_alive(self):
                return True

        embarked = _Unit("EmbarkedUnit")
        embarked.embarked_in = object()
        available = _Unit("AvailableUnit")

        player = SimpleNamespace(name="P1", id="P1", control=SimpleNamespace(name="REMOTE"), has_control=lambda: False, _choose_optional_value=lambda *_a, **_k: None)
        army = Army("Space Marines", "Gladius Task Force")
        army.faction_id = "SM"
        player.get_army = lambda: army
        army.player = player

        mgr = OathOfMomentManager(army)
        army.oath_of_moment = mgr

        game = _GameStub(enemies=[embarked, available], units=[embarked, available], player=player)
        mgr.on_command_phase_start(game=game, player=player)

        from warhammer40k_ai.engine.decision_dispatcher import dispatch_decision
        from warhammer40k_ai.engine.decisions import DecisionResult

        req = game.decision_queue.peek()
        self.assertIsNotNone(req)
        option = next(
            opt for opt in req.options if opt.payload.get("target_unit_id") == getattr(available, "_id", None)
        )
        result = DecisionResult(decision_id=req.decision_id, player_id=player.id, option_id=option.option_id, payload={})
        apply_result = dispatch_decision(game, req, result)
        self.assertTrue(apply_result.ok)

        self.assertEqual(mgr.oathOfMomentTargetUnitId, available._id)

    def test_oath_persists_on_surviving_leader_after_attached_target_splits(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.rules.oath_of_moment import OathOfMomentManager

        class _Unit:
            def __init__(self, name: str):
                self.name = name
                self._id = name
                self.embarked_in = None
                self.attached_to = None
                self.attached_leaders = []
                self._alive = True

            def get_attached_unit_root(self):
                return self.attached_to if self.attached_to is not None else self

            def get_attached_unit_members(self):
                root = self.get_attached_unit_root()
                return [root] + list(getattr(root, "attached_leaders", []) or [])

            @property
            def is_embarked(self):
                return self.embarked_in is not None

            def is_alive(self):
                return bool(self._alive)

            def detach_from_unit(self):
                bodyguard = self.attached_to
                if bodyguard is None:
                    return
                leaders = list(getattr(bodyguard, "attached_leaders", []) or [])
                if self in leaders:
                    leaders.remove(self)
                bodyguard.attached_leaders = leaders
                self.attached_to = None

        bodyguard = _Unit("Bodyguard")
        leader = _Unit("Leader")
        leader.attached_to = bodyguard
        bodyguard.attached_leaders = [leader]
        backup = _Unit("Backup")

        player = SimpleNamespace(name="P1", id="P1")
        army = Army("Space Marines", "Gladius Task Force")
        army.faction_id = "SM"
        army.player = player
        player.get_army = lambda: army
        army.units = [bodyguard, leader, backup]

        mgr = OathOfMomentManager(army)
        army.oath_of_moment = mgr
        mgr.set_target(bodyguard, queue_followups=False)
        mgr.set_backup_target(backup)

        self.assertTrue(mgr.is_oath_target(bodyguard))
        self.assertTrue(mgr.is_oath_target(leader))

        bodyguard._alive = False
        leader.detach_from_unit()

        changed = mgr.on_oath_target_destroyed(bodyguard, player=player)

        self.assertTrue(bool(changed))
        self.assertEqual(str(mgr.oathOfMomentTargetUnitId or ""), leader._id)
        self.assertEqual(str(mgr.oathOfMomentBackupTargetUnitId or ""), backup._id)
        self.assertTrue(mgr.is_oath_target(leader))
        self.assertFalse(mgr.is_oath_target(bodyguard))

    def test_extremis_level_threat_queues_activates_and_expires(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.rules.oath_of_moment import OathOfMomentManager
        from warhammer40k_ai.engine.decision_dispatcher import dispatch_decision
        from warhammer40k_ai.engine.decisions import DecisionResult
        from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_CONFIRM_YES_NO

        class _Unit:
            def __init__(self, name: str, keywords=None):
                self.name = name
                self._id = name
                self._keywords = set((keywords or []))
                self.embarked_in = None
                self._army = None

            def set_army(self, army):
                self._army = army

            def get_parent_army(self):
                return self._army

            def get_attached_unit_root(self):
                return self

            @property
            def is_embarked(self):
                return self.embarked_in is not None

            def is_alive(self):
                return True

            def has_any_keyword(self, keyword: str) -> bool:
                return keyword.strip().upper() in {k.upper() for k in self._keywords}

        enemy_unit = _Unit("Enemy1")
        attacker_unit = _Unit("Intercessors", keywords=["ADEPTUS ASTARTES"])

        player = SimpleNamespace(
            name="P1",
            id="P1",
            control=SimpleNamespace(name="REMOTE"),
            has_control=lambda: False,
            _choose_optional_value=lambda *_a, **_k: None,
        )
        army = Army("Space Marines", "1st Company Task Force")
        army.faction_id = "SM"
        player.get_army = lambda: army
        army.player = player
        for u in (enemy_unit, attacker_unit):
            u.set_army(army)

        mgr = OathOfMomentManager(army)
        army.oath_of_moment = mgr

        game = _GameStub(enemies=[enemy_unit], units=[enemy_unit, attacker_unit], player=player)
        game.players = [player]
        game._resolve_army_by_id = lambda army_id: army if str(getattr(army, "_id", "")) == str(army_id) else None

        mgr.on_command_phase_start(game=game, player=player)
        pending = list(game.decision_queue.list() or [])
        self.assertTrue(any(str((req.context or {}).get("ability", "")) == "oath_of_moment" for req in pending))
        self.assertTrue(any(str((req.context or {}).get("ability", "")) == "extremis_level_threat" for req in pending))

        oath_req = next(
            req
            for req in pending
            if req.decision_type == DECISION_CHOOSE_QUARRY and str((req.context or {}).get("ability", "")) == "oath_of_moment"
        )
        oath_opt = next(opt for opt in oath_req.options if opt.payload.get("target_unit_id") == enemy_unit._id)
        oath_res = DecisionResult(decision_id=oath_req.decision_id, player_id=player.id, option_id=oath_opt.option_id, payload={})
        self.assertTrue(dispatch_decision(game, oath_req, oath_res).ok)

        ex_req = next(
            req
            for req in list(game.decision_queue.list() or [])
            if req.decision_type == DECISION_CONFIRM_YES_NO
            and str((req.context or {}).get("ability", "")) == "extremis_level_threat"
        )
        ex_opt = next(opt for opt in ex_req.options if bool((opt.payload or {}).get("choice", False)))
        ex_res = DecisionResult(decision_id=ex_req.decision_id, player_id=player.id, option_id=ex_opt.option_id, payload={})
        self.assertTrue(dispatch_decision(game, ex_req, ex_res).ok)

        self.assertTrue(bool(mgr.extremisLevelThreatActive))
        self.assertTrue(bool(mgr.extremisLevelThreatUsed))
        self.assertTrue(mgr.extremis_level_threat_reroll_wound_applies(attacker_unit, enemy_unit))
        self.assertFalse(mgr.can_activate_extremis_level_threat())

        mgr.on_command_phase_start(game=None, player=player)
        self.assertFalse(bool(mgr.extremisLevelThreatActive))
        self.assertTrue(bool(mgr.extremisLevelThreatUsed))

    def test_extremis_level_threat_grants_wound_reroll_vs_oath_target(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.engine.event.system import EventSystem
        from warhammer40k_ai.units.model import Model
        from warhammer40k_ai.utility.model_base import Base, BaseType
        from warhammer40k_ai.units.wargear import WargearProfile
        from warhammer40k_ai.rules.oath_of_moment import OathOfMomentManager

        game = SimpleNamespace(event_system=EventSystem(), map=None, phase=SimpleNamespace(name="COMMAND_PHASE"))
        player = SimpleNamespace(
            name="P1",
            id="P1",
            control=SimpleNamespace(name="LOCAL"),
            has_control=lambda: True,
            game=game,
        )
        army = Army("Space Marines", "1st Company Task Force")
        army.faction_id = "SM"
        army.player = player
        player.get_army = lambda: army

        class _Round:
            remained_stationary_this_round = False
            charged_this_round = False

        class _Unit:
            def __init__(self, name: str, keywords=None):
                self.name = name
                self._id = name
                self.toughness = 4
                self.round_state = _Round()
                self.models = []
                self.special_rules = {}
                self._keywords = set((keywords or []))
                self.embarked_in = None

            def get_parent_army(self):
                return army

            def get_attached_unit_root(self):
                return self

            def is_alive(self):
                return True

            @property
            def is_embarked(self):
                return self.embarked_in is not None

            def has_any_keyword(self, keyword: str) -> bool:
                return keyword.strip().upper() in {k.upper() for k in self._keywords}

            def get_models_for_wound_allocation(self):
                return self.models

        attacker_unit = _Unit("Intercessors", keywords=["ADEPTUS ASTARTES"])
        target_unit = _Unit("Target")
        army.units = [attacker_unit]

        mgr = OathOfMomentManager(army)
        army.oath_of_moment = mgr
        mgr._army_has_oath = lambda: True
        mgr.set_target(target_unit)
        self.assertTrue(mgr.activate_extremis_level_threat(game=game, player=player))
        self.assertTrue(bool(mgr.extremisLevelThreatActive))

        attacker_model = Model(
            name="Marine",
            movement=6,
            toughness=4,
            save=3,
            wounds=2,
            leadership=6,
            objective_control=2,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        attacker_model.parent_unit = attacker_unit

        target_model = Model(
            name="Enemy",
            movement=6,
            toughness=4,
            save=3,
            wounds=2,
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        target_model.parent_unit = target_unit
        target_unit.models = [target_model]

        melee_parent = SimpleNamespace(name="Test Weapon", is_melee=lambda: True)
        prof = WargearProfile(
            profile_name="Melee",
            wargear_data={
                "range": "Melee",
                "A": "1",
                "BS_WS": "4+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=melee_parent,
        )

        aura_stub = SimpleNamespace(
            hit=0,
            wound=0,
            reroll_hit_ones=False,
            reroll_wound_ones=False,
            reroll_hit_reasons=(),
            reroll_wound_reasons=(),
            target_toughness_delta=0,
            target_toughness_reasons=(),
        )

        from warhammer40k_ai.units import wargear as wargear_mod

        seq = iter([
            4,  # hit (success, no hit reroll needed)
            2, 5,  # wound (fail then Extremis-level Threat reroll to success)
        ])
        old_get_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _s: next(seq)
        try:
            attack_instance = {"_aura_attack_mods": aura_stub}
            _ = prof._hit_target_with_tracking(target_unit, attacker_model, attack_instance)
            wound_res = prof._wound_target_with_tracking(target_unit, attacker_model, attack_instance)
            self.assertEqual(int(wound_res.get("roll", 0) or 0), 5)
            self.assertEqual(int(wound_res.get("reroll", 0) or 0), 5)
            self.assertTrue(any("Extremis-level Threat" in x for x in wound_res.get("special_effects", [])))
        finally:
            wargear_mod.get_roll = old_get_roll


if __name__ == "__main__":
    unittest.main()
