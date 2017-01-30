#
# This script assigns every business site to a point on the road network.
# The output is an amended list of sites. The extra fields are an identifier of the
# road segment that the site lies on, the length of that segment, and the distance along the
# segment where the site can be found.
#


import os
import csv
from rote import *
from rtree import index
import shapely.geometry
from e_utils import get_remap_function
from e_utils import psvin


print('# Mapping business sites to points on the road network')


msa_base = os.environ.get('MSA_BASE')
msa_name = os.environ.get('MSA_NAME')
msa_dir = '%s/%s' % (msa_base, msa_name)
ref_dir = '%s/ref' % msa_dir
area_dir = '%s/areas' % msa_dir
biz_dir = '%s/biz' % msa_dir
road_dir = '%s/roads' % msa_dir


# Get a function to re-map coordinates for the local CRS.
remap = get_remap_function()


# Get the list of all business sites. [Remember these are the distinct business locations,
# not the actual businesses.]
fname = '%s/site_list.psv' % biz_dir
print('## Reading list of businesses from "%s"' % fname)
siteList = []
with open(fname) as infile:
    reader = csv.DictReader(infile, delimiter='|')
    siteFieldnames = reader.fieldnames
    for rec in reader:
        siteList.append(rec)


# Get a list of all road segments. A "segment" here is corresponds to an "edge" in the
# road network graph. I use the two terms to mean different things. An "edge" is an element
# of the road network graph -- i.e. it's just a connection between two road network
# "nodes" (i.e. intersections). A "segment" refers to the actual shape represented by an edge.
# So a "segment" consists of the list of all the coordinates that define its shape.
# We need the "segment" data in order to match with site locations.
fname = '%s/road_segments.psv' % road_dir
print('## Reading road segments from "%s"' % fname)
segList = {}
with open(fname) as infile:
    reader = csv.DictReader(infile, delimiter='|')
    for rec in reader:
        edge_id = rec['edge_id']
        if edge_id not in segList:
            segList[edge_id] = {'xx': [], 'yy': []}
        segList[edge_id]['xx'].append(float(rec['xx']))
        segList[edge_id]['yy'].append(float(rec['yy']))


# In another script, we built a spatial index for the road segments. This reads it back in.
seg_rtree = index.Rtree('%s/road_segments' % road_dir)


# Utility function to convert a set of coordinates into a shapely shape, which we use for
# further calculations below.
def make_segment_shape(seg):
    n = len(seg['xx'])
    cc = []
    for i in range(n):
        cc.append((seg['xx'][i], seg['yy'][i]))
    shape = shapely.geometry.LineString(cc)
    return shape


# As we do the match-up between business sites and road segments, we will keep encountering
# the same segments because businesses cluster. We will use this dictionary to remember them
# so we don't need to keep re-creating them.
seg_shape_list = {}


# Loop over all business sites. For each one, find its closest road segment and map its coordinates
# onto it. Also remember the edge ID for each site.
print('## Looping over sites')
k = 0
for site in siteList:

    k += 1
    if k % 1000 == 0:
        print('### Site %d / %d' % (k, len(siteList)))

    # Get a shapely "point" for this site.
    xx = float(site['xx'])
    yy = float(site['yy'])
    pt = shapely.geometry.Point(xx, yy)

    # Select a bounding box with which to search for nearby road segments.  Here we
    # just grow the size of the box until we get at least one hit.
    dd = 300.0
    cc = 0
    while cc == 0:
        bb = (xx-dd, yy-dd, xx+dd, yy+dd)
        cc = seg_rtree.count(bb)
        if cc == 0:
            dd += 50.0

    nearest_distance = None
    nearest_seg_id = None
    nearby = seg_rtree.intersection(bb, objects=True)
    for x in nearby:
        seg_id = x.object

        if len(segList[seg_id]['xx']) < 2:
            continue

        if seg_id not in seg_shape_list:
            seg_shape_list[seg_id] = make_segment_shape(segList[seg_id])

        dd = pt.distance(seg_shape_list[seg_id])
        if nearest_distance is None or dd < nearest_distance:
            nearest_distance = dd
            nearest_seg_id = seg_id

    seg = seg_shape_list[nearest_seg_id]
    distance_along = seg.project(pt)
    nearest_point = seg.interpolate(distance_along)
    nearest_x = nearest_point.xy[0][0]
    nearest_y = nearest_point.xy[1][0]
    (nearestLon, nearestLat) = remap(nearest_x, nearest_x, inverse=True)

    site['segId'] = nearest_seg_id
    site['segDistance'] = '%.1f' % nearest_distance
    site['segAlong'] = '%.1f' % distance_along
    site['segLength'] = '%.1f' % seg.length
    site['segxx'] = '%.1f' % nearest_x
    site['segyy'] = '%.1f' % nearest_y


fname = '%s/site_road_info.psv' % biz_dir
print('## Writing site road info file "%s"' % fname)
with open(fname, 'w') as outfile:
    fieldnames = siteFieldnames + ['segId', 'segDistance', 'segAlong', 'segLength', 'segxx', 'segyy']
    writer = csv.DictWriter(outfile, delimiter='|', fieldnames=fieldnames)
    writer.writeheader()
    for rec in siteList:
        writer.writerow(rec)


# Write a file showing the mapping between original locations and road network locations.
# This is just for validation -- it's not used for any further calculations.
import fiona
from e_utils import get_projection_string
crs = get_projection_string()
driver = 'ESRI Shapefile'
schema = {'geometry': 'LineString',
          'properties': {'id': 'str', 'segId': 'str'}}

fname = '%s/site_road_remap.shp' % biz_dir
print('## Writing shapefile with site-to-road re-mapping info: "%s"' % fname)
with fiona.open(fname, 'w', crs=crs, driver=driver, schema=schema) as dest:
    for rec in siteList:
        coords = [(float(rec['xx']), float(rec['yy'])), (float(rec['segxx']), float(rec['segyy']))]
        feature = {'type': 'Feature','id': id,
                   'geometry': {'coordinates': coords, 'type': 'LineString'},
                   'properties': {'id': rec['siteId'], 'segId': rec['segId']}}
        dest.write(feature)

print
