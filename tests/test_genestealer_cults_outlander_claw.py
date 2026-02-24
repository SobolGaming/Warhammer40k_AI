from __future__ import annotations

from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str,
        keywords: list[str] | None = None,
        faction_keywords: list[str] | None = None,
        points: int = 100,
        objective_control: int = 1,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": int(points)}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "4",
                "W": "2",
                "Ld": "7",
                "OC": str(int(objective_control)),
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


class _FakeObjective:
    def __init__(self, x: float, y: float):
        self._id = f"objective_{x}_{y}"
        self.location = self
        self.x = float(x)
        self.y = float(y)
        self.removed = False
        self.controlling_player = None
        self.sticky_controller = None
        self.sticky_source = None

    def update_control(self, _game) -> None:
        return None

    def set_sticky_control(self, player, source: str | None = None) -> None:
        self.sticky_controller = player
        self.sticky_source = source
        self.controlling_player = player


def _make_unit(
    name: str,
    *,
    faction_name: str,
    keywords: list[str] | None = None,
    faction_keywords: list[str] | None = None,
    points: int = 100,
    objective_control: int = 1,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            points=points,
            objective_control=objective_control,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _build_game() -> tuple[Game, Army, Army, Player, Player]:
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    gsc_army = Army("Genestealer Cults", "Outlander Claw", points_limit=2000)
    gsc_army.faction_id = "GC"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    p1 = Player("GSC", control=PlayerControl.REMOTE, army=gsc_army)
    p2 = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)
    return game, gsc_army, enemy_army, p1, p2


def test_rapid_takeover_objective_control_bonus_applies_to_mounted_and_vehicle_models():
    _game, gsc_army, _enemy_army, _gsc_player, _enemy_player = _build_game()

    jackals = _make_unit(
        "Atalan Jackals",
        faction_name="Genestealer Cults",
        keywords=["MOUNTED"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    truck = _make_unit(
        "Goliath Truck",
        faction_name="Genestealer Cults",
        keywords=["VEHICLE"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    infantry = _make_unit(
        "Neophyte Hybrids",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    gsc_army.add_unit(jackals)
    gsc_army.add_unit(truck)
    gsc_army.add_unit(infantry)

    assert int(jackals.models[0].objective_control or 0) == 2
    assert int(truck.models[0].objective_control or 0) == 2
    assert int(infantry.models[0].objective_control or 0) == 1

    jackals.is_battle_shocked = lambda: True
    assert int(jackals.models[0].objective_control or 0) == 1


def test_rapid_takeover_applies_sticky_objectives_for_atalan_jackals_on_command_phase_end():
    game, gsc_army, _enemy_army, gsc_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.turn = 2
    game.current_player_index = 0

    jackals = _make_unit(
        "Atalan Jackals",
        faction_name="Genestealer Cults",
        keywords=["MOUNTED"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    ridgerunners = _make_unit(
        "Achilles Ridgerunners",
        faction_name="Genestealer Cults",
        keywords=["MOUNTED"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    gsc_army.add_unit(jackals)
    gsc_army.add_unit(ridgerunners)

    game.map.objectives = [_FakeObjective(0.0, 0.0), _FakeObjective(10.0, 0.0)]
    objectives = list(getattr(game.map, "objectives", []) or [])
    primary_loc = getattr(objectives[0], "location", objectives[0])
    secondary_loc = getattr(objectives[1], "location", objectives[1])

    primary_loc.controlling_player = gsc_player
    secondary_loc.controlling_player = gsc_player

    jackals.is_within_objective_range = lambda loc: loc is primary_loc
    ridgerunners.is_within_objective_range = lambda _loc: False

    game._on_phase_end_cleanup(player=gsc_player, phase=BattleRoundPhases.COMMAND_PHASE)

    assert primary_loc.sticky_controller is gsc_player
    assert str(getattr(primary_loc, "sticky_source", "") or "") == "rapid_takeover"
    assert secondary_loc.sticky_controller is not gsc_player
