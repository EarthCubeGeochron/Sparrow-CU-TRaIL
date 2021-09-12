FROM sparrowdata/backend:latest

# We need the OpenCV computer-vision library to do image manipulation
RUN pip install opencv-python

# Inherit command from upstream dockerfile
CMD ["/bin/run"]