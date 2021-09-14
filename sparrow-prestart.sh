# Build the backend image before we run sparrow up
# We can do this in the config file becaues it's actually a shell script...
# We should do this after loading all relevant environment variables
# (this only works in Sparrow >= 2.0.0.beta14, and we might find a better way
#  to do it in the future)
echo "Building custom backend image..." >&2
if [ $SPARROW_ENV != "production" ]; then
  sparrow build backend
fi
docker build -t $SPARROW_BACKEND_IMAGE base-image