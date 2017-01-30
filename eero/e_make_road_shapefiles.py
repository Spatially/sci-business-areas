#
# this file creates shapefiles containing the vertices and edges of the road network.
#


import shapely.geometry
import networkx as nx
import fiona
import pyproj
import shapely
import csv
import os
from e_utils import get_remap_function


print('# Making shapefiles describing the road network')


msa_base = os.environ.get('MSA_BASE')
msa_name = os.environ.get('MSA_NAME')
msa_dir = '%s/%s' % (msa_base, msa_name)
ref_dir = '%s/ref' % msa_dir
area_dir = '%s/areas' % msa_dir
biz_dir = '%s/biz' % msa_dir
road_dir = '%s/roads' % msa_dir


remap = get_remap_function()


gg = nx.read_graphml('%s/road_network.xml' % road_dir)


crs = '+proj=longlat +ellps=WGS84 +datum=WGS84'
driver = 'ESRI Shapefile'


#
# write a file containing road network vertices;
#
oname = '%s/road_network_vertices.shp' % road_dir
print('## Making shapefile with road network vertices: "%s"' % oname)
schema = {'geometry': 'Point',
          'properties': {'id':'str'}}

with fiona.open(oname, 'w', crs=crs, driver=driver, schema=schema) as dest:
    for v in gg.nodes():
        feature = {'type': 'Feature',
                   'id': v,
                   'geometry': {'coordinates': (gg.node[v]['lon'], gg.node[v]['lat']), 'type': 'Point'},
                   'properties': {'id': v}}
        dest.write(feature)


#
# write a file containing road network edges;
#
oname = '%s/road_network_edges.shp' % road_dir
print('## Making shapefile with road network edges: "%s"' % oname)
schema = {'geometry': 'LineString',
          'properties': {'id': 'str', 'length': 'float', 'road_class': 'str'}}

with fiona.open(oname, 'w', crs=crs, driver=driver, schema=schema) as dest:
    for e in gg.edges():
        n0 = e[0]
        n1 = e[1]
        id = gg.edge[e[0]][e[1]]['id']
        length = gg.edge[e[0]][e[1]]['length']
        road_class = gg.edge[e[0]][e[1]]['road_class']
        coords = [(gg.node[n0]['lon'], gg.node[n0]['lat']), (gg.node[n1]['lon'], gg.node[n1]['lat'])]
        feature = {'type': 'Feature',
                   'id': id,
                   'geometry': {'coordinates': coords, 'type': 'LineString'},
                   'properties': {'id': id, 'length': length, 'road_class': road_class}}
        dest.write(feature)



oname = '%s/road_segments.psv' % road_dir
print('## Making shapefile with road segments: "%s"' % oname)
segmentList = {}
with open(oname) as infile:
    reader = csv.DictReader(infile, delimiter='|')
    for rec in reader:
        eid = rec['edge_id']
        if eid not in segmentList:
            segmentList[eid] = []
        segmentList[eid].append((float(rec['lon']), float(rec['lat'])))


crs = '+proj=longlat +ellps=WGS84 +datum=WGS84'
driver = 'ESRI Shapefile'
schema = {'geometry': 'LineString',
          'properties': {'eid': 'str'}}

with fiona.open('%s/road_segments.shp' % road_dir, 'w', driver=driver, crs=crs, schema=schema) as dest:
    for eid in segmentList:
        feature = {'type': 'Feature',
                   'id': eid,
                   'geometry': {'coordinates': segmentList[eid], 'type': 'LineString'},
                   'properties': {'eid': eid}}
        dest.write(feature)


print