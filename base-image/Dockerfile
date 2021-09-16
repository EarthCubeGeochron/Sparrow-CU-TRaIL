FROM python:3.9 AS downloader

# We download the packages in a separate stage so it can be cached.
RUN mkdir /package-cache
RUN pip3 download -d /package-cache opencv-python-headless

FROM sparrowdata/backend

COPY --from=downloader /package-cache /package-cache
COPY --from=downloader /var/cache/apt/archives /var/cache/apt/archives


RUN apt-get update && apt-get install -y libgl1
# We need the OpenCV computer-vision library to do image manipulation
RUN pip3 install --no-index --find-links /package-cache opencv-python-headless
RUN rm -rf /package-cache

# Test that the library is installed
RUN python3 -c "import cv2"

# Inherit command from upstream dockerfile
CMD ["/bin/run"]