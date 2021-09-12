
# Build custom docker base images before install
# The base image depends on the sparrowdata/backend image
# so we have to build this image first
all:
	sparrow build backend
	docker build -t sparrow_trail_backend:latest base-image