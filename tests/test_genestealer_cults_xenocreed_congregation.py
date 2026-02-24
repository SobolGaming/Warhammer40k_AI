from __future__ import annotations

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str,
        keywords: list[str] | None = None,
        faction_keywords: list[str] | None = None,
        points: int = 100,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": int(points)}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "4",
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
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str,
    keywords: list[str] | None = None,
    faction_keywords: list[str] | None = None,
    points: int = 100,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            points=points,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _build_game() -> tuple[Game, Army, Army, Player, Player]:
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    gsc_army = Army("Genestealer Cults", "Xenocreed Congregation", points_limit=2000)
    gsc_army.faction_id = "GC"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    p1 = Player("GSC", control=PlayerControl.REMOTE, army=gsc_army)
    p2 = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)
    return game, gsc_army, enemy_army, p1, p2


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    leader.can_be_attached_to = ["BODYGUARD"]
    leader.attached_to = bodyguard
    leaders = list(getattr(bodyguard, "attached_leaders", []) or [])
    leaders.append(leader)
    bodyguard.attached_leaders = leaders


def _has_fnp_value(entries: list[tuple[int, str | None]], value: int) -> bool:
    for dice_value, _cond in list(entries or []):
        if int(dice_value or 0) == int(value):
            return True
    return False


def test_unquestioning_fanaticism_grants_reroll_advance_and_charge_to_eligible_led_units():
    game, gsc_army, _enemy_army, _gsc_player, _enemy_player = _build_game()

    neophytes = _make_unit(
        "Neophyte Hybrids",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    clamavus = _make_unit(
        "Clamavus",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    gsc_army.add_unit(neophytes)
    gsc_army.add_unit(clamavus)
    _attach_leader(neophytes, clamavus)

    purestrains = _make_unit(
        "Purestrain Genestealers",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    second_clamavus = _make_unit(
        "Clamavus",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    gsc_army.add_unit(purestrains)
    gsc_army.add_unit(second_clamavus)
    _attach_leader(purestrains, second_clamavus)

    mgr = gsc_army.genestealer_cults_detachments

    assert bool(mgr.xenocreed_unquestioning_fanaticism_reroll_advance_applies(neophytes)) is True
    assert bool(mgr.xenocreed_unquestioning_fanaticism_reroll_charge_applies(neophytes)) is True
    assert bool(neophytes.can_reroll_advance_roll()) is True
    assert bool(neophytes.can_reroll_charge_roll(game=game)) is True

    assert bool(mgr.xenocreed_unquestioning_fanaticism_reroll_advance_applies(purestrains)) is False
    assert bool(mgr.xenocreed_unquestioning_fanaticism_reroll_charge_applies(purestrains)) is False


def test_unquestioning_fanaticism_fnp_applies_only_to_magus_primus_or_iconward_leader_models():
    _game, gsc_army, _enemy_army, _gsc_player, _enemy_player = _build_game()

    acolytes = _make_unit(
        "Acolyte Hybrids with Autopistols",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    primus = _make_unit(
        "Primus",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    gsc_army.add_unit(acolytes)
    gsc_army.add_unit(primus)
    _attach_leader(acolytes, primus)

    neophytes = _make_unit(
        "Neophyte Hybrids",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    clamavus = _make_unit(
        "Clamavus",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    gsc_army.add_unit(neophytes)
    gsc_army.add_unit(clamavus)
    _attach_leader(neophytes, clamavus)

    primus_fnp = list(primus.has_feel_no_pain(target_model=primus.models[0]) or [])
    acolyte_fnp = list(acolytes.has_feel_no_pain(target_model=acolytes.models[0]) or [])
    clamavus_fnp = list(clamavus.has_feel_no_pain(target_model=clamavus.models[0]) or [])

    assert _has_fnp_value(primus_fnp, 3)
    assert not _has_fnp_value(acolyte_fnp, 3)
    assert not _has_fnp_value(clamavus_fnp, 3)
