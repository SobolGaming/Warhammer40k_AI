from __future__ import annotations

from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
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
        keywords=None,
        faction_keywords=None,
        toughness: str = "4",
    ) -> None:
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": str(toughness),
                "Sv": "3",
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


def _normalize_name(name: str) -> str:
    text = str(name or "")
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    text = text.replace("\u2011", "-").replace("\u2013", "-").replace("\u2014", "-")
    return text.strip().upper()


def _find_stratagem_name(player: Player, canonical_name: str) -> str:
    target = _normalize_name(canonical_name)
    for stratagem in list(player.stratagems.available or []):
        name = str(getattr(stratagem, "name", "") or "")
        if _normalize_name(name) == target:
            return name
    raise AssertionError(f"Missing stratagem '{canonical_name}' in available list.")


def _make_unit(
    name: str,
    *,
    keywords=None,
    faction_keywords=None,
    toughness: str = "4",
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            toughness=toughness,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _deploy_unit(unit: Unit, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)


def _build_game():
    battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield)

    shadow_army = Army("Chaos Daemons", "Shadow Legion")
    shadow_army.faction_id = "CD"
    shadow_army.detachment_type = "Shadow Legion"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    shadow_player = Player("P1", control=PlayerControl.LOCAL, army=shadow_army)
    enemy_player = Player("P2", control=PlayerControl.LOCAL, army=enemy_army)

    game.add_player(shadow_player)
    game.add_player(enemy_player)

    shadow_player.command_points = 5
    enemy_player.command_points = 5
    return game, shadow_player, enemy_player, shadow_army, enemy_army


def test_shadow_legion_step1_stratagem_descriptors_registered():
    binding = get_stratagem_tool_descriptor(stratagem_id="000009979007")
    assert binding is not None
    assert binding.name == "Binding Shadow"
    assert binding.effect == "enter_strategic_reserves"
    assert int(binding.cp_cost) == 1

    wrath = get_stratagem_tool_descriptor(stratagem_id="000009979003")
    assert wrath is not None
    assert wrath.name == "Channelled Wrath"
    assert wrath.effect == "melee_weapons_gain_lance_and_khorne_ap_bonus"
    assert int(wrath.cp_cost) == 1

    by_name_binding = get_stratagem_tool_descriptor(name="BINDING SHADOW")
    assert by_name_binding is not None
    assert str(by_name_binding.stratagem_id) == "000009979007"

    by_name_wrath = get_stratagem_tool_descriptor(name="CHANNELLED WRATH")
    assert by_name_wrath is not None
    assert str(by_name_wrath.stratagem_id) == "000009979003"


def test_channelled_wrath_grants_lance_and_khorne_ap_until_fight_phase_end():
    game, shadow_player, _enemy_player, shadow_army, enemy_army = _build_game()
    shadow_unit = _make_unit(
        "Khorne Unit",
        keywords=["LEGIONES DAEMONICA", "KHORNE"],
    )
    enemy_unit = _make_unit("Enemy Unit", keywords=["INFANTRY"], toughness="5")
    shadow_army.add_unit(shadow_unit)
    enemy_army.add_unit(enemy_unit)
    game.map.units.extend([shadow_unit, enemy_unit])
    _deploy_unit(shadow_unit, 0.0, 0.0)
    _deploy_unit(enemy_unit, 1.0, 0.0)

    game.turn = 2
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.current_player_index = 0
    game.event_system.publish("phase_start", player=shadow_player, phase=BattleRoundPhases.FIGHT_PHASE)

    assert shadow_unit.has_any_keyword("SHADOW LEGION")
    shadow_unit.round_state.charged_this_round = True
    shadow_unit.round_state.fought_this_phase = False

    wrath_name = _find_stratagem_name(shadow_player, "CHANNELLED WRATH")
    ok = shadow_player.stratagems.use(
        wrath_name,
        unit=shadow_unit,
        phase_name="Fight phase",
    )
    assert ok is True
    assert shadow_player.command_points == 4

    weapon = Wargear(
        {
            "name": "Test Blade",
            "type": "Melee",
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )
    profile = weapon.profiles["default"]

    wound_result = profile._wound_target_with_tracking(
        enemy_unit,
        shadow_unit.models[0],
        {},
        roll_value=4,
        log_roll=False,
    )
    assert int(wound_result.get("final_needed", 0) or 0) == 4
    assert any("CHANNELLED WRATH" in str(modifier or "").upper() for modifier in list(wound_result.get("modifiers", []) or []))
    assert int(profile.get_effective_ap(shadow_unit.models[0], enemy_unit)) == -1

    game.event_system.publish("phase_end", player=shadow_player, phase=BattleRoundPhases.FIGHT_PHASE)
    rules = dict(getattr(shadow_unit, "special_rules", {}) or {})
    assert "shadow_legion_channelled_wrath_active" not in rules
    assert "shadow_legion_channelled_wrath_lance_active" not in rules
    assert "shadow_legion_channelled_wrath_ap_bonus" not in rules

    wound_result_after = profile._wound_target_with_tracking(
        enemy_unit,
        shadow_unit.models[0],
        {},
        roll_value=4,
        log_roll=False,
    )
    assert int(wound_result_after.get("final_needed", 0) or 0) == 5
    assert int(profile.get_effective_ap(shadow_unit.models[0], enemy_unit)) == 0


def test_channelled_wrath_rejects_unit_already_selected_to_fight():
    game, shadow_player, _enemy_player, shadow_army, enemy_army = _build_game()
    shadow_unit = _make_unit(
        "Chosen",
        keywords=["HERETIC ASTARTES"],
    )
    enemy_unit = _make_unit("Enemy Unit", keywords=["INFANTRY"])
    shadow_army.add_unit(shadow_unit)
    enemy_army.add_unit(enemy_unit)
    game.map.units.extend([shadow_unit, enemy_unit])
    _deploy_unit(shadow_unit, 0.0, 0.0)
    _deploy_unit(enemy_unit, 1.0, 0.0)

    game.turn = 2
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.current_player_index = 0
    game.event_system.publish("phase_start", player=shadow_player, phase=BattleRoundPhases.FIGHT_PHASE)

    shadow_unit.round_state.fought_this_phase = True
    wrath_name = _find_stratagem_name(shadow_player, "CHANNELLED WRATH")
    ok = shadow_player.stratagems.use(
        wrath_name,
        unit=shadow_unit,
        phase_name="Fight phase",
    )
    assert ok is False
    assert shadow_player.command_points == 5


def test_binding_shadow_queues_on_phase_end_and_moves_units_to_reserves():
    game, shadow_player, enemy_player, shadow_army, enemy_army = _build_game()
    heretic = _make_unit("Chaos Lord", keywords=["HERETIC ASTARTES"])
    daemon = _make_unit("Bloodletters", keywords=["LEGIONES DAEMONICA"])
    engaged_daemon = _make_unit("Engaged Daemon", keywords=["LEGIONES DAEMONICA"])
    enemy_blocker = _make_unit("Enemy Blocker", keywords=["INFANTRY"])
    enemy_other = _make_unit("Enemy Other", keywords=["INFANTRY"])

    shadow_army.add_unit(heretic)
    shadow_army.add_unit(daemon)
    shadow_army.add_unit(engaged_daemon)
    enemy_army.add_unit(enemy_blocker)
    enemy_army.add_unit(enemy_other)
    game.map.units.extend([heretic, daemon, engaged_daemon, enemy_blocker, enemy_other])

    _deploy_unit(heretic, 0.0, 0.0)
    _deploy_unit(daemon, 8.0, 0.0)
    _deploy_unit(engaged_daemon, 16.0, 0.0)
    _deploy_unit(enemy_blocker, 16.5, 0.0)
    _deploy_unit(enemy_other, 30.0, 0.0)

    game.turn = 2
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.current_player_index = 1
    game.event_system.publish("phase_start", player=enemy_player, phase=BattleRoundPhases.FIGHT_PHASE)

    game.event_system.publish("phase_end", player=enemy_player, phase=BattleRoundPhases.FIGHT_PHASE)
    pending = shadow_player.stratagems.get_pending_reactions()
    binding_reactions = [
        reaction
        for reaction in list(pending or [])
        if _normalize_name(str(reaction.get("stratagem", "") or "")) == "BINDING SHADOW"
    ]
    assert len(binding_reactions) == 1

    reaction = binding_reactions[0]
    reaction_candidates = list(reaction.get("candidates", []) or [])
    assert heretic in reaction_candidates
    assert daemon in reaction_candidates
    assert engaged_daemon not in reaction_candidates

    binding_name = _find_stratagem_name(shadow_player, "BINDING SHADOW")
    ok = shadow_player.stratagems.use(
        binding_name,
        units=[heretic, daemon],
        phase_name="Fight phase",
        dequeue=True,
    )
    assert ok is True
    assert shadow_player.command_points == 4
    assert heretic.reserve_status == "strategic_reserves"
    assert daemon.reserve_status == "strategic_reserves"
