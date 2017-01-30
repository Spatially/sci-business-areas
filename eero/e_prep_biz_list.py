#
# This script does some initial preparation of the list of businesses. This includes:
# * Adding business category information.
# * Filtering out any businesses that are not within this MSA's bounds.
# * Adding geocoded coordinates where possible.
#


import shapely.geometry
import os
import os.path
import csv
from e_utils import psvin
from e_utils import get_msa_shape
from e_utils import get_remap_function
import numpy as np


print('# Adding business category information to the list of all businesses')


msa_base = os.environ.get('MSA_BASE')
msa_name = os.environ.get('MSA_NAME')
ref_dir = '%s/ref' % msa_base
msa_dir = '%s/%s' % (msa_base, msa_name)
biz_dir = '%s/biz' % msa_dir
area_dir = '%s/areas' % msa_dir
parcel_dir = '%s/parcels' % msa_dir
meta_dir = '%s/meta' % msa_dir
road_dir = '%s/roads' % msa_dir


msa_shape = get_msa_shape()
remap = get_remap_function()


# THis threshold controls the maximum distance by which the geolocation process is allowed to
# relocate a site's coordinates. If the computed move is greater than this, then the site stays
# where it is.
#
# Based on some spot checks, the bad cases look like they are errors in the US Census geocoder
# rather than in our source data, for wha it's worth.
geocode_reloc_threshold = 50.0


# Read the file that maps SIC codes into NAICS code.
infile = '%s/sbc/lookup_sic_n17.psv' % ref_dir
print('## Using SIC-to-NAICS lookup table "%s"' % infile)
sic_to_n17 = psvin(infile, key='sic')


# Read the table that maps NAICS codes into Spatially Business Class (SBC) codes
infile = '%s/sbc/lookup_n17_sbc.psv' % ref_dir
print('## Using NAICS-to-SBC lookup table "%s"' % infile)
n17_to_sbc = psvin(infile, key='naics2017')


# Read the file that contains a lookup table for geocoded coordinates. If the file defining
# geolocations does not exist, then just initialize a blank lookup table.
geocode_fname = '%s/geocode.psv' % biz_dir
if os.path.isfile(geocode_fname):
    geocode_lookup = psvin(biz_dir + '/geocode.psv', key='key')
else:
    geocode_lookup = {}


# This will store a list of line segments indicating how sites were moved via geolocation.
reloc_list = {}


# Loop over all businesses, applying Spatially business class labels.
in_fname = '%s/biz_list_0.psv' % biz_dir
with open(in_fname) as infile:
    reader = csv.DictReader(infile, delimiter='|')

    out_fname = '%s/biz_list.psv' % biz_dir
    print('## Creating classified business list "%s"' % out_fname)
    with open(out_fname, 'w') as outfile:
        fieldnames = reader.fieldnames + ['gclon', 'gclat', 'bcid', 'bc1', 'bc2', 'bc3']
        writer = csv.DictWriter(outfile, delimiter='|', fieldnames=fieldnames)
        writer.writeheader()

        k = 0

        for rec in reader:

            k += 1
            if k % 10000 == 0:
                print('### Record %d' % k)

            biz_id = rec['pid']

            lon = float(rec['lon'])
            lat = float(rec['lat'])
            if not msa_shape.contains(shapely.geometry.Point(lon, lat)):
                continue

            # Check whether we have geocoded info for this record.
            # The key for geocoded coordinates is derived from teh various address fueklds.
            rec['gclon'] = ''
            rec['gclat'] = ''
            key = '%s, %s, %s, %s' % (rec['address'], rec['city'], rec['state'], rec['zip'])
            if key in geocode_lookup:
                gclon = float(geocode_lookup[key]['lon'])
                gclat = float(geocode_lookup[key]['lat'])
                (gcxx, gcyy) = remap(gclon, gclat)
                (xx, yy) = remap(lon, lat)
                d = np.sqrt((xx - gcxx) ** 2 + (yy - gcyy) ** 2)
                if d < geocode_reloc_threshold:
                    rec['gclon'] = '%.6f' % gclon
                    rec['gclat'] = '%.6f' % gclat
                    reloc_list[biz_id] = {
                        'coords': ([(lon, lat), (gclon, gclat)]),
                        'addr': key}

            # Deal with the business classification.
            sic = rec['psic']
            if sic in sic_to_n17:
                n17 = sic_to_n17[sic]['naics2017']
            else:
                n17 = '0'

            if rec['res_type'] == 'Fast Food':
                n17 = '722513'
            elif rec['res_type'] == 'Coffee/Drinks':
                n17 = '722515'
            elif rec['res_type'] == 'Casual':
                n17 = '722511'

            if n17 in n17_to_sbc:
                rec['bcid'] = n17_to_sbc[n17]['bcid']
                rec['bc1'] = n17_to_sbc[n17]['bc1']
                rec['bc2'] = n17_to_sbc[n17]['bc2']
                rec['bc3'] = n17_to_sbc[n17]['bc3']
                writer.writerow(rec)
            else:
                rec['bcid'] = '99-999-999'
                rec['bc1'] = 'Unknown'
                rec['bc2'] = 'Unknown'
                rec['bc3'] = 'Unknown'
                writer.writerow(rec)

# Make a file indicating how points were moved via geolocation.
oname = '%s/s_relocation.shp' % biz_dir
print('## Making shapefile with relocation information: "%s"' % oname)
crs = '+proj=longlat +ellps=WGS84 +datum=WGS84'
driver = 'ESRI Shapefile'
schema = {'geometry': 'LineString', 'properties': {'id': 'str', 'addr': 'str'}}
import fiona

with fiona.open(oname, 'w', crs=crs, driver=driver, schema=schema) as dest:
    for biz_id in reloc_list:
        feature = {'type': 'Feature',
                   'id': biz_id,
                   'geometry': {'coordinates': reloc_list[biz_id]['coords'], 'type': 'LineString'},
                   'properties': {'id': biz_id, 'addr': reloc_list[biz_id]['addr']}}
        dest.write(feature)


print
