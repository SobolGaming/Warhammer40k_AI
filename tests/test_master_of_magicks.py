from types import SimpleNamespace


class _MockDatasheet:
    def __init__(self, name, *, unit_comp="1 Test Model", abilities=None, keywords=None):
        self.id = ""
        self.name = name
        self.faction_data = {"name": "Chaos Daemons"}
        self.keywords = list(keywords or [])
        self.faction_keywords = ["CHAOS"]
        self.datasheets_unit_composition = [{"description": unit_comp}]
        self.datasheets_models_cost = [{"description": unit_comp, "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "8",
                "Sv": "4",
                "W": "16",
                "Ld": "7",
                "OC": "3",
                "base_size": "100mm",
                "inv_sv": "4",
                "inv_sv_descr": "4+",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: Bolt of Change; staff of Tzeentch."
        self.attached_to = []


def _make_unit(name, *, ability_desc=None, ability_name=None, model_count=1, keywords=None):
    from warhammer40k_ai.units.unit import Unit

    abilities = []
    if ability_desc:
        abilities.append(
            {
                "name": ability_name or name,
                "description": ability_desc,
                "type": "Datasheet",
                "parameter": "",
            }
        )
    datasheet = _MockDatasheet(name, unit_comp=f"{model_count} Test Models", abilities=abilities, keywords=keywords)
    return Unit(datasheet)


def test_master_of_magicks_selection_grants_keyword():
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.engine.phase import BattleRoundPhases
    from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_MASTER_OF_MAGICKS
    from warhammer40k_ai.utility.decision_utils import resolve_decision_command

    ability = (
        "In your Shooting phase, select one of the following abilities: [IGNORES COVER]; [LETHAL HITS]; [SUSTAINED HITS D3]. "
        "Until the end of the phase, this model’s Bolt of Change has that ability."
    )
    unit = _make_unit("Lord of Change", ability_desc=ability, ability_name="Master of Magicks (Psychic)", model_count=1)
    enemy = _make_unit("Enemy")

    player = SimpleNamespace(name="P1", id="P1", control=SimpleNamespace(name="LOCAL"), has_control=lambda: True)
    enemy_player = SimpleNamespace(name="P2", id="P2", control=SimpleNamespace(name="REMOTE"), has_control=lambda: False)
    army = SimpleNamespace(id="A1", player=player, units=[unit])
    enemy_army = SimpleNamespace(id="A2", player=enemy_player, units=[enemy])
    player.get_army = lambda: army
    enemy_player.get_army = lambda: enemy_army
    unit.set_parent_army(army)
    enemy.set_parent_army(enemy_army)

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.players = [player, enemy_player]
    game.current_player_idx = 0
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.rebuild_entity_registry()

    game._on_shooting_targets_selected_master_of_magicks(attacking_unit=unit, target_units=[enemy])
    pending = list(game.decision_queue.list() or [])
    assert pending
    req = pending[0]
    assert req.decision_type == DECISION_CHOOSE_MASTER_OF_MAGICKS

    option_id = req.options[0].option_id
    resolve_decision_command(game, req, option_id, player_id=player.id)

    bonuses = unit.get_model_weapon_keyword_bonuses(
        model=unit.models[0],
        weapon_name="Bolt of Change",
        attack_type="ranged",
    )
    assert bonuses.get("ignores_cover") is True
