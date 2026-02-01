from types import SimpleNamespace


class _MockDatasheet:
    def __init__(self, name, *, unit_comp="1 Test Model", abilities=None, keywords=None):
        self.id = ""
        self.name = name
        self.faction_data = {"name": "Aeldari"}
        self.keywords = list(keywords or [])
        self.faction_keywords = ["AELDARI"]
        self.datasheets_unit_composition = [{"description": unit_comp}]
        self.datasheets_models_cost = [{"description": unit_comp, "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "3",
                "Sv": "5",
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


def _attach_leader(bodyguard, leader):
    leader.can_be_attached_to = ["INFANTRY"]
    leader.attached_to = bodyguard
    bodyguard.attached_leaders = [leader]


def test_choreographer_of_war_pile_in_rules():
    from warhammer40k_ai.utility.calcs import MovementType, get_validation_rules

    ability_text = (
        "While this model is leading a unit, each time that unit makes a pile-in or consolidation move, "
        "it can move up to 6\" instead of up to 3\", but must end as close as possible to the closest enemy unit."
    )
    bodyguard = _make_unit("Troupe", model_count=5)
    leader = _make_unit("Troupe Master", ability_desc=ability_text, model_count=1)
    _attach_leader(bodyguard, leader)

    pile_in_rules = get_validation_rules(MovementType.PILE_IN, moving_unit=bodyguard)
    assert pile_in_rules.get("max_distance_override") == 6.0
    assert pile_in_rules.get("must_end_as_close_as_possible_to_closest_enemy_unit") is True
    assert pile_in_rules.get("must_end_closer_to_enemies") is False

    consolidate_rules = get_validation_rules(MovementType.CONSOLIDATE, moving_unit=bodyguard)
    assert consolidate_rules.get("max_distance_override") == 6.0
    assert consolidate_rules.get("must_end_as_close_as_possible_to_closest_enemy_unit") is True
    assert consolidate_rules.get("must_end_closer_to_enemies_or_objectives") is False


def test_dance_of_death_hit_and_wound_bonuses():
    ability_text = (
        "While this model is leading a unit, at the start of the Fight phase, select one of the following performances."
    )
    bodyguard = _make_unit("Troupe", model_count=5)
    leader = _make_unit("Troupe Master", ability_desc=ability_text, ability_name="Dance of Death", model_count=1)
    _attach_leader(bodyguard, leader)

    assert bodyguard.has_dance_of_death()

    bodyguard.set_dance_of_death_choice("HERO", phase_name="FIGHT_PHASE")
    hit_mods = bodyguard.get_unit_hit_reroll_modifiers("melee")
    assert hit_mods.get("reroll_hit_ones") is True

    bodyguard.set_dance_of_death_choice("VILLAIN", phase_name="FIGHT_PHASE")
    wound_mods = bodyguard.get_unit_wound_reroll_modifiers("melee")
    assert wound_mods.get("wound") == 1


def test_dance_of_death_trickster_hit_penalty():
    ability_text = (
        "While this model is leading a unit, at the start of the Fight phase, select one of the following performances."
    )
    bodyguard = _make_unit("Troupe", model_count=5)
    leader = _make_unit("Troupe Master", ability_desc=ability_text, ability_name="Dance of Death", model_count=1)
    _attach_leader(bodyguard, leader)

    bodyguard.set_dance_of_death_choice("TRICKSTER", phase_name="FIGHT_PHASE")
    penalty, _reasons = bodyguard.get_target_hit_roll_penalty("melee")
    assert penalty == 1


def test_cruel_amusement_selection_grants_keyword():
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.engine.phase import BattleRoundPhases
    from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_CRUEL_AMUSEMENT
    from warhammer40k_ai.utility.decision_utils import resolve_decision_command

    ability = (
        "In your Shooting phase, each time this model is selected to shoot, select one of the abilities below. "
        "Until the end of the phase, this model's shrieker cannon has that ability."
    )
    unit = _make_unit("Death Jester", ability_desc=ability, model_count=1)
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

    game._on_shooting_targets_selected_cruel_amusement(attacking_unit=unit, target_units=[enemy])
    pending = list(game.decision_queue.list() or [])
    assert pending
    req = pending[0]
    assert req.decision_type == DECISION_CHOOSE_CRUEL_AMUSEMENT

    option_id = req.options[0].option_id
    resolve_decision_command(game, req, option_id, player_id=player.id)

    bonuses = unit.get_model_weapon_keyword_bonuses(
        model=unit.models[0],
        weapon_name="shrieker cannon",
        attack_type="ranged",
    )
    assert bonuses.get("ignores_cover") is True


def test_cry_of_the_wind_sets_temporary_crit():
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game

    ability = (
        "Each time this model is set up on the battlefield, until the end of the turn, "
        "each time this model makes a ranged attack, a successful unmodified Hit roll scores a Critical Hit."
    )
    unit = _make_unit("Skyweaver", ability_desc=ability, model_count=1)

    player = SimpleNamespace(name="P1", id="P1")
    enemy_player = SimpleNamespace(name="P2", id="P2")
    army = SimpleNamespace(player=player, units=[unit])
    enemy_army = SimpleNamespace(player=enemy_player, units=[])
    player.get_army = lambda: army
    enemy_player.get_army = lambda: enemy_army
    unit.set_parent_army(army)

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.players = [player, enemy_player]
    game.current_player_idx = 0
    game.turn = 1

    game._on_unit_set_up_cry_of_the_wind(unit=unit)
    assert unit.models[0].has_temporary_crit_on_successful_hit(game=game)


def test_cloudstrider_no_charge_and_min_distance():
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game

    unit = _make_unit("Baharroth", model_count=1)
    enemy = _make_unit("Enemy", model_count=1)

    player = SimpleNamespace(name="P1", id="P1")
    enemy_player = SimpleNamespace(name="P2", id="P2")
    army = SimpleNamespace(player=player, units=[unit])
    enemy_army = SimpleNamespace(player=enemy_player, units=[enemy])
    player.get_army = lambda: army
    enemy_player.get_army = lambda: enemy_army
    unit.set_parent_army(army)
    enemy.set_parent_army(enemy_army)

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.players = [player, enemy_player]
    game.current_player_idx = 0
    game.turn = 1

    unit.special_rules = {
        "cloudstrider_deep_strike_min_distance": 6.0,
        "cloudstrider_choice_turn": 1,
        "cloudstrider_choice_turn_owner": "P1",
        "cloudstrider_no_charge_turn": 1,
        "cloudstrider_no_charge_turn_owner": "P1",
    }

    assert unit.get_deep_strike_min_distance_override() == 6.0

    class _ChargeMap:
        def get_enemy_units(self, _unit):
            return [enemy]

        def get_distance_between_units(self, _a, _b):
            return 5.0

        def is_path_blocked(self, _a, _b):
            return False

        def is_within_engagement_range(self, _a, _b):
            return False

    game.map = _ChargeMap()
    assert unit.can_declare_charge_against(enemy, game) is False
