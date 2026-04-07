from __future__ import annotations

from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        datasheet_id: str | None = None,
        faction_name: str = "Chaos Space Marines",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        transport: str = "",
    ):
        self.id = str(datasheet_id or f"ds_{name.lower().replace(' ', '_')}")
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Model"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "3",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = str(transport or "")
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    datasheet_id: str | None = None,
    faction_name: str = "Chaos Space Marines",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    transport: str = "",
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            datasheet_id=datasheet_id,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            transport=transport,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _set_unit_location(unit: Unit, *, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str, description: str = "") -> Enhancement:
    enhancement = Enhancement(
        id=str(enhancement_id),
        name=str(enhancement_name),
        faction_id="CSM",
        detachment="Huron's Marauders",
        points=20,
        description=str(description or enhancement_name),
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)
    return enhancement


def _make_profile(*, weapon_type: str):
    weapon = Wargear(
        {
            "name": "Test Weapon",
            "type": "Melee" if str(weapon_type).lower() == "melee" else "Ranged",
            "range": "Melee" if str(weapon_type).lower() == "melee" else "24",
            "A": "1",
            "BS_WS": "4+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )
    return weapon.profiles["default"]


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    csm_army = Army.with_detachment("Chaos Space Marines", "Huron's Marauders")
    csm_army.faction_id = "CSM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    csm_player = Player("CSM", control=PlayerControl.REMOTE, army=csm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(csm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    game.phase = BattleRoundPhases.COMMAND_PHASE
    return game, csm_army, enemy_army, csm_player, enemy_player


def test_hurons_marauders_enhancement_descriptors_registered():
    expected = {
        "000010688002": ("Voice of the Tyrant", "bearer_unit_has_both_tyrannical_motivation_abilities"),
        "000010688003": ("Raid Leader", "allow_charge_after_disembark_from_transport_normal_move"),
        "000010688004": ("Dread Reputation", "on_set_up_enemy_units_within_range_take_battleshock_test"),
        "000010688005": ("Eager for Bloodshed", "bearer_gains_infiltrators"),
    }
    for enhancement_id, (name, effect) in expected.items():
        descriptor = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert descriptor is not None
        assert str(getattr(descriptor, "name", "") or "") == name
        assert str(getattr(descriptor, "effect", "") or "") == effect


def test_voice_of_the_tyrant_grants_both_tyrannical_motivation_abilities_without_huron_visibility():
    game, csm_army, enemy_army, _csm_player, _enemy_player = _build_game()
    source = _make_unit(
        "Chaos Lord",
        keywords=["CHARACTER", "INFANTRY", "HERETIC ASTARTES", "CHAOS LORD"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    csm_army.add_unit(source)
    enemy_army.add_unit(enemy)
    game.map.units = [source, enemy]
    game.rebuild_entity_registry()

    _apply_enhancement(source, enhancement_id="000010688002", enhancement_name="Voice of the Tyrant")
    source.round_state.fell_back_this_round = True

    csm_mgr = csm_army.chaos_space_marines_detachments
    hit_bonus, hit_source = csm_mgr.tyrannical_motivation_hit_bonus(source.models[0], game=game)
    assert int(hit_bonus) == 1
    assert "Tyrannical Motivation" in str(hit_source)

    profile = _make_profile(weapon_type="ranged")
    assert csm_mgr.tyrannical_motivation_can_shoot_after_fall_back(source, profile=profile, game=game) is True
    assert csm_mgr.tyrannical_motivation_can_charge_after_fall_back(source, game=game) is True
    assert source.can_shoot_after_fall_back(profile) is True
    assert source.can_charge_after_fall_back() is True


def test_raid_leader_allows_charge_after_disembark_from_normal_move():
    game, csm_army, enemy_army, _csm_player, _enemy_player = _build_game()
    transport = _make_unit(
        "Chaos Rhino",
        keywords=["HERETIC ASTARTES", "VEHICLE", "TRANSPORT"],
        faction_keywords=["HERETIC ASTARTES"],
        transport="Transport Capacity 12",
    )
    passenger = _make_unit(
        "Legionaries",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    csm_army.add_unit(transport)
    csm_army.add_unit(passenger)
    enemy_army.add_unit(enemy)

    _apply_enhancement(passenger, enhancement_id="000010688003", enhancement_name="Raid Leader")

    _set_unit_location(transport, x=10.0, y=10.0)
    _set_unit_location(enemy, x=20.0, y=10.0)
    game.map.place_unit(transport)
    game.map.place_unit(enemy)
    game.map.units = [transport, enemy]

    transport.round_state.moved_this_round = True
    transport.round_state.remained_stationary_this_round = False
    transport.transport_passengers = [passenger]
    passenger.embarked_in = transport

    ok = passenger.disembark(game_map=game.map, transport_unit=transport, current_turn=1)
    assert ok is True
    assert bool(passenger.round_state.disembarked_from_moved_transport) is True
    assert bool(passenger.round_state.disembarked_cannot_charge) is False


def test_dread_reputation_forces_battleshock_on_set_up_and_expands_range_with_deep_strike():
    game, csm_army, enemy_army, _csm_player, _enemy_player = _build_game()
    source = _make_unit(
        "Chaos Lord",
        keywords=["CHARACTER", "INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    enemy_close = _make_unit(
        "Enemy Close",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    enemy_mid = _make_unit(
        "Enemy Mid",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    enemy_far = _make_unit(
        "Enemy Far",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    csm_army.add_unit(source)
    enemy_army.add_unit(enemy_close)
    enemy_army.add_unit(enemy_mid)
    enemy_army.add_unit(enemy_far)

    _apply_enhancement(source, enhancement_id="000010688004", enhancement_name="Dread Reputation")

    _set_unit_location(source, x=0.0, y=0.0)
    _set_unit_location(enemy_close, x=5.0, y=0.0)
    _set_unit_location(enemy_mid, x=10.0, y=0.0)
    _set_unit_location(enemy_far, x=18.0, y=0.0)
    game.map.units = [source, enemy_close, enemy_mid, enemy_far]
    game.rebuild_entity_registry()

    calls: list[str] = []
    enemy_close.take_battle_shock_test = lambda _turn: calls.append("close")
    enemy_mid.take_battle_shock_test = lambda _turn: calls.append("mid")
    enemy_far.take_battle_shock_test = lambda _turn: calls.append("far")

    game._on_unit_set_up_csm_detachment_rules(
        unit=source,
        set_up_as_reinforcements=False,
        used_deep_strike=False,
    )
    assert calls == ["close"]

    calls.clear()
    game._on_unit_set_up_csm_detachment_rules(
        unit=source,
        set_up_as_reinforcements=True,
        used_deep_strike=True,
    )
    assert calls == ["close", "mid"]


def test_dread_reputation_triggers_from_disembarked_event_hook():
    game, csm_army, enemy_army, _csm_player, _enemy_player = _build_game()
    source = _make_unit(
        "Chaos Lord",
        keywords=["CHARACTER", "INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    enemy_close = _make_unit(
        "Enemy Close",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    enemy_far = _make_unit(
        "Enemy Far",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    csm_army.add_unit(source)
    enemy_army.add_unit(enemy_close)
    enemy_army.add_unit(enemy_far)
    _apply_enhancement(source, enhancement_id="000010688004", enhancement_name="Dread Reputation")

    _set_unit_location(source, x=0.0, y=0.0)
    _set_unit_location(enemy_close, x=5.0, y=0.0)
    _set_unit_location(enemy_far, x=18.0, y=0.0)
    game.map.units = [source, enemy_close, enemy_far]
    game.rebuild_entity_registry()

    calls: list[str] = []
    enemy_close.take_battle_shock_test = lambda _turn: calls.append("close")
    enemy_far.take_battle_shock_test = lambda _turn: calls.append("far")

    game._on_unit_disembarked_csm_detachment_rules(unit=source)
    assert calls == ["close"]


def test_eager_for_bloodshed_grants_infiltrators_and_invalidates_cache():
    _game, csm_army, _enemy_army, _csm_player, _enemy_player = _build_game()
    source = _make_unit(
        "Chaos Lord",
        keywords=["CHARACTER", "INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    csm_army.add_unit(source)

    assert source.has_infiltrate() is False
    _apply_enhancement(source, enhancement_id="000010688005", enhancement_name="Eager for Bloodshed")
    assert source.has_infiltrate() is True
