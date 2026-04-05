from unittest.mock import patch


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        datasheet_id: str,
        unit_comp: str,
        wounds: str = "4",
        abilities=None,
        attached_to=None,
    ):
        self.id = str(datasheet_id)
        self.name = name
        self.faction_data = {"name": "Chaos Space Marines"}
        self.keywords = []
        self.faction_keywords = ["HERETIC ASTARTES"]
        self.datasheets_unit_composition = [{"description": unit_comp}]
        self.datasheets_models_cost = [{"description": unit_comp, "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": str(wounds),
                "Ld": "6",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.attached_to = list(attached_to or [])
        self.attached_to_names = []
        self.transport = ""


def _make_unit_from_datasheet(datasheet):
    from warhammer40k_ai.units.unit import Unit

    return Unit(datasheet)


def test_chirurgeon_returns_model_and_reattaches_to_bodyguard():
    from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    chirurgeon_text = (
        "The first time this unit's FABIUS BILE model is destroyed, at the end of the phase, roll one D6: "
        "on a 2+, set that model back up on the battlefield with its full wounds remaining. If this unit is "
        "attached to a unit when that model is destroyed, this model must be set back up attached to that unit."
    )

    leader_ds = _MockDatasheet(
        "Fabius Bile",
        datasheet_id="CSM_LEADER",
        unit_comp="1 Fabius Bile",
        wounds="5",
        abilities=[{"name": "Chirurgeon", "description": chirurgeon_text, "type": "Datasheet", "parameter": ""}],
        attached_to=["CSM_BODYGUARD"],
    )
    bodyguard_ds = _MockDatasheet(
        "Chosen",
        datasheet_id="CSM_BODYGUARD",
        unit_comp="1 Chosen",
        wounds="2",
    )

    leader = _make_unit_from_datasheet(leader_ds)
    bodyguard = _make_unit_from_datasheet(bodyguard_ds)

    battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield)
    army = Army("CSM", "Chaos")
    enemy_army = Army("Enemy", "Enemy")
    player = Player("P1", PlayerControl.LOCAL, army)
    enemy = Player("P2", PlayerControl.LOCAL, enemy_army)
    game.add_player(player)
    game.add_player(enemy)

    leader.set_parent_army(army)
    bodyguard.set_parent_army(army)
    leader.attach_to_unit(bodyguard)

    army.add_unit(bodyguard)
    army.add_unit(leader)
    bodyguard.deployed = True
    leader.deployed = True
    bodyguard.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    leader.models[0].set_location(10.2, 10.0, 0.0, 0.0)
    game.map.units = [bodyguard, leader]
    game.phase = BattleRoundPhases.SHOOTING_PHASE

    leader.models[0].take_damage(5, game_map=game.map)
    assert len(leader.models) == 0
    assert leader.attached_to is None
    assert game._phoenix_gem_pending

    with patch("warhammer40k_ai.engine.game.get_roll", return_value=2):
        game._on_phase_end_cleanup(player=player, phase=game.phase)

    assert len(leader.models) == 1
    assert int(leader.models[0].wounds) == 5
    assert leader.attached_to is bodyguard
    assert leader in list(getattr(bodyguard, "attached_leaders", []) or [])
