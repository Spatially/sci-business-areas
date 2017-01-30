#
# his script  prints out queries that get chunks of data from the OpenStreetMap "Overpass API".
# These will be the source of all our road network data.
#


import os
import csv
import shapely.geometry
import numpy
from e_utils import get_msa_shape


print('# Generating queries that get OSM road network data using the Overpass API')


msa_base = os.environ.get('MSA_BASE')
msa_name = os.environ.get('MSA_NAME')
msa_dir = '%s/%s' % (msa_base, msa_name)
ref_dir = '%s/ref' % msa_dir
area_dir = '%s/areas' % msa_dir
biz_dir = '%s/biz' % msa_dir
road_dir = '%s/roads' % msa_dir


# Get the bounds of the area that we are interested in, rounded to the nearest 0.1 degree
# latitude and longitude.
msa_shape = get_msa_shape()
bounds = msa_shape.bounds
lonMin = numpy.floor(bounds[0] * 10.0) / 10.0
latMin = numpy.floor(bounds[1] * 10.0) / 10.0
lonMax = numpy.ceil(bounds[2] * 10.0) / 10.0
latMax = numpy.ceil(bounds[3] * 10.0) / 10.0

print('## Writing the query script')
increment = 0.1

# This block creates a shell script that gets the OSM road network data. It does not
# actually run the script.
with open(road_dir + '/z_run_osm_queries.sh', 'w') as outfile:

    outfile.write('#!/bin/sh\n\n')
    outfile.write(' test -d osm || mkdir osm\n')

    lon = lonMin
    while lon < lonMax:

        lat = latMin
        while lat < latMax:

            lat1 = lat + increment
            lon1 = lon + increment
            coords = [(lon, lat), (lon1, lat), (lon1, lat1), (lon, lat1), (lon, lat)]
            box = shapely.geometry.Polygon(coords)
            if box.intersects(msa_shape):
                coordString = '%.1f,%.1f,%.1f,%.1f' % (lat, lon, lat1, lon1)
                fname = 'osm/roads_%.0f_%.0f.json' % (abs(lon * 10.0), abs(lat * 10.0))
                outfile.write("if ! test -s %s\n" % fname)
                outfile.write("then\n")
                outfile.write("q='[out:json]; ( way(%s) [highway]; node(w); ); out;'\n" % coordString)
                outfile.write('wget -O %s "http://overpass-api.de/api/interpreter?data=$q"\n' % fname)
                outfile.write('fi\n\n')

            lat += increment

        lon += increment

print






