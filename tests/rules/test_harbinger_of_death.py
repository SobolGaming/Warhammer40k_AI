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
        self.loadout = "This model is equipped with: hellforged blade."
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


def test_harbinger_of_death_selection_grants_keyword():
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.engine.phase import BattleRoundPhases
    from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_HARBINGER_OF_DEATH
    from warhammer40k_ai.utility.decision_utils import resolve_decision_command

    ability = (
        "Each time this model is selected to fight, select one of the following abilities. "
        "Until the end of the phase, this model's hellforged weapons have that ability."
    )
    unit = _make_unit("Daemon Prince", ability_desc=ability, ability_name="Harbinger of Death", model_count=1)
    enemy = _make_unit("Enemy")
    unit.deployed = True
    unit.reserve_status = "deployed"

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
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.rebuild_entity_registry()

    game._on_fight_unit_selected_harbinger_of_death(unit=unit)
    pending = list(game.decision_queue.list() or [])
    assert pending
    req = pending[0]
    assert req.decision_type == DECISION_CHOOSE_HARBINGER_OF_DEATH

    option_id = req.options[0].option_id
    resolve_decision_command(game, req, option_id, player_id=player.id)

    bonuses = unit.get_model_weapon_keyword_bonuses(
        model=unit.models[0],
        weapon_name="Hellforged blade",
        attack_type="melee",
    )
    assert bonuses.get("lethal_hits") is True
