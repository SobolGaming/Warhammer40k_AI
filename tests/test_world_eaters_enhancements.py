import unittest
from types import SimpleNamespace
from unittest.mock import patch


class TestWorldEatersEnhancements(unittest.TestCase):
    class _MockDatasheet:
        def __init__(
            self,
            name,
            *,
            faction_name="World Eaters",
            keywords=None,
            faction_keywords=None,
            cost=100,
        ):
            self.name = name
            self.faction_data = {"name": faction_name}
            self.keywords = list(keywords or [])
            self.faction_keywords = list(faction_keywords or [])
            self.datasheets_unit_composition = [{"description": "1 Test Model"}]
            self.datasheets_models_cost = [{"description": "1 model", "cost": cost}]
            self.datasheets_models = [
                {
                    "M": "6",
                    "T": "4",
                    "Sv": "6",
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
            self.attached_to = []

    def _make_unit(self, name, *, faction_name="World Eaters", keywords=None, faction_keywords=None, cost=100):
        from warhammer40k_ai.units.unit import Unit

        datasheet = self._MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            cost=cost,
        )
        return Unit(datasheet)
    def _hit_result_stub(self, *, hit: bool = False):
        return {
            "roll": 1,
            "needed": 3,
            "base_skill": 3,
            "modifiers": [],
            "final_needed": 3,
            "hit": hit,
            "special_effects": [],
        }

    def _make_melee_profile(self, *, attacks: str = "1", damage: str = "1", keywords: str = ""):
        from warhammer40k_ai.units.wargear import Wargear

        data = {
            "range": "Melee",
            "A": attacks,
            "BS_WS": "3",
            "S": "4",
            "AP": "0",
            "D": damage,
            "description": keywords,
            "type": "Melee",
            "name": "Test Weapon",
        }
        parent = Wargear(data)
        return parent.profiles["default"]

    def test_berzerker_glaive_melee_attacks_and_damage(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.rules.enhancement import Enhancement
        from warhammer40k_ai.units.model import Model
        from warhammer40k_ai.utility.model_base import Base, BaseType

        army = Army("World Eaters", "Berzerker Warband")
        army.faction_id = "WE"
        unit = SimpleNamespace(
            special_rules={},
            models=[],
            possible_abilities=[],
            abilities=[],
            round_state=SimpleNamespace(remained_stationary_this_round=False, charged_this_round=False),
        )
        unit.get_parent_army = lambda: army
        army.units = [unit]

        Enhancement(
            id="000008432002",
            name="Berzerker Glaive",
            faction_id="WE",
            detachment="Berzerker Warband",
            points=35,
            description="",
        ).apply_to_unit(unit)

        profile = self._make_melee_profile(attacks="1", damage="1")
        attacker_model = Model(
            name="Attacker",
            movement=6,
            toughness=4,
            save=3,
            wounds=5,
            leadership=6,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        attacker_model.set_parent_unit(unit)

        target_model_stub = Model(
            name="Target",
            movement=6,
            toughness=4,
            save=3,
            wounds=5,
            leadership=6,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        target = SimpleNamespace(
            name="Target",
            toughness=4,
            models=[target_model_stub],
        )
        target.get_attached_unit_models = lambda: list(target.models)

        with patch.object(type(profile), "_hit_target_with_tracking", return_value=self._hit_result_stub()):
            result = profile.attack(target, attacker_model, game_map=None)

        self.assertEqual(int(result.attacks_rolled), 2)
        self.assertTrue(any("Berzerker Glaive" in m for m in (result.attacks_special_modifiers or [])))

        target_unit = SimpleNamespace(
            special_rules={},
            models=[],
            has_feel_no_pain=lambda: [],
            damaged_profile=None,
            damaged_profile_desc=None,
        )
        target_model = Model(
            name="Target",
            movement=6,
            toughness=4,
            save=3,
            wounds=5,
            leadership=6,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        target_model.set_parent_unit(target_unit)
        target_unit.models = [target_model]

        before = target_model.wounds
        profile._damage_target_with_tracking(
            target_model,
            attacker_model,
            {"below_half_distance": False, "mortal_wound": False},
            game_map=None,
        )
        self.assertEqual(target_model.wounds, before - 2)

    def test_berzerker_glaive_excludes_extra_attacks(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.rules.enhancement import Enhancement
        from warhammer40k_ai.units.model import Model
        from warhammer40k_ai.utility.model_base import Base, BaseType

        army = Army("World Eaters", "Berzerker Warband")
        army.faction_id = "WE"
        unit = SimpleNamespace(
            special_rules={},
            models=[],
            possible_abilities=[],
            abilities=[],
            round_state=SimpleNamespace(remained_stationary_this_round=False, charged_this_round=False),
        )
        unit.get_parent_army = lambda: army
        army.units = [unit]

        Enhancement(
            id="000008432002",
            name="Berzerker Glaive",
            faction_id="WE",
            detachment="Berzerker Warband",
            points=35,
            description="",
        ).apply_to_unit(unit)

        profile = self._make_melee_profile(attacks="1", damage="1", keywords="Extra Attacks")
        attacker_model = Model(
            name="Attacker",
            movement=6,
            toughness=4,
            save=3,
            wounds=5,
            leadership=6,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        attacker_model.set_parent_unit(unit)

        target_model_stub = Model(
            name="Target",
            movement=6,
            toughness=4,
            save=3,
            wounds=5,
            leadership=6,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        target = SimpleNamespace(
            name="Target",
            toughness=4,
            models=[target_model_stub],
        )
        target.get_attached_unit_models = lambda: list(target.models)

        with patch.object(type(profile), "_hit_target_with_tracking", return_value=self._hit_result_stub()):
            result = profile.attack(target, attacker_model, game_map=None)

        self.assertEqual(int(result.attacks_rolled), 1)
        self.assertFalse(any("Berzerker Glaive" in m for m in (result.attacks_special_modifiers or [])))

        target_unit = SimpleNamespace(
            special_rules={},
            models=[],
            has_feel_no_pain=lambda: [],
            damaged_profile=None,
            damaged_profile_desc=None,
        )
        target_model = Model(
            name="Target",
            movement=6,
            toughness=4,
            save=3,
            wounds=5,
            leadership=6,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        target_model.set_parent_unit(target_unit)
        target_unit.models = [target_model]

        before = target_model.wounds
        profile._damage_target_with_tracking(
            target_model,
            attacker_model,
            {"below_half_distance": False, "mortal_wound": False},
            game_map=None,
        )
        self.assertEqual(target_model.wounds, before - 1)

    def test_battle_lust_reroll_and_bonus(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.rules.enhancement import Enhancement
        from warhammer40k_ai.units.unit import Unit
        from warhammer40k_ai.rules.blessings_of_khorne import BlessingsOfKhorneManager
        from warhammer40k_ai.engine.game import Game, Battlefield

        army = Army("World Eaters", "Berzerker Warband")
        army.faction_id = "WE"
        unit = SimpleNamespace(
            special_rules={},
            possible_abilities=[],
            abilities=[],
            enhancement=None,
        )
        unit.get_parent_army = lambda: army
        Enhancement(
            id="000008432005",
            name="Battle-lust",
            faction_id="WE",
            detachment="Berzerker Warband",
            points=10,
            description="",
        ).apply_to_unit(unit)

        self.assertTrue(Unit.can_reroll_charge_roll(unit))

        battlefield = Battlefield(width=44, height=30)
        game = Game(battlefield, players=[])
        player = SimpleNamespace(game=game, name="P1", id="P1")
        army.player = player
        mgr = BlessingsOfKhorneManager()
        mgr.on_battle_round_start(1)
        mgr.active_blessing_keys.add("UNBRIDLED_BLOODLUST")
        army.blessings_of_khorne = mgr

        modified = game._apply_charge_modifiers(unit, 6)
        self.assertEqual(int(modified), 7)

    def test_favoured_of_khorne_rerolls_available(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.rules.enhancement import Enhancement
        from warhammer40k_ai.rules.blessings_of_khorne import BlessingsOfKhorneManager

        army = Army("World Eaters", "Berzerker Warband")
        army.faction_id = "WE"
        unit = SimpleNamespace(
            special_rules={},
            enhancement=None,
            deployed=True,
            reserve_status="deployed",
        )
        unit.is_alive = lambda: True
        unit.get_parent_army = lambda: army
        army.units = [unit]

        Enhancement(
            id="000008432004",
            name="Favoured of Khorne",
            faction_id="WE",
            detachment="Berzerker Warband",
            points=15,
            description="",
        ).apply_to_unit(unit)
        unit.enhancement = SimpleNamespace(name="Favoured of Khorne")

        mgr = BlessingsOfKhorneManager()
        self.assertEqual(int(mgr.favoured_of_khorne_rerolls_for_army(army)), 2)

    def test_helm_of_brazen_ire_reduces_damage(self):
        from warhammer40k_ai.rules.enhancement import Enhancement

        unit = SimpleNamespace(special_rules={}, models=[])
        Enhancement(
            id="000008432003",
            name="Helm of Brazen Ire",
            faction_id="WE",
            detachment="Berzerker Warband",
            points=30,
            description="Each time an attack is allocated to the bearer, subtract 1 from the Damage characteristic of that attack.",
        ).apply_to_unit(unit)

        self.assertEqual(int(unit.special_rules.get("enhancement_reduce_damage_taken", 0) or 0), 1)

    def test_blood_forged_armour_save_and_btp_on_death(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.rules.enhancement import Enhancement
        from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
        from warhammer40k_ai.roster.player import Player, PlayerControl

        army = Army("World Eaters", "Khorne Daemonkin")
        army.faction_id = "WE"
        unit = self._make_unit(
            "Blood Legion",
            keywords=["BLOOD LEGIONS"],
            faction_keywords=["WORLD EATERS"],
        )
        army.add_unit(unit)

        Enhancement(
            id="000010078003",
            name="Blood-forged Armour",
            faction_id="WE",
            detachment="Khorne Daemonkin",
            points=20,
            description="The bearer has a Save characteristic of 2+. If the bearer is destroyed, you gain 1 Blood Tithe point.",
        ).apply_to_unit(unit)

        self.assertEqual(int(unit.models[0].save), 2)

        enemy_army = Army("Enemy", "Other")
        enemy_army.faction_id = "EN"
        enemy = self._make_unit("Enemy", faction_name="Enemy", faction_keywords=["ENEMY"])
        enemy_army.add_unit(enemy)

        bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
        game = Game(bf, players=[
            Player("P1", control=PlayerControl.LOCAL, army=army),
            Player("P2", control=PlayerControl.REMOTE, army=enemy_army),
        ])

        game.event_system.publish("unit_destroyed", unit=unit, destroyed_by_unit=enemy)
        self.assertEqual(int(army.world_eaters_detachments.blood_tithe_points), 1)

    def test_blade_of_endless_bloodshed_auto_btp_on_melee_kill(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.rules.enhancement import Enhancement
        from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
        from warhammer40k_ai.roster.player import Player, PlayerControl

        army = Army("World Eaters", "Khorne Daemonkin")
        army.faction_id = "WE"
        unit = self._make_unit(
            "Champion",
            keywords=["WORLD EATERS"],
            faction_keywords=["WORLD EATERS"],
        )
        army.add_unit(unit)

        Enhancement(
            id="000010078005",
            name="Blade of Endless Bloodshed",
            faction_id="WE",
            detachment="Khorne Daemonkin",
            points=15,
            description="Add 1 to the Attacks, Strength and Damage characteristics of the bearers melee weapons.",
        ).apply_to_unit(unit)

        self.assertEqual(int(unit.special_rules.get("enhancement_melee_attacks_bonus", 0) or 0), 1)
        self.assertEqual(int(unit.special_rules.get("enhancement_melee_strength_bonus", 0) or 0), 1)
        self.assertEqual(int(unit.special_rules.get("enhancement_melee_damage_bonus", 0) or 0), 1)

        enemy_army = Army("Enemy", "Other")
        enemy_army.faction_id = "EN"
        enemy = self._make_unit("Enemy", faction_name="Enemy", faction_keywords=["ENEMY"])
        enemy_army.add_unit(enemy)

        bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
        game = Game(bf, players=[
            Player("P1", control=PlayerControl.LOCAL, army=army),
            Player("P2", control=PlayerControl.REMOTE, army=enemy_army),
        ])

        weapon_profile = SimpleNamespace(parent_wargear=SimpleNamespace(is_melee=lambda: True))
        with patch("warhammer40k_ai.utility.dice.get_roll", return_value=1):
            game.event_system.publish(
                "unit_destroyed",
                unit=enemy,
                destroyed_by_unit=unit,
                destroyed_by_weapon_profile=weapon_profile,
            )

        self.assertEqual(int(army.world_eaters_detachments.blood_tithe_points), 1)

    def test_murderous_onslaught_prevents_overwatch_after_disembark(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.rules.enhancement import Enhancement
        from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
        from warhammer40k_ai.roster.player import Player, PlayerControl

        army = Army("World Eaters", "Goretrack Onslaught")
        army.faction_id = "WE"
        enemy_army = Army("Enemy", "Other")
        enemy_army.faction_id = "EN"

        transport = self._make_unit(
            "Test Transport",
            keywords=["Transport", "Dedicated Transport", "Vehicle"],
            faction_keywords=["WORLD EATERS"],
        )
        passenger = self._make_unit(
            "Test Squad",
            keywords=["Infantry"],
            faction_keywords=["WORLD EATERS"],
        )
        enemy = self._make_unit(
            "Enemy",
            faction_name="Enemy",
            keywords=["Infantry"],
            faction_keywords=["ENEMY"],
        )

        bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
        game = Game(
            bf,
            players=[
                Player("P1", control=PlayerControl.LOCAL, army=army),
                Player("P2", control=PlayerControl.REMOTE, army=enemy_army),
            ],
        )

        army.add_unit(transport)
        army.add_unit(passenger)
        enemy_army.add_unit(enemy)

        transport.transport_capacity = 10

        enh = Enhancement(
            id="000010086002",
            name="Murderous Onslaught",
            faction_id="WE",
            detachment="Goretrack Onslaught",
            points=20,
            description="",
        )
        passenger.enhancement = enh
        enh.apply_to_unit(passenger)

        transport.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        enemy.models[0].set_location(10.0, 0.0, 0.0, 0.0)
        game.map.place_unit(transport)
        game.map.place_unit(enemy)

        transport.add_passenger(passenger, game_map=game.map)
        passenger.round_state.embarked_this_round = False
        game.current_player_index = 0

        ok = passenger.disembark(game_map=game.map, transport_unit=transport, current_turn=1)
        self.assertTrue(ok)
        self.assertTrue(passenger.is_overwatch_prevented_against(enemy, game=game))

    def test_aggressive_deployment_grants_scouts_to_dedicated_transport(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.rules.enhancement import Enhancement
        from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
        from warhammer40k_ai.roster.player import Player, PlayerControl

        army = Army("World Eaters", "Goretrack Onslaught")
        army.faction_id = "WE"
        enemy_army = Army("Enemy", "Other")
        enemy_army.faction_id = "EN"

        transport = self._make_unit(
            "Test Transport",
            keywords=["Transport", "Dedicated Transport", "Vehicle"],
            faction_keywords=["WORLD EATERS"],
        )
        passenger = self._make_unit(
            "Bearer",
            keywords=["Infantry", "Character"],
            faction_keywords=["WORLD EATERS"],
        )

        bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
        game = Game(
            bf,
            players=[
                Player("P1", control=PlayerControl.LOCAL, army=army),
                Player("P2", control=PlayerControl.REMOTE, army=enemy_army),
            ],
        )

        army.add_unit(transport)
        army.add_unit(passenger)

        transport.transport_capacity = 10

        enh = Enhancement(
            id="000010086003",
            name="Aggressive Deployment",
            faction_id="WE",
            detachment="Goretrack Onslaught",
            points=20,
            description="",
        )
        passenger.enhancement = enh
        enh.apply_to_unit(passenger)

        transport.deployed = False
        passenger.deployed = False
        passenger.embark(transport, game_map=game.map)

        has_scout, distance = transport.has_scout()
        self.assertTrue(has_scout)
        self.assertEqual(float(distance), 9.0)

    def test_unleash_hell_selects_vehicle_and_marks(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.rules.enhancement import Enhancement
        from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
        from warhammer40k_ai.engine.phase import BattleRoundPhases
        from warhammer40k_ai.engine.decision_kinds import DECISION_SELECT_UNLEASH_HELL_VEHICLE
        from warhammer40k_ai.roster.player import Player, PlayerControl
        from warhammer40k_ai.utility.decision_utils import resolve_decision_command
        from warhammer40k_ai.utility.entity_ids import get_entity_id

        army = Army("World Eaters", "Goretrack Onslaught")
        army.faction_id = "WE"
        enemy_army = Army("Enemy", "Other")
        enemy_army.faction_id = "EN"

        bearer = self._make_unit(
            "Bearer",
            keywords=["Infantry", "Character"],
            faction_keywords=["WORLD EATERS"],
        )
        vehicle = self._make_unit(
            "Vehicle",
            keywords=["Vehicle"],
            faction_keywords=["WORLD EATERS"],
        )

        bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
        game = Game(
            bf,
            players=[
                Player("P1", control=PlayerControl.LOCAL, army=army),
                Player("P2", control=PlayerControl.REMOTE, army=enemy_army),
            ],
        )

        army.add_unit(bearer)
        army.add_unit(vehicle)
        game.rebuild_entity_registry()

        bearer.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        vehicle.models[0].set_location(5.0, 0.0, 0.0, 0.0)
        game.map.place_unit(bearer)
        game.map.place_unit(vehicle)
        bearer.deployed = True
        vehicle.deployed = True
        bearer.reserve_status = "deployed"
        vehicle.reserve_status = "deployed"

        enh = Enhancement(
            id="000010086004",
            name="Unleash Hell",
            faction_id="WE",
            detachment="Goretrack Onslaught",
            points=20,
            description="",
        )
        bearer.enhancement = enh
        enh.apply_to_unit(bearer)

        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game._on_phase_start_world_eaters_enhancements(player=game.get_current_player(), phase=game.phase)

        requests = [
            req for req in game.decision_queue.list()
            if str(getattr(req, "decision_type", "")) == DECISION_SELECT_UNLEASH_HELL_VEHICLE
        ]
        self.assertEqual(len(requests), 1)
        request = requests[0]

        vid = str(get_entity_id(vehicle) or "")
        option_id = None
        for opt in list(getattr(request, "options", []) or []):
            payload = dict(getattr(opt, "payload", {}) or {})
            if str(payload.get("unit_id", "") or "") == vid:
                option_id = opt.option_id
                break
        self.assertTrue(option_id)

        resolve_decision_command(game, request, option_id, player_id=getattr(game.get_current_player(), "id", None))
        sr = getattr(vehicle, "special_rules", {})
        self.assertTrue(bool(sr.get("unleash_hell_active")))
        self.assertEqual(str(sr.get("unleash_hell_owner", "")), str(game.get_current_player().id))
        self.assertEqual(str(sr.get("unleash_hell_expires_phase", "")), "SHOOTING_PHASE")

    def test_unleash_hell_rejects_out_of_range_target(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.rules.enhancement import Enhancement
        from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
        from warhammer40k_ai.engine.phase import BattleRoundPhases
        from warhammer40k_ai.engine.decision_kinds import DECISION_SELECT_UNLEASH_HELL_VEHICLE
        from warhammer40k_ai.roster.player import Player, PlayerControl
        from warhammer40k_ai.utility.decision_utils import resolve_decision_command
        from warhammer40k_ai.utility.entity_ids import get_entity_id

        army = Army("World Eaters", "Goretrack Onslaught")
        army.faction_id = "WE"
        enemy_army = Army("Enemy", "Other")
        enemy_army.faction_id = "EN"

        bearer = self._make_unit(
            "Bearer",
            keywords=["Infantry", "Character"],
            faction_keywords=["WORLD EATERS"],
        )
        vehicle = self._make_unit(
            "Vehicle",
            keywords=["Vehicle"],
            faction_keywords=["WORLD EATERS"],
        )

        bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
        game = Game(
            bf,
            players=[
                Player("P1", control=PlayerControl.LOCAL, army=army),
                Player("P2", control=PlayerControl.REMOTE, army=enemy_army),
            ],
        )

        army.add_unit(bearer)
        army.add_unit(vehicle)
        game.rebuild_entity_registry()

        bearer.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        vehicle.models[0].set_location(5.0, 0.0, 0.0, 0.0)
        game.map.place_unit(bearer)
        game.map.place_unit(vehicle)
        bearer.deployed = True
        vehicle.deployed = True
        bearer.reserve_status = "deployed"
        vehicle.reserve_status = "deployed"

        enh = Enhancement(
            id="000010086004",
            name="Unleash Hell",
            faction_id="WE",
            detachment="Goretrack Onslaught",
            points=20,
            description="",
        )
        bearer.enhancement = enh
        enh.apply_to_unit(bearer)

        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game._on_phase_start_world_eaters_enhancements(player=game.get_current_player(), phase=game.phase)

        requests = [
            req for req in game.decision_queue.list()
            if str(getattr(req, "decision_type", "")) == DECISION_SELECT_UNLEASH_HELL_VEHICLE
        ]
        self.assertEqual(len(requests), 1)
        request = requests[0]

        vid = str(get_entity_id(vehicle) or "")
        option_id = None
        for opt in list(getattr(request, "options", []) or []):
            payload = dict(getattr(opt, "payload", {}) or {})
            if str(payload.get("unit_id", "") or "") == vid:
                option_id = opt.option_id
                break
        self.assertTrue(option_id)

        vehicle.models[0].set_location(20.0, 0.0, 0.0, 0.0)

        result = resolve_decision_command(game, request, option_id, player_id=getattr(game.get_current_player(), "id", None))
        self.assertFalse(bool(getattr(result, "ok", False)))
        self.assertTrue(any("out of range" in str(err).lower() for err in getattr(result, "errors", ()) or ()))

    def test_infernal_infusion_grants_fight_first_flag(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.rules.enhancement import Enhancement

        army = Army("World Eaters", "Goretrack Onslaught")
        army.faction_id = "WE"
        unit = SimpleNamespace(
            special_rules={},
            models=[],
            possible_abilities=[],
            abilities=[],
            round_state=SimpleNamespace(remained_stationary_this_round=False, charged_this_round=False),
        )
        unit.get_parent_army = lambda: army
        army.units = [unit]

        Enhancement(
            id="000010086005",
            name="Infernal Infusion",
            faction_id="WE",
            detachment="Goretrack Onslaught",
            points=20,
            description="Once per battle, at the start of the Fight phase, the bearer can use this Enhancement. If it does, until the end of the phase, the bearer’s unit has the Fights First ability.",
        ).apply_to_unit(unit)

        self.assertTrue(bool(unit.special_rules.get("enhancement_fight_first_once_per_battle")))

    def test_chosen_of_the_blood_god_extends_aura_range(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.rules.enhancement import Enhancement
        from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
        from warhammer40k_ai.roster.player import Player, PlayerControl
        from warhammer40k_ai.utility.aura_effects import get_aura_advance_charge_roll_modifiers

        army = Army("World Eaters", "Cult of Blood")
        army.faction_id = "WE"
        enemy_army = Army("Enemy", "Other")
        enemy_army.faction_id = "EN"

        bearer = self._make_unit(
            "Bearer",
            keywords=["Monster", "Character"],
            faction_keywords=["WORLD EATERS"],
        )
        target = self._make_unit(
            "Target",
            keywords=["Jakhals"],
            faction_keywords=["WORLD EATERS"],
        )
        bearer.possible_abilities = [
            SimpleNamespace(
                name="War Cry (Aura)",
                description='While a friendly WORLD EATERS unit is within 6" of this model, add 1 to Advance and Charge rolls made for that unit.',
                type="Datasheet",
                parameter="",
            )
        ]

        army.add_unit(bearer)
        army.add_unit(target)

        game = Game(
            Battlefield(BattlefieldSize.STRIKE_FORCE),
            players=[
                Player("P1", control=PlayerControl.LOCAL, army=army),
                Player("P2", control=PlayerControl.REMOTE, army=enemy_army),
            ],
        )

        bearer.models[0].set_location(10.0, 10.0, 0.0, 0.0)
        target.models[0].set_location(19.0, 10.0, 0.0, 0.0)
        self.assertTrue(game.map.place_unit(bearer))
        self.assertTrue(game.map.place_unit(target))

        advance_mods, charge_mods = get_aura_advance_charge_roll_modifiers(target, game_map=game.map)
        self.assertFalse(advance_mods)
        self.assertFalse(charge_mods)

        enh = Enhancement(
            id="000010074002",
            name="Chosen of the Blood God",
            faction_id="WE",
            detachment="Cult of Blood",
            points=15,
            description='World Eaters Monster model only. Add 3" to the range of the bearers Aura abilities.',
        )
        bearer.enhancement = enh
        enh.apply_to_unit(bearer)

        advance_mods, charge_mods = get_aura_advance_charge_roll_modifiers(target, game_map=game.map)
        self.assertTrue(any(int(v) == 1 for v, _ in list(advance_mods or [])))
        self.assertTrue(any(int(v) == 1 for v, _ in list(charge_mods or [])))

    def test_butcher_lord_attachment_and_conditional_infiltrators(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.rules.enhancement import Enhancement

        army = Army("World Eaters", "Cult of Blood")
        army.faction_id = "WE"

        bearer = self._make_unit(
            "Bearer",
            keywords=["Infantry", "Character"],
            faction_keywords=["WORLD EATERS"],
        )
        bearer.can_be_attached_to = ["DUMMY"]

        jakhals = self._make_unit(
            "Jakhals",
            keywords=["Infantry", "Jakhals"],
            faction_keywords=["WORLD EATERS"],
        )
        goremongers = self._make_unit(
            "Goremongers",
            keywords=["Infantry", "Goremongers"],
            faction_keywords=["WORLD EATERS"],
        )
        other = self._make_unit(
            "Berzerkers",
            keywords=["Infantry"],
            faction_keywords=["WORLD EATERS"],
        )

        army.add_unit(bearer)
        army.add_unit(jakhals)
        army.add_unit(goremongers)
        army.add_unit(other)

        enh = Enhancement(
            id="000010074003",
            name="Butcher Lord",
            faction_id="WE",
            detachment="Cult of Blood",
            points=10,
            description=(
                "World Eaters Infantry model only. During the Declare Battle Formations step, the bearer can be "
                "attached to a Jakhals or Goremongers unit. If attached to a GOREMONGERS unit, the bearer has the "
                "Infiltrators ability."
            ),
        )
        bearer.enhancement = enh
        enh.apply_to_unit(bearer)

        self.assertTrue(bearer.can_attach_to(jakhals))
        self.assertTrue(bearer.can_attach_to(goremongers))
        self.assertFalse(bearer.can_attach_to(other))

        self.assertFalse(bearer.has_infiltrate())
        bearer.attach_to_unit(jakhals)
        self.assertFalse(bearer.has_infiltrate())
        bearer.detach_from_unit()
        bearer.attach_to_unit(goremongers)
        self.assertTrue(bearer.has_infiltrate())

    def test_brazen_form_grants_toughness_and_fnp(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.rules.enhancement import Enhancement

        army = Army("World Eaters", "Cult of Blood")
        army.faction_id = "WE"
        unit = self._make_unit(
            "Daemon Engine",
            keywords=["Monster", "Character"],
            faction_keywords=["WORLD EATERS"],
        )
        army.add_unit(unit)
        bearer = unit.models[0]
        base_toughness = int(getattr(bearer, "_toughness", 0) or 0)

        enh = Enhancement(
            id="000010074004",
            name="Brazen Form",
            faction_id="WE",
            detachment="Cult of Blood",
            points=25,
            description="World Eaters Monster model only. Add 1 to the bearer’s Toughness characteristic and the bearer has the Feel No Pain 5+ ability.",
        )
        unit.enhancement = enh
        enh.apply_to_unit(unit)

        self.assertEqual(int(getattr(bearer, "_toughness", 0) or 0), base_toughness + 1)
        fnp = list(unit.has_feel_no_pain(target_model=bearer) or [])
        self.assertTrue(any(int(v) == 5 for v, _ in fnp))

    def test_strategic_slaughter_redeploy_filters_to_jakhals_or_goremongers(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.rules.enhancement import Enhancement
        from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
        from warhammer40k_ai.roster.player import Player, PlayerControl
        from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from warhammer40k_ai.utility.entity_ids import get_entity_id

        army = Army("World Eaters", "Cult of Blood")
        army.faction_id = "WE"
        enemy_army = Army("Enemy", "Other")
        enemy_army.faction_id = "EN"

        bearer = self._make_unit(
            "Bearer",
            keywords=["Character"],
            faction_keywords=["WORLD EATERS"],
        )
        jakhals = self._make_unit(
            "Jakhals",
            keywords=["Jakhals", "Infantry"],
            faction_keywords=["WORLD EATERS"],
        )
        goremongers = self._make_unit(
            "Goremongers",
            keywords=["Goremongers", "Infantry"],
            faction_keywords=["WORLD EATERS"],
        )
        other = self._make_unit(
            "Berzerkers",
            keywords=["Infantry"],
            faction_keywords=["WORLD EATERS"],
        )

        army.add_unit(bearer)
        army.add_unit(jakhals)
        army.add_unit(goremongers)
        army.add_unit(other)

        enh = Enhancement(
            id="000010074005",
            name="Strategic Slaughter",
            faction_id="WE",
            detachment="Cult of Blood",
            points=20,
            description=(
                "World Eaters model only. After both players have deployed their armies, select up to three Jakhals "
                "and/or Goremongers units from your army and redeploy them. When doing so, you can set those units up "
                "in Strategic Reserves, regardless of how many units are already in Strategic Reserves."
            ),
        )
        bearer.enhancement = enh
        enh.apply_to_unit(bearer)

        game = Game(
            Battlefield(BattlefieldSize.STRIKE_FORCE),
            players=[
                Player("P1", control=PlayerControl.REMOTE, army=army),
                Player("P2", control=PlayerControl.REMOTE, army=enemy_army),
            ],
        )
        game.attacker_index = 0
        game.defender_index = 1

        for unit in [bearer, jakhals, goremongers, other]:
            unit.deployed = True
            unit.reserve_status = "deployed"

        bearer.models[0].set_location(10.0, 10.0, 0.0, 0.0)
        jakhals.models[0].set_location(15.0, 10.0, 0.0, 0.0)
        goremongers.models[0].set_location(20.0, 10.0, 0.0, 0.0)
        other.models[0].set_location(25.0, 10.0, 0.0, 0.0)
        self.assertTrue(game.map.place_unit(bearer))
        self.assertTrue(game.map.place_unit(jakhals))
        self.assertTrue(game.map.place_unit(goremongers))
        self.assertTrue(game.map.place_unit(other))
        game.rebuild_entity_registry()

        game.execute_redeploy_units_phase()

        pending = [
            req for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "")) == DECISION_CHOOSE_QUARRY
        ]
        self.assertEqual(len(pending), 1)
        request = pending[0]

        jakhals_id = str(get_entity_id(jakhals) or "")
        goremongers_id = str(get_entity_id(goremongers) or "")
        other_id = str(get_entity_id(other) or "")

        target_ids = {
            str((dict(getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or ""))
            for opt in list(getattr(request, "options", []) or [])
        }
        self.assertIn(jakhals_id, target_ids)
        self.assertIn(goremongers_id, target_ids)
        self.assertNotIn(other_id, target_ids)

        options = list(getattr(request, "options", []) or [])
        self.assertTrue(
            any(
                str((dict(getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or "")) == jakhals_id
                and str((dict(getattr(opt, "payload", {}) or {}).get("redeploy_action", "") or "")) == "strategic_reserves"
                for opt in options
            )
        )
        self.assertTrue(
            any(
                str((dict(getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or "")) == goremongers_id
                and str((dict(getattr(opt, "payload", {}) or {}).get("redeploy_action", "") or "")) == "strategic_reserves"
                for opt in options
            )
        )

    def test_archslaughterer_ap_bonus_and_vessel_damage_bonus(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.rules.enhancement import Enhancement
        from warhammer40k_ai.units.model import Model
        from warhammer40k_ai.utility.model_base import Base, BaseType

        army = Army("World Eaters", "Vessels of Wrath")
        army.faction_id = "WE"
        unit = self._make_unit(
            "Bearer",
            keywords=["Character"],
            faction_keywords=["WORLD EATERS"],
        )
        army.add_unit(unit)

        enh = Enhancement(
            id="000009847002",
            name="Archslaughterer",
            faction_id="WE",
            detachment="Vessels of Wrath",
            points=25,
            description="",
        )
        unit.enhancement = enh
        enh.apply_to_unit(unit)

        attacker = unit.models[0]
        profile = self._make_melee_profile(attacks="1", damage="1")
        target_unit = self._make_unit(
            "Target",
            faction_name="Enemy",
            keywords=["Infantry"],
            faction_keywords=["ENEMY"],
        )

        self.assertEqual(int(profile.get_effective_ap(attacker, target_unit)), -1)

        target_stub_unit = SimpleNamespace(
            special_rules={},
            models=[],
            has_feel_no_pain=lambda: [],
            damaged_profile=None,
            damaged_profile_desc=None,
        )
        target_model = Model(
            name="Target",
            movement=6,
            toughness=4,
            save=3,
            wounds=5,
            leadership=6,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        target_model.set_parent_unit(target_stub_unit)
        target_stub_unit.models = [target_model]

        before = target_model.wounds
        profile._damage_target_with_tracking(
            target_model,
            attacker,
            {"below_half_distance": False, "mortal_wound": False},
            game_map=None,
        )
        self.assertEqual(target_model.wounds, before - 1)

        attacker.keywords = list(getattr(attacker, "keywords", []) or []) + ["Vessel of Wrath"]

        target_model_vessel = Model(
            name="Target",
            movement=6,
            toughness=4,
            save=3,
            wounds=5,
            leadership=6,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        target_model_vessel.set_parent_unit(target_stub_unit)
        target_stub_unit.models = [target_model_vessel]

        before_vessel = target_model_vessel.wounds
        profile._damage_target_with_tracking(
            target_model_vessel,
            attacker,
            {"below_half_distance": False, "mortal_wound": False},
            game_map=None,
        )
        self.assertEqual(target_model_vessel.wounds, before_vessel - 2)

    def test_vox_diabolus_cp_gain_uses_roll_and_vessel_bonus(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.rules.enhancement import Enhancement
        from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
        from warhammer40k_ai.roster.player import Player, PlayerControl

        army = Army("World Eaters", "Vessels of Wrath")
        army.faction_id = "WE"
        attacker = self._make_unit(
            "Bearer",
            keywords=["Character"],
            faction_keywords=["WORLD EATERS"],
        )
        army.add_unit(attacker)

        enemy_army = Army("Enemy", "Other")
        enemy_army.faction_id = "EN"
        enemy = self._make_unit(
            "Enemy",
            faction_name="Enemy",
            keywords=["Infantry"],
            faction_keywords=["ENEMY"],
        )
        enemy_army.add_unit(enemy)

        bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
        game = Game(
            bf,
            players=[
                Player("P1", control=PlayerControl.LOCAL, army=army),
                Player("P2", control=PlayerControl.REMOTE, army=enemy_army),
            ],
        )

        enh = Enhancement(
            id="000009847003",
            name="Vox-diabolus",
            faction_id="WE",
            detachment="Vessels of Wrath",
            points=20,
            description="",
        )
        attacker.enhancement = enh
        enh.apply_to_unit(attacker)

        weapon_profile = SimpleNamespace(parent_wargear=SimpleNamespace(is_melee=lambda: True))

        with patch("warhammer40k_ai.engine.game.get_roll", return_value=3):
            game.event_system.publish(
                "unit_destroyed",
                unit=enemy,
                destroyed_by_unit=attacker,
                destroyed_by_model=attacker.models[0],
                destroyed_by_weapon_profile=weapon_profile,
            )
        self.assertEqual(int(game.players[0].command_points), 0)

        attacker.models[0].keywords = list(getattr(attacker.models[0], "keywords", []) or []) + ["Vessel of Wrath"]
        with patch("warhammer40k_ai.engine.game.get_roll", return_value=3):
            game.event_system.publish(
                "unit_destroyed",
                unit=enemy,
                destroyed_by_unit=attacker,
                destroyed_by_model=attacker.models[0],
                destroyed_by_weapon_profile=weapon_profile,
            )
        self.assertEqual(int(game.players[0].command_points), 1)

    def test_avengers_crown_sets_bearer_melee_fight_on_death_rule(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.rules.enhancement import Enhancement
        from warhammer40k_ai.units.model import Model
        from warhammer40k_ai.utility.model_base import Base, BaseType

        army = Army("World Eaters", "Vessels of Wrath")
        army.faction_id = "WE"
        unit = self._make_unit(
            "Bearer",
            keywords=["Character"],
            faction_keywords=["WORLD EATERS"],
        )
        army.add_unit(unit)

        enh = Enhancement(
            id="000009847004",
            name="Avenger's Crown",
            faction_id="WE",
            detachment="Vessels of Wrath",
            points=15,
            description="",
        )
        unit.enhancement = enh
        enh.apply_to_unit(unit)

        bearer = unit.models[0]
        rule = unit.get_melee_fight_on_death_after_attacks_rule(model=bearer)
        self.assertIsNotNone(rule)
        self.assertEqual(int(rule.get("threshold", 0) or 0), 2)

        not_bearer = Model(
            name="Other",
            movement=6,
            toughness=4,
            save=3,
            wounds=5,
            leadership=6,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        not_bearer.set_parent_unit(unit)
        self.assertIsNone(unit.get_melee_fight_on_death_after_attacks_rule(model=not_bearer))

    def test_gateways_to_glory_grants_move_through_rules(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.rules.enhancement import Enhancement
        from warhammer40k_ai.utility.calcs import MovementType, get_validation_rules

        army = Army("World Eaters", "Vessels of Wrath")
        army.faction_id = "WE"
        unit = self._make_unit(
            "Daemon Prince",
            keywords=["Monster", "Character"],
            faction_keywords=["WORLD EATERS"],
        )
        army.add_unit(unit)

        enh = Enhancement(
            id="000009847005",
            name="Gateways to Glory",
            faction_id="WE",
            detachment="Vessels of Wrath",
            points=10,
            description="",
        )
        unit.enhancement = enh
        enh.apply_to_unit(unit)

        move_rules = get_validation_rules(MovementType.MOVE, moving_unit=unit)
        self.assertTrue(bool(move_rules.get("can_move_through_enemy_models")))
        self.assertTrue(bool(move_rules.get("can_move_through_terrain")))
        self.assertFalse(bool(move_rules.get("cannot_move_within_engagement_range")))
        self.assertTrue(bool(move_rules.get("cannot_end_in_engagement_range")))

        advance_rules = get_validation_rules(MovementType.ADVANCE, moving_unit=unit)
        self.assertTrue(bool(advance_rules.get("can_move_through_enemy_models")))
        self.assertTrue(bool(advance_rules.get("can_move_through_terrain")))
        self.assertFalse(bool(advance_rules.get("cannot_move_within_engagement_range")))
        self.assertTrue(bool(advance_rules.get("cannot_end_in_engagement_range")))

        charge_rules = get_validation_rules(MovementType.CHARGE, moving_unit=unit)
        self.assertTrue(bool(charge_rules.get("can_move_through_enemy_models")))
        self.assertTrue(bool(charge_rules.get("can_move_through_terrain")))
        self.assertFalse(bool(charge_rules.get("cannot_end_in_engagement_range")))


if __name__ == "__main__":
    unittest.main()
