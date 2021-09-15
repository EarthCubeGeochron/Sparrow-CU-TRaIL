"""
An API route that allows grain image thumbnails to be resolved
and served from the SPARROW_DATA_DIR
"""
from starlette.responses import Response
import sparrow
from sparrow.api import SparrowAPIError
from pathlib import Path


def FileResponse(file: Path):
    return Response(
        headers={
            "Content-Type": "",
            "Content-Disposition": f'attachment; filename="{file.basename}"',
            # X-Accel-Redirect is an NGINX feature, if we're running sparrow outside of
            # the usual docker context it will not work...
            # Right now, the SPARROW_DATA_DIR folder is always mounted to /data in Docker...
            "X-Accel-Redirect": str(file),
        }
    )


def get_thumbnail(request):
    """Get a single data file"""
    uuid = request.path_params["uuid"]
    db = sparrow.get_database()
    data_dir = Path(sparrow.settings.DATA_DIR)

    thumbnail = data_dir / ".grain-thumbnails" / uuid + ".jpg"
    if thumbnail.exists():
        # Success!
        return FileResponse(thumbnail)

    # Handle various kinds of errors...
    # Check that data file actually exists
    DataFile = db.model.data_file
    df = db.session.query(DataFile).get(uuid)
    if df is None:
        raise SparrowAPIError("Data file with UUID {uuid} not found", status_code=404)
    raise SparrowAPIError(
        "Thumbnail not available for data file {uuid}", status_code=404
    )
