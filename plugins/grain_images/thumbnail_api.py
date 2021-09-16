"""
An API route that allows grain image thumbnails to be resolved
and served from the SPARROW_DATA_DIR
"""
from starlette.responses import FileResponse, JSONResponse
import sparrow
from sparrow.api import SparrowAPIError
from sparrow import SparrowPlugin
from pathlib import Path


def get_thumbnail(request):
    """Get a single data file"""
    uuid = request.path_params["uuid"]
    db = sparrow.get_database()
    data_dir = Path(sparrow.settings.DATA_DIR)

    thumbnail = data_dir / ".grain-thumbnails" / (uuid + ".jpg")
    if thumbnail.exists():
        # Success!
        return FileResponse(thumbnail)

    # Handle various kinds of errors...
    # Check that data file actually exists
    if data_file is None:
        data_file = db.session.query(db.model.data_file).get(uuid)
    if data_file is None:
        raise SparrowAPIError("Data file with UUID {uuid} not found", status_code=404)
    raise SparrowAPIError(
        "Thumbnail not available for data file {uuid}", status_code=404
    )
    return thumbnail_for_datafile(uuid)


def find_grain_image(request):
    """Get a single data file"""
    # We could probably do this by adapting the basic data_file route
    # but this is potentially simpler while we work on that API
    sample_id = request.query_params["sample_id"]
    db = sparrow.get_database()

    DataFile = db.model.data_file
    DataFileLink = db.model.data_file_link
    q = (
        db.session.query(DataFile)
        .join(DataFile.data_file_link_collection)
        .filter(DataFile.type_id == "Grain image")
        .filter(DataFileLink.sample_id == int(sample_id))
    )

    data_file = q.first()
    if data_file is None:
        return JSONResponse([])

    return JSONResponse([{"uuid": data_file.file_hash}])


class ThumbnailAPIPlugin(SparrowPlugin):
    name = "thumbnail-api"

    def on_api_initialized_v2(self, api):
        api.add_route(
            "/grain-image/{uuid}.jpg",
            get_thumbnail,
            name="thumbnail_api",
            help="Get the thumbnail for a grain",
        )

        api.add_route(
            "/grain-image",
            find_grain_image,
            name="thumbnail_api",
            help="Get the thumbnail for a sample",
        )
