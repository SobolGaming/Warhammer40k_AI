from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.utility.modifier_choice import CHOICE_IGNORE_NEGATIVE


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Space Marines",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        wounds: int = 4,
        toughness: int = 4,
        move: int = 6,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            faction_keywords = ["ADEPTUS ASTARTES"] if faction_name == "Space Marines" else [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": str(int(move)),
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
    faction_name: str = "Space Marines",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: int = 4,
    toughness: int = 4,
    move: int = 6,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
            toughness=toughness,
            move=move,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    sm_army = Army.with_detachment("Space Marines", "Wrathful Procession")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    sm_player = Player("Space Marines", control=PlayerControl.LOCAL, army=sm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0

    sm_player.command_points = 10
    enemy_player.command_points = 10

    sm_army.configure_rule_managers(force=True)
    sm_player.stratagems.refresh_available()
    return game, sm_player, enemy_player, sm_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for index, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + float(index) * 1.5, float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _force_units_engaged(game: Game, first: Unit, second: Unit) -> None:
    original = getattr(game.map, "is_within_engagement_range", None)
    first_id = str(get_entity_id(first) or "")
    second_id = str(get_entity_id(second) or "")

    def _is_within_engagement_range(a, b):
        aid = str(get_entity_id(a) or "")
        bid = str(get_entity_id(b) or "")
        if {aid, bid} == {first_id, second_id}:
            return True
        if callable(original):
            return bool(original(a, b))
        return False

    game.map.is_within_engagement_range = _is_within_engagement_range


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=phase)


def _normalize_name(value: str) -> str:
    return str(value or "").strip().upper().replace("’", "'")


def _pending_by_name(stratagems, name: str):
    target = _normalize_name(name)
    for reaction in list(stratagems.get_pending_reactions() or []):
        if _normalize_name(str(reaction.get("stratagem", "") or "")) == target:
            return reaction
    return None


def _pending_names(stratagems) -> set[str]:
    return {_normalize_name(str(item.get("stratagem", "") or "")) for item in list(stratagems.get_pending_reactions(clear=True) or [])}


def _melee_wargear(
    name: str = "Power Sword",
    *,
    skill: str = "3+",
    strength: str = "4",
    description: str = "",
) -> Wargear:
    return Wargear(
        {
            "name": str(name),
            "type": "Melee",
            "range": "Melee",
            "A": "1",
            "BS_WS": str(skill),
            "S": str(strength),
            "AP": "0",
            "D": "1",
            "description": str(description),
        }
    )


def _first_profile(wargear: Wargear):
    return next(iter(dict(getattr(wargear, "profiles", {}) or {}).values()))


def test_wrathful_procession_stratagem_descriptors_registered():
    expected = {
        "000009844004": ("Castigate the Demagogues", "grant_precision_to_melee_weapons"),
        "000009844005": ("Brute Fervour", "ignore_skill_hit_wound_modifiers"),
        "000009844006": ("Relentless Momentum", "fight_eligibility_within_3"),
        "000009844007": ("Voice of Devotion", "unit_specific_zealous_litany_override"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=expected_name.upper())
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == expected_name
        assert by_name.name == expected_name
        assert by_id.effect == expected_effect


def test_wrathful_procession_phase_start_reactions_queue_expected_stratagems():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    crusaders = _make_unit(
        "Primaris Crusader Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    outriders = _make_unit(
        "Outriders",
        keywords=["MOUNTED"],
        faction_keywords=["ADEPTUS ASTARTES"],
        move=12,
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(crusaders)
    sm_army.add_unit(outriders)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, crusaders, 10.0, 10.0)
    _deploy_unit(game, outriders, 20.0, 10.0)
    _deploy_unit(game, enemy, 13.0, 10.0)
    game.rebuild_entity_registry()
    _force_units_engaged(game, crusaders, enemy)

    _set_phase(game, sm_player, "COMMAND_PHASE", 0)
    pending = _pending_by_name(sm_player.stratagems, "VOICE OF DEVOTION")
    assert pending is not None
    assert {str(option.get("choice_key", "") or "") for option in list(pending.get("choice_options") or [])} == {
        "CHORUS_OF_RELENTLESS_HATE",
        "RITE_OF_PERFERVID_WRATH",
        "CHANT_OF_DEATHLESS_DEVOTION",
    }
    sm_player.stratagems.get_pending_reactions(clear=True)

    _set_phase(game, sm_player, "FIGHT_PHASE", 0)
    assert _pending_names(sm_player.stratagems) == {
        "BRUTE FERVOUR",
        "CASTIGATE THE DEMAGOGUES",
        "RELENTLESS MOMENTUM",
    }


def test_voice_of_devotion_generic_tool_candidates_bind_unit_and_litany_choice():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    crusaders = _make_unit(
        "Crusader Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    outriders = _make_unit(
        "Outriders",
        keywords=["MOUNTED"],
        faction_keywords=["ADEPTUS ASTARTES"],
        move=12,
    )
    sm_army.add_unit(crusaders)
    sm_army.add_unit(outriders)
    _deploy_unit(game, crusaders, 10.0, 10.0)
    _deploy_unit(game, outriders, 20.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "COMMAND_PHASE", 0)
    pending = _pending_by_name(sm_player.stratagems, "VOICE OF DEVOTION")
    assert pending is not None

    item = {
        "name": "VOICE OF DEVOTION",
        "available": True,
        "is_reaction": True,
        "context": pending,
    }
    specs = sm_player.stratagems._build_tool_action_specs_for_item(item)

    assert len(specs) == 6
    assert sm_player.stratagems.get_tool_action_probe_diagnostics() == []
    for spec in specs:
        kwargs = spec["payload"]["resolved_kwargs"]
        assert kwargs["unit"] == kwargs["target_unit"]
        assert "__entity_ref__" in kwargs["unit"]
        assert kwargs["choice_key"] in {
            "CHORUS_OF_RELENTLESS_HATE",
            "RITE_OF_PERFERVID_WRATH",
            "CHANT_OF_DEATHLESS_DEVOTION",
        }
        assert kwargs["override_key"] == kwargs["choice_key"]


def test_voice_of_devotion_descriptor_choices_prevent_incomplete_generic_probes():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    crusaders = _make_unit(
        "Crusader Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    outriders = _make_unit(
        "Outriders",
        keywords=["MOUNTED"],
        faction_keywords=["ADEPTUS ASTARTES"],
        move=12,
    )
    sm_army.add_unit(crusaders)
    sm_army.add_unit(outriders)
    _deploy_unit(game, crusaders, 10.0, 10.0)
    _deploy_unit(game, outriders, 20.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "COMMAND_PHASE", 0)
    item = {
        "name": "VOICE OF DEVOTION",
        "available": True,
        "context": {"phase_name": "Command phase"},
    }
    specs = sm_player.stratagems._build_tool_action_specs_for_item(item)

    assert len(specs) == 6
    assert sm_player.stratagems.get_tool_action_probe_diagnostics() == []
    for spec in specs:
        kwargs = spec["payload"]["resolved_kwargs"]
        assert kwargs["unit"] == kwargs["target_unit"]
        assert "allowed_choice_keys" not in kwargs
        assert "choice_options" not in kwargs
        assert kwargs["choice_key"] in {
            "CHORUS_OF_RELENTLESS_HATE",
            "RITE_OF_PERFERVID_WRATH",
            "CHANT_OF_DEATHLESS_DEVOTION",
        }


def test_voice_of_devotion_overrides_only_the_selected_unit_until_battle_round_end():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    primary = _make_unit(
        "Sword Brethren",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        move=6,
    )
    secondary = _make_unit(
        "Crusader Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        move=6,
    )
    enemy = _make_unit(
        "Enemy Tough Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        toughness=5,
    )
    sm_army.add_unit(primary)
    sm_army.add_unit(secondary)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, primary, 10.0, 10.0)
    _deploy_unit(game, secondary, 20.0, 10.0)
    _deploy_unit(game, enemy, 12.0, 10.0)
    game.rebuild_entity_registry()

    mgr = sm_army.space_marines_detachments
    assert mgr.select_zealous_litany("CHORUS_OF_RELENTLESS_HATE", battle_round=1, player_id=sm_player.id)

    _set_phase(game, sm_player, "COMMAND_PHASE", 0)
    assert sm_player.stratagems.use(
        "VOICE OF DEVOTION",
        unit=primary,
        choice_key="RITE_OF_PERFERVID_WRATH",
        phase_name="Command phase",
        dequeue=True,
    )

    assert mgr.wrathful_procession_effective_litany_key(primary, game=game) == "RITE_OF_PERFERVID_WRATH"
    assert mgr.wrathful_procession_effective_litany_key(secondary, game=game) == "CHORUS_OF_RELENTLESS_HATE"
    assert int(primary.get_effective_model_characteristic(primary.models[0], "movement")) == 6
    assert int(secondary.get_effective_model_characteristic(secondary.models[0], "movement")) == 8

    primary_profile = _first_profile(_melee_wargear())
    secondary_profile = _first_profile(_melee_wargear())
    primary_result = primary_profile._wound_target_with_tracking(
        enemy,
        primary.models[0],
        {"distance_to_target": 1.0},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    secondary_result = secondary_profile._wound_target_with_tracking(
        enemy,
        secondary.models[0],
        {"distance_to_target": 1.0},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(primary_result.get("wound", False)) is True
    assert bool(secondary_result.get("wound", False)) is False

    game.turn = 2
    assert mgr.wrathful_procession_effective_litany_key(primary, game=game) == ""
    assert int(primary.get_effective_model_characteristic(primary.models[0], "movement")) == 6


def test_castigate_the_demagogues_grants_precision_and_cleans_up():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    brethren = _make_unit(
        "Sword Brethren",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    brethren.models[0].wargear = [_melee_wargear()]
    sm_army.add_unit(brethren)
    _deploy_unit(game, brethren, 10.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "FIGHT_PHASE", 0)
    assert sm_player.stratagems.use("CASTIGATE THE DEMAGOGUES", unit=brethren, dequeue=True)

    bonuses = brethren.models[0].get_temporary_weapon_keyword_bonuses("Power Sword")
    assert any(
        str(item.get("keyword", "") or "").strip().upper() == "PRECISION"
        and str(item.get("attack_type", "") or "").strip().lower() == "melee"
        for item in list(bonuses or [])
    )

    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert list(brethren.models[0].get_temporary_weapon_keyword_bonuses("Power Sword") or []) == []


def test_relentless_momentum_enables_fight_within_three_and_cleans_up():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    crusaders = _make_unit(
        "Primaris Crusader Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(crusaders)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, crusaders, 10.0, 10.0)
    _deploy_unit(game, enemy, 13.0, 10.0)
    game.rebuild_entity_registry()
    _force_units_engaged(game, crusaders, enemy)

    _set_phase(game, sm_player, "FIGHT_PHASE", 0)
    assert sm_player.stratagems.use("RELENTLESS MOMENTUM", unit=crusaders, dequeue=True)

    assert crusaders.fight_within_3_active() is True
    assert crusaders.get_fight_within_3_sources() == ["RELENTLESS MOMENTUM"]

    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert crusaders.fight_within_3_active() is False
    assert crusaders.get_fight_within_3_sources() == []


def test_brute_fervour_applies_reroll_and_modifier_ignore_rules_then_cleans_up():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    crusaders = _make_unit(
        "Primaris Crusader Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        toughness=4,
    )
    weapon = _melee_wargear()
    profile = _first_profile(weapon)
    crusaders.models[0].wargear = [weapon]
    sm_army.add_unit(crusaders)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, crusaders, 10.0, 10.0)
    _deploy_unit(game, enemy, 13.0, 10.0)
    game.rebuild_entity_registry()
    _force_units_engaged(game, crusaders, enemy)

    _set_phase(game, sm_player, "FIGHT_PHASE", 0)
    assert sm_player.stratagems.use("BRUTE FERVOUR", unit=crusaders, dequeue=True)

    mgr = sm_army.space_marines_detachments
    reroll_hit_ones, source = mgr.wrathful_procession_brute_fervour_reroll_hit_ones(
        crusaders.models[0],
        attack_type="melee",
        game=game,
    )
    assert reroll_hit_ones is True
    assert source == "BRUTE FERVOUR"

    ignore_hit_rule = profile._ignore_hit_modifier_rule(crusaders.models[0])
    assert ignore_hit_rule is not None
    assert ignore_hit_rule.get("attack_type") == "melee"
    assert set(ignore_hit_rule.get("skill_kinds") or set()) == {"weapon"}

    hit_attack = {"hit_roll_modifiers": [(-1, "Test penalty")]}
    hit_result = profile._hit_target_with_tracking(
        enemy,
        crusaders.models[0],
        hit_attack,
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert hit_result.get("hit") is True
    assert hit_attack.get("hit_modifier_choice") == CHOICE_IGNORE_NEGATIVE

    ignore_wound_rule = profile._ignore_wound_modifier_rule(crusaders.models[0])
    assert ignore_wound_rule is not None
    assert ignore_wound_rule.get("attack_type") == "melee"

    wound_attack = {"wound_roll_modifiers": [(-1, "Test penalty")]}
    wound_result = profile._wound_target_with_tracking(
        enemy,
        crusaders.models[0],
        wound_attack,
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert wound_result.get("wound") is True

    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    reroll_after, _source_after = mgr.wrathful_procession_brute_fervour_reroll_hit_ones(
        crusaders.models[0],
        attack_type="melee",
        game=game,
    )
    assert reroll_after is False
    assert profile._ignore_hit_modifier_rule(crusaders.models[0]) is None
