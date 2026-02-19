from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


class _MockDatasheet:
    def __init__(self, name: str, *, faction: str, keywords=None, faction_keywords=None):
        self.id = ""
        self.name = name
        self.faction_data = {"name": faction}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "3",
                "Sv": "5",
                "W": "2",
                "Ld": "7",
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
        self.attached_to = []


def _make_unit(name: str, *, faction: str, faction_keywords: list[str], keywords: list[str]) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction=faction,
            keywords=keywords,
            faction_keywords=faction_keywords,
        )
    )
    model = unit.models[0]
    model.wargear.append(
        SimpleNamespace(
            _id=f"{name}:autopistol",
            name="Autopistol",
            is_ranged=lambda: True,
            is_melee=lambda: False,
            profiles={},
        )
    )
    model.wargear.append(
        SimpleNamespace(
            _id=f"{name}:cult_knife",
            name="Cult Knife",
            is_ranged=lambda: False,
            is_melee=lambda: True,
            profiles={},
        )
    )
    unit.deployed = True
    return unit


def _make_game(
    detachment_type: str,
    *,
    gsc_control: PlayerControl = PlayerControl.LOCAL,
    enemy_control: PlayerControl = PlayerControl.LOCAL,
) -> tuple[Game, Player, Player, Unit]:
    gsc_army = Army("Genestealer Cults", detachment_type)
    gsc_army.faction_id = "GC"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "ENEMY"

    gsc_player = Player("GSC", gsc_control, army=gsc_army)
    enemy_player = Player("Enemy", enemy_control, army=enemy_army)

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[gsc_player, enemy_player])
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game.turn = 1

    gsc_unit = _make_unit(
        "Neophyte Hybrids",
        faction="Genestealer Cults",
        faction_keywords=["GENESTEALER CULTS"],
        keywords=["INFANTRY"],
    )
    gsc_army.add_unit(gsc_unit)
    game.map.units = [gsc_unit]
    game.rebuild_entity_registry()
    return game, gsc_player, enemy_player, gsc_unit


def _weapon_bonuses(unit: Unit, weapon_name: str, *, attack_type: str) -> dict:
    return unit.get_model_weapon_keyword_bonuses(
        model=unit.models[0],
        weapon_name=weapon_name,
        attack_type=attack_type,
    )


def _apply_enhancement(unit: Unit, *, enhancement_id: str, name: str, description: str) -> Enhancement:
    enhancement = Enhancement(
        id=enhancement_id,
        name=name,
        faction_id="GC",
        detachment="Host of Ascension",
        description=description,
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)
    return enhancement


def _resolve_yes(game: Game, request, *, player_id: str) -> None:
    option_id = None
    for opt in list(getattr(request, "options", []) or []):
        if bool((getattr(opt, "payload", {}) or {}).get("choice", False)):
            option_id = opt.option_id
            break
    assert option_id is not None
    resolve_decision_command(game, request, option_id, player_id=player_id)


def test_a_perfect_ambush_applies_on_reinforcements_setup() -> None:
    game, _gsc_player, _enemy_player, gsc_unit = _make_game("Host of Ascension")
    game.current_player_index = 0

    game.event_system.publish(
        "unit_set_up",
        unit=gsc_unit,
        set_up_as_reinforcements=True,
    )

    ranged_bonuses = _weapon_bonuses(gsc_unit, "Autopistol", attack_type="ranged")
    assert ranged_bonuses.get("sustained_hits_value", 0) == 1
    assert ranged_bonuses.get("ignores_cover", False) is True

    melee_bonuses = _weapon_bonuses(gsc_unit, "Cult Knife", attack_type="melee")
    assert melee_bonuses.get("sustained_hits_value", 0) == 1
    assert melee_bonuses.get("ignores_cover", False) is True


def test_a_perfect_ambush_expires_at_end_of_owners_next_fight_phase() -> None:
    game, gsc_player, enemy_player, gsc_unit = _make_game("Host of Ascension")
    game.current_player_index = 1

    game.event_system.publish(
        "unit_set_up",
        unit=gsc_unit,
        set_up_as_reinforcements=True,
    )

    before_cleanup = _weapon_bonuses(gsc_unit, "Autopistol", attack_type="ranged")
    assert before_cleanup.get("sustained_hits_value", 0) == 1
    assert before_cleanup.get("ignores_cover", False) is True

    game._on_phase_end_cleanup(player=enemy_player, phase=BattleRoundPhases.FIGHT_PHASE)
    after_enemy_fight = _weapon_bonuses(gsc_unit, "Autopistol", attack_type="ranged")
    assert after_enemy_fight.get("sustained_hits_value", 0) == 1
    assert after_enemy_fight.get("ignores_cover", False) is True

    game._on_phase_end_cleanup(player=gsc_player, phase=BattleRoundPhases.FIGHT_PHASE)
    after_owner_fight = _weapon_bonuses(gsc_unit, "Autopistol", attack_type="ranged")
    assert after_owner_fight.get("sustained_hits_value", 0) == 0
    assert after_owner_fight.get("ignores_cover", False) is False


def test_host_of_ascension_enhancement_descriptors_registered() -> None:
    prowling = get_enhancement_tool_descriptor(enhancement_id="000009067002")
    assert prowling is not None
    assert prowling.name == "Prowling Agitant"
    assert prowling.effect == "reactive_normal_move_up_to_d6"

    chink = get_enhancement_tool_descriptor(enhancement_id="000009067003")
    assert chink is not None
    assert chink.name == "A Chink in Their Armour"
    assert chink.effect == "grant_weapon_keywords"
    assert tuple(chink.effect_params.get("keywords", ())) == ("LETHAL HITS",)

    our_time = get_enhancement_tool_descriptor(enhancement_id="000009067004")
    assert our_time is not None
    assert our_time.name == "Our Time Is Nigh"
    assert our_time.once_per_battle is True
    assert int(our_time.effect_params.get("charge_roll_bonus", 0) or 0) == 2

    edict = get_enhancement_tool_descriptor(enhancement_id="000009067005")
    assert edict is not None
    assert edict.name == "Assassination Edict"
    assert edict.effect == "add_hit_roll_modifier"
    assert int(edict.effect_params.get("hit_roll_bonus", 0) or 0) == 1


def test_a_chink_in_their_armour_grants_ranged_lethal_hits_on_reinforcements() -> None:
    game, gsc_player, enemy_player, gsc_unit = _make_game("Host of Ascension")
    game.current_player_index = 1
    _apply_enhancement(
        gsc_unit,
        enhancement_id="000009067003",
        name="A Chink in Their Armour",
        description=(
            "GENESTEALER CULTS model only. Each time the bearer is set up on the battlefield as Reinforcements, "
            "until the end of your next Fight phase, ranged weapons equipped by models in the bearer's unit have "
            "the [LETHAL HITS] ability."
        ),
    )

    game.event_system.publish(
        "unit_set_up",
        unit=gsc_unit,
        set_up_as_reinforcements=True,
    )

    ranged_bonuses = _weapon_bonuses(gsc_unit, "Autopistol", attack_type="ranged")
    assert ranged_bonuses.get("lethal_hits", False) is True
    melee_bonuses = _weapon_bonuses(gsc_unit, "Cult Knife", attack_type="melee")
    assert melee_bonuses.get("lethal_hits", False) is False

    game._on_phase_end_cleanup(player=enemy_player, phase=BattleRoundPhases.FIGHT_PHASE)
    still_active = _weapon_bonuses(gsc_unit, "Autopistol", attack_type="ranged")
    assert still_active.get("lethal_hits", False) is True

    game._on_phase_end_cleanup(player=gsc_player, phase=BattleRoundPhases.FIGHT_PHASE)
    expired = _weapon_bonuses(gsc_unit, "Autopistol", attack_type="ranged")
    assert expired.get("lethal_hits", False) is False


def test_prowling_agitant_triggers_loping_speed_prompt_from_bearers_unit_wording() -> None:
    game, _gsc_player, enemy_player, gsc_unit = _make_game("Host of Ascension")
    enemy_unit = _make_unit(
        "Enemy Movers",
        faction="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY"],
    )
    enemy_player.army.add_unit(enemy_unit)
    _apply_enhancement(
        gsc_unit,
        enhancement_id="000009067002",
        name="Prowling Agitant",
        description=(
            "GENESTEALER CULTS model only. Once per turn, when an enemy unit ends a Normal, Advance or Fall Back "
            "move within 9\" of the bearer's unit, if the bearer's unit is not within Engagement Range of any enemy "
            "units, it can make a Normal move of up to D6\"."
        ),
    )

    gsc_unit.models[0].set_location(8.0, 0.0, 0.0, 0.0)
    enemy_unit.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    game.map.units = [gsc_unit, enemy_unit]
    game.rebuild_entity_registry()

    prompts = []
    game.event_system.subscribe("loping_speed_prompt", lambda **kwargs: prompts.append(kwargs))
    game.event_system.publish("unit_move_ended", unit=enemy_unit, action="move")

    assert len(prompts) == 1
    assert prompts[0].get("unit") is gsc_unit
    assert prompts[0].get("moving_unit") is enemy_unit


def test_our_time_is_nigh_is_optional_and_applies_after_confirmation() -> None:
    game, gsc_player, enemy_player, gsc_unit = _make_game(
        "Host of Ascension",
        gsc_control=PlayerControl.REMOTE,
        enemy_control=PlayerControl.REMOTE,
    )
    game.phase = BattleRoundPhases.CHARGE_PHASE
    game.current_player_index = 0
    _apply_enhancement(
        gsc_unit,
        enhancement_id="000009067004",
        name="Our Time Is Nigh",
        description=(
            "GENESTEALER CULTS model only. Once per battle, when the bearer's unit declares a charge, the bearer can "
            "use this Enhancement. If it does, until the end of the phase, add 2 to Charge rolls made for the bearer's unit."
        ),
    )

    target = _make_unit(
        "Target Unit",
        faction="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY"],
    )
    enemy_player.army.add_unit(target)
    game.map.units = [gsc_unit, target]
    game.rebuild_entity_registry()

    gsc_unit._can_declare_charge_base = lambda _game, out_of_turn=False: True
    gsc_unit.can_declare_charge_against = lambda _target, _game, out_of_turn=False: True

    mods_before = list(game.get_charge_roll_modifiers(gsc_unit, target_unit=target))
    assert not any("our time is nigh" in str(source or "").strip().lower() for _val, source in mods_before)

    declared = game.declare_charge(gsc_unit, [target])
    assert declared is not None

    pending = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CONFIRM_YES_NO
        and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "our_time_is_nigh"
    ]
    assert len(pending) == 1
    _resolve_yes(game, pending[0], player_id=gsc_player.id)

    assert gsc_unit.has_used_unit_once_per_battle("our_time_is_nigh")
    mods_after = list(game.get_charge_roll_modifiers(gsc_unit, target_unit=target))
    assert any(int(val or 0) == 2 and "our time is nigh" in str(source or "").strip().lower() for val, source in mods_after)

    game.phase = BattleRoundPhases.FIGHT_PHASE
    mods_after_phase = list(game.get_charge_roll_modifiers(gsc_unit, target_unit=target))
    assert not any("our time is nigh" in str(source or "").strip().lower() for _val, source in mods_after_phase)


def test_assassination_edict_adds_hit_against_character_targets() -> None:
    game, _gsc_player, enemy_player, gsc_unit = _make_game("Host of Ascension")
    _apply_enhancement(
        gsc_unit,
        enhancement_id="000009067005",
        name="Assassination Edict",
        description=(
            "GENESTEALER CULTS model only. Each time a model in the bearer's unit makes an attack that targets a "
            "CHARACTER unit, add 1 to the Hit roll."
        ),
    )

    character_target = _make_unit(
        "Enemy Character",
        faction="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["CHARACTER", "INFANTRY"],
    )
    non_character_target = _make_unit(
        "Enemy Infantry",
        faction="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY"],
    )
    enemy_player.army.add_unit(character_target)
    enemy_player.army.add_unit(non_character_target)
    game.map.units = [gsc_unit, character_target, non_character_target]

    mods_vs_character = gsc_unit.get_unit_hit_reroll_modifiers("ranged", target=character_target)
    assert int(mods_vs_character.get("hit", 0) or 0) >= 1
    assert any("assassination edict" in str(reason or "").strip().lower() for reason in mods_vs_character.get("hit_reasons", ()))

    mods_vs_non_character = gsc_unit.get_unit_hit_reroll_modifiers("ranged", target=non_character_target)
    assert not any(
        "assassination edict" in str(reason or "").strip().lower()
        for reason in mods_vs_non_character.get("hit_reasons", ())
    )
