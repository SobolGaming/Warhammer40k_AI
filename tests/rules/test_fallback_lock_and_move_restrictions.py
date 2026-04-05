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

    def get_distance_between_units(self, unit_a, unit_b):
        a = unit_a.models[0].model_base
        b = unit_b.models[0].model_base
        return float(a.get_base_shape().distance(b.get_base_shape()))

    def is_within_engagement_range(self, unit_a, unit_b):
        return bool(self.get_distance_between_units(unit_a, unit_b) <= 1.0 + 1e-6)


def _make_stub_unit(name: str, army, *, keywords=(), enhancement=None):
    from warhammer40k_ai.units.unit import Unit

    unit = Unit.__new__(Unit)
    unit.name = name
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.keywords = list(keywords)
    unit.faction_keywords = []
    unit.has_keyword = lambda k: str(k).lower() in {kw.lower() for kw in keywords}
    unit.has_any_keyword = lambda k: str(k).lower() in {kw.lower() for kw in keywords}
    unit.get_parent_army = lambda: army
    unit.is_alive = lambda: True
    unit.get_attached_unit_root = lambda: unit
    unit.get_attached_unit_members = lambda: [unit]
    unit.get_attached_unit_models = lambda: unit.models
    unit.round_state = SimpleNamespace(remained_stationary_this_round=False)
    unit.models = [SimpleNamespace(is_alive=True, model_base=_DummyBase(), parent_unit=unit, abilities={})]
    unit.possible_abilities = []
    unit.special_rules = {}
    unit._ability_cache = {}
    unit.enhancement = enhancement
    return unit


def test_no_escape_aura_blocks_fall_back_on_failed_leadership(monkeypatch):
    from warhammer40k_ai.units.unit import Unit

    player_a = SimpleNamespace(name="Player A", id="Player A")
    player_b = SimpleNamespace(name="Player B", id="Player B")
    game = SimpleNamespace(turn=1)
    player_a.game = game
    player_b.game = game
    army_a = SimpleNamespace(player=player_a, units=[])
    army_b = SimpleNamespace(player=player_b, units=[])

    bearer = _make_stub_unit(
        "Inquisitor",
        army_a,
        keywords=("CHARACTER",),
        enhancement=SimpleNamespace(id="000009130004", name="No Escape (Aura)"),
    )
    bearer.models[0].model_base.x = 0.0
    bearer.models[0].model_base.y = 0.0

    target = _make_stub_unit("Target Unit", army_b, keywords=())
    target.models[0].model_base.x = 0.0
    target.models[0].model_base.y = 3.0

    army_a.units.append(bearer)
    army_b.units.append(target)
    game_map = _DummyMap([bearer, target])
    game.map = game_map

    monkeypatch.setattr(Unit, "pass_leadership_check", lambda self: False)

    ok = target.fall_back((0.0, 0.0, 0.0), [], game_map)
    assert not ok
    assert target.round_state.remained_stationary_this_round is True


def test_soulless_reaper_blocks_fall_back_on_three_plus(monkeypatch):
    from warhammer40k_ai.units import unit as unit_module

    player_a = SimpleNamespace(name="Player A", id="Player A")
    player_b = SimpleNamespace(name="Player B", id="Player B")
    game = SimpleNamespace(turn=1)
    player_a.game = game
    player_b.game = game
    army_a = SimpleNamespace(player=player_a, units=[])
    army_b = SimpleNamespace(player=player_b, units=[])

    bearer = _make_stub_unit(
        "Destroyer Lord",
        army_a,
        keywords=("CHARACTER",),
        enhancement=SimpleNamespace(id="000008543004", name="Soulless Reaper"),
    )
    bearer.models[0].model_base.x = 0.0
    bearer.models[0].model_base.y = 0.0

    target = _make_stub_unit("Target Unit", army_b, keywords=())
    target.models[0].model_base.x = 0.0
    target.models[0].model_base.y = 0.5

    army_a.units.append(bearer)
    army_b.units.append(target)
    game_map = _DummyMap([bearer, target])
    game.map = game_map

    monkeypatch.setattr(unit_module, "get_roll", lambda *_args, **_kwargs: 4)

    ok = target.fall_back((0.0, 0.0, 0.0), [], game_map)
    assert not ok
    assert target.round_state.remained_stationary_this_round is True


def test_grasping_tendrils_blocks_fall_back_on_three_plus(monkeypatch):
    from warhammer40k_ai.units import unit as unit_module

    player_a = SimpleNamespace(name="Player A", id="Player A")
    player_b = SimpleNamespace(name="Player B", id="Player B")
    game = SimpleNamespace(turn=1)
    player_a.game = game
    player_b.game = game
    army_a = SimpleNamespace(player=player_a, units=[])
    army_b = SimpleNamespace(player=player_b, units=[])

    bearer = _make_stub_unit("Toxicrene", army_a, keywords=("MONSTER",))
    bearer.possible_abilities = [
        SimpleNamespace(
            name="Grasping Tendrils",
            description=(
                "Each time an enemy unit (excluding TITANIC units) within Engagement Range of one or more units "
                "from your army with this ability is selected to Fall Back, you can roll one D6: on a 3+, "
                "that enemy unit must Remain Stationary instead."
            ),
        )
    ]
    bearer.models[0].model_base.x = 0.0
    bearer.models[0].model_base.y = 0.0

    target = _make_stub_unit("Target Unit", army_b, keywords=())
    target.models[0].model_base.x = 0.0
    target.models[0].model_base.y = 0.5

    army_a.units.append(bearer)
    army_b.units.append(target)
    game_map = _DummyMap([bearer, target])
    game.map = game_map

    monkeypatch.setattr(unit_module, "get_roll", lambda *_args, **_kwargs: 3)

    ok = target.fall_back((0.0, 0.0, 0.0), [], game_map)
    assert not ok
    assert target.round_state.remained_stationary_this_round is True


def test_harpoon_barbs_deals_d6_mortals_when_enemy_selected_to_fall_back(monkeypatch):
    from warhammer40k_ai.units import unit as unit_module
    from warhammer40k_ai.units.unit import Unit

    player_a = SimpleNamespace(name="Player A", id="Player A")
    player_b = SimpleNamespace(name="Player B", id="Player B")
    game = SimpleNamespace(turn=1, get_current_player=lambda: player_b)
    player_a.game = game
    player_b.game = game
    army_a = SimpleNamespace(player=player_a, units=[])
    army_b = SimpleNamespace(player=player_b, units=[])

    bearer = _make_stub_unit("Norn Assimilator", army_a, keywords=("MONSTER",))
    bearer.possible_abilities = [
        SimpleNamespace(
            name="Harpoon Barbs",
            description=(
                "Once per turn, when an enemy unit within Engagement Range of this model is selected to Fall Back, "
                "roll one D6: on a 2+, that unit suffers D6 mortal wounds."
            ),
        ),
        SimpleNamespace(
            name="Grasping Tendrils",
            description=(
                "Each time an enemy unit (excluding TITANIC units) within Engagement Range of one or more units "
                "from your army with this ability is selected to Fall Back, you can roll one D6: on a 3+, "
                "that enemy unit must Remain Stationary instead."
            ),
        ),
    ]
    bearer.models[0].model_base.x = 0.0
    bearer.models[0].model_base.y = 0.0

    target = _make_stub_unit("Target Unit", army_b, keywords=())
    target.models[0].model_base.x = 0.0
    target.models[0].model_base.y = 0.5

    army_a.units.append(bearer)
    army_b.units.append(target)
    game_map = _DummyMap([bearer, target])
    game.map = game_map

    mortal_amounts = []

    def _fake_apply_mortal(self, target_unit, mortal_wound_amount, game_map=None):
        mortal_amounts.append(int(mortal_wound_amount or 0))
        return 0

    rolls = iter([2, 5, 3])
    monkeypatch.setattr(unit_module, "get_roll", lambda *_args, **_kwargs: next(rolls))
    monkeypatch.setattr(Unit, "_apply_mortal_wounds_to_unit", _fake_apply_mortal)

    ok = target.fall_back((0.0, 0.0, 0.0), [], game_map)
    assert not ok
    assert mortal_amounts == [5]


def test_harpoon_barbs_is_limited_to_once_per_turn(monkeypatch):
    from warhammer40k_ai.units import unit as unit_module
    from warhammer40k_ai.units.unit import Unit

    player_a = SimpleNamespace(name="Player A", id="Player A")
    player_b = SimpleNamespace(name="Player B", id="Player B")
    game = SimpleNamespace(turn=2, get_current_player=lambda: player_b)
    player_a.game = game
    player_b.game = game
    army_a = SimpleNamespace(player=player_a, units=[])
    army_b = SimpleNamespace(player=player_b, units=[])

    bearer = _make_stub_unit("Norn Assimilator", army_a, keywords=("MONSTER",))
    bearer.possible_abilities = [
        SimpleNamespace(
            name="Harpoon Barbs",
            description=(
                "Once per turn, when an enemy unit within Engagement Range of this model is selected to Fall Back, "
                "roll one D6: on a 2+, that unit suffers D6 mortal wounds."
            ),
        ),
        SimpleNamespace(
            name="Grasping Tendrils",
            description=(
                "Each time an enemy unit (excluding TITANIC units) within Engagement Range of one or more units "
                "from your army with this ability is selected to Fall Back, you can roll one D6: on a 3+, "
                "that enemy unit must Remain Stationary instead."
            ),
        ),
    ]
    bearer.models[0].model_base.x = 0.0
    bearer.models[0].model_base.y = 0.0

    target_one = _make_stub_unit("Target One", army_b, keywords=())
    target_one.models[0].model_base.x = 0.0
    target_one.models[0].model_base.y = 0.4

    target_two = _make_stub_unit("Target Two", army_b, keywords=())
    target_two.models[0].model_base.x = 0.4
    target_two.models[0].model_base.y = 0.0

    army_a.units.append(bearer)
    army_b.units.extend([target_one, target_two])
    game_map = _DummyMap([bearer, target_one, target_two])
    game.map = game_map

    mortal_amounts = []

    def _fake_apply_mortal(self, target_unit, mortal_wound_amount, game_map=None):
        mortal_amounts.append(int(mortal_wound_amount or 0))
        return 0

    rolls = iter([2, 4, 3, 3])
    monkeypatch.setattr(unit_module, "get_roll", lambda *_args, **_kwargs: next(rolls))
    monkeypatch.setattr(Unit, "_apply_mortal_wounds_to_unit", _fake_apply_mortal)

    ok_one = target_one.fall_back((0.0, 0.0, 0.0), [], game_map)
    ok_two = target_two.fall_back((0.0, 0.0, 0.0), [], game_map)
    assert not ok_one
    assert not ok_two
    assert mortal_amounts == [4]
