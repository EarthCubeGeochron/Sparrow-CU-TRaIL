# Configures environment for TRaIL lab

export SPARROW_BACKUP_DIR="$SPARROW_CONFIG_DIR/backups"
export SPARROW_LAB_NAME="TRaIL"
export SPARROW_VERSION=">=2.0.0.beta14"

#export SPARROW_SITE_CONTENT="$PROJECT_DIR/site-content"

# Keep volumes for this project separate from those for different labs
export COMPOSE_PROJECT_NAME="${SPARROW_LAB_NAME}"
export SPARROW_DATA_DIR="$SPARROW_CONFIG_DIR/TRaIL-Data"

# Frontend content overrides
export SPARROW_SITE_CONTENT="$SPARROW_CONFIG_DIR/site-content"

# Plugins
export SPARROW_PLUGIN_DIR="$SPARROW_CONFIG_DIR/plugins"

# Load secret values (not tracked in version control)
overrides="${SPARROW_CONFIG_DIR}/sparrow-secrets.sh"
[ -f "$overrides" ] && source "$overrides"

# We need to build our own base image for OpenCV support.
# The backend image is built in the Sparrow-Prestart script.
# when `sparrow up` is called.
export SPARROW_BACKEND_IMAGE="sparrow_trail_backend:latest"

# Had to change port nnumber because windows update on
# 10/15/21 apparently reserved port 54321. Details on finding
# reserved ports here:
# https://stackoverflow.com/questions/15619921/an-attempt-was-made-to-access-a-socket-in-a-way-forbidden-by-its-access-permissi
export SPARROW_DB_PORT="5432"