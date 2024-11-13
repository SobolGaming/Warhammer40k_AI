import logging
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper
from warhammer40k_ai.classes.unit import Unit

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s")
logger = logging.getLogger(__name__)

def test_load_all_datasheet_units():
    waha_helper = WahaHelper()
    for unit_name, unit_id in waha_helper.get_all_datasheet_names():
        print(f"-----  {unit_name} -----")
        u = Unit(waha_helper.get_datasheet(unit_name, unit_id))
        for model in u.models:
            print(f"{model.name}: {model.wargear}")
        ranged_threat_level, melee_threat_level = u.get_threat_level()
        try:
            cost = u.models_cost[len(u.models)]
        except KeyError:
            try:
                cost = u.models_cost[len(u.models) - 1]
                cost += u.models_cost["extra"]
            except KeyError:
                print(f"No cost found for {unit_name}")
                cost = 1000
        print(f"Ranged Threat level: {ranged_threat_level}, Melee Threat level: {melee_threat_level}, Ranged Threat per Cost: {ranged_threat_level/cost}, Melee Threat per Cost: {melee_threat_level/cost}")
        print(f"------------------------------------------------------------------\n")

if __name__ == "__main__":
    test_load_all_datasheet_units()
