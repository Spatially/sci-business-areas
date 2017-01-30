#
# This script computes the site-to-site road network distances.
#


import networkx as nx
from rote import *
import os
from e_utils import get_remap_function


print('# Getting road network distances between nearby site pairs')


msa_base = os.environ.get('MSA_BASE')
msa_name = os.environ.get('MSA_NAME')
msa_dir = '%s/%s' % (msa_base, msa_name)
ref_dir = '%s/ref' % msa_dir
area_dir = '%s/areas' % msa_dir
biz_dir = '%s/biz' % msa_dir
road_dir = '%s/roads' % msa_dir


# Parameters used below.
distance_cutoff = 1200.0  # maximum distance [meters] for which to report road network distances.
time_cutoff = 1200.0


# Get a function to handle local map projections.
remap = get_remap_function()


# This is the list that we will be filling up here. It will consist of IDs of business pairs
# along with the road network distance between them.
sitePairDistanceList = {}


# Read the road network graph.
fname = '%s/road_network.xml' % road_dir
print('## Reading road network file "%s"' % fname)
gg = nx.read_graphml(fname)


# Add a "time" field to each edge. This will be based on a typical speed for each segement, which in turn depends
# on its road class.
for e in gg.edges():
    e0 = e[0]
    e1 = e[1]
    length = gg.edge[e0][e1]['length']
    road_class = gg.edge[e0][e1]['road_class']

    # Assign road speeds according to road class. Units are nominally meters per second.
    # These aren't really meant to be typical values -- they should just be considered relative
    # to one another. The real purpose of doing this is so that things that are on big roads are
    # in a sense "closer together" than things on smalle roads. For example, two businesses
    # 500 meters apart on a major arterial are effectively "closer together" than are two
    # businesses that are 500 meters apart along residential streets.
    if road_class in ['primary', 'secondary']:
        speed = 1.5
    elif road_class in ['residential']:
        speed = 0.5
    else:
        speed = 1.0

    gg.edge[e0][e1]['time'] = length / speed


# Read the list of sites.
fname = '%s/site_road_info.psv' % biz_dir
print('## Reading site road network info: "%s"' % fname)
siteList = {}
with open(fname) as infile:
    reader = csv.DictReader(infile, delimiter='|')
    for rec in reader:
        siteId = rec['siteId']
        siteList[siteId] = rec


# Below, we will need to get a list of sites on an edge given the edge ID. Here we
# build a lookup table that lets us do that.
print('## Making edge / site lookup')
sitesOnEdge = {}
for siteId in siteList:
    edgeId = siteList[siteId]['segId']
    if edgeId not in sitesOnEdge:
        sitesOnEdge[edgeId] = []
    sitesOnEdge[edgeId].append(siteId)


#
# This is the routine that does all the work. It finds distances from a source site to all
# destination sites within a given threshold distance.
#
# This routine writes its results directly into the "sitePairDistanceList" dictionary.
# Note that entries of that dictionary may get updated over multiple calls to this function.
# That's basically because the distance from A to B may not be the same as the distance from
# B to A due to one way streets. In such cases the minimum distance is retained.
#
def doDistances(sourceNodeId, sourceSiteId, lengthOfFirstPart):

    # Get the shortest path distance to all nodes within some threshold distance.
    # shortestPathLengths = nx.single_source_dijkstra_path_length(gg, sourceNodeId,
    #                                                             cutoff=distance_cutoff, weight='length')
    shortestPathLengths = nx.single_source_dijkstra_path_length(gg, sourceNodeId,
                                                                cutoff=time_cutoff, weight='time')

    # This makes some debugging output, if needed.
    # with open('tmp_localNodes_%s.csv' % sourceNodeId, 'w') as outfile:
    #     writer = csv.DictWriter(outfile, delimiter='|', fieldnames=['id', 'lon', 'lat', 'dist[f]'])
    #     writer.writeheader()
    #     for nid in shortestPathLengths:
    #         writer.writerow({'id': nid, 'lon': gg.node[nid]['lon'], 'lat': gg.node[nid]['lat'],
    #                         'dist[f]': shortestPathLengths[nid]})

    # The two nested loops below together loop over all edges in the local shortest path graph.
    # For each edge, we compute the distance to any business site that lies along it.
    for nid0 in shortestPathLengths:
        distanceToNid0 = shortestPathLengths[nid0]

        for nid1 in gg.edge[nid0]:

            if nid1 not in shortestPathLengths:
                continue

            distanceToNid1 = shortestPathLengths[nid1]

            # At this point, we know that we have found an edge that is part of the local
            # shortest path graph. Skip it if it has no sites on it.
            destEdgeId = '%s-%s' % (nid0, nid1)
            if destEdgeId not in sitesOnEdge:
                continue

            # OK, so this edge has sites on it. For each one, figure out the total distance to
            # the source node, accounting for the distance from the respective endpoints.
            for destSiteId in sitesOnEdge[destEdgeId]:
                destSite = siteList[destSiteId]
                dd0 = lengthOfFirstPart + distanceToNid0 + float(destSite['segAlong'])
                dd1 = lengthOfFirstPart + distanceToNid1 + float(destSite['segLength']) \
                      - float(destSite['segAlong'])
                dd = min(dd0, dd1)

                indexTuple = (min(sourceSiteId, destSiteId), max(sourceSiteId, destSiteId))
                if indexTuple in sitePairDistanceList:
                    sitePairDistanceList[indexTuple] = min(sitePairDistanceList[indexTuple], dd)
                else:
                    sitePairDistanceList[indexTuple] = dd


# Loop over all sites.
k = 0
for sourceSiteId in siteList:

    k += 1
    if k % 1000 == 0:
        print('### Source site %d / %d' % (k, len(siteList)))

    sourceSite = siteList[sourceSiteId]
    sourceEdgeId = sourceSite['segId']
    (sourceNodeId0, sourceNodeId1) = sourceEdgeId.split('-')
    doDistances(sourceNodeId0, sourceSiteId, float(sourceSite['segAlong']))
    doDistances(sourceNodeId1, sourceSiteId, float(sourceSite['segLength'])
                - float(sourceSite['segAlong']))


# A patch: If two businesses are on the same segment, re-compute their distance.
for edgeId in sitesOnEdge:
    siteIdList = sitesOnEdge[edgeId]
    nn = len(siteIdList)
    for ii in range(nn):
        siteId0 = siteIdList[ii]

        for jj in range(ii, nn):
            siteId1 = siteIdList[jj]

            dd = abs(float(siteList[siteId0]['segAlong']) - float(siteList[siteId1]['segAlong']))
            indexTuple = (min(siteId0, siteId1), max(siteId0, siteId1))
            sitePairDistanceList[indexTuple] = dd


# Create the big output file giving inter-site road distances
out_fname = '%s/site_road_distances.psv' % biz_dir
print('## Writing file giving inter-site road distances: "%s"' % out_fname)
with open(out_fname, 'w') as outfile:
    writer = csv.DictWriter(outfile, delimiter='|', fieldnames=['siteId0', 'siteId1', 'distance'])
    writer.writeheader()
    for key in sitePairDistanceList:
        writer.writerow({'siteId0': key[0], 'siteId1': key[1], 'distance': '%.1f' % sitePairDistanceList[key]})


# # Write out the results for a test case, for QA.
# keySiteId = 'site006185'
# with open('%s/results_%s.csv' % (biz_dir, keySiteId), 'w') as outfile:
#     fieldnames = ['siteId', 'dist[f]', 'lon', 'lat']
#     writer = csv.DictWriter(outfile, delimiter='|', fieldnames=fieldnames)
#     writer.writeheader()
#     for key in sitePairDistanceList:
#         if key[0] == keySiteId:
#             outSiteId = key[1]
#         elif key[1] == keySiteId:
#             outSiteId = key[0]
#         else:
#             continue
#         orec = {'siteId': outSiteId, 'dist[f]': sitePairDistanceList[key],
#                 'lon': siteList[outSiteId]['lon'], 'lat': siteList[outSiteId]['lat']}
#         writer.writerow(orec)


print
