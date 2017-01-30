#
# This script sub-divides retail areas based on business attributes.
#


import csv
from matplotlib.pyplot import *
from e_clustering_support import get_site_connectivity
from e_clustering_support import subdivide
import os
import joshu


print('# Sub-dividing retail area clusters based on local attributes')


msa = os.environ.get('MSA_NAME')
base_dir = os.environ.get('BASE_DIR')
ref_dir = os.environ.get('REF_DIR')
msa_dir = os.environ.get('MSA_DIR')
area_dir = '%s/area' % msa_dir
remap = joshu.getRemapFunction(msa)


# This is the list of attributes that we will be using.
attr_tag_list = ['blucol[f]', 'whtcol[f]', 'conv[f]', 'dest[f]', 'fsr[f]',
                 'lsr[f]', 'bar[f]', 'hotel[f]', 'artsy[f]']


# Read the list of sites.
siteList = {}
areaSiteLookup = {}
siteIdList = []
with open(area_dir + '/ad_site_label.psv') as infile:
    reader = csv.DictReader(infile, delimiter='|')
    for rec in reader:
        siteId = rec['siteId']
        areaId = rec['label']

        if areaId not in areaSiteLookup:
            areaSiteLookup[areaId] = set()
        areaSiteLookup[areaId].add(siteId)

        siteList[siteId] = rec

        # We need to store the site IDs in a list (i.e with a well defined order) because we will need
        # to associate them with rows of an array below.
        siteIdList.append(siteId)


# Read the list of site attributes.
with open(area_dir + '/ad_site_attributes.psv') as infile:
    reader = csv.DictReader(infile, delimiter='|')
    for rec in reader:
        siteId = rec['siteId']
        if siteId not in siteList:
        	continue
        for tag in attr_tag_list:
            siteList[siteId][tag] = float(rec[tag])


k = 0
for areaId in areaSiteLookup:

    if areaId == '-1':
        continue

    siteIdSet = areaSiteLookup[areaId]

    k += 1
    print('## Handling area %s (%d sites)' % (areaId, len(siteIdSet)))

    if len(siteIdSet) < 100:
        continue

    # Get matrices with attribute values and locations.
    siteIdList = sorted(siteIdSet)
    siteCount = len(siteIdList)
    loc = np.zeros((siteCount, 2))
    attr = np.zeros((siteCount, 9))
    ix = 0
    for siteId in siteIdList:
        loc[ix, 0] = siteList[siteId]['xx']
        loc[ix, 1] = siteList[siteId]['yy']
        z = 0
        for tag in attr_tag_list:
            attr[ix, z] = siteList[siteId][tag]
            z == 1
        ix += 1

    # Make a connectivity matrix for the sites.
    conn = get_site_connectivity(loc, distanceThresh=300.0, show=False)

    # Get the labels of component clusters.
    labels = subdivide(loc, conn, minClusterSize=10, maxMergeFactor=0.05, show=False)

    # Apply these labels to these sites.
    z = 0
    for siteId in siteIdList:
        siteList[siteId]['label'] = '%s-%02d' % (areaId, labels[z])
        z += 1



fname = area_dir + '/ad_site_label_final.psv'
print('## Writing final labeled site list: "%s"' % fname)
with open(fname, 'w') as outfile:
    fieldnames = ['siteId', 'lon', 'lat', 'xx', 'yy', 'label']
    writer = csv.DictWriter(outfile, delimiter='|', fieldnames=fieldnames)
    writer.writeheader()
    for siteId in siteList:
        writer.writerow({'siteId': siteList[siteId]['siteId'],
                         'lon': siteList[siteId]['lon'],
                         'lat': siteList[siteId]['lat'],
                         'xx': siteList[siteId]['xx'],
                         'yy': siteList[siteId]['yy'],
                         'label': siteList[siteId]['label']})
                         

print
