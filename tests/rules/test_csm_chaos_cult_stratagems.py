from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Chaos Space Marines",
        keywords=None,
        faction_keywords=None,
        wounds: str = "4",
        toughness: str = "4",
        leadership: str = "7",
        model_count: int = 1,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Model"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": str(toughness),
                "Sv": "3",
                "W": str(wounds),
                "Ld": str(leadership),
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "0",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Chaos Space Marines",
    keywords=None,
    faction_keywords=None,
    wounds: str = "4",
    toughness: str = "4",
    leadership: str = "7",
    model_count: int = 1,
    dark_pacts: bool = False,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            wounds=wounds,
            toughness=toughness,
            leadership=leadership,
            model_count=model_count,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    if dark_pacts:
        unit.possible_abilities = ["Dark Pacts"]
        unit.has_dark_pacts = lambda: True
    return unit


def _make_profile(
    *,
    melee: bool,
    attacks: str = "1",
    strength: str = "4",
    ap: str = "0",
    damage: str = "1",
):
    weapon = Wargear(
        {
            "name": "Test Weapon",
            "type": "Melee" if melee else "Ranged",
            "range": "Melee" if melee else "24",
            "A": str(attacks),
            "BS_WS": "3+",
            "S": str(strength),
            "AP": str(ap),
            "D": str(damage),
            "description": "",
        }
    )
    return weapon.profiles["default"]


def _build_game():
    battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield)

    csm_army = Army("Chaos Space Marines", "Chaos Cult")
    csm_army.faction_id = "CSM"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    csm_player = Player("CSM", control=PlayerControl.LOCAL, army=csm_army)
    enemy_player = Player("EN", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(csm_player)
    game.add_player(enemy_player)

    csm_player.command_points = 10
    enemy_player.command_points = 10
    csm_army.configure_rule_managers(force=True)
    csm_player.stratagems.refresh_available()
    game.rebuild_entity_registry()
    return game, csm_player, enemy_player, csm_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    if unit not in game.map.units:
        game.map.units.append(unit)


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    phase = getattr(BattleRoundPhases, str(phase_name or "").strip(), None)
    game.phase = phase if phase is not None else SimpleNamespace(name=phase_name)
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=game.phase)


def _contains_text(entries, expected: str) -> bool:
    expected_lower = str(expected or "").strip().lower()
    return any(expected_lower in str(entry or "").strip().lower() for entry in list(entries or []))


def test_chaos_cult_stratagem_descriptors_registered():
    expected = {
        "000008982002": "Chosen for Glory",
        "000008982003": "Selfless Demise",
        "000008982004": "Infernal Sacrifice",
        "000008982005": "Crazed Focus",
        "000008982006": "Reckless Haste",
        "000008982007": "Mortal Thralls",
    }

    for stratagem_id, name in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        by_name = get_stratagem_tool_descriptor(name=name)
        assert by_id is not None
        assert by_id.name == name
        assert by_name is not None
        assert by_name.stratagem_id == stratagem_id


def test_chosen_for_glory_grants_hit_and_wound_rerolls_when_pact_passes():
    game, csm_player, _enemy_player, csm_army, enemy_army = _build_game()
    shooter = _make_unit(
        "Accursed Cultists",
        keywords=["DAMNED", "INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
        dark_pacts=True,
    )
    shooter.pass_leadership_check = lambda: True
    enemy = _make_unit("Enemy", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    csm_army.add_unit(shooter)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, shooter, 10.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, csm_player, "SHOOTING_PHASE", 0)
    assert csm_player.stratagems.use("CHOSEN FOR GLORY", unit=shooter, phase_name="Shooting phase")

    profile = _make_profile(melee=False)
    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=4):
        hit_result = profile._hit_target_with_tracking(
            enemy,
            shooter.models[0],
            {},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )
        wound_result = profile._wound_target_with_tracking(
            enemy,
            shooter.models[0],
            {},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
    )

    assert hit_result["hit"] is True
    assert int(hit_result.get("reroll", 0) or 0) == 4
    assert _contains_text(hit_result.get("special_effects", []), "Chosen for Glory")
    assert wound_result["wound"] is True
    assert int(wound_result.get("reroll", 0) or 0) == 4
    assert _contains_text(wound_result.get("special_effects", []), "Chosen for Glory")


def test_chosen_for_glory_failed_pact_still_rerolls_hit_but_not_wound():
    game, csm_player, _enemy_player, csm_army, enemy_army = _build_game()
    shooter = _make_unit(
        "Accursed Cultists",
        keywords=["DAMNED", "INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
        dark_pacts=True,
    )
    shooter.pass_leadership_check = lambda: False
    enemy = _make_unit("Enemy", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"], toughness="4")
    csm_army.add_unit(shooter)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, shooter, 10.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, csm_player, "SHOOTING_PHASE", 0)
    with patch("warhammer40k_ai.rules.chaos_space_marines_detachments.get_roll", return_value=2):
        assert csm_player.stratagems.use("CHOSEN FOR GLORY", unit=shooter, phase_name="Shooting phase")
    assert int(shooter.models[0].wounds) == 2

    profile = _make_profile(melee=False)
    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=4):
        hit_result = profile._hit_target_with_tracking(
            enemy,
            shooter.models[0],
            {},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )
        wound_result = profile._wound_target_with_tracking(
            enemy,
            shooter.models[0],
            {},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )

    assert hit_result["hit"] is True
    assert int(hit_result.get("reroll", 0) or 0) == 4
    assert wound_result["wound"] is False
    assert "reroll" not in wound_result


def test_crazed_focus_improves_ranged_ap_and_strength_when_pact_passes():
    game, csm_player, _enemy_player, csm_army, enemy_army = _build_game()
    shooter = _make_unit(
        "Traitor Guardsmen Squad",
        keywords=["DAMNED", "INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
        dark_pacts=True,
    )
    shooter.pass_leadership_check = lambda: True
    enemy = _make_unit(
        "Enemy Tough",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        toughness="5",
    )
    csm_army.add_unit(shooter)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, shooter, 10.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, csm_player, "SHOOTING_PHASE", 0)
    assert csm_player.stratagems.use("CRAZED FOCUS", unit=shooter, phase_name="Shooting phase")

    profile = _make_profile(melee=False, strength="4", ap="0")
    assert int(profile.get_effective_ap(shooter.models[0], enemy)) == -1
    wound_result = profile._wound_target_with_tracking(
        enemy,
        shooter.models[0],
        {},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert wound_result["wound"] is True
    assert _contains_text(wound_result.get("modifiers", []), "Crazed Focus")


def test_infernal_sacrifice_adds_melee_attacks_strength_and_extra_mortals():
    game, csm_player, _enemy_player, csm_army, enemy_army = _build_game()
    fighter = _make_unit(
        "Accursed Cultists",
        keywords=["DAMNED", "INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
        dark_pacts=True,
    )
    fighter.pass_leadership_check = lambda: True
    enemy = _make_unit(
        "Enemy Tough",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        toughness="5",
    )
    csm_army.add_unit(fighter)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, fighter, 10.0, 10.0)
    _deploy_unit(game, enemy, 12.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, csm_player, "FIGHT_PHASE", 0)
    with patch("warhammer40k_ai.rules.chaos_space_marines_detachments.get_roll", return_value=2):
        assert csm_player.stratagems.use("INFERNAL SACRIFICE", unit=fighter, phase_name="Fight phase")
    assert int(fighter.models[0].wounds) == 2

    profile = _make_profile(melee=True, attacks="2", strength="4")
    preview = profile.preview_attack_count(enemy, fighter.models[0], publish_roll_event=False)
    assert int(preview.num_attacks) == 3
    wound_result = profile._wound_target_with_tracking(
        enemy,
        fighter.models[0],
        {},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert wound_result["wound"] is True
    assert _contains_text(wound_result.get("modifiers", []), "Infernal Sacrifice")


def test_reckless_haste_allows_charge_after_advance_until_charge_phase_end():
    game, csm_player, _enemy_player, csm_army, _enemy_army = _build_game()
    unit = _make_unit(
        "Traitor Guardsmen Squad",
        keywords=["DAMNED", "INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    csm_army.add_unit(unit)
    _deploy_unit(game, unit, 10.0, 10.0)
    game.rebuild_entity_registry()

    unit.round_state.advanced_this_round = True
    assert not unit.can_charge_after_advance()

    _set_phase(game, csm_player, "CHARGE_PHASE", 0)
    assert csm_player.stratagems.use("RECKLESS HASTE", unit=unit, phase_name="Charge phase")
    assert unit.can_charge_after_advance()

    game.event_system.publish("phase_end", player=csm_player, phase=game.phase)
    assert not unit.can_charge_after_advance()


def test_mortal_thralls_queues_and_redirects_wound_rolls_to_support_unit():
    game, csm_player, enemy_player, csm_army, enemy_army = _build_game()
    protected = _make_unit(
        "Legionaries",
        keywords=["INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    support = _make_unit(
        "Cultists Mob",
        keywords=["DAMNED", "INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    attacker = _make_unit("Enemy Shooters", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    csm_army.add_unit(protected)
    csm_army.add_unit(support)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, protected, 10.0, 10.0)
    _deploy_unit(game, support, 12.0, 10.0)
    _deploy_unit(game, attacker, 18.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish(
        "shooting_targets_selected",
        attacking_unit=attacker,
        target_units=[protected],
    )
    pending = csm_player.stratagems.get_pending_reactions()
    assert any(str(r.get("stratagem", "")).upper() == "MORTAL THRALLS" for r in pending)

    assert csm_player.stratagems.use(
        "MORTAL THRALLS",
        unit=protected,
        support_unit=support,
        phase_name="Shooting phase",
        dequeue=True,
    )

    profile = _make_profile(melee=False, damage="2")
    protected_before = int(protected.models[0].wounds)
    support_before = int(support.models[0].wounds)
    wound_result = profile._wound_target_with_tracking(
        protected,
        attacker.models[0],
        {},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )

    assert wound_result["wound"] is False
    assert int(protected.models[0].wounds) == protected_before
    assert int(support.models[0].wounds) == support_before - 2
    assert _contains_text(wound_result.get("special_effects", []), "Mortal Thralls")


def test_selfless_demise_queues_and_resolves_post_attack_mortal_retaliation():
    game, csm_player, enemy_player, csm_army, enemy_army = _build_game()
    doomed = _make_unit(
        "Cultists Mob",
        keywords=["DAMNED", "INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
        wounds="1",
        model_count=2,
    )
    attacker = _make_unit("Enemy Fighters", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    csm_army.add_unit(doomed)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, doomed, 10.0, 10.0)
    _deploy_unit(game, attacker, 11.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish(
        "fight_targets_selected",
        attacking_unit=attacker,
        target_units=[doomed],
    )
    pending = csm_player.stratagems.get_pending_reactions()
    assert any(str(r.get("stratagem", "")).upper() == "SELFLESS DEMISE" for r in pending)

    assert csm_player.stratagems.use(
        "SELFLESS DEMISE",
        unit=doomed,
        phase_name="Fight phase",
        dequeue=True,
    )

    profile = _make_profile(melee=True)
    before_attacker_wounds = int(attacker.models[0].wounds)
    profile._apply_damage_with_tracking(
        doomed.models[0],
        attacker.models[0],
        1,
        False,
        attack_instance={},
        game_map=game.map,
    )

    with patch("warhammer40k_ai.engine.game_mixins.shooting_fight_handlers_mixin.get_roll", return_value=6):
        game._on_fight_sequence_complete_allocated_melee_mortal_retaliation(unit=attacker)

    assert int(attacker.models[0].wounds) == before_attacker_wounds - 1
