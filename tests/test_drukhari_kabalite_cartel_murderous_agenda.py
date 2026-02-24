from __future__ import annotations

import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_dispatcher import dispatch_decision
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_MURDEROUS_AGENDA
from warhammer40k_ai.engine.decisions import DecisionQueue, DecisionResult
from warhammer40k_ai.engine.event.system import EventSystem
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit


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
    @staticmethod
    def get_friendly_units(_unit):
        return []


class _GameStub:
    def __init__(self, *, current_player, enemy_units_by_player, units, players):
        self.is_authoritative = True
        self.turn = 1
        self.phase = SimpleNamespace(name="COMMAND_PHASE")
        self.map = _MapStub()
        self.event_system = EventSystem()
        self.decision_queue = DecisionQueue()
        self.players = list(players or [])
        self.entity_registry = _RegistryStub(units, players)
        self._current_player = current_player
        self._enemy_units_by_player = {
            str(pid or ""): list(enemy_units or [])
            for pid, enemy_units in dict(enemy_units_by_player or {}).items()
        }

    def get_current_player(self):
        return self._current_player

    def request_decision(self, request):
        self.decision_queue.add(request)

    def get_enemy_units(self, player):
        return list(self._enemy_units_by_player.get(str(getattr(player, "id", "") or ""), []))


class _MockDatasheet:
    def __init__(self, name, *, faction_name, keywords=None, faction_keywords=None):
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "7",
                "T": "4",
                "Sv": "4",
                "W": "3",
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


def _make_unit(name, *, faction_name, keywords=None, faction_keywords=None):
    datasheet = _MockDatasheet(
        name,
        faction_name=faction_name,
        keywords=keywords,
        faction_keywords=faction_keywords,
    )
    unit = Unit(datasheet)
    unit._id = name
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


class TestDrukhariKabaliteCartelMurderousAgenda(unittest.TestCase):
    def _setup_players(self):
        dru_army = Army("Drukhari", detachment_type="Kabalite Cartel")
        dru_army.faction_id = "DRU"
        dru_player = Player("DRU", control=PlayerControl.REMOTE, army=dru_army)
        dru_army.player = dru_player

        enemy_army = Army("Enemy", detachment_type="None")
        enemy_army.faction_id = "EN"
        enemy_player = Player("EN", control=PlayerControl.REMOTE, army=enemy_army)
        enemy_army.player = enemy_player
        return dru_army, dru_player, enemy_army, enemy_player

    def test_murderous_agenda_request_and_trophy_hunters_apply_precision(self):
        dru_army, dru_player, enemy_army, enemy_player = self._setup_players()
        kabal = _make_unit(
            "Kabalite Warriors",
            faction_name="Drukhari",
            keywords=["DRUKHARI", "KABAL", "INFANTRY"],
            faction_keywords=["DRUKHARI"],
        )
        non_kabal = _make_unit(
            "Wracks",
            faction_name="Drukhari",
            keywords=["DRUKHARI", "HAEMONCULUS COVENS", "INFANTRY"],
            faction_keywords=["DRUKHARI"],
        )
        enemy_character = _make_unit(
            "Enemy Captain",
            faction_name="Enemy",
            keywords=["CHARACTER", "INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        enemy_infantry = _make_unit(
            "Enemy Troops",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        dru_army.add_unit(kabal)
        dru_army.add_unit(non_kabal)
        enemy_army.add_unit(enemy_character)
        enemy_army.add_unit(enemy_infantry)

        all_units = list(dru_army.units) + list(enemy_army.units)
        game = _GameStub(
            current_player=dru_player,
            enemy_units_by_player={
                dru_player.id: list(enemy_army.units),
                enemy_player.id: list(dru_army.units),
            },
            units=all_units,
            players=[dru_player, enemy_player],
        )
        dru_player.game = game
        enemy_player.game = game

        mgr = dru_army.drukhari_detachments
        mgr.on_battle_round_start(battle_round=1, game=game, player=dru_player)
        requests = [
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_MURDEROUS_AGENDA
        ]
        self.assertTrue(requests)
        request = requests[-1]
        option = next(
            opt
            for opt in list(request.options or [])
            if str((getattr(opt, "payload", {}) or {}).get("contract_key", "") or "") == "TROPHY_HUNTERS"
            and str((getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or "") == str(enemy_character._id)
        )
        result = DecisionResult(
            decision_id=request.decision_id,
            player_id=dru_player.id,
            option_id=option.option_id,
            payload={},
        )
        apply_result = dispatch_decision(game, request, result)
        self.assertTrue(apply_result.ok)

        kabal_bonuses = kabal.get_model_weapon_keyword_bonuses(
            attack_type="ranged",
            model=kabal.models[0],
            weapon_name="Splinter Rifle",
            target=enemy_character,
        )
        self.assertTrue(bool(kabal_bonuses.get("precision")))
        self.assertTrue(any("Murderous Agenda" in str(source) for source in list(kabal_bonuses.get("sources", []) or [])))

        non_kabal_bonuses = non_kabal.get_model_weapon_keyword_bonuses(
            attack_type="ranged",
            model=non_kabal.models[0],
            weapon_name="Weapon",
            target=enemy_character,
        )
        self.assertFalse(bool(non_kabal_bonuses.get("precision")))

    def test_murderous_agenda_sow_fear_completion_grants_pain_tokens(self):
        dru_army, dru_player, enemy_army, enemy_player = self._setup_players()
        kabal = _make_unit(
            "Kabalite Warriors",
            faction_name="Drukhari",
            keywords=["DRUKHARI", "KABAL", "INFANTRY"],
            faction_keywords=["DRUKHARI"],
        )
        enemy_infantry = _make_unit(
            "Enemy Troops",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        dru_army.add_unit(kabal)
        enemy_army.add_unit(enemy_infantry)

        all_units = list(dru_army.units) + list(enemy_army.units)
        game = _GameStub(
            current_player=dru_player,
            enemy_units_by_player={
                dru_player.id: list(enemy_army.units),
                enemy_player.id: list(dru_army.units),
            },
            units=all_units,
            players=[dru_player, enemy_player],
        )
        dru_player.game = game
        enemy_player.game = game

        mgr = dru_army.drukhari_detachments
        self.assertTrue(
            mgr.select_murderous_agenda(
                "SOW_FEAR_AND_TERROR",
                enemy_infantry._id,
                game=game,
                player=dru_player,
            )
        )
        pre_bonuses = kabal.get_model_weapon_keyword_bonuses(
            attack_type="ranged",
            model=kabal.models[0],
            weapon_name="Splinter Rifle",
            target=enemy_infantry,
        )
        self.assertEqual(int(pre_bonuses.get("sustained_hits_value", 0) or 0), 1)

        self.assertEqual(int(dru_army.power_from_pain.tokens), 0)
        enemy_infantry.models[0].wounds = 0
        mgr.on_command_phase_start(game=game, player=dru_player)
        self.assertTrue(bool(mgr.murderous_agenda_contract_completed))
        self.assertEqual(int(dru_army.power_from_pain.tokens), 3)

        post_bonuses = kabal.get_model_weapon_keyword_bonuses(
            attack_type="ranged",
            model=kabal.models[0],
            weapon_name="Splinter Rifle",
            target=enemy_infantry,
        )
        self.assertEqual(int(post_bonuses.get("sustained_hits_value", 0) or 0), 0)

    def test_murderous_agenda_show_of_strength_applies_lethal_hits(self):
        dru_army, dru_player, enemy_army, enemy_player = self._setup_players()
        kabal = _make_unit(
            "Kabalite Warriors",
            faction_name="Drukhari",
            keywords=["DRUKHARI", "KABAL", "INFANTRY"],
            faction_keywords=["DRUKHARI"],
        )
        enemy_vehicle = _make_unit(
            "Enemy Tank",
            faction_name="Enemy",
            keywords=["VEHICLE"],
            faction_keywords=["ENEMY"],
        )
        enemy_army.add_unit(enemy_vehicle)
        dru_army.add_unit(kabal)

        all_units = list(dru_army.units) + list(enemy_army.units)
        game = _GameStub(
            current_player=dru_player,
            enemy_units_by_player={
                dru_player.id: list(enemy_army.units),
                enemy_player.id: list(dru_army.units),
            },
            units=all_units,
            players=[dru_player, enemy_player],
        )
        dru_player.game = game
        enemy_player.game = game

        mgr = dru_army.drukhari_detachments
        self.assertTrue(
            mgr.select_murderous_agenda(
                "SHOW_OF_STRENGTH",
                enemy_vehicle._id,
                game=game,
                player=dru_player,
            )
        )
        bonuses = kabal.get_model_weapon_keyword_bonuses(
            attack_type="ranged",
            model=kabal.models[0],
            weapon_name="Dark Lance",
            target=enemy_vehicle,
        )
        self.assertTrue(bool(bonuses.get("lethal_hits")))


if __name__ == "__main__":
    unittest.main()
