from types import SimpleNamespace


def test_using_sir_hekhtur_parse_sets_spawn_only_and_core_stratagem_targeting():
    from warhammer40k_ai.units.unit import Unit

    unit = Unit.__new__(Unit)
    unit.name = "Sir Hekhtur"
    unit.special_rules = {}
    unit._datasheet = SimpleNamespace(datasheets_models_cost=[])
    unit.possible_abilities = [SimpleNamespace(name="USING SIR HEKHTUR")]

    unit._parse_spawn_only_restrictions()

    assert unit.special_rules.get("spawn_only") is True
    assert unit.special_rules.get("stratagem_target_core_only") is True


class _CoreOnlyTargetUnit:
    def __init__(self):
        self.special_rules = {"stratagem_target_core_only": True}
        self.embarked_in = None

    @property
    def is_embarked(self):
        return False

    def is_battle_shocked(self):
        return False


class _Player:
    def __init__(self, cp=1):
        self.command_points = int(cp)


class _Game:
    def __init__(self, current_player):
        self._current_player = current_player

    def get_current_player(self):
        return self._current_player


def test_using_sir_hekhtur_blocks_non_core_stratagem_targeting():
    from warhammer40k_ai.rules.stratagems import Stratagem

    player = _Player(cp=2)
    game = _Game(current_player=player)
    target = _CoreOnlyTargetUnit()

    non_core = Stratagem(
        id="x",
        name="TEST NON-CORE",
        type="Battle Tactic Stratagem",
        description="",
        cp_cost=1,
        turn="Either",
        phase="Any phase",
        detachment="",
        faction_id="",
    )
    core = Stratagem(
        id="y",
        name="GO TO GROUND",
        type="Core - Battle Tactic Stratagem",
        description="",
        cp_cost=1,
        turn="Either",
        phase="Any phase",
        detachment="",
        faction_id="",
    )

    assert non_core.can_use(player, game, target_unit=target) is False
    assert core.can_use(player, game, target_unit=target) is True


def test_sir_hekhtur_death_publishes_parent_canis_rex_destroyed_event():
    from warhammer40k_ai.units.unit import Unit

    published = []

    class _EventSystem:
        @staticmethod
        def publish(event_name, **kwargs):
            published.append((event_name, kwargs))

    parent_unit = SimpleNamespace(_id="canis-parent-id", name="Canis Rex", special_rules={})
    game = SimpleNamespace(
        event_system=_EventSystem(),
        _resolve_unit_by_id=lambda uid: parent_unit if str(uid) == "canis-parent-id" else None,
    )
    army = SimpleNamespace(player=SimpleNamespace(game=game), units=[parent_unit])

    sir = Unit.__new__(Unit)
    sir.name = "Sir Hekhtur"
    sir.special_rules = {"using_sir_hekhtur_parent_unit_id": "canis-parent-id"}
    sir.get_parent_army = lambda: army
    sir._last_destroyed_by_model = "attacker-model"
    sir._last_destroyed_by_unit = "attacker-unit"
    sir._last_destroyed_by_weapon_profile = "weapon-profile"

    handled = sir._maybe_publish_using_sir_hekhtur_parent_destroyed(last_model="sir-model", game_map="map")

    assert handled is True
    assert len(published) == 1
    assert published[0][0] == "unit_destroyed"
    assert published[0][1]["unit"] is parent_unit
    assert parent_unit.special_rules.get("using_sir_hekhtur_destroyed_event_published") is True


def test_canis_rex_destroyed_spawns_and_defers_until_sir_hekhtur_dies():
    from warhammer40k_ai.units.unit import Unit

    fake_sir = SimpleNamespace(
        _id="sir-child-id",
        name="Sir Hekhtur",
        special_rules={},
        spawned_in_battle=False,
        embarked_in=None,
        round_state=SimpleNamespace(embarked_this_round=False),
        set_parent_army=lambda _army: None,
        disembark=lambda **_kwargs: True,
        is_alive=lambda: True,
    )

    class _Army:
        def __init__(self):
            self.faction_id = "QI"
            self.units = []
            self.player = SimpleNamespace(game=SimpleNamespace(turn=2))

        def add_unit(self, unit):
            self.units.append(unit)
            unit.set_parent_army(self)
            return True

    army = _Army()

    canis = Unit.__new__(Unit)
    canis._id = "canis-id"
    canis.name = "Canis Rex"
    canis.special_rules = {}
    canis.transport_passengers = []
    canis.round_state = SimpleNamespace()
    canis.set_parent_army(army)
    canis.get_parent_army = lambda: army
    canis._create_sir_hekhtur_unit_for_parent = lambda: fake_sir

    game_map = SimpleNamespace(units=[])
    result = canis._handle_using_sir_hekhtur_on_destroyed(
        last_model=SimpleNamespace(model_base=object()),
        game_map=game_map,
    )

    assert result == "defer"
    assert canis.special_rules.get("using_sir_hekhtur_destroyed_pending") is True
    assert fake_sir.special_rules.get("using_sir_hekhtur_parent_unit_id") == "canis-id"
    assert fake_sir.special_rules.get("stratagem_target_core_only") is True
