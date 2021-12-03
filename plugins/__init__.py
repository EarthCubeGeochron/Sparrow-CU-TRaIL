from .import_data import DataReductionImportPlugin
from .grain_images import import_grain_images, ThumbnailAPIPlugin
from .import_data.importer import TRaILImporter
from .import_data.customImport import TRaILpartial
from .import_data.pickingImport import TRaILpicking
from .import_data.heliumImport import TRaILhelium
from .import_data.icpmsImport import TRaILicpms

from sparrow import get_app
from click import secho
from sparrow.task_manager import task
from pathlib import Path

@task(name="say-hello")
def say_hello():
    secho("Hello World, I am a Sparrow Task", fg='green')

@task(name='import-picking-info')
def import_picking():
    app = get_app()
    data_dir = Path("/data")
    TRaILpicking(app, data_dir)
    
@task(name='import-helium')
def import_helium():
    app = get_app()
    data_dir = Path("/data")
    TRaILhelium(app, data_dir)
                
@task(name='import-ICPMS')
def import_icpms():
    app = get_app()
    data_dir = Path("/data")
    TRaILicpms(app, data_dir)
    
@task(name='import-archive')
def import_full_data():
    app = get_app()
    data_dir = Path("/data")
    TRaILImporter(app, data_dir)