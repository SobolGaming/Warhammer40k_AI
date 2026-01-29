import unittest
from unittest.mock import patch


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        abilities=None,
        keywords=None,
        faction_keywords=None,
        model_count=1,
        base_size="32mm",
    ):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{model_count} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{model_count} models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": "7",
                "OC": "1",
                "base_size": base_size,
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(name, *, abilities=None, keywords=None, faction_keywords=None, model_count=1):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        abilities=abilities,
        keywords=keywords,
        faction_keywords=faction_keywords,
        model_count=model_count,
    )
    return Unit(datasheet)


def _build_game():
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)

    army1 = Army("Aeldari", detachment_type="Battle Host")
    army1.faction_id = "AE"
    army2 = Army("Enemy", detachment_type="Other")
    army2.faction_id = "EN"

    p1 = Player("P1", control=PlayerControl.LOCAL, army=army1)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army2)
    game.add_player(p1)
    game.add_player(p2)
    return game, p1, p2, army1, army2


class _DummyWargear:
    def is_melee(self):
        return True


class _DummyProfile:
    def __init__(self):
        self.parent_wargear = _DummyWargear()

class _DummyRangedWargear:
    def is_melee(self):
        return False


class _DummyRangedProfile:
    def __init__(self):
        self.parent_wargear = _DummyRangedWargear()


class TestMeleeFightOnDeathAfterAttacks(unittest.TestCase):
    def test_malevolent_souls_defers_fight_on_death_on_3_plus(self):
        game, _p1, _p2, army1, _army2 = _build_game()
        abilities = [
            {
                "name": "Malevolent Souls",
                "description": (
                    "Each time a model in this unit is destroyed by a melee attack, if that model has not fought this "
                    "phase, roll one D6. On a 3+, do not remove it from play; that destroyed model can fight after "
                    "the attacking unit has finished making its attacks, and is then removed from play."
                ),
                "type": "Datasheet",
                "parameter": "",
            }
        ]
        unit = _make_unit("Wraithblades", abilities=abilities)
        army1.add_unit(unit)
        unit.deployed = True
        unit.round_state.fought_this_phase = False
        unit._last_destroyed_by_weapon_profile = _DummyProfile()
        model = unit.models[0]
        model._wounds = 0

        with patch("warhammer40k_ai.units.unit.get_roll", return_value=3):
            unit._handle_model_destroyed(model, game.map)

        pending = getattr(unit, "_melee_fight_on_death_pending_models", [])
        self.assertIn(model, pending)

        with patch.object(unit, "_try_fight_on_death") as mocked:
            unit.end_attack_resolution(game_map=game.map)
        self.assertEqual(mocked.call_count, 1)
        self.assertFalse(getattr(unit, "_melee_fight_on_death_pending_models", []))

    def test_malevolent_souls_roll_fails_no_queue(self):
        game, _p1, _p2, army1, _army2 = _build_game()
        abilities = [
            {
                "name": "Malevolent Souls",
                "description": (
                    "Each time a model in this unit is destroyed by a melee attack, if that model has not fought this "
                    "phase, roll one D6. On a 3+, do not remove it from play; that destroyed model can fight after "
                    "the attacking unit has finished making its attacks, and is then removed from play."
                ),
                "type": "Datasheet",
                "parameter": "",
            }
        ]
        unit = _make_unit("Wraithblades", abilities=abilities)
        army1.add_unit(unit)
        unit.deployed = True
        unit.round_state.fought_this_phase = False
        unit._last_destroyed_by_weapon_profile = _DummyProfile()
        model = unit.models[0]
        model._wounds = 0

        with patch("warhammer40k_ai.units.unit.get_roll", return_value=2):
            unit._handle_model_destroyed(model, game.map)

        self.assertFalse(getattr(unit, "_melee_fight_on_death_pending_models", []))
        with patch.object(unit, "_try_fight_on_death") as mocked:
            unit.end_attack_resolution(game_map=game.map)
        self.assertEqual(mocked.call_count, 0)

    def test_fight_on_death_after_attacks_on_2_plus(self):
        game, _p1, _p2, army1, _army2 = _build_game()
        abilities = [
            {
                "name": "Death Throes",
                "description": (
                    "If this model is destroyed by a melee attack, if it has not fought this phase, roll one D6. "
                    "On a 2+, do not remove it from play. This model can fight after the attacking unit has "
                    "finished making its attacks, and is then removed from play."
                ),
                "type": "Datasheet",
                "parameter": "",
            }
        ]
        unit = _make_unit("Champion", abilities=abilities)
        army1.add_unit(unit)
        unit.deployed = True
        unit.round_state.fought_this_phase = False
        unit._last_destroyed_by_weapon_profile = _DummyProfile()
        model = unit.models[0]
        model._wounds = 0

        with patch("warhammer40k_ai.units.unit.get_roll", return_value=2):
            unit._handle_model_destroyed(model, game.map)

        pending = getattr(unit, "_melee_fight_on_death_pending_models", [])
        self.assertIn(model, pending)

    def test_fight_on_death_after_attacks_requires_melee(self):
        game, _p1, _p2, army1, _army2 = _build_game()
        abilities = [
            {
                "name": "Death Throes",
                "description": (
                    "If this model is destroyed by a melee attack, if it has not fought this phase, roll one D6: "
                    "on a 2+, do not remove it from play. This model can fight after the attacking unit has "
                    "finished making its attacks, and is then removed from play."
                ),
                "type": "Datasheet",
                "parameter": "",
            }
        ]
        unit = _make_unit("Champion", abilities=abilities)
        army1.add_unit(unit)
        unit.deployed = True
        unit.round_state.fought_this_phase = False
        unit._last_destroyed_by_weapon_profile = _DummyRangedProfile()
        model = unit.models[0]
        model._wounds = 0

        with patch("warhammer40k_ai.units.unit.get_roll", return_value=6):
            unit._handle_model_destroyed(model, game.map)

        self.assertFalse(getattr(unit, "_melee_fight_on_death_pending_models", []))
