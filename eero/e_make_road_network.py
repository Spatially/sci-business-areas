#
# This script assembles a big road network graph from the chunks in a bunch of OSM JSON files.
#

import shapely.geometry
import os
import glob
import networkx as nx
from e_graph_support import graph_from_osm_files
from rtree import index
from e_utils import get_remap_function
import csv


print('# Building road network graph structure')


msa_base = os.environ.get('MSA_BASE')
msa_name = os.environ.get('MSA_NAME')
msa_dir = '%s/%s' % (msa_base, msa_name)
ref_dir = '%s/ref' % msa_dir
area_dir = '%s/areas' % msa_dir
biz_dir = '%s/biz' % msa_dir
road_dir = '%s/roads' % msa_dir


remap = get_remap_function()


# Get the road network graph, and some associated information that we will use below.
fnameList = glob.glob('%s/osm/roads*.json' % road_dir)
gg, nodeList, wayList, edgeList = graph_from_osm_files(fnameList, remap)
nx.write_graphml(gg, '%s/road_network.xml' % road_dir)


# For every edge, find its nodes by referring back to the original way and node list.
print('## Getting nodes for each road segment')
internalNodeList = []
edgeBoxList = {}
k = 0
for edge_id in edgeList:

    # k += 1
    # if k > 1000:
    #     break

    edge = edgeList[edge_id]
    wid = edge['wayId']
    nid0 = edge['v0']
    nid1 = edge['v1']
    way = wayList[wid]
    node_id_list = way['nodes']
    index0 = node_id_list.index(nid0)
    index1 = node_id_list.index(nid1)
    xxMin = None
    xxMax = None
    yyMin = None
    yyMax = None

    if index0 < index1:
        indexList = range(index0, index1 + 1)
    else:
        indexList = range(index0, index1 - 1, -1)
    for ii in indexList:
        node_id = node_id_list[ii]
        lon = float(nodeList[node_id]['lon'])
        lat = float(nodeList[node_id]['lat'])
        (xx, yy) = remap(lon, lat)
        internalNodeList.append({'edge_id': edge_id, 'node_id': node_id, 'lon': lon, 'lat': lat,
                                 'xx': '%.0f' % xx, 'yy': '%.0f' % yy})
        if xxMin is None or xx < xxMin:
            xxMin = xx
        if xxMax is None or xx > xxMax:
            xxMax = xx
        if yyMin is None or yy < yyMin:
            yyMin = yy
        if yyMax is None or yy > yyMax:
            yyMax = yy

    edgeBoxList[edge_id] = (xxMin, yyMin, xxMax, yyMax)


out_fname = '%s/road_segments.psv' % road_dir
print('## Writing road segment CSV file: "%s"' % out_fname)
with open(out_fname, 'w') as outfile:
    fieldnames = ['edge_id', 'node_id', 'lon', 'lat', 'xx', 'yy']
    writer = csv.DictWriter(outfile, delimiter='|', fieldnames=fieldnames)
    writer.writeheader()
    for rec in internalNodeList:
        writer.writerow(rec)


# Make a file that contains some extra info about road edges, i.e. their typical speeds and
# road class.
out_fname = '%s/road_edges.psv' % road_dir
print('## Writing file with information about road network edges: "%s"' % out_fname)
with open(out_fname, 'w') as outfile:
    writer = csv.DictWriter(outfile, delimiter='|', fieldnames=['edge_id', 'road_class', 'length'])
    writer.writeheader()
    for edge_id in edgeList:
        writer.writerow({'edge_id': edge_id, 'road_class': edgeList[edge_id]['road_class'],
                         'length': edgeList[edge_id]['length']})


# Create an index for the road segments.
out_fname = '%s/road_segments' % road_dir
print('## Building spatial index for road segments: "%s"' % out_fname)
try:
    os.remove('%s/road_segments.dat' % road_dir)
    os.remove('%s/road_segments.idx' % road_dir)
except OSError:
    pass
idx = index.Rtree(out_fname)
for edge_id in edgeBoxList:
    idx.insert(0, edgeBoxList[edge_id], obj=edge_id)
idx.close()


print
