import unittest
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET,
    DECISION_CHOOSE_QUARRY,
    DECISION_CONFIRM_YES_NO,
)
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.utility.model_base import Base, BaseType


class TestAeldariBatch1Abilities(unittest.TestCase):
    def _make_unit(self, name, army, *, abilities=None, keywords=None, faction_keywords=None):
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
        unit.possible_abilities = list(abilities or [])
        unit.status_effects = []
        unit.special_rules = {}
        unit.round_state = SimpleNamespace(num_lost_models_this_round=0, disembarked_from_transport_id="")
        unit.attached_leaders = []
        unit.attached_to = None
        unit.can_be_attached_to = []
        unit.embarked_in = None
        unit._ability_cache = {}
        unit._characteristic_modifiers = {}
        unit.is_alive = lambda: True
        unit.get_parent_army = lambda: army
        unit.get_attached_unit_root = lambda: unit
        unit.get_attached_unit_models = lambda: list(unit.models)
        unit.get_attached_unit_members = lambda: [unit]
        unit.get_models_for_collision = lambda: list(unit.models)
        unit.get_models_for_wound_allocation = lambda: list(unit.models)
        unit.is_in_reserves = lambda: False
        unit.has_any_keyword = lambda kw: any(
            str(kw or "").strip().upper() == str(k or "").strip().upper()
            for k in (unit.keywords + unit.faction_keywords)
        )
        unit.has_keyword = unit.has_any_keyword
        return unit

    def _make_model(self, name, unit, *, wounds: int = 1):
        model = Model(
            name=name,
            movement=6,
            toughness=4,
            save=3,
            wounds=int(wounds),
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        model.parent_unit = unit
        model.set_location(0.0, 0.0, 0.0, 0.0)
        return model

    def _resolve_yes(self, game, request, player):
        option_id = None
        for opt in list(request.options or []):
            if bool((opt.payload or {}).get("choice", False)):
                option_id = opt.option_id
                break
        self.assertIsNotNone(option_id)
        resolve_decision_command(game, request, option_id, player_id=player.id)

    def test_face_of_death_queues_battleshock_penalty(self):
        army = Army("Aeldari", detachment_type="Other")
        army.faction_id = "AE"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "SM"

        player = Player("Player", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0

        ability_desc = (
            "In your Shooting phase, after this model has shot, select one enemy unit hit by one or more of those attacks. "
            "That enemy unit must take a Battle-shock test, subtracting 1 from the result."
        )
        ability = Ability("Face of Death", "AE", ability_desc, "Datasheet", "")

        attacker_unit = self._make_unit("Death Jester", army, abilities=[ability], faction_keywords=["AELDARI"])
        attacker_model = self._make_model("Jester", attacker_unit)
        attacker_model.abilities = {"Face of Death": ability}
        attacker_unit.models = [attacker_model]
        army.units = [attacker_unit]

        target_unit = self._make_unit("Target", enemy_army)
        target_model = self._make_model("Target Model", target_unit)
        target_unit.models = [target_model]
        enemy_army.units = [target_unit]

        game.rebuild_entity_registry()

        game._on_unit_shooting_resolved_post_shoot_battleshock(
            attacker_unit=attacker_unit,
            hits_by_target={target_unit: 1},
        )

        pending = game.decision_queue.list()
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(request.decision_type, DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET)
        payload = request.options[0].payload or {}
        self.assertEqual(payload.get("battle_shock_test_modifier"), -1)

    def test_fire_support_disembark_wound_reroll(self):
        army = Army("Aeldari", detachment_type="Other")
        army.faction_id = "AE"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "SM"

        player = Player("Player", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0
        game.turn = 1

        ability_desc = (
            "In your Shooting phase, after this model has shot, select one enemy unit hit by one or more of those attacks, "
            "Until the end of the phase, each time a friendly model that disembarked from this Transport this turn makes an attack "
            "that targets that enemy unit, you can re-roll the Wound roll."
        )
        ability = Ability("Fire Support", "AE", ability_desc, "Datasheet", "")

        transport = self._make_unit("Falcon", army, abilities=[ability], faction_keywords=["AELDARI"])
        transport_model = self._make_model("Falcon Model", transport)
        transport_model.abilities = {"Fire Support": ability}
        transport.models = [transport_model]

        disembarked = self._make_unit("Disembarked", army, faction_keywords=["AELDARI"])
        disembarked_model = self._make_model("Passenger", disembarked)
        disembarked.models = [disembarked_model]
        disembarked.round_state.disembarked_from_transport_id = str(get_entity_id(transport) or "")

        army.units = [transport, disembarked]

        target_unit = self._make_unit("Target", enemy_army)
        target_model = self._make_model("Target Model", target_unit)
        target_unit.models = [target_model]
        enemy_army.units = [target_unit]

        game.rebuild_entity_registry()

        game._on_unit_shooting_resolved_post_shoot_disembark_wound_reroll(
            attacker_unit=transport,
            hits_by_target={target_unit: 1},
        )

        pending = game.decision_queue.list()
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(request.decision_type, DECISION_CHOOSE_QUARRY)
        resolve_decision_command(game, request, request.options[0].option_id, player_id=player.id)

        mods = disembarked.get_unit_wound_reroll_modifiers("ranged", target=target_unit)
        self.assertTrue(mods.get("reroll_wound_full"))

    def test_fleet_of_foot_fade_back_without_tokens(self):
        army = Army("Aeldari", detachment_type="Other")
        army.faction_id = "AE"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "SM"

        player = Player("Player", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0
        game.turn = 1

        ability_desc = (
            "This unit can perform the Fade Back Agile Manoeuvre without spending a Battle Focus token to do so. "
            "It can do so even if other units have done so in the same phase, and doing so does not prevent other units "
            "from performing the same Agile Manoeuvre in the same phase."
        )
        ability = Ability("Fleet of Foot", "AE", ability_desc, "Datasheet", "")
        battle_focus = Ability("Battle Focus", "AE", "", "Datasheet", "")

        unit = self._make_unit("Fleet Unit", army, abilities=[ability, battle_focus], faction_keywords=["ASURYANI"])
        unit.models = [self._make_model("Runner", unit)]
        army.units = [unit]

        bf = army.battle_focus
        bf.tokens = 0
        bf._maneuvers_used_this_phase = {bf.MANEUVER_FADE_BACK}

        candidates = bf.get_fade_back_candidates([unit], game)
        self.assertIn(unit, candidates)

        bf._maneuvers_used_this_phase = set()
        bf._units_used_this_phase = set()

        with patch("warhammer40k_ai.utility.dice.get_roll", return_value=1):
            bf.apply_reactive_maneuver(unit, bf.MANEUVER_FADE_BACK, game)

        self.assertEqual(bf.tokens, 0)
        self.assertNotIn(bf.MANEUVER_FADE_BACK, bf._maneuvers_used_this_phase)
        self.assertIn(bf._unit_id(unit), bf._units_used_this_phase)

    def test_hand_of_asuryan_applies_weapon_bonuses(self):
        army = Army("Aeldari", detachment_type="Other")
        army.faction_id = "AE"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "SM"

        player = Player("Player", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0

        ability_desc = (
            "Once per battle, when this model is selected to shoot, it can use this ability. "
            "If it does, until the end of the phase, its Bloody Twins weapon has a Damage characteristic of 3 "
            "and the [ANTI-INFANTRY 5+] and [DEVASTATING WOUNDS] abilities."
        )
        ability = Ability("Hand of Asuryan", "AE", ability_desc, "Datasheet", "")

        attacker_unit = self._make_unit("Autarch", army, abilities=[ability], faction_keywords=["AELDARI"])
        attacker_model = self._make_model("Autarch", attacker_unit)
        attacker_model.abilities = {"Hand of Asuryan": ability}
        attacker_unit.models = [attacker_model]
        army.units = [attacker_unit]

        target_unit = self._make_unit("Target", enemy_army)
        target_unit.models = [self._make_model("Target Model", target_unit)]
        enemy_army.units = [target_unit]

        game._on_shooting_targets_selected_hand_of_asuryan(
            attacking_unit=attacker_unit,
            target_units=[target_unit],
        )

        pending = game.decision_queue.list()
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(request.decision_type, DECISION_CONFIRM_YES_NO)
        self._resolve_yes(game, request, player)

        dmg, _source = attacker_model.get_temporary_weapon_damage_override("Bloody Twins")
        self.assertEqual(dmg, 3)
        keywords = {k.get("keyword") for k in attacker_model.get_temporary_weapon_keyword_bonuses("Bloody Twins")}
        self.assertIn("ANTI-INFANTRY 5+", keywords)
        self.assertIn("DEVASTATING WOUNDS", keywords)
        self.assertTrue(attacker_model.has_used_once_per_battle("hand_of_asuryan"))

    def test_harvester_of_souls_marks_and_applies_mortals(self):
        army = Army("Aeldari", detachment_type="Other")
        army.faction_id = "AE"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "SM"

        player = Player("Player", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0
        game.turn = 1

        ability_desc = (
            "While this model is leading a unit, in your Shooting phase, after selecting targets for that unit’s attacks, "
            "if every attack targets the same unit, roll one D6 for the target unit and one D6 for every other enemy unit "
            "within 3\" of the target unit. On a 5+, the unit being rolled for is struck by explosive debris; after resolving "
            "all of that unit’s attacks against the target unit, each unit struck by explosive debris suffers D3 mortal wounds."
        )
        ability = Ability("Harvester of Souls", "AE", ability_desc, "Datasheet", "")

        leader = self._make_unit("Leader", army, abilities=[ability], faction_keywords=["AELDARI"])
        leader.can_be_attached_to = ["Unit"]

        attacker_unit = self._make_unit("Unit", army, faction_keywords=["AELDARI"])
        attacker_unit.models = [self._make_model("Shooter", attacker_unit)]
        attacker_unit.attached_leaders = [leader]
        leader.attached_to = attacker_unit

        army.units = [attacker_unit, leader]

        target_unit = self._make_unit("Target", enemy_army)
        target_unit.models = [self._make_model("Target Model", target_unit)]
        target_unit.models[0].set_location(0.0, 0.0, 0.0, 0.0)

        nearby_unit = self._make_unit("Nearby", enemy_army)
        nearby_unit.models = [self._make_model("Nearby Model", nearby_unit)]
        nearby_unit.models[0].set_location(2.0, 0.0, 0.0, 0.0)

        enemy_army.units = [target_unit, nearby_unit]

        game.map.units = [attacker_unit, target_unit, nearby_unit]
        game.rebuild_entity_registry()

        def fake_roll(spec):
            if str(spec).upper() == "D6":
                return 6
            if str(spec).upper() == "D3":
                return 2
            return 1

        with patch("warhammer40k_ai.engine.game.get_roll", side_effect=fake_roll):
            game._on_shooting_targets_selected_harvester_of_souls(
                attacking_unit=attacker_unit,
                target_units=[target_unit],
            )

            pending_ids = attacker_unit.special_rules.get("harvester_of_souls_pending_ids")
            self.assertTrue(pending_ids)

            applied = []

            def _record_mortals(unit, amount, game_map=None):
                applied.append((unit, amount))

            attacker_unit._apply_mortal_wounds_to_unit = _record_mortals
            game._on_unit_shooting_resolved_harvester_of_souls(attacker_unit=attacker_unit)

        self.assertEqual(len(applied), 2)
        self.assertEqual({amt for _u, amt in applied}, {2})

    def test_herald_of_ynnead_selection_and_reroll(self):
        army = Army("Aeldari", detachment_type="Other")
        army.faction_id = "AE"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "SM"

        player = Player("Player", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
        game.phase = BattleRoundPhases.FIGHT_PHASE
        game.current_player_index = 0
        game.turn = 1

        ability_desc = (
            "At the start of the Fight phase, select one enemy unit within Engagement Range of this model. "
            "Until the end of the phase, each time a friendly AELDARI model makes an attack that targets that unit, "
            "you can re-roll a Wound roll of 1."
        )
        ability = Ability("Herald of Ynnead", "AE", ability_desc, "Datasheet", "")

        attacker_unit = self._make_unit("Visarch", army, abilities=[ability], faction_keywords=["AELDARI"])
        attacker_model = self._make_model("Visarch", attacker_unit)
        attacker_model.abilities = {"Herald of Ynnead": ability}
        attacker_model.set_location(0.0, 0.0, 0.0, 0.0)
        attacker_unit.models = [attacker_model]
        army.units = [attacker_unit]

        enemy_unit = self._make_unit("Enemy", enemy_army)
        enemy_model = self._make_model("Enemy Model", enemy_unit)
        enemy_model.set_location(0.5, 0.0, 0.0, 0.0)
        enemy_unit.models = [enemy_model]
        enemy_army.units = [enemy_unit]

        game.map.units = [attacker_unit, enemy_unit]
        game.rebuild_entity_registry()

        game._on_phase_start_herald_of_ynnead(phase=game.phase)

        pending = game.decision_queue.list()
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(request.decision_type, DECISION_CHOOSE_QUARRY)
        resolve_decision_command(game, request, request.options[0].option_id, player_id=player.id)

        mods = attacker_unit.get_unit_wound_reroll_modifiers("melee", target=enemy_unit)
        self.assertTrue(mods.get("reroll_wound_ones"))

    def test_misfortune_applies_wound_penalty(self):
        army = Army("Aeldari", detachment_type="Other")
        army.faction_id = "AE"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "SM"

        player = Player("Player", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
        game.phase = BattleRoundPhases.MOVEMENT_PHASE
        game.current_player_index = 0
        game.turn = 1

        ability_desc = (
            "At the end of your Movement phase, select one enemy unit within 18\" of and visible to this model. "
            "Until the start of your next Command phase, each time a model in that unit makes an attack, subtract 1 from the Wound roll. "
            "Each unit can only be selected for this ability once per turn."
        )
        ability = Ability("Misfortune (Psychic)", "AE", ability_desc, "Datasheet", "")

        source_unit = self._make_unit("Shadowseer", army, abilities=[ability], faction_keywords=["AELDARI"])
        source_model = self._make_model("Shadowseer", source_unit)
        source_model.abilities = {"Misfortune (Psychic)": ability}
        source_model.set_location(0.0, 0.0, 0.0, 0.0)
        source_unit.models = [source_model]
        source_unit._has_line_of_sight_to_target = lambda m, t, gm: True
        army.units = [source_unit]

        enemy_unit = self._make_unit("Enemy", enemy_army)
        enemy_model = self._make_model("Enemy Model", enemy_unit)
        enemy_model.set_location(10.0, 0.0, 0.0, 0.0)
        enemy_unit.models = [enemy_model]
        enemy_army.units = [enemy_unit]

        game.map.units = [source_unit, enemy_unit]
        game.rebuild_entity_registry()

        game._on_phase_end_misfortune(player=player, phase=game.phase)

        pending = game.decision_queue.list()
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(request.decision_type, DECISION_CHOOSE_QUARRY)
        resolve_decision_command(game, request, request.options[0].option_id, player_id=player.id)

        self.assertTrue(enemy_unit.special_rules.get("misfortune_active"))
        mods = enemy_unit.get_unit_wound_reroll_modifiers("melee", target=source_unit)
        self.assertEqual(mods.get("wound"), -1)

    def test_monofilament_web_applies_pinned(self):
        army = Army("Aeldari", detachment_type="Other")
        army.faction_id = "AE"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "SM"

        player = Player("Player", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0
        game.turn = 1

        ability_desc = (
            "In your Shooting phase, after this model has shot, if one or more of those attacks made with its doomweaver scored a hit "
            "against an enemy unit, until the start of your next turn, that enemy unit is pinned. While a unit is pinned, subtract 2 from "
            "that unit’s Move characteristic and subtract 2 from Charge rolls made for it."
        )
        ability = Ability("Monofilament Web", "AE", ability_desc, "Datasheet", "")

        attacker_unit = self._make_unit("Support Weapon", army, abilities=[ability], faction_keywords=["AELDARI"])
        attacker_model = self._make_model("Doomweaver", attacker_unit)
        attacker_model.abilities = {"Monofilament Web": ability}
        attacker_unit.models = [attacker_model]
        army.units = [attacker_unit]

        target_unit = self._make_unit("Target", enemy_army)
        target_model = self._make_model("Target Model", target_unit)
        target_unit.models = [target_model]
        enemy_army.units = [target_unit]

        game.rebuild_entity_registry()

        weapon_key = attacker_unit._normalize_keyword_phrase("doomweaver")
        hit_models_by_target_weapon = {target_unit: {weapon_key: {attacker_model}}}

        game._on_unit_shooting_resolved_post_shoot_pinned(
            attacker_unit=attacker_unit,
            hits_by_target={target_unit: 1},
            hit_models_by_target_weapon=hit_models_by_target_weapon,
        )

        sr = target_unit.special_rules
        self.assertTrue(sr.get("pinned_active"))
        self.assertEqual(sr.get("pinned_move_penalty"), -2)
        self.assertEqual(sr.get("pinned_charge_penalty"), -2)

    def test_piratical_raiders_quarry_and_keywords(self):
        army = Army("Aeldari", detachment_type="Other")
        army.faction_id = "AE"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "SM"

        player = Player("Player", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
        game.turn = 1

        ability_desc = (
            "At the start of the battle, select one unit from your opponent’s army. "
            "Weapons equipped by models in this unit have the [LETHAL HITS] and [PRECISION] abilities while targeting that unit."
        )
        ability = Ability("Piratical Raiders", "AE", ability_desc, "Datasheet", "")

        source_unit = self._make_unit("Corsairs", army, abilities=[ability], faction_keywords=["AELDARI"])
        source_model = self._make_model("Corsair", source_unit)
        source_model.abilities = {"Piratical Raiders": ability}
        source_unit.models = [source_model]
        army.units = [source_unit]

        target_unit = self._make_unit("Target", enemy_army)
        target_unit.models = [self._make_model("Target Model", target_unit)]
        enemy_army.units = [target_unit]

        game.rebuild_entity_registry()
        army.on_battle_round_start(1)

        pending = game.decision_queue.list()
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(request.decision_type, DECISION_CHOOSE_QUARRY)
        resolve_decision_command(game, request, request.options[0].option_id, player_id=player.id)

        bonuses = source_unit.get_model_weapon_keyword_bonuses(
            model=source_model,
            weapon_name="shuriken rifle",
            target=target_unit,
        )
        self.assertTrue(bonuses.get("lethal_hits"))
        self.assertTrue(bonuses.get("precision"))

    def test_point_blank_devastation_rerolls_attacks(self):
        army = Army("Aeldari", detachment_type="Other")
        army.faction_id = "AE"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "SM"

        player = Player("Player", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
        game.turn = 1
        game.map.roll_reroll_provider = lambda **_kwargs: True

        ability_desc = (
            "Each time this model’s heavy wraithcannon or suncannon targets a unit within half range, "
            "you can re-roll the dice to determine the number of attacks made."
        )
        ability = Ability("Point-blank Devastation", "AE", ability_desc, "Datasheet", "")

        unit = self._make_unit("Wraithknight", army, abilities=[ability], faction_keywords=["AELDARI"])
        model = self._make_model("Wraithknight", unit)
        model.abilities = {"Point-blank Devastation": ability}
        unit.models = [model]
        army.units = [unit]

        target_unit = self._make_unit("Target", enemy_army)
        target_unit.models = [self._make_model("Target Model", target_unit)]
        enemy_army.units = [target_unit]

        model.return_closest_model_in_unit = lambda _unit: (target_unit.models[0], 10.0)

        wargear = Wargear(
            {
                "name": "Heavy Wraithcannon",
                "type": "Ranged",
                "range": "24",
                "A": "D6",
                "BS_WS": "3+",
                "S": "12",
                "AP": "-3",
                "D": "D6",
                "description": "",
            }
        )
        profile = wargear.profiles["default"]

        with patch("warhammer40k_ai.utility.dice.get_dice_roll", side_effect=[1, 6]):
            info = profile.preview_attack_count(target_unit, model, publish_roll_event=False)

        self.assertEqual(info.dice_rolls, [6])
        self.assertTrue(any("Point-blank Devastation" in s for s in info.special_modifiers))


if __name__ == "__main__":
    unittest.main()
