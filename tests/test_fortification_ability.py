import pytest
from types import SimpleNamespace


class _DummyBase:
    def __init__(self):
        self.x = 0.0
        self.y = 0.0
        self.z = 0.0

    def get_base_shape(self):
        from shapely.geometry import Point
        return Point(self.x, self.y)


class _DummyProfile:
    def __init__(self, *, pistol: bool = False, blast: bool = False, indirect: bool = True):
        self._pistol = pistol
        self._blast = blast
        self._indirect = indirect
        self.name = "Dummy Weapon"
        self.range = SimpleNamespace(max=999.0)

    def is_pistol(self) -> bool:
        return self._pistol

    def is_blast(self) -> bool:
        return self._blast

    def is_indirect_fire(self) -> bool:
        return self._indirect


class _DummyMap:
    def __init__(self, units, engaged_pairs):
        self.units = list(units)
        self._engaged = set(frozenset({id(a), id(b)}) for (a, b) in engaged_pairs)

    def get_enemy_units(self, unit):
        return [u for u in self.units if u.get_parent_army() != unit.get_parent_army()]

    def get_friendly_units(self, unit):
        return [u for u in self.units if u.get_parent_army() == unit.get_parent_army()]

    def is_within_engagement_range(self, a, b) -> bool:
        return frozenset({id(a), id(b)}) in self._engaged


def _make_phase(player, *, shooting_phase: bool):
    game = SimpleNamespace(
        is_shooting_phase=lambda: shooting_phase,
        get_current_player=lambda: player,
        map=None,
    )
    player.game = game
    return game


def _make_stub_unit(name: str, army, *, keywords=()):
    from warhammer40k_ai.units.unit import Unit

    u = Unit.__new__(Unit)
    u._id = f"unit:{name}"
    u.name = name
    u.deployed = True
    u.has_keyword = lambda k: k.lower() in {kw.lower() for kw in keywords}
    u.get_parent_army = lambda: army
    u.is_alive = lambda: True
    u.has_lone_operative = lambda: False
    u.has_stealth = lambda: False
    u.get_models_for_collision = lambda: u.models
    u.get_attached_unit_models = lambda: u.models
    u.get_attached_unit_root = lambda: u
    u.is_in_reserves = lambda: False
    u.embarked_in = None
    u.special_rules = {}
    u.models = [SimpleNamespace(is_alive=True, model_base=_DummyBase(), parent_unit=u, name="Model")]
    return u


def test_fortification_allows_target_when_only_engaged():
    player_a = SimpleNamespace(name="Player A", id="Player A")
    player_b = SimpleNamespace(name="Player B", id="Player B")
    _make_phase(player_a, shooting_phase=True)
    _make_phase(player_b, shooting_phase=True)

    army_a = SimpleNamespace(player=player_a)
    army_b = SimpleNamespace(player=player_b)

    shooter = _make_stub_unit("Shooter", army_a)
    fort = _make_stub_unit("Fortification", army_a, keywords=("Fortification",))
    target = _make_stub_unit("Target", army_b)

    game_map = _DummyMap(units=[shooter, fort, target], engaged_pairs=[(fort, target)])

    profile = _DummyProfile(pistol=False, blast=False, indirect=True)
    assert shooter._can_model_shoot_weapon_at_target(shooter.models[0], profile, target, game_map)


def test_fortification_blocked_when_engaged_with_non_fortification():
    player_a = SimpleNamespace(name="Player A", id="Player A")
    player_b = SimpleNamespace(name="Player B", id="Player B")
    _make_phase(player_a, shooting_phase=True)
    _make_phase(player_b, shooting_phase=True)

    army_a = SimpleNamespace(player=player_a)
    army_b = SimpleNamespace(player=player_b)

    shooter = _make_stub_unit("Shooter", army_a)
    fort = _make_stub_unit("Fortification", army_a, keywords=("Fortification",))
    friend = _make_stub_unit("Friend", army_a)
    target = _make_stub_unit("Target", army_b)

    game_map = _DummyMap(units=[shooter, fort, friend, target], engaged_pairs=[(fort, target), (friend, target)])

    profile = _DummyProfile(pistol=False, blast=False, indirect=True)
    assert not shooter._can_model_shoot_weapon_at_target(shooter.models[0], profile, target, game_map)


def test_fortification_hit_penalty_non_pistol_only(monkeypatch):
    from warhammer40k_ai.units.wargear import WargearProfile

    player_a = SimpleNamespace(name="Player A", id="Player A")
    player_b = SimpleNamespace(name="Player B", id="Player B")
    game_a = _make_phase(player_a, shooting_phase=True)
    _make_phase(player_b, shooting_phase=True)

    army_a = SimpleNamespace(player=player_a)
    army_b = SimpleNamespace(player=player_b)

    shooter = _make_stub_unit("Shooter", army_a)
    fort = _make_stub_unit("Fortification", army_a, keywords=("Fortification",))
    target = _make_stub_unit("Target", army_b)

    game_map = _DummyMap(units=[shooter, fort, target], engaged_pairs=[(fort, target)])
    game_a.map = game_map

    wp = WargearProfile.__new__(WargearProfile)
    wp.skill = 3
    wp.parent_wargear = SimpleNamespace(is_ranged=lambda: True, is_melee=lambda: False)
    wp.is_torrent = lambda: False
    wp.is_heavy = lambda: False
    wp.is_pistol = lambda: False
    wp.is_blast = lambda: False
    wp.is_indirect_fire = lambda: True
    wp.is_lethal_hits = lambda: False
    wp.is_sustained_hits = lambda: False
    wp.is_extra_attacks = lambda: False

    monkeypatch.setattr("warhammer40k_ai.units.wargear.get_roll", lambda _: 4)

    hit = wp._hit_target_with_tracking(target, shooter.models[0], {})
    assert hit["final_needed"] == 4
    assert any("Fortification" in m for m in hit["modifiers"])

    wp.is_pistol = lambda: True
    hit = wp._hit_target_with_tracking(target, shooter.models[0], {})
    assert hit["final_needed"] == 3
    assert not any("Fortification" in m for m in hit["modifiers"])
