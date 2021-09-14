FROM sparrowdata/backend-base:2.0 AS downloader

# We download the packages in a separate stage so it can be cached.
RUN mkdir /package-cache
RUN pip download -d /package-cache opencv-python-headless

FROM sparrowdata/backend

COPY --from=downloader /package-cache/ /package-cache/

# We need the OpenCV computer-vision library to do image manipulation
RUN pip install --no-index --find-links /package-cache opencv-python-headless
RUN rm -rf /package-cache

# Inherit command from upstream dockerfile
CMD ["/bin/run"]