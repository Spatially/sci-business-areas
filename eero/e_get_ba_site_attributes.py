#
# This function gets a bunch of attributes for the sites to be used for area definition.
#


import shapely.geometry
import fiona
import numpy as np
import csv
import os
from e_utils import psvin


print('# Getting attributes for sites to be used for area definition')


msa_base = os.environ.get('MSA_BASE')
msa_name = os.environ.get('MSA_NAME')
msa_dir = '%s/%s' % (msa_base, msa_name)
ref_dir = '%s/ref' % msa_base
area_dir = '%s/areas' % msa_dir
biz_dir = '%s/biz' % msa_dir
road_dir = '%s/roads' % msa_dir


# Parameters used below.
range_parameter = 200.0  # For kernel density computation.
distance_cutoff = 500.0


# Read the lookup table that maps business IDs into site IDs.
ifname = biz_dir + '/biz_site_lookup.psv'
print('## Reading business-to-site lookup table: "%s"' % ifname)
biz_site_lookup = {}
with open(ifname) as infile:
    reader = csv.DictReader(infile, delimiter='|')
    for rec in reader:
        biz_id = rec['bizId']
        site_id = rec['siteId']
        biz_site_lookup[biz_id] = site_id


# Get a list of all businesses. Use the version that has category labels, since a lot of the processing below
# bases the attributes of a site on the local business types.
ifname = biz_dir + '/biz_list.psv'
print('## Reading list of all businesses with category labels: "%s"' % ifname)
biz_list = {}
with open(ifname) as infile:
    reader = csv.DictReader(infile, delimiter='|')
    for rec in reader:
        biz_id = rec['pid']
        site_id = biz_site_lookup[biz_id]
        biz_list[biz_id] = {'siteId': site_id, 'chainid': rec['chainid'], 'bcid': rec['bcid']}


# Get the list of "ba" sites -- i.e. those being used for business area definition.
print('## Initializing list of business area site attributes')
ba_site_attrs = {}
with open(area_dir + '/ba_site_list.psv') as infile:
    reader = csv.DictReader(infile, delimiter='|')
    for rec in reader:
        site_id = rec['siteId']
        ba_site_attrs[site_id] = {'siteId': site_id, 'lon': rec['lon'], 'lat': rec['lat']}


# Read the list of site-to-site distances.
fname = biz_dir + '/site_road_distances_scaled.psv'
print('## Reading site-to-site distance lookup table: "%s"' % fname)
distance_lookup = {}
nearby_list = {}
with open(fname) as infile:
    reader = csv.DictReader(infile, delimiter='|')
    for rec in reader:
        sid0 = rec['siteId0']
        sid1 = rec['siteId1']
        road_distance = float(rec['distance'])
        if road_distance < distance_cutoff:

            distance_lookup[(sid0, sid1)] = road_distance

            if sid0 not in nearby_list:
                nearby_list[sid0] = []
            nearby_list[sid0].append(sid1)

            if sid1 not in nearby_list:
                nearby_list[sid1] = []
            nearby_list[sid1].append(sid0)


# Read the file defining local site density.
site_density = {}
fname = biz_dir + '/site_density.psv'
with open(fname) as source:
    reader = csv.DictReader(source, delimiter='|')
    for rec in reader:
        site_density[rec['siteId']] = float(rec['density'])


# Read the lookup table defining business category semantics.
ifname = ref_dir + '/sbc/sbc_semantics.psv'
print('## Reading business category semantics lookup: "%s"' % ifname)
biz_cat_semantics = psvin(ifname, key='bcid')


# Here is a kernel density function.
def kd_gaussian(dd, ss):
    vv = np.exp(-(dd * dd) / (2.0 * ss ** 2))
    return vv


# #
# # This function gets an attribute for all sites.
# # The input 'attr_name' refers to a column of the table "biz_cat_semantics".
# #
# def add_attribute(attr_name, kd_function, kd_param):
#
#     print('## Computing attribute "%s"' % attr_name)
#
#     # Initialize this attribute for all BA sites.
#     for site_id in ba_site_attrs:
#         ba_site_attrs[site_id][attr_name] = 0.0
#
#     # Here's what the block below does.
#     # for each business:
#     #     if this business has the property of interest:
#     #         get the site id for this business
#     #         for all ba sites near this business:
#     #             get the distance between the two
#     #             increment the kernel density for the ba site, using that distance
#     for biz_id in biz_list:
#
#         bcid = biz_list[biz_id]['bcid']
#         if bcid not in biz_cat_semantics:
#             # If all is well, this won't happen. Just print an warning message.
#             print('*** Warning: no known semantics for business caegory ID "%s"' % bcid)
#             continue
#
#         if biz_cat_semantics[bcid][attr_name] == '1':
#
#             biz_site_id = biz_site_lookup[biz_id]
#
#             # The following condition happens for business sites that have nothing nearby. In those cases,
#             # the business site would not contribute to any other site's kernel density anyway, so we can safely
#             # skip the rest of the loop.
#             if biz_site_id not in nearby_list:
#                 continue
#
#             for target_site_id in nearby_list[biz_site_id]:
#                 if target_site_id in ba_site_attrs:
#
#                     # Get the distance between that business site and this target site. Note that these distances
#                     # are indexed by a tuple in which the lexically smaller index comes first. Also note that the
#                     # distance lookup doesn't give the distance between a site and itself (i.e. zero), but we
#                     # need to include that case here.
#                     if biz_site_id == target_site_id:
#                         dd = 0.0
#                     else:
#                         if biz_site_id < target_site_id:
#                             index = (biz_site_id, target_site_id)
#                         else:
#                             index = (target_site_id, biz_site_id)
#                         dd = distance_lookup[index]
#
#                     # Increment the attribute value for this target site by the value of the given
#                     # kernel density function.
#                     v = kd_function(dd, kd_param)
#                     ba_site_attrs[target_site_id][attr_name] += v
#
#
# #  Define a bunch of attributes.
# attr_name_list = ['adef', 'blucol', 'whtcol', 'conv', 'dest', 'fsr', 'lsr', 'bar', 'hotel', 'artsy', 'eds', 'meds', 'gov']
# for attr_name in attr_name_list:
#     add_attribute(attr_name, kd_gaussian, range_parameter)



#
# Here, "filter" is a function that takes a business record as input, and returns True if that business is to be
# used to compute the named attribute.
#
def add_attribute(attr_name, filter, kd_function, kd_param):

    print('## Computing attribute "%s"' % attr_name)

    # Initialize this attribute for all BA sites.
    for site_id in ba_site_attrs:
        ba_site_attrs[site_id][attr_name] = 0.0

    # Here's what the block below does.
    # for each business:
    #     if this business has the property of interest:
    #         get the site id for this business
    #         for all ba sites near this business:
    #             get the distance between the two
    #             increment the kernel density for the ba site, using that distance
    for biz_id in biz_list:

        # This is where we apply the filter function.
        if filter(biz_list[biz_id]):

            biz_site_id = biz_site_lookup[biz_id]

            # The following condition happens for business sites that have nothing nearby. In those cases,
            # the business site would not contribute to any other site's kernel density anyway, so we can safely
            # skip the rest of the loop.
            if biz_site_id not in nearby_list:
                continue

            for target_site_id in nearby_list[biz_site_id]:
                if target_site_id in ba_site_attrs:

                    # Get the distance between that business site and this target site. Note that these distances
                    # are indexed by a tuple in which the lexically smaller index comes first. Also note that the
                    # distance lookup doesn't give the distance between a site and itself (i.e. zero), but we
                    # need to include that case here.
                    if biz_site_id == target_site_id:
                        dd = 0.0
                    else:
                        if biz_site_id < target_site_id:
                            index = (biz_site_id, target_site_id)
                        else:
                            index = (target_site_id, biz_site_id)
                        dd = distance_lookup[index]

                    # Increment the attribute value for this target site by the value of the given
                    # kernel density function.
                    v = kd_function(dd, kd_param)
                    ba_site_attrs[target_site_id][attr_name] += v



#  Define a bunch of attributes. The first bunch are all computed in essentially the same way -- by looking at the
# SBC label for each business and checking for a corresponding attribute in the business category semantics list.
# That's essentially what's happeing in this (slightly cryptic) loop.
attr_name_list = ['adef', 'blucol', 'whtcol', 'conv', 'dest', 'fsr', 'lsr', 'bar', 'hotel', 'artsy', 'eds', 'meds', 'gov']
for attr_name in attr_name_list:
    add_attribute(attr_name, lambda bz: biz_cat_semantics[bz['bcid']][attr_name] == '1',
                  kd_gaussian, range_parameter)


# This attribute relates to the density of retail/restaurant/service businesses that are parts of chains.
add_attribute('chain', lambda bz: bz['chainid'] != '0', kd_gaussian, range_parameter)
attr_name_list.append('chain')



# We now have the attribute values stored in 'ba_site_attrs'. Scale them.
for attr_name in attr_name_list:

    # Normalize every attribute by the overall density.
    for site_id in ba_site_attrs:
        ba_site_attrs[site_id][attr_name] = ba_site_attrs[site_id][attr_name] / site_density[site_id]

    # Scale the distribution of attribute values to the range [0 1], using an exponential remapping.
    nr = len(ba_site_attrs)
    d = np.zeros(nr)
    i = 0
    for k in ba_site_attrs:
        d[i] = ba_site_attrs[k][attr_name]
        i += 1
    f = np.percentile(d, 90.0)
    for site_id in ba_site_attrs:
        v = ba_site_attrs[site_id][attr_name]
        ba_site_attrs[site_id][attr_name] = '%.4f' % (1.0 - np.exp(-1.0 * v / f))


# Make the output file.
ofname = area_dir + '/ba_site_attributes.psv'
print('## Writing output file "%s"' % ofname)
with open(ofname, 'w') as outfile:
    fieldnames = ['siteId', 'lon', 'lat'] + attr_name_list
    writer = csv.DictWriter(outfile, delimiter='|', fieldnames=fieldnames)
    writer.writeheader()
    for site_id in sorted(ba_site_attrs.keys()):
        writer.writerow(ba_site_attrs[site_id])


# For debug / visualization purposes, make a shapefile that contains all the attribute values for each point.
oname = '%s/s_ba_site_attributes.shp' % area_dir
print('## Making shapefile with attributes: "%s"' % oname)
crs = '+proj=longlat +ellps=WGS84 +datum=WGS84'
driver = 'ESRI Shapefile'
schema = {'geometry': 'Point', 'properties': {}}
for attr_name in attr_name_list:
    schema['properties'][attr_name] = 'float'

with fiona.open(oname, 'w', crs=crs, driver=driver, schema=schema) as dest:
    for site_id in sorted(ba_site_attrs.keys()):
        props = {}
        for attr_name in attr_name_list:
            props[attr_name] = float(ba_site_attrs[site_id][attr_name])
        lon = float(ba_site_attrs[site_id]['lon'])
        lat = float(ba_site_attrs[site_id]['lat'])
        feature = {'type': 'Feature',
                   'id': site_id,
                   'geometry': {'coordinates': (lon, lat), 'type': 'Point'},
                   'properties': props}
        dest.write(feature)


print

