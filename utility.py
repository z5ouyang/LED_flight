import json,traceback,gc,time,math,os,re
import kdnode as kd
kd.init_iata_info()

WAIT_TIME=15
UPDATE_TIME=5
WAIT_TIME_MAX=75
MAX_FOLLOW_PLAN=70
LANDING_ALTITUDE=51
FLIGHT_SEARCH_HEAD="https://data-cloud.flightradar24.com/zones/fcgi/feed.js?"
FLIGHT_SEARCH_TAIL="&faa=1&satellite=1&mlat=1&flarm=1&adsb=1&gnd=0&air=1&vehicles=0&estimated=0&maxage=14400&gliders=0&stats=0&ems=1" #&limit=1
FLIGHT_LONG_DETAILS_HEAD="https://data-live.flightradar24.com/clickhandler/?flight="
HTTP_HEADERS = {
     "User-Agent": "Mozilla/5.0",
     "cache-control": "no-store, no-cache, must-revalidate, post-check=0, pre-check=0",
     "accept": "application/json"
}
FLIGHT_SHORT_KEYS = ['ICAO_aircraft','latitude','logitude','heading','altitude','speed','squawk','radar','aircraft_type','aircraft_reg','timestamp',
        'ori','dest','flight_number','vertical_speed','squawk_status','callsign','ADS_B','ICAO_airline']
TIME_ZONE_SEARCH_HEAD="https://api.timezonedb.com/v2.1/get-time-zone?key=APIKEY&format=json&by=zone&zone="
IATA_INFO=None
FLIGHT_DETAILS_LATEST=None


def get_config():
    with open('private.json') as f:
        config = json.load(f)
    return config

def is_between(v,r):
    s, l = r
    if s>l:
        s, l = l, s
    return s <= v <= l

def get_request_response(requests,url,DEBUG_VERBOSE=False):
    try:       
        response = requests.get(url=url,headers=HTTP_HEADERS)
        response_json = response.json()
        response.close()
        gc.collect()
    except Exception as e:
        if DEBUG_VERBOSE:
            traceback.print_exception(e)
        return None
    return response_json

def get_distance(center,loc):
    if center is None:
        return 1
    return math.sqrt((center[0] - loc[0])**2 + (center[1] - loc[1])**2)

def get_dict_value(d,keys):
    if d is None:
        return 'NA'
    if len(keys)==0:
        return d
    if isinstance(keys[0],(int)):
        return get_dict_value(d[keys[0]],keys[1:])
    if keys[0] in d.keys():
        return get_dict_value(d.get(keys[0]),keys[1:])
    return 'NA'

def get_est_arrival(eta):
    if eta=='Unknown':
        return 5
    return min(WAIT_TIME_MAX,max(5,int(eta-time.time()-50)))

# geoloc not across 180 longitude
def is_in_dynamic_altitude(fInfo,geoloc,altitude,threshold_rate=0.2):
    h = fInfo[3]
    tl_lat,br_lat,tl_lon,br_lon = geoloc
    span_lat = abs(tl_lat-br_lat)
    span_lon = abs(tl_lon-br_lon)
    if 45<= h < 135: # east
        progress = (fInfo[2]-tl_lon)/span_lon
    elif 135 <= h < 225: # south
        progress = abs(tl_lat - fInfo[1])/span_lat
    elif 225<= h < 315: # west
        progress = (br_lon-fInfo[2])/span_lon
    else: # north
        progress = (fInfo[1] - br_lat)/span_lat
    expected_altitude = altitude[0] + progress * (altitude[1]-altitude[0])
    #print(progress,expected_altitude,abs(fInfo[4] - expected_altitude),expected_altitude*threshold_rate)
    return (abs(fInfo[4] - expected_altitude))<=(expected_altitude*threshold_rate)#,progress,(altitude[0]+progress * (altitude[1]-altitude[0]))

def is_in_altitude(fInfo,geoloc,altitude,altitude_rev,threshold_rate=0.2):
    if altitude is None and altitude_rev is None:
        return True
    for one in [altitude,altitude_rev]:
        if one is not None and is_in_dynamic_altitude(fInfo,geoloc,one,threshold_rate):
            return True
    return False

def is_in_heading(fheading,heading,heading_rev):
    if heading is None and heading_rev is None:
        return True,None
    for one in [heading,heading_rev]:
        if one is not None and is_between(fheading,one):
            return True,one
    return False,None

def is_in_region(fInfo,geoloc,altitude,heading,speed,altitude_rev,heading_rev):
    if speed is not None and not is_between(fInfo[5],speed):
        return False
    b_heading,h = is_in_heading(fInfo[3],heading,heading_rev)
    if not b_heading:
        return False
    if h is None:
        return is_in_altitude(fInfo,geoloc,altitude,altitude_rev)
    if h==heading:
        return is_in_dynamic_altitude(fInfo,geoloc,altitude)
    if h==heading_rev:
        return is_in_dynamic_altitude(fInfo,geoloc,altitude_rev)
    return False

#v = ['AA',32.72,-117.105,106,3000,135]
#is_in_region(v,geoloc,altitude,heading,speed,altitude_rev,heading_rev) 


def get_flights(requests,geoloc,rInfo,DEBUG_VERBOSE=False):
    altitude=rInfo.get('altitude')
    heading=rInfo.get('heading')
    speed=rInfo.get('speed')
    altitude_rev = rInfo.get("altitude_rev")
    heading_rev = rInfo.get('heading_rev')
    center_geoloc=rInfo.get('center_loc')
    dest=rInfo.get('dest')
    # https://data-cloud.flightradar24.com/zones/fcgi/feed.js?bounds=32.74,32.70,-117.17,-117.10&faa=1&satellite=1&mlat=1&flarm=1&adsb=1&gnd=0&air=1&vehicles=0&estimated=0&maxage=14400&gliders=0&stats=0&ems=1
    url = FLIGHT_SEARCH_HEAD+"bounds="+",".join(str(i) for i in geoloc)+FLIGHT_SEARCH_TAIL
    flight=get_request_response(requests,url,DEBUG_VERBOSE)
    if DEBUG_VERBOSE:
        print(flight)
    flight_dist={}
    flight_short={}
    if flight is not None and len(flight)>2:
        #{'0':'ICAO 24-bit aircraft address (hex)', '1':'Latitude', '2':'Longitude', '3':'Aircraft heading (degrees)','4':'Altitude (feet)',
        #    '5':'Ground speed (knots)','6':'Vertical speed (feet/min) — empty or unknown','7':'Radar source or feed ID','8':'Aircraft type (Boeing 737 MAX 9)',
        #    '9':'Registration number','10':'Timestamp (Unix epoch)','11':'Departure airport (San Francisco Intl)','12':'Arrival airport (San Diego Intl)',
        #    '13':'Flight number','14':'Possibly on-ground status (0 = airborne)','15':'Vertical speed (feet/min)','16':'Callsign',
        #    '17':'Possibly squawk code or status flag','18':'Airline ICAO code (United Airlines)']
        #heading_rev = None if heading is None else [(_+180)%360 for _ in heading]
        for k,v in flight.items():
            if isinstance(v,list) and len(v)>13 and is_in_region(v,geoloc,altitude,heading,speed,altitude_rev,heading_rev) and (dest is None or v[12]=='' or dest==v[12]):
               flight_dist[k] = get_distance(center_geoloc,v[1:3])
               flight_short[k] = {FLIGHT_SHORT_KEYS[i]:v[i] for i in range(min(len(FLIGHT_SHORT_KEYS),len(v)))}#    {'heading':v[3],'altitude':v[4]}
    flight_index = None if len(flight_dist)==0 else min(flight_dist, key=flight_dist.get)
    if FLIGHT_DETAILS_LATEST is not None and FLIGHT_DETAILS_LATEST['flight_index'] == flight_index:
        flight_short[flight_index].update({k:v for k,v in FLIGHT_DETAILS_LATEST.items() if k in ['flight_number','ori','dest']})
    return flight_index,None if flight_index is None else flight_short[flight_index],flight is not None and len(flight)>0 # return a flag meaning the requests were successful

def get_flight_detail(requests,flight_index,DEBUG_VERBOSE=False):
    global FLIGHT_DETAILS_LATEST
    if DEBUG_VERBOSE:
        print("flight_index: ",flight_index)
    flight_details=None
    flight=get_request_response(requests,FLIGHT_LONG_DETAILS_HEAD+flight_index,DEBUG_VERBOSE)
    if flight is not None:
        ori_iata = get_dict_value(flight,['airport','origin','code','iata'])
        ori_city = get_dict_value(flight,['airport','origin','position','region','city'])
        if (ori_iata=='NA' or ori_city=='NA') and is_ori_trail(get_dict_value(flight,['trail'])):
            try:
                ori_iata,ori_city = get_iata_loc(get_dict_value(flight,['trail',-1]),ori_iata,ori_city)
            except Exception as e:
                if DEBUG_VERBOSE:
                    print("Error: get_iata_loc ori")
                    print(e)
        dest_iata = get_dict_value(flight,['airport','destination','code','iata'])
        dest_city = get_dict_value(flight,['airport','destination','position','region','city'])
        if (dest_iata=='NA' or dest_city=='NA') and is_dest_trails(get_dict_value(flight,['trail'])):
            try:
                dest_iata,dest_city = get_iata_loc(estimate_dest_trails(get_dict_value(flight,['trail'])),dest_iata,dest_city)
            except Exception as e:
                if DEBUG_VERBOSE:
                    print("Error: get_iata_loc dest")
                    print(e)         
        flight_details={
                'flight_index':flight_index,
                'flight_number': (get_dict_value(flight,['identification','number','default']) 
                    if get_dict_value(flight,['identification','number','default'])!='NA'
                    else get_dict_value(flight,['identification','callsign'])),
                'airline_name': get_dict_value(flight,['airline','name']),
                'airports_short': ori_iata + "-" + dest_iata,
                'airports_long': ori_city +"-" + dest_city,
                'aircraft_code': get_dict_value(flight,['aircraft','model','code']),
                'aircraft_model': get_dict_value(flight,['aircraft','model','text']),
                'status': get_dict_value(flight,['status','text']),
                'altitude': get_dict_value(flight,['trail',0,'alt']),
                'heading': get_dict_value(flight,['trail',0,'hd']),
                'speed': get_dict_value(flight,['trail',0,'spd']),
                'eta': get_dict_value(flight,['time','estimated','arrival']),
                'ori': ori_iata,
                'dest': dest_iata
        }
        flight_details['flight_number'] = flight_details['flight_number'] if not flight_details['flight_number']=='NA' else flight_details['airline_name']
        flight_details['airports_short'] = re.sub('NA','',flight_details['airports_short'])
    FLIGHT_DETAILS_LATEST = flight_details
    return flight_details

def get_flight_short(requests,flight_index,DEBUG_VERBOSE=False):
    if flight_index is None:
        return None
    url = FLIGHT_SEARCH_HEAD+"flight_id="+flight_index #+FLIGHT_SEARCH_TAIL
    flight=get_request_response(requests,url,DEBUG_VERBOSE)
    if not flight_index in flight.keys():
        return None
    flight_details = {FLIGHT_SHORT_KEYS[i]:flight[flight_index][i] for i in range(min(len(FLIGHT_SHORT_KEYS),len(flight[flight_index])))}
    if FLIGHT_DETAILS_LATEST is not None and FLIGHT_DETAILS_LATEST['flight_index'] == flight_index:
        flight_details.update({k:v for k,v in FLIGHT_DETAILS_LATEST.items() if k in ['flight_number','ori','dest']})
    return flight_details #{FLIGHT_SHORT_KEYS[i]:flight[flight_index][i] for i in range(min(len(FLIGHT_SHORT_KEYS),len(flight[flight_index])))}

def get_time_zone_offset(requests,tz,DEBUG_VERBOSE):
    url=re.sub('APIKEY',os.getenv("TIMEZONEDB_API_KEY"),TIME_ZONE_SEARCH_HEAD)+tz
    tInfo = get_request_response(requests,url,DEBUG_VERBOSE=DEBUG_VERBOSE)
    if tInfo['status'] == 'OK':
        return tInfo['gmtOffset']/3600,tInfo['abbreviation']
    return None,None

def closest_heading(angle):
    compass_points = [0, 45, 90, 135, 180, 225, 270, 315]
    return min(compass_points, key=lambda x: abs((angle - x + 180) % 360 - 180))

def get_iata_loc(trail,iata,city):
    airport_info = kd.nearest(kd.IATA_INFO,(trail['lat'],trail['lng']))
    if airport_info is not None:
        lat,lng,iata,city = airport_info
    return iata,city

def is_ori_trail(trails,tolerance=0.85):
    takeoff_index = min(len(trails),200)
    takeoff_alt = sum(1 for i in range(len(trails)-takeoff_index,len(trails)) if trails[i-1]['alt'] >= trails[i]['alt'])
    return takeoff_alt/takeoff_index > tolerance

def is_dest_trails(trails,tolerance=0.85):
    landing_index = min(len(trails)-1,200)
    landing_alt = sum(1 for i in range(landing_index) if trails[i]['alt'] <= trails[i+1]['alt'])
    return landing_alt/landing_index > tolerance

def estimate_dest_trails(trails,last_points=10):
    pred_trail = trails[0].copy()
    if pred_trail['alt']>3000:
        return pred_trail
    # [(trails[i+1]['alt']-trails[i]['alt']) for i in range(last_points)]
    # [(trails[i]['ts']-trails[i+1]['ts']) for i in range(last_points)]
    # [(trails[i]['spd']-trails[i+1]['spd']) for i in range(last_points)]
    alt_sp = [(trails[i+1]['alt']-trails[i]['alt'])/(trails[i]['ts']-trails[i+1]['ts']) for i in range(last_points)]
    alt_sp = [_ for _ in alt_sp if _ >0]
    alt_sp = sum(alt_sp)/len(alt_sp)
    ts = pred_trail['alt']/alt_sp/2 # estimate decendent 2 times faster
    lat_diff = [trails[i]['lat']-trails[i+1]['lat'] for i in range(last_points)]
    lng_diff = [trails[i]['lng']-trails[i+1]['lng'] for i in range(last_points)]
    #'%.4f,%.4f'%(pred_trail['lat']+ts*sum(lat_diff)/last_points,pred_trail['lng']+ts*sum(lng_diff)/last_points)
    pred_trail.update({
        'lat':pred_trail['lat']+ts*sum(lat_diff)/last_points,
        'lng':pred_trail['lng']+ts*sum(lng_diff)/last_points,
    })
    #print('%.4f,%.4f'%(pred_trail['lat'],pred_trail['lng']))
    return pred_trail
