# from .import_data import DataReductionImportPlugin
# from .grain_images import import_grain_images, ThumbnailAPIPlugin
from .import_data.ArchiveImporter import TRaILImporter
from .import_data.pickingImport import TRaILpicking
from .import_data.heliumImport import TRaILhelium
from .import_data.icpmsImport import TRaILicpms
from .export_data.sampleID_export import LabID_exporter
from .export_data.create_publication_table import PublicationTable_exporter
from .manipulate_data.dataReduction import TRaILdatecalc
from .manipulate_data.AddSampleNote import AddSampleNote

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
    TRaILImporter(app, data_dir)
    
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
    
@task(name='add-note')
def add_note(id_: str = None, note: str = None):
    app = get_app()
    data_dir = Path('/data')
    AddSampleNote(app, data_dir, id_, note)
    
@task(name='export-ID')
def export_ID():
    app = get_app()
    data_dir = Path('/data')
    LabID_exporter(app, data_dir)

@task(name='export-table')
def export_table(filename: str = None):
    app = get_app()
    data_dir = Path('/data')
    PublicationTable_exporter(app, data_dir, filename)