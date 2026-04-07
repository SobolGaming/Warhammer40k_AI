import unittest

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Space Marines",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        wounds: int = 4,
        attached_to=None,
        abilities=None,
    ):
        self.id = ""
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            faction_keywords = ["ADEPTUS ASTARTES"] if faction_name == "Space Marines" else [str(faction_name).upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": str(int(wounds)),
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
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Space Marines",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: int = 4,
    attached_to=None,
    abilities=None,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
            attached_to=attached_to,
            abilities=abilities,
        )
    )


def _build_game(detachment_type: str = "Vindication Task Force"):
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    sm_army = Army.with_detachment("Space Marines", detachment_type)
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", control=PlayerControl.REMOTE, army=sm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    return game, sm_army, enemy_army


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str) -> None:
    Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="SM",
        detachment="Vindication Task Force",
        points=15,
        description="",
    ).apply_to_unit(unit)


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    bodyguard.attached_leaders = [leader]
    leader.attached_to = bodyguard
    for unit in (bodyguard, leader):
        invalidate_cache = getattr(unit, "_invalidate_ability_cache", None)
        if callable(invalidate_cache):
            invalidate_cache()


class TestSpaceMarinesVindicationTaskForceEnhancements(unittest.TestCase):
    def test_vindication_enhancement_descriptors_exist(self):
        expected = {
            "000010396002": (
                "Imperialis of the Eternal Crusade",
                "charge_roll_penalty_against_enemy_unit_targeting_bearer_unit",
            ),
            "000010396003": ("Consecrating Aura", "bearer_unit_invulnerable_save"),
            "000010396004": ("Orb of the Emperor's Aegis", "grant_deep_strike_to_bearer_unit"),
            "000010396005": ("Warden of Honour", "vengeful_exhortation_roll_bonus"),
        }
        for enhancement_id, (name, effect) in expected.items():
            desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
            self.assertIsNotNone(desc)
            self.assertEqual(str(getattr(desc, "name", "") or ""), name)
            self.assertEqual(str(getattr(desc, "effect", "") or ""), effect)

    def test_imperialis_of_the_eternal_crusade_applies_negative_charge_and_is_non_cumulative(self):
        game, sm_army, enemy_army = _build_game()
        leader = _make_unit(
            "Crusade Ancient",
            keywords=["CHARACTER", "INFANTRY", "ANCIENT"],
            faction_keywords=["ADEPTUS ASTARTES"],
            attached_to=["INFANTRY_BODYGUARD"],
        )
        bodyguard = _make_unit(
            "Crusader Squad",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=5,
            wounds=2,
        )
        charger = _make_unit(
            "Enemy Chargers",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            model_count=5,
            wounds=2,
        )
        sm_army.add_unit(leader)
        sm_army.add_unit(bodyguard)
        enemy_army.add_unit(charger)
        _attach_leader(bodyguard, leader)
        _apply_enhancement(
            leader,
            enhancement_id="000010396002",
            enhancement_name="Imperialis of the Eternal Crusade",
        )

        mods = list(game.get_charge_roll_modifiers(charger, target_unit=bodyguard) or [])
        self.assertTrue(any(int(v or 0) == -2 for v, _ in mods))

        charger.special_rules = {"charge_roll_modifiers": [{"value": -1, "source": "Test penalty"}]}
        mods_non_cumulative = list(game.get_charge_roll_modifiers(charger, target_unit=bodyguard) or [])
        negative_total = sum(int(v or 0) for v, _ in mods_non_cumulative if int(v or 0) < 0)
        self.assertEqual(negative_total, -2)

    def test_consecrating_aura_grants_five_plus_invulnerable_to_bearer_unit(self):
        _game, sm_army, _enemy_army = _build_game()
        leader = _make_unit(
            "Crusade Ancient",
            keywords=["CHARACTER", "INFANTRY", "ANCIENT"],
            faction_keywords=["ADEPTUS ASTARTES"],
            attached_to=["INFANTRY_BODYGUARD"],
        )
        bodyguard = _make_unit(
            "Crusader Squad",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=5,
            wounds=2,
        )
        sm_army.add_unit(leader)
        sm_army.add_unit(bodyguard)
        _attach_leader(bodyguard, leader)

        _apply_enhancement(leader, enhancement_id="000010396003", enhancement_name="Consecrating Aura")
        invuln, source = bodyguard.get_model_invulnerable_save_override(bodyguard.models[0])
        self.assertEqual(invuln, 5)
        self.assertIn("Consecrating Aura", str(source or ""))

    def test_orb_of_the_emperors_aegis_grants_deep_strike_to_bearer_unit(self):
        _game, sm_army, _enemy_army = _build_game()
        leader = _make_unit(
            "Crusade Ancient",
            keywords=["CHARACTER", "INFANTRY", "ANCIENT"],
            faction_keywords=["ADEPTUS ASTARTES"],
            attached_to=["INFANTRY_BODYGUARD"],
        )
        bodyguard = _make_unit(
            "Crusader Squad",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=5,
            wounds=2,
        )
        sm_army.add_unit(leader)
        sm_army.add_unit(bodyguard)
        _attach_leader(bodyguard, leader)

        _apply_enhancement(
            leader,
            enhancement_id="000010396004",
            enhancement_name="Orb of the Emperor's Aegis",
        )
        self.assertTrue(bool(bodyguard.has_deep_strike()))

    def test_warden_of_honour_adds_one_to_vengeful_exhortation_roll_while_leading(self):
        _game, sm_army, _enemy_army = _build_game()
        vengeful_exhortation = {
            "name": "Vengeful Exhortation",
            "description": (
                "While this model is leading a unit, each time a model in that unit is destroyed by a melee attack, "
                "if it has not fought this phase, roll one D6: on a 4+, do not remove it from play. The destroyed "
                "model can fight after the attacking unit has finished making its attacks, and is then removed from play."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        leader = _make_unit(
            "Crusade Ancient",
            keywords=["CHARACTER", "INFANTRY", "ANCIENT"],
            faction_keywords=["ADEPTUS ASTARTES"],
            attached_to=["INFANTRY_BODYGUARD"],
            abilities=[vengeful_exhortation],
        )
        bodyguard = _make_unit(
            "Crusader Squad",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=5,
            wounds=2,
        )
        sm_army.add_unit(leader)
        sm_army.add_unit(bodyguard)
        _attach_leader(bodyguard, leader)

        _apply_enhancement(leader, enhancement_id="000010396005", enhancement_name="Warden of Honour")
        rule = bodyguard.get_melee_fight_on_death_after_attacks_rule(model=bodyguard.models[0])
        self.assertIsNotNone(rule)
        self.assertEqual(int(rule.get("threshold", 0) or 0), 3)
        self.assertIn("Warden of Honour", str(rule.get("source", "") or ""))

    def test_warden_of_honour_does_not_modify_vengeful_exhortation_when_not_leading(self):
        _game, sm_army, _enemy_army = _build_game()
        vengeful_exhortation = {
            "name": "Vengeful Exhortation",
            "description": (
                "While this model is leading a unit, each time a model in that unit is destroyed by a melee attack, "
                "if it has not fought this phase, roll one D6: on a 4+, do not remove it from play. The destroyed "
                "model can fight after the attacking unit has finished making its attacks, and is then removed from play."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        leader = _make_unit(
            "Crusade Ancient",
            keywords=["CHARACTER", "INFANTRY", "ANCIENT"],
            faction_keywords=["ADEPTUS ASTARTES"],
            abilities=[vengeful_exhortation],
        )
        sm_army.add_unit(leader)
        _apply_enhancement(leader, enhancement_id="000010396005", enhancement_name="Warden of Honour")

        rule = leader.get_melee_fight_on_death_after_attacks_rule(model=leader.models[0])
        self.assertIsNotNone(rule)
        self.assertEqual(int(rule.get("threshold", 0) or 0), 4)


if __name__ == "__main__":
    unittest.main()
