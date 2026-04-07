from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.missions import DeploymentZone, DeploymentZoneType
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile


class _MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None):
        self.id = f"mock-{name.lower().replace(' ', '-')}"
        self.name = name
        self.faction_data = {"name": "Necrons"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
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


class _ObjectiveLocation:
    def __init__(self, x: float, y: float, controlling_player):
        self.x = float(x)
        self.y = float(y)
        self.removed = False
        self.controlling_player = controlling_player

    def update_control(self, _game) -> None:
        return None


class _Objective:
    def __init__(self, x: float, y: float, controlling_player):
        self.location = _ObjectiveLocation(x, y, controlling_player)


def _create_unit(name: str, *, keywords=None, faction_keywords=None) -> Unit:
    unit = Unit(_MockDatasheet(name, keywords=keywords, faction_keywords=faction_keywords))
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _configure_deployment_zones(game: Game, p1: Player, p2: Player) -> None:
    game.deployment_zones = {
        p1.id: {
            "mission_zones": [
                DeploymentZone(
                    name="P1 Zone",
                    zone_type=DeploymentZoneType.DEFENDER,
                    vertices=[(0.0, 0.0), (18.0, 0.0), (18.0, 44.0), (0.0, 44.0)],
                )
            ]
        },
        p2.id: {
            "mission_zones": [
                DeploymentZone(
                    name="P2 Zone",
                    zone_type=DeploymentZoneType.ATTACKER,
                    vertices=[(42.0, 0.0), (60.0, 0.0), (60.0, 44.0), (42.0, 44.0)],
                )
            ]
        },
    }


def _build_game(*, necron_units: list[Unit], enemy_units: list[Unit]):
    necron_army = Army.with_detachment("Necrons", "Canoptek Court")
    necron_army.faction_id = "NEC"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "ENEMY"

    for unit in list(necron_units or []):
        necron_army.add_unit(unit)
        unit.deployed = True
        unit.reserve_status = "deployed"
    for unit in list(enemy_units or []):
        enemy_army.add_unit(unit)
        unit.deployed = True
        unit.reserve_status = "deployed"

    necron_player = Player("Necron Player", control=PlayerControl.LOCAL, army=necron_army)
    enemy_player = Player("Enemy Player", control=PlayerControl.REMOTE, army=enemy_army)

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.add_player(necron_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    game.phase = SimpleNamespace(name="SHOOTING_PHASE")
    _configure_deployment_zones(game, necron_player, enemy_player)
    game.map.units = list(necron_units or []) + list(enemy_units or [])
    return game, necron_player, enemy_player


def _set_xy(unit: Unit, x: float, y: float) -> None:
    unit.models[0].set_location(float(x), float(y), 0.0, 0.0)


def _make_ranged_profile(*, bs: str = "3+") -> WargearProfile:
    parent = SimpleNamespace(name="Gauss Blaster", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        "Profile",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": str(bs),
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def _resolve_hit(profile: WargearProfile, attacker_model, target_unit, *, rolls: list[int], monkeypatch):
    import warhammer40k_ai.units.wargear as wargear_mod

    sequence = list(rolls or [1])
    fallback = int(sequence[-1])
    index = {"i": 0}

    def _fake_roll(_faces):
        i = int(index["i"])
        index["i"] = i + 1
        if i < len(sequence):
            return int(sequence[i])
        return fallback

    monkeypatch.setattr(wargear_mod, "get_roll", _fake_roll)
    attack_instance = {"_aura_attack_mods": SimpleNamespace(hit=0, hit_reasons=())}
    return profile._hit_target_with_tracking(target_unit, attacker_model, attack_instance)


def test_power_matrix_rerolls_hit_roll_of_one_for_canoptek_units_outside_matrix(monkeypatch):
    canoptek = _create_unit(
        "Canoptek Wraiths",
        keywords=["CANOPTEK", "INFANTRY"],
        faction_keywords=["NECRONS"],
    )
    enemy = _create_unit("Enemy Unit", keywords=["INFANTRY"])
    game, _p1, _p2 = _build_game(necron_units=[canoptek], enemy_units=[enemy])
    _set_xy(canoptek, 30.0, 22.0)
    _set_xy(enemy, 35.0, 22.0)

    profile = _make_ranged_profile(bs="3+")
    one_rerolled = _resolve_hit(profile, canoptek.models[0], enemy, rolls=[1, 4], monkeypatch=monkeypatch)
    assert bool(one_rerolled.get("hit"))

    no_full_reroll = _resolve_hit(profile, canoptek.models[0], enemy, rolls=[2, 4], monkeypatch=monkeypatch)
    assert not bool(no_full_reroll.get("hit"))


def test_power_matrix_grants_full_hit_reroll_when_wholly_within_own_zone(monkeypatch):
    canoptek = _create_unit(
        "Canoptek Tomb Crawlers",
        keywords=["CANOPTEK", "INFANTRY"],
        faction_keywords=["NECRONS"],
    )
    enemy = _create_unit("Enemy Unit", keywords=["INFANTRY"])
    game, _p1, _p2 = _build_game(necron_units=[canoptek], enemy_units=[enemy])
    _set_xy(canoptek, 8.0, 22.0)
    _set_xy(enemy, 28.0, 22.0)

    profile = _make_ranged_profile(bs="3+")
    full_reroll = _resolve_hit(profile, canoptek.models[0], enemy, rolls=[2, 5], monkeypatch=monkeypatch)
    assert bool(full_reroll.get("hit"))


def test_power_matrix_only_applies_to_cryptek_or_canoptek_units(monkeypatch):
    cryptek = _create_unit(
        "Chronomancer",
        keywords=["CRYPTEK", "INFANTRY"],
        faction_keywords=["NECRONS"],
    )
    warriors = _create_unit(
        "Necron Warriors",
        keywords=["INFANTRY"],
        faction_keywords=["NECRONS"],
    )
    enemy = _create_unit("Enemy Unit", keywords=["INFANTRY"])
    game, _p1, _p2 = _build_game(necron_units=[cryptek, warriors], enemy_units=[enemy])
    _set_xy(cryptek, 30.0, 20.0)
    _set_xy(warriors, 30.0, 24.0)
    _set_xy(enemy, 36.0, 22.0)

    profile = _make_ranged_profile(bs="3+")
    cryptek_hit = _resolve_hit(profile, cryptek.models[0], enemy, rolls=[1, 4], monkeypatch=monkeypatch)
    assert bool(cryptek_hit.get("hit"))

    warrior_hit = _resolve_hit(profile, warriors.models[0], enemy, rolls=[1, 4], monkeypatch=monkeypatch)
    assert not bool(warrior_hit.get("hit"))


def test_power_matrix_no_mans_land_snapshot_persists_until_phase_end(monkeypatch):
    canoptek = _create_unit(
        "Canoptek Spyders",
        keywords=["CANOPTEK", "INFANTRY"],
        faction_keywords=["NECRONS"],
    )
    enemy = _create_unit("Enemy Unit", keywords=["INFANTRY"])
    game, necron_player, enemy_player = _build_game(necron_units=[canoptek], enemy_units=[enemy])
    _set_xy(canoptek, 30.0, 22.0)
    _set_xy(enemy, 36.0, 22.0)

    nml_obj_a = _Objective(24.0, 22.0, controlling_player=necron_player)
    nml_obj_b = _Objective(36.0, 22.0, controlling_player=enemy_player)
    game.map.objectives = [nml_obj_a, nml_obj_b]

    profile = _make_ranged_profile(bs="3+")
    active_first = _resolve_hit(profile, canoptek.models[0], enemy, rolls=[2, 5], monkeypatch=monkeypatch)
    assert bool(active_first.get("hit"))

    nml_obj_a.location.controlling_player = enemy_player
    nml_obj_b.location.controlling_player = enemy_player

    still_active_same_phase = _resolve_hit(profile, canoptek.models[0], enemy, rolls=[2, 5], monkeypatch=monkeypatch)
    assert bool(still_active_same_phase.get("hit"))

    game.phase = SimpleNamespace(name="FIGHT_PHASE")
    inactive_next_phase = _resolve_hit(profile, canoptek.models[0], enemy, rolls=[2, 5], monkeypatch=monkeypatch)
    assert not bool(inactive_next_phase.get("hit"))
