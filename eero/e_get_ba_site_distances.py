#
# This script gets a list of inter-site distances to be used for business area definition.
#


import csv
from rtree import index
import os
from e_utils import get_remap_function


print('# Compiling a collection of inter-site distance metrics for area definition')


msa_base = os.environ.get('MSA_BASE')
msa_name = os.environ.get('MSA_NAME')
msa_dir = '%s/%s' % (msa_base, msa_name)
ref_dir = '%s/ref' % msa_base
area_dir = '%s/areas' % msa_dir
biz_dir = '%s/biz' % msa_dir
road_dir = '%s/roads' % msa_dir


# A function for coordinate transformations.
remap = get_remap_function()


# Parameters used below.
distance_cutoff = 400.0


# First, get a list of all sites to be used for area definition.
ba_site_list = {}
fname = area_dir + '/ba_site_list.psv'
print('## Reading list of sites from "%s"' % fname)
with open(fname) as infile:
    reader = csv.DictReader(infile, delimiter='|')
    for rec in reader:
        sid = rec['siteId']
        xx = float(rec['xx'])
        yy = float(rec['yy'])
        ba_site_list[sid] = {'xx': xx, 'yy': yy}


# Make a spatial index for sites.
print('## Creating a spatial index for sites')
site_rtree = index.Index()
for site_id in ba_site_list:
    xx = float(ba_site_list[site_id]['xx'])
    yy = float(ba_site_list[site_id]['yy'])
    site_rtree.insert(0, (xx, yy, xx, yy), site_id)


# Read the list of road network distances. It is indexed by a tuple consisting of two
# site identifiers.
ifname = '%s/site_road_distances_scaled.psv' % biz_dir
print('## Reading scaled road network distances from "%s"' % ifname)
road_distance_lookup = {}
with open(ifname) as infile:
    reader = csv.DictReader(infile, delimiter='|')
    for rec in reader:
        road_distance_lookup[(rec['siteId0'], rec['siteId1'])] = rec['distance']


# Loop over all sites. For each one, check the spatial index for sites that fall within
# a threshold Euclidean distance.
ofname = '%s/ba_site_distances.psv' % area_dir
print('## Creating file containing inter-site distance metrics: "%s"' % ofname)
print('### Output will only contain site pairs within %.0f meters of one another (Euclidean)' % distance_cutoff)
with open(ofname, 'w') as outfile:
    writer = csv.writer(outfile, delimiter='|')
    writer.writerow(('siteId0', 'siteId1', 'distance'))

    print('## Looping over sites')
    k = 0
    for siteId0 in ba_site_list:

        k += 1
        if k % 1000 == 0:
            print('### Site %d / %d' % (k, len(ba_site_list)))

        xx0 = float(ba_site_list[siteId0]['xx'])
        yy0 = float(ba_site_list[siteId0]['yy'])
        thresh = distance_cutoff
        nearby = site_rtree.intersection((xx0-thresh, yy0-thresh, xx0+thresh, yy0+thresh), objects=True)
        for x in nearby:
            siteId1 = x.object

            xx1 = float(ba_site_list[siteId1]['xx'])
            yy1 = float(ba_site_list[siteId1]['yy'])

            # Road network distance.
            if siteId0 < siteId1:
                ix = (siteId0, siteId1)
            else:
                ix = (siteId1, siteId0)
            if ix in road_distance_lookup:
                distance = '%.0f' % float(road_distance_lookup[ix])
                writer.writerow((siteId0, siteId1, distance))

print