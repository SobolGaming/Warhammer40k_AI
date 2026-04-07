from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        objective_control: int = 1,
        movement: int = 6,
        toughness: int = 4,
        save: int = 4,
        wounds: int = 5,
        model_count: int = 1,
        keywords=None,
        faction_name: str = "Chaos Daemons",
    ):
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": f"{model_count} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{model_count} models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": str(movement),
                "T": str(toughness),
                "Sv": str(save),
                "W": str(wounds),
                "Ld": "7",
                "OC": str(objective_control),
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


def _make_unit(name: str, army: Army, *, objective_control: int = 1, wounds: int = 5, faction_name: str = "Chaos Daemons") -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            objective_control=objective_control,
            wounds=wounds,
            faction_name=faction_name,
        )
    )
    unit.deployed = True
    army.add_unit(unit)
    return unit


def _build_game():
    game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE))

    shadow_army = Army.with_detachment("Chaos Daemons", detachment_type="Shadow Legion")
    shadow_army.faction_id = "CD"
    enemy_army = Army.with_detachment("Enemies", detachment_type="Other")
    enemy_army.faction_id = "SM"

    shadow_player = Player("Shadow", PlayerControl.LOCAL, shadow_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, enemy_army)
    game.add_player(shadow_player)
    game.add_player(enemy_player)

    return game, shadow_player, enemy_player


def test_shadow_legion_enhancement_descriptors_registered():
    ids_to_names = {
        "000009980002": "Leaping Shadows",
        "000009980003": "Mantle of Gloom (Aura)",
        "000009980004": "Fade to Darkness",
        "000009980005": "Malice Made Manifest",
    }
    for enh_id, expected_name in ids_to_names.items():
        desc = get_enhancement_tool_descriptor(enhancement_id=enh_id)
        assert desc is not None
        assert str(desc.name) == expected_name


def test_leaping_shadows_grants_scouts_9():
    army = Army.with_detachment("Chaos Daemons", detachment_type="Shadow Legion")
    army.faction_id = "CD"
    bearer = _make_unit("Bearer", army)

    Enhancement(
        id="000009980002",
        name="Leaping Shadows",
        faction_id="CD",
        detachment="Shadow Legion",
    ).apply_to_unit(bearer)

    has_scout, distance = bearer.has_scout()
    assert has_scout is True
    assert float(distance) == 9.0


def test_mantle_of_gloom_reduces_enemy_objective_control_when_engaged():
    game, shadow_player, enemy_player = _build_game()
    bearer = _make_unit("Bearer", shadow_player.army)
    target = _make_unit("Enemy Target", enemy_player.army, objective_control=2, faction_name="Enemies")

    Enhancement(
        id="000009980003",
        name="Mantle of Gloom (Aura)",
        faction_id="CD",
        detachment="Shadow Legion",
    ).apply_to_unit(bearer)

    bearer.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    target.models[0].set_location(8.0, 0.0, 0.0, 0.0)
    game.map.units = [bearer, target]
    game.rebuild_entity_registry()

    baseline_oc = int(target.get_effective_model_characteristic(target.models[0], "objective_control", game_map=game.map))
    assert baseline_oc == 2

    bearer.models[0].set_location(7.0, 0.0, 0.0, 0.0)
    reduced_oc = int(target.get_effective_model_characteristic(target.models[0], "objective_control", game_map=game.map))
    assert reduced_oc == 1


def test_fade_to_darkness_registers_fight_phase_strategic_reserves_ability():
    army = Army.with_detachment("Chaos Daemons", detachment_type="Shadow Legion")
    army.faction_id = "CD"
    bearer = _make_unit("Bearer", army)

    Enhancement(
        id="000009980004",
        name="Fade to Darkness",
        faction_id="CD",
        detachment="Shadow Legion",
    ).apply_to_unit(bearer)

    ability = bearer.get_end_of_fight_phase_destroyed_strategic_reserves_ability()
    assert isinstance(ability, dict)
    assert str(ability.get("ability_key", "")) == "fight_phase_destroyed_strategic_reserves"
    assert str(ability.get("name", "")) == "Fade to Darkness"


def test_malice_made_manifest_queues_target_selection_at_fight_phase_start():
    game, shadow_player, enemy_player = _build_game()
    bearer = _make_unit("Bearer", shadow_player.army, wounds=6)
    target = _make_unit("Enemy Target", enemy_player.army, faction_name="Enemies", wounds=6)

    Enhancement(
        id="000009980005",
        name="Malice Made Manifest",
        faction_id="CD",
        detachment="Shadow Legion",
    ).apply_to_unit(bearer)

    bearer.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    target.models[0].set_location(0.5, 0.0, 0.0, 0.0)
    game.map.units = [bearer, target]
    game.rebuild_entity_registry()

    game._on_phase_start_malice_made_manifest(player=shadow_player, phase=BattleRoundPhases.FIGHT_PHASE)
    requests = list(game.decision_queue.list() or [])
    assert len(requests) == 1
    request = requests[0]
    assert str(request.decision_type) == DECISION_CHOOSE_QUARRY
    assert str((request.context or {}).get("ability", "")) == "malice_made_manifest"


def test_malice_made_manifest_does_not_queue_when_no_engaged_enemy():
    game, shadow_player, enemy_player = _build_game()
    bearer = _make_unit("Bearer", shadow_player.army, wounds=6)
    target = _make_unit("Enemy Target", enemy_player.army, faction_name="Enemies", wounds=6)

    Enhancement(
        id="000009980005",
        name="Malice Made Manifest",
        faction_id="CD",
        detachment="Shadow Legion",
    ).apply_to_unit(bearer)

    bearer.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    target.models[0].set_location(20.0, 0.0, 0.0, 0.0)
    game.map.units = [bearer, target]
    game.rebuild_entity_registry()

    game._on_phase_start_malice_made_manifest(player=shadow_player, phase=BattleRoundPhases.FIGHT_PHASE)
    assert list(game.decision_queue.list() or []) == []


def test_malice_made_manifest_applies_mortal_wounds_table():
    game, shadow_player, enemy_player = _build_game()
    bearer = _make_unit("Bearer", shadow_player.army, wounds=6)
    target = _make_unit("Enemy Target", enemy_player.army, faction_name="Enemies", wounds=6)

    Enhancement(
        id="000009980005",
        name="Malice Made Manifest",
        faction_id="CD",
        detachment="Shadow Legion",
    ).apply_to_unit(bearer)

    bearer.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    target.models[0].set_location(0.5, 0.0, 0.0, 0.0)
    game.map.units = [bearer, target]
    game.rebuild_entity_registry()

    game._on_phase_start_malice_made_manifest(player=shadow_player, phase=BattleRoundPhases.FIGHT_PHASE)
    request = list(game.decision_queue.list() or [])[0]
    option_id = request.options[0].option_id

    target_model = target.models[0]
    starting_wounds = int(target_model.wounds)
    with patch("warhammer40k_ai.utility.dice.get_roll", side_effect=[5, 2]):
        resolve_decision_command(game, request, option_id, player_id=shadow_player.id)

    assert int(target_model.wounds) == starting_wounds - 2
