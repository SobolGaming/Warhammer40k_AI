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
    u.keywords = list(keywords)
    u.faction_keywords = []
    u.has_keyword = lambda k: str(k).lower() in {kw.lower() for kw in keywords}
    u.has_any_keyword = lambda k: str(k).lower() in {kw.lower() for kw in keywords}
    u.get_parent_army = lambda: army
    u.is_alive = lambda: True
    u.get_attached_unit_root = lambda: u
    u.get_attached_unit_members = lambda: [u]
    u.get_attached_unit_models = lambda: u.models
    u.round_state = SimpleNamespace(remained_stationary_this_round=False)
    u.models = [SimpleNamespace(is_alive=True, model_base=_DummyBase(), parent_unit=u, abilities={})]
    u.possible_abilities = []
    u.special_rules = {}
    u._ability_cache = {}
    return u


def test_daemonic_speed_selection_grants_fight_first():
    from warhammer40k_ai.rules.daemon_primarch_slaanesh import (
        KEY_DAEMONIC_SPEED,
        set_active_daemon_primarch_slaanesh,
    )

    player = SimpleNamespace(name="Player A", id="Player A")
    game = SimpleNamespace(turn=1)
    player.game = game
    army = SimpleNamespace(player=player, units=[])

    fulgrim = _make_stub_unit("Fulgrim", army, keywords=("FULGRIM",))
    fulgrim.possible_abilities = [
        SimpleNamespace(name="Daemon Primarch of Slaanesh"),
        SimpleNamespace(name="Daemonic Speed", description="This model has the Fights First ability."),
    ]
    army.units.append(fulgrim)

    assert fulgrim.has_fight_first() is False
    set_active_daemon_primarch_slaanesh(
        fulgrim,
        KEY_DAEMONIC_SPEED,
        start_round=1,
        expires_round=2,
        opponent_player_id="Player B",
    )
    assert fulgrim.has_fight_first() is True


def test_beguiling_form_hit_penalty_only_when_selected():
    from warhammer40k_ai.rules.daemon_primarch_slaanesh import (
        KEY_BEGUILING_FORM,
        set_active_daemon_primarch_slaanesh,
    )

    player = SimpleNamespace(name="Player A", id="Player A")
    game = SimpleNamespace(turn=1)
    player.game = game
    army = SimpleNamespace(player=player, units=[])

    fulgrim = _make_stub_unit("Fulgrim", army, keywords=("FULGRIM",))
    fulgrim.possible_abilities = [
        SimpleNamespace(name="Daemon Primarch of Slaanesh"),
        SimpleNamespace(
            name="Beguiling Form",
            description="Each time a model makes an attack that targets this model, subtract 1 from the Hit roll.",
        ),
    ]
    army.units.append(fulgrim)

    penalty, _ = fulgrim.get_target_hit_roll_penalty("ranged")
    assert penalty == 0

    set_active_daemon_primarch_slaanesh(
        fulgrim,
        KEY_BEGUILING_FORM,
        start_round=1,
        expires_round=2,
        opponent_player_id="Player B",
    )

    penalty, _ = fulgrim.get_target_hit_roll_penalty("ranged")
    assert penalty == 1


def test_enthralling_hypnosis_blocks_fall_back_on_failed_leadership(monkeypatch):
    from warhammer40k_ai.units.unit import Unit
    from warhammer40k_ai.rules.daemon_primarch_slaanesh import (
        KEY_ENTHRALLING_HYPNOSIS,
        set_active_daemon_primarch_slaanesh,
    )

    player_a = SimpleNamespace(name="Player A", id="Player A")
    player_b = SimpleNamespace(name="Player B", id="Player B")
    game = SimpleNamespace(turn=1)
    player_a.game = game
    player_b.game = game
    army_a = SimpleNamespace(player=player_a, units=[])
    army_b = SimpleNamespace(player=player_b, units=[])

    fulgrim = _make_stub_unit("Fulgrim", army_a, keywords=("FULGRIM",))
    fulgrim.models[0].model_base.x = 0.0
    fulgrim.models[0].model_base.y = 0.0
    fulgrim.possible_abilities = [SimpleNamespace(name="Daemon Primarch of Slaanesh")]
    set_active_daemon_primarch_slaanesh(
        fulgrim,
        KEY_ENTHRALLING_HYPNOSIS,
        start_round=1,
        expires_round=2,
        opponent_player_id="Player B",
    )

    target = _make_stub_unit("Target", army_b, keywords=())
    target.models[0].model_base.x = 0.0
    target.models[0].model_base.y = 3.0

    army_a.units.append(fulgrim)
    army_b.units.append(target)
    game_map = _DummyMap([fulgrim, target])
    game.map = game_map

    monkeypatch.setattr(Unit, "pass_leadership_check", lambda self: False)

    ok = target.fall_back((0.0, 0.0, 0.0), [], game_map)
    assert not ok
    assert target.round_state.remained_stationary_this_round is True
