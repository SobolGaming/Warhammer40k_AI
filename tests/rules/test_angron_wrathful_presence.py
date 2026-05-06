from types import SimpleNamespace


class _DummyBase:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)

    def get_base_shape(self):
        from shapely.geometry import Point
        return Point(self.x, self.y)


class _DummyMap:
    def __init__(self, units):
        self.units = list(units)

    def get_enemy_units(self, unit):
        return [u for u in self.units if u.get_parent_army() != unit.get_parent_army()]

    def get_friendly_units(self, unit):
        return [u for u in self.units if u.get_parent_army() == unit.get_parent_army()]


def _make_stub_unit(name: str, army, *, keywords=()):
    from warhammer40k_ai.units.unit import Unit

    u = Unit.__new__(Unit)
    u.name = name
    u.deployed = True
    u.reserve_status = "deployed"
    u.has_keyword = lambda k: k.lower() in {kw.lower() for kw in keywords}
    u.has_any_keyword = lambda k: k.lower() in {kw.lower() for kw in keywords}
    u.get_parent_army = lambda: army
    u.is_alive = lambda: True
    u.get_attached_unit_root = lambda: u
    u.get_attached_unit_members = lambda: [u]
    u.get_attached_unit_models = lambda: u.models
    u.round_state = SimpleNamespace(remained_stationary_this_round=True)
    u.models = [SimpleNamespace(is_alive=True, model_base=_DummyBase(), parent_unit=u)]
    u.possible_abilities = []
    return u


def test_blood_gods_favour_grants_six_rerolls():
    from warhammer40k_ai.rules.blessings_of_khorne import BlessingsOfKhorneManager
    from warhammer40k_ai.rules.wrathful_presence import KEY_BLOOD_GODS_FAVOUR, set_active_wrathful_presence

    player = SimpleNamespace(name="Player 1", id="Player 1")
    game = SimpleNamespace(turn=2)
    player.game = game
    army = SimpleNamespace(player=player, units=[])

    angron = _make_stub_unit("Angron", army, keywords=("WORLD EATERS",))
    angron.possible_abilities = [SimpleNamespace(name="Wrathful Presence")]
    set_active_wrathful_presence(angron, KEY_BLOOD_GODS_FAVOUR, battle_round=2)
    army.units.append(angron)

    mgr = BlessingsOfKhorneManager()
    assert mgr.favoured_of_khorne_rerolls_for_army(army) == 6


def test_wrathful_presence_defers_blessings_until_aura_choice(monkeypatch):
    from warhammer40k_ai.engine.decision_handlers.abilities import _apply_choose_wrathful
    from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_BLESSINGS, DECISION_CHOOSE_WRATHFUL_PRESENCE
    from warhammer40k_ai.engine.decisions import DecisionQueue, DecisionResult
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.rules.wrathful_presence import KEY_BLOOD_GODS_FAVOUR

    class _Game:
        def __init__(self):
            self.turn = 1
            self.players = []
            self.decision_queue = DecisionQueue()
            self.is_authoritative = True
            rolls = iter([1, 1, 2, 2, 3, 3, 4, 4])
            self.random_source = SimpleNamespace(randint=lambda _low, _high: next(rolls))

        def request_decision(self, request):
            self.decision_queue.add(request)

    army = Army("World Eaters")
    angron = _make_stub_unit("Angron", army, keywords=("WORLD EATERS",))
    angron._id = "unit:angron"
    angron.possible_abilities = [SimpleNamespace(name="Wrathful Presence")]
    angron.attached_unit_has_blessings_of_khorne = lambda: True
    angron._find_ability_with_patterns = lambda _patterns: (False, None)
    army.units = [angron]

    game = _Game()
    player = SimpleNamespace(id="player:we", name="World Eaters", game=game, army=army, get_army=lambda: army)
    game.players = [player]
    army.player = player

    monkeypatch.setattr("warhammer40k_ai.utility.ability_support.army_has_ability_id", lambda _army, _ability: True)

    army.on_battle_round_start(1)

    pending = game.decision_queue.list()
    assert [req.decision_type for req in pending] == [DECISION_CHOOSE_WRATHFUL_PRESENCE]

    wrathful_req = pending[0]
    option = next(
        opt
        for opt in wrathful_req.options
        if (opt.payload or {}).get("choice_key") == KEY_BLOOD_GODS_FAVOUR
    )
    result = DecisionResult(
        decision_id=wrathful_req.decision_id,
        player_id=wrathful_req.player_id,
        option_id=option.option_id,
        payload=dict(option.payload or {}),
    )
    game.decision_queue.pop(wrathful_req.decision_id)
    _apply_choose_wrathful(game, wrathful_req, result)

    pending = game.decision_queue.list()
    assert [req.decision_type for req in pending] == [DECISION_CHOOSE_BLESSINGS]
    ctx = dict(pending[0].context.get("ctx") or {})
    assert ctx["battle_round"] == 1
    assert ctx["rerolls_allowed"] == 6


def test_overwhelming_wrath_blocks_fall_back_on_failed_leadership(monkeypatch):
    from warhammer40k_ai.units.unit import Unit
    from warhammer40k_ai.rules.wrathful_presence import KEY_OVERWHELMING_WRATH, set_active_wrathful_presence

    player_a = SimpleNamespace(name="Player A", id="Player A")
    player_b = SimpleNamespace(name="Player B", id="Player B")
    game = SimpleNamespace(turn=2)
    player_a.game = game
    player_b.game = game
    army_a = SimpleNamespace(player=player_a, units=[])
    army_b = SimpleNamespace(player=player_b, units=[])

    angron = _make_stub_unit("Angron", army_a, keywords=("WORLD EATERS",))
    angron.possible_abilities = [SimpleNamespace(name="Wrathful Presence")]
    angron.models[0].model_base.x = 0.0
    angron.models[0].model_base.y = 0.0
    set_active_wrathful_presence(angron, KEY_OVERWHELMING_WRATH, battle_round=2)

    target = _make_stub_unit("Target", army_b, keywords=())
    target.models[0].model_base.x = 0.0
    target.models[0].model_base.y = 3.0

    army_a.units.append(angron)
    army_b.units.append(target)
    game_map = _DummyMap([angron, target])
    game.map = game_map

    monkeypatch.setattr(Unit, "pass_leadership_check", lambda self: False)

    ok = target.fall_back((0.0, 0.0, 0.0), [], game_map)
    assert not ok
    assert target.round_state.remained_stationary_this_round is True


def test_driven_by_ultimate_rage_ignores_negative_hit_modifiers(monkeypatch):
    from warhammer40k_ai.units.wargear import WargearProfile
    from warhammer40k_ai.rules.wrathful_presence import KEY_DRIVEN_BY_ULTIMATE_RAGE, set_active_wrathful_presence

    player_a = SimpleNamespace(name="Player A", id="Player A")
    player_b = SimpleNamespace(name="Player B", id="Player B")
    game = SimpleNamespace(turn=2)
    player_a.game = game
    player_b.game = game
    army_a = SimpleNamespace(player=player_a, units=[])
    army_b = SimpleNamespace(player=player_b, units=[])

    angron = _make_stub_unit("Angron", army_a, keywords=("WORLD EATERS",))
    angron.possible_abilities = [SimpleNamespace(name="Wrathful Presence")]
    angron.models[0].model_base.x = 0.0
    angron.models[0].model_base.y = 0.0
    set_active_wrathful_presence(angron, KEY_DRIVEN_BY_ULTIMATE_RAGE, battle_round=2)

    attacker_unit = _make_stub_unit("Eightbound", army_a, keywords=("WORLD EATERS",))
    attacker_unit.models[0].model_base.x = 0.0
    attacker_unit.models[0].model_base.y = 4.0

    target = _make_stub_unit("Target", army_b, keywords=())
    target.has_stealth = lambda: True

    army_a.units.extend([angron, attacker_unit])
    army_b.units.append(target)
    game_map = _DummyMap([angron, attacker_unit, target])
    game.map = game_map

    wp = WargearProfile.__new__(WargearProfile)
    wp.skill = 3
    wp.parent_wargear = SimpleNamespace(is_ranged=lambda: False, is_melee=lambda: True)
    wp.is_torrent = lambda: False
    wp.is_heavy = lambda: False
    wp.is_pistol = lambda: False
    wp.is_lethal_hits = lambda: False
    wp.is_sustained_hits = lambda: False

    monkeypatch.setattr("warhammer40k_ai.units.wargear.get_roll", lambda _: 4)

    hit = wp._hit_target_with_tracking(
        target,
        attacker_unit.models[0],
        {"hit_modifier_choice": "ignore_negative"},
    )
    assert hit["final_needed"] == 3
    assert all("Stealth" not in m for m in hit.get("modifiers", []))
