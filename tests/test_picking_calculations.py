# Add plugins to sys.path
from pathlib import Path
import sys

plugins = Path(__file__).parent.parent/"plugins"

sys.path.append(str(plugins))

# Check that we can import the plugin
from import_data.pickingImport import read_picking_data


def test_data_picking():
    read_picking_data()

