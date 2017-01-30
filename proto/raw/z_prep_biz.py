

import shapely.geometry
from e_utils import get_msa_shape
import csv


msa_shape = get_msa_shape(msa_name='proto')


biz_list = {}
with open('biz.psv') as infile:
    reader = csv.reader(infile, delimiter='|', quoting=csv.QUOTE_NONE)
    for rec in reader:
        pid = rec[0]
        name = rec[3]
        address = '%s %s %s %s' % (rec[6], rec[7], rec[8], rec[9])
        city = rec[14]
        state = rec[15]
        zip = rec[16]
        lon = rec[46]
        lat = rec[45]
        chainid = rec[1]

        if msa_shape.contains(shapely.geometry.Point(float(lon), float(lat))):
            biz_list[pid] = {'pid': pid, 'name': name,
                             'address': address, 'city': city, 'state': state, 'zip': zip,
                             'lon': lon, 'lat': lat,
                             'chainid': chainid, 'psic': '', 'allsics': '', 'res_type': ''}


with open('/Users/jbcollins/msa/ref/sic/CompanySIC.txt') as infile:
    reader = csv.reader(infile, delimiter='|')
    for rec in reader:
        if rec[0] in biz_list:
            biz_list[rec[0]]['allsics'] += rec[1] + ':'
            if rec[2] == '1':
                biz_list[rec[0]]['psic'] = rec[1]


with open('../biz/biz_list_0.psv', 'w') as outfile:
    fieldnames = ['pid', 'name', 'address', 'city', 'state', 'zip', 'lon', 'lat', 'chainid', 'psic', 'allsics', 'res_type']
    writer = csv.DictWriter(outfile, delimiter='|', fieldnames=fieldnames)
    writer.writeheader()
    for pid in sorted(biz_list.keys()):
        writer.writerow(biz_list[pid])






