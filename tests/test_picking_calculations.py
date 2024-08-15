# Add plugins to sys.path
from pathlib import Path
import sys
from sparrow.core import get_app

plugins = Path(__file__).parent.parent/"plugins"

sys.path.append(str(plugins))

# Check that we can import the plugin
from import_data.pickingImport import TRaILpicking


def test_data_picking():
    app = get_app()
    data_dir = Path("/data")
    TRaILpicking(app, data_dir)
    assert True

