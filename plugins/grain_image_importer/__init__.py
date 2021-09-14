import sparrow
from sparrow.import_helpers import BaseImporter, SparrowImportError
from os import environ
from pathlib import Path
from rich import print

from .trim_image import create_thumbnail

# from .trim_image import create_thumbnail

from sparrow.settings import DATA_DIR, CACHE_DIR


class ImageImporter(BaseImporter):
    file_type = "Grain image"
    data_dir = Path(DATA_DIR)

    def run(self, redo=False, recreate_thumbnails=False):
        file_list = self.data_dir.glob("**/*.tif")
        # Get rid of copied files
        filtered_list = (f for f in file_list if not f.stem.endswith("_copy"))
        self.iterfiles(filtered_list, fix_errors=True, redo=redo)

        # Deal with thumbnails
        self.thumbnail_dir = self.data_dir / ".grain-thumbnails"
        self.thumbnail_dir.mkdir(exist_ok=True)
        self.create_thumbnails(overwrite=recreate_thumbnails)

    def create_thumbnails(self, overwrite=False):
        """
        Create thumbnails for all images
        """
        db = sparrow.get_database()
        q = db.session.query(db.model.data_file).filter_by(type_id="Grain image")
        for data_file in q:
            infile = self.data_dir / data_file.file_path
            outfile = self.thumbnail_dir / (data_file.file_hash + ".jpg")
            print(f"Creating thumbnail for [cyan]{data_file.basename}[/cyan]")
            if outfile.exists() and not overwrite:
                continue
            create_thumbnail(str(infile), str(outfile))

    def import_datafile(self, fn, rec, **kwargs):
        """
        Import an original data file
        """
        sample_name = fn.stem
        # The last part of the filename seems like an image index
        if sample_name[-1] in "abcdef":
            sample_name = sample_name[:-1]
        db = sparrow.get_database()
        Sample = db.model.sample

        # Get or create a sample using SQLAlchemy methods
        sample = (
            db.session.query(Sample)
            .filter(Sample.name.ilike(f"{sample_name}%"))
            .one_or_none()
        )

        if sample is None:
            sample = Sample(name=sample_name)
            db.session.add(sample)

        # Provide this sample to be linked to the data file
        yield sample


@sparrow.task()
def import_grain_images(redo: bool = False, recreate_thumbnails: bool = False):
    """
    Import grain images, link them to samples, and create thumbnails.
    """
    app = sparrow.get_app()
    importer = ImageImporter(app)
    importer.run(redo=redo, recreate_thumbnails=recreate_thumbnails)
