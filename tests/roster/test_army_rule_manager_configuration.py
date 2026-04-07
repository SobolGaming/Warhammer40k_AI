from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.rules.deathstrike import DeathstrikeManager


def test_genestealer_cults_configures_deathstrike_manager() -> None:
    army = Army.with_detachment("Genestealer Cults", detachment_type="Brood Brother Auxilia")
    army.faction_id = "GC"
    army.configure_rule_managers(force=True)

    assert isinstance(army.deathstrike, DeathstrikeManager)
