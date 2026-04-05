import unittest

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.utility.model_base import Base, BaseType


class _Ability:
    def __init__(self, *, name: str, description: str):
        self.name = name
        self.description = description


def _make_unit(name, army, *, keywords=None, faction_keywords=None, x=0.0, y=0.0, abilities=None):
    unit = Unit.__new__(Unit)
    unit.name = name
    unit._id = name
    unit.parent_army = army
    unit.faction = getattr(army, "faction_id", "")
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.models = []
    unit.models_lost = []
    unit.keywords = list(keywords or [])
    unit.faction_keywords = list(faction_keywords or [])
    unit.possible_abilities = []
    unit.status_effects = []
    unit.special_rules = {}
    unit.round_state = None
    unit.attached_leaders = []
    unit.attached_to = None
    unit.can_be_attached_to = []
    unit.embarked_in = None
    unit.transport_passengers = []
    unit._ability_cache = {}
    unit.enhancement = None
    unit.is_alive = lambda: True
    unit.get_parent_army = lambda: army
    unit.get_attached_unit_root = lambda: unit
    unit.get_attached_unit_models = lambda: list(unit.models)
    unit.get_attached_unit_members = lambda: [unit]
    unit.get_models_for_collision = lambda: list(unit.models)
    unit.is_in_reserves = lambda: unit.reserve_status in ("reserves", "strategic_reserves")
    unit._iter_active_possible_abilities = lambda: []
    unit._ability_is_active = lambda ability: True
    unit.has_any_keyword = lambda kw: any(
        str(kw or "").strip().upper() == str(k or "").strip().upper()
        for k in (unit.keywords + unit.faction_keywords)
    )

    model = Model(
        name=f"{name} Model",
        movement=6,
        toughness=4,
        save=3,
        wounds=4,
        leadership=7,
        objective_control=1,
        model_base=Base(BaseType.CIRCULAR, 1.0),
    )
    model.parent_unit = unit
    model.set_location(float(x), float(y), 0.0, 0.0)
    model.abilities = list(abilities or [])
    unit.models = [model]
    return unit


def _build_game(*, faction_id: str):
    army = Army("Primary", detachment_type="Test")
    army.faction_id = faction_id
    enemy_army = Army("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"

    player = Player("Player", PlayerControl.REMOTE, army=army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
    game.auto_resolve_dice_rolls = False
    game.attacker_index = 0
    game.defender_index = 1
    return game, army, enemy_army, player, enemy_player


def _find_redeploy_request(game: Game, *, player_id: str, ability_name: str):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        if str(getattr(req, "player_id", "") or "") != str(player_id):
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability_name", "") or "") != str(ability_name):
            continue
        return req
    return None


def _find_option_id(request, *, target_unit_id: str, action: str) -> str:
    target_id = str(target_unit_id or "")
    action_norm = str(action or "").strip().lower()
    for opt in list(getattr(request, "options", []) or []):
        payload = dict(getattr(opt, "payload", {}) or {})
        if str(payload.get("target_unit_id", "") or "") != target_id:
            continue
        if str(payload.get("redeploy_action", "") or "").strip().lower() != action_norm:
            continue
        return str(getattr(opt, "option_id", "") or "")
    return ""


class TestPR2ARedeploySupport(unittest.TestCase):
    def test_pr2a_enhancement_descriptors_exist(self):
        expected = {
            "000009130003": ("Liber Heresius", "AGENTS OF THE IMPERIUM"),
            "000008442004": ("Solid-image Projection Unit", "T'AU EMPIRE"),
            "000010197004": ("Duplicitous Malediction", "THOUSAND SONS"),
            "000008417005": ("Neuronode", "VANGUARD INVADER"),
        }
        for enhancement_id, (name, filter_keyword) in expected.items():
            desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
            self.assertIsNotNone(desc)
            self.assertEqual(str(getattr(desc, "name", "") or ""), name)
            self.assertEqual(str(getattr(desc, "effect", "") or ""), "redeploy_units")
            self.assertEqual(int((getattr(desc, "effect_params", {}) or {}).get("max_units", 0) or 0), 3)
            self.assertTrue(bool((getattr(desc, "effect_params", {}) or {}).get("allow_strategic_reserves", False)))
            self.assertEqual(
                tuple((getattr(desc, "effect_params", {}) or {}).get("redeploy_filters", ()) or ()),
                (filter_keyword,),
            )

    def _assert_redeploy_filter(self, *, enhancement_id, name, faction_id, description, expected_filter):
        game, army, enemy_army, player, _enemy = _build_game(faction_id=faction_id)
        source = _make_unit(
            "Source",
            army,
            keywords=["CHARACTER"],
            faction_keywords=[expected_filter],
            x=0.0,
            y=0.0,
        )
        eligible = _make_unit(
            "Eligible",
            army,
            keywords=["INFANTRY"],
            faction_keywords=[expected_filter],
            x=6.0,
            y=0.0,
        )
        ineligible = _make_unit(
            "Ineligible",
            army,
            keywords=["INFANTRY"],
            faction_keywords=["OTHER"],
            x=12.0,
            y=0.0,
        )
        enemy = _make_unit(
            "Enemy",
            enemy_army,
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            x=24.0,
            y=0.0,
        )

        enhancement = Enhancement(
            id=enhancement_id,
            name=name,
            faction_id=faction_id,
            detachment="Test",
            description=description,
        )
        source.enhancement = enhancement
        enhancement.apply_to_unit(source)

        army.units = [source, eligible, ineligible]
        enemy_army.units = [enemy]
        game.map.units = [source, eligible, ineligible, enemy]
        game.rebuild_entity_registry()

        has_redeploy, count, can_place_in_reserves = source.has_redeploy()
        self.assertTrue(has_redeploy)
        self.assertEqual(int(count), 3)
        self.assertTrue(can_place_in_reserves)
        self.assertEqual(list((getattr(source, "_ability_cache", {}) or {}).get("redeploy_filters", []) or []), [expected_filter])

        game.execute_redeploy_units_phase()
        request = _find_redeploy_request(game, player_id=player.id, ability_name=name)
        self.assertIsNotNone(request)

        target_ids = {
            str((dict(getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or ""))
            for opt in list(getattr(request, "options", []) or [])
            if str((dict(getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or ""))
        }
        self.assertIn(str(get_entity_id(eligible) or ""), target_ids)
        self.assertNotIn(str(get_entity_id(ineligible) or ""), target_ids)

        option_id = _find_option_id(
            request,
            target_unit_id=str(get_entity_id(eligible) or ""),
            action="strategic_reserves",
        )
        self.assertTrue(bool(option_id))

    def test_liber_heresius_redeploy_filter(self):
        self._assert_redeploy_filter(
            enhancement_id="000009130003",
            name="Liber Heresius",
            faction_id="AoI",
            description=(
                "INQUISITOR or MINISTORUM PRIEST model only. After both players have deployed their armies, "
                "select up to three AGENTS OF THE IMPERIUM units from your army and redeploy them. When doing so, "
                "you can set those units up in Strategic Reserves if you wish, regardless of how many units are already in Strategic Reserves."
            ),
            expected_filter="AGENTS OF THE IMPERIUM",
        )

    def test_solid_image_projection_unit_redeploy_filter(self):
        self._assert_redeploy_filter(
            enhancement_id="000008442004",
            name="Solid-image Projection Unit",
            faction_id="TAU",
            description=(
                "T'AU EMPIRE model only. After both players have deployed their armies, select up to three T'AU EMPIRE "
                "units from your army and redeploy them. When doing so, you can set those units up in Strategic Reserves "
                "if you wish, regardless of how many units are already in Strategic Reserves."
            ),
            expected_filter="T'AU EMPIRE",
        )

    def test_duplicitous_malediction_redeploy_filter(self):
        self._assert_redeploy_filter(
            enhancement_id="000010197004",
            name="Duplicitous Malediction",
            faction_id="TS",
            description=(
                "THOUSAND SONS or Lord of Change model only. After both players have deployed their armies, select up "
                "to three THOUSAND SONS units from your army and redeploy them. When doing so, you can set those units "
                "up in Strategic Reserves if you wish, regardless of how many units are already in Strategic Reserves."
            ),
            expected_filter="THOUSAND SONS",
        )

    def test_neuronode_redeploy_filter(self):
        self._assert_redeploy_filter(
            enhancement_id="000008417005",
            name="Neuronode",
            faction_id="TYR",
            description=(
                "TYRANIDS model only. After both players have deployed their armies, you can select up to three Vanguard "
                "Invader units from your army and redeploy all of those units. When doing so, any of those units can be "
                "placed into Strategic Reserves, regardless of how many units are already in Strategic Reserves."
            ),
            expected_filter="VANGUARD INVADER",
        )

    def test_kroot_ambush_requires_source_then_other_kroot(self):
        game, army, enemy_army, player, _enemy = _build_game(faction_id="TAU")
        source = _make_unit(
            "Kroot Trail Shaper",
            army,
            keywords=["CHARACTER", "KROOT"],
            faction_keywords=["T'AU EMPIRE"],
            x=0.0,
            y=0.0,
            abilities=[
                _Ability(
                    name="Kroot Ambush",
                    description=(
                        "After both players have deployed their armies, you can redeploy this model's unit and one other "
                        "friendly Kroot unit. When doing so, any of those units can be placed into Strategic Reserves, "
                        "regardless of how many units are already in Strategic Reserves."
                    ),
                )
            ],
        )
        other_kroot = _make_unit(
            "Kroot Carnivores",
            army,
            keywords=["INFANTRY", "KROOT"],
            faction_keywords=["T'AU EMPIRE"],
            x=6.0,
            y=0.0,
        )
        non_kroot = _make_unit(
            "Strike Team",
            army,
            keywords=["INFANTRY"],
            faction_keywords=["T'AU EMPIRE"],
            x=12.0,
            y=0.0,
        )
        enemy = _make_unit(
            "Enemy",
            enemy_army,
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            x=24.0,
            y=0.0,
        )

        army.units = [source, other_kroot, non_kroot]
        enemy_army.units = [enemy]
        game.map.units = [source, other_kroot, non_kroot, enemy]
        game.rebuild_entity_registry()

        has_redeploy, count, can_place_in_reserves = source.has_redeploy()
        self.assertTrue(has_redeploy)
        self.assertEqual(int(count), 2)
        self.assertTrue(can_place_in_reserves)
        cache = dict(getattr(source, "_ability_cache", {}) or {})
        self.assertEqual(list(cache.get("redeploy_filters", []) or []), ["KROOT"])
        self.assertTrue(bool(cache.get("redeploy_must_include_source_unit", False)))
        self.assertTrue(bool(cache.get("redeploy_require_exact_count", False)))

        game.execute_redeploy_units_phase()
        request_one = _find_redeploy_request(game, player_id=player.id, ability_name="Kroot Ambush")
        self.assertIsNotNone(request_one)

        first_target_ids = {
            str((dict(getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or ""))
            for opt in list(getattr(request_one, "options", []) or [])
            if str((dict(getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or ""))
        }
        source_id = str(get_entity_id(source) or "")
        other_kroot_id = str(get_entity_id(other_kroot) or "")
        non_kroot_id = str(get_entity_id(non_kroot) or "")
        self.assertEqual(first_target_ids, {source_id})

        first_option_id = _find_option_id(request_one, target_unit_id=source_id, action="strategic_reserves")
        self.assertTrue(bool(first_option_id))
        resolve_decision_command(game, request_one, first_option_id, player_id=player.id)

        request_two = _find_redeploy_request(game, player_id=player.id, ability_name="Kroot Ambush")
        self.assertIsNotNone(request_two)
        second_target_ids = {
            str((dict(getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or ""))
            for opt in list(getattr(request_two, "options", []) or [])
            if str((dict(getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or ""))
        }
        self.assertIn(other_kroot_id, second_target_ids)
        self.assertNotIn(source_id, second_target_ids)
        self.assertNotIn(non_kroot_id, second_target_ids)

        skip_options = [
            opt
            for opt in list(getattr(request_two, "options", []) or [])
            if str((dict(getattr(opt, "payload", {}) or {}).get("action", "") or "")).strip().lower() == "skip"
        ]
        self.assertEqual(skip_options, [])

        second_option_id = _find_option_id(request_two, target_unit_id=other_kroot_id, action="strategic_reserves")
        self.assertTrue(bool(second_option_id))
        resolve_decision_command(game, request_two, second_option_id, player_id=player.id)

        self.assertEqual(str(getattr(other_kroot, "reserve_status", "") or ""), "strategic_reserves")
        self.assertNotIn(other_kroot, list(getattr(game.map, "units", []) or []))


if __name__ == "__main__":
    unittest.main()
