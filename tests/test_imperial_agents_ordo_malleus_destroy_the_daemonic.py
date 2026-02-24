from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str,
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
    ):
        count = max(1, int(model_count or 1))
        self.id = f"mock-{name.lower().replace(' ', '-')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{count} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{count} models", "cost": 100}]
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
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str,
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    ia_army = Army("Imperial Agents", "Ordo Malleus Daemon Hunters")
    ia_army.faction_id = "AOI"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "ENEMY"
    ia_player = Player("IA", control=PlayerControl.LOCAL, army=ia_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ia_player)
    game.add_player(enemy_player)
    return game, ia_player, enemy_player


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    if unit not in list(getattr(game.map, "units", []) or []):
        game.map.units.append(unit)


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
    )


def _attack_profile() -> WargearProfile:
    parent = SimpleNamespace(
        name="Test Gun",
        is_melee=lambda: False,
        is_ranged=lambda: True,
    )
    data = {
        "range": "24",
        "A": "1",
        "BS_WS": "4+",
        "S": "4",
        "AP": "0",
        "D": "1",
        "description": "",
    }
    return WargearProfile("Profile", wargear_data=data, parent_wargear=parent)


def test_destroy_the_daemonic_rerolls_hit_roll_of_one_for_eligible_models(monkeypatch):
    game, ia_player, enemy_player = _build_game()

    eligible = _make_unit(
        "Inquisitorial Agents",
        faction_name="Imperial Agents",
        keywords=["INFANTRY", "INQUISITORIAL AGENTS"],
        faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
    )
    ineligible = _make_unit(
        "Voidsmen-at-Arms",
        faction_name="Imperial Agents",
        keywords=["INFANTRY", "VOIDFARERS"],
        faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["CHAOS"],
    )

    ia_player.army.add_unit(eligible)
    ia_player.army.add_unit(ineligible)
    enemy_player.army.add_unit(enemy)
    _deploy_unit(game, eligible, 0.0, 0.0)
    _deploy_unit(game, ineligible, 2.0, 0.0)
    _deploy_unit(game, enemy, 12.0, 0.0)

    monkeypatch.setattr("warhammer40k_ai.units.wargear.get_roll", lambda _expr: 5)

    profile = _attack_profile()

    eligible_attack = {"_aura_attack_mods": _aura_stub()}
    eligible_result = profile._hit_target_with_tracking(
        enemy,
        eligible.models[0],
        eligible_attack,
        roll_value=1,
        allow_rerolls=True,
        log_roll=False,
    )
    assert int(eligible_result.get("reroll", 0) or 0) == 5
    assert any("Destroy the Daemonic" in str(effect) for effect in list(eligible_result.get("special_effects", []) or []))

    ineligible_attack = {"_aura_attack_mods": _aura_stub()}
    ineligible_result = profile._hit_target_with_tracking(
        enemy,
        ineligible.models[0],
        ineligible_attack,
        roll_value=1,
        allow_rerolls=True,
        log_roll=False,
    )
    assert "reroll" not in ineligible_result


def test_destroy_the_daemonic_rerolls_wound_roll_of_one_only_vs_daemon_targets(monkeypatch):
    game, ia_player, enemy_player = _build_game()

    attacker_unit = _make_unit(
        "Ordo Malleus Inquisitor",
        faction_name="Imperial Agents",
        keywords=["INFANTRY", "INQUISITOR", "ORDO MALLEUS"],
        faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
    )
    daemon_target = _make_unit(
        "Daemon Target",
        faction_name="Enemy",
        keywords=["INFANTRY", "DAEMON"],
        faction_keywords=["CHAOS"],
    )
    non_daemon_target = _make_unit(
        "Non-daemon Target",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["CHAOS"],
    )

    ia_player.army.add_unit(attacker_unit)
    enemy_player.army.add_unit(daemon_target)
    enemy_player.army.add_unit(non_daemon_target)
    _deploy_unit(game, attacker_unit, 0.0, 0.0)
    _deploy_unit(game, daemon_target, 12.0, 0.0)
    _deploy_unit(game, non_daemon_target, 14.0, 0.0)

    monkeypatch.setattr("warhammer40k_ai.units.wargear.get_roll", lambda _expr: 5)

    profile = _attack_profile()
    attacker_model = attacker_unit.models[0]

    attack_vs_daemon = {
        "_aura_attack_mods": _aura_stub(),
        "_aura_wound_mods": _aura_stub(),
        "attacker_model": attacker_model,
        "attacker_unit": attacker_unit,
    }
    daemon_result = profile._wound_target_with_tracking(
        daemon_target,
        attacker_model,
        attack_vs_daemon,
        roll_value=1,
        allow_rerolls=True,
        log_roll=False,
    )
    assert int(daemon_result.get("reroll", 0) or 0) == 5
    assert any("Destroy the Daemonic" in str(effect) for effect in list(daemon_result.get("special_effects", []) or []))

    attack_vs_non_daemon = {
        "_aura_attack_mods": _aura_stub(),
        "_aura_wound_mods": _aura_stub(),
        "attacker_model": attacker_model,
        "attacker_unit": attacker_unit,
    }
    non_daemon_result = profile._wound_target_with_tracking(
        non_daemon_target,
        attacker_model,
        attack_vs_non_daemon,
        roll_value=1,
        allow_rerolls=True,
        log_roll=False,
    )
    assert "reroll" not in non_daemon_result
