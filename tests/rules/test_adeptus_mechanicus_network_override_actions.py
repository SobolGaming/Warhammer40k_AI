import unittest
from types import SimpleNamespace


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        datasheet_id: str,
        abilities=None,
        attached_to=None,
        attached_to_names=None,
        keywords=None,
        faction_keywords=None,
        composition: str = "1 Test Model",
        toughness: int = 4,
    ):
        self.name = name
        self.id = datasheet_id
        self.faction_data = {"name": "Adeptus Mechanicus"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or ["ADEPTUS MECHANICUS"])
        self.datasheets_unit_composition = [{"description": composition}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": str(int(toughness)),
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
        self.attached_to_names = list(attached_to_names or [])


def _ability(name: str, description: str) -> dict:
    return {
        "name": name,
        "description": description,
        "type": "Datasheet",
        "parameter": "",
    }


def _make_unit(
    name,
    *,
    datasheet_id: str,
    abilities=None,
    attached_to=None,
    attached_to_names=None,
    keywords=None,
    faction_keywords=None,
    composition: str = "1 Test Model",
    toughness: int = 4,
):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        datasheet_id=datasheet_id,
        abilities=abilities,
        attached_to=attached_to,
        attached_to_names=attached_to_names,
        keywords=keywords,
        faction_keywords=faction_keywords,
        composition=composition,
        toughness=toughness,
    )
    return Unit(datasheet)


def _build_game(detachment_type: str = "Data-psalm Conclave"):
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield)
    game.turn = 1

    army_adm = Army.with_detachment("Adeptus Mechanicus", detachment_type)
    army_adm.faction_id = "ADM"
    army_enemy = Army.with_detachment("Enemy", "Other")
    army_enemy.faction_id = "EN"

    p1 = Player("P1", control=PlayerControl.LOCAL, army=army_adm)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army_enemy)
    game.add_player(p1)
    game.add_player(p2)

    return game, army_adm, army_enemy


def _make_ranged_profile():
    from warhammer40k_ai.units.wargear import WargearProfile

    parent = SimpleNamespace(name="Arc Rifle", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        profile_name="Ranged",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


NETWORK_OVERRIDE_TEXT = (
    "While this unit contains one or more Tech-Priest models, this unit is: "
    "Eligible to perform an Action in a turn in which it Advanced. "
    "Eligible to shoot in a turn in which it started an Action."
)


class TestAdeptusMechanicusNetworkOverrideActions(unittest.TestCase):
    def _make_network_override_bodyguard(self):
        return _make_unit(
            "Kataphron Breachers",
            datasheet_id="BG1",
            abilities=[_ability("Network Override", NETWORK_OVERRIDE_TEXT)],
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS MECHANICUS"],
            composition="1 Servitor",
        )

    def _make_tech_priest_leader(self):
        return _make_unit(
            "Tech-Priest Enginseer",
            datasheet_id="L1",
            attached_to=["BG1"],
            attached_to_names=["Kataphron Breachers"],
            keywords=["INFANTRY", "CHARACTER", "TECH-PRIEST"],
            faction_keywords=["ADEPTUS MECHANICUS"],
            composition="1 Tech-Priest Enginseer",
        )

    def test_network_override_allows_action_after_advance_with_attached_tech_priest(self):
        game, army_adm, _army_enemy = _build_game()
        bodyguard = self._make_network_override_bodyguard()
        leader = self._make_tech_priest_leader()
        bodyguard.deployed = True
        leader.deployed = True
        army_adm.add_unit(bodyguard)
        army_adm.add_unit(leader)
        leader.attach_to_unit(bodyguard)

        bodyguard.round_state.advanced_this_round = True
        check = game._is_unit_eligible_to_start_action(bodyguard)
        self.assertTrue(bool(check.get("valid")))

    def test_network_override_does_not_allow_action_after_advance_without_tech_priest(self):
        game, army_adm, _army_enemy = _build_game()
        bodyguard = self._make_network_override_bodyguard()
        bodyguard.deployed = True
        army_adm.add_unit(bodyguard)

        bodyguard.round_state.advanced_this_round = True
        check = game._is_unit_eligible_to_start_action(bodyguard)
        self.assertFalse(bool(check.get("valid")))
        self.assertIn("advanced", str(check.get("reason", "")).lower())

    def test_network_override_allows_single_shoot_after_action_start(self):
        game, army_adm, army_enemy = _build_game()
        bodyguard = self._make_network_override_bodyguard()
        leader = self._make_tech_priest_leader()
        target = _make_unit(
            "Enemy Unit",
            datasheet_id="EN1",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            composition="1 Enemy Model",
        )
        bodyguard.deployed = True
        leader.deployed = True
        target.deployed = True
        army_adm.add_unit(bodyguard)
        army_adm.add_unit(leader)
        army_enemy.add_unit(target)
        leader.attach_to_unit(bodyguard)
        game.rebuild_entity_registry()

        bodyguard.round_state.action_locked_until_turn_end = True
        bodyguard.round_state.performing_action_name = "CLEANSE"
        bodyguard.round_state.action_started_turn = int(game.turn)
        bodyguard.round_state.shot_this_round = True
        bodyguard.round_state.action_permitted_shoot_used = False

        bodyguard.validate_ctan_power_selection = lambda *_args, **_kwargs: (True, "")
        call_counter = {"count": 0}

        def _reject_declaration(*_args, **_kwargs):
            call_counter["count"] += 1
            return {"valid": False, "reason": "intentional no-op for unit test"}

        bodyguard._validate_shooting_declaration = _reject_declaration
        profile = _make_ranged_profile()
        declarations = [
            {
                "weapon_profile": profile,
                "target_unit": target,
                "models": [bodyguard.models[0]],
            }
        ]

        result_first = bodyguard.execute_shooting_declarations(declarations, game.map)
        self.assertFalse(result_first)
        self.assertEqual(call_counter["count"], 1)
        self.assertTrue(bool(bodyguard.round_state.action_permitted_shoot_used))

        result_second = bodyguard.execute_shooting_declarations(declarations, game.map)
        self.assertFalse(result_second)
        self.assertEqual(call_counter["count"], 1)


if __name__ == "__main__":
    unittest.main()
