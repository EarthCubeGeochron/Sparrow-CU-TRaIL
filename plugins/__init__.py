# from .import_data import DataReductionImportPlugin
# from .grain_images import import_grain_images, ThumbnailAPIPlugin
from .import_data.archiveImporter import TRaILarchive
from .import_data.pickingImport import TRaILpicking
from .import_data.heliumImport import TRaILhelium
from .import_data.icpmsImport import TRaILicpms
from .export_data.sampleIDexport import LabIDexporter
from .export_data.createPublicationTable import PublicationTableExporter
from .manipulate_data.dataReduction import TRaILdatecalc
from .manipulate_data.addSampleNote import AddSampleNote
from .manipulate_data.addLocation import AddLocation
from .manipulate_data.removeEmbargo import RemoveEmbargo
from .grain_images import ImageImporter, ThumbnailAPIPlugin

from sparrow import get_app
from click import secho
from sparrow.task_manager import task
from pathlib import Path

@task(name='say-hello')
def say_hello():
    secho('Hello World, I am a Sparrow Task', fg='green')
    
@task(name='import-archive')
def import_full_data():
    app = get_app()
    data_dir = Path('/data')
    TRaILarchive(app, data_dir)
    
@task(name='import-picking-info')
def import_picking():
    app = get_app()
    data_dir = Path('/data')
    TRaILpicking(app, data_dir)
    
@task(name='import-helium')
def import_helium():
    app = get_app()
    data_dir = Path('/data')
    TRaILhelium(app, data_dir)
                
@task(name='import-icpms')
def import_icpms():
    app = get_app()
    data_dir = Path('/data')
    TRaILicpms(app, data_dir)
        
@task(name='calculate-dates')
def get_date():
    app = get_app()
    data_dir = Path('/data')
    TRaILdatecalc(app, data_dir)

@task(name='add-locations')
def add_locations():
    app = get_app()
    data_dir = Path('/data')
    AddLocation(app, data_dir)

@task(name='remove-embargo')
def remove_embargo():
    app = get_app()
    data_dir = Path('/data')
    RemoveEmbargo(app, data_dir)

@task(name='add-note')
def add_note(id_: str = None, note: str = None):
    app = get_app()
    data_dir = Path('/data')
    AddSampleNote(app, data_dir, id_, note)
    
@task(name='export-ID')
def export_ID():
    app = get_app()
    data_dir = Path('/data')
    LabIDexporter(app, data_dir)

@task(name='export-table')
def export_table(filename: str = None):
    app = get_app()
    data_dir = Path('/data')
    PublicationTableExporter(app, data_dir, filename)

@task(name='import-grain-images')
def import_grain_images(redo: bool = False, recreate_thumbnails: bool = False):
    """
    Import grain images, link them to samples, and create thumbnails.
    """
    app = get_app()
    importer = ImageImporter(app)
    importer.run(redo=redo, recreate_thumbnails=recreate_thumbnails)
