#
# This script identifies all unique business sites in the area of interest. It creates a list of
# those sites and a file that maps each distinct business ot a site.
#
# In:
#   biz_bcid.psv
#
# Out:
#   site_list.psv
#   biz_site_lookup.psv: maps businesses to sites
#


import os
import csv
from rtree import index
from e_utils import get_remap_function


print('# Refining list of businesses into list of distinct sites')


msa_base = os.environ.get('MSA_BASE')
msa_name = os.environ.get('MSA_NAME')
ref_dir = '%s/ref' % msa_base
msa_dir = '%s/%s' % (msa_base, msa_name)
biz_dir = '%s/biz' % msa_dir
area_dir = '%s/areas' % msa_dir
parcel_dir = '%s/parcels' % msa_dir
meta_dir = '%s/meta' % msa_dir
road_dir = '%s/roads' % msa_dir


# Get a function that re-maps coordinates for the local CRS.
remap = get_remap_function()


#
# Read the input data, building a list of unique sites. A site's uniqueness is defined by its
# xx and yy coordinates for the local MSA projection. These coordinates are rounded to meters.
#
idn = 0  # a counter, used for assigning site IDs
site_list = {}
biz_count = 0;
in_fname = '%s/biz_list.psv' % biz_dir
print('## Reading list of businesses from "%s"' % in_fname)
with open(in_fname) as infile:
    reader = csv.DictReader(infile, delimiter='|')
    for rec in reader:

        biz_count += 1

        biz_id = rec['pid']
        lon = rec['lon']
        lat = rec['lat']

        # Get the reference coordinates for this location. Basically if the location has geocoded
        # coordinates, we use them; otherwise we use the original coordinates.
        if rec['gclon'] == '' or rec['gclat'] == '':
            ref_lon = float(lon)
            ref_lat = float(lat)
        else:
            ref_lon = float(rec['gclon'])
            ref_lat = float(rec['gclat'])
        
        (xx, yy) = remap(ref_lon, ref_lat)

        key = '%.0f-%.0f' % (xx, yy)
        if key not in site_list:
            idn += 1
            site_id = '%d' % idn
            site_list[key] = {'siteId': site_id,
                              'lon': lon, 'lat': lat, 'xx': xx, 'yy': yy,
                              'bizIdList': []}
        site_list[key]['bizIdList'].append(biz_id)


# Make the output files. First, the list of sites.
out_fname = '%s/site_list.psv' % biz_dir
print('## Writing list of sites to "%s"' % out_fname)
with open(out_fname, 'w') as outfile:
    fieldnames = ['siteId', 'lon', 'lat', 'xx', 'yy']
    writer = csv.DictWriter(outfile, delimiter='|', fieldnames=fieldnames)
    writer.writeheader()
    for key in site_list:
        orec = {'siteId': site_list[key]['siteId'],
                'lon': '%.6f' % float(site_list[key]['lon']),
                'lat': '%.6f' % float(site_list[key]['lat']),
                'xx': '%.0f' % site_list[key]['xx'],
                'yy': '%.0f' % site_list[key]['yy']}
        writer.writerow(orec)


# Next, write the file that gives the mapping between sites and businesses.
out_fname = '%s/biz_site_lookup.psv' % biz_dir
print('## Writing lookup table mapping businesses to sites: "%s"' % out_fname)
with open(out_fname, 'w') as outfile:
    fieldnames = ['siteId', 'bizId']
    writer = csv.DictWriter(outfile, delimiter='|', fieldnames=fieldnames)
    writer.writeheader()
    for key in site_list:
        siteId = site_list[key]['siteId']
        for bizId in site_list[key]['bizIdList']:
            writer.writerow({'siteId': siteId, 'bizId': bizId})


# Build a spatial index for sites.
out_fname = '%s/site_rtree' % biz_dir
print('## Creating a spatial index for sites: "%s"' % out_fname)
try:
    os.remove('%s/site_rtree.dat' % biz_dir)
    os.remove('%s/site_rtree.idx' % biz_dir)
except OSError:
    pass

idx = index.Rtree(out_fname)
for key in site_list:
    xx = float(site_list[key]['xx'])
    yy = float(site_list[key]['yy'])
    idx.insert(0, (xx, yy, xx, yy), site_list[key]['siteId'])
idx.close()


print('## %d businesses map to %d ditinct sites' % (biz_count, len(site_list)))
print
