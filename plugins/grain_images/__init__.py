import sparrow
from sparrow.import_helpers import BaseImporter, SparrowImportError
from os import environ
from pathlib import Path
from rich import print
from sqlalchemy.exc import MultipleResultsFound

from .trim_image import create_thumbnail
from .thumbnail_api import get_thumbnail, ThumbnailAPIPlugin

# from .trim_image import create_thumbnail

from sparrow.settings import DATA_DIR, CACHE_DIR


class ImageImporter(BaseImporter):
    file_type = "Grain image"
    data_dir = Path(DATA_DIR)
    thumbnail_cache_dir = Path(CACHE_DIR)/".grain-thumbnails"
    recreate_thumbnails = False

    def run(self, redo=False, recreate_thumbnails=False):
        file_list = (self.data_dir/"PickingImages").glob("**/*.tif")
        # Get rid of copied files
        filtered_list = (f for f in file_list if not f.stem.endswith("_copy"))
        self.recreate_thumbnails = recreate_thumbnails
        self.iterfiles(filtered_list, fix_errors=True, redo=redo)

        # Deal with thumbnails
        self.thumbnail_cache_dir.mkdir(exist_ok=True)
        self.create_thumbnails_bulk(overwrite=recreate_thumbnails)

    def create_thumbnails_bulk(self, overwrite=False):
        """
        Create thumbnails for all images
        """
        db = sparrow.get_database()
        q = db.session.query(db.model.data_file).filter_by(type_id="Grain image")
        for data_file in q:
            self.create_thumbnail(data_file, overwrite=self.recreate_thumbnails)

    def create_thumbnail(self, data_file, overwrite=False):
            infile = self.data_dir / data_file.file_path
            outfile = self.thumbnail_cache_dir / (data_file.file_hash + ".jpg")
            if outfile.exists() and not overwrite:
                return
            print(f"Creating thumbnail for [cyan]{data_file.basename}[/cyan]")
            try:
                create_thumbnail(str(infile), str(outfile))
                print(f"Created thumbnail [cyan]{outfile}[/cyan]")

            except Exception as e:
                print(f"Error creating thumbnail for [cyan]{data_file.basename}[/cyan]")
                print(e)


    def import_datafile(self, fn, rec, **kwargs):
        """
        Import an original data file
        """
        sample_name = fn.stem
        db = sparrow.get_database()
        Sample = db.model.sample

        # The last part of the filename seems like an image index
        if sample_name[-1] in "abcdef":
            sample_name = sample_name[:-1]


        # Get or create a sample using SQLAlchemy methods
        sample = None
        while sample_name is not None:
            print(f"Looking for sample [cyan]{sample_name}[/cyan]")
            try:
                sample = (
                    db.session.query(Sample)
                    .filter(Sample.name.ilike(f"{sample_name}%"))
                    .one_or_none()
                )
            except MultipleResultsFound:
                # We can't link this to a unique sample, apparently!
                print(f"Multiple samples found for [cyan]{sample_name}[/cyan], cannot link")
                break

            if sample is not None:
                break

            # If we can't find a sample, try removing the last part of the name (after the last underscore)
            new_sample_name = sample_name.rsplit("_", 1)[0]
            if new_sample_name == sample_name:
                break
            sample_name = new_sample_name
            # If the remaining name is too short we're in dangerous territory
            # Grain files should also have at least one underscore
            if len(sample_name) < 4:
                break

        self.create_thumbnail(rec, overwrite=self.recreate_thumbnails)

        # For now, we do nothing if we cannot directly match
        # a thumbnail to a sample.
        if sample is None:
            return
        else:
            print(f"Found sample [cyan]{sample.name}[/cyan]")

        
        #if sample is None:
        #    sample = Sample(name=sample_name)
        #    db.session.add(sample)

        # Provide this sample to be linked to the data file
        yield sample


