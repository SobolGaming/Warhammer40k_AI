import unittest
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_dispatcher import dispatch_decision
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.decisions import DecisionResult
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, BattleRoundPhases, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.utility.modifier_choice import CHOICE_IGNORE_NEGATIVE


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        datasheet_id: str = "",
        faction_name: str = "Emperor's Children",
        faction_keywords=None,
        keywords=None,
        toughness: int = 4,
        wounds: int = 6,
        abilities=None,
    ):
        self.id = str(datasheet_id or "")
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            if faction_name == "Emperor's Children":
                faction_keywords = ["EMPEROR'S CHILDREN"]
            else:
                faction_keywords = [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": str(int(toughness)),
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
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    datasheet_id: str = "",
    faction_name: str = "Emperor's Children",
    faction_keywords=None,
    keywords=None,
    toughness: int = 4,
    wounds: int = 6,
    abilities=None,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            datasheet_id=datasheet_id,
            faction_name=faction_name,
            faction_keywords=faction_keywords,
            keywords=keywords,
            toughness=toughness,
            wounds=wounds,
            abilities=abilities,
        )
    )


def _build_game(detachment: str = "Court of the Phoenician"):
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    ec_army = Army.with_detachment("Emperor's Children", detachment)
    ec_army.faction_id = "EC"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    p1 = Player("P1", control=PlayerControl.REMOTE, army=ec_army)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)
    return game, ec_army, enemy_army, p1, p2


def _deploy(*units: Unit) -> None:
    for unit in units:
        unit.deployed = True
        unit.reserve_status = "deployed"
        unit.embarked_in = None


def _make_melee_profile(*, strength: int = 4, skill: str = "4+") -> WargearProfile:
    parent = SimpleNamespace(name="Blade", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        profile_name="Melee",
        wargear_data={
            "range": "Melee",
            "A": "1",
            "BS_WS": str(skill),
            "S": str(int(strength)),
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def _aura_stub():
    return SimpleNamespace(
        hit=0,
        wound=0,
        reroll_hit_ones=False,
        reroll_wound_ones=False,
        reroll_hit_reasons=(),
        reroll_wound_reasons=(),
        target_toughness_delta=0,
        target_toughness_reasons=(),
    )


class TestEmperorsChildrenCourtOfThePhoenicianEnhancements(unittest.TestCase):
    def test_tears_of_the_phoenix_ignores_melee_hit_and_wound_modifiers_by_choice(self):
        _game, army, enemy_army, _p1, _p2 = _build_game()

        leader = _make_unit("Lord Exultant", keywords=["CHARACTER"])
        bodyguard = _make_unit("Noise Marines", keywords=["INFANTRY"])
        target = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
            abilities=[{"name": "Stealth", "description": "Stealth.", "type": "Datasheet", "parameter": ""}],
        )
        army.add_unit(leader)
        army.add_unit(bodyguard)
        enemy_army.add_unit(target)

        leader.attached_to = bodyguard
        bodyguard.attached_leaders = [leader]

        Enhancement(
            id="000010654002",
            name="Tears of the Phoenix",
            faction_id="EC",
            detachment="Court of the Phoenician",
            points=25,
            description="",
        ).apply_to_unit(leader)

        self.assertTrue(bool(leader.special_rules.get("enhancement_tears_of_the_phoenix")))

        profile = _make_melee_profile(strength=4, skill="4+")

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=4):
            no_ignore_hit = profile._hit_target_with_tracking(
                target,
                bodyguard.models[0],
                {"_aura_attack_mods": _aura_stub()},
                roll_value=None,
                allow_rerolls=False,
                log_roll=False,
            )
        self.assertFalse(bool(no_ignore_hit.get("hit")))

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=4):
            with_ignore_hit = profile._hit_target_with_tracking(
                target,
                bodyguard.models[0],
                {
                    "_aura_attack_mods": _aura_stub(),
                    "hit_modifier_choice": CHOICE_IGNORE_NEGATIVE,
                },
                roll_value=None,
                allow_rerolls=False,
                log_roll=False,
            )
        self.assertTrue(bool(with_ignore_hit.get("hit")))

        target.special_rules["pain_melee_wound_roll_defense_mod"] = -1

        no_ignore_wound = profile._wound_target_with_tracking(
            target,
            bodyguard.models[0],
            {"_aura_attack_mods": _aura_stub()},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(bool(no_ignore_wound.get("wound")))

        with_ignore_wound = profile._wound_target_with_tracking(
            target,
            bodyguard.models[0],
            {
                "_aura_attack_mods": _aura_stub(),
                "wound_modifier_choice": CHOICE_IGNORE_NEGATIVE,
            },
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(bool(with_ignore_wound.get("wound")))

    def test_exalted_patron_allows_lord_exultant_to_attach_to_flawless_blades(self):
        _game, army, _enemy_army, _p1, _p2 = _build_game()

        leader = _make_unit("Lord Exultant", datasheet_id="000004078", keywords=["CHARACTER"])
        flawless_blades = _make_unit("Flawless Blades", datasheet_id="000004089", keywords=["INFANTRY"])
        other = _make_unit("Noise Marines", keywords=["INFANTRY"])
        leader.can_be_attached_to = ["Noise Marines"]

        army.add_unit(leader)
        army.add_unit(flawless_blades)
        army.add_unit(other)

        Enhancement(
            id="000010654003",
            name="Exalted Patron",
            faction_id="EC",
            detachment="Court of the Phoenician",
            points=20,
            description="",
        ).apply_to_unit(leader)

        self.assertTrue(bool(leader.special_rules.get("enhancement_exalted_patron")))
        self.assertTrue(leader.can_attach_to(flawless_blades))
        self.assertFalse(leader.can_attach_to(other))

    def test_soulstain_made_manifest_queues_single_dialog_and_applies_battleshock_modifier(self):
        game, army, enemy_army, p1, _p2 = _build_game()

        source = _make_unit("Lord Exultant", datasheet_id="000004078", keywords=["CHARACTER"])
        source.can_be_attached_to = ["Noise Marines"]
        enemy_a = _make_unit(
            "Enemy A",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        enemy_b = _make_unit(
            "Enemy B",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )

        army.add_unit(source)
        enemy_army.add_unit(enemy_a)
        enemy_army.add_unit(enemy_b)
        _deploy(source, enemy_a, enemy_b)

        game.turn = 1
        game.phase = BattleRoundPhases.FIGHT_PHASE
        game.current_player_index = 0
        game.map.units = [source, enemy_a, enemy_b]
        game.rebuild_entity_registry()

        tested_turns: list[int] = []
        enemy_a.take_battle_shock_test = lambda turn: tested_turns.append(int(turn))

        Enhancement(
            id="000010654004",
            name="Soulstain Made Manifest",
            faction_id="EC",
            detachment="Court of the Phoenician",
            points=20,
            description="",
        ).apply_to_unit(source)

        with patch(
            "warhammer40k_ai.utility.aura_utils.model_within_engagement_range_of_unit",
            side_effect=lambda _model, enemy: enemy is enemy_a,
        ):
            game._on_phase_start_emperors_children_enhancements(player=p1, phase=game.phase)

        requests = [
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "")) == DECISION_CHOOSE_QUARRY
            and str((getattr(req, "context", {}) or {}).get("ability_name", "")) == "Soulstain Made Manifest"
        ]
        self.assertEqual(len(requests), 1)
        request = requests[0]

        self.assertTrue(any(str((opt.payload or {}).get("action", "")) == "skip" for opt in list(request.options or [])))
        enemy_a_id = str(get_entity_id(enemy_a) or "")
        enemy_b_id = str(get_entity_id(enemy_b) or "")
        target_ids = [str((opt.payload or {}).get("target_unit_id", "") or "") for opt in list(request.options or [])]
        self.assertIn(enemy_a_id, target_ids)
        self.assertNotIn(enemy_b_id, target_ids)

        invalid_result = DecisionResult(
            decision_id=request.decision_id,
            player_id=p1.id,
            option_id="invalid-option",
        )
        invalid_apply = dispatch_decision(game, request, invalid_result)
        self.assertFalse(bool(invalid_apply.ok))

        choose_enemy_a = next(
            opt for opt in list(request.options or []) if str((opt.payload or {}).get("target_unit_id", "")) == enemy_a_id
        )
        valid_result = DecisionResult(
            decision_id=request.decision_id,
            player_id=p1.id,
            option_id=choose_enemy_a.option_id,
        )
        valid_apply = dispatch_decision(game, request, valid_result)
        self.assertTrue(bool(valid_apply.ok))

        self.assertEqual(tested_turns, [1])
        self.assertEqual(int(enemy_a.special_rules.get("battle_shock_test_modifier", 0) or 0), -1)

    def test_spiritsliver_sets_bearer_melee_strength_and_attacks_bonuses(self):
        _game, army, _enemy_army, _p1, _p2 = _build_game()

        bearer = _make_unit(
            "Daemon Prince of Slaanesh",
            datasheet_id="000004086",
            keywords=["CHARACTER", "MONSTER"],
        )
        army.add_unit(bearer)

        Enhancement(
            id="000010654005",
            name="Spiritsliver",
            faction_id="EC",
            detachment="Court of the Phoenician",
            points=15,
            description="",
        ).apply_to_unit(bearer)

        sr = getattr(bearer, "special_rules", {}) or {}
        self.assertTrue(bool(sr.get("enhancement_spiritsliver")))
        self.assertEqual(int(sr.get("enhancement_bearer_melee_strength_bonus", 0) or 0), 1)
        self.assertEqual(int(sr.get("enhancement_bearer_melee_attacks_bonus", 0) or 0), 1)
        self.assertTrue(str(sr.get("enhancement_bearer_model_id", "") or ""))


if __name__ == "__main__":
    unittest.main()
