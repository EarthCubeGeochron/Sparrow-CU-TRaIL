# Add plugins to sys.path
from pathlib import Path

from plugins.import_data.pickingImport import read_picking_data, get_picking_specs

def test_data_picking():
    fn = Path(__file__).parent.parent/"test_data"/"PickingData"/"Test_Picking_Sheet.xlsx"
    read_picking_data(fn, get_picking_specs(), lambda d: 1)

