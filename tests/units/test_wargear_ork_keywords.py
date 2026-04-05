from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import AttackResult, Wargear, WargearProfile
from warhammer40k_ai.utility.model_base import Base, BaseType


class DummyUnit:
    def __init__(self, name: str, *, keywords=None):
        self.name = name
        self.special_rules = {}
        self.round_state = SimpleNamespace(
            remained_stationary_this_round=False,
            charged_this_round=False,
        )
        self.models = []
        self.keywords = list(keywords or [])
        self.faction_keywords = []
        self._army = SimpleNamespace(player=SimpleNamespace(game=None, name="P1", id="P1"))

    def get_parent_army(self):
        return self._army

    def get_attached_unit_root(self):
        return self

    def get_attached_unit_models(self):
        return list(self.models)

    def get_models_for_wound_allocation(self):
        return list(self.models)

    def is_alive(self):
        return True

    def has_keyword(self, keyword: str) -> bool:
        kw = (keyword or "").strip().lower()
        return any(kw == k.lower() for k in (self.keywords or []))

    def has_any_keyword(self, keyword: str) -> bool:
        return self.has_keyword(keyword)


def _make_model(name: str, unit: DummyUnit) -> Model:
    model = Model(
        name=name,
        movement=6,
        toughness=4,
        save=3,
        wounds=3,
        leadership=7,
        objective_control=1,
        model_base=Base(BaseType.CIRCULAR, 1.0),
    )
    model.parent_unit = unit
    return model


def _make_attack_result(profile, attacker, target):
    return AttackResult(
        weapon_name="Test Weapon",
        attacker_name=attacker.name,
        target_unit_name=target.name,
        attacks_rolled=0,
        attacks_dice_expression=str(profile.attacks),
        attacks_dice_rolls=[],
        attacks_special_modifiers=[],
        hit_results=[],
        wound_results=[],
        save_results=[],
        damage_results=[],
        hazardous_roll=None,
        hazardous_damage=0,
        total_hits=0,
        total_wounds=0,
        total_saves_failed=0,
        total_damage_dealt=0,
        models_killed=0,
    )


def test_dead_choppy_adds_attacks_for_extra_dread_klaws():
    wargear = Wargear(
        {
            "name": "Dead Choppy Klaw",
            "type": "Melee",
            "range": "Melee",
            "A": "3",
            "BS_WS": "3+",
            "S": "8",
            "AP": "-2",
            "D": "2",
            "description": "dead choppy",
        }
    )
    profile = list(wargear.profiles.values())[0]

    attacker_unit = DummyUnit("Attacker")
    attacker = _make_model("Attacker", attacker_unit)
    attacker.wargear = [
        SimpleNamespace(name="Dread Klaw"),
        SimpleNamespace(name="Dread Klaw"),
    ]
    attacker_unit.models = [attacker]

    target = DummyUnit("Target")
    target.models = [SimpleNamespace(is_alive=True)]

    attack_result = _make_attack_result(profile, attacker, target)
    info = profile._resolve_attack_count(
        target,
        attacker,
        attack_result,
        publish_roll_event=False,
    )

    assert info.num_attacks == 4
    assert any("Dead Choppy" in s for s in attack_result.attacks_special_modifiers)


def test_ork_charge_keywords_track_hits_vs_monster_vehicle():
    attacker_unit = DummyUnit("Attacker")
    attacker = _make_model("Attacker", attacker_unit)
    attacker_unit.models = [attacker]

    target_unit = DummyUnit("Target", keywords=["Monster"])
    target_model = _make_model("Target", target_unit)
    target_unit.models = [target_model]

    keywords = [
        ("harpooned", "harpooned_target", "Harpooned"),
        ("hooked", "hooked_target", "Hooked"),
        ("impaled", "impaled_target", "Impaled"),
        ("snagged", "snagged_target", "Snagged"),
    ]

    for keyword, flag, effect in keywords:
        profile = WargearProfile(
            profile_name="Ranged",
            wargear_data={
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "8",
                "AP": "-2",
                "D": "2",
                "description": keyword,
            },
            parent_wargear=SimpleNamespace(
                name="Test Gun",
                is_ranged=lambda: True,
                is_melee=lambda: False,
            ),
        )

        attack_instance = {}
        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=6):
            hit_result = profile._hit_target_with_tracking(target_unit, attacker, attack_instance)

        assert attack_instance.get(flag) is True
        assert any(effect in s for s in hit_result.get("special_effects", []))


def test_bubblechukka_profile_selection():
    wargear = Wargear(
        {
            "name": "Bubblechukka - big bubble",
            "type": "Ranged",
            "range": "48",
            "A": "D6",
            "BS_WS": "4+",
            "S": "8",
            "AP": "-2",
            "D": "2",
            "description": "bubblechukka, blast",
        }
    )
    wargear.add_profile(
        "wobbly bubble",
        {
            "name": "Bubblechukka - wobbly bubble",
            "type": "Ranged",
            "range": "48",
            "A": "D6",
            "BS_WS": "4+",
            "S": "9",
            "AP": "-3",
            "D": "2",
            "description": "bubblechukka, blast",
        },
    )
    wargear.add_profile(
        "dense bubble",
        {
            "name": "Bubblechukka - dense bubble",
            "type": "Ranged",
            "range": "48",
            "A": "D6",
            "BS_WS": "4+",
            "S": "10",
            "AP": "-4",
            "D": "2",
            "description": "bubblechukka, blast",
        },
    )

    profile = wargear.profiles["big bubble"]
    assert profile.get_bubblechukka_profile_for_roll(1).name == "big bubble"
    assert profile.get_bubblechukka_profile_for_roll(3).name == "wobbly bubble"
    assert profile.get_bubblechukka_profile_for_roll(6).name == "dense bubble"

    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=5):
        selected = wargear.select_bubblechukka_profile()
    assert selected is not None
    assert selected.name == "dense bubble"


def test_bubblechukka_execute_weapon_attacks_uses_selected_profile():
    wargear = Wargear(
        {
            "name": "Bubblechukka - big bubble",
            "type": "Ranged",
            "range": "48",
            "A": "D6",
            "BS_WS": "4+",
            "S": "8",
            "AP": "-2",
            "D": "2",
            "description": "bubblechukka, blast",
        }
    )
    wargear.add_profile(
        "wobbly bubble",
        {
            "name": "Bubblechukka - wobbly bubble",
            "type": "Ranged",
            "range": "48",
            "A": "D6",
            "BS_WS": "4+",
            "S": "9",
            "AP": "-3",
            "D": "2",
            "description": "bubblechukka, blast",
        },
    )
    wargear.add_profile(
        "dense bubble",
        {
            "name": "Bubblechukka - dense bubble",
            "type": "Ranged",
            "range": "48",
            "A": "D6",
            "BS_WS": "4+",
            "S": "10",
            "AP": "-4",
            "D": "2",
            "description": "bubblechukka, blast",
        },
    )

    big_profile = wargear.profiles["big bubble"]
    dense_profile = wargear.profiles["dense bubble"]

    unit = Unit.__new__(Unit)
    unit.name = "Shooters"
    unit._can_model_shoot_weapon_at_target = lambda *_a, **_k: True
    unit.get_parent_army = lambda: SimpleNamespace(player=SimpleNamespace(name="Player 1", id="Player 1"))

    model = SimpleNamespace(is_alive=True, wargear=[wargear], name="Shooter")
    unit.models = [model]

    target = SimpleNamespace(name="Target", is_alive=True, models=[])
    dummy_map = SimpleNamespace()

    called = {"big": 0, "dense": 0}

    def _attack_for(key):
        def _attack(*_args, **_kwargs):
            called[key] += 1
            return SimpleNamespace(total_hits=1)
        return _attack

    big_profile.attack = _attack_for("big")
    dense_profile.attack = _attack_for("dense")

    with patch("warhammer40k_ai.units.unit.get_roll", return_value=5):
        unit._execute_weapon_attacks(big_profile, target, [model], dummy_map)

    assert called["dense"] == 1
    assert called["big"] == 0


def test_wargear_charge_bonus_applies_to_max_distance():
    class _DummyMap:
        def get_friendly_units(self, _unit):
            return []

    player = SimpleNamespace(name="Player 1", id="Player 1")
    army = SimpleNamespace(player=player)

    game = Game.__new__(Game)
    game.map = _DummyMap()
    game.turn = 1
    game.get_current_player = lambda: player

    charging_unit = Unit.__new__(Unit)
    charging_unit.name = "Charger"
    charging_unit.special_rules = {}
    charging_unit.keywords = []
    charging_unit.faction_keywords = []
    charging_unit.get_parent_army = lambda: army
    charging_unit.get_charge_roll_target_strength_modifiers = lambda target_units=None: []
    charging_unit._filter_internal_rivalries_roll_modifiers = lambda mods, kind: list(mods or [])
    charging_unit._filter_driven_by_ultimate_rage_roll_modifiers = lambda mods, kind: list(mods or [])

    target_unit = Unit.__new__(Unit)
    target_unit.name = "Target"
    target_unit.special_rules = {}
    target_unit._id = "target-1"

    charging_unit.register_wargear_charge_keyword_hit(
        target_unit,
        "snagged",
        no_overwatch=True,
        game=game,
    )

    mods = charging_unit.get_wargear_charge_keyword_modifiers(target_unit, game=game)
    assert mods == [(2, "Snagged (wargear)")]
    assert game.get_max_charge_distance(charging_unit, target_unit=target_unit) == 14.0


def test_overwatch_filtered_for_wargear_no_overwatch():
    from warhammer40k_ai.rules.stratagems import Stratagem, StratagemManager

    class _DummyPlayer:
        def __init__(self, name):
            self.name = name
            self.id = name
            self.command_points = 2
            self._army = None

        def get_army(self):
            return self._army

    class _DummyArmy:
        def __init__(self, player, units):
            self.player = player
            self.units = list(units or [])

    class _DummyGame:
        def __init__(self, current_player):
            self._current_player = current_player
            self.map = _DummyMap()

        def get_current_player(self):
            return self._current_player

    class _DummyMap:
        def get_distance_between_units(self, _a, _b):
            return 12.0

    class _DummyUnit:
        def __init__(self, name, army):
            self.name = name
            self._army = army
            self.deployed = True
            self.is_titanic = False
            self.special_rules = {}
            self.embarked_in = None

        def get_parent_army(self):
            return self._army

        def is_alive(self):
            return True

        def is_embarked(self):
            return False

        def is_battle_shocked(self):
            return False

        def is_overwatch_prevented_against(self, _target_unit, game=None):
            return False

    owner = _DummyPlayer("Owner")
    opponent = _DummyPlayer("Opponent")
    game = _DummyGame(owner)

    moving_army = _DummyArmy(owner, [])
    opponent_army = _DummyArmy(opponent, [])
    owner._army = moving_army
    opponent._army = opponent_army

    moving_unit = _DummyUnit("Mover", moving_army)
    shooter = _DummyUnit("Shooter", opponent_army)
    opponent_army.units = [shooter]

    moving_unit.is_overwatch_prevented_against = lambda target, game=None: target is shooter

    manager = StratagemManager.__new__(StratagemManager)
    manager.player = opponent
    manager.game = game
    manager.available = [
        Stratagem(
            id="X",
            name="FIRE OVERWATCH",
            type="Stratagem",
            description="",
            cp_cost=1,
            turn="Opponent's turn",
            phase="Charge phase",
            detachment="",
            faction_id="",
        )
    ]
    manager._pending_reactions = []
    manager._reaction_timeout_s = 5.0
    manager._used_this_turn = {"OVERWATCH": False}
    manager._current_phase_name = "Charge phase"

    manager._maybe_queue_overwatch(moving_unit, action="charge", when="start")
    assert manager._pending_reactions == []
