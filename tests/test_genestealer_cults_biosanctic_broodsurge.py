import unittest
from types import SimpleNamespace


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        faction_name: str,
        keywords=None,
        faction_keywords=None,
        toughness: int = 4,
    ):
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": str(int(toughness)),
                "Sv": "4",
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
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(
    name: str,
    *,
    faction_name: str,
    faction_keywords=None,
    keywords=None,
    toughness: int = 4,
):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        faction_name=faction_name,
        faction_keywords=faction_keywords,
        keywords=keywords,
        toughness=toughness,
    )
    unit = Unit(datasheet)
    unit.deployed = True
    return unit


def _build_game(detachment_type: str = "Biosanctic Broodsurge"):
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    gsc_army = Army("Genestealer Cults", detachment_type)
    gsc_army.faction_id = "GC"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    gsc_player = Player("GSC", control=PlayerControl.LOCAL, army=gsc_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(gsc_player)
    game.add_player(enemy_player)
    return game, gsc_player, gsc_army, enemy_army


def _make_melee_profile():
    from warhammer40k_ai.units.wargear import WargearProfile

    parent = SimpleNamespace(name="Test Claw", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        profile_name="Melee",
        wargear_data={
            "range": "Melee",
            "A": "1",
            "BS_WS": "4+",
            "S": "5",
            "AP": "1",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


class TestGenestealerCultsBiosancticBroodsurge(unittest.TestCase):
    def test_hypermorphic_fury_adds_charge_bonus_for_eligible_unit_names(self):
        game, _gsc_player, gsc_army, enemy_army = _build_game("Biosanctic Broodsurge")
        attacker = _make_unit(
            "Aberrants",
            faction_name="Genestealer Cults",
            faction_keywords=["GENESTEALER CULTS"],
            keywords=["INFANTRY"],
        )
        target = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        gsc_army.add_unit(attacker)
        enemy_army.add_unit(target)

        modifiers = list(game.get_charge_roll_modifiers(attacker, target_unit=target))
        self.assertTrue(
            any(int(value or 0) == 1 and "hypermorphic fury" in str(source or "").lower() for value, source in modifiers)
        )

    def test_hypermorphic_fury_does_not_add_charge_bonus_for_other_units(self):
        game, _gsc_player, gsc_army, enemy_army = _build_game("Biosanctic Broodsurge")
        attacker = _make_unit(
            "Neophyte Hybrids",
            faction_name="Genestealer Cults",
            faction_keywords=["GENESTEALER CULTS"],
            keywords=["INFANTRY"],
        )
        target = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        gsc_army.add_unit(attacker)
        enemy_army.add_unit(target)

        modifiers = list(game.get_charge_roll_modifiers(attacker, target_unit=target))
        self.assertFalse(any("hypermorphic fury" in str(source or "").lower() for _value, source in modifiers))

    def test_hypermorphic_fury_applies_melee_attacks_bonus_when_selected_to_fight_after_charge(self):
        game, gsc_player, gsc_army, enemy_army = _build_game("Biosanctic Broodsurge")
        attacker = _make_unit(
            "Aberrants",
            faction_name="Genestealer Cults",
            faction_keywords=["GENESTEALER CULTS"],
            keywords=["INFANTRY"],
        )
        target = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        gsc_army.add_unit(attacker)
        enemy_army.add_unit(target)
        attacker.round_state.charged_this_round = True
        game.phase = SimpleNamespace(name="FIGHT_PHASE")

        game.event_system.publish("fight_unit_selected", unit=attacker, selecting_player=gsc_player)
        self.assertEqual(int(attacker.special_rules.get("hypermorphic_fury_melee_attacks_bonus", 0) or 0), 1)

        profile = _make_melee_profile()
        captured = []
        original_summary = profile._print_attack_summary
        profile._print_attack_summary = lambda result: captured.append(result)
        try:
            profile.attack(target, attacker.models[0], game_map=None)
        finally:
            profile._print_attack_summary = original_summary
        self.assertTrue(captured, "Expected attack summary to capture an AttackResult")
        attack_result = captured[0]
        self.assertEqual(int(attack_result.attacks_rolled), 2)
        self.assertTrue(any("Hypermorphic Fury" in entry for entry in list(attack_result.attacks_special_modifiers or [])))

    def test_hypermorphic_fury_cleans_up_at_end_of_fight_phase(self):
        game, gsc_player, gsc_army, _enemy_army = _build_game("Biosanctic Broodsurge")
        attacker = _make_unit(
            "Aberrants",
            faction_name="Genestealer Cults",
            faction_keywords=["GENESTEALER CULTS"],
            keywords=["INFANTRY"],
        )
        gsc_army.add_unit(attacker)
        attacker.round_state.charged_this_round = True
        game.phase = SimpleNamespace(name="FIGHT_PHASE")

        game.event_system.publish("fight_unit_selected", unit=attacker, selecting_player=gsc_player)
        self.assertIn("hypermorphic_fury_melee_attacks_bonus", attacker.special_rules)

        game.event_system.publish("phase_end", player=gsc_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
        self.assertNotIn("hypermorphic_fury_melee_attacks_bonus", attacker.special_rules)
        self.assertNotIn("hypermorphic_fury_source", attacker.special_rules)
        self.assertNotIn("hypermorphic_fury_expires_phase", attacker.special_rules)

    def test_hypermorphic_fury_handler_registered_for_fight_unit_selected(self):
        game, _gsc_player, _gsc_army, _enemy_army = _build_game("Biosanctic Broodsurge")
        callbacks = [cb for cb, _group in list(game.event_system.subscribers.get("fight_unit_selected", []) or [])]
        callback_names = {str(getattr(cb, "__name__", "") or "") for cb in callbacks}
        self.assertIn("_on_fight_unit_selected_hypermorphic_fury", callback_names)


if __name__ == "__main__":
    unittest.main()
