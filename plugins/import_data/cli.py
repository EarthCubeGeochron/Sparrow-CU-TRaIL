from click import command, option
from sparrow import get_app
from .ArchiveImporter import TRaILImporter
##from .customImport import TRaILpartial
from .pickingImport import TRaILpicking
from .heliumImport import TRaILhelium
from .icpmsImport import TRaILicpms
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
    proceed = input('import Full, Partial, ICPMS, Helium, or Picking?').casefold()
    data_dir = Path("/data")
    if proceed == 'Full'.casefold():
        #data_dir = get_data_directory()
        # The unit of work for a session is a row in the data-reduction sheet...
        TRaILImporter(app, data_dir, redo=redo)
    if proceed == 'Partial'.casefold():
        TRaILpartial(app, data_dir, redo=redo)
    if proceed == 'Picking'.casefold():
        TRaILpicking(app, data_dir, redo=redo)
    if proceed == 'Helium'.casefold():
        TRaILhelium(app, data_dir, redo=redo)
    if proceed == 'ICPMS'.casefold():
        TRaILicpms(app, data_dir, redo=redo)
