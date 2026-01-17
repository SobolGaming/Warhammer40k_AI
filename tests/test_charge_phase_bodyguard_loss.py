from types import SimpleNamespace


class _MockDatasheet:
    def __init__(self, name, datasheet_id, *, model_count=1, abilities=None, attached_to=None):
        self.name = name
        self.id = datasheet_id
        self.faction_data = {"name": "Test Faction"}
        self.keywords = []
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": f"{model_count} Test Models"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
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
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = list(attached_to or [])
        self.attached_to_names = []


def _make_unit(*, name, datasheet_id, model_count=1, abilities=None, attached_to=None):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        datasheet_id,
        model_count=model_count,
        abilities=abilities,
        attached_to=attached_to,
    )
    return Unit(datasheet)


class _MapStub:
    def get_enemy_units(self, _unit):
        return []

    def is_within_engagement_range(self, _unit, _enemy):
        return False


def test_charge_phase_bodyguard_loss_ai(monkeypatch):
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, BattleRoundPhases, Game
    from warhammer40k_ai.roster.player import Player, PlayerControl

    ability = {
        "name": "Battle Lust",
        "description": (
            "At the end of your Charge phase, if this model is leading a unit and that unit is not within "
            "Engagement Range of one or more enemy units, you must take a Leadership test for this model. "
            "If that test is failed, one Bodyguard model in that unit is destroyed."
        ),
        "type": "Datasheet",
        "parameter": "",
    }

    bodyguard = _make_unit(name="Jakhals", datasheet_id="bodyguard1", model_count=2)
    leader = _make_unit(
        name="Slaughterbound",
        datasheet_id="leader1",
        abilities=[ability],
        attached_to=["bodyguard1"],
    )

    army = Army("Test Faction", "Detachment")
    army.faction_id = "TF"
    army.add_unit(bodyguard)
    army.add_unit(leader)
    leader.attach_to_unit(bodyguard)

    bodyguard.deployed = True
    bodyguard.reserve_status = "deployed"
    leader.deployed = True
    leader.reserve_status = "deployed"

    player = Player("P1", control=PlayerControl.REMOTE, army=army)
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[player])
    game.map = _MapStub()

    monkeypatch.setattr("warhammer40k_ai.units.unit.get_roll", lambda _die: 12)
    player.set_next_optional_selection("CHARGE_PHASE_BODYGUARD_LOSS_MODEL", bodyguard.models[0])

    game.event_system.publish("phase_end", player=player, phase=BattleRoundPhases.CHARGE_PHASE)

    assert len(bodyguard.models) == 1
    assert len(leader.models) == 1


def test_charge_phase_bodyguard_loss_prompts_human(monkeypatch):
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, BattleRoundPhases, Game

    ability = {
        "name": "Battle Lust",
        "description": (
            "At the end of your Charge phase, if this model is leading a unit and that unit is not within "
            "Engagement Range of one or more enemy units, you must take a Leadership test for this model. "
            "If that test is failed, one Bodyguard model in that unit is destroyed."
        ),
        "type": "Datasheet",
        "parameter": "",
    }

    bodyguard = _make_unit(name="Jakhals", datasheet_id="bodyguard1", model_count=2)
    leader = _make_unit(
        name="Slaughterbound",
        datasheet_id="leader1",
        abilities=[ability],
        attached_to=["bodyguard1"],
    )

    army = Army("Test Faction", "Detachment")
    army.faction_id = "TF"
    army.add_unit(bodyguard)
    army.add_unit(leader)
    leader.attach_to_unit(bodyguard)

    bodyguard.deployed = True
    bodyguard.reserve_status = "deployed"
    leader.deployed = True
    leader.reserve_status = "deployed"

    player = SimpleNamespace(name="P1", control=SimpleNamespace(name="LOCAL"), has_control=lambda: True, army=army)
    army.player = player

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.players = [player]
    game.map = _MapStub()

    monkeypatch.setattr("warhammer40k_ai.units.unit.get_roll", lambda _die: 12)

    game.event_system.subscribe("charge_phase_bodyguard_loss_prompt", lambda **_k: None)

    published = {}
    original_publish = game.event_system.publish

    def _record_publish(event_name, **kwargs):
        if event_name == "charge_phase_bodyguard_loss_prompt":
            published["event"] = event_name
            published["kwargs"] = kwargs
        return original_publish(event_name, **kwargs)

    monkeypatch.setattr(game.event_system, "publish", _record_publish)

    game.event_system.publish("phase_end", player=player, phase=BattleRoundPhases.CHARGE_PHASE)

    assert published.get("event") == "charge_phase_bodyguard_loss_prompt"
    assert len(published["kwargs"]["candidates"]) == 2
    assert callable(published["kwargs"].get("on_select"))
