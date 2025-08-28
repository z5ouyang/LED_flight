import os, subprocess,yaml,requests,time
from datetime import datetime
from zoneinfo import ZoneInfo

VERBOSE_LEVEL=1 #0: no print out; 1: important; 2: everything
WAIT_TIME=15
FLIGHT_SEARCH_HEAD="https://data-cloud.flightradar24.com/zones/fcgi/feed.js?bounds="
FLIGHT_SEARCH_TAIL="&faa=1&satellite=1&mlat=1&flarm=1&adsb=1&gnd=0&air=1&vehicles=0&estimated=0&maxage=14400&gliders=0&stats=0&ems=1&limit=1"
FLIGHT_LONG_DETAILS_HEAD="https://data-live.flightradar24.com/clickhandler/?flight="
HTTP_HEADERS = {
     "User-Agent": "Mozilla/5.0",
     "cache-control": "no-store, no-cache, must-revalidate, post-check=0, pre-check=0",
     "accept": "application/json"
}
TZ = ZoneInfo("America/Los_Angeles")

def get_serial():
    strSerial = "/proc/device-tree/serial-number"
    if os.path.isfile(strSerial):
        with open(strSerial,'r') as f:
            return f.read().strip()
    strSerial = "/proc/cpuinfo"
    if os.path.isfile(strSerial):
        with open(strSerial,'r') as f:
            for line in f:
                if line.strip().startswith('Serial'):
                    return line.strip().split(':')[1].strip()
    try:
        cmd = "system_profiler SPHardwareDataType | awk '/Serial Number/ {print $4}'"
        result = subprocess.run(cmd, stdout=subprocess.PIPE, shell=True, check=True)
        return result.stdout.decode().strip()
    except:
        pass
    #except Exception as e:
    #    return f"Error: {e}"
    return "0000000000000000"

def get_config():
    strConfig = 'private.yml'
    config=None
    if os.path.isfile(strConfig):
        with open(strConfig,'r') as f:
            config=yaml.safe_load(f)
    return config

def bool_between(v,r):
    if r is None:
        return True
    return (v>r[0] and v<r[1])

def get_flights(geoloc,altitude=None,heading=None):
    url = FLIGHT_SEARCH_HEAD+",".join(str(i) for i in geoloc)+FLIGHT_SEARCH_TAIL
    flight_index=None
    try:
        flight=requests.get(url=url,headers=HTTP_HEADERS).json()
    except:
        if VERBOSE_LEVEL>0:
            print("Cannot get flight number from url: %s"%url)
        return None
    if len(flight)>2:
        for k,v in flight.items():
            if VERBOSE_LEVEL>1 and isinstance(v,list) and len(v)>13:
                print("\t",v) 
            if isinstance(v,list) and len(v)>13 and bool_between(v[4],altitude) and bool_between(v[3],heading):
               flight_index = k
               break
    return flight_index

def get_dict_value(d,keys):
    if d is None:
        return 'Unknown'
    if len(keys)==0:
        return d
    return get_dict_value(d.get(keys[0]),keys[1:])

def get_est_arrival(eta):
    if eta=='Unknown':
        return 5
    return min(75,max(5,int(eta-time.time()-50)))

def get_flight_detail(flight_index):
    flight_details=None
    try:
        flight=requests.get(url=FLIGHT_LONG_DETAILS_HEAD+flight_index,headers=HTTP_HEADERS).json()
        flight_details={
            'flight_number': get_dict_value(flight,['identification','number','default']),
            'airline_name': get_dict_value(flight,['airline','name']),
            'airports_short': get_dict_value(flight,['airport','origin','code','iata']) +" - " + get_dict_value(flight,['airport','destination','code','iata']),
            'airports_long': get_dict_value(flight,['airport','origin','position','region','city']) +" - " + get_dict_value(flight,['airport','destination','position','region','city']),
            'aircraft_code': get_dict_value(flight,['aircraft','model','code']),
            'aircraft_model': get_dict_value(flight,['aircraft','model','text']),
            'eta': get_dict_value(flight,['time','estimated','arrival'])
        }
    except:
        if VERBOSE_LEVEL>0:
            print("Cannot get flight details from url: "+FLIGHT_LONG_DETAILS_HEAD+flight_index)
        return None
    return flight_details

def show_flight(flight_info):
    if VERBOSE_LEVEL>0:
        print(datetime.now(TZ),flight_info)

def clear_flight():
    if VERBOSE_LEVEL>0:
        print(datetime.now(TZ),"Clear")

def main():
    print("Unique serial:",get_serial())
    config = get_config()
    findex_old=None
    while True:
        wait_time = WAIT_TIME
        findex = get_flights(config['geo_loc'],config.get('altitude'),config.get('heading'))
        if findex!=findex_old:
            findex_old = findex
            if findex is None:
                clear_flight()
            else:
                finfo = get_flight_detail(findex)
                if finfo is not None:                    
                    show_flight(finfo)
                    wait_time=get_est_arrival(finfo['eta'])
        if VERBOSE_LEVEL>1:
            print("\tWaiting",wait_time,"seconds")
        time.sleep(wait_time)

if __name__ == "__main__":
    main()