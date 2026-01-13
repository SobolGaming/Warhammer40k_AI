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
        # engaged_pairs: iterable of (unit_a, unit_b). Store by object id to avoid Unit hashing requirements.
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
    )
    player.game = game


def _make_stub_unit(name: str, army, *, keywords=()):
    from warhammer40k_ai.classes.unit import Unit

    u = Unit.__new__(Unit)
    u.name = name
    u.deployed = True
    u.has_keyword = lambda k: k.lower() in {kw.lower() for kw in keywords}
    u.get_parent_army = lambda: army
    u.is_alive = lambda: True
    u.has_lone_operative = lambda: False
    u.has_stealth = lambda: False
    u.get_models_for_collision = lambda: u.models
    u.get_attached_unit_models = lambda: u.models
    u.models = [SimpleNamespace(is_alive=True, model_base=_DummyBase(), parent_unit=u)]
    return u


def test_vehicle_engaged_shoots_out_of_combat_allowed_and_hit_penalty(monkeypatch):
    from warhammer40k_ai.classes.wargear import WargearProfile

    # Shooter is a VEHICLE, locked in combat with enemy1, shooting enemy2 (not in ER)
    player_a = SimpleNamespace()
    _make_phase(player_a, shooting_phase=True)
    army_a = SimpleNamespace(player=player_a)

    player_b = SimpleNamespace()
    _make_phase(player_b, shooting_phase=True)
    army_b = SimpleNamespace(player=player_b)

    vehicle = _make_stub_unit("Vehicle", army_a, keywords=("Vehicle",))
    enemy1 = _make_stub_unit("Enemy Engaged", army_b, keywords=())
    enemy2 = _make_stub_unit("Enemy Far", army_b, keywords=())

    game_map = _DummyMap(units=[vehicle, enemy1, enemy2], engaged_pairs=[(vehicle, enemy1)])

    non_blast = _DummyProfile(pistol=False, blast=False, indirect=True)
    assert vehicle._can_model_shoot_weapon_at_target(vehicle.models[0], non_blast, enemy2, game_map)

    # Verify the -1 to hit is applied using the snapshot flag.
    wp = WargearProfile.__new__(WargearProfile)
    wp.skill = 3
    wp.parent_wargear = SimpleNamespace(is_ranged=lambda: True, is_melee=lambda: False)
    wp.is_torrent = lambda: False
    wp.is_heavy = lambda: False
    wp.is_pistol = lambda: False
    wp.is_lethal_hits = lambda: False
    wp.is_sustained_hits = lambda: False

    monkeypatch.setattr("warhammer40k_ai.classes.wargear.get_roll", lambda _: 4)

    setattr(vehicle, "_bgnt_locked_at_target_selection", True)
    hit = wp._hit_target_with_tracking(enemy2, vehicle.models[0], {})
    assert hit["final_needed"] == 4  # 3+ base becomes 4+ from BGNT -1 to hit
    assert any("Big Guns Never Tire" in m for m in hit["modifiers"])


def test_vehicle_engaged_can_shoot_engaged_unit_non_blast_but_blast_blocked():
    player_a = SimpleNamespace()
    _make_phase(player_a, shooting_phase=True)
    army_a = SimpleNamespace(player=player_a)

    player_b = SimpleNamespace()
    _make_phase(player_b, shooting_phase=True)
    army_b = SimpleNamespace(player=player_b)

    vehicle = _make_stub_unit("Vehicle", army_a, keywords=("Vehicle",))
    engaged_enemy = _make_stub_unit("Enemy", army_b, keywords=())

    game_map = _DummyMap(units=[vehicle, engaged_enemy], engaged_pairs=[(vehicle, engaged_enemy)])

    non_blast = _DummyProfile(pistol=False, blast=False, indirect=True)
    blast = _DummyProfile(pistol=False, blast=True, indirect=True)

    assert vehicle._can_model_shoot_weapon_at_target(vehicle.models[0], non_blast, engaged_enemy, game_map)
    assert not vehicle._can_model_shoot_weapon_at_target(vehicle.models[0], blast, engaged_enemy, game_map)


def test_enemy_blast_cannot_target_locked_vehicle_due_to_friendly_engagement():
    # Shooter is Army B. Target is a VEHICLE from Army A locked with a friendly Army B unit.
    player_a = SimpleNamespace()
    _make_phase(player_a, shooting_phase=True)
    army_a = SimpleNamespace(player=player_a)

    player_b = SimpleNamespace()
    _make_phase(player_b, shooting_phase=True)
    army_b = SimpleNamespace(player=player_b)

    shooter = _make_stub_unit("Shooter", army_b, keywords=())
    friend_in_combat = _make_stub_unit("Friend Engaging", army_b, keywords=())
    target_vehicle = _make_stub_unit("Target Vehicle", army_a, keywords=("Vehicle",))

    game_map = _DummyMap(units=[shooter, friend_in_combat, target_vehicle], engaged_pairs=[(friend_in_combat, target_vehicle)])

    blast = _DummyProfile(pistol=False, blast=True, indirect=True)
    assert not shooter._can_model_shoot_weapon_at_target(shooter.models[0], blast, target_vehicle, game_map)


def test_overwatch_cannot_target_locked_vehicle_via_bgnt():
    # Out-of-phase: shooter is NOT in its Shooting phase (e.g., Overwatch window).
    player_a = SimpleNamespace()
    _make_phase(player_a, shooting_phase=True)
    army_a = SimpleNamespace(player=player_a)

    player_b = SimpleNamespace()
    _make_phase(player_b, shooting_phase=False)  # out-of-phase for shooter
    army_b = SimpleNamespace(player=player_b)

    shooter = _make_stub_unit("Overwatch Shooter", army_b, keywords=())
    friend_engaging = _make_stub_unit("Friend Engaging", army_b, keywords=())
    target_vehicle = _make_stub_unit("Target Vehicle", army_a, keywords=("Vehicle",))

    game_map = _DummyMap(units=[shooter, friend_engaging, target_vehicle], engaged_pairs=[(friend_engaging, target_vehicle)])

    non_blast = _DummyProfile(pistol=False, blast=False, indirect=True)
    assert not shooter._can_model_shoot_weapon_at_target(shooter.models[0], non_blast, target_vehicle, game_map)


def test_locked_vehicle_cannot_overwatch_while_engaged_with_non_pistol():
    # Vehicle is the shooter, but it's not its Shooting phase and it is engaged.
    player_a = SimpleNamespace()
    _make_phase(player_a, shooting_phase=False)
    army_a = SimpleNamespace(player=player_a)

    player_b = SimpleNamespace()
    _make_phase(player_b, shooting_phase=True)
    army_b = SimpleNamespace(player=player_b)

    vehicle = _make_stub_unit("Vehicle", army_a, keywords=("Vehicle",))
    engaged_enemy = _make_stub_unit("Enemy Engaged", army_b, keywords=())
    other_enemy = _make_stub_unit("Enemy Other", army_b, keywords=())

    game_map = _DummyMap(units=[vehicle, engaged_enemy, other_enemy], engaged_pairs=[(vehicle, engaged_enemy)])

    non_pistol = _DummyProfile(pistol=False, blast=False, indirect=True)
    assert not vehicle._can_shoot_while_engaged(vehicle.models[0], non_pistol, other_enemy, game_map)

