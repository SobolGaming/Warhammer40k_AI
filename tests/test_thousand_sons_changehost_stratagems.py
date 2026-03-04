from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        toughness: str = "4",
        wounds: str = "3",
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": "Thousand Sons"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": str(toughness),
                "Sv": "3",
                "W": str(wounds),
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
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
    keywords=None,
    faction_keywords=None,
    toughness: str = "4",
    wounds: str = "3",
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            toughness=toughness,
            wounds=wounds,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    ts_army = Army("Thousand Sons", "Changehost of Deceit")
    ts_army.faction_id = "TS"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    ts_player = Player("TS", control=PlayerControl.LOCAL, army=ts_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ts_player)
    game.add_player(enemy_player)

    ts_player.command_points = 10
    enemy_player.command_points = 10
    ts_army.configure_rule_managers(force=True)
    ts_player.stratagems.refresh_available()
    game.rebuild_entity_registry()
    return game, ts_player, enemy_player, ts_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    game.phase = SimpleNamespace(name=phase_name)
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=game.phase)


def _pending_by_name(stratagems, name: str):
    name_u = str(name or "").strip().upper()
    return [
        r for r in list(stratagems.get_pending_reactions() or [])
        if str(r.get("stratagem", "") or "").strip().upper() == name_u
    ]


def test_glimmershift_portal_queues_at_end_of_opponent_fight_phase():
    game, ts_player, enemy_player, ts_army, enemy_army = _build_game()
    non_monster_a = _make_unit(
        "Pink Horrors A",
        keywords=["INFANTRY", "SCINTILLATING LEGIONS"],
        faction_keywords=["SCINTILLATING LEGIONS"],
    )
    non_monster_b = _make_unit(
        "Pink Horrors B",
        keywords=["INFANTRY", "SCINTILLATING LEGIONS"],
        faction_keywords=["SCINTILLATING LEGIONS"],
    )
    monster = _make_unit(
        "Kairos Fateweaver",
        keywords=["MONSTER", "SCINTILLATING LEGIONS"],
        faction_keywords=["SCINTILLATING LEGIONS"],
    )
    too_close = _make_unit(
        "Flamers Too Close",
        keywords=["INFANTRY", "SCINTILLATING LEGIONS"],
        faction_keywords=["SCINTILLATING LEGIONS"],
    )
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])

    ts_army.add_unit(non_monster_a)
    ts_army.add_unit(non_monster_b)
    ts_army.add_unit(monster)
    ts_army.add_unit(too_close)
    enemy_army.add_unit(enemy)

    _deploy_unit(game, non_monster_a, 4.0, 4.0)
    _deploy_unit(game, non_monster_b, 8.0, 4.0)
    _deploy_unit(game, monster, 12.0, 4.0)
    _deploy_unit(game, too_close, 25.0, 20.0)
    _deploy_unit(game, enemy, 20.0, 20.0)

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish("phase_end", player=enemy_player, phase=game.phase)

    pending = _pending_by_name(ts_player.stratagems, "GLIMMERSHIFT PORTAL")
    assert len(pending) == 1
    candidates = list(pending[0].get("candidates") or [])
    assert non_monster_a in candidates
    assert non_monster_b in candidates
    assert monster in candidates
    assert too_close not in candidates
    assert int(pending[0].get("max_units", 0) or 0) == 2


def test_glimmershift_portal_moves_two_non_monster_units_into_strategic_reserves():
    game, ts_player, enemy_player, ts_army, enemy_army = _build_game()
    non_monster_a = _make_unit(
        "Pink Horrors A",
        keywords=["INFANTRY", "SCINTILLATING LEGIONS"],
        faction_keywords=["SCINTILLATING LEGIONS"],
    )
    non_monster_b = _make_unit(
        "Pink Horrors B",
        keywords=["INFANTRY", "SCINTILLATING LEGIONS"],
        faction_keywords=["SCINTILLATING LEGIONS"],
    )
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    ts_army.add_unit(non_monster_a)
    ts_army.add_unit(non_monster_b)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, non_monster_a, 4.0, 4.0)
    _deploy_unit(game, non_monster_b, 10.0, 4.0)
    _deploy_unit(game, enemy, 20.0, 20.0)

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    ok = ts_player.stratagems.use(
        "GLIMMERSHIFT PORTAL",
        units=[non_monster_a, non_monster_b],
        candidates=[non_monster_a, non_monster_b],
        max_units=2,
        phase_name="Fight phase",
    )
    assert ok
    assert int(ts_player.command_points or 0) == 9
    assert non_monster_a.is_in_reserves()
    assert non_monster_b.is_in_reserves()


def test_glimmershift_portal_rejects_mixed_monster_and_non_monster_selection():
    game, ts_player, enemy_player, ts_army, enemy_army = _build_game()
    non_monster = _make_unit(
        "Pink Horrors",
        keywords=["INFANTRY", "SCINTILLATING LEGIONS"],
        faction_keywords=["SCINTILLATING LEGIONS"],
    )
    monster = _make_unit(
        "Kairos Fateweaver",
        keywords=["MONSTER", "SCINTILLATING LEGIONS"],
        faction_keywords=["SCINTILLATING LEGIONS"],
    )
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    ts_army.add_unit(non_monster)
    ts_army.add_unit(monster)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, non_monster, 4.0, 4.0)
    _deploy_unit(game, monster, 10.0, 4.0)
    _deploy_unit(game, enemy, 20.0, 20.0)

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    blocked = ts_player.stratagems.use(
        "GLIMMERSHIFT PORTAL",
        units=[non_monster, monster],
        candidates=[non_monster, monster],
        max_units=2,
        phase_name="Fight phase",
    )
    assert not blocked
    assert int(ts_player.command_points or 0) == 10


def test_changehost_glimmershift_portal_descriptor_registered():
    by_id = get_stratagem_tool_descriptor(stratagem_id="000010198007")
    assert by_id is not None
    assert by_id.name == "Glimmershift Portal"
    assert by_id.effect == "enter_strategic_reserves"
    assert int(by_id.effect_params.get("max_units", 0) or 0) == 2
    assert float(by_id.effect_params.get("min_enemy_horizontal_distance", 0.0) or 0.0) == 6.0

    by_name = get_stratagem_tool_descriptor(name="GLIMMERSHIFT PORTAL")
    assert by_name is not None
    assert by_name.stratagem_id == "000010198007"
