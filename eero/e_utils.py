#
# This file is part of the "eero" package. It provides some simple utilities 

import shapely.geometry
import shapely.ops
import csv
import os
import pyproj
import fiona


msa_base = os.environ.get('MSA_BASE')
msa_name = os.environ.get('MSA_NAME')
ref_dir = '%s/ref' % msa_base
msa_dir = '%s/%s' % (msa_base, msa_name)
area_dir = '%s/areas' % msa_dir
parcel_dir = '%s/parcels' % msa_dir
meta_dir = '%s/meta' % msa_dir


def get_msa_shape(projected=False, msa_name=None):
    """
    Returns a "shape" representing the boundary of the MSA.

    :param projected: If True, then return the shape in projected coordinates
    :return: A "shape" (in the sense of the "shapely" package.
    """
    if msa_name is None:
        fname = meta_dir + '/bounds.shp'
    else:
        fname = '%s/%s/meta/bounds.shp' % (msa_base, msa_name)

    print('reading MSA shape from "%s"' % fname)
    with fiona.open(fname) as source:
        f = source.next()
    s = shapely.geometry.geo.shape(f['geometry'])

    if projected == True:
        remap = get_remap_function(msa_name)
        s = shapely.ops.transform(remap, s)

    return s


def get_projection_string(msa_name=None):
    """
    This function gets the "proj4" string for the current MSA.

    :return: a "proj4" string
    """

    if msa_name is None:
        meta_fname = meta_dir + '/meta.psv'
    else:
        meta_fname = '%s/%s/meta/meta.psv' % (msa_base, msa_name)

    meta = psvin(meta_fname, key='name')
    p = meta['projection']['value']
    return p


def get_remap_function(msa_name=None):
    """
    This function gets a function that re-maps coordinates between WGS84 and the local Coordinate
    Reference System (CRS). This is basically a function from the "pyproj" library.

    :return: A function that re-maps coordinates.
    """

    p = get_projection_string(msa_name)
    remap = pyproj.Proj(p)
    return remap


def remap_feature(f0, remap):

    # Make the feature in to a shape.
    s0 = shapely.geometry.geo.shape(f0['geometry'])

    # Apply the remapping function to the shape
    s1 = shapely.ops.transform(remap, s0)

    # Build the new feature.
    f1 = {'geometry': shapely.geometry.mapping(s1),
          'properties': f0['properties']}

    # Done.
    return f1


def psvin(fname, key=None, filter=None):
    """
    This is a utility that can handle much of the PSV (pipe-separated value) file reading that
    we need to do within the eero system. This function assumes that fields are pipe-delimited,
    that there is no need for quotation of any of the fields, and that the file has a header row.
    Results are either returned as a list of records, or as a dictionary inexed by the indicated field.

    :param fname: name of th input file
    :param key: name of key field, if desired
    :param filter: function that filters out rows
    :return: list or dict containing file rows, as a dictionary indexed by column name
    """

    if key is None:
        rec_list = []
    else:
        rec_list = {}

    with open(fname) as infile:
        reader = csv.DictReader(infile, delimiter='|')
        for rec in reader:
            if filter is None or filter(rec) is True:
                if key is None:
                    rec_list.append(rec)
                else:
                    rec_list[rec[key]] = rec

    return rec_list


def plist(x, limit=20):
    """
    Print the contents of a list.

    :param x:
    :param limit:
    :return:
    """
    count = 0
    for z in x:
        count += 1
        if limit is not None and count > limit:
            break
        print z


def pdict(d, limit=30, indent=0):
    """
    Print the contents of a dictionary.
    :param d:
    :param limit:
    :param indent:
    :return:
    """
    count = 0
    for k in d.keys():
        if type(d[k]) == dict:
            print ' '*indent, k, ': {'
            pdict(d[k], indent=indent+4)
            print ' '*indent + '}'
        else:
            print ' '*indent, k, ':', d[k]
        count += 1
        if limit is not None and count >= limit:
            break

