import os
import math
import operator
import numpy as np
import tempfile, subprocess

import scipy
import scipy.misc as misc
import scipy.ndimage as ndimage
import scipy.spatial as spatial
from scipy.signal.signaltools import correlate2d as c2d

from PIL import Image, ImageDraw, ImageFilter

class BBox(object):
    def __init__(self, x1, y1, x2, y2):
        '''
        (x1, y1) is the upper left corner,
        (x2, y2) is the lower right corner,
        with (0, 0) being in the upper left corner.
        '''
        if x1 > x2: x1, x2 = x2, x1
        if y1 > y2: y1, y2 = y2, y1
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2
    def taxicab_diagonal(self):
        '''
        Return the taxicab distance from (x1,y1) to (x2,y2)
        '''
        return self.x2 - self.x1 + self.y2 - self.y1
    def overlaps(self, other):
        '''
        Return True iff self and other overlap.
        '''
        return not ((self.x1 > other.x2)
                    or (self.x2 < other.x1)
                    or (self.y1 > other.y2)
                    or (self.y2 < other.y1))
    def __eq__(self, other):
        return (self.x1 == other.x1
                and self.y1 == other.y1
                and self.x2 == other.x2
                and self.y2 == other.y2)

def find_paws(data, smooth_radius = 5, threshold = 0.0001):
    # http://stackoverflow.com/questions/4087919/how-can-i-improve-my-paw-detection
    """Detects and isolates contiguous regions in the input array"""
    # Blur the input data a bit so the paws have a continous footprint 
    data = ndimage.uniform_filter(data, smooth_radius)
    # Threshold the blurred data (this needs to be a bit > 0 due to the blur)
    thresh = data > threshold
    # Fill any interior holes in the paws to get cleaner regions...
    filled = ndimage.morphology.binary_fill_holes(thresh)
    # Label each contiguous paw
    coded_paws, num_paws = ndimage.label(filled)
    # Isolate the extent of each paw
    # find_objects returns a list of 2-tuples: (slice(...), slice(...))
    # which represents a rectangular box around the object
    data_slices = ndimage.find_objects(coded_paws)
    return data_slices

def slice_to_bbox(slices):
    for s in slices:
        dy, dx = s[:2]
        yield BBox(dx.start, dy.start, dx.stop+1, dy.stop+1)

def remove_overlaps(bboxes):
    '''
    Return a set of BBoxes which contain the given BBoxes.
    When two BBoxes overlap, replace both with the minimal BBox that contains both.
    '''
    # list upper left and lower right corners of the Bboxes
    corners = []

    # list upper left corners of the Bboxes
    ulcorners = []

    # dict mapping corners to Bboxes.
    bbox_map = {}

    for bbox in bboxes:
        ul = (bbox.x1, bbox.y1)
        lr = (bbox.x2, bbox.y2)
        bbox_map[ul] = bbox
        bbox_map[lr] = bbox
        ulcorners.append(ul)
        corners.append(ul)
        corners.append(lr)        

    # Use a KDTree so we can find corners that are nearby efficiently.
    tree = spatial.KDTree(corners)
    new_corners = []
    for corner in ulcorners:
        bbox = bbox_map[corner]
        # Find all points which are within a taxicab distance of corner
        indices = tree.query_ball_point(
            corner, bbox_map[corner].taxicab_diagonal(), p = 1)
        for near_corner in tree.data[indices]:
            near_bbox = bbox_map[tuple(near_corner)]
            if bbox != near_bbox and bbox.overlaps(near_bbox):
                # Expand both bboxes.
                # Since we mutate the bbox, all references to this bbox in
                # bbox_map are updated simultaneously.
                bbox.x1 = near_bbox.x1 = min(bbox.x1, near_bbox.x1)
                bbox.y1 = near_bbox.y1 = min(bbox.y1, near_bbox.y1) 
                bbox.x2 = near_bbox.x2 = max(bbox.x2, near_bbox.x2)
                bbox.y2 = near_bbox.y2 = max(bbox.y2, near_bbox.y2) 
    return set(bbox_map.values())

def load_samples( parent_dir='samples'):
    m = dict() # m is our map, a dict of lists of numpy arrays
    for d in os.listdir( parent_dir ):
        if os.path.isdir( os.path.join( parent_dir, d ) ):
            continue
        filename = os.path.join( parent_dir, d )
        letter = os.path.basename( filename ).split( '.' )[0]
        if not letter.startswith( 'to_validate' ):
            m[letter] = misc.imread( filename )
    return m 

def image2letter( image, digits_map ):
    best_key = None
    best_score = None
    #h1 = misc.toimage( image ).histogram()
    im1 = prepare_image( misc.fromimage( image ) )
    for ( k, ir ) in digits_map.items():
        #h2 = misc.toimage( ir ).histogram()
        #rms = math.sqrt( reduce( operator.add, map( lambda a, b: ( a-b )**2, h1, h2 ) )/ len( h1 ) )
        rms = c2d( im1, prepare_image( ir ), 'same' ).max()
        if not best_score or best_score > rms:
            best_key = k
            best_score = rms
    return best_key[0] if best_key else None, best_score

def prepare_image( image ):
    data = scipy.inner( image, [299, 587, 114] ) / 1000.0
    return ( data - data.mean() ) / data.std()

def read_captcha( file ):
    from time import time

    image = Image.open( file )
    image = image.convert( "P" )
    image = image.resize( ( image.size[0] * 3, image.size[1] * 3 ), Image.ANTIALIAS )

    image2 = Image.new( "P", image.size, 255 )

    for x in range( image.size[1] ):
      for y in range( image.size[0] ):
        pix = image.getpixel( ( y, x ) )
        if pix > 15 and pix < 150:
            pass
            image2.putpixel( ( y, x ), 0 )

    image2 = image2.convert( 'RGB' )

    data = misc.fromimage( image2 )
    data_slices = find_paws( 255-data, smooth_radius = 2, threshold = 200 )

    draw = ImageDraw.Draw( image2 )

    letters = []
    bboxes = slice_to_bbox( data_slices )
    for bbox in bboxes:
        xwidth = bbox.x2 - bbox.x1
        ywidth = bbox.y2 - bbox.y1
        if xwidth < 40 and ywidth < 40:
            draw.rectangle( ( bbox.x1 - 1, bbox.y1 - 1, bbox.x2 + 1, bbox.y2 + 1 ), fill='white' )
        elif xwidth > 60 and ywidth > 69:
            letters.append( ( bbox.x1, bbox.y1, bbox.x2, bbox.y2 ) )
            #draw.rectangle( ( bbox.x1 - 1, bbox.y1 - 1, bbox.x2 + 1, bbox.y2 + 1 ), outline='red' )
   
    letters = sorted( letters, key=lambda i: i[0] )
    if len( letters ) == 5: 
        i = 0
        final_result = []
        for letter in letters:
            i += 1
            im = image2.crop( letter )
            image = image.convert( "P" )
            im = im.resize( ( im.size[0], im.size[1] ), Image.ANTIALIAS )
            im = im.filter( ImageFilter.DETAIL )

            dt = misc.fromimage( im )

            filename = 'tools/samples/%s-%d.png' % ( file, i )
            im = misc.toimage( dt )
            im.save( filename )

            tempFile = tempfile.NamedTemporaryFile( delete = False )

            process = subprocess.Popen(['tesseract', filename, tempFile.name, '-psm', '10', 'letters' ], stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.STDOUT)
            process.communicate()
            final_result.append( open( tempFile.name + '.txt', 'r' ).read() )

        return ''.join( [ l.upper().strip() for l in final_result ] )


if __name__ == '__main__':
    read_captcha( 'captcha.jpg' )
