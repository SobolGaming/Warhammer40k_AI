from types import SimpleNamespace
from unittest.mock import patch


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


def _make_stub_unit(name: str, army, *, keywords=(), faction_keywords=()):
    from warhammer40k_ai.units.unit import Unit

    kw = {str(k).strip().lower() for k in keywords}
    fkw = {str(k).strip().lower() for k in faction_keywords}

    u = Unit.__new__(Unit)
    u._id = name.lower().replace(" ", "_")
    u.name = name
    u.deployed = True
    u.reserve_status = "deployed"
    u.keywords = list(keywords)
    u.faction_keywords = list(faction_keywords)
    u.has_keyword = lambda k: str(k).strip().lower() in kw or str(k).strip().lower() in fkw
    u.has_any_keyword = lambda k: str(k).strip().lower() in kw or str(k).strip().lower() in fkw
    u.get_effective_keywords = lambda: list(u.keywords)
    u.get_effective_faction_keywords = lambda: list(u.faction_keywords)
    u.get_parent_army = lambda: army
    u.is_alive = lambda: True
    u.get_attached_unit_root = lambda: u
    u.get_attached_unit_members = lambda: [u]
    u.get_attached_unit_models = lambda: u.models
    u.round_state = SimpleNamespace(remained_stationary_this_round=True)
    u.models = [SimpleNamespace(is_alive=True, model_base=_DummyBase(), parent_unit=u)]
    u.possible_abilities = []
    u.special_rules = {}
    u._ability_cache = {}
    return u


def test_warmaster_paragon_of_hatred_aura_requires_selection():
    from warhammer40k_ai.rules.csm_warmaster import KEY_PARAGON_OF_HATRED, set_active_warmaster
    from warhammer40k_ai.utility.aura_effects import get_aura_attack_modifiers

    player_a = SimpleNamespace(name="Player A", id="Player A")
    player_b = SimpleNamespace(name="Player B", id="Player B")
    game = SimpleNamespace(turn=1)
    player_a.game = game
    player_b.game = game
    army_a = SimpleNamespace(player=player_a, units=[])
    army_b = SimpleNamespace(player=player_b, units=[])

    attacker = _make_stub_unit(
        "Legionaries",
        army_a,
        keywords=("INFANTRY", "HERETIC ASTARTES"),
        faction_keywords=("HERETIC ASTARTES",),
    )
    abaddon = _make_stub_unit(
        "Abaddon The Despoiler",
        army_a,
        keywords=("INFANTRY", "HERETIC ASTARTES"),
        faction_keywords=("HERETIC ASTARTES",),
    )
    target = _make_stub_unit("Target", army_b, keywords=("INFANTRY",), faction_keywords=("ENEMY",))

    abaddon.possible_abilities = [
        SimpleNamespace(name="The Warmaster"),
        SimpleNamespace(
            name="Paragon of Hatred (Aura)",
            description=(
                'While a friendly HERETIC ASTARTES unit is within 6" (excluding DAMNED units) of this model, '
                "each time a model in that unit makes an attack, you can re-roll the Hit roll."
            ),
        ),
    ]
    army_a.units.extend([attacker, abaddon])
    army_b.units.append(target)
    game_map = _DummyMap([attacker, abaddon, target])
    game.map = game_map

    profile = SimpleNamespace(parent_wargear=SimpleNamespace(is_ranged=lambda: True, is_melee=lambda: False))

    with patch("warhammer40k_ai.utility.aura_effects.unit_within_range_of_unit", return_value=True):
        mods = get_aura_attack_modifiers(attacker, target, profile, game_map=game_map)
    assert mods.reroll_hit_full is False

    set_active_warmaster(
        abaddon,
        KEY_PARAGON_OF_HATRED,
        start_round=1,
        expires_round=2,
        player_id=player_a.id,
    )
    with patch("warhammer40k_ai.utility.aura_effects.unit_within_range_of_unit", return_value=True):
        mods = get_aura_attack_modifiers(attacker, target, profile, game_map=game_map)
    assert mods.reroll_hit_full is True


def test_warmaster_only_selected_sub_ability_is_active():
    from warhammer40k_ai.rules.csm_warmaster import (
        KEY_LORD_OF_THE_TRAITOR_LEGIONS,
        set_active_warmaster,
    )

    player = SimpleNamespace(name="Player A", id="Player A", game=SimpleNamespace(turn=1))
    army = SimpleNamespace(player=player, units=[])
    abaddon = _make_stub_unit(
        "Abaddon The Despoiler",
        army,
        keywords=("INFANTRY", "HERETIC ASTARTES"),
        faction_keywords=("HERETIC ASTARTES",),
    )
    paragon = SimpleNamespace(name="Paragon of Hatred (Aura)", description="Aura")
    mark = SimpleNamespace(name="Mark of Chaos Ascendant (Aura)", description="Aura")
    lord = SimpleNamespace(name="Lord of the Traitor Legions (Aura)", description="Aura")
    abaddon.possible_abilities = [SimpleNamespace(name="The Warmaster"), paragon, mark, lord]
    army.units.append(abaddon)

    assert abaddon._ability_is_active(paragon) is False
    assert abaddon._ability_is_active(mark) is False
    assert abaddon._ability_is_active(lord) is False

    set_active_warmaster(
        abaddon,
        KEY_LORD_OF_THE_TRAITOR_LEGIONS,
        start_round=1,
        expires_round=2,
        player_id=player.id,
    )
    assert abaddon._ability_is_active(paragon) is False
    assert abaddon._ability_is_active(mark) is False
    assert abaddon._ability_is_active(lord) is True


def test_warmaster_manager_requests_choice_in_command_phase():
    from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_WARMASTER_ABILITY
    from warhammer40k_ai.engine.decisions import DecisionQueue
    from warhammer40k_ai.rules.csm_warmaster import WarmasterManager

    player = SimpleNamespace(name="Player A", id="Player A")
    army = SimpleNamespace(player=player, units=[])
    abaddon = _make_stub_unit(
        "Abaddon The Despoiler",
        army,
        keywords=("INFANTRY", "HERETIC ASTARTES"),
        faction_keywords=("HERETIC ASTARTES",),
    )
    abaddon.possible_abilities = [SimpleNamespace(name="The Warmaster")]
    army.units.append(abaddon)

    queue = DecisionQueue()
    game = SimpleNamespace(turn=2, is_authoritative=True, decision_queue=queue)
    game.request_decision = queue.add
    player.game = game

    mgr = WarmasterManager(army)
    mgr.on_command_phase_start(player, game=game)

    pending = queue.list()
    assert len(pending) == 1
    req = pending[0]
    assert req.decision_type == DECISION_CHOOSE_WARMASTER_ABILITY
    assert len(req.options) == 3
    assert str(req.context.get("battle_round", "")) == "2"
