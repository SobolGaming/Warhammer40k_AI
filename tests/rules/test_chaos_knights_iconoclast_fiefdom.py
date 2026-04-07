import unittest
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_dispatcher import dispatch_decision
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_SELECT_REALM_OF_CHAOS_UNITS
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionQueue, DecisionRequest, DecisionResult
from warhammer40k_ai.engine.event.system import EventSystem
from warhammer40k_ai.roster.army import Army, ArmyValidationError
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.aura_effects import get_aura_attack_modifiers


class _RegistryStub:
    def __init__(self, units, players):
        self._units = {str(getattr(unit, "_id", "") or ""): unit for unit in list(units or []) if unit is not None}
        self._players = {str(getattr(player, "id", "") or ""): player for player in list(players or []) if player is not None}

    def get(self, entity_id: str, *, kind: str):
        if kind == "unit":
            return self._units.get(str(entity_id or ""))
        if kind == "player":
            return self._players.get(str(entity_id or ""))
        return None


class _MapStub:
    def __init__(self, friendly_units=None):
        self._friendly_units = list(friendly_units or [])

    def get_friendly_units(self, _attacker_unit):
        return list(self._friendly_units)


class _GameStub:
    def __init__(self, *, current_player, enemy_units_by_player, units, players, phase_name="SHOOTING_PHASE"):
        self.is_authoritative = True
        self.turn = 1
        self.phase = SimpleNamespace(name=str(phase_name or "SHOOTING_PHASE"))
        self.map = _MapStub(units)
        self.event_system = EventSystem()
        self.decision_queue = DecisionQueue()
        self.players = list(players or [])
        self.entity_registry = _RegistryStub(units, players)
        self._current_player = current_player
        self._enemy_units_by_player = {
            str(player_id or ""): list(enemy_units or [])
            for player_id, enemy_units in dict(enemy_units_by_player or {}).items()
        }

    def get_current_player(self):
        return self._current_player

    def request_decision(self, request):
        self.decision_queue.add(request)

    def get_enemy_units(self, player):
        player_id = str(getattr(player, "id", "") or "")
        return list(self._enemy_units_by_player.get(player_id, []))


class _MockDatasheet:
    def __init__(self, name, *, faction_name, keywords=None, faction_keywords=None, cost=100):
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": int(cost)}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": "7",
                "OC": "2",
                "base_size": "32mm",
                "inv_sv": "0",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(name, *, faction_name, keywords=None, faction_keywords=None, cost=100):
    datasheet = _MockDatasheet(
        name,
        faction_name=faction_name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        cost=cost,
    )
    unit = Unit(datasheet)
    unit._id = name
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.round_state.shot_this_round = False
    return unit


def _set_unit_position(unit, x: float, y: float, z: float = 0.0):
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), float(z), 0.0)


class TestChaosKnightsIconoclastFiefdom(unittest.TestCase):
    def _setup_players(self, *, points_limit=2000):
        ck_army = Army.with_detachment("Chaos Knights", detachment_type="Iconoclast Fiefdom", points_limit=points_limit)
        ck_army.faction_id = "QT"
        ck_player = Player("CK", control=PlayerControl.REMOTE, army=ck_army)
        ck_army.player = ck_player

        enemy_army = Army.with_detachment("Enemy", detachment_type="None")
        enemy_army.faction_id = "EN"
        enemy_player = Player("EN", control=PlayerControl.REMOTE, army=enemy_army)
        enemy_army.player = enemy_player
        return ck_army, ck_player, enemy_army, enemy_player

    def _make_chaos_knight(self, name: str, *, titanic=False, cost=400):
        keywords = ["CHAOS KNIGHTS"]
        if titanic:
            keywords.append("TITANIC")
        return _make_unit(
            name,
            faction_name="Chaos Knights",
            keywords=keywords,
            faction_keywords=["CHAOS KNIGHTS"],
            cost=cost,
        )

    def _make_damned(self, name: str, *, cost=100, character=False):
        keywords = ["DAMNED", "INFANTRY"]
        if character:
            keywords.append("CHARACTER")
        return _make_unit(
            name,
            faction_name="Heretic Astartes",
            keywords=keywords,
            faction_keywords=["HERETIC ASTARTES"],
            cost=cost,
        )

    def test_iconoclast_validation_rejects_damned_warlord(self):
        ck_army, _ck_player, _enemy_army, _enemy_player = self._setup_players()
        ck_army.add_unit(self._make_chaos_knight("Knight Abominant", titanic=True))
        damned = self._make_damned("Cultist Mob", character=True)
        ck_army.add_unit(damned)
        ck_army.select_warlord(damned)

        with self.assertRaises(ArmyValidationError):
            ck_army.validate_detachment_rules()

    def test_iconoclast_validation_rejects_damned_points_cap(self):
        ck_army, _ck_player, _enemy_army, _enemy_player = self._setup_players(points_limit=1000)
        ck_army.add_unit(self._make_chaos_knight("Knight Abominant", titanic=True))
        ck_army.add_unit(self._make_damned("Damned A", cost=100))
        ck_army.add_unit(self._make_damned("Damned B", cost=100))
        ck_army.add_unit(self._make_damned("Damned C", cost=100))

        with self.assertRaises(ArmyValidationError):
            ck_army.validate_detachment_rules()

    def test_iconoclast_dark_sacrifice_request_and_apply(self):
        ck_army, ck_player, enemy_army, enemy_player = self._setup_players()
        source = self._make_chaos_knight("Knight Desecrator", titanic=True)
        damned = self._make_damned("Cultist Mob")
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            cost=100,
        )
        ck_army.add_unit(source)
        ck_army.add_unit(damned)
        enemy_army.add_unit(enemy)

        _set_unit_position(source, 0.0, 0.0, 0.0)
        _set_unit_position(damned, 3.0, 0.0, 0.0)
        _set_unit_position(enemy, 10.0, 0.0, 0.0)

        all_units = list(ck_army.units) + list(enemy_army.units)
        game = _GameStub(
            current_player=ck_player,
            enemy_units_by_player={
                ck_player.id: [enemy],
                enemy_player.id: list(ck_army.units),
            },
            units=all_units,
            players=[ck_player, enemy_player],
            phase_name="SHOOTING_PHASE",
        )
        ck_player.game = game
        enemy_player.game = game

        mgr = ck_army.chaos_knights_detachments
        mgr.queue_iconoclast_dark_sacrifice_choice(source, trigger="shooting", game=game)

        requests = [
            req for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
            and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "iconoclast_dark_sacrifice"
        ]
        self.assertTrue(requests)
        request = requests[-1]

        option = next(
            opt
            for opt in list(request.options or [])
            if str((getattr(opt, "payload", {}) or {}).get("damned_unit_id", "") or "") == str(getattr(damned, "_id", ""))
            and str((getattr(opt, "payload", {}) or {}).get("sacrifice_mode", "") or "") == "LETHAL_HITS"
        )
        result = DecisionResult(
            decision_id=request.decision_id,
            player_id=ck_player.id,
            option_id=option.option_id,
            payload={},
        )

        damned.pass_leadership_check = lambda *_a, **_k: True
        with patch("warhammer40k_ai.rules.chaos_knights_detachments.get_roll", return_value=2):
            apply_result = dispatch_decision(game, request, result)
        self.assertTrue(apply_result.ok)
        self.assertEqual(len(getattr(damned, "models", []) or []), 0)

        source_model = source.models[0]
        bonuses = source.get_model_weapon_keyword_bonuses(
            attack_type="ranged",
            model=source_model,
            weapon_name="Desecrator Cannon",
            target=enemy,
        )
        self.assertTrue(bool(bonuses.get("lethal_hits", False)))

        game.phase = SimpleNamespace(name="FIGHT_PHASE")
        bonuses_after = source.get_model_weapon_keyword_bonuses(
            attack_type="ranged",
            model=source_model,
            weapon_name="Desecrator Cannon",
            target=enemy,
        )
        self.assertFalse(bool(bonuses_after.get("lethal_hits", False)))

    def test_iconoclast_dark_sacrifice_invalid_path_rejected(self):
        ck_army, ck_player, enemy_army, enemy_player = self._setup_players()
        source = self._make_chaos_knight("Knight Desecrator", titanic=True)
        damned = self._make_damned("Cultist Mob")
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            cost=100,
        )
        ck_army.add_unit(source)
        ck_army.add_unit(damned)
        enemy_army.add_unit(enemy)

        _set_unit_position(source, 0.0, 0.0, 0.0)
        _set_unit_position(damned, 3.0, 0.0, 0.0)
        _set_unit_position(enemy, 12.0, 0.0, 0.0)

        all_units = list(ck_army.units) + list(enemy_army.units)
        game = _GameStub(
            current_player=ck_player,
            enemy_units_by_player={
                ck_player.id: [enemy],
                enemy_player.id: list(ck_army.units),
            },
            units=all_units,
            players=[ck_player, enemy_player],
            phase_name="SHOOTING_PHASE",
        )
        ck_player.game = game
        enemy_player.game = game

        bad_request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Dark Sacrifice invalid test",
            player_id=ck_player.id,
            options=[
                DecisionOption.create(
                    "Bad option",
                    payload={
                        "source_unit_id": str(getattr(source, "_id", "")),
                        "damned_unit_id": str(getattr(enemy, "_id", "")),
                        "target_unit_id": str(getattr(enemy, "_id", "")),
                        "sacrifice_mode": "LETHAL_HITS",
                        "trigger": "shooting",
                    },
                )
            ],
            context={
                "ability": "iconoclast_dark_sacrifice",
                "ability_name": "Dark Sacrifice",
                "source_unit_id": str(getattr(source, "_id", "")),
                "trigger": "shooting",
                "candidate_damned_unit_ids": [str(getattr(damned, "_id", ""))],
                "allowed_modes": ["LETHAL_HITS", "SUSTAINED_HITS_1"],
                "optional": True,
            },
        )
        bad_result = DecisionResult(
            decision_id=bad_request.decision_id,
            player_id=ck_player.id,
            option_id=bad_request.options[0].option_id,
            payload={},
        )
        apply_result = dispatch_decision(game, bad_request, bad_result)
        self.assertFalse(apply_result.ok)

    def test_iconoclast_profane_altar_dark_sacrifice_grants_both_keywords_and_max_models(self):
        ck_army, ck_player, enemy_army, enemy_player = self._setup_players()
        source = self._make_chaos_knight("Knight Desecrator", titanic=True)
        damned = self._make_damned("Cultist Mob")
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            cost=100,
        )
        ck_army.add_unit(source)
        ck_army.add_unit(damned)
        enemy_army.add_unit(enemy)
        _set_unit_position(source, 0.0, 0.0, 0.0)
        _set_unit_position(damned, 3.0, 0.0, 0.0)
        _set_unit_position(enemy, 10.0, 0.0, 0.0)

        source._get_enhancement_bearer_model = lambda: source.models[0]
        Enhancement(
            id="000009765002",
            name="Profane Altar",
            faction_id="QT",
            detachment="Iconoclast Fiefdom",
            description="",
        ).apply_to_unit(source)
        self.assertTrue(bool(source.special_rules.get("enhancement_iconoclast_profane_altar")))

        all_units = list(ck_army.units) + list(enemy_army.units)
        game = _GameStub(
            current_player=ck_player,
            enemy_units_by_player={
                ck_player.id: [enemy],
                enemy_player.id: list(ck_army.units),
            },
            units=all_units,
            players=[ck_player, enemy_player],
            phase_name="SHOOTING_PHASE",
        )
        ck_player.game = game
        enemy_player.game = game

        damned.pass_leadership_check = lambda *_a, **_k: False
        mgr = ck_army.chaos_knights_detachments
        with patch("warhammer40k_ai.rules.chaos_knights_detachments.get_roll", return_value=1):
            outcome = mgr.apply_iconoclast_dark_sacrifice(
                source,
                damned,
                mode="LETHAL_HITS",
                game=game,
                player=ck_player,
            )
        self.assertTrue(bool(outcome.get("ok")))
        self.assertEqual(int(outcome.get("destroy_target", 0) or 0), 6)
        self.assertEqual(set(outcome.get("weapon_keywords") or []), {"LETHAL HITS", "SUSTAINED HITS 1"})

        source_model = source.models[0]
        bonuses = source.get_model_weapon_keyword_bonuses(
            attack_type="ranged",
            model=source_model,
            weapon_name="Desecrator Cannon",
            target=enemy,
        )
        self.assertTrue(bool(bonuses.get("lethal_hits", False)))
        self.assertEqual(int(bonuses.get("sustained_hits_value", 0) or 0), 1)

    def test_iconoclast_tyrants_banner_allows_visible_dark_sacrifice_target(self):
        ck_army, ck_player, enemy_army, enemy_player = self._setup_players()
        source = self._make_chaos_knight("Knight Desecrator", titanic=True)
        damned = self._make_damned("Cultist Mob")
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            cost=100,
        )
        ck_army.add_unit(source)
        ck_army.add_unit(damned)
        enemy_army.add_unit(enemy)
        _set_unit_position(source, 0.0, 0.0, 0.0)
        _set_unit_position(damned, 12.0, 0.0, 0.0)
        _set_unit_position(enemy, 20.0, 0.0, 0.0)

        source._get_enhancement_bearer_model = lambda: source.models[0]
        Enhancement(
            id="000009765004",
            name="Tyrant's Banner",
            faction_id="QT",
            detachment="Iconoclast Fiefdom",
            description="",
        ).apply_to_unit(source)
        self.assertTrue(bool(source.special_rules.get("enhancement_iconoclast_tyrants_banner")))

        all_units = list(ck_army.units) + list(enemy_army.units)
        game = _GameStub(
            current_player=ck_player,
            enemy_units_by_player={
                ck_player.id: [enemy],
                enemy_player.id: list(ck_army.units),
            },
            units=all_units,
            players=[ck_player, enemy_player],
            phase_name="SHOOTING_PHASE",
        )
        game._model_can_see_unit = lambda model, target, game_map=None: target is damned
        ck_player.game = game
        enemy_player.game = game

        mgr = ck_army.chaos_knights_detachments
        mgr.queue_iconoclast_dark_sacrifice_choice(source, trigger="shooting", game=game)
        requests = [
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
            and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "iconoclast_dark_sacrifice"
        ]
        self.assertTrue(requests)
        request = requests[-1]
        self.assertIn(str(getattr(damned, "_id", "")), list((request.context or {}).get("candidate_damned_unit_ids", []) or []))

        option = next(
            opt
            for opt in list(request.options or [])
            if str((getattr(opt, "payload", {}) or {}).get("damned_unit_id", "") or "") == str(getattr(damned, "_id", ""))
        )
        damned.pass_leadership_check = lambda *_a, **_k: True
        result = DecisionResult(
            decision_id=request.decision_id,
            player_id=ck_player.id,
            option_id=option.option_id,
            payload={},
        )
        with patch("warhammer40k_ai.rules.chaos_knights_detachments.get_roll", return_value=1):
            apply_result = dispatch_decision(game, request, result)
        self.assertTrue(apply_result.ok)

    def test_iconoclast_pave_the_way_selection_applies_scouts(self):
        ck_army, ck_player, enemy_army, enemy_player = self._setup_players()
        source = self._make_chaos_knight("Knight Rampager", titanic=True)
        damned_a = self._make_damned("Damned A")
        damned_b = self._make_damned("Damned B")
        damned_c = self._make_damned("Damned C")
        damned_d = self._make_damned("Damned D")
        ck_army.add_unit(source)
        ck_army.add_unit(damned_a)
        ck_army.add_unit(damned_b)
        ck_army.add_unit(damned_c)
        ck_army.add_unit(damned_d)

        source._get_enhancement_bearer_model = lambda: source.models[0]
        Enhancement(
            id="000009765003",
            name="Pave the Way",
            faction_id="QT",
            detachment="Iconoclast Fiefdom",
            description="",
        ).apply_to_unit(source)
        self.assertTrue(bool(source.special_rules.get("enhancement_iconoclast_pave_the_way")))

        all_units = list(ck_army.units) + list(enemy_army.units)
        game = _GameStub(
            current_player=ck_player,
            enemy_units_by_player={
                ck_player.id: list(enemy_army.units),
                enemy_player.id: list(ck_army.units),
            },
            units=all_units,
            players=[ck_player, enemy_player],
            phase_name="DECLARE_BATTLE_FORMATIONS",
        )
        ck_player.game = game
        enemy_player.game = game

        mgr = ck_army.chaos_knights_detachments
        mgr.queue_iconoclast_pave_the_way_selection_request(game=game, player=ck_player)
        requests = [
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_SELECT_REALM_OF_CHAOS_UNITS
            and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "iconoclast_pave_the_way_selection"
        ]
        self.assertTrue(requests)
        request = requests[-1]
        select_ids = [str(getattr(damned_a, "_id", "")), str(getattr(damned_b, "_id", "")), str(getattr(damned_c, "_id", ""))]
        result = DecisionResult(
            decision_id=request.decision_id,
            player_id=ck_player.id,
            option_id=request.options[0].option_id,
            payload={"unit_ids": list(select_ids)},
        )
        apply_result = dispatch_decision(game, request, result)
        self.assertTrue(apply_result.ok)
        for unit in (damned_a, damned_b, damned_c):
            self.assertTrue(bool(unit.special_rules.get("iconoclast_pave_the_way_active")))
            has_scout, distance = unit.has_scout()
            self.assertTrue(bool(has_scout))
            self.assertEqual(float(distance), 6.0)
        self.assertFalse(bool(damned_d.special_rules.get("iconoclast_pave_the_way_active")))

    def test_iconoclast_dread_tyrants_aura_applies_within_range(self):
        ck_army, _ck_player, enemy_army, _enemy_player = self._setup_players()
        source = self._make_chaos_knight("Knight Tyrant", titanic=True)
        attacker = self._make_damned("Damned Squad")
        target = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            cost=100,
        )
        ck_army.add_unit(source)
        ck_army.add_unit(attacker)
        enemy_army.add_unit(target)

        _set_unit_position(source, 0.0, 0.0, 0.0)
        _set_unit_position(attacker, 4.0, 0.0, 0.0)
        _set_unit_position(target, 12.0, 0.0, 0.0)

        weapon_profile = SimpleNamespace(name="Autogun")
        aura_map = _MapStub([source, attacker])
        mods = get_aura_attack_modifiers(attacker, target, weapon_profile, game_map=aura_map)
        self.assertTrue(bool(mods.reroll_hit_ones))
        self.assertTrue(bool(mods.reroll_wound_ones))

        _set_unit_position(source, 20.0, 0.0, 0.0)
        mods_out_of_range = get_aura_attack_modifiers(attacker, target, weapon_profile, game_map=aura_map)
        self.assertFalse(bool(mods_out_of_range.reroll_hit_ones))
        self.assertFalse(bool(mods_out_of_range.reroll_wound_ones))


if __name__ == "__main__":
    unittest.main()
