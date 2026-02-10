import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.calcs import MovementType, get_validation_rules
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Emperor's Children",
        faction_keywords=None,
        keywords=None,
        toughness: int = 4,
        wounds: int = 6,
    ):
        self.id = ""
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
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Emperor's Children",
    faction_keywords=None,
    keywords=None,
    toughness: int = 4,
    wounds: int = 6,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            faction_keywords=faction_keywords,
            keywords=keywords,
            toughness=toughness,
            wounds=wounds,
        )
    )


def _build_game(detachment: str = "Court of the Phoenician"):
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    ec_army = Army("Emperor's Children", detachment)
    ec_army.faction_id = "EC"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    p1 = Player("P1", control=PlayerControl.REMOTE, army=ec_army)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)
    return game, ec_army, enemy_army, p1, p2


def _make_melee_profile(*, strength: int = 5) -> WargearProfile:
    parent = SimpleNamespace(name="Blade", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        profile_name="Melee",
        wargear_data={
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
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


class TestEmperorsChildrenMercurialHostEnhancements(unittest.TestCase):
    def test_steeped_in_suffering_applies_hit_and_wound_bonuses(self):
        _game, army, enemy_army, _p1, _p2 = _build_game(detachment="Court of the Phoenician")

        leader = _make_unit("Lord Exultant", keywords=["CHARACTER"])
        bodyguard = _make_unit("Noise Marines", keywords=["INFANTRY"])
        target = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
            wounds=6,
        )
        army.add_unit(leader)
        army.add_unit(bodyguard)
        enemy_army.add_unit(target)

        leader.attached_to = bodyguard
        bodyguard.attached_leaders = [leader]
        leader.can_be_attached_to = [bodyguard.name]

        Enhancement(
            id="000009998002",
            name="Steeped in Suffering",
            faction_id="EC",
            detachment="Court of the Phoenician",
            points=20,
            description="",
        ).apply_to_unit(leader)

        self.assertTrue(bool(leader.special_rules.get("enhancement_steeped_in_suffering")))

        full_hit = bodyguard.get_unit_hit_reroll_modifiers("melee", target=target)
        full_wound = bodyguard.get_unit_wound_reroll_modifiers("melee", target=target)
        self.assertEqual(int(full_hit.get("hit", 0) or 0), 0)
        self.assertEqual(int(full_wound.get("wound", 0) or 0), 0)

        target.models[0]._wounds = 5
        below_start_hit = bodyguard.get_unit_hit_reroll_modifiers("melee", target=target)
        below_start_wound = bodyguard.get_unit_wound_reroll_modifiers("melee", target=target)
        self.assertEqual(int(below_start_hit.get("hit", 0) or 0), 1)
        self.assertEqual(int(below_start_wound.get("wound", 0) or 0), 0)

        target.models[0]._wounds = 2
        below_half_hit = bodyguard.get_unit_hit_reroll_modifiers("melee", target=target)
        below_half_wound = bodyguard.get_unit_wound_reroll_modifiers("melee", target=target)
        self.assertEqual(int(below_half_hit.get("hit", 0) or 0), 1)
        self.assertEqual(int(below_half_wound.get("wound", 0) or 0), 1)

    def test_intoxicating_musk_applies_melee_wound_penalty_only_while_bearer_alive(self):
        _game, army, enemy_army, _p1, _p2 = _build_game(detachment="Court of the Phoenician")

        leader = _make_unit("Lord Exultant", keywords=["CHARACTER"])
        bodyguard = _make_unit("Noise Marines", keywords=["INFANTRY"], toughness=4)
        attacker_unit = _make_unit(
            "Enemy Attacker",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        army.add_unit(leader)
        army.add_unit(bodyguard)
        enemy_army.add_unit(attacker_unit)

        leader.attached_to = bodyguard
        bodyguard.attached_leaders = [leader]
        leader.can_be_attached_to = [bodyguard.name]

        Enhancement(
            id="000009998003",
            name="Intoxicating Musk",
            faction_id="EC",
            detachment="Court of the Phoenician",
            points=20,
            description="",
        ).apply_to_unit(leader)

        profile = _make_melee_profile(strength=5)
        with_penalty = profile._wound_target_with_tracking(
            bodyguard,
            attacker_unit.models[0],
            {"_aura_attack_mods": _aura_stub()},
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(bool(with_penalty.get("wound")))
        self.assertTrue(any("Intoxicating Musk" in str(v) for v in list(with_penalty.get("modifiers", []) or [])))

        leader.models[0]._wounds = 0
        without_penalty = profile._wound_target_with_tracking(
            bodyguard,
            attacker_unit.models[0],
            {"_aura_attack_mods": _aura_stub()},
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(bool(without_penalty.get("wound")))

    def test_tactical_perfection_redeploy_filters_to_emperors_children_units(self):
        game, army, enemy_army, _p1, _p2 = _build_game(detachment="Court of the Phoenician")
        game.attacker_index = 0
        game.defender_index = 1

        bearer = _make_unit("Bearer", keywords=["CHARACTER"])
        ec_unit = _make_unit("EC Unit", keywords=["INFANTRY"], faction_keywords=["EMPEROR'S CHILDREN"])
        allied_unit = _make_unit(
            "Allied Unit",
            faction_keywords=["LEGIONS OF EXCESS"],
            keywords=["INFANTRY"],
        )

        army.add_unit(bearer)
        army.add_unit(ec_unit)
        army.add_unit(allied_unit)
        enemy_army.add_unit(_make_unit("Enemy", faction_name="Enemy", faction_keywords=["ENEMY"], keywords=["INFANTRY"]))

        enh = Enhancement(
            id="000009998004",
            name="Tactical Perfection",
            faction_id="EC",
            detachment="Court of the Phoenician",
            points=15,
            description=(
                "Emperor's Children model only. After both players have deployed their armies, select up to two EMPEROR'S "
                "CHILDREN units from your army and redeploy them. When doing so, you can set those units up in Strategic "
                "Reserves if you wish, regardless of how many units are already in Strategic Reserves."
            ),
        )
        bearer.enhancement = enh
        enh.apply_to_unit(bearer)

        for idx, unit in enumerate([bearer, ec_unit, allied_unit], start=1):
            unit.deployed = True
            unit.reserve_status = "deployed"
            unit.models[0].set_location(float(5 * idx), 5.0, 0.0, 0.0)
            self.assertTrue(game.map.place_unit(unit))
        game.rebuild_entity_registry()

        game.execute_redeploy_units_phase()

        pending = [
            req for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
        ]
        self.assertEqual(len(pending), 1)
        request = pending[0]
        options = list(getattr(request, "options", []) or [])

        allied_id = str(get_entity_id(allied_unit) or "")
        target_ids = {
            str((dict(getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or ""))
            for opt in options
        }
        self.assertNotIn(allied_id, target_ids)

        ec_id = str(get_entity_id(ec_unit) or "")
        self.assertTrue(
            any(
                str((dict(getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or "")) == ec_id
                and str((dict(getattr(opt, "payload", {}) or {}).get("redeploy_action", "") or "")).lower()
                == "strategic_reserves"
                for opt in options
            )
        )

    def test_loathsome_dexterity_applies_move_through_enemy_and_auto_pass_fall_back(self):
        _game, army, _enemy_army, _p1, _p2 = _build_game(detachment="Court of the Phoenician")

        leader = _make_unit("Lord Exultant", keywords=["CHARACTER"])
        bodyguard = _make_unit("Noise Marines", keywords=["INFANTRY"])
        army.add_unit(leader)
        army.add_unit(bodyguard)

        leader.attached_to = bodyguard
        bodyguard.attached_leaders = [leader]
        leader.can_be_attached_to = [bodyguard.name]

        Enhancement(
            id="000009998005",
            name="Loathsome Dexterity",
            faction_id="EC",
            detachment="Court of the Phoenician",
            points=15,
            description="",
        ).apply_to_unit(leader)

        self.assertIsNone(bodyguard._get_advance_no_roll_effect())

        move_rules = get_validation_rules(MovementType.MOVE, moving_unit=bodyguard)
        self.assertTrue(bool(move_rules.get("can_move_through_enemy_models")))
        self.assertFalse(bool(move_rules.get("cannot_move_within_engagement_range")))
        self.assertTrue(bool(move_rules.get("cannot_end_in_engagement_range")))

        fall_back_rules = get_validation_rules(MovementType.FALL_BACK, moving_unit=bodyguard)
        self.assertTrue(bool(fall_back_rules.get("can_move_through_enemy_models")))
        self.assertFalse(bool(fall_back_rules.get("check_desperate_escape", True)))


if __name__ == "__main__":
    unittest.main()
