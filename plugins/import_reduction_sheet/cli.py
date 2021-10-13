from click import command, option
from sparrow.import_helpers import get_data_directory
from sparrow import get_app
from .importer import TRaILImporter
from .customImport import TRaILpartial
from .pickingImport import TRaILpicking
from IPython import embed
from pathlib import Path

from logging import getLogger, WARNING

logger = getLogger(__name__)


@command(name="import-data")
@option("--redo", "-r", is_flag=True, default=False)
@option("--stop-on-error", is_flag=True, default=False)
@option("--verbose", "-v", is_flag=True, default=False)
@option("--show-data", "-S", is_flag=True, default=False)
def import_data(redo=False, stop_on_error=False, verbose=False, show_data=False):
    """Import data from TRaIL's data reduction format"""
    app = get_app()
    proceed = input('import Full, Partial, or Picking?')
    data_dir = Path("/data")
    if proceed == 'Full':
        #data_dir = get_data_directory()
        # The unit of work for a session is a row in the data-reduction sheet...
        TRaILImporter(app, data_dir, redo=redo)
    if proceed == 'Partial':
        TRaILpartial(app, data_dir, redo=redo)
    if proceed == 'Picking':
        TRaILpicking(app, data_dir, redo=redo)