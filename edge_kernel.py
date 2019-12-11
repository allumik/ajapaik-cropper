import cv2
import numpy as np
import pandas as pd
import scipy.stats as stat
import scipy.signal as signal
import scipy.ndimage as ndimage
import matplotlib.pyplot as plt

def edge_dec(orig, mod):
    '''See modified picture and original side-by-side'''
    plt.subplot(121),plt.imshow(orig, cmap = "gray")
    plt.title('Original Image'), plt.xticks([]), plt.yticks([])

    plt.subplot(122),plt.imshow(mod, cmap = "gray")
    plt.title('Modded Image'), plt.xticks([]), plt.yticks([])

def show_stats(mod, stats1, stats2):
    '''Display the axes extracted from the picture on the picture'''
    plt.subplot(121), plt.imshow(mod, cmap = "gray")
    plt.subplot(121), plt.plot(stats1)

    plt.subplot(122), plt.imshow(np.rot90(mod), cmap = "gray")
    plt.subplot(122), plt.plot(stats2)

# Hough method, detects lines probabilistically
def apply_hough(mat, thresh = 110, maxgap = 3, minline = 50):
    '''Detect and create mask of lines from the picture.
    Hough method, probabilistic line detection but not accurate enough
    for standalone usage. Mayby add it before rectangle detection for more
    flexible frame detection?'''
    dims = mat.shape
    blank = np.zeros(dims)
    lines = cv2.HoughLinesP(mat,
                            rho = 1,
                            theta = np.pi/180,
                            threshold = thresh,
                            minLineLength = minline,
                            maxLineGap = maxgap)

    for x1,y1,x2,y2 in np.squeeze( lines ):
        cv2.line(blank,(x1,y1),(x2,y2),(254),1)
    return blank

def check_for_rect(mat):
    '''Checker function for controlling the presence of lines
    with z-scores over 3.5 in quarters of images'''
    dims = mat.shape

    ax_vert = stat.zscore(np.sum(mat, axis=1))
    ax_vert_left = ax_vert[:int(dims[0]/3)]
    ax_vert_right = ax_vert[int(dims[0]*2/3):]

    ax_hori = stat.zscore(np.sum(mat, axis=0))
    ax_hori_upper = ax_hori[:int(dims[1]/3)]
    ax_hori_lower = ax_hori[int(dims[1]*2/3):]

    # check for 3.5 (99.5 limit) in the corners and that
    # the area is smaller than quarter of axis length
    return (np.sum( ax_vert_left[ax_vert_left > 3.5] ) / dims[0] > 0 and
       np.sum( ax_vert_right[ax_vert_right > 3.5] ) / dims[0] > 0 and
       np.sum( ax_hori_upper[ax_hori_upper > 3.5] ) / dims[1] > 0 and
       np.sum( ax_hori_lower[ax_hori_lower > 3.5] ) / dims[1] > 0 and
       np.sum( ax_vert[ax_vert > 3.5] ) / dims[0] < 0.25 and
       np.sum( ax_hori[ax_hori > 3.5] ) / dims[1] < 0.25)

def detect_rect(mat, minlineprop):
    '''Detect lines from picture (mat) that are horizontal and rectangular
    and minimum length of defined proprtion (minlineprop) of picture axis
    length'''
    dims = mat.shape

    vertic_struct = cv2.getStructuringElement(cv2.MORPH_RECT,
                                              (1, int(dims[0]*minlineprop)))
    vertic = cv2.erode(mat, vertic_struct)
    vertic = cv2.dilate(vertic, vertic_struct)

    # detect horizontal lines
    horiz_struct = cv2.getStructuringElement(cv2.MORPH_RECT,
                                             (int(dims[1]*minlineprop), 1))
    horiz = cv2.erode(mat, horiz_struct)
    horiz = cv2.dilate(horiz, horiz_struct)
    return vertic+horiz

def detect_rot_rect(mat, minlineprop, rotrange):
    '''Detect lines that are horizontal and rectangular and 2/3 of picture length.
        Finds also slightly curved lines by image rotation'''
    checkrange = np.insert(
        np.arange(-int(rotrange/2), int(rotrange/2)), 0, 0)
    test = mat.copy()

    for degree in checkrange:
        res = detect_rect(test, minlineprop)
        if check_for_rect(res):
            print("Rotated", degree, "degrees.", end='\n')
            return ndimage.rotate(res, -degree, reshape = False)
        else:
            print("Rotateing", degree, "degrees.", end='\r')
            test = ndimage.rotate(mat, degree, reshape = False)
    return None

#### MAIN
# inputs
img_path = "img/img1.png"

img = cv2.imread(img_path, 0)
dims = img.shape
# denoise for more edgy picture
img = cv2.fastNlMeansDenoising(img, None, 10, 5, 21)
# Canny edge detection
edg = cv2.Canny(img, 50, 240, apertureSize=3)
# smooth the edges slightly for smoother lines
edg = ndimage.gaussian_filter(edg, 2)
# hugh = apply_hough(edg, thresh = 250, maxgap = 2, minline = min(dims)*0.5)
# edge_dec(edg, hugh)
#edg = ndimage.rotate(edg, 1, reshape = False)
edge_dec(img, edg)

plt.close()

detected = detect_rect(edg, .58)
edge_dec(edg, detected)


rectd = detect_rot_rect(edg, .58, 30)
if rectd is not None:
    edge_dec(edg, rectd)
else:
    print("Could not find the frame!")

## from git's main function
# contours = get_contours(img)
# bounds = get_boundaries(img, contours)
# cropped = crop(img, bounds)

# use the countour finding on the other solution after this
# frame reduction

####
#### NOTE: from here on snatched from the git
####

def crop(img, boundaries):
    """Crop the image to the given boundaries."""
    minx, miny, maxx, maxy = boundaries
    return img[miny:maxy, minx:maxx]

def get_contours(img):
    """Threshold the image and get contours."""
    # First make the image 1-bit and get contours
    imgray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Find the right threshold level
    tl = 100
    ret, thresh = cv2.threshold(imgray, tl, 255, 0)
    while white_percent(thresh) > 0.85:
        tl += 10
        ret, thresh = cv2.threshold(imgray, tl, 255, 0)

    contours, hierarchy = cv2.findContours(thresh, 1, 2)

    # filter contours that are too large or small
    contours = [cc for cc in contours if contourOK(img, cc)]
    return contours

def get_boundaries(img, contours):
    """Find the boundaries of the photo in the image using contours."""
    # margin is the minimum distance from the edges of the image, as a fraction
    ih, iw = img.shape[:2]
    minx = iw
    miny = ih
    maxx = 0
    maxy = 0

    for cc in contours:
        x, y, w, h = cv2.boundingRect(cc)
        if x < minx: minx = x
        if y < miny: miny = y
        if x + w > maxx: maxx = x + w
        if y + h > maxy: maxy = y + h

    return (minx, miny, maxx, maxy)

def get_size(img):
    """Return the size of the image in pixels."""
    ih, iw = img.shape[:2]
    return iw * ih

def white_percent(img):
    """Return the percentage of the thresholded image that's white."""
    return cv2.countNonZero(img) / get_size(img)

def contourOK(img, cc):
    """Check if the contour is a good predictor of photo location."""
    # Dont check edges, they dont matter here
    # if near_edge(img, cc): return False # shouldn't be near edges
    x, y, w, h = cv2.boundingRect(cc)
    if w < 100 or h < 100: return False # too narrow or wide is bad
    area = cv2.contourArea(cc)
    if area > (get_size(img) * 0.3): return False
    if area < 200: return False
    return True
