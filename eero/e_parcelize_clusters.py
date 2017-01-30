#
# This script creates a "parcelized" set of business areas.
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
# from e_gis_support import ortho_merge
from scipy.spatial import Voronoi
from copy import copy


print('# Parcelizing business areas.')


msa_base = os.environ.get('MSA_BASE')
msa_name = os.environ.get('MSA_NAME')
ref_dir = '%s/ref' % msa_base
msa_dir = '%s/%s' % (msa_base, msa_name)
biz_dir = '%s/biz' % msa_dir
area_dir = '%s/areas' % msa_dir
parcel_dir = '%s/parcels' % msa_dir
meta_dir = '%s/meta' % msa_dir
road_dir = '%s/roads' % msa_dir


min_viable_size = 4
remap = get_remap_function()


# Get a list of sites.
fname = '%s/ba_clusters.psv' % area_dir
print('## Reading business area labels from "%s"' % fname)
ba_site_list = {}
with open(fname) as infile:
    reader = csv.DictReader(infile, delimiter='|')
    for rec in reader:
        sid = rec['siteId']
        label = rec['label']
        lon = float(rec['lon'])
        lat = float(rec['lat'])
        (xx, yy) = remap(lon, lat)
        ba_site_list[sid] = {'label': label, 'xx': xx, 'yy': yy}


# Read the list of parcel labels for each site. There is one parcel or every site, but
# generally multiple sites per parcel. We will need lookup tables that go both ways.
fname = '%s/site_parcel_lookup.psv' % parcel_dir
print('## Reading site / parcel lookup from "%s"' % fname)
parcel_for_site = {}
sites_for_parcel = {}
with open(fname) as infile:
    reader = csv.DictReader(infile, delimiter='|')
    for rec in reader:
        sid = rec['siteId']
        if sid in ba_site_list:
            pid = int(rec['parcelId'])
            parcel_for_site[sid] = pid
            if pid not in sites_for_parcel:
                sites_for_parcel[pid] = []
            sites_for_parcel[pid].append(sid)


# Read the list of sites along with their labels.
fname = '%s/ba_clusters.psv' % area_dir
print('## Reading business area labels from "%s"' % fname)
ba_site_list = {}
site_count_for_label = {}
with open(fname) as infile:
    reader = csv.DictReader(infile, delimiter='|')
    for rec in reader:
        sid = rec['siteId']
        label = rec['label']
        lon = float(rec['lon'])
        lat = float(rec['lat'])
        (xx, yy) = remap(lon, lat)
        ba_site_list[sid] = {'label': label, 'xx': xx, 'yy': yy}
        if label not in site_count_for_label:
            site_count_for_label[label] = 0
        site_count_for_label[label] += 1


# Read all parcel polygons.
fn = parcel_dir + '/parcels.shp'
print('## Reading original parcel data from "%s"' % fn)
ba_list = {}
with fiona.open(fn) as source:
    driver = source.driver
    crs = source.crs
    k = 0
    for f0 in source:

        # Get the ID for this parcel.
        pid = f0['properties']['id']

        # Skip this parcel if it's not one of our BA parcels.
        if pid not in sites_for_parcel:
            continue

        k += 1
        if k % 1000 == 0:
            print('### Parcel %d' % k)

        # Make the feature into a shape, and re-map it to the local CRS.
        s0 = shapely.geometry.geo.shape(f0['geometry'])
        s1 = shapely.ops.transform(remap, s0)

        # Get the list of all sites that fall in this parcel.
        for sid in sites_for_parcel[pid]:
            label = ba_site_list[sid]['label']
            if label not in ba_list:
                ba_list[label] = []
            ba_list[label].append(s1)

        # # Determine how many unique labels there are in this parcel.
        # labels_in_parcel = set()
        # for sid in sites_in_parcel:
        #     if sid in ba_site_list:
        #         labels_in_parcel.add(ba_site_list[sid]['label'])
        #
        # # If all of the sites in this parcel have the same label, then just add it to our list.
        # if len(labels_in_parcel) == 1:
        #     sid = sites_in_parcel[0]
        #     label = ba_site_list[sid]['label']
        #     if label not in ba_list:
        #         ba_list[label] = []
        #     ba_list[label].append(s1)
        # else:
        #     # If we get here, then we need to split this parcel ("s1") into sub-polygons,
        #     # each containing only points with one label.
        #     points = []
        #     labels = []
        #     for sid in sites_in_parcel:
        #         points.append((ba_site_list[sid]['xx'], ba_site_list[sid]['yy']))
        #         labels.append(ba_site_list[sid]['label'])
        #     vp_list = subdivide(s1, points, labels)
        #     for z in vp_list:
        #         label = z['label']
        #         if label not in ba_list:
        #             ba_list[label] = []
        #         ba_list[label].append(z['shape'])


# Make a list of business area polygons represented as multipolygons.
print('## Making a representation of business areas as multipolygons.')
ba_multi = {}
for label in ba_list:
    ba_multi[label] = shapely.ops.cascaded_union(ba_list[label])


def geom_count(s):
    gc = -1
    if s.geom_type == 'Polygon':
        gc = 1
    elif s.geom_type == 'MultiPolygon':
        gc = len(s.geoms)
    return gc


def poly_merge(s0, label):
    """
    Adapted from the original R version (below) by Sebastian Santibanez.

    The input is a multipolygon, The output is a "merged" version having an envelope that
    approximately follows the outer contours of the input multipolygon.

    :param s0:
    :return:
    """
    if s0.geom_type == 'Polygon':
        return s0
    ff = copy(s0)
    try:
        nc = len(s0.geoms)
        buffer_size = 30.0

        while ff.geom_type == 'MultiPolygon' and len(ff.geoms) > 1 and buffer_size <= 500.0:
            tmp0 = copy(s0)
            tmp1 = tmp0.buffer(+buffer_size)
            tmp2 = tmp1.buffer(-buffer_size)
            ff = shapely.ops.cascaded_union((tmp2, s0))
            buffer_size += 5.0
    except ValueError:
        print('!!! Error in poly_merge')
    return ff


def ortho_merge(s0, label):
    """
    Adapted from the original R version (below) by Sebastian Santibanez.

    The input is a multipolygon, The output is a "merged" version having an envelope that
    approximately follows the outer contours of the input multipolygon.

    :param s0:
    :return:
    """
    if s0.geom_type == 'Polygon':
        return s0

    ff = copy(s0)

    try:
        nc = len(s0.geoms)
        buffer_size = 10.0

        while ff.geom_type == 'MultiPolygon' and len(ff.geoms) > 1 and buffer_size < 501.0:
            tmp0 = copy(s0)
            tmp1 = tmp0.buffer(+buffer_size, resolution=4, cap_style=2, join_style=2, mitre_limit=2.5)
            tmp2 = tmp1.buffer(-buffer_size, resolution=4, cap_style=2, join_style=2, mitre_limit=2.5)
            ff = shapely.ops.cascaded_union((tmp2, s0))
            buffer_size += 5.0
    except ValueError:
        print('!!! Error in ortho_merge')

    if buffer_size > 499.0:
        print('!!! "%s": Orthogonal merge failed -- trying regular merge' % label)
        ff = poly_merge(s0, label)

    return ff


# Do an orthogonal merge of each multipolygon.
print('## Doing an orthogonal merge of business area multipolygons')
k = 0
ba_ortho = {}
for label in ba_multi:

    k += 1
    if k % 500 == 0:
        print('### Multipolygon %d / %d' % (k, len(ba_multi)))

    ss = ba_multi[label]
    ba_ortho[label] = ortho_merge(ss, label)


# This is used below to re-map coordinates from the local system back to WGS84.
def towgs(xx, yy, zz=None):
    return remap(xx, yy, inverse=True)


outfile = area_dir + '/s_ba_multi.shp'
print('## Writing business area polygons to "%s"' % outfile)
schema = {'geometry': 'Polygon', 'properties': {'label': 'str'}}
with fiona.open(outfile, 'w', driver=driver, crs=crs, schema=schema) as dest:
    for label in ba_multi:
        if site_count_for_label[label] < min_viable_size:
            continue
        shape = shapely.ops.transform(towgs, ba_multi[label])
        outFeature = {
            'geometry': shapely.geometry.mapping(shape),
            'properties': {'label': label}}
        dest.write(outFeature)


outfile = area_dir + '/s_ba_ortho.shp'
print('## Writing business area polygons to "%s"' % outfile)
schema = {'geometry': 'Polygon', 'properties': {'label': 'str'}}
with fiona.open(outfile, 'w', driver=driver, crs=crs, schema=schema) as dest:
    for label in ba_ortho:
        if site_count_for_label[label] < min_viable_size:
            continue
        shape = shapely.ops.transform(towgs, ba_ortho[label])
        if shape.geom_type != 'Polygon' and shape.geom_type != 'MultiPolygon':
            print ('### Skipping %s (type %s)' % (label, shape.geom_type))
            continue
        outFeature = {
            'geometry': shapely.geometry.mapping(shape),
            'properties': {'label': label}}
        dest.write(outFeature)

