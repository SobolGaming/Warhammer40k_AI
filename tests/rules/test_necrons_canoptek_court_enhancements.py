from __future__ import annotations

import types
from types import SimpleNamespace

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.missions import DeploymentZone, DeploymentZoneType
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
        faction_name: str = "Necrons",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        wounds: int = 4,
    ):
        self.id = ""
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            faction_keywords = ["NECRONS"] if faction_name == "Necrons" else [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "5",
                "T": "5",
                "Sv": "3",
                "W": str(int(wounds)),
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
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Necrons",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: int = 4,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _set_unit_location(unit: Unit, *, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + float(idx) * 0.1, float(y), 0.0, 0.0)


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


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    necron_army = Army.with_detachment("Necrons", "Canoptek Court")
    necron_army.faction_id = "NEC"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    necron_player = Player("Necrons", control=PlayerControl.REMOTE, army=necron_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(necron_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.battle_round_starting_player_index = 0
    game.turn = 1
    game.phase = SimpleNamespace(name="SHOOTING_PHASE")
    _configure_deployment_zones(game, necron_player, enemy_player)
    necron_army.configure_rule_managers(force=True)
    return game, necron_army, enemy_army, necron_player, enemy_player


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    leader.can_be_attached_to = [bodyguard.name]
    leader.attached_to = bodyguard
    bodyguard.attached_leaders = [leader]
    for unit in (bodyguard, leader):
        invalidate_cache = getattr(unit, "_invalidate_ability_cache", None)
        if callable(invalidate_cache):
            invalidate_cache()


def _make_profile(*, skill: str = "3+"):
    data = {
        "range": "24",
        "A": "1",
        "BS_WS": skill,
        "S": "4",
        "AP": "0",
        "D": "1",
        "description": "",
    }
    parent = Wargear({"name": "Test Weapon", "type": "Ranged", **data})
    return parent.profiles["default"]


def _apply_named_enhancement(
    unit: Unit,
    *,
    enhancement_id: str,
    name: str,
    description: str,
    points: int = 20,
) -> None:
    enhancement = Enhancement(
        id=enhancement_id,
        name=name,
        faction_id="NEC",
        detachment="Canoptek Court",
        points=points,
        description=description,
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)


def _bearer_model(unit: Unit):
    getter = getattr(unit, "_get_enhancement_bearer_model", None)
    if callable(getter):
        model = getter()
        if model is not None:
            return model
    models = list(getattr(unit, "models", []) or [])
    return models[0] if models else None


def _resolve_wound(profile, attacker_model, target_unit, *, rolls: list[int], monkeypatch):
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
    return profile._wound_target_with_tracking(target_unit, attacker_model, attack_instance)


def test_canoptek_court_enhancement_descriptors_registered():
    expected = {
        "000008546002": ("Dimensional Sanctum", "grant_infiltrators_to_bearer_unit_models"),
        "000008546003": ("Hyperphasic Fulcrum", "power_matrix_bearer_unit_wound_reroll_ones_while_leading"),
        "000008546005": ("Metalodermal Tesla Weave", "charge_target_mortal_wounds_once_per_phase"),
    }

    for enhancement_id, (name, effect) in expected.items():
        descriptor = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert descriptor is not None
        assert str(getattr(descriptor, "name", "") or "") == name
        assert str(getattr(descriptor, "effect", "") or "") == effect


def test_dimensional_sanctum_grants_infiltrators_to_bearer_unit_while_bearer_alive():
    game, necron_army, _enemy_army, _necron_player, _enemy_player = _build_game()
    cryptek = _make_unit(
        "Chronomancer",
        keywords=["CHARACTER", "CRYPTEK", "INFANTRY", "NECRONS"],
        faction_keywords=["NECRONS"],
    )
    bodyguard = _make_unit(
        "Necron Warriors",
        keywords=["INFANTRY", "NECRONS"],
        faction_keywords=["NECRONS"],
        model_count=2,
        wounds=2,
    )
    necron_army.add_unit(cryptek)
    necron_army.add_unit(bodyguard)
    game.map.units = [cryptek, bodyguard]
    game.rebuild_entity_registry()

    _apply_named_enhancement(
        cryptek,
        enhancement_id="000008546002",
        name="Dimensional Sanctum",
        description="CRYPTEK model only. Models in the bearer's unit have the Infiltrators ability.",
    )

    assert bool(cryptek.has_infiltrate())
    assert not bool(bodyguard.has_infiltrate())

    _attach_leader(bodyguard, cryptek)
    assert bool(bodyguard.has_infiltrate())

    bearer = _bearer_model(cryptek)
    assert bearer is not None
    bearer.take_damage(int(getattr(bearer, "wounds", 0) or 0), game_map=game.map)
    invalidate_cache = getattr(bodyguard, "_invalidate_ability_cache", None)
    if callable(invalidate_cache):
        invalidate_cache()
    assert not bool(bodyguard.has_infiltrate())


def test_hyperphasic_fulcrum_rerolls_wound_ones_only_while_leading_and_wholly_within_power_matrix(monkeypatch):
    game, necron_army, enemy_army, _necron_player, _enemy_player = _build_game()
    cryptek = _make_unit(
        "Technomancer",
        keywords=["CHARACTER", "CRYPTEK", "INFANTRY", "NECRONS"],
        faction_keywords=["NECRONS"],
    )
    bodyguard = _make_unit(
        "Immortals",
        keywords=["INFANTRY", "NECRONS"],
        faction_keywords=["NECRONS"],
        model_count=2,
        wounds=2,
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    necron_army.add_unit(cryptek)
    necron_army.add_unit(bodyguard)
    enemy_army.add_unit(enemy)
    _set_unit_location(cryptek, x=6.0, y=20.0)
    _set_unit_location(bodyguard, x=6.0, y=20.5)
    _set_unit_location(enemy, x=30.0, y=20.0)
    game.map.units = [cryptek, bodyguard, enemy]
    game.rebuild_entity_registry()

    _apply_named_enhancement(
        cryptek,
        enhancement_id="000008546003",
        name="Hyperphasic Fulcrum",
        description=(
            "CRYPTEK model only. While the bearer is leading a unit, if that unit is wholly within your army's "
            "Power Matrix, each time a model in that unit makes an attack, re-roll a Wound roll of 1."
        ),
    )
    _attach_leader(bodyguard, cryptek)

    profile = _make_profile()
    buffed = _resolve_wound(profile, bodyguard.models[0], enemy, rolls=[1, 5], monkeypatch=monkeypatch)
    assert bool(buffed.get("wound"))
    assert 1 in list(buffed.get("reroll_values", []) or [])
    assert any(
        "Hyperphasic Fulcrum" in str(reason or "")
        for reason in list(buffed.get("reroll_value_reasons", []) or [])
    )

    _set_unit_location(bodyguard, x=28.0, y=20.0)
    unbuffed = _resolve_wound(profile, bodyguard.models[0], enemy, rolls=[1, 5], monkeypatch=monkeypatch)
    assert not bool(unbuffed.get("wound"))
    assert 1 not in list(unbuffed.get("reroll_values", []) or [])

    _set_unit_location(bodyguard, x=6.0, y=20.5)
    bearer = _bearer_model(cryptek)
    assert bearer is not None
    bearer.take_damage(int(getattr(bearer, "wounds", 0) or 0), game_map=game.map)
    no_bearer = _resolve_wound(profile, bodyguard.models[0], enemy, rolls=[1, 5], monkeypatch=monkeypatch)
    assert not bool(no_bearer.get("wound"))
    assert 1 not in list(no_bearer.get("reroll_values", []) or [])


def test_metalodermal_tesla_weave_triggers_once_per_phase_when_charge_is_declared(monkeypatch):
    game, necron_army, enemy_army, _necron_player, _enemy_player = _build_game()
    game.phase = SimpleNamespace(name="CHARGE_PHASE")
    cryptek = _make_unit(
        "Plasmancer",
        keywords=["CHARACTER", "CRYPTEK", "INFANTRY", "NECRONS"],
        faction_keywords=["NECRONS"],
    )
    bodyguard = _make_unit(
        "Lychguard",
        keywords=["INFANTRY", "NECRONS"],
        faction_keywords=["NECRONS"],
        model_count=2,
        wounds=2,
    )
    charging = _make_unit(
        "Enemy Chargers",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds=8,
    )
    necron_army.add_unit(cryptek)
    necron_army.add_unit(bodyguard)
    enemy_army.add_unit(charging)
    game.map.units = [cryptek, bodyguard, charging]
    game.rebuild_entity_registry()

    _apply_named_enhancement(
        cryptek,
        enhancement_id="000008546005",
        name="Metalodermal Tesla Weave",
        description=(
            "CRYPTEK model only. Once per phase, when an enemy unit selects the bearer's unit as a target of a charge, "
            "roll one D6: on a 2-5, that enemy unit suffers D3 mortal wounds; on a 6, that enemy unit suffers 3 mortal wounds."
        ),
    )
    _attach_leader(bodyguard, cryptek)

    applied = {"amounts": []}

    def _apply(self, target_unit, amount, game_map=None):
        applied["amounts"].append(int(amount or 0))
        return 0

    bodyguard._apply_mortal_wounds_to_unit = types.MethodType(_apply, bodyguard)

    import warhammer40k_ai.rules.necrons_detachments as necrons_mod

    sequence = [5, 2, 6]
    index = {"i": 0}

    def _fake_roll(_faces):
        value = int(sequence[index["i"]])
        index["i"] = index["i"] + 1
        return value

    monkeypatch.setattr(necrons_mod, "get_roll", _fake_roll)

    game._on_charge_declared_detachment_rules(unit=charging, target_units=[bodyguard])
    assert applied["amounts"] == [2]

    game._on_charge_declared_detachment_rules(unit=charging, target_units=[bodyguard])
    assert applied["amounts"] == [2]

    game.turn = 2
    game._on_charge_declared_detachment_rules(unit=charging, target_units=[bodyguard])
    assert applied["amounts"] == [2, 3]

    bearer = _bearer_model(cryptek)
    assert bearer is not None
    bearer.take_damage(int(getattr(bearer, "wounds", 0) or 0), game_map=game.map)
    game.turn = 3
    game._on_charge_declared_detachment_rules(unit=charging, target_units=[bodyguard])
    assert applied["amounts"] == [2, 3]
