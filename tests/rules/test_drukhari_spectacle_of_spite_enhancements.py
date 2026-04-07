import unittest
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_COMBAT_DRUGS
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Drukhari",
        faction_keywords=None,
        keywords=None,
        wounds: int = 3,
    ):
        self.id = ""
        self.name = name
        self.faction_data = {"name": faction_name}
        if faction_keywords is None:
            faction_keywords = ["DRUKHARI"] if faction_name == "Drukhari" else [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords or [])
        self.keywords = list(keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "8",
                "T": "3",
                "Sv": "6",
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
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Drukhari",
    faction_keywords=None,
    keywords=None,
    wounds: int = 3,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            faction_keywords=faction_keywords,
            keywords=keywords,
            wounds=wounds,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    drukhari_army = Army.with_detachment("Drukhari", "Spectacle of Spite")
    drukhari_army.faction_id = "DRU"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    p1 = Player("P1", control=PlayerControl.REMOTE, army=drukhari_army)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)
    game.turn = 1
    game.current_player_index = 0
    return game, p1, p2, drukhari_army, enemy_army


def _find_pending_request(game: Game, decision_type: str):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") == str(decision_type):
            return req
    return None


def _find_option_by_choice_key(request, key: str):
    key = str(key or "").strip().upper()
    for opt in list(getattr(request, "options", []) or []):
        payload = dict(getattr(opt, "payload", {}) or {})
        choice = str(payload.get("choice_key", "") or "").strip().upper()
        if choice == key:
            return opt
    return None


def _make_melee_profile(*, attacks: str = "1", ap: str = "0", damage: str = "1"):
    parent = type(
        "_Parent",
        (),
        {
            "name": "Test Blade",
            "is_melee": staticmethod(lambda: True),
            "is_ranged": staticmethod(lambda: False),
        },
    )()
    data = {
        "range": "Melee",
        "A": str(attacks),
        "BS_WS": "3+",
        "S": "4",
        "AP": str(ap),
        "D": str(damage),
        "description": "",
    }
    return WargearProfile("Profile", wargear_data=data, parent_wargear=parent)


class TestDrukhariSpectacleOfSpiteEnhancements(unittest.TestCase):
    def test_pharmacophex_applies_extra_combat_drug_to_bearer_unit_after_selection(self):
        game, p1, _p2, drukhari_army, _enemy_army = _build_game()
        succubus = _make_unit(
            "Succubus",
            keywords=["INFANTRY", "CHARACTER", "WYCH CULT", "DRUKHARI"],
            faction_keywords=["DRUKHARI"],
        )
        wyches = _make_unit(
            "Wyches",
            keywords=["INFANTRY", "WYCH CULT", "DRUKHARI"],
            faction_keywords=["DRUKHARI"],
        )
        drukhari_army.add_unit(succubus)
        drukhari_army.add_unit(wyches)

        enh = Enhancement(
            id="000010580002",
            name="Pharmacophex",
            faction_id="DRU",
            detachment="Spectacle of Spite",
            points=15,
            description="",
        )
        succubus.enhancement = enh
        enh.apply_to_unit(succubus)

        game._maybe_prompt_combat_drugs()
        req = _find_pending_request(game, DECISION_CHOOSE_COMBAT_DRUGS)
        self.assertIsNotNone(req)
        option = _find_option_by_choice_key(req, "HYPEX")
        self.assertIsNotNone(option)

        from warhammer40k_ai.rules import drukhari_detachments as dd

        with patch.object(dd, "get_roll", return_value=5):
            resolve_decision_command(game, req, option.option_id, player_id=p1.id)

        mgr = drukhari_army.drukhari_detachments
        succ_keys = mgr.get_active_combat_drug_keys_for_model(succubus.models[0], game=game)
        wych_keys = mgr.get_active_combat_drug_keys_for_model(wyches.models[0], game=game)
        self.assertEqual(succ_keys, {"HYPEX", "GRAVE_LOTUS"})
        self.assertEqual(wych_keys, {"HYPEX"})

    def test_pharmacophex_duplicate_drug_has_no_additional_effect(self):
        game, p1, _p2, drukhari_army, _enemy_army = _build_game()
        succubus = _make_unit(
            "Succubus",
            keywords=["INFANTRY", "CHARACTER", "WYCH CULT", "DRUKHARI"],
            faction_keywords=["DRUKHARI"],
        )
        drukhari_army.add_unit(succubus)

        enh = Enhancement(
            id="000010580002",
            name="Pharmacophex",
            faction_id="DRU",
            detachment="Spectacle of Spite",
            points=15,
            description="",
        )
        succubus.enhancement = enh
        enh.apply_to_unit(succubus)

        game._maybe_prompt_combat_drugs()
        req = _find_pending_request(game, DECISION_CHOOSE_COMBAT_DRUGS)
        self.assertIsNotNone(req)
        option = _find_option_by_choice_key(req, "HYPEX")
        self.assertIsNotNone(option)

        from warhammer40k_ai.rules import drukhari_detachments as dd

        with patch.object(dd, "get_roll", return_value=2):
            resolve_decision_command(game, req, option.option_id, player_id=p1.id)

        mgr = drukhari_army.drukhari_detachments
        succ_keys = mgr.get_active_combat_drug_keys_for_model(succubus.models[0], game=game)
        self.assertEqual(succ_keys, {"HYPEX"})
        sr = dict(getattr(succubus, "special_rules", {}) or {})
        self.assertEqual(str(sr.get("enhancement_pharmacophex_drug_key", "") or ""), "")

    def test_periapt_of_torments_prevents_overwatch_against_bearer_unit(self):
        game, _p1, _p2, drukhari_army, enemy_army = _build_game()
        succubus = _make_unit(
            "Succubus",
            keywords=["INFANTRY", "CHARACTER", "WYCH CULT", "DRUKHARI"],
            faction_keywords=["DRUKHARI"],
        )
        drukhari_ally = _make_unit(
            "Wyches",
            keywords=["INFANTRY", "WYCH CULT", "DRUKHARI"],
            faction_keywords=["DRUKHARI"],
        )
        enemy = _make_unit(
            "Enemy Shooters",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        drukhari_army.add_unit(succubus)
        drukhari_army.add_unit(drukhari_ally)
        enemy_army.add_unit(enemy)

        enh = Enhancement(
            id="000010580004",
            name="Periapt of Torments",
            faction_id="DRU",
            detachment="Spectacle of Spite",
            points=25,
            description="",
        )
        succubus.enhancement = enh
        enh.apply_to_unit(succubus)

        self.assertTrue(succubus.is_overwatch_prevented_against(enemy, game=game))
        self.assertFalse(succubus.is_overwatch_prevented_against(drukhari_ally, game=game))

    def test_morghennas_curse_grants_bearer_melee_ap_and_damage_bonus(self):
        _game, _p1, _p2, drukhari_army, enemy_army = _build_game()
        succubus = _make_unit(
            "Succubus",
            keywords=["INFANTRY", "CHARACTER", "WYCH CULT", "DRUKHARI"],
            faction_keywords=["DRUKHARI"],
            wounds=5,
        )
        target = _make_unit(
            "Enemy Target",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
            wounds=5,
        )
        drukhari_army.add_unit(succubus)
        enemy_army.add_unit(target)

        enh = Enhancement(
            id="000010580005",
            name="Morghenna's Curse",
            faction_id="DRU",
            detachment="Spectacle of Spite",
            points=20,
            description="",
        )
        succubus.enhancement = enh
        enh.apply_to_unit(succubus)

        profile = _make_melee_profile(attacks="1", ap="0", damage="1")
        attacker_model = succubus.models[0]
        target_model = target.models[0]
        self.assertEqual(int(profile.get_effective_ap(attacker_model, target)), -1)

        before = int(target_model.wounds)
        profile._damage_target_with_tracking(
            target_model,
            attacker_model,
            {"below_half_distance": False, "mortal_wound": False},
            game_map=None,
        )
        self.assertEqual(int(target_model.wounds), before - 2)

    def test_chronoshard_activates_once_per_battle_fight_first(self):
        _game, _p1, _p2, drukhari_army, _enemy_army = _build_game()
        succubus = _make_unit(
            "Succubus",
            keywords=["INFANTRY", "CHARACTER", "WYCH CULT", "DRUKHARI"],
            faction_keywords=["DRUKHARI"],
        )
        drukhari_army.add_unit(succubus)

        enh = Enhancement(
            id="000010580003",
            name="Chronoshard",
            faction_id="DRU",
            detachment="Spectacle of Spite",
            points=15,
            description="",
        )
        succubus.enhancement = enh
        enh.apply_to_unit(succubus)

        self.assertTrue(succubus.has_enhancement_fight_first_once_per_battle())
        self.assertTrue(succubus.can_use_enhancement_fight_first())
        self.assertTrue(succubus.activate_enhancement_fight_first())
        self.assertTrue(bool(succubus.special_rules.get("enhancement_fight_first_active")))
        self.assertFalse(succubus.can_use_enhancement_fight_first())


if __name__ == "__main__":
    unittest.main()
