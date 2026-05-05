from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.battlefield.map import Map
from warhammer40k_ai.rules.chaos_space_marines_detachments import ChaosSpaceMarinesDetachmentManager
from warhammer40k_ai.rules.stratagems_chaos_space_marines import ChaosSpaceMarinesStratagemMixin
from warhammer40k_ai.units.ability import Ability


class _MirrorArmy:
    faction_id = "CSM"
    detachment_type = "Deceptors"

    def __init__(self, army_id: str):
        self._id = army_id
        self.units = []
        self.player = None
        self.chaos_space_marines_detachments = ChaosSpaceMarinesDetachmentManager(self)

    @property
    def id(self) -> str:
        return self._id

    def __eq__(self, other):
        return (
            getattr(other, "faction_id", None) == self.faction_id
            and getattr(other, "detachment_type", None) == self.detachment_type
        )

    def get_primary_detachment_type(self, _faction_id: str = "") -> str:
        return self.detachment_type

    def get_detachment_instances_for_faction(self, _faction_id: str = "") -> list:
        return [SimpleNamespace(detachment_type=self.detachment_type)]


class _MirrorUnit:
    def __init__(self, name: str, army: _MirrorArmy, *, abilities=None, keywords=()):
        self._id = name
        self.name = name
        self._army = army
        self.possible_abilities = list(abilities or [])
        self.keywords = list(keywords)
        self.faction_keywords = list(keywords)
        self.models = []
        self.deployed = True
        self.reserve_status = "deployed"
        self.special_rules = {}
        self.round_state = SimpleNamespace(remained_stationary_this_round=False)
        army.units.append(self)

    def get_parent_army(self):
        return self._army

    def get_attached_unit_root(self):
        return self

    def get_attached_unit_models(self):
        return list(self.models)

    def get_models_for_collision(self):
        return list(self.models)

    def is_alive(self) -> bool:
        return True

    def has_any_keyword(self, keyword: str) -> bool:
        key = str(keyword or "").strip().lower()
        return key in {str(k or "").strip().lower() for k in self.keywords + self.faction_keywords}

    def has_keyword(self, keyword: str) -> bool:
        return self.has_any_keyword(keyword)

    def get_effective_keywords(self):
        return list(self.keywords)

    def get_effective_faction_keywords(self):
        return list(self.faction_keywords)


class _Base:
    has_circular_base = True

    def __init__(self, x: float, y: float):
        self.x = float(x)
        self.y = float(y)
        self.z = 0.0

    def get_radius(self) -> float:
        return 0.5


def _attach_model(unit: _MirrorUnit, x: float, y: float):
    model = SimpleNamespace(is_alive=True, model_base=_Base(x, y), parent_unit=unit)
    unit.models.append(model)
    return model


def _mirror_game():
    game_map = Map(60, 44)
    game = SimpleNamespace(turn=1, map=game_map, event_system=SimpleNamespace(publish=lambda *_a, **_k: None))
    player_a = SimpleNamespace(id="player-a", name="Player A", game=game)
    player_b = SimpleNamespace(id="player-b", name="Player B", game=game)
    army_a = _MirrorArmy("army-a")
    army_b = _MirrorArmy("army-b")
    player_a.army = army_a
    player_b.army = army_b
    army_a.player = player_a
    army_b.player = player_b
    return game, game_map, player_a, player_b, army_a, army_b


def test_map_uses_army_ids_for_same_csm_detachment_mirror_match():
    _game, game_map, _player_a, _player_b, army_a, army_b = _mirror_game()
    own = _MirrorUnit("own-legionaries", army_a, keywords=("HERETIC ASTARTES",))
    own_friend = _MirrorUnit("own-cultists", army_a, keywords=("HERETIC ASTARTES",))
    mirror_enemy = _MirrorUnit("mirror-legionaries", army_b, keywords=("HERETIC ASTARTES",))
    game_map.units = [own, own_friend, mirror_enemy]

    assert game_map.get_friendly_units(own) == [own, own_friend]
    assert game_map.get_enemy_units(own) == [mirror_enemy]


def test_opposing_same_csm_detachment_aura_does_not_buff_attacker():
    from warhammer40k_ai.utility.aura_effects import get_aura_attack_modifiers

    _game, game_map, _player_a, _player_b, army_a, army_b = _mirror_game()
    aura = Ability(
        name="Paragon of Hatred (Aura)",
        faction_id="",
        description=(
            'While a friendly HERETIC ASTARTES unit is within 6" (excluding DAMNED units) of this model, '
            "each time a model in that unit makes an attack, you can re-roll the Hit roll."
        ),
        type="Datasheet",
        parameter="",
        legend=None,
    )
    attacker = _MirrorUnit("attacker", army_a, keywords=("HERETIC ASTARTES",))
    target = _MirrorUnit("target", army_b, keywords=("HERETIC ASTARTES",))
    opposing_abaddon = _MirrorUnit("opposing-abaddon", army_b, abilities=[aura], keywords=("HERETIC ASTARTES",))
    game_map.units = [attacker, target, opposing_abaddon]
    profile = SimpleNamespace(parent_wargear=SimpleNamespace(is_melee=lambda: False, is_ranged=lambda: True))

    with patch("warhammer40k_ai.utility.aura_effects.unit_within_range_of_unit", return_value=True):
        mods = get_aura_attack_modifiers(attacker, target, profile, game_map=game_map)

    assert mods.reroll_hit_full is False


def test_csm_detachment_and_stratagem_helpers_scope_to_owner_army_id():
    _game, _game_map, player_a, player_b, army_a, army_b = _mirror_game()
    own = _MirrorUnit("own", army_a, keywords=("HERETIC ASTARTES",))
    mirror_enemy = _MirrorUnit("mirror", army_b, keywords=("HERETIC ASTARTES",))

    assert army_a.chaos_space_marines_detachments._unit_in_army(own) is True
    assert army_a.chaos_space_marines_detachments._unit_in_army(mirror_enemy) is False
    assert army_b.chaos_space_marines_detachments._unit_in_army(mirror_enemy) is True

    assert ChaosSpaceMarinesStratagemMixin._csm_owned_by_player(own, player_a) is True
    assert ChaosSpaceMarinesStratagemMixin._csm_owned_by_player(mirror_enemy, player_a) is False
    assert ChaosSpaceMarinesStratagemMixin._csm_owned_by_player(mirror_enemy, player_b) is True


def test_enemy_model_count_uses_army_ids_not_matching_csm_labels():
    from warhammer40k_ai.utility.aura_utils import count_enemy_models_within_range

    _game, game_map, _player_a, _player_b, army_a, army_b = _mirror_game()
    source = _MirrorUnit("source", army_a, keywords=("HERETIC ASTARTES",))
    friend = _MirrorUnit("friend", army_a, keywords=("HERETIC ASTARTES",))
    mirror_enemy = _MirrorUnit("mirror-enemy", army_b, keywords=("HERETIC ASTARTES",))
    source_model = _attach_model(source, 0, 0)
    _attach_model(friend, 1, 0)
    _attach_model(mirror_enemy, 2, 0)
    game_map.units = [source, friend, mirror_enemy]

    assert count_enemy_models_within_range(source_model, 3.0, game_map=game_map) == 1
