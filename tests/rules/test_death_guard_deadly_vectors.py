from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.nurgles_gift import PLAGUE_RATTLEJOINT
from warhammer40k_ai.units.unit import Unit


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str,
        faction_keywords=None,
        model_count: int = 1,
        wounds: int = 4,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = []
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "5",
                "T": "5",
                "Sv": "3",
                "W": str(int(wounds)),
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


def _make_unit(
    name: str,
    *,
    faction_name: str,
    faction_keywords,
    model_count: int = 1,
    wounds: int = 4,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
        )
    )


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    if unit not in game.map.units:
        game.map.units.append(unit)


def _build_game(detachment: str):
    battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield)

    dg_army = Army.with_detachment("Death Guard", detachment)
    dg_army.faction_id = "DG"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    dg_player = Player("DG", control=PlayerControl.LOCAL, army=dg_army)
    enemy_player = Player("EN", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(dg_player)
    game.add_player(enemy_player)

    dg_army.nurgles_gift.active_plague_key = PLAGUE_RATTLEJOINT.key
    return game, dg_player, enemy_player


def _publish_command_phase_start_for_enemy(game: Game, enemy_player: Player) -> None:
    game.phase = SimpleNamespace(name="COMMAND_PHASE")
    game.current_player_index = int(list(game.players).index(enemy_player))
    game.event_system.publish("phase_start", player=enemy_player, phase=game.phase)


def test_deadly_vectors_deals_mortal_wounds_to_afflicted_enemy_units():
    game, dg_player, enemy_player = _build_game("Death Lord's Chosen")
    dg_unit = _make_unit(
        "Plague Marines",
        faction_name="Death Guard",
        faction_keywords=["DEATH GUARD"],
    )
    afflicted_enemy = _make_unit(
        "Enemy Near",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
    )
    far_enemy = _make_unit(
        "Enemy Far",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
    )
    dg_player.army.add_unit(dg_unit)
    enemy_player.army.add_unit(afflicted_enemy)
    enemy_player.army.add_unit(far_enemy)
    _deploy_unit(game, dg_unit, 0.0, 0.0)
    _deploy_unit(game, afflicted_enemy, 2.0, 0.0)
    _deploy_unit(game, far_enemy, 20.0, 0.0)

    afflicted_model = afflicted_enemy.models[0]
    far_model = far_enemy.models[0]
    before_afflicted = int(getattr(afflicted_model, "wounds", 0))
    before_far = int(getattr(far_model, "wounds", 0))

    with patch("warhammer40k_ai.rules.death_guard_detachments.get_roll", side_effect=[5, 2]):
        _publish_command_phase_start_for_enemy(game, enemy_player)

    assert int(getattr(afflicted_model, "wounds", 0)) == before_afflicted - 2
    assert int(getattr(far_model, "wounds", 0)) == before_far


def test_deadly_vectors_applies_below_half_strength_modifier():
    game, dg_player, enemy_player = _build_game("Death Lord's Chosen")
    dg_unit = _make_unit(
        "Plague Marines",
        faction_name="Death Guard",
        faction_keywords=["DEATH GUARD"],
    )
    wounded_enemy = _make_unit(
        "Enemy Wounded",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
        wounds=6,
    )
    dg_player.army.add_unit(dg_unit)
    enemy_player.army.add_unit(wounded_enemy)
    _deploy_unit(game, dg_unit, 0.0, 0.0)
    _deploy_unit(game, wounded_enemy, 2.0, 0.0)
    wounded_enemy.models[0].wounds = 2

    with patch("warhammer40k_ai.rules.death_guard_detachments.get_roll", side_effect=[7, 1]):
        _publish_command_phase_start_for_enemy(game, enemy_player)

    assert int(getattr(wounded_enemy.models[0], "wounds", 0)) == 1


def test_deadly_vectors_not_active_outside_death_lords_chosen():
    game, dg_player, enemy_player = _build_game("Virulent Vectorium")
    dg_unit = _make_unit(
        "Plague Marines",
        faction_name="Death Guard",
        faction_keywords=["DEATH GUARD"],
    )
    enemy = _make_unit(
        "Enemy Near",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
    )
    dg_player.army.add_unit(dg_unit)
    enemy_player.army.add_unit(enemy)
    _deploy_unit(game, dg_unit, 0.0, 0.0)
    _deploy_unit(game, enemy, 2.0, 0.0)

    before = int(getattr(enemy.models[0], "wounds", 0))
    with patch("warhammer40k_ai.rules.death_guard_detachments.get_roll", side_effect=[5, 2]):
        _publish_command_phase_start_for_enemy(game, enemy_player)

    assert int(getattr(enemy.models[0], "wounds", 0)) == before
