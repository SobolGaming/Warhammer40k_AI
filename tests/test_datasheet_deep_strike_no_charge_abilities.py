from types import SimpleNamespace


class _MockDatasheet:
    def __init__(self, name, *, abilities=None, keywords=None, faction_keywords=None):
        self.id = ""
        self.name = name
        self.faction_data = {"name": "Agents of the Imperium"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "4",
                "W": "4",
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
        self.attached_to = []


def _make_unit(name, *, ability_name=None, ability_desc=None):
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
    datasheet = _MockDatasheet(
        name,
        abilities=abilities,
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["AGENTS OF THE IMPERIUM"],
    )
    return Unit(datasheet)


def test_etheric_emergence_is_detected_for_deep_strike_no_charge_override():
    ability_desc = (
        "In your Movement phase, when this model is set up on the battlefield using the Deep Strike ability, it can perform "
        "an etheric emergence. If it does, this model can be set up anywhere on the battlefield that is more than 6\" "
        "horizontally away from all enemy units, but until the end of the turn, it is not eligible to declare a charge."
    )
    unit = _make_unit(
        "Culexus Assassin",
        ability_name="Etheric Emergence",
        ability_desc=ability_desc,
    )
    source = unit.get_cloudstrider_deep_strike_source()
    assert "etheric emergence" in str(source or "").lower()
    rule = unit.get_cloudstrider_deep_strike_rule()
    assert isinstance(rule, dict)
    assert float(rule.get("deep_strike_min_distance", 0.0) or 0.0) == 6.0


def test_etheric_emergence_override_applies_six_inch_setup_and_no_charge_same_turn():
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game

    unit = _make_unit("Culexus Assassin")
    enemy = _make_unit("Enemy Unit")

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


def test_meteoric_descent_three_inch_variant_is_detected():
    ability_desc = (
        "In your Movement phase, when this unit is set up on the battlefield using the Deep Strike ability, it can "
        "perform a meteoric descent. If it does, this unit can be set up anywhere on the battlefield that is more "
        "than 3\" horizontally away from all enemy units, but until the end of the turn, it is not eligible to "
        "declare a charge."
    )
    unit = _make_unit(
        "Meteor Unit",
        ability_name="Meteoric Descent",
        ability_desc=ability_desc,
    )
    source = unit.get_cloudstrider_deep_strike_source()
    assert "meteoric descent" in str(source or "").lower()
    rule = unit.get_cloudstrider_deep_strike_rule()
    assert isinstance(rule, dict)
    assert float(rule.get("deep_strike_min_distance", 0.0) or 0.0) == 3.0
