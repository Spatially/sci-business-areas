#
# This function does the clustering of site data, yielding [retail|business|whatever] areas.
#


import csv
from e_smpc import smpc
import os
import fiona


print('# Creating business area clusters from business site locations')


msa_base = os.environ.get('MSA_BASE')
msa_name = os.environ.get('MSA_NAME')
msa_dir = '%s/%s' % (msa_base, msa_name)
ref_dir = '%s/ref' % msa_dir
area_dir = '%s/areas' % msa_dir
biz_dir = '%s/biz' % msa_dir


# Read the list of all sites to be used for business area definition.
print('## Reading list of sites')
site_loc_list = {}  # site locations
site_id_list = []  # site IDs
with open(area_dir + '/ba_site_list.psv') as infile:
    reader = csv.DictReader(infile, delimiter='|')
    for rec in reader:
        sid = rec['siteId']
        lon = float(rec['lon'])
        lat = float(rec['lat'])
        site_id_list.append(sid)
        site_loc_list[sid] = {'xx': float(rec['xx']), 'yy': float(rec['yy']), 'lon': lon, 'lat': lat}


# Get a list of distances to use for the clustering.
fname = area_dir + '/ba_site_distances.psv'
print('## Reading inter-site distances from "%s"' % fname)
site_distance_list = {}  # Inter-site distances.
with open(fname) as infile:
    reader = csv.DictReader(infile, delimiter='|')
    for rec in reader:
        sid0 = rec['siteId0']
        sid1 = rec['siteId1']
        if sid0 < sid1:
            site_distance_list[(sid0, sid1)] = float(rec['distance'])
        else:
            site_distance_list[(sid1, sid0)] = float(rec['distance'])


# Read the list of site attributes.
# Get a list of site attributes. First we peek at the first line of the file to determine which columns contain
# attribute values. We save them and then read only those columns from the file.
fname = area_dir + '/ba_site_attributes.psv'
print('## Reading site attributes from "%s"' % fname)
attr_tag_list = []
with open(fname) as infile:
    reader = csv.reader(infile, delimiter='|')
    tags = reader.next()
    for tag in tags:
        if tag != 'siteId' and tag != 'lon' and tag != 'lat':
            attr_tag_list.append(tag)

site_attr_list = {}  # Site attributes
with open(fname) as infile:
    reader = csv.DictReader(infile, delimiter='|')
    for rec in reader:
        sid = rec['siteId']
        site_attr_list[sid] = {}
        for tag in attr_tag_list:
            site_attr_list[sid][tag] = rec[tag]


#
# Read the clustering parameters and run clustering.
#
print('## Running clustering')
with open('%s/ba_parameters.psv' % area_dir) as infile:
    reader = csv.DictReader(infile, delimiter='|')
    rec = reader.next()
param = {}
param['epsilon'] = float(rec['epsilon'])
param['merge_threshold'] = float(rec['merge_threshold'])
param['max_cluster_size'] = float(rec['max_cluster_size'])
# param = {'epsilon': 300.0, 'merge_threshold': 5.0, 'max_cluster_size': 70}
print('## Parameters: epsilon = %.1f  merge_threshold = %.1f  max_cluster_size = %.0f' % (
    param['epsilon'], param['merge_threshold'], param['max_cluster_size']))
tri_graph, merge_list, labels = smpc(site_id_list, site_loc_list, site_attr_list, site_distance_list, param)


# Write out the list of merges.
print('## Creating a list of merges')
with open(area_dir + '/ba_merges.psv', 'w') as outfile:
    writer = csv.DictWriter(outfile, delimiter='|', fieldnames=['cid0', 'cid1', 'mcid', 'd'])
    writer.writeheader()
    for rec in merge_list:
        writer.writerow({'cid0': rec[0], 'cid1': rec[1], 'mcid': rec[2], 'd': '%.4f' % rec[3]})


# Write out a list of points for display.
print('## Creating a list of points')
with open(area_dir + '/ba_test_points.psv', 'w') as outfile:
    writer = csv.DictWriter(outfile, delimiter='|', fieldnames=['siteId', 'lon', 'lat', 'label'])
    writer.writeheader()
    for sid in site_loc_list:
        writer.writerow({'siteId': sid, 'lon': site_loc_list[sid]['lon'],
                         'lat': site_loc_list[sid]['lat'], 'label': '1'})


# Make shapefiles with triangulation results.
print('## Making shapefiles with triangulation results')
crs = '+proj=longlat +ellps=WGS84 +datum=WGS84'
driver = 'ESRI Shapefile'
schema = {'geometry': 'LineString', 'properties': {'d': 'float'}}
with fiona.open(area_dir + '/s_tri_edges.shp', 'w', crs=crs, driver=driver, schema=schema) as dest:
    for e in tri_graph.edges():
        lon0 = site_loc_list[e[0]]['lon']
        lat0 = site_loc_list[e[0]]['lat']
        lon1 = site_loc_list[e[1]]['lon']
        lat1 = site_loc_list[e[1]]['lat']
        coords = [(lon0, lat0), (lon1, lat1)]
        if e[0] < e[1]:
            d = site_distance_list[(e[0], e[1])]
        else:
            d = site_distance_list[(e[1], e[0])]
        feature = {'type': 'Feature',
                   'id': '1',
                   'geometry': {'coordinates': coords, 'type': 'LineString'},
                   'properties': {'d': d}}
        dest.write(feature)

schema = {'geometry': 'Point', 'properties': {'id': 'str'}}
with fiona.open(area_dir + '/s_tri_nodes.shp', 'w', crs=crs, driver=driver, schema=schema) as dest:
    for nd in tri_graph.nodes():
        lon0 = site_loc_list[nd]['lon']
        lat0 = site_loc_list[nd]['lat']
        coords = (lon0, lat0)
        feature = {'type': 'Feature',
                   'id': nd,
                   'geometry': {'coordinates': coords, 'type': 'Point'},
                   'properties': {'id': nd}}
        dest.write(feature)


# Write out a file containing the cluster label for each site.
with open(area_dir + '/ba_site_list.psv') as infile:
    reader = csv.DictReader(infile, delimiter='|')
    ofname = '%s/ba_clusters.psv' % area_dir
    print('## Writing file with business area cluster labels: "%s"' % ofname)
    with open(ofname, 'w') as outfile:
        fieldnames = ['siteId', 'lon', 'lat', 'label']
        writer = csv.DictWriter(outfile, delimiter='|', fieldnames=fieldnames)
        writer.writeheader()
        for rec in reader:
            writer.writerow({'siteId': rec['siteId'],
                             'lon': rec['lon'],
                             'lat': rec['lat'],
                             'label': labels[rec['siteId']]})


print
