#
# This file contains support routines for doing GIS-type stuff.
#


import shapely.geometry
import shapely.ops
from scipy.spatial import Voronoi
from copy import copy


# This function sub-divides a shape based on a Voronoi tesselation of a set of points.  The points need not be
# inside the shape.
def vpsplit(s0, p0, l0):

    vp = copy(p0)
    vp.append((-10000000, -10000000))
    vp.append((+10000000, -10000000))
    vp.append((+10000000, +10000000))
    vp.append((-10000000, +10000000))
    vor = Voronoi(vp)

    # Get a list of polygons representing the intersection of the Voronoi tesselation with the
    # original polygon ("s").
    vp_list = []
    for index in range(len(p0)):
        label = l0[index]
        z = vor.point_region[index]
        vertex_index_list = vor.regions[z]
        vp_coords = [(vor.vertices[ix][0], vor.vertices[ix][1]) for ix in vertex_index_list]
        # print('label %s: ' % label)
        # print('vertex index list: ', vertex_index_list)
        # print('coords', vp_coords)
        pp = shapely.geometry.Polygon(vp_coords)
        px = pp.intersection(s0)
        # print(pp)
        # print(px)
        vp_list.append({'shape': px, 'label': label})

    return vp_list


def outer_ring(ss):
    mm = shapely.geometry.mapping(ss)
    cc = mm['coordinates']
    if mm['type'] == 'Polygon':
        ring = shapely.geometry.Polygon(cc[0])
    else:
        print('Un-handled geometry type: "%s"' % mm['type'])
    return ring


def poly_merge(s0, label):
    """
    Adapted from the original R version (below) by Sebastian Santibanez.

    The input is a multipolygon, The output is a "merged" version having an envelope that
    approximately follows the outer contours of the input multipolygon.

    :param s0:
    :return:
    """
    if s0.geom_type == 'Polygon':
        return s0
    ff = copy(s0)
    try:
        nc = len(s0.geoms)
        buffer_size = 100.0

        while ff.geom_type == 'MultiPolygon' and len(ff.geoms) > 1 and buffer_size <= 500.0:
            tmp0 = copy(s0)
            tmp1 = tmp0.buffer(+buffer_size)
            tmp2 = tmp1.buffer(-buffer_size)
            ff = shapely.ops.cascaded_union((tmp2, s0))
            buffer_size += 50.0
    except ValueError:
        print('!!! Error in poly_merge')
    return ff


def ortho_merge(s0, label):
    """
    Adapted from the original R version (below) by Sebastian Santibanez.

    The input is a multipolygon, The output is a "merged" version having an envelope that
    approximately follows the outer contours of the input multipolygon.

    :param s0:
    :return:
    """
    if s0.geom_type == 'Polygon':
        return s0

    ff = copy(s0)

    try:
        #print('### Input multipolygon has %d components' % len(s0.geoms))
        nc = len(s0.geoms)
        buffer_size = 50.0

        while ff.geom_type == 'MultiPolygon' and len(ff.geoms) > 1 and buffer_size < 501.0:
            #print('  running with buffer size %.1f' % buffer_size)
            tmp0 = copy(s0)
            tmp1 = tmp0.buffer(+buffer_size, resolution=4, cap_style=2, join_style=2, mitre_limit=2.5)
            tmp2 = tmp1.buffer(-buffer_size, resolution=4, cap_style=2, join_style=2, mitre_limit=2.5)
            ff = shapely.ops.cascaded_union((tmp2, s0))
            buffer_size += 10.0
    except ValueError:
        print('!!! Error in ortho_merge')

    # if buffer_size > 499.0:
    #     print('!!! "%s": Orthogonal merge failed -- trying regular merge' % label)
    #     ff = poly_merge(ff, label)

    return ff





#
# This is the original R version of "orthoMerge".
#
# orthoMerge = function(f){
#     require(rgeos)
#     tryCatch({
#         #"c" is the complexity of the solution (in this version is the number of polygons in the merged solution)
#         # we want the result to deliver only 1 polygon, so we'll iterate until we get a single polygon
#         c = 2
#         w = 10 # the starting width of the buffer.  Make sure the projection is in meters.
#         ml = 2.5 #The mitreLimit is how far the mitre can extend.  This number is empirical.
#                 #2.5m works well for the Boston BAs (buffers deal with joins in basically 3 ways: round, bevel, and mitre)
#         while(c > 1){
#             f2 = gBuffer(gBuffer(f, width=w, joinStyle = 'MITRE', mitreLimit = ml),
#                     width=w*-1, joinStyle = 'MITRE', mitreLimit = ml)
#             c = length(f2@polygons[[1]]@Polygons)
#             w = w+5
#     }
#     f3 = gUnion(f, f2)
#     return(f3)
#   }, error=function(i) {return()})
# }
