from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.aura_effects import get_aura_attack_modifiers


_ENCEPHALIC_DIFFUSION_DESCRIPTION = (
    "While an enemy unit is within 6\" of this model, each time a model in that unit makes an attack, "
    "subtract 1 from the Hit roll, and, if that enemy unit is Below Half-strength, subtract 1 from the Wound roll as well."
)


class _MockDatasheet:
    def __init__(self, name: str, *, faction_name="Tyranids", keywords=None, faction_keywords=None, model_count: int = 1):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "8",
                "T": "5",
                "Sv": "4",
                "W": "2",
                "Ld": "7",
                "OC": "1",
                "base_size": "40mm",
                "inv_sv": "0",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []


def _make_unit(
    name: str,
    *,
    faction_name="Tyranids",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    tyr_army = Army.with_detachment("Tyranids", "Other")
    tyr_army.faction_id = "TYR"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    tyr_player = Player("Tyr", control=PlayerControl.LOCAL, army=tyr_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(tyr_player)
    game.add_player(enemy_player)
    return game, tyr_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (0.1 * idx), float(y), 0.0, 0.0)
    if not game.map.place_unit(unit):
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _make_ranged_profile() -> WargearProfile:
    parent = SimpleNamespace(name="Test Gun", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        profile_name="Ranged",
        wargear_data={
            "range": "24",
            "A": "2",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def test_encephalic_diffusion_applies_enemy_hit_penalty_within_aura():
    game, tyr_army, enemy_army = _build_game()
    maleceptor = _make_unit("Maleceptor", keywords=["MONSTER"], faction_keywords=["TYRANIDS"], model_count=1)
    maleceptor.possible_abilities = [
        Ability("Encephalic Diffusion (Aura, Psychic)", "TYR", _ENCEPHALIC_DIFFUSION_DESCRIPTION, "Datasheet", "")
    ]
    attacker = _make_unit("Enemy Attackers", faction_name="Enemy", faction_keywords=["ENEMY"], model_count=3)
    tyr_army.add_unit(maleceptor)
    enemy_army.add_unit(attacker)

    _deploy_unit(game, maleceptor, 10.0, 10.0)
    _deploy_unit(game, attacker, 14.0, 10.0)
    game.rebuild_entity_registry()

    profile = _make_ranged_profile()
    mods = get_aura_attack_modifiers(attacker, maleceptor, profile, game_map=game.map)

    assert int(getattr(mods, "hit", 0) or 0) == -1
    assert int(getattr(mods, "wound", 0) or 0) == 0


def test_encephalic_diffusion_adds_wound_penalty_when_attacker_below_half_strength():
    game, tyr_army, enemy_army = _build_game()
    maleceptor = _make_unit("Maleceptor", keywords=["MONSTER"], faction_keywords=["TYRANIDS"], model_count=1)
    maleceptor.possible_abilities = [
        Ability("Encephalic Diffusion (Aura, Psychic)", "TYR", _ENCEPHALIC_DIFFUSION_DESCRIPTION, "Datasheet", "")
    ]
    attacker = _make_unit("Enemy Attackers", faction_name="Enemy", faction_keywords=["ENEMY"], model_count=4)
    tyr_army.add_unit(maleceptor)
    enemy_army.add_unit(attacker)

    _deploy_unit(game, maleceptor, 10.0, 10.0)
    _deploy_unit(game, attacker, 14.0, 10.0)
    game.rebuild_entity_registry()

    # Force the attacker state into Below Half-strength for deterministic coverage.
    attacker.is_below_half_strength = lambda: True

    profile = _make_ranged_profile()
    mods = get_aura_attack_modifiers(attacker, maleceptor, profile, game_map=game.map)

    assert int(getattr(mods, "hit", 0) or 0) == -1
    assert int(getattr(mods, "wound", 0) or 0) == -1
