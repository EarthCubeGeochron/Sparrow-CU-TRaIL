import sparrow
from sparrow.import_helpers import BaseImporter
from os import environ
from pathlib import Path


class ImageImporter(BaseImporter):
    def run(self):
        data_dir = environ.get("SPARROW_DATA_DIR", None)
        file_list = Path(str(data_dir)).glob("**/*.tif")
        self.iterfiles(file_list)

    def import_datafile(self, fn, rec, **kwargs):
        """
        Import an original data file
        """
        print(fn)


@sparrow.task()
def import_grain_images():
    """
    Import grain images, link them to samples, and create thumbnails.
    """
    app = sparrow.get_app()
    importer = ImageImporter(app)
    importer.run()
