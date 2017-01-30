#
# This script reads in business areas as point clusters, and creates a GIS layer that wraps them in
# nice compact polygons.
#


import shapely.geometry
import shapely.ops
from shapely.topology import TopologicalError
from shapely.predicates import PredicateError
import csv
import fiona
from rtree import index
import os
from e_utils import get_remap_function
from e_gis_support import vpsplit
from e_gis_support import ortho_merge
from e_gis_support import poly_merge


print('# Wrapping business areas.')


msa_base = os.environ.get('MSA_BASE')
msa_name = os.environ.get('MSA_NAME')
ref_dir = '%s/ref' % msa_base
msa_dir = '%s/%s' % (msa_base, msa_name)
area_dir = '%s/areas' % msa_dir
parcel_dir = '%s/parcels' % msa_dir
meta_dir = '%s/meta' % msa_dir


# These factors control the "closing" operation on point clouds.
dilation_factor = 250.0
erosion_factor = -249.0

# This is for final trimming of the BAs.
trim_factor = 0.0

# For remapping coordinates.
remap = get_remap_function()


# This will be an index for all business points. The index gives the BA label of the point.
point_index = index.Index()

# from e_gis_support import ortho_merge
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

        # Add this coordinate pair to the list for this site. Also expand the bounds given the new coords.
        if label not in ba_points:
            ba_points[label] = []
            ba_bounds[label] = (xx, yy, xx, yy)
        ba_points[label].append((xx, yy))
        x0 = min(xx, ba_bounds[label][0])
        y0 = min(yy, ba_bounds[label][1])
        x1 = max(xx, ba_bounds[label][2])
        y1 = max(yy, ba_bounds[label][3])
        ba_bounds[label] = (x0, y0, x1, y1)


# Make a set of polygons representing a closing of the point cloud for each BA.
print('## Closing point clouds')
blob_list = {}
glob_list = {}
blob_index = index.Index()
k = 0
for label in ba_points:

    k += 1
    # if k > 100:
    #     break

    coords = ba_points[label]
    s0 = shapely.geometry.MultiPoint(coords)
    s1 = s0.buffer(dilation_factor)
    s2 = s1.buffer(erosion_factor)
    glob_list[label] = s1
    blob_list[label] = s2
    blob_index.insert(0, s2.bounds, label)


# Go through all parcels. For each one, find any blob that it intersects, and add it to the
# set of parcels associated with that blob.
print('## Finding all parcels that touch any blob.')
parcels_list = {}
fn = parcel_dir + '/parcels.shp'
with fiona.open(fn) as source:
    parcel_count = len(source)
    k = 0
    for f0 in source:

        k += 1
        if k % 10000 == 0:
            print('### Parcel %d / %d' % (k, parcel_count))
        # if k > 100000:
        #     break

        s0 = shapely.geometry.geo.shape(f0['geometry'])
        s1 = shapely.ops.transform(remap, s0)

        # Get the ID for this parcel.
        parcel_id = f0['properties']['id']

        nb = blob_index.count(s1.bounds)
        if nb == 0:
            continue

        nearby = blob_index.intersection(s1.bounds, objects=True)
        for x in nearby:
            label = x.object
            if s1.intersects(blob_list[label]):
                if label not in parcels_list:
                    parcels_list[label] = []
                parcels_list[label].append(s1)


clob_list = {}
for label in parcels_list:
    # clob_list[label] = shapely.ops.cascaded_union(parcels_list[label]).intersection(glob_list[label])
    clob_list[label] = shapely.ops.cascaded_union(parcels_list[label])



print('## Doing an orthogonal merge of all areas')
ortho_list = {}
for label in clob_list:
    ortho_list[label] = ortho_merge(clob_list[label], label)


# print('## Subdividing clobs based on Voronoi polygons')
# chunk_list = {}
# k = 0
# for label in clob_list:
#
#     k += 1
#     if k % 200 == 0:
#         print('### Handling clob %d / %d' % (k, len(glob_list)))
#
#     # Get a big area around this shape in which to look for other points.
#     dd = 1000.0
#     x0 = ba_bounds[label][0] - dd
#     y0 = ba_bounds[label][1] - dd
#     x1 = ba_bounds[label][2] + dd
#     y1 = ba_bounds[label][3] + dd
#
#     np = point_index.count((x0, y0, x1, y1))
#     # print('### Found %d points near area "%s"' % (np, label))
#
#     point_list = []
#     label_list = []
#     nearby = point_index.intersection((x0, y0, x1, y1), objects=True)
#     for zz in nearby:
#         point_list.append((zz.bounds[0], zz.bounds[2]))
#         label_list.append(zz.object)
#
#     clob = clob_list[label]
#
#     try:
#         vp_list = vpsplit(clob,  point_list, label_list)
#
#         keepers = []
#         for pp in vp_list:
#             #if pp['label'] == label and pp['shape'].geom_type == 'Polygon':
#             if pp['label'] == label:
#                 keepers.append(pp['shape'])
#
#         chunk_list[label] = shapely.ops.cascaded_union(keepers)
#
#     except TopologicalError:
#         chunk_list[label] = clob


# This is used below to re-map coordinates from the local system back to WGS84.
def towgs(xx, yy, zz=None):
    return remap(xx, yy, inverse=True)


crs = '+proj=longlat +ellps=WGS84 +datum=WGS84'
driver = 'ESRI Shapefile'


outfile = area_dir + '/s_ba_clusters.shp'
print('## Writing business area clusters to "%s"' % outfile)
schema = {'geometry': 'MultiPoint', 'properties': {'label': 'str'}}
with fiona.open(outfile, 'w', driver=driver, crs=crs, schema=schema) as dest:
    for label in ba_points:
        pp = ba_points[label]
        shape = shapely.ops.transform(towgs, shapely.geometry.MultiPoint(pp))
        outFeature = {
            'geometry': shapely.geometry.mapping(shape),
            'properties': {'label': label}}
        dest.write(outFeature)


outfile = area_dir + '/s_ba_blobs.shp'
print('## Writing business area blobs to "%s"' % outfile)
schema = {'geometry': 'Polygon', 'properties': {'label': 'str'}}
with fiona.open(outfile, 'w', driver=driver, crs=crs, schema=schema) as dest:
    for label in blob_list:
        shape = shapely.ops.transform(towgs, blob_list[label])
        outFeature = {
            'geometry': shapely.geometry.mapping(shape),
            'properties': {'label': label}}
        dest.write(outFeature)


# outfile = area_dir + '/s_ba_globs.shp'
# print('## Writing business area globs to "%s"' % outfile)
# schema = {'geometry': 'Polygon', 'properties': {'label': 'str'}}
# with fiona.open(outfile, 'w', driver=driver, crs=crs, schema=schema) as dest:
#     for label in glob_list:
#         shape = shapely.ops.transform(towgs, glob_list[label])
#         outFeature = {
#             'geometry': shapely.geometry.mapping(shape),
#             'properties': {'label': label}}
#         dest.write(outFeature)


# outfile = area_dir + '/s_ba_clobs.shp'
# print('## Writing business area clobs to "%s"' % outfile)
# schema = {'geometry': 'Polygon', 'properties': {'label': 'str'}}
# with fiona.open(outfile, 'w', driver=driver, crs=crs, schema=schema) as dest:
#     for label in clob_list:
#         shape = shapely.ops.transform(towgs, clob_list[label])
#         outFeature = {
#             'geometry': shapely.geometry.mapping(shape),
#             'properties': {'label': label}}
#         dest.write(outFeature)


outfile = area_dir + '/s_ba_ortho.shp'
print('## Writing ortho-merged areas to "%s"' % outfile)
schema = {'geometry': 'Polygon', 'properties': {'label': 'str'}}
with fiona.open(outfile, 'w', driver=driver, crs=crs, schema=schema) as dest:
    for label in ortho_list:
        shape = shapely.ops.transform(towgs, ortho_list[label])
        outFeature = {
            'geometry': shapely.geometry.mapping(shape),
            'properties': {'label': label}}
        dest.write(outFeature)


# outfile = area_dir + '/s_ba_chunks.shp'
# print('## Writing business area chunks to "%s"' % outfile)
# schema = {'geometry': 'Polygon', 'properties': {'label': 'str'}}
# with fiona.open(outfile, 'w', driver=driver, crs=crs, schema=schema) as dest:
#     for label in chunk_list:
#         shape = shapely.ops.transform(towgs, chunk_list[label])
#         outFeature = {
#             'geometry': shapely.geometry.mapping(shape),
#             'properties': {'label': label}}
#         dest.write(outFeature)


print
