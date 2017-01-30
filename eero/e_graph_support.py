#
# This file has functions supporting the buildng of road network graphs from
# open street map input files.
#


import math
import json
import networkx as nx


def graph_from_osm_files(osm_file_name_list, remap):
    """
    This function assembles road network data structures from a set of OSM JSON files.
    Pass in a list of names of JSON files downloaded from the overpass API, and get back
    a "networkx" graph structure and some associated data.

    The input files should be ones that were retrieved using the following Overpass API syntax:
        [out:json]; ( way(42.6,-71.9,42.7,-71.8) [highway]; node(w); ); out;
    The cryptic Overpass syntax can be interpreted thusly:
        (1) Create JSON-format output.
        (2) Give me all of the "way" objects that intersect the given lon/lat bounding box [which
            is (lat_min, lon_min, lat_max, lon_max)] that have an attribute named "highway". Having
            a "highway" attribute is how OSM identifies all roads.
        (3) Also give me all of the nodes that are any part of these ways.

    :param osm_file_name_list:
    :param remap: The name of a function that gives local (x,y) coordinates given (lon,lat).
        That is, (x, y) = remap(lon, lat). This is the style of function returned by "pyproj.Proj()"
    :return: A networkx-format graph and some other things.
    """

    # These define the types of roads we are interested in.
    good_classes = [ "motorway", "motorway_junction", "motorway_link",
                     "primary", "primary_link", "residential", "secondary", "secondary_link",
                     "service", "tertiary", "tertiary_link", "trunk", "trunk_link",
                     "turning_circle", "unclassified"]

    # In the following loop, we will be building up big lists of all nodes and all edges
    # from all of the input files; here we initialize them.
    node_list = {}
    way_list = {}

    for osm_file_name in osm_file_name_list:

        # slurp in the input file;
        print osm_file_name
        try:
            with open(osm_file_name) as infile:
                data = json.load(infile)

            for e in data['elements']:

                id = e['id']

                if e['type'] == 'node':
                    if id not in node_list:
                        (x, y) = remap(e['lon'], e['lat'])
                        node_list[id] = {'x': x, 'y': y, 'lon': e['lon'], 'lat': e['lat'], 'ways': []}

                elif e['type'] == 'way':
                    if id not in way_list:
                        tags = e['tags']
                        # 'highway' is the (unintuitive) name of the field that says what kind of road this is;
                        road_class = tags['highway']
                        is_one_way = False
                        if 'oneway' in tags and tags['oneway'] == 'yes':
                            is_one_way = True
                        if road_class in good_classes:
                            way_list[e['id']] = {'nodes': e['nodes'], 'road_class': road_class, 'oneway': is_one_way}
        except ValueError:
            continue

    # End of loop over input files.

    # Make each node remember the ways that use it.
    for w in way_list:
        for n in way_list[w]['nodes']:
            node_list[n]['ways'].append(w)

    # This will hold a set of network vertices.
    vertex_set = set()

    # Go through the list of ways; for each one, add the first and last node to the vertex set.
    for w in way_list:
        vertex_set.add(way_list[w]['nodes'][0])
        vertex_set.add(way_list[w]['nodes'][-1])

    # That doesn't catch all of them -- there may be other graph vertices that are internal to the node set.
    # Those are precisely the ones that have more than one 'way' associated with them, which is what we
    # figured out above.
    for n in node_list:
        if len(node_list[n]['ways']) > 1:
            vertex_set.add(n)

    # Now that we have a list of vertices, define the edges of the transportation network graph; we crawl along
    # each 'way', and every time we encounter a vertex, chop off an edge at that point; note we're also keeping track of
    # length as we crawl through the list of nodes;
    edge_list = {}
    for w in way_list:
        nodes = way_list[w]['nodes']
        road_class = way_list[w]['road_class']
        is_one_way = way_list[w]['oneway']
        last_vertex = nodes[0]
        last_x = node_list[nodes[0]]['x']
        last_y = node_list[nodes[0]]['y']
        xx = [last_x]
        yy = [last_y]
        running_length = 0.0
        for i in range(1, len(nodes)):
            this_node = nodes[i]
            this_x = node_list[this_node]['x']
            this_y = node_list[this_node]['y']
            xx.append(this_x)
            yy.append(this_y)
            dd = math.sqrt((this_x-last_x)**2 + (this_y-last_y)**2)
            running_length += dd
            if i == len(nodes)-1 or this_node in vertex_set:
                # Found the end of an edge; add it to the list.
                edge_id = '%d-%d' % (last_vertex, this_node)
                edge_list[edge_id] = {'wayId': w,
                                      'v0': last_vertex, 'v1': this_node,
                                      'length': int(running_length),
                                      'road_class': road_class,
                                      'xx': xx, 'yy': yy}
                # # if this way is *not* a one-way, then we need to add a separate edge going
                # # 'the other way';
                # if not is_one_way:
                #     edge_id = '%d-%d' % (this_node, last_vertex)
                #     edge_list[edge_id] = {'wayId': w,
                #                         'v0': this_node, 'v1': last_vertex,
                #                         'length': int(running_length), 'time': int(running_length / speed),
                #                         'road_class': road_class,
                #                         'xx': xx, 'yy': yy}
                last_vertex = this_node
                running_length = 0.0
                xx = [this_x]
                yy = [this_y]
            last_x = this_x
            last_y = this_y

    # Build the transportation network graph.
    # g = nx.DiGraph()
    g = nx.Graph()
    for v in vertex_set:
        g.add_node(v, lon=node_list[v]['lon'], lat=node_list[v]['lat'])

    for e in edge_list:
        length = edge_list[e]['length']
        road_class = edge_list[e]['road_class']
        g.add_edge(edge_list[e]['v0'], edge_list[e]['v1'], length=length, road_class=road_class, id=e)

    # All done.
    return g, node_list, way_list, edge_list
