#
# This script does some final tidying up of business area clusters.
#


import shapely.geometry
import shapely.ops
from shapely.topology import TopologicalError
from shapely.predicates import PredicateError
import csv
import fiona
from rtree import index
import os
import os.path
from e_utils import get_remap_function
from e_utils import remap_feature
from e_gis_support import outer_ring
from copy import copy
from copy import deepcopy


print('# Tidying up business areas.')


msa_base = os.environ.get('MSA_BASE')
msa_name = os.environ.get('MSA_NAME')
ref_dir = '%s/ref' % msa_base
msa_dir = '%s/%s' % (msa_base, msa_name)
area_dir = '%s/areas' % msa_dir
parcel_dir = '%s/parcels' % msa_dir
meta_dir = '%s/meta' % msa_dir


# Don't write out any BAs with fewer than this many components.
min_viable_size = 2

# For remapping coordinates.
remap = get_remap_function()


# This is used below to re-map coordinates from the local system back to WGS84.
def towgs(xx, yy, zz=None):
    return remap(xx, yy, inverse=True)


# This will be an index for all business points. The index gives the BA label of the point.
point_index = index.Index()


fname = '%s/ba_clusters.psv' % area_dir
print('## Reading business area point labels from "%s"' % fname)
ba_points = {}
ba_bounds = {}
site_count_for_label = {}
with open(fname) as infile:
    reader = csv.DictReader(infile, delimiter='|')
    for rec in reader:
        sid = rec['siteId']
        label = rec['label']
        lon = float(rec['lon'])
        lat = float(rec['lat'])
        (xx, yy) = remap(lon, lat)

        # Insert this point into our spatial index for all points.
        point_index.insert(0, (xx, yy, xx, yy), label)


# Read all business area polygons. While we're at it, unroll all multipolygons into single
# polygons. This changes the polygon IDs.

poly_list = {}
idn = 0

fname = area_dir + '/s_ba_ortho.shp'
print('## Reading business area shapes from "%s"' % fname)
with fiona.open(fname) as source:
    for f0 in source:
        f1 = remap_feature(f0, remap)
        s1 = shapely.geometry.shape(f1['geometry'])
        if s1.geom_type == 'Polygon':
            idn += 1
            poly_list[idn] = outer_ring(s1)
        elif s1.geom_type == 'MultiPolygon':
            for s1x in s1.geoms:
                if s1x.geom_type == 'Polygon':
                    idn += 1
                    poly_list[idn] = outer_ring(s1x)


# Write the file containing the unrolled polygons.
# crs = '+proj=longlat +ellps=WGS84 +datum=WGS84'
# driver = 'ESRI Shapefile'
# outfile = area_dir + '/s_ba_polys.shp'
# print('## Writing business area shapes to "%s"' % outfile)
# schema = {'geometry': 'Polygon', 'properties': {'label': 'str'}}
# with fiona.open(outfile, 'w', driver=driver, crs=crs, schema=schema) as dest:
#     for label in poly_list:
#         shape = shapely.ops.transform(towgs, poly_list[label])
#         outFeature = {
#             'geometry': shapely.geometry.mapping(shape),
#             'properties': {'label': label}}
#         dest.write(outFeature)


# Make a spatial index for the polygons.
poly_index = index.Index()
for label in poly_list:
    bb = poly_list[label].bounds
    poly_index.insert(0, poly_list[label].bounds, label)


# A post-processing step. We sometimes get shapes that have a hole that contains
# some small, separate BA. Here we look for those cases, and we just merge the smaller with
# the larger.
print('## Dealing with overlaps')
tbr = set()
for label0 in poly_list:

    if label0 in tbr:
        continue

    p0 = poly_list[label0].buffer(0.0)
    bb = p0.bounds
    if len(bb) != 4:
        continue

    nearby = poly_index.intersection(bb, objects=True)
    for zz in nearby:

        label1 = zz.object
        if label0 == label1 or label1 in tbr:
            continue

        try:

            p1 = poly_list[label1].buffer(0.0)
            if p1.intersects(p0):

                px = p1.intersection(p0)
                a0 = p0.area
                a1 = p1.area
                ax = px.area
                # print('intersection areas: areas: %.1f %.1f %.1f' % (a0, a1, ax))

                if ax < 0.1:
                    # print('doing nothing')
                    continue

                if a0 > a1:
                    if ax / a1 > 0.5:
                        # If the overlap area is a big enough fraction of the smaller shape, then
                        # merge the smaller with the larger.
                        # print('absorbing %s into %s and marking %s for deletion' % (label1, label0, label1))
                        poly_list[label0] = shapely.ops.cascaded_union((p0, p1))
                        tbr.add(label1)
                    else:
                        # Otherwise, give the overlap chunk to the smaller shape.
                        # print('punching overlap out of %s' % label0)
                        poly_list[label0] = p0.difference(px)
                else:
                    # This branch does the same as above, but for the case where p1 is larger than p0.
                    if ax / a0 > 0.5:
                        # print('absorbing %s into %s and marking %s for deletion' % (label0, label1, label0))
                        poly_list[label1] = shapely.ops.cascaded_union((p0, p1))
                        tbr.add(label0)
                    else:
                        # print('punching overlap out of %s' % label1)
                        poly_list[label1] = p1.difference(px)
        except (TopologicalError, ValueError):
            # print('!!! Error processing polygons "%s" and "%s"' % (label0, label1))
            pass



new_poly_list = {}
idn = 0
for label in poly_list:

    if label in tbr:
        continue

    s1 = poly_list[label]
    if s1.geom_type == 'Polygon':
        idn += 1
        new_poly_list[idn] = outer_ring(s1)
    elif s1.geom_type == 'MultiPolygon':
        for s1x in s1.geoms:
            if s1x.geom_type == 'Polygon':
                idn += 1
                new_poly_list[idn] = outer_ring(s1x)

poly_list = new_poly_list


# Below we will be filtering out polygons based in part of the local tapestry classification.
# Specifically we will need to know whether a BA falls entirely within a residential area.
# The easiest way to do this is to store and index the tapestry polygons that do NOT
# correspond to residential areas.
tap_index = index.Index()
tap_shape_list = {}
fname = '%s/tapestry.shp' % meta_dir
if os.path.isfile(fname):
    print('## Reading tapestry information from "%s"' % fname)
    with fiona.open(fname) as source:
        for f0 in source:
            if f0['properties']['type'] == 'countHousing':
                continue
            s0 = shapely.geometry.geo.shape(f0['geometry'])
            s1 = shapely.ops.transform(remap, s0)
            id = f0['properties']['id']
            tap_index.insert(0, s1.bounds, id)
            tap_shape_list[id] = s1


# Get rid of any polygons that have less than the minimum number of points.
print('## Removing empty polygons')
tbr = []
for label in poly_list:

    # Count the number of points in this polygon.
    point_count = 0
    bb = poly_list[label].bounds
    nearby = point_index.intersection(bb, objects=True)
    for x in nearby:
        pp = shapely.geometry.Point(x.bbox[0], x.bbox[1])
        if poly_list[label].contains(pp):
            point_count += 1

    # See whether this polygon is all residential.
    is_residential = True
    nearby = tap_index.intersection(bb, objects=True)
    for x in nearby:
        id = x.object
        if tap_shape_list[id].intersects(poly_list[label]):
            is_residential = False

    if point_count < min_viable_size or (point_count < 4 and is_residential):
        tbr.append(label)

for label in tbr:
    del poly_list[label]



crs = '+proj=longlat +ellps=WGS84 +datum=WGS84'
driver = 'ESRI Shapefile'
outfile = area_dir + '/s_ba_shapes.shp'
print('## Writing business area shapes to "%s"' % outfile)
schema = {'geometry': 'Polygon', 'properties': {'label': 'str'}}
with fiona.open(outfile, 'w', driver=driver, crs=crs, schema=schema) as dest:
    for label in poly_list:

        shape = shapely.ops.transform(towgs, poly_list[label])
        outFeature = {
            'geometry': shapely.geometry.mapping(shape),
            'properties': {'label': label}}
        dest.write(outFeature)


