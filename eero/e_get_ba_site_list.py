# -*- coding: utf-8 -*-


#
# This script figures out which sites to use for business area definition.
#

import os
import csv
from e_utils import psvin


print('# Finding sites to be used for business area definition')


msa_base = os.environ.get('MSA_BASE')
msa_name = os.environ.get('MSA_NAME')
ref_dir = '%s/ref' % msa_base
msa_dir = '%s/%s' % (msa_base, msa_name)
biz_dir = '%s/biz' % msa_dir
area_dir = '%s/areas' % msa_dir
parcel_dir = '%s/parcels' % msa_dir
meta_dir = '%s/meta' % msa_dir
road_dir = '%s/roads' % msa_dir


# Read the table that gives business category semantics. That table contains an indicator of whether
# businesses of any category are to be used for area definition.
fname = '%s/sbc/sbc_semantics.psv' % ref_dir
biz_cat_semantics = psvin(fname, key='bcid')


# Get a lookup table that maps business IDs to site IDs.
fname = '%s/biz_site_lookup.psv' % biz_dir
site_lookup = psvin(fname, key='bizId')


# Read the input records, filtering out the ones that we won't be using. Note the 'biz_cat_semantics' table
# includes a column named 'adef' which indicates whether businesses of that category should be used for
# business area definition. The "lambda" function below basically checks that field to determine whether
# to keep a business.
ifname = '%s/biz_list.psv' % biz_dir
ba_biz_list = psvin(ifname, filter=lambda biz: biz_cat_semantics[biz['bcid']]['adef'] == '1')


# Go through the list of businesses (which has already been filtered to only contain those to be used
# for business area definition), and determine the site ID for each one.  Keep a list of those site IDs.
ad_site_list = set()
for rec in ba_biz_list:
    biz_id = rec['pid']
    site_id = site_lookup[biz_id]['siteId']
    ad_site_list.add(site_id)


# Write out the new file. The 'rad' suffix indicates that this is the list of businesses to be used
# for retail area definition.
with open('%s/site_list.psv' % biz_dir) as infile:
    reader = csv.DictReader(infile, delimiter='|')

    ofname = '%s/ba_site_list.psv' % area_dir
    print('## Writing list of business area definition sites: "%s"' % ofname)
    with open(ofname, 'w') as outfile:
        writer = csv.DictWriter(outfile, delimiter='|', fieldnames=reader.fieldnames)
        writer.writeheader()

        for rec in reader:
            if rec['siteId'] in ad_site_list:
                writer.writerow(rec)


print






