# Build the backend image before we run sparrow up
# (this only works in Sparrow >= 2.0.0.beta14, and we might find a better way
#  to do it in the future)
echo "Restarting Google Drive mount." >&2
bash restart-gdrive.sh
if [ $? -ne 0 ]; then
  echo "Google Drive mount was not created properly!" >&2
  echo "If the system was recently updated, try setting the 'user_allow_other' option in /etc/fuse.conf" >&2
fi
echo "" >&2

if [ -z SPARROW_BACKEND_IMAGE ]; then
	echo "Custom backend image not provided" >&2
else
	echo "Building custom backend image..." >&2
	sparrow build backend
	docker build -t $SPARROW_BACKEND_IMAGE base-image
fi
