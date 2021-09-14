# Configures environment for TRaIL lab

export SPARROW_BACKUP_DIR="$SPARROW_CONFIG_DIR/backups"
export SPARROW_LAB_NAME="TRaIL"
export SPARROW_VERSION=">=2.0.0.beta13"

#export SPARROW_SITE_CONTENT="$PROJECT_DIR/site-content"

# Keep volumes for this project separate from those for different labs
export COMPOSE_PROJECT_NAME="${SPARROW_LAB_NAME}"
export SPARROW_DATA_DIR="$SPARROW_CONFIG_DIR/TRaIL-Data"

# Plugins
export SPARROW_PLUGIN_DIR="$SPARROW_CONFIG_DIR/plugins"

# Load secret values (not tracked in version control)
overrides="${SPARROW_CONFIG_DIR}/sparrow-secrets.sh"
[ -f "$overrides" ] && source "$overrides"

# We need to build our own base image for OpenCV support
# Note, you must build the backend image by running `make` in this repository
# before running `sparrow up`. We are working on making this type
# of substitution simpler.
export SPARROW_BACKEND_IMAGE="sparrow_trail_backend:latest"