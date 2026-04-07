from types import SimpleNamespace

from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
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
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "5",
                "T": "4",
                "Sv": "6",
                "W": "1",
                "Ld": "8",
                "OC": "1",
                "base_size": "25mm",
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
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
        )
    )


def _build_game(*, points_limit: int = 2000):
    battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield)

    dg_army = Army.with_detachment("Death Guard", "Shamblerot Vectorium", points_limit=points_limit)
    dg_army.faction_id = "DG"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    dg_player = Player("DG", control=PlayerControl.LOCAL, army=dg_army)
    enemy_player = Player("EN", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(dg_player)
    game.add_player(enemy_player)
    return game, dg_player


def test_shamblerot_vectorium_grants_battleline_to_poxwalkers_on_add_unit():
    _game, dg_player = _build_game()
    poxwalkers = _make_unit(
        "Poxwalkers",
        faction_name="Death Guard",
        keywords=["INFANTRY", "POXWALKERS"],
        faction_keywords=["DEATH GUARD"],
        model_count=10,
    )

    dg_player.army.add_unit(poxwalkers)

    keywords = [str(token or "").strip().lower() for token in list(getattr(poxwalkers, "keywords", []) or [])]
    assert "battleline" in keywords


def test_numberless_horde_spawns_poxwalkers_in_eligible_rounds_only():
    game, dg_player = _build_game(points_limit=2000)
    army = dg_player.army
    mgr = army.death_guard_detachments

    def _run_command_phase(round_number: int) -> None:
        game.turn = int(round_number)
        game.phase = SimpleNamespace(name="COMMAND_PHASE")
        mgr.on_command_phase_start(game=game, player=dg_player)

    _run_command_phase(1)
    assert len(list(getattr(army, "units", []) or [])) == 0

    _run_command_phase(2)
    assert len(list(getattr(army, "units", []) or [])) == 1

    _run_command_phase(2)
    assert len(list(getattr(army, "units", []) or [])) == 1

    _run_command_phase(3)
    _run_command_phase(4)
    assert len(list(getattr(army, "units", []) or [])) == 3

    _run_command_phase(5)
    assert len(list(getattr(army, "units", []) or [])) == 3

    spawned_units = [unit for unit in list(getattr(army, "units", []) or []) if bool(getattr(unit, "spawned_in_battle", False))]
    assert len(spawned_units) == 3
    for spawned in spawned_units:
        assert "poxwalker" in str(getattr(spawned, "name", "") or "").strip().lower()
        assert int(getattr(spawned, "starting_model_count", 0) or 0) == 10
        assert len(list(getattr(spawned, "models", []) or [])) == 10
        assert str(getattr(spawned, "reserve_status", "") or "").strip().lower() == "strategic_reserves"
        assert bool(getattr(spawned, "deployed", False))
        assert spawned not in list(getattr(game.map, "units", []) or [])
        keywords = [str(token or "").strip().lower() for token in list(getattr(spawned, "keywords", []) or [])]
        assert "battleline" in keywords
