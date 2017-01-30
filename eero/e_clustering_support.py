#
# This file contains functions that do clustering in a couple of different ways.
#

# from scipy.sparse import csc_matrix
# import csv
# from matplotlib.pyplot import *
#
#
import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sklearn.cluster import ward_tree
from sklearn.cluster import DBSCAN
from sklearn.neighbors import kneighbors_graph
from scipy.sparse import coo_matrix
from scipy.sparse import csc_matrix
from scipy.sparse import find
from scipy.spatial import Delaunay
from scipy.cluster.hierarchy import dendrogram
import matplotlib.pyplot as pyplot
import matplotlib.colors as colors
import matplotlib.cm as cm


def cluster_all(site_list, attr_list, distance_list, param):
    """
    This function does an end-to-end clustering of sites into business areas.

    :param site_list: List of sites to be clustered
    :param attr_list: Site attributes. If None, then clustering phase 2 is skipped.
    :param distance_list: Inter-site distances
    :param param: Dictionary containing all required parameters
    :return: Looking table assigning area labels for site IDs
    """

    #
    # Do clustering phase 1, which is the distance=based clustering using DBSCAN.
    #

    site_id_list = site_list.keys()
    label_for_site = site_clusters_1(site_id_list, distance_list,
                                     epsilon=param['epsilon'],
                                     samples=param['samples'])

    # If we didn't pass in a list of site attributes, we can't do phase 2. So just return what
    # we have at this point.
    if attr_list is None:
        print('Skipping clustering phase 2.')
        return label_for_site

    #
    # Phase 2: sub-divide the clusters that we got in phase 1 based on their attribute values.
    #

    # Get the tags for all of the attributes that we will be using.
    attr_tag_list = attr_list[attr_list.keys()[0]].keys()

    # First establish a mapping between the phase-1 labels and the sites that they contain. This is a thing
    # that is indexed by the "area ID" (i.e. the phase 1 label) and whose contents are a list of the
    # site ID values in that area.
    sites_in_area = {}
    for site_id in label_for_site:
        area_id = label_for_site[site_id]
        if area_id not in sites_in_area:
            sites_in_area[area_id] = []
        sites_in_area[area_id].append(site_id)

    # Now we loop over the phase-1 areas -- i.e. the indices of the "sites_in_area" that we
    # just defined.
    area_number = 0
    for area_id in sites_in_area:

        # Sites with a phase-1 label of '-1' are actually "unclassified". So we don't want to
        # subdivide them.
        if area_id == -1:
            continue

        area_number += 1
        sites_in_this_area = sorted(sites_in_area[area_id])
        site_count = len(sites_in_this_area)
        if site_count > 3000:
            print('#### Info: Large cluster [%d]: %d sites' % (area_id, site_count))

        # If this area ia small enough, don't bother trying to subdivide it.
        if site_count < 20:
            continue

        # Get matrices with attribute values and locations.
        loc = np.zeros((site_count, 2))
        attr = np.zeros((site_count, len(attr_tag_list)))
        ix = 0
        for siteId in sites_in_this_area:

            loc[ix, 0] = site_list[siteId]['xx']
            loc[ix, 1] = site_list[siteId]['yy']

            for z in range(len(attr_tag_list)):
                attr[ix, z] = float(attr_list[siteId][attr_tag_list[z]])

            ix += 1

        # Make a connectivity matrix for the sites.
        conn = get_site_connectivity(loc, show=False, distanceThresh=400.0)

        # Get the labels of component clusters.
        labels = subdivide(attr, conn, show=False,
                           maxClusterSize=param['max_cluster_size'],
                           mergeThreshold=param['merge_threshold'])

        # Apply these labels to these sites. We over-write the existing label with a value derived from the
        # labels from the phase-1 and phase-2 clusterings.
        for z in range(site_count):
            sid = sites_in_this_area[z]
            tmp = label_for_site[sid]
            label_for_site[sid] = '%s-%d' % (tmp, labels[z])

    return label_for_site


def subdivide(attr, connectivity, minClusterSize=5, maxClusterSize=100, mergeThreshold=1.0, show=False):
    """
    Does a clustering of some number of samples based on attribute values and connectivity. This is built on
    top of 'sklearn' and 'scipy' routines that do hierarchical agglomerative clustering. This routne
    just provides some knobs to control custer sizes.

    :param attr: matrix of attribute values; rows are samples; columns are attributes

    :param connectivity: a scipy sparse entity connectivity matrix; elements correspond to the
    rows of 'attr'; non-zero values imply connection -- i.e. that the two corresponding
    sampels are eligible to be merged during the clustering process

    :param minClusterSize: try to make cluster sizes at least this big; not a strict limit, as there may
    be no clusters sufficiety close together to assure that this size limit is satisfied;

    :param maxMergeDistance: try to only merge clusters closer than this; not a strict limit, as clusters may still
    merge if they are too small to stand on their own (i.e. if their size is less than 'minClusterSize')

    :param maxMergeFactor: if maxMergeDistance is None, then use this to compute it from the distance range

    :param show: boolean: controls showing of debug info and plots

    :return: an array of labels; elements of the array correspond to rows of 'attr'; values are integers
    starting at 1 and going up to the number of clusters;

    """

    # Get the number of samples -- i.e. the number entities being clustered.
    nSamples = attr.shape[0]

    # Run the routine that determines the constrained merges.
    (children, n_components, n_leaves, parents, distances) = \
        ward_tree(attr, connectivity=connectivity, return_distance=True)

    if show:
        # Initialize clusters.
        clusters = {}
        for i in range(nSamples):
            clusters[i] = set()
            clusters[i].add(i)

        # Assemble a linkage matrix like the one used by the 'dendrogram' routine.
        nr = children.shape[0]
        lm = np.zeros((nr, 4))
        cidx = nSamples
        for i in range(nr):
            cid1 = children[i, 0]
            cid2 = children[i, 1]
            icd = distances[i] # inter-cluster distance
            clusters[cidx] = clusters[cid1].union(clusters[cid2])
            nx = len(clusters[cidx])
            cidx += 1
            lm[i] = [cid1, cid2, icd, nx]

        # Make a dendrogram plot.
        pyplot.figure(11, figsize=(25, 10))
        pyplot.title('Hierarchical Clustering Dendrogram')
        pyplot.xlabel('sample index')
        pyplot.ylabel('distance')
        dendrogram(lm, leaf_rotation=90., leaf_font_size=8)
        pyplot.show()

    # A function to convert a cluster into a string.
    def clusterString(s):
        r = '[%3d] {%s}' % (len(s), ','.join(['%s' %x for x in sorted(s)]))
        return r

    # Initialize the table of clusters.
    clusters = {}
    for i in range(nSamples):
        clusters[i] = set()
        clusters[i].add(i)

    nr = children.shape[0]
    cidx = nSamples
    for i in range(nr):
        cid1 = children[i, 0]
        cid2 = children[i, 1]
        icd = distances[i]

        if show:
            print('proposed merge: [%.2f] %d + %d -> %d' % (icd, cid1, cid2, cidx))

        if cid1 in clusters and cid2 in clusters:
            n1 = len(clusters[cid1])
            n2 = len(clusters[cid2])
            if (icd < mergeThreshold and n1 + n2 < maxClusterSize) or n1 < minClusterSize or n2 < minClusterSize:
                if show:
                    print('merging: [%.2f] %s + %s' % (icd, clusterString(clusters[cid1]), clusterString(clusters[cid2])))
                clusters[cidx] = clusters[cid1].union(clusters[cid2])
                del clusters[cid1]
                del clusters[cid2]
            else:
                if show:
                    print('rejected: dist=%.2f  size1=%d  size2=%d' % (icd, len(clusters[cid1]), len(clusters[cid2])))
        else:
            if show:
                print('rejected: %d=%d  %d=%d' % (cid1, cid1 in clusters, cid2, cid2 in clusters))

        cidx += 1

    if show:
        print('final clusters:')
        for cid in clusters:
            print('%s' % clusterString(clusters[cid]))

    # Set the final labels.
    labels = np.zeros(nSamples, dtype=np.int)
    clusterLabel = 0
    for cid in clusters:
        clusterLabel += 1
        for ix in clusters[cid]:
            labels[ix] = clusterLabel

    return(labels)


def get_site_connectivity(loc, distanceThresh=None, show=False):
    '''
    Gets a matrix indicating site connecivity for the purpose of site subdivision. That is, the
    subdivision of clusters into sub-clusters will respect the connectivity constraints contained in the
    matrix computed here.

    :param loc:
    :param distanceThresh:
    :param show:
    :return:
    '''

    use_knn = False
    if use_knn:
        # Create a connectivity matrix using a nearest-neighbors graph.
        connectivity = kneighbors_graph(loc, 4, include_self=False)

    else:

        if distanceThresh is None:
            distanceThresh = 99999.9

        pointCount = loc.shape[0]

        # Create a connectivity matrix based on a Delaunay triangulation.
        tri = Delaunay(loc)
        simp = tri.simplices
        triCount = simp.shape[0]
        edge_set = set()

        for i in range(triCount):

            ix0 = simp[i, 0]
            ix1 = simp[i, 1]
            ix2 = simp[i, 2]

            x0 = loc[ix0, 0]
            y0 = loc[ix0, 1]
            x1 = loc[ix1, 0]
            y1 = loc[ix1, 1]
            x2 = loc[ix2, 0]
            y2 = loc[ix2, 1]

            s01 = np.sqrt((x1-x0)**2 + (y1-y0)**2)
            s12 = np.sqrt((x2-x1)**2 + (y2-y1)**2)
            s20 = np.sqrt((x0-x2)**2 + (y0-y2)**2)

            thresh = 1.01

            if s01 < (s12 + s20) * thresh and s01 < distanceThresh:
                edge_set.add((ix0, ix1))
                edge_set.add((ix1, ix0))

            if s12 < (s20 + s01) * thresh and s12 < distanceThresh:
                edge_set.add((ix1, ix2))
                edge_set.add((ix2, ix1))

            if s20 < (s01 + s12) * thresh and s20 < distanceThresh:
                edge_set.add((ix2, ix0))
                edge_set.add((ix0, ix2))

        row_index = []
        col_index = []
        val = []
        for e in edge_set:
            row_index.append(e[0])
            col_index.append(e[1])
            val.append(1.0)

        connectivity = coo_matrix((val, (row_index, col_index)), shape=(pointCount, pointCount))

    if show:
        (rr, cc, vv) = find(connectivity)
        pyplot.figure(12)
        pyplot.clf()
        pyplot.hold(True)
        for i in range(len(rr)):
            i0 = rr[i]
            i1 = cc[i]
            pyplot.plot([loc[i0, 0], loc[i1, 0]], [loc[i0, 1], loc[i1, 1]], 'k-')
            pyplot.plot([loc[i0, 0]], [loc[i0, 1]], 'r.')
            pyplot.plot([loc[i1, 0]], [loc[i1, 1]], 'r.')

    return connectivity


def site_clusters_1(site_id_list, distance_lookup, epsilon=100.0, samples=3):
    """

    :param site_id_list:
    :param distance_lookup:
    :param epsilon:
    :param samples:
    :return:
    """

    # Get a lookup table that maps site IDs to index values.
    site_count = len(site_id_list)
    site_index_lookup = {}
    for i in range(site_count):
        site_index_lookup[site_id_list[i]] = i

    # Assemble the (sparse) matrix of distance values to be used in the 'dbscan' routine.
    distance_values = []
    distance_row_index = []
    distance_col_index = []
    for i in range(len(distance_lookup)):
        rec = distance_lookup[i]
        index0 = site_index_lookup[rec['siteId0']]
        index1 = site_index_lookup[rec['siteId1']]
        distance_values.append(rec['distance'])
        distance_row_index.append(index0)
        distance_col_index.append(index1)
        distance_values.append(rec['distance'])
        distance_row_index.append(index1)
        distance_col_index.append(index0)
    x = csc_matrix((distance_values, (distance_row_index, distance_col_index)), shape=(site_count, site_count))

    # Find the clusters.
    model = DBSCAN(eps=epsilon, min_samples=int(samples), metric='precomputed')
    labels = model.fit_predict(x)

    # Get a thing that maps site IDs to their labels.
    site_label_lookup = {}
    for site_id in site_index_lookup:
        ix = site_index_lookup[site_id]
        site_label_lookup[site_id] = labels[ix]

    # All done.
    return site_label_lookup


