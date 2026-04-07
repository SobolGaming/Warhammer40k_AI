from __future__ import annotations

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        datasheet_id: str,
        faction_name: str,
        keywords: list[str] | None = None,
        faction_keywords: list[str] | None = None,
        attached_to: list[str] | None = None,
        toughness: str = "5",
    ) -> None:
        self.id = datasheet_id
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.attached_to = list(attached_to or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "5",
                "T": toughness,
                "Sv": "3",
                "W": "4",
                "Ld": "7",
                "OC": "2",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


def _make_unit(
    name: str,
    datasheet_id: str,
    *,
    faction_name: str,
    keywords: list[str] | None = None,
    faction_keywords: list[str] | None = None,
    attached_to: list[str] | None = None,
    toughness: str = "5",
) -> Unit:
    datasheet = _MockDatasheet(
        name,
        datasheet_id=datasheet_id,
        faction_name=faction_name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        attached_to=attached_to,
        toughness=toughness,
    )
    return Unit(datasheet)


def _deploy_unit(unit: Unit, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(x, y, 0.0, 0.0)
    unit.deployed = True


def _make_game(detachment: str = "Virulent Vectorium") -> tuple[Game, Player, Player]:
    battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield)
    dg_army = Army.with_detachment("Death Guard", detachment)
    dg_army.faction_id = "DG"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    dg_player = Player("DG", control=PlayerControl.LOCAL, army=dg_army)
    enemy_player = Player("EN", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(dg_player)
    game.add_player(enemy_player)
    return game, dg_player, enemy_player


def _add_objective(game: Game, x: float, y: float) -> ObjectivePoint:
    point = ObjectivePoint(x=x, y=y, z=0.0, control_radius=3.0)
    objective = Objective(
        name="Test Objective",
        category=ObjectiveCategory.PRIMARY,
        points=0,
        description="",
        conditions=lambda _g: False,
        location=point,
    )
    game.map.add_objective(objective)
    return point


class _MeleeWargear:
    name = "Test Blade"

    @staticmethod
    def is_melee() -> bool:
        return True

    @staticmethod
    def is_ranged() -> bool:
        return False


def _melee_profile(
    *,
    strength: int = 4,
    attacks: int = 2,
    skill: int = 3,
    ap: int = -1,
    damage: int = 1,
    description: str = "",
) -> WargearProfile:
    return WargearProfile(
        "Test Blade",
        {
            "range": "Melee",
            "A": str(attacks),
            "BS_WS": str(skill),
            "S": str(strength),
            "AP": str(ap),
            "D": str(damage),
            "description": description,
        },
        parent_wargear=_MeleeWargear(),
    )


def _apply_enhancement(army: Army, unit: Unit, enhancement_name: str) -> None:
    enhancement = _WAHA.get_enhancement_by_name(enhancement_name)
    assert enhancement is not None, enhancement_name
    army.add_enhancement(enhancement, unit)


def test_daemon_weapon_of_nurgle_crits_on_five_plus():
    game, dg_player, enemy_player = _make_game()
    bearer = _make_unit(
        "Bearer",
        "dg-bearer",
        faction_name="Death Guard",
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["DEATH GUARD"],
    )
    target = _make_unit(
        "Target",
        "enemy-target",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    dg_player.army.add_unit(bearer)
    enemy_player.army.add_unit(target)
    _deploy_unit(bearer, 0.0, 0.0)
    _deploy_unit(target, 10.0, 0.0)
    game.map.units = [bearer, target]

    _apply_enhancement(dg_player.army, bearer, "Daemon Weapon of Nurgle")

    profile = _melee_profile()
    attack_instance: dict = {"damage_characteristic": 1}
    hit_result = profile._hit_target_with_tracking(
        target,
        bearer.models[0],
        attack_instance,
        roll_value=5,
        allow_rerolls=False,
        log_roll=False,
    )

    assert hit_result["crit_threshold"] == 5
    assert attack_instance.get("crit_hit") is True


def test_furnace_of_plagues_boosts_melee_and_grants_devastating_wounds():
    game, dg_player, enemy_player = _make_game()
    bearer = _make_unit(
        "Bearer",
        "dg-furnace-bearer",
        faction_name="Death Guard",
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["DEATH GUARD"],
    )
    # Toughness 5 means S4 would normally wound on 5+; S5 improves it to 4+.
    target = _make_unit(
        "Target",
        "enemy-furnace-target",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        toughness="5",
    )
    dg_player.army.add_unit(bearer)
    enemy_player.army.add_unit(target)
    _deploy_unit(bearer, 0.0, 0.0)
    _deploy_unit(target, 10.0, 0.0)
    game.map.units = [bearer, target]

    _apply_enhancement(dg_player.army, bearer, "Furnace of Plagues")

    profile = _melee_profile(strength=4)
    attack_instance: dict = {"damage_characteristic": 1}
    profile._hit_target_with_tracking(
        target,
        bearer.models[0],
        attack_instance,
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert attack_instance.get("bonus_devastating_wounds") is True

    wound_result = profile._wound_target_with_tracking(
        target,
        bearer.models[0],
        attack_instance,
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert wound_result["wound"] is True


def test_arch_contaminator_rerolls_wounds_on_controlled_objective(monkeypatch):
    game, dg_player, enemy_player = _make_game()
    bearer = _make_unit(
        "Bearer",
        "dg-arch-bearer",
        faction_name="Death Guard",
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["DEATH GUARD"],
    )
    target = _make_unit(
        "Target",
        "enemy-arch-target",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    dg_player.army.add_unit(bearer)
    enemy_player.army.add_unit(target)
    point = _add_objective(game, 0.0, 0.0)
    _deploy_unit(bearer, 0.0, 0.0)
    _deploy_unit(target, 20.0, 0.0)
    game.map.units = [bearer, target]
    point.update_control(game)

    _apply_enhancement(dg_player.army, bearer, "Arch Contaminator")

    monkeypatch.setattr("warhammer40k_ai.units.wargear.get_roll", lambda _expr: 5)

    profile = _melee_profile(strength=4)
    attack_instance: dict = {}
    wound_result = profile._wound_target_with_tracking(
        target,
        bearer.models[0],
        attack_instance,
        roll_value=2,
        allow_rerolls=True,
        log_roll=False,
    )

    assert wound_result.get("reroll") == 5
    assert wound_result["wound"] is True
    assert any(
        "Arch Contaminator" in reason
        for reason in wound_result.get("reroll_full_reasons", [])
    )


def test_arch_contaminator_applies_to_attached_unit(monkeypatch):
    game, dg_player, enemy_player = _make_game()
    bodyguard = _make_unit(
        "Bodyguard",
        "dg-bodyguard",
        faction_name="Death Guard",
        keywords=["INFANTRY"],
        faction_keywords=["DEATH GUARD"],
    )
    leader = _make_unit(
        "Leader",
        "dg-leader",
        faction_name="Death Guard",
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["DEATH GUARD"],
    )
    target = _make_unit(
        "Target",
        "enemy-attached-target",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    dg_player.army.add_unit(bodyguard)
    dg_player.army.add_unit(leader)
    enemy_player.army.add_unit(target)
    point = _add_objective(game, 0.0, 0.0)
    _deploy_unit(bodyguard, 0.0, 0.0)
    _deploy_unit(leader, 0.0, 0.0)
    _deploy_unit(target, 20.0, 0.0)
    game.map.units = [bodyguard, leader, target]
    point.update_control(game)

    _apply_enhancement(dg_player.army, leader, "Arch Contaminator")

    # Manual attachment keeps the attached-unit root logic deterministic in tests.
    leader.can_be_attached_to = [bodyguard.get_datasheet_id()]
    leader.attached_to = bodyguard
    bodyguard.attached_leaders = [leader]

    monkeypatch.setattr("warhammer40k_ai.units.wargear.get_roll", lambda _expr: 5)

    profile = _melee_profile(strength=4)
    attack_instance: dict = {}
    wound_result = profile._wound_target_with_tracking(
        target,
        bodyguard.models[0],
        attack_instance,
        roll_value=2,
        allow_rerolls=True,
        log_roll=False,
    )

    assert wound_result.get("reroll") == 5
    assert wound_result["wound"] is True


def test_revolting_regeneration_adds_fnp_five_plus():
    game, dg_player, enemy_player = _make_game()
    bearer = _make_unit(
        "Bearer",
        "dg-regeneration-bearer",
        faction_name="Death Guard",
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["DEATH GUARD"],
    )
    target = _make_unit(
        "Target",
        "enemy-regeneration-target",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    dg_player.army.add_unit(bearer)
    enemy_player.army.add_unit(target)
    _deploy_unit(bearer, 0.0, 0.0)
    _deploy_unit(target, 10.0, 0.0)
    game.map.units = [bearer, target]

    _apply_enhancement(dg_player.army, bearer, "Revolting Regeneration")

    fnp_values = [val for val, _cond in bearer.has_feel_no_pain()]
    assert 5 in fnp_values
