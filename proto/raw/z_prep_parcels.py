#
# This script combines and filters the available Boston MSA parcels and
# writes the result to a single big file.
#


import shapely.geometry
import fiona
from e_utils import get_remap_function
from e_utils import remap_feature
from e_utils import get_msa_shape
import os


remap = get_remap_function('proto')
msa_shape = get_msa_shape(msa_name='proto', projected=True)


# This is used below to re-map coordinates from the local system back to WGS84.
def towgs(xx, yy, zz=None):
    return remap(xx, yy, inverse=True)


infile_list = ['/Users/jbcollins/msa/seattle/raw/parcels_0.shp']


crs = '+proj=longlat +ellps=WGS84 +datum=WGS84'
driver = 'ESRI Shapefile'
schema = {'geometry': 'Polygon', 'properties': {'id': 'int'}}

idn = 0
outfile ='../parcels/parcels.shp'
print('## Will write all parcel polygons to "%s"' % outfile)
with fiona.open(outfile, 'w', driver=driver, crs=crs, schema=schema) as dest:

    for fn in infile_list:
        k = 0
        with fiona.open(fn) as infile:

            print('## Reading parcels from "%s"' % fn)

            for f0 in infile:

                k += 1
                if k % 10000 == 0:
                    print('### Feature %d / %d' % (k, len(infile)))

                f1 = remap_feature(f0, remap)
                s1 = shapely.geometry.geo.shape(f1['geometry'])

                if s1.within(msa_shape):

                    p = s1.length
                    a = s1.area
                    q = (p / 4.0) ** 2 / a

                    if q < 3.0:
                        idn += 1
                        f0['properties'] = {'id': idn}
                        dest.write(f0)
