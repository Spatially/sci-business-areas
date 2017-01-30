#
# This module produces a set of inter-site distances by scaling the previously computed road distances
# by a measure of the local business density.
#


import csv
import os
import numpy as np


print('# Scaling inter-site road network distances according to local business density')


msa_base = os.environ.get('MSA_BASE')
msa_name = os.environ.get('MSA_NAME')
msa_dir = '%s/%s' % (msa_base, msa_name)
ref_dir = '%s/ref' % msa_base
area_dir = '%s/areas' % msa_dir
biz_dir = '%s/biz' % msa_dir
road_dir = '%s/roads' % msa_dir


# Define a few parameters to be used below
sigma = 200.0  # kernel density bandwidth parameter
max_distance = sigma * 3.0


# First we just need a lost of site IDs.
fname = biz_dir + '/site_list.psv'
print('## Reading site IDs from "%s"' % fname)
site_id_list = []
with open(fname) as infile:
    reader = csv.reader(infile, delimiter='|')
    reader.next() # Skip the header.
    for rec in reader:
        site_id_list.append(rec[0])


# Initialize the list of density values.
print('## Initializing density values.')
density_list = {}
for site_id in site_id_list:
    density_list[site_id] = 0.0


# Get density values by making a pass through the list of inter-site distances.
fname = biz_dir + '/site_road_distances.psv'
print('## Computing density from inter-site distances using "%s"' % fname)
fff = -1.0 / (2.0 * sigma * sigma)  # Used in kernel density computation below.
with open(fname) as infile:

    reader = csv.reader(infile, delimiter='|')
    reader.next() # Skip the header
    k = 0
    for rec in reader:

        k += 1
        if k % 1000000 == 0:
            print('### Record %d' % k)

        dd = float(rec[2])
        if dd < max_distance:
            # Compute the kernel density value.
            kv = np.exp(dd * dd * fff)
            sid0 = rec[0]
            sid1 = rec[1]
            density_list[sid0] += kv
            if sid1 != sid0:
                density_list[sid1] += kv


# Write out the list of site density values.
fname = biz_dir + '/site_density.psv'
print('## Writing list of site density values: "%s"' % fname)
with open(fname, 'w') as outfile:
    writer = csv.DictWriter(outfile, delimiter='|', fieldnames=['siteId', 'lon', 'lat', 'density'])
    writer.writeheader()

    with open(biz_dir + '/site_list.psv') as source:
        reader = csv.DictReader(source, delimiter='|')
        for rec in reader:
            writer.writerow({'siteId': rec['siteId'],
                             'lon': rec['lon'],
                             'lat': rec['lat'],
                             'density': '%.1f' % density_list[rec['siteId']]})


# Get local scaling factors for each site.
d = density_list.values()
x0 = np.percentile(d, 20.0)
x1 = np.percentile(d, 80.0)
y0 = 0.2
y1 = 1.0
factor_list = {}
for site_id in density_list:
    xx = density_list[site_id]
    yy = y0 + (xx - x0) / (x1 - x0) * (y1 - y0)
    factor_list[site_id] = np.clip(yy, y0, y1)


# Now that we have the scaling factors, go back and apply them to the original distance data.
fname_in = biz_dir + '/site_road_distances.psv'
fname_out = biz_dir + '/site_road_distances_scaled.psv'
print('## Writing scaled road distances to "%s"' % fname_out)
k = 0
with open(fname_in) as infile:
    reader = csv.reader(infile, delimiter='|')

    with open(fname_out, 'w') as outfile:
        writer = csv.writer(outfile, delimiter='|')

        rec = reader.next()
        writer.writerow(rec)

        k = 0
        for rec in reader:

            k += 1
            if k % 1000000 == 0:
                print('### Record %d' % k)

            sid0 = rec[0]
            sid1 = rec[1]
            dd0 = float(rec[2])
            f = np.max([factor_list[sid0], factor_list[sid1]])
            # Hack: temporarily turning off the scaling.
            # dd1 = '%.1f' % dd0
            dd1 = '%.1f' % (dd0 * f)
            writer.writerow((sid0, sid1, dd1))


print


