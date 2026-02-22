from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.units import wargear as wargear_mod
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.unit_mixins import damage_death_mixin as death_mod
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility import dice as dice_mod
from warhammer40k_ai.utility.dice import DiceCollection


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Thousand Sons",
        keywords=None,
        faction_keywords=None,
        toughness: str = "4",
        wounds: str = "8",
    ):
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "10",
                "T": str(toughness),
                "Sv": "3",
                "W": str(wounds),
                "Ld": "7",
                "OC": "3",
                "base_size": "60mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.attached_to = []


def _make_unit(
    name: str,
    *,
    keywords=None,
    faction_keywords=None,
    faction_name: str = "Thousand Sons",
    toughness: str = "4",
    wounds: str = "8",
) -> Unit:
    datasheet = _MockDatasheet(
        name,
        faction_name=faction_name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        toughness=toughness,
        wounds=wounds,
    )
    unit = Unit(datasheet)
    unit.deployed = True
    return unit


def _set_location(unit: Unit, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)


def _make_profile(*, ranged: bool, damage: str = "D6") -> WargearProfile:
    parent = SimpleNamespace(
        name="Test Weapon",
        is_melee=lambda: not ranged,
        is_ranged=lambda: ranged,
    )
    return WargearProfile(
        profile_name="Profile",
        wargear_data={
            "range": "24" if ranged else "Melee",
            "A": "1",
            "BS_WS": "4+",
            "S": "4",
            "AP": "0",
            "D": str(damage),
            "description": "",
        },
        parent_wargear=parent,
    )


def _aura_stub():
    return SimpleNamespace(
        hit=0,
        wound=0,
        reroll_hit_ones=False,
        reroll_wound_ones=False,
        reroll_hit_reasons=(),
        reroll_wound_reasons=(),
        target_toughness_delta=0,
        target_toughness_reasons=(),
        crit_wound_threshold=None,
        crit_wound_reasons=(),
    )


def _build_game(*, army: Army, enemy_army: Army, phase_name: str = "SHOOTING_PHASE"):
    game_map = SimpleNamespace(roll_reroll_provider=None)
    player = SimpleNamespace(
        id="P1",
        name="P1",
        has_control=lambda: False,
        game=None,
        stratagems=None,
        get_army=lambda: army,
    )
    enemy_player = SimpleNamespace(
        id="P2",
        name="P2",
        has_control=lambda: False,
        game=None,
        stratagems=None,
        get_army=lambda: enemy_army,
    )
    game = SimpleNamespace(
        turn=1,
        phase=SimpleNamespace(name=str(phase_name)),
        players=[player, enemy_player],
        map=game_map,
        get_current_player=lambda: player,
    )
    player.game = game
    enemy_player.game = game
    army.player = player
    enemy_army.player = enemy_player
    return game


def test_warpfire_infusion_nearby_psyker_grants_one_hit_wound_and_damage_reroll():
    army = Army("Thousand Sons", "Warpforged Cabal")
    army.faction_id = "TS"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    vehicle = _make_unit(
        "Thousand Sons Tank",
        keywords=["THOUSAND SONS", "VEHICLE"],
        faction_keywords=["THOUSAND SONS"],
    )
    psyker = _make_unit(
        "Thousand Sons Psyker",
        keywords=["THOUSAND SONS", "PSYKER"],
        faction_keywords=["THOUSAND SONS"],
    )
    army.add_unit(vehicle)
    army.add_unit(psyker)
    _set_location(vehicle, 0.0, 0.0)
    _set_location(psyker, 4.0, 0.0)
    game = _build_game(army=army, enemy_army=enemy_army, phase_name="SHOOTING_PHASE")

    mgr = army.thousand_sons_detachments
    assert mgr.warpfire_infusion_start_selection(vehicle, action="shoot", game=game)

    assert mgr.warpfire_infusion_reroll_is_available(vehicle, "hit", action="shoot", game=game)
    assert mgr.consume_warpfire_infusion_reroll(vehicle, "hit", action="shoot", game=game)
    assert not mgr.warpfire_infusion_reroll_is_available(vehicle, "hit", action="shoot", game=game)

    assert mgr.warpfire_infusion_reroll_is_available(vehicle, "wound", action="shoot", game=game)
    assert mgr.consume_warpfire_infusion_reroll(vehicle, "wound", action="shoot", game=game)
    assert not mgr.warpfire_infusion_reroll_is_available(vehicle, "wound", action="shoot", game=game)

    assert mgr.warpfire_infusion_reroll_is_available(vehicle, "damage", action="shoot", game=game)
    assert mgr.consume_warpfire_infusion_reroll(vehicle, "damage", action="shoot", game=game)
    assert not mgr.warpfire_infusion_reroll_is_available(vehicle, "damage", action="shoot", game=game)


def test_warpfire_infusion_without_nearby_psyker_allows_only_one_total_reroll():
    army = Army("Thousand Sons", "Warpforged Cabal")
    army.faction_id = "TS"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    vehicle = _make_unit(
        "Thousand Sons Tank",
        keywords=["THOUSAND SONS", "VEHICLE"],
        faction_keywords=["THOUSAND SONS"],
    )
    psyker = _make_unit(
        "Thousand Sons Psyker",
        keywords=["THOUSAND SONS", "PSYKER"],
        faction_keywords=["THOUSAND SONS"],
    )
    army.add_unit(vehicle)
    army.add_unit(psyker)
    _set_location(vehicle, 0.0, 0.0)
    _set_location(psyker, 20.0, 0.0)
    game = _build_game(army=army, enemy_army=enemy_army, phase_name="SHOOTING_PHASE")

    mgr = army.thousand_sons_detachments
    assert mgr.warpfire_infusion_start_selection(vehicle, action="shoot", game=game)
    assert mgr.consume_warpfire_infusion_reroll(vehicle, "hit", action="shoot", game=game)
    assert not mgr.warpfire_infusion_reroll_is_available(vehicle, "hit", action="shoot", game=game)
    assert not mgr.warpfire_infusion_reroll_is_available(vehicle, "wound", action="shoot", game=game)
    assert not mgr.warpfire_infusion_reroll_is_available(vehicle, "damage", action="shoot", game=game)


def test_warpfire_infusion_rerolls_hit_wound_and_damage_in_attack_resolution(monkeypatch):
    army = Army("Thousand Sons", "Warpforged Cabal")
    army.faction_id = "TS"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    vehicle = _make_unit(
        "Thousand Sons Tank",
        keywords=["THOUSAND SONS", "VEHICLE"],
        faction_keywords=["THOUSAND SONS"],
        wounds="12",
    )
    psyker = _make_unit(
        "Thousand Sons Psyker",
        keywords=["THOUSAND SONS", "PSYKER"],
        faction_keywords=["THOUSAND SONS"],
        wounds="4",
    )
    target = _make_unit(
        "Enemy Target",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        toughness="4",
        wounds="12",
    )
    army.add_unit(vehicle)
    army.add_unit(psyker)
    enemy_army.add_unit(target)
    _set_location(vehicle, 0.0, 0.0)
    _set_location(psyker, 4.0, 0.0)
    _set_location(target, 8.0, 0.0)
    game = _build_game(army=army, enemy_army=enemy_army, phase_name="SHOOTING_PHASE")
    army.player.has_control = lambda: True
    game.map.roll_reroll_provider = lambda **_kwargs: True

    mgr = army.thousand_sons_detachments
    assert mgr.warpfire_infusion_start_selection(vehicle, action="shoot", game=game)

    rolls = iter([5, 4])
    monkeypatch.setattr(wargear_mod, "get_roll", lambda _expr: next(rolls))
    monkeypatch.setattr(dice_mod, "get_roll", lambda _expr: 6)

    profile = _make_profile(ranged=True, damage="D6")
    attack_instance = {"_aura_attack_mods": _aura_stub()}

    hit = profile._hit_target_with_tracking(
        target,
        vehicle.models[0],
        attack_instance,
        roll_value=1,
        allow_rerolls=True,
        log_roll=False,
    )
    assert int(hit.get("reroll", 0) or 0) == 5
    assert any("Warpfire Infusion" in str(entry) for entry in hit.get("special_effects", []))

    wound = profile._wound_target_with_tracking(
        target,
        vehicle.models[0],
        attack_instance,
        roll_value=1,
        allow_rerolls=True,
        log_roll=False,
    )
    assert int(wound.get("reroll", 0) or 0) == 4
    assert any("Warpfire Infusion" in str(entry) for entry in wound.get("special_effects", []))

    damage = profile._damage_target_with_tracking(
        target.models[0],
        vehicle.models[0],
        {"below_half_distance": False, "mortal_wound": False},
        roll_value=1,
        roll_values=[1],
        allow_rerolls=True,
    )
    assert int(damage.get("reroll", 0) or 0) == 6
    assert any("Warpfire Infusion" in str(entry) for entry in damage.get("special_effects", []))


def test_warpfire_infusion_deadly_demise_triggers_on_five_when_near_psyker(monkeypatch):
    army = Army("Thousand Sons", "Warpforged Cabal")
    army.faction_id = "TS"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    vehicle = _make_unit(
        "Thousand Sons Tank",
        keywords=["THOUSAND SONS", "VEHICLE"],
        faction_keywords=["THOUSAND SONS"],
    )
    psyker = _make_unit(
        "Thousand Sons Psyker",
        keywords=["THOUSAND SONS", "PSYKER"],
        faction_keywords=["THOUSAND SONS"],
    )
    army.add_unit(vehicle)
    army.add_unit(psyker)
    _set_location(vehicle, 0.0, 0.0)
    _set_location(psyker, 4.0, 0.0)
    _build_game(army=army, enemy_army=enemy_army, phase_name="SHOOTING_PHASE")

    vehicle.has_deadly_demise = lambda: (True, DiceCollection.from_string("D3"))
    explosions = {"count": 0}

    def _record_explosion(*, damage_dice, position, game_map):
        _ = damage_dice
        _ = position
        _ = game_map
        explosions["count"] += 1

    vehicle._apply_deadly_demise_explosion = _record_explosion
    monkeypatch.setattr(death_mod, "get_roll", lambda _expr: 5)

    vehicle._trigger_deadly_demise(vehicle.models[0], game_map=SimpleNamespace())
    assert int(explosions["count"]) == 1

    explosions["count"] = 0
    _set_location(psyker, 20.0, 0.0)
    vehicle._trigger_deadly_demise(vehicle.models[0], game_map=SimpleNamespace())
    assert int(explosions["count"]) == 0
