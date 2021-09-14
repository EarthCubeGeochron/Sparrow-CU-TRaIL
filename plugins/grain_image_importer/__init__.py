import sparrow
from sparrow.import_helpers import BaseImporter, SparrowImportError
from os import environ
from pathlib import Path
from rich import print


class ImageImporter(BaseImporter):
    def run(self):
        data_dir = environ.get("SPARROW_DATA_DIR", None)
        file_list = Path(str(data_dir)).glob("**/*.tif")
        # Get rid of copied files
        filtered_list = (f for f in file_list if not f.stem.endswith("_copy"))
        self.iterfiles(filtered_list, fix_errors=True)

    def import_datafile(self, fn, rec, **kwargs):
        """
        Import an original data file
        """
        sample_name = fn.stem
        # The last part of the filename seems like an image index
        if name[-1] in "abcdef":
            sample_name = sample_name[:-1]
        print(name)
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

        raise SparrowImportError("Refusing to import")


@sparrow.task()
def import_grain_images():
    """
    Import grain images, link them to samples, and create thumbnails.
    """
    app = sparrow.get_app()
    importer = ImageImporter(app)
    importer.run()
