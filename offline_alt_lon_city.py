import os
import json
import pickle
import requests
import time
import csv
import kdnode as kd
import utility as ut
from io import StringIO
iata_url = 'https://raw.githubusercontent.com/davidmegginson/ourairports-data/refs/heads/main/airports.csv'

airport_info = []
airport_us_info = []
#strPkl = 'iata_info.pkl'
#if os.path.isfile(strPkl):
#    with open(strPkl, "rb") as f:
#        airport_info = pickle.load(f)
#url = f'https://api.bigdatacloud.net/data/reverse-geocode-client?latitude={row['latitude']}&longitude={row['longitude']}&localityLanguage=en'

iata_io = requests.get(iata_url)
iata_info = list(csv.DictReader(StringIO(iata_io.text)))
for i,row in enumerate(iata_info):
    if len(row['iata_code'])!=3:
        continue
    airport_info.append([float(row['latitude_deg']),float(row['longitude_deg']),
        row['iata_code'],row['municipality']+","+row['iso_region']
        ])
    if row['iso_region'].startswith('US'):
        airport_us_info.append([float(row['latitude_deg']),float(row['longitude_deg']),
        row['iata_code'],row['municipality']+","+row['iso_region']
        ])
print("Total number of IATA airports: %d"%len(airport_info))
print("Total number of US IATA airports: %d"%len(airport_us_info))
airport_info = kd.build_kdtree(airport_info)
with open("iata_info.json",'w') as f:
    json.dump(kd.node_to_dict(airport_info),f)

airport_us_info = kd.build_kdtree(airport_us_info)
with open("iata_us_info.json",'w') as f:
    json.dump(kd.node_to_dict(airport_us_info),f)

#airport_info = [[24.2617, 55.6092, 'AAN', 'Al Ain City,United Arab Emirates (the)'], [24.433, 54.6511, 'AUH', 'Abu Dhabi,United Arab Emirates (the)'], [24.467, 54.6103, 'AYM', 'Abu Dhabi,United Arab Emirates (the)'], [24.4283, 54.4581, 'AZI', 'Abu Dhabi,United Arab Emirates (the)'], [24.2482, 54.5477, 'DHF', 'Abu Dhabi,United Arab Emirates (the)'], [24.2836, 52.5803, 'XSB', 'Al Dhafra,United Arab Emirates (the)'], [24.51, 52.3352, 'ZDY', 'Al Dhafra,United Arab Emirates (the)'], [25.1122, 56.324, 'FJR', 'Fujairah,United Arab Emirates (the)'], [25.3286, 55.5172, 'SHJ', 'Sharjah,United Arab Emirates (the)'], [25.2422, 55.3314, 'DCG', 'Dubai,United Arab Emirates (the)'], [24.989, 55.0238, 'DJH', 'Dubai,United Arab Emirates (the)'], [24.8964, 55.1614, 'DWC', 'Dubai,United Arab Emirates (the)'], [25.2528, 55.3644, 'DXB', 'Dubai,United Arab Emirates (the)'], [25.0268, 55.3662, 'NHD', 'Dubai,United Arab Emirates (the)'], [25.691, 55.778, 'RHR', 'Ras Al Khaimah,United Arab Emirates (the)'], [25.6135, 55.9388, 'RKT', 'Ras Al Khaimah,United Arab Emirates (the)'], [38.4611, 70.8825, 'DAZ', 'Darwaz-e Pa’in,Afghanistan'], [37.1211, 70.5181, 'FBD', 'Argo,Afghanistan'], [37.752, -89.0154, 'KUR', 'Marion,United States of America (the)'], [37.883, 70.217, 'KWH', 'Khwahan,Afghanistan']]
