import sparrow
from sparrow.import_helpers import BaseImporter, SparrowImportError
from os import environ
from pathlib import Path
from rich import print

# from .trim_image import create_thumbnail


class ImageImporter(BaseImporter):
    file_type = "Grain image"

    def run(self, redo=False):
        data_dir = environ.get("SPARROW_DATA_DIR", None)
        file_list = Path(str(data_dir)).glob("**/*.tif")
        # Get rid of copied files
        filtered_list = (f for f in file_list if not f.stem.endswith("_copy"))
        self.iterfiles(filtered_list, fix_errors=True, redo=redo)

    def save_thumbnail(self, fn):
        """
        Save a thumbnail of the image
        """
        pass

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

        # self.save_thumbnail(fn)


@sparrow.task()
def import_grain_images(redo: bool = False):
    """
    Import grain images, link them to samples, and create thumbnails.
    """
    app = sparrow.get_app()
    importer = ImageImporter(app)
    importer.run(redo=redo)
