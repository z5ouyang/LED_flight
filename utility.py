import json,traceback,gc,time,math,os,re

WAIT_TIME=15
UPDATE_TIME=5
WAIT_TIME_MAX=75
MAX_FOLLOW_PLAN=60
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

def get_config():
    with open('private.json') as f:
        config = json.load(f)
    return config

def bool_between(v,r):
    if r is None:
        return True
    return (v>r[0] and v<r[1])

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
    return get_dict_value(d.get(keys[0]),keys[1:])

def get_est_arrival(eta):
    if eta=='Unknown':
        return 5
    return min(WAIT_TIME_MAX,max(5,int(eta-time.time()-50)))

def get_flights(requests,geoloc,altitude=None,heading=None,center_geoloc=None,dest=None,speed=None,DEBUG_VERBOSE=False):
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
        heading_rev = None if heading is None else [(_+180)%360 for _ in heading]
        for k,v in flight.items():
            if isinstance(v,list) and len(v)>13 and bool_between(v[4],altitude) and bool_between(v[5],speed) and (bool_between(v[3],heading) or bool_between(v[3],heading_rev)) and (dest is None or v[12]=='' or dest==v[12]):
               flight_dist[k] = get_distance(center_geoloc,v[1:3])
               flight_short[k] = {FLIGHT_SHORT_KEYS[i]:v[i] for i in range(min(len(FLIGHT_SHORT_KEYS),len(v)))}#    {'heading':v[3],'altitude':v[4]}
    flight_index = None if len(flight_dist)==0 else min(flight_dist, key=flight_dist.get)
    return flight_index,None if flight_index is None else flight_short[flight_index],len(flight)>0 # return a flag meaning the requests were successful

def get_flight_detail(requests,flight_index,DEBUG_VERBOSE=False):
    if DEBUG_VERBOSE:
        print("flight_index: ",flight_index)
    flight_details=None
    flight=get_request_response(requests,FLIGHT_LONG_DETAILS_HEAD+flight_index,DEBUG_VERBOSE)
    if flight is not None:
            flight_details={
                'flight_index':flight_index,
                'flight_number': get_dict_value(flight,['identification','number','default']),
                'airline_name': get_dict_value(flight,['airline','name']),
                'airports_short': get_dict_value(flight,['airport','origin','code','iata']) +"-" + get_dict_value(flight,['airport','destination','code','iata']),
                'airports_long': get_dict_value(flight,['airport','origin','position','region','city']) +"-" + get_dict_value(flight,['airport','destination','position','region','city']),
                'aircraft_code': get_dict_value(flight,['aircraft','model','code']),
                'aircraft_model': get_dict_value(flight,['aircraft','model','text']),
                'status': get_dict_value(flight,['status','text']),
                'altitude': flight['trail'][0]['alt'],
                'heading': flight['trail'][0]['hd'],
                'speed': flight['trail'][0]['spd'],
                'eta': get_dict_value(flight,['time','estimated','arrival'])
            }
            flight_details['flight_number'] = flight_details['flight_number'] if not flight_details['flight_number']=='NA' else flight_details['airline_name']
            flight_details['airports_short'] = re.sub('NA','',flight_details['airports_short'])
    return flight_details

def get_flight_short(requests,flight_index,DEBUG_VERBOSE=False):
    if flight_index is None:
        return None
    url = FLIGHT_SEARCH_HEAD+"flight_id="+flight_index #+FLIGHT_SEARCH_TAIL
    flight=get_request_response(requests,url,DEBUG_VERBOSE)
    if not flight_index in flight.keys():
        return None
    return {FLIGHT_SHORT_KEYS[i]:flight[flight_index][i] for i in range(min(len(FLIGHT_SHORT_KEYS),len(flight[flight_index])))}

def get_time_zone_offset(requests,tz,DEBUG_VERBOSE):
    url=re.sub('APIKEY',os.getenv("TIMEZONEDB_API_KEY"),TIME_ZONE_SEARCH_HEAD)+tz
    tInfo = get_request_response(requests,url,DEBUG_VERBOSE=DEBUG_VERBOSE)
    if tInfo['status'] == 'OK':
        return tInfo['gmtOffset']/3600,tInfo['abbreviation']
    return None,None

def closest_heading(angle):
    compass_points = [0, 45, 90, 135, 180, 225, 270, 315]
    return min(compass_points, key=lambda x: abs((angle - x + 180) % 360 - 180))

