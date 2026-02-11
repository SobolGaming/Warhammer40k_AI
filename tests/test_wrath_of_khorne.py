from types import SimpleNamespace


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        faction_name="World Eaters",
        keywords=None,
        faction_keywords=None,
        cost=100,
    ):
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": cost}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "5",
                "W": "2",
                "Ld": "6",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.attached_to = []


def _make_model(name, *, keywords=None, faction_keywords=None):
    from warhammer40k_ai.units.model import Model
    from warhammer40k_ai.utility.model_base import Base, BaseType

    return Model(
        name=name,
        movement=6,
        toughness=4,
        save=5,
        wounds=2,
        leadership=6,
        objective_control=1,
        model_base=Base(BaseType.CIRCULAR, 1),
        keywords=list(keywords or []),
        faction_keywords=list(faction_keywords or []),
    )


def _make_unit(name, *, keywords=None, faction_keywords=None, model_names=None):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
    )
    unit = Unit(datasheet)
    unit.keywords = list(keywords or [])
    unit.faction_keywords = list(faction_keywords or [])
    unit.models = []
    for mname in list(model_names or [name]):
        model = _make_model(mname, keywords=keywords, faction_keywords=faction_keywords)
        model.set_parent_unit(unit)
        unit.models.append(model)
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _make_army():
    from warhammer40k_ai.roster.army import Army

    army = Army("World Eaters", "Vessels of Wrath")
    army.faction_id = "WE"
    return army


def test_wrath_of_khorne_candidates():
    army = _make_army()
    mgr = army.world_eaters_detachments

    character = _make_unit(
        "Chaos Lord",
        keywords=["CHARACTER"],
        faction_keywords=["WORLD EATERS"],
        model_names=["Chaos Lord"],
    )
    epic = _make_unit(
        "Angron",
        keywords=["CHARACTER", "Epic Hero"],
        faction_keywords=["WORLD EATERS"],
        model_names=["Angron"],
    )
    eightbound = _make_unit(
        "Eightbound",
        keywords=["EIGHTBOUND"],
        faction_keywords=["WORLD EATERS"],
        model_names=["Eightbound Champion", "Eightbound"],
    )
    random_unit = _make_unit(
        "Jakhals",
        keywords=["JAKHALS"],
        faction_keywords=["WORLD EATERS"],
        model_names=["Jakhal"],
    )

    army.add_unit(character)
    army.add_unit(epic)
    army.add_unit(eightbound)
    army.add_unit(random_unit)

    candidates = mgr.get_wrath_of_khorne_candidates()
    names = {m.name for m in candidates}
    assert "Chaos Lord" in names
    assert "Eightbound Champion" in names
    assert "Angron" not in names
    assert "Jakhal" not in names


def test_wrath_of_khorne_apply_models_and_blessing():
    army = _make_army()
    mgr = army.world_eaters_detachments
    bless_mgr = army.blessings_of_khorne

    character = _make_unit(
        "Chaos Lord",
        keywords=["CHARACTER"],
        faction_keywords=["WORLD EATERS"],
        model_names=["Chaos Lord"],
    )
    other = _make_unit(
        "Jakhals",
        keywords=["JAKHALS"],
        faction_keywords=["WORLD EATERS"],
        model_names=["Jakhal"],
    )
    army.add_unit(character)
    army.add_unit(other)

    model = character.models[0]
    model_id = str(getattr(model, "id", ""))
    assert mgr.apply_wrath_of_khorne_models([model_id], battle_round=1)
    assert any(str(k).lower() == "vessel of wrath" for k in (model.keywords or []))

    key = "UNBRIDLED_BLOODLUST"
    assert key not in bless_mgr.active_blessing_keys
    assert mgr.apply_wrath_of_khorne_blessing(key, battle_round=1)
    assert bless_mgr.is_blessing_active_for_unit(key, character, battle_round=1)
    assert not bless_mgr.is_blessing_active_for_unit(key, other, battle_round=1)


def test_wrath_of_khorne_model_limit_by_points():
    army = _make_army()
    mgr = army.world_eaters_detachments
    army.points_limit = 1000
    assert mgr.get_wrath_of_khorne_max_models() == 2
    army.points_limit = 2000
    assert mgr.get_wrath_of_khorne_max_models() == 3
    army.points_limit = 3000
    assert mgr.get_wrath_of_khorne_max_models() == 4


def test_reborn_in_blood_does_not_block_wrath_of_khorne_prompt():
    from warhammer40k_ai.engine.decision_kinds import DECISION_SELECT_VESSEL_OF_WRATH_MODELS
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.player import Player, PlayerControl
    from warhammer40k_ai.units.ability import Ability

    army = _make_army()
    player = Player("P1", control=PlayerControl.LOCAL, army=army)
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.add_player(player)

    candidate = _make_unit(
        "Chaos Lord",
        keywords=["CHARACTER"],
        faction_keywords=["WORLD EATERS"],
        model_names=["Chaos Lord"],
    )
    angron = _make_unit(
        "Angron",
        keywords=["CHARACTER", "Epic Hero"],
        faction_keywords=["WORLD EATERS"],
        model_names=["Angron"],
    )
    angron.possible_abilities = [Ability("Reborn in Blood", "WE", "Reborn in Blood", "Datasheet")]
    angron.models_lost = list(angron.models)
    angron.models = []

    army.add_unit(candidate)
    army.add_unit(angron)

    assert army.schedule_reborn_in_blood(game=game)
    queued = army.world_eaters_detachments.prompt_wrath_of_khorne_model_selection(
        game=game,
        player=player,
        battle_round=1,
        source="FAQ",
    )
    assert queued

    pending = list(game.decision_queue.list() or [])
    assert pending
    assert str(getattr(pending[0], "decision_type", "")) == DECISION_SELECT_VESSEL_OF_WRATH_MODELS
