import logging
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper
from warhammer40k_ai.classes.unit import Unit

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s")
logger = logging.getLogger(__name__)

def test_load_all_datasheet_units():
    waha_helper = WahaHelper()
    for unit_name, unit_id in waha_helper.get_all_datasheet_names():
        print(f"-----  {unit_name} -----")
        Unit(waha_helper.get_datasheet(unit_name, unit_id))
        print(f"------------------------------------------------------------------\n")

if __name__ == "__main__":
    test_load_all_datasheet_units()
