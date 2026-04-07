import pytest

from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.roster.army import Army, ArmyValidationError
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.nurgles_gift import NurglesGiftManager, PLAGUE_RATTLEJOINT
from warhammer40k_ai.utility.aura_effects import get_aura_attack_modifiers
from warhammer40k_ai.units.unit import Unit


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str,
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        cost: int = 100,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": int(cost)}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "5",
                "Sv": "3",
                "W": "4",
                "Ld": "7",
                "OC": "2",
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


class _StubParentWargear:
    @staticmethod
    def is_melee() -> bool:
        return False


class _StubWeaponProfile:
    def __init__(self):
        self.parent_wargear = _StubParentWargear()


def _make_unit(
    name: str,
    *,
    faction_name: str,
    keywords=None,
    faction_keywords=None,
    cost: int = 100,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            cost=cost,
        )
    )


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    if unit not in list(getattr(game.map, "units", []) or []):
        game.map.units.append(unit)


def _build_game():
    battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield)
    dg_army = Army.with_detachment("Death Guard", "Tallyband Summoners")
    dg_army.faction_id = "DG"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    dg_player = Player("DG", control=PlayerControl.LOCAL, army=dg_army)
    enemy_player = Player("EN", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(dg_player)
    game.add_player(enemy_player)
    dg_army.nurgles_gift.active_plague_key = PLAGUE_RATTLEJOINT.key
    return game, dg_player, enemy_player


def test_reverberant_rancidity_grants_plague_legions_contagion_source():
    game, dg_player, enemy_player = _build_game()
    dg_source = _make_unit(
        "Plague Marines",
        faction_name="Death Guard",
        keywords=["INFANTRY"],
        faction_keywords=["DEATH GUARD"],
    )
    plague_legions_source = _make_unit(
        "Plaguebearers",
        faction_name="Chaos Daemons",
        keywords=["INFANTRY", "PLAGUE LEGIONS"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )

    dg_player.army.add_unit(dg_source)
    dg_player.army.add_unit(plague_legions_source)
    enemy_player.army.add_unit(enemy)
    _deploy_unit(game, dg_source, 0.0, 0.0)
    _deploy_unit(game, plague_legions_source, 6.0, 0.0)
    _deploy_unit(game, enemy, 9.0, 0.0)
    game.turn = 1

    afflicted = NurglesGiftManager.get_afflicted_plague_for_unit(enemy, game=game, game_map=game.map)
    assert afflicted is not None
    assert str(afflicted.key or "").strip().upper() == PLAGUE_RATTLEJOINT.key

    mods = get_aura_attack_modifiers(dg_source, enemy, _StubWeaponProfile(), game_map=game.map)
    assert int(getattr(mods, "target_toughness_delta", 0) or 0) == -1


def test_reverberant_rancidity_adds_three_contagion_range_to_nearby_death_guard_units():
    game, dg_player, enemy_player = _build_game()
    dg_source = _make_unit(
        "Plague Marines",
        faction_name="Death Guard",
        keywords=["INFANTRY"],
        faction_keywords=["DEATH GUARD"],
    )
    plague_legions_anchor = _make_unit(
        "Nurglings",
        faction_name="Chaos Daemons",
        keywords=["INFANTRY", "PLAGUE LEGIONS"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )

    dg_player.army.add_unit(dg_source)
    dg_player.army.add_unit(plague_legions_anchor)
    enemy_player.army.add_unit(enemy)
    _deploy_unit(game, dg_source, 0.0, 0.0)
    _deploy_unit(game, plague_legions_anchor, -6.0, 0.0)
    _deploy_unit(game, enemy, 8.0, 0.0)
    game.turn = 2

    contagion_range = float(
        dg_player.army.nurgles_gift.get_contagion_range(
            2,
            source_unit=dg_source,
            game=game,
            game_map=game.map,
        )
    )
    assert contagion_range == 9.0

    afflicted = NurglesGiftManager.get_afflicted_plague_for_unit(enemy, game=game, game_map=game.map)
    assert afflicted is not None


def test_tallyband_summoners_rejects_plague_legions_points_above_battle_size_cap():
    army = Army.with_detachment("Death Guard", "Tallyband Summoners", points_limit=2000)
    army.faction_id = "DG"
    army.add_unit(
        _make_unit(
            "Plaguebearers A",
            faction_name="Chaos Daemons",
            keywords=["PLAGUE LEGIONS"],
            faction_keywords=["LEGIONES DAEMONICA"],
            cost=600,
        )
    )
    army.add_unit(
        _make_unit(
            "Plaguebearers B",
            faction_name="Chaos Daemons",
            keywords=["PLAGUE LEGIONS"],
            faction_keywords=["LEGIONES DAEMONICA"],
            cost=600,
        )
    )

    with pytest.raises(ArmyValidationError):
        army.validate_detachment_rules()


def test_tallyband_summoners_rejects_plague_legions_warlord():
    army = Army.with_detachment("Death Guard", "Tallyband Summoners", points_limit=2000)
    army.faction_id = "DG"
    warlord = _make_unit(
        "Great Unclean One",
        faction_name="Chaos Daemons",
        keywords=["MONSTER", "PLAGUE LEGIONS"],
        faction_keywords=["LEGIONES DAEMONICA"],
        cost=250,
    )
    army.add_unit(warlord)
    warlord.is_warlord = True
    army.warlord = warlord

    with pytest.raises(ArmyValidationError):
        army.validate_detachment_rules()


def test_tallyband_summoners_allows_valid_plague_legions_allies():
    army = Army.with_detachment("Death Guard", "Tallyband Summoners", points_limit=2000)
    army.faction_id = "DG"
    ally = _make_unit(
        "Plaguebearers",
        faction_name="Chaos Daemons",
        keywords=["PLAGUE LEGIONS"],
        faction_keywords=["LEGIONES DAEMONICA"],
        cost=500,
    )
    warlord = _make_unit(
        "Lord of Virulence",
        faction_name="Death Guard",
        keywords=["CHARACTER"],
        faction_keywords=["DEATH GUARD"],
        cost=120,
    )
    army.add_unit(ally)
    army.add_unit(warlord)
    warlord.is_warlord = True
    army.warlord = warlord

    army.validate_detachment_rules()
