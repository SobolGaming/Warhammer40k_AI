import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_handlers.abilities import _apply_choose_quarry
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Imperial Agents",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        wounds: int = 4,
        leadership: int = 7,
    ):
        self.id = ""
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            faction_keywords = ["AGENTS OF THE IMPERIUM", "IMPERIUM"] if faction_name == "Imperial Agents" else ["ENEMY"]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": str(int(leadership)),
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(
    name: str,
    *,
    faction_name: str = "Imperial Agents",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: int = 4,
    leadership: int = 7,
):
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
            leadership=leadership,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _make_extra_model(name: str, parent_unit: Unit) -> Model:
    template = parent_unit.models[0]
    model = Model(
        name=str(name),
        movement=int(getattr(template, "movement", getattr(template, "_movement", 6)) or 6),
        toughness=int(getattr(template, "toughness", getattr(template, "_toughness", 4)) or 4),
        save=int(getattr(template, "save", getattr(template, "_save", 3)) or 3),
        wounds=int(getattr(template, "wounds", getattr(template, "_wounds", 4)) or 4),
        leadership=int(getattr(template, "leadership", getattr(template, "_leadership", 7)) or 7),
        objective_control=int(
            getattr(template, "objective_control", getattr(template, "_objective_control", 1)) or 1
        ),
        model_base=template.model_base,
        inv_save=int(getattr(template, "_inv_save", 7) or 7),
        inv_save_condition=getattr(template, "_inv_save_condition", None),
        keywords=list(getattr(template, "keywords", []) or []),
        faction_keywords=list(getattr(template, "faction_keywords", []) or []),
    )
    model.parent_unit = parent_unit
    return model


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    ia_army = Army("Imperial Agents", "Ordo Xenos Alien Hunters")
    ia_army.faction_id = "AOI"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    ia_player = Player("IA", control=PlayerControl.LOCAL, army=ia_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ia_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    return game, ia_army, enemy_army, ia_player, enemy_player


def _apply_ordo_xenos_enhancement(unit: Unit, *, enhancement_id: str, name: str, description: str = "") -> None:
    Enhancement(
        id=str(enhancement_id),
        name=str(name),
        faction_id="AOI",
        detachment="Ordo Xenos Alien Hunters",
        detachment_id="000000892",
        points=0,
        description=str(description),
    ).apply_to_unit(unit)


def _bearer_model(unit: Unit):
    bearer_id = str(getattr(unit, "special_rules", {}).get("enhancement_bearer_model_id", "") or "")
    for model in list(getattr(unit, "models", []) or []):
        if str(get_entity_id(model) or "") == bearer_id:
            return model
    for model in list(getattr(unit, "models", []) or []):
        alive_attr = getattr(model, "is_alive", False)
        if bool(alive_attr() if callable(alive_attr) else alive_attr):
            return model
    return None


class TestImperialAgentsOrdoXenosAlienHuntersEnhancements(unittest.TestCase):
    def test_ordo_xenos_enhancement_descriptors_registered(self):
        amulet = get_enhancement_tool_descriptor(enhancement_id="000009126002")
        self.assertIsNotNone(amulet)
        self.assertEqual(amulet.name, "Amulet of Auto-Chastisement")
        self.assertEqual(tuple(amulet.effect_params.get("required_target_keywords", ()) or ()), ("VEHICLE",))
        self.assertEqual(tuple(amulet.effect_params.get("excluded_target_keywords", ()) or ()), ("TITANIC",))

        beacon = get_enhancement_tool_descriptor(enhancement_id="000009126003")
        self.assertIsNotNone(beacon)
        self.assertEqual(beacon.name, "Beacon Angelis")
        self.assertTrue(bool(beacon.effect_params.get("grants_deep_strike", False)))

        universal = get_enhancement_tool_descriptor(enhancement_id="000009126005")
        self.assertIsNotNone(universal)
        self.assertEqual(universal.name, "Universal Anathema")
        self.assertEqual(
            tuple(universal.effect_params.get("granted_keywords", ()) or ()),
            ("ANTI-INFANTRY 2+", "ANTI-MONSTER 4+"),
        )

    def test_amulet_of_auto_chastisement_queues_only_non_titanic_vehicle_targets(self):
        game, ia_army, enemy_army, _ia_player, enemy_player = _build_game()
        source = _make_unit(
            "Watch Master",
            keywords=["CHARACTER", "INFANTRY", "WATCH MASTER"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM", "DEATHWATCH"],
        )
        enemy_vehicle = _make_unit(
            "Enemy Vehicle",
            faction_name="Enemy",
            keywords=["VEHICLE"],
            faction_keywords=["ENEMY"],
        )
        enemy_infantry = _make_unit(
            "Enemy Infantry",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        enemy_titanic = _make_unit(
            "Enemy Titanic",
            faction_name="Enemy",
            keywords=["VEHICLE", "TITANIC"],
            faction_keywords=["ENEMY"],
        )
        ia_army.add_unit(source)
        enemy_army.add_unit(enemy_vehicle)
        enemy_army.add_unit(enemy_infantry)
        enemy_army.add_unit(enemy_titanic)
        for unit in (source, enemy_vehicle, enemy_infantry, enemy_titanic):
            unit.deployed = True
        source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        enemy_vehicle.models[0].set_location(8.0, 0.0, 0.0, 0.0)
        enemy_infantry.models[0].set_location(8.0, 2.0, 0.0, 0.0)
        enemy_titanic.models[0].set_location(8.0, -2.0, 0.0, 0.0)
        source._has_line_of_sight_to_target = lambda _m, _t, _g: True
        game.map.units = [source, enemy_vehicle, enemy_infantry, enemy_titanic]
        game.rebuild_entity_registry()

        _apply_ordo_xenos_enhancement(
            source,
            enhancement_id="000009126002",
            name="Amulet of Auto-Chastisement",
        )

        game.current_player_index = 1
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game._on_phase_start_opponent_shooting_phase_disrupt(player=enemy_player, phase=BattleRoundPhases.SHOOTING_PHASE)
        pending = [
            req
            for req in list(game.decision_queue.list() or [])
            if str((req.context or {}).get("ability", "") or "") == "opponent_shooting_phase_disrupt"
        ]
        self.assertTrue(pending)
        request = pending[0]
        target_ids = {
            str((opt.payload or {}).get("target_unit_id", "") or "")
            for opt in list(request.options or [])
            if (opt.payload or {}).get("target_unit_id")
        }
        self.assertIn(str(get_entity_id(enemy_vehicle) or ""), target_ids)
        self.assertNotIn(str(get_entity_id(enemy_infantry) or ""), target_ids)
        self.assertNotIn(str(get_entity_id(enemy_titanic) or ""), target_ids)

    def test_amulet_of_auto_chastisement_leadership_test_pass_and_fail_outcomes(self):
        game, ia_army, enemy_army, ia_player, enemy_player = _build_game()
        source = _make_unit(
            "Watch Master",
            keywords=["CHARACTER", "INFANTRY", "WATCH MASTER"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM", "DEATHWATCH"],
        )
        pass_target = _make_unit(
            "Pass Target",
            faction_name="Enemy",
            keywords=["VEHICLE"],
            faction_keywords=["ENEMY"],
            leadership=7,
        )
        fail_target = _make_unit(
            "Fail Target",
            faction_name="Enemy",
            keywords=["VEHICLE"],
            faction_keywords=["ENEMY"],
            leadership=7,
        )
        ia_army.add_unit(source)
        enemy_army.add_unit(pass_target)
        enemy_army.add_unit(fail_target)
        for unit in (source, pass_target, fail_target):
            unit.deployed = True
        game.map.units = [source, pass_target, fail_target]
        game.rebuild_entity_registry()

        _apply_ordo_xenos_enhancement(
            source,
            enhancement_id="000009126002",
            name="Amulet of Auto-Chastisement",
        )
        bearer = _bearer_model(source)
        self.assertIsNotNone(bearer)
        pass_target.pass_leadership_check = lambda: True
        fail_target.pass_leadership_check = lambda: False

        game.current_player_index = 1
        game.phase = BattleRoundPhases.SHOOTING_PHASE

        pass_request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Amulet of Auto-Chastisement",
            player_id=ia_player.id,
            options=[
                DecisionOption.create(
                    "Pass Target",
                    payload={
                        "target_unit_id": str(get_entity_id(pass_target) or ""),
                        "source_unit_id": str(get_entity_id(source) or ""),
                        "model_id": str(get_entity_id(bearer) or ""),
                    },
                )
            ],
            context={
                "ability": "opponent_shooting_phase_disrupt",
                "ability_name": "Amulet of Auto-Chastisement",
                "ability_key": "AMULET_OF_AUTO_CHASTISEMENT",
                "resolution_mode": "leadership_test",
                "required_target_keywords": ["VEHICLE"],
                "excluded_target_keywords": ["TITANIC"],
            },
        )
        pass_result = DecisionResult(
            decision_id=pass_request.decision_id,
            player_id=ia_player.id,
            option_id=pass_request.options[0].option_id,
        )
        _apply_choose_quarry(game, pass_request, pass_result)
        self.assertTrue(bool(pass_target.special_rules.get("shooting_phase_hit_penalty_active")))
        self.assertFalse(pass_target.is_shooting_phase_ineligible(game))

        fail_request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Amulet of Auto-Chastisement",
            player_id=ia_player.id,
            options=[
                DecisionOption.create(
                    "Fail Target",
                    payload={
                        "target_unit_id": str(get_entity_id(fail_target) or ""),
                        "source_unit_id": str(get_entity_id(source) or ""),
                        "model_id": str(get_entity_id(bearer) or ""),
                    },
                )
            ],
            context={
                "ability": "opponent_shooting_phase_disrupt",
                "ability_name": "Amulet of Auto-Chastisement",
                "ability_key": "AMULET_OF_AUTO_CHASTISEMENT",
                "resolution_mode": "leadership_test",
                "required_target_keywords": ["VEHICLE"],
                "excluded_target_keywords": ["TITANIC"],
            },
        )
        fail_result = DecisionResult(
            decision_id=fail_request.decision_id,
            player_id=ia_player.id,
            option_id=fail_request.options[0].option_id,
        )
        _apply_choose_quarry(game, fail_request, fail_result)
        self.assertTrue(bool(fail_target.special_rules.get("shooting_phase_ineligible_active")))
        self.assertTrue(fail_target.is_shooting_phase_ineligible(game))
        self.assertEqual(str(fail_target.special_rules.get("shooting_phase_ineligible_owner", "") or ""), enemy_player.id)

    def test_beacon_angelis_grants_deep_strike_and_rapid_ingress_zero_cp(self):
        game, ia_army, _enemy_army, ia_player, _enemy_player = _build_game()
        unit = _make_unit(
            "Watch Master",
            keywords=["CHARACTER", "INFANTRY", "WATCH MASTER"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM", "DEATHWATCH"],
            wounds=6,
        )
        ia_army.add_unit(unit)
        unit.deployed = True
        game.map.units = [unit]
        game.rebuild_entity_registry()

        _apply_ordo_xenos_enhancement(
            unit,
            enhancement_id="000009126003",
            name="Beacon Angelis",
        )

        self.assertTrue(unit.has_deep_strike())
        rapid_ingress = SimpleNamespace(name="RAPID INGRESS", cp_cost=1)
        preview = ia_player.preview_stratagem_cp_cost(rapid_ingress, target_unit=unit)
        self.assertEqual(int(preview.get("cost", 99)), 0)
        self.assertTrue(any("Beacon Angelis" in str(reason) for reason in list(preview.get("reasons", []) or [])))

        apply_first = ia_player.apply_stratagem_cp_cost(rapid_ingress, target_unit=unit)
        apply_second = ia_player.apply_stratagem_cp_cost(rapid_ingress, target_unit=unit)
        self.assertEqual(int(apply_first.get("cost", 99)), 0)
        self.assertEqual(int(apply_second.get("cost", 99)), 0)

    def test_universal_anathema_grants_bearer_only_melee_anti_keywords(self):
        _game, ia_army, _enemy_army, _ia_player, _enemy_player = _build_game()
        bearer_unit = _make_unit(
            "Watch Master",
            keywords=["CHARACTER", "INFANTRY", "WATCH MASTER"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM", "DEATHWATCH"],
        )
        bearer_unit.models.append(_make_extra_model("Deathwatch Veteran", bearer_unit))
        ia_army.add_unit(bearer_unit)

        _apply_ordo_xenos_enhancement(
            bearer_unit,
            enhancement_id="000009126005",
            name="Universal Anathema",
        )

        bearer = _bearer_model(bearer_unit)
        self.assertIsNotNone(bearer)
        non_bearer = next(model for model in list(bearer_unit.models or []) if model is not bearer)

        bearer_melee = bearer_unit.get_model_weapon_keyword_bonuses(
            attack_type="melee",
            model=bearer,
            weapon_name="Guardian Spear",
        )
        anti_specs = {tuple(spec) for spec in list(bearer_melee.get("anti_specs") or [])}
        self.assertIn(("INFANTRY", 2), anti_specs)
        self.assertIn(("MONSTER", 4), anti_specs)

        bearer_ranged = bearer_unit.get_model_weapon_keyword_bonuses(
            attack_type="ranged",
            model=bearer,
            weapon_name="Boltgun",
        )
        self.assertEqual(list(bearer_ranged.get("anti_specs") or []), [])

        other_melee = bearer_unit.get_model_weapon_keyword_bonuses(
            attack_type="melee",
            model=non_bearer,
            weapon_name="Close Combat Weapon",
        )
        self.assertEqual(list(other_melee.get("anti_specs") or []), [])


if __name__ == "__main__":
    unittest.main()
