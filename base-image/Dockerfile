#FROM python:3.9 AS downloader

# We download the packages in a separate stage so it can be cached.
#RUN mkdir -p /package-cache
#RUN pip3 download -d /package-cache opencv-python-headless

FROM ghcr.io/earthcubegeochron/sparrow/backend

#COPY --from=downloader /package-cache /package-cache
#COPY --from=downloader /var/cache/apt/archives /var/cache/apt/archives


RUN apt-get update && apt-get install -y libgl1
# We need the OpenCV computer-vision library to do image manipulation
#RUN pip3 install --no-index --find-links /package-cache opencv-python-headless
RUN pip3 install opencv-python-headless
#RUN rm -rf /package-cache

# Install additional packages needed for TRaIL-Sparrow
RUN pip3 install uncertainties
RUN pip3 install hecalc

# Test that the libraries are installed
RUN python3 -c "import cv2"
RUN python3 -c "import hecalc"

# Inherit command from upstream dockerfile
CMD ["/bin/run"]