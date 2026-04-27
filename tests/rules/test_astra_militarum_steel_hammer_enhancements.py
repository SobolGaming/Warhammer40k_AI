from types import SimpleNamespace

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.rules.voice_of_command import ORDER_MOVE, VoiceOfCommandManager
from warhammer40k_ai.units.unit import Unit


class _Datasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        abilities=None,
        wounds: int = 6,
    ):
        self.id = f"ds-{name.lower().replace(' ', '-')}"
        self.name = name
        self.faction_data = {"name": "Astra Militarum"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or ["ASTRA MILITARUM"])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "10",
                "T": "11",
                "Sv": "3",
                "W": str(wounds),
                "Ld": "6",
                "OC": "5",
                "base_size": "170mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = [
            {
                "name": getattr(ability, "name", ""),
                "description": getattr(ability, "description", ""),
                "type": "Datasheet",
                "parameter": "",
            }
            for ability in list(abilities or [])
        ]
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _ability(name: str, description: str = ""):
    return SimpleNamespace(name=name, description=description or name)


def _make_unit(
    name: str,
    *,
    keywords=None,
    faction_keywords=None,
    abilities=None,
    wounds: int = 6,
) -> Unit:
    unit = Unit(
        _Datasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            abilities=abilities,
            wounds=wounds,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game(detachment_type: str = "Steel Hammer"):
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1
    am_army = Army.with_detachment("Astra Militarum", detachment_type=detachment_type)
    am_army.faction_id = "AM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "ENEMY"
    am_player = Player("Astra Militarum", control=PlayerControl.REMOTE, army=am_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(am_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    return game, am_army, enemy_army


def _place_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    if unit not in game.map.units:
        game.map.units.append(unit)


def _battalion_commander() -> Enhancement:
    return Enhancement(
        id="000010787002",
        name="Battalion Commander",
        faction_id="AM",
        detachment="Steel Hammer",
        points=20,
        description=(
            "Astra Militarum Titanic Character model only. The bearer has the Voice of Command ability "
            "and the Officer keyword, and can issue up to 2 Orders to Astra Militarum Titanic and Squadron units."
        ),
    )


def test_battalion_commander_descriptor_exists():
    desc = get_enhancement_tool_descriptor(enhancement_id="000010787002")

    assert desc is not None
    assert desc.name == "Battalion Commander"
    assert desc.effect == "grant_voice_of_command_and_officer"
    assert desc.effect_params["order_count"] == 2


def test_battalion_commander_grants_voice_and_two_titanic_or_squadron_orders():
    game, army, _enemy_army = _build_game()
    commander = _make_unit("Baneblade Commander", keywords=["VEHICLE", "TITANIC", "CHARACTER"], wounds=24)
    titanic_target = _make_unit("Stormsword", keywords=["VEHICLE", "TITANIC"], wounds=24)
    squadron_target = _make_unit("Scout Sentinel", keywords=["VEHICLE", "SQUADRON"], wounds=7)
    regiment_target = _make_unit("Infantry Squad", keywords=["INFANTRY", "REGIMENT"], wounds=1)
    non_am_squadron = _make_unit(
        "Allied Speeder",
        keywords=["VEHICLE", "SQUADRON"],
        faction_keywords=["ADEPTUS ASTARTES"],
        wounds=7,
    )

    for unit in (commander, titanic_target, squadron_target, regiment_target, non_am_squadron):
        army.add_unit(unit)
    _battalion_commander().apply_to_unit(commander)

    _place_unit(game, commander, 10.0, 10.0)
    _place_unit(game, titanic_target, 14.0, 10.0)
    _place_unit(game, squadron_target, 15.0, 10.0)
    _place_unit(game, regiment_target, 12.0, 10.0)
    _place_unit(game, non_am_squadron, 13.0, 10.0)
    game.rebuild_entity_registry()

    manager = VoiceOfCommandManager(army)
    manager._army_has_voice = lambda: True
    army.voice_of_command = manager

    assert commander.has_any_keyword("OFFICER")
    assert commander in manager.get_eligible_officers(game=game, player=army.player)

    targets = manager.get_eligible_targets(commander, game=game, order_key=ORDER_MOVE.key)
    assert titanic_target in targets
    assert squadron_target in targets
    assert regiment_target not in targets
    assert non_am_squadron not in targets

    assert manager.issue_order(game, commander, titanic_target, ORDER_MOVE.key, phase_name="COMMAND_PHASE")
    assert manager.issue_order(game, commander, squadron_target, ORDER_MOVE.key, phase_name="COMMAND_PHASE")
    assert manager.orders_remaining(commander, 1) == 0
    assert not manager.issue_order(game, commander, regiment_target, ORDER_MOVE.key, phase_name="COMMAND_PHASE")


def test_battalion_commander_is_detachment_and_character_gated():
    game, army, _enemy_army = _build_game(detachment_type="Combined Arms")
    commander = _make_unit("Baneblade Commander", keywords=["VEHICLE", "TITANIC", "CHARACTER"], wounds=24)
    army.add_unit(commander)
    _battalion_commander().apply_to_unit(commander)
    _place_unit(game, commander, 10.0, 10.0)
    game.rebuild_entity_registry()

    manager = VoiceOfCommandManager(army)
    manager._army_has_voice = lambda: True
    army.voice_of_command = manager

    assert not commander.has_any_keyword("OFFICER")
    assert commander not in manager.get_eligible_officers(game=game, player=army.player)

    steel_game, steel_army, _ = _build_game(detachment_type="Steel Hammer")
    non_character = _make_unit("Baneblade", keywords=["VEHICLE", "TITANIC"], wounds=24)
    steel_army.add_unit(non_character)
    _battalion_commander().apply_to_unit(non_character)
    _place_unit(steel_game, non_character, 10.0, 10.0)
    steel_game.rebuild_entity_registry()

    steel_manager = VoiceOfCommandManager(steel_army)
    steel_manager._army_has_voice = lambda: True
    steel_army.voice_of_command = steel_manager

    assert non_character.has_any_keyword("OFFICER")
    assert non_character not in steel_manager.get_eligible_officers(game=steel_game, player=steel_army.player)
