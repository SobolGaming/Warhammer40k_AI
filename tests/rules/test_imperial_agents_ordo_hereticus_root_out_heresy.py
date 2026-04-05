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
        movement: int = 6,
        leadership: int = 7,
        objective_control: int = 1,
        save: int = 3,
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
                "M": str(int(movement)),
                "T": "4",
                "Sv": str(int(save)),
                "W": "2",
                "Ld": str(int(leadership)),
                "OC": str(int(objective_control)),
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
    ia_army = Army("Imperial Agents", "Ordo Hereticus Purgation Force")
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


def _attack_profile(*, is_ranged: bool = True) -> WargearProfile:
    parent = SimpleNamespace(
        name="Test Gun" if is_ranged else "Test Blade",
        is_melee=lambda: not is_ranged,
        is_ranged=lambda: is_ranged,
    )
    data = {
        "range": "24" if is_ranged else "2",
        "A": "1",
        "BS_WS": "4+",
        "S": "4",
        "AP": "0",
        "D": "1",
        "description": "",
    }
    return WargearProfile("Profile", wargear_data=data, parent_wargear=parent)


def test_root_out_heresy_grants_ranged_ignores_cover_to_eligible_models_only():
    game, ia_player, enemy_player = _build_game()

    eligible = _make_unit(
        "Exaction Squad",
        faction_name="Imperial Agents",
        keywords=["INFANTRY", "ADEPTUS ARBITES"],
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

    profile = _attack_profile(is_ranged=True)

    eligible_attack = {"_aura_attack_mods": _aura_stub()}
    profile._hit_target_with_tracking(
        enemy,
        eligible.models[0],
        eligible_attack,
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(eligible_attack.get("ignores_cover", False))

    ineligible_attack = {"_aura_attack_mods": _aura_stub()}
    profile._hit_target_with_tracking(
        enemy,
        ineligible.models[0],
        ineligible_attack,
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(ineligible_attack.get("ignores_cover", False)) is False


def test_root_out_heresy_grants_sustained_hits_only_vs_chaos_units_with_five_or_more_models():
    game, ia_player, enemy_player = _build_game()

    attacker = _make_unit(
        "Inquisitorial Agents",
        faction_name="Imperial Agents",
        keywords=["INFANTRY", "INQUISITORIAL AGENTS"],
        faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
    )
    chaos_five = _make_unit(
        "Chaos Mob Five",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["CHAOS"],
        model_count=5,
    )
    chaos_four = _make_unit(
        "Chaos Mob Four",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["CHAOS"],
        model_count=4,
    )
    non_chaos_five = _make_unit(
        "Loyal Mob Five",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["IMPERIUM"],
        model_count=5,
    )

    ia_player.army.add_unit(attacker)
    enemy_player.army.add_unit(chaos_five)
    enemy_player.army.add_unit(chaos_four)
    enemy_player.army.add_unit(non_chaos_five)
    _deploy_unit(game, attacker, 0.0, 0.0)
    _deploy_unit(game, chaos_five, 12.0, 0.0)
    _deploy_unit(game, chaos_four, 14.0, 0.0)
    _deploy_unit(game, non_chaos_five, 16.0, 0.0)

    profile = _attack_profile(is_ranged=True)
    attacker_model = attacker.models[0]

    attack_vs_chaos_five = {"_aura_attack_mods": _aura_stub()}
    hit_vs_chaos_five = profile._hit_target_with_tracking(
        chaos_five,
        attacker_model,
        attack_vs_chaos_five,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert int(attack_vs_chaos_five.get("sustained_hit", 0) or 0) == 1
    assert any("Root out Heresy" in str(effect) for effect in list(hit_vs_chaos_five.get("special_effects", []) or []))

    attack_vs_chaos_four = {"_aura_attack_mods": _aura_stub()}
    profile._hit_target_with_tracking(
        chaos_four,
        attacker_model,
        attack_vs_chaos_four,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert int(attack_vs_chaos_four.get("sustained_hit", 0) or 0) == 0

    attack_vs_non_chaos_five = {"_aura_attack_mods": _aura_stub()}
    profile._hit_target_with_tracking(
        non_chaos_five,
        attacker_model,
        attack_vs_non_chaos_five,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert int(attack_vs_non_chaos_five.get("sustained_hit", 0) or 0) == 0
