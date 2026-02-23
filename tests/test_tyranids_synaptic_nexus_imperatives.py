import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


class _DummyPlayer:
    def __init__(self, name: str = "Player"):
        self.name = name
        self.control = SimpleNamespace(name="LOCAL")
        self.has_control = lambda: True
        self.game = None


class _DummyArmy:
    def __init__(self, *, faction_id: str = "TYR", detachment_type: str = "Synaptic Nexus"):
        self.faction_id = faction_id
        self.detachment_type = detachment_type
        self.units = []
        self.player = _DummyPlayer()
        self.synapse = None
        self.tyranids_detachments = None


class _DummySynapse:
    def unit_in_synapse_range(self, unit, *, game=None, game_map=None) -> bool:
        return bool(getattr(unit, "_in_synapse", False))


class _DummyModel:
    def __init__(self, unit, *, keywords=None, faction_keywords=None, name: str = "Model"):
        self.name = name
        self.parent_unit = unit
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.wounds = 1
        self.is_alive = True

    def has_any_keyword(self, keyword: str) -> bool:
        kw = str(keyword or "").strip().lower()
        if not kw:
            return False
        pool = [str(k or "").strip().lower() for k in (self.keywords or []) + (self.faction_keywords or [])]
        return kw in pool


class _DummyUnit:
    def __init__(
        self,
        name: str,
        army: _DummyArmy,
        *,
        keywords=None,
        faction_keywords=None,
        toughness: int = 4,
    ):
        self.name = name
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.possible_abilities = []
        self.abilities = []
        self.models = []
        self.special_rules = {}
        self.round_state = SimpleNamespace(remained_stationary_this_round=False)
        self._army = army
        self.parent_army = army
        self.toughness = int(toughness)
        self._in_synapse = True
        model = _DummyModel(
            self,
            name=f"{name} #1",
            keywords=self.keywords,
            faction_keywords=self.faction_keywords,
        )
        self.models.append(model)

    def get_parent_army(self):
        return self._army

    def set_parent_army(self, army):
        self._army = army
        self.parent_army = army

    def has_any_keyword(self, keyword: str) -> bool:
        kw = str(keyword or "").strip().lower()
        if not kw:
            return False
        pool = [str(k or "").strip().lower() for k in (self.keywords or []) + (self.faction_keywords or [])]
        return kw in pool

    def has_keyword(self, keyword: str) -> bool:
        return self.has_any_keyword(keyword)

    def get_attached_unit_root(self):
        return self

    def get_attached_unit_members(self):
        return [self]

    def get_attached_unit_models(self):
        return list(self.models)

    def get_models_for_collision(self):
        return list(self.models)

    def get_models_for_wound_allocation(self):
        return list(self.models)

    def is_battle_shocked(self):
        return False

    def is_in_reserves(self):
        return False

    def is_alive(self):
        return True

    def has_stealth(self):
        return False

    def has_first_prince_tzeentch_defense(self):
        return False

    def has_advance_and_shoot(self):
        return False


class TestSynapticNexusImperatives(unittest.TestCase):
    def _aura_stub(self):
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

    def _make_profile(self, *, weapon_type="Melee", skill="4+"):
        from warhammer40k_ai.units.wargear import WargearProfile

        parent = SimpleNamespace(
            name="Test Weapon",
            is_melee=lambda: str(weapon_type).strip().lower() == "melee",
            is_ranged=lambda: str(weapon_type).strip().lower() == "ranged",
        )
        data = {
            "range": "Melee" if str(weapon_type).strip().lower() == "melee" else "24",
            "A": "1",
            "BS_WS": str(skill),
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
        return WargearProfile("Profile", wargear_data=data, parent_wargear=parent)

    @staticmethod
    def _find_synaptic_request(game):
        for req in list(game.decision_queue.list() or []):
            if req.decision_type != DECISION_CHOOSE_QUARRY:
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "") == "synaptic_imperatives":
                return req
        return None

    def test_synaptic_imperatives_queue_and_resolve_once_per_round(self):
        army = Army("Tyranids", detachment_type="Synaptic Nexus")
        army.faction_id = "TYR"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "SM"

        player = Player("Player", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])

        army.on_battle_round_start(1)
        req = self._find_synaptic_request(game)
        self.assertIsNotNone(req)

        option_payloads = [dict(getattr(opt, "payload", {}) or {}) for opt in list(req.options or [])]
        self.assertTrue(any(str(payload.get("action", "") or "") == "skip" for payload in option_payloads))
        available_keys = {
            str(payload.get("choice_key", "") or "").strip().upper()
            for payload in option_payloads
            if str(payload.get("choice_key", "") or "").strip()
        }
        self.assertEqual(
            available_keys,
            {"SYNAPTIC_AUGMENTATION", "SURGING_VITALITY", "GOADED_TO_SLAUGHTER"},
        )

        chosen_option_id = None
        for opt in list(req.options or []):
            payload = dict(getattr(opt, "payload", {}) or {})
            if str(payload.get("choice_key", "") or "").strip().upper() == "SURGING_VITALITY":
                chosen_option_id = str(getattr(opt, "option_id", "") or "")
                break
        self.assertTrue(chosen_option_id)

        cmd_result = resolve_decision_command(game, req, chosen_option_id, player_id=player.id)
        apply_result = getattr(cmd_result, "value", None)
        self.assertTrue(apply_result.ok, msg=str(apply_result.errors))

        mgr = army.tyranids_detachments
        self.assertEqual(str(mgr.active_synaptic_imperative_key or ""), "SURGING_VITALITY")
        self.assertEqual(int(mgr.synaptic_imperative_active_round or 0), 1)
        self.assertIn("SURGING_VITALITY", set(mgr.synaptic_imperatives_used_keys or []))

        army.on_battle_round_start(2)
        req_round_2 = self._find_synaptic_request(game)
        self.assertIsNotNone(req_round_2)
        option_payloads_round_2 = [dict(getattr(opt, "payload", {}) or {}) for opt in list(req_round_2.options or [])]
        round_2_keys = {
            str(payload.get("choice_key", "") or "").strip().upper()
            for payload in option_payloads_round_2
            if str(payload.get("choice_key", "") or "").strip()
        }
        self.assertEqual(round_2_keys, {"SYNAPTIC_AUGMENTATION", "GOADED_TO_SLAUGHTER"})

        skip_option_id = None
        for opt in list(req_round_2.options or []):
            payload = dict(getattr(opt, "payload", {}) or {})
            if str(payload.get("action", "") or "") == "skip":
                skip_option_id = str(getattr(opt, "option_id", "") or "")
                break
        self.assertTrue(skip_option_id)
        cmd_result = resolve_decision_command(game, req_round_2, skip_option_id, player_id=player.id)
        apply_result = getattr(cmd_result, "value", None)
        self.assertTrue(apply_result.ok, msg=str(apply_result.errors))
        self.assertIsNone(mgr.active_synaptic_imperative_key)
        self.assertEqual(int(mgr.synaptic_imperative_active_round or 0), 2)
        self.assertEqual(int(mgr.synaptic_imperative_resolved_round or 0), 2)

        army.on_battle_round_start(2)
        self.assertIsNone(self._find_synaptic_request(game))

    def test_synaptic_imperative_effect_methods_cover_all_three_modes(self):
        from warhammer40k_ai.rules.tyranids_detachments import TyranidsDetachmentManager

        army = _DummyArmy(detachment_type="Synaptic Nexus")
        army.synapse = _DummySynapse()
        mgr = TyranidsDetachmentManager(army)
        army.tyranids_detachments = mgr

        unit = _DummyUnit(
            "Warriors",
            army,
            keywords=["INFANTRY", "TYRANIDS"],
            faction_keywords=["TYRANIDS"],
        )
        army.units = [unit]
        model = unit.models[0]

        self.assertTrue(mgr.select_synaptic_imperative("SYNAPTIC_AUGMENTATION", battle_round=1))
        game = SimpleNamespace(turn=1)
        unit._in_synapse = True
        inv_value, _inv_source = mgr.synaptic_imperatives_invulnerable_save(model, unit=unit, game=game)
        self.assertEqual(int(inv_value or 0), 5)
        unit._in_synapse = False
        inv_value, _inv_source = mgr.synaptic_imperatives_invulnerable_save(model, unit=unit, game=game)
        self.assertEqual(int(inv_value or 0), 0)

        self.assertTrue(mgr.select_synaptic_imperative("SURGING_VITALITY", battle_round=2))
        game.turn = 2
        unit._in_synapse = True
        adv_bonus, _adv_source = mgr.synaptic_imperatives_advance_roll_bonus(unit, game=game)
        charge_bonus, _charge_source = mgr.synaptic_imperatives_charge_roll_bonus(unit, game=game)
        self.assertEqual(int(adv_bonus or 0), 1)
        self.assertEqual(int(charge_bonus or 0), 1)

        self.assertTrue(mgr.select_synaptic_imperative("GOADED_TO_SLAUGHTER", battle_round=3))
        game.turn = 3
        hit_bonus, _hit_source = mgr.synaptic_imperatives_melee_hit_bonus(model, unit=unit, game=game)
        self.assertEqual(int(hit_bonus or 0), 1)

    def test_goaded_to_slaughter_applies_melee_hit_bonus_in_attack_resolution(self):
        from warhammer40k_ai.rules.tyranids_detachments import TyranidsDetachmentManager

        army = _DummyArmy(detachment_type="Synaptic Nexus")
        enemy_army = _DummyArmy(faction_id="SM", detachment_type="Other")
        army.synapse = _DummySynapse()
        mgr = TyranidsDetachmentManager(army)
        army.tyranids_detachments = mgr
        army.player.game = SimpleNamespace(turn=1, map=None)

        attacker_unit = _DummyUnit(
            "Warriors",
            army,
            keywords=["INFANTRY", "TYRANIDS"],
            faction_keywords=["TYRANIDS"],
            toughness=4,
        )
        target_unit = _DummyUnit("Target", enemy_army, toughness=4)
        army.units = [attacker_unit]
        enemy_army.units = [target_unit]
        attacker_model = attacker_unit.models[0]
        profile = self._make_profile(weapon_type="Melee", skill="4+")

        self.assertTrue(mgr.select_synaptic_imperative("GOADED_TO_SLAUGHTER", battle_round=1))
        attacker_unit._in_synapse = True
        attack_instance = {"_aura_attack_mods": self._aura_stub()}
        hit = profile._hit_target_with_tracking(
            target_unit,
            attacker_model,
            attack_instance,
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(hit["hit"])
        self.assertTrue(any("Synaptic Imperatives" in m for m in hit.get("modifiers", [])))

        attacker_unit._in_synapse = False
        attack_instance = {"_aura_attack_mods": self._aura_stub()}
        hit = profile._hit_target_with_tracking(
            target_unit,
            attacker_model,
            attack_instance,
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(hit["hit"])
        self.assertFalse(any("Synaptic Imperatives" in m for m in hit.get("modifiers", [])))


if __name__ == "__main__":
    unittest.main()
