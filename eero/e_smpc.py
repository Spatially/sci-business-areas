#
# SMPC: Spatially Multi-Phase Clustering
#
# This file contains code that implements the Spatially multi-phase clustering algorithm.
# This algorithm finds clusters in a set of points representing business locations. A rough outline is:
#
# 1. Do a Delaunay triangulation of a set of business sites.
# 2. Remove edges with a length greater than some given "distance" threshold.
# 3. For each connected component in the resulting graph:
# 3a. Do a hierarchical agglomerative clustering of the points in this component, using the Delaunay edges as
#     connectivity constraints.
# 4. Merge the dendrograms of all components from (3).
#
# The output is the merged dendrogram from (4). This is a data structure that can be used to define clusters with
# variable levels of fragmentation by specifying a threshold on inter-custer distance.
#

# from scipy.sparse import csc_matrix
# import csv
# from matplotlib.pyplot import *
#
#
import numpy as np
from sklearn.cluster import ward_tree
from scipy.spatial import Delaunay
import networkx as nx


def smpc(id_list, loc_list, attr_list, distance_list, param):
    """
    This function does an end-to-end clustering of sites into business areas.

    :param id_list: IDs of sites to be clustered
    :param loc_list: Locations of sites to be clustered
    :param attr_list: Attributes of sites to be clustered.
    :param distance_list: Inter-site distances
    :param param: Dictionary containing all required parameters
    :return: Looking table assigning area labels for site IDs
    """

    # Get a graph representing triangulation results.
    tri_graph = get_tri_graph(id_list, loc_list, distance_list, param['epsilon'])

    # Get a list of all the merges that need to happen.
    merge_list = get_merge_list(id_list, attr_list, tri_graph)

    # Get the final labels using the merge list.
    labels = get_labels(merge_list, param['merge_threshold'], param['max_cluster_size'])

    return tri_graph, merge_list, labels


def get_tri_graph(id_list, loc_list, distance_list, epsilon):
    """
    Gets a pruned triangulation graph giving a top-level view of the connectivity among the
    input points. Basically we start with a Delaunay triangulation, then remove edges whose "distance"
    metric (according to the input "distance_list") is below some threshold.

    :param id_list:
    :param loc_list:
    :param distance_list:
    :param epsilon:
    :return:
    """

    # Below we will need to convert between array indices and site IDs. The input "id_list" gives
    # us an ID given an index. Here we create a lookup that goes the other way.
    id_lookup = id_list
    index_lookup = {}
    for i in range(len(id_list)):
        index_lookup[id_list[i]] = i

    # Get a matrix of (x,y) locations to serve as input to the Delaunay triangulation.
    nn = len(id_list)
    loc = np.zeros((nn, 2))
    for id in id_list:
        ix = index_lookup[id]
        loc[ix, 0] = loc_list[id]['xx']
        loc[ix, 1] = loc_list[id]['yy']

    # Do the triangulation.
    tri = Delaunay(loc)

    # Build a list of edges to tbe added to the graph.
    edge_set = set()
    simps = tri.simplices
    tri_count = simps.shape[0]

    def order(a, b):
        if a < b:
            return a, b
        else:
            return b, a

    for i in range(tri_count):

        id0 = id_lookup[simps[i, 0]]
        id1 = id_lookup[simps[i, 1]]
        id2 = id_lookup[simps[i, 2]]

        # For each side of this simplex, check its distance.
        oo = order(id0, id1)
        if oo in distance_list and distance_list[oo] < epsilon:
            edge_set.add(oo)

        oo = order(id1, id2)
        if oo in distance_list and distance_list[oo] < epsilon:
            edge_set.add(oo)

        oo = order(id2, id0)
        if oo in distance_list and distance_list[oo] < epsilon:
            edge_set.add(oo)

    # Make a "networkx" graph representing the results.
    gg = nx.Graph()
    gg.add_nodes_from(id_list)
    gg.add_edges_from(edge_set)

    return gg


def get_merge_list(id_list, attr_list, tri_graph):
    """
    Gets a list of hierarchical merges that can be used to produce clusters at any given level
    of granularity.

    :param id_list:
    :param attr_list:
    :param tri_graph:
    :param param:
    :return:
    """

    # Below we will need a list of keys for the attributes that we are using.
    attr_key_list = attr_list[attr_list.keys()[0]].keys()
    attr_count = len(attr_key_list)

    # Get the connected component sub-graphs.
    components = list(nx.connected_component_subgraphs(tri_graph))
    for i in range(len(components)):
        nc = len(components[i].nodes())
        ec = len(components[i].edges())

    # Initialize the list of merges. Each record of this list will indicate a merge between a pair
    # of clusters and the inter-cluster distance of that merge. Initialize it with the singleton clusters --
    # i.e. each site as an individual cluster.
    merge_list = []
    for id in id_list:
        merge_list.append((id, '0', id, 0.0))

    # We need to make sure that cluster IDs are distinct across the different components. This is
    # a variable that helps us keep track of that.
    cluster_id_ticker = 0

    # Loop over sub-graphs.
    for component in components:

        # This keeps track of the cluster IDs generated within this loop.
        local_cluster_id_list = []

        # If we only have one node in this component, there is nothing to be done.
        nn = len(component.nodes())
        if nn == 1:
            continue

        # Get a connectivity matrix for this component.
        node_list = component.nodes()
        conn = nx.to_scipy_sparse_matrix(component, node_list)

        # Assemble the attribute matrix for this component. Note that we are taking care to
        # order the array of attributes so that each row corresponds to the correct row/column
        # index in the sparse matrix that we just created. "node_list" is the variable
        # that ties the two together. If we didn't do this, the results would be nonsense.
        node_count = len(node_list)
        attr = np.zeros((node_count, attr_count))
        node_index = 0
        for node in node_list:
            for attr_index in range(attr_count):
                attr[node_index, attr_index] = float(attr_list[node][attr_key_list[attr_index]])
            node_index += 1

        # Get the dendrogram representing how to aggregate the points of this component.
        (pairs, n_components, n_leaves, parents, distances) = \
            ward_tree(attr, connectivity=conn, return_distance=True)

        # Merge the dendrogram with the big overall dendrogram.
        pair_count = len(distances)
        for i in range(pair_count):

            # Here we deal with the conventions that 'sklearn' uses to represent dendrograms
            # from clustering routines.

            ix0 = pairs[i][0]
            if ix0 < nn:
                cid0 = node_list[ix0]
            else:
                cid0 = local_cluster_id_list[ix0 - nn]

            ix1 = pairs[i][1]
            if ix1 < nn:
                cid1 = node_list[ix1]
            else:
                cid1 = local_cluster_id_list[ix1 - nn]

            # Get an ID for the new cluster. I'm prefixing these with the letter "m" (for "merged")
            # because otherwise we would have name clashes with the site labels.
            cluster_id_ticker += 1
            new_cid = 'm%d' % cluster_id_ticker
            local_cluster_id_list.append(new_cid)

            # Add the information about this merge to the big list of all merges.
            merge_list.append((cid0, cid1, new_cid, distances[i]))

    return merge_list


def get_labels(merge_list, merge_threshold, max_cluster_size):
    """
    Apply the parameters to the list of possible merges, yielding a set of final cluster labels.

    :param merge_list:
    :param merge_threshold:
    :param max_cluster_size:
    :return:
    """

    clusters = {}
    for rec in merge_list:
        cid0 = rec[0]
        cid1 = rec[1]
        cidx = rec[2]
        dd = rec[3]

        if dd < merge_threshold:
            # The convention used in the list of merges is that if a record specifies "0" as
            # the second cluster ID, then this record really just represents a singleton -- i.e.
            # one site as a cluster on its own. So here we just insert it into the cluster
            # list as such.
            if cid1 == "0":
                clusters[cidx] = [cid0]
            else:
                # It is possible that the specified clusters are not in the list, for example if
                # an earlier merge was disallowed because the resulting cluster would have been
                # too large. In such cases there is nothing to do.
                if cid0 in clusters and cid1 in clusters:

                    # Only allow this merge if the resulting cluster will not be too big.
                    if len(clusters[cid0]) + len(clusters[cid1]) <= max_cluster_size:
                        clusters[cidx] = clusters[cid0] + clusters[cid1]
                        del clusters[cid0]
                        del clusters[cid1]

    # Unroll the list of clusters into a label lookup. While we're at it, re-set the cluster labels to be
    # a sequence of integers starting at 1.  Makes life easier.
    labels = {}
    cluster_id_ticker = 0
    for cid in clusters:
        cluster_id_ticker += 1
        for z in clusters[cid]:
            labels[z] = cluster_id_ticker

    return labels