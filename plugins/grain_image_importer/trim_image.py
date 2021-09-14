# -*- coding: utf-8 -*-
"""
Created on Tue Aug 17 13:27:39 2021

@author: Peter
"""


def create_thumbnail(filename, outfile):
    """Create a thumbnail of a grain image that is cropped to the boundaries of the grain."""
    import cv2

    image = cv2.imread(filename)  # TODO change import for Sparrow
    image = cv2.resize(image, (0, 0), fx=0.4, fy=0.4)

    # Some images have scalebars near the edges, so we need to crop these out
    (height, width, nbands) = image.shape
    margin = height // 10
    image = image[margin : height - margin, margin : width - margin]

    # Convert to grayscale and threshold
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # Binary_inv converts all darker regions (i.e. grains) to 1s and others to 0
    # OTSU is a denoising algorithm to smooth the threshold
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]

    # Plot thresholded image
    # cv2.imshow('image', thresh)
    # cv2.waitKey(0)
    # cv2.destroyAllWindows()

    # Find contours from thresholded image
    ROI_number = 0
    cnts = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cnts = cnts[0] if len(cnts) == 2 else cnts[1]

    # Draw contours for illustration
    # for contour in cnts:
    #     cv2.drawContours(image, contour, -1, (0, 255, 0), 3)

    # Get bounding boxes for contours
    boxes = []
    for c in cnts:
        x1, y1, w, h = cv2.boundingRect(c)
        x2, y2 = x1 + w, y1 + h
        aspect = w / h
        area = w * h
        # exclude the scale bar
        if aspect < 8:
            boxes.append([x1, x2, y1, y2, area])
        # draw rectangles to show where bounding boxes are
        # cv2.rectangle(image, (x1, y1), (x2, y2), (36,255,12), 2)

    # find largest bounding box-- assume this is the grain
    grain = [0, 0, 0, 0, 0]
    for b in boxes:
        if b[4] > grain[4]:
            grain = b

    # If there are boxes more than 20% the size of the grain,
    # assume there are multiple grains and create a box around all of them
    mult_grains = []
    for b in boxes:
        if b[4] > grain[4] * 0.2:
            mult_grains.append(b)
    if len(mult_grains) > 1:
        grain = [
            min([b[0] for b in mult_grains]),
            max([b[1] for b in mult_grains]),
            min([b[2] for b in mult_grains]),
            max([b[3] for b in mult_grains]),
        ]

    # Add 20% cushion
    w = grain[1] - grain[0]
    l = grain[1] - grain[0]
    grain[0] = int(grain[0] - 0.2 * w)
    grain[1] = int(grain[1] + 0.2 * w)
    grain[2] = int(grain[2] - 0.2 * l)
    grain[3] = int(grain[3] + 0.2 * l)

    # cv2.rectangle(image, (grain[0], grain[2]), (grain[1], grain[3]), (36,255,12), 2)

    # trim to grain bounding box
    image = image[grain[2] : grain[3], grain[0] : grain[1]]
    # save out as jpeg... Can lower quality to compress for less data if needed (change 100 to ~50)
    # TODO instead of writing to active directory, save to DB
    cv2.imwrite(outfile, image, [int(cv2.IMWRITE_JPEG_QUALITY), 100])
