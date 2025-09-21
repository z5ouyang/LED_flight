import time, board, terminalio, json, displayio, framebufferio, rgbmatrix, gc, busio, neopixel, re, ssl, wifi, socketpool, rtc, adafruit_ntp, traceback
from random import randrange
from adafruit_matrixportal.matrixportal import MatrixPortal
from adafruit_portalbase.network import HttpError
import adafruit_requests
import adafruit_display_text.label
from digitalio import DigitalInOut
from microcontroller import watchdog as w
from watchdog import WatchDogMode
w.timeout=300 # timeout in seconds
w.mode = WatchDogMode.RESET
#CIRCUITPY_WIFI_SSID = "..."
#CIRCUITPY_WIFI_PASSWORD = "..."
#
FONT=terminalio.FONT

DEBUG_VERBOSE=False
WAIT_TIME=15
WAIT_TIME_MAX=75
FLIGHT_SEARCH_HEAD="https://data-cloud.flightradar24.com/zones/fcgi/feed.js?bounds="
FLIGHT_SEARCH_TAIL="&faa=1&satellite=1&mlat=1&flarm=1&adsb=1&gnd=0&air=1&vehicles=0&estimated=0&maxage=14400&gliders=0&stats=0&ems=1&limit=1"
FLIGHT_LONG_DETAILS_HEAD="https://data-live.flightradar24.com/clickhandler/?flight="
HTTP_HEADERS = {
     "User-Agent": "Mozilla/5.0",
     "cache-control": "no-store, no-cache, must-revalidate, post-check=0, pre-check=0",
     "accept": "application/json"
}
# limited sockets so global:
SOCKET = socketpool.SocketPool(wifi.radio)
REQUESTS = adafruit_requests.Session(SOCKET, ssl.create_default_context())
# Colours and timings
TEXT_COLOR=[0x440844,0x0040B0,0xB08000]#;g = get_text(labels_s);matrixportal.display.root_group = g
PLANE_COLOUR=0x4B0082
# Time in seconds to wait between scrolling one label and the next
PAUSE_BETWEEN_LABEL_SCROLLING=3
# speed plane animation will move - pause time per pixel shift in seconds
PLANE_SPEED=0.04
# speed text labels will move - pause time per pixel shift in seconds
TEXT_SPEED=0.04

def get_matrix_portal():
    status_light = neopixel.NeoPixel(
        board.NEOPIXEL, 1, brightness=0.2
    )
    # Top level matrixportal object
    matrixportal = MatrixPortal(
        headers=HTTP_HEADERS,
        rotation=0,
        debug=False
    )
    return matrixportal

def get_plane_Bmp(matrixportal):
    # Little plane to scroll across when we find a flight overhead
    planeBmp = displayio.Bitmap(12, 12, 2)
    planePalette = displayio.Palette(2)
    planePalette[1] = PLANE_COLOUR
    planePalette[0] = 0x000000
    planeBmp[6,0]=planeBmp[6,1]=planeBmp[5,1]=planeBmp[4,2]=planeBmp[5,2]=planeBmp[6,2]=1
    planeBmp[9,3]=planeBmp[5,3]=planeBmp[4,3]=planeBmp[3,3]=1
    planeBmp[1,4]=planeBmp[2,4]=planeBmp[3,4]=planeBmp[4,4]=planeBmp[5,4]=planeBmp[6,4]=planeBmp[7,4]=planeBmp[8,4]=planeBmp[9,4]=1
    planeBmp[1,5]=planeBmp[2,5]=planeBmp[3,5]=planeBmp[4,5]=planeBmp[5,5]=planeBmp[6,5]=planeBmp[7,5]=planeBmp[8,5]=planeBmp[9,5]=1
    planeBmp[9,6]=planeBmp[5,6]=planeBmp[4,6]=planeBmp[3,6]=1
    planeBmp[6,9]=planeBmp[6,8]=planeBmp[5,8]=planeBmp[4,7]=planeBmp[5,7]=planeBmp[6,7]=1
    planeTg= displayio.TileGrid(planeBmp, pixel_shader=planePalette)
    planeG=displayio.Group(x=matrixportal.display.width+12,y=10)
    planeG.append(planeTg)
    return planeG

def plane_animation(matrixportal,planeG):
    matrixportal.display.root_group = planeG
    for i in range(matrixportal.display.width+24,-12,-1):
            planeG.x=i
            time.sleep(PLANE_SPEED)

def get_text(label_s):
    # We can fit three rows of text on a panel, so one label for each. We'll change their text as needed
    g = displayio.Group()
    for i in range(len(label_s)):
        g.append(adafruit_display_text.label.Label(
            FONT,color=TEXT_COLOR[i],x=1,y=i*10+5,
            text=label_s[i]))
    return g

def text_scroll(line,matrixportal):
    line.x=matrixportal.display.width
    for i in range(matrixportal.display.width+1,0-line.bounding_box[2],-1):
        line.x=i
        time.sleep(TEXT_SPEED)

def display_flight(flight_info,matrixportal):
    labels_s = [flight_info['flight_number'],flight_info['airports_short'],flight_info['aircraft_code']]
    labels_l = [flight_info['airline_name'],flight_info['airports_long'],flight_info['aircraft_model']]
    g = get_text(labels_s)
    matrixportal.display.root_group = g
    for i in range(len(labels_l)):
        time.sleep(PAUSE_BETWEEN_LABEL_SCROLLING)
        g[i].text = labels_l[i]
        text_scroll(g[i],matrixportal)
        g[i].text=labels_s[i]
        g[i].x=1

def get_config():
    with open('private.json') as f:
        config = json.load(f)
    return config

def bool_between(v,r):
    if r is None:
        return True
    return (v>r[0] and v<r[1])

def get_request_response(url):
    try:       
        response = REQUESTS.get(url=url,headers=HTTP_HEADERS)
        response_json = response.json()
        response.close()
        gc.collect()
    except Exception as e:
        if DEBUG_VERBOSE:
            traceback.print_exception(e)
        return None
    return response_json

def get_flights(geoloc,altitude=None,heading=None):
    url = FLIGHT_SEARCH_HEAD+",".join(str(i) for i in geoloc)+FLIGHT_SEARCH_TAIL
    flight_index=None
    flight=get_request_response(url)
    if DEBUG_VERBOSE:
        print(flight)
    if len(flight)>0:
        w.feed()
    if len(flight)>2:
        for k,v in flight.items():
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
    return min(WAIT_TIME_MAX,max(5,int(eta-time.time()-50)))

def get_flight_detail(flight_index):
    flight_details=None
    flight=get_request_response(FLIGHT_LONG_DETAILS_HEAD+flight_index)
    if flight is not None:
            flight_details={
                'flight_number': get_dict_value(flight,['identification','number','default']),
                'airline_name': get_dict_value(flight,['airline','name']),
                'airports_short': get_dict_value(flight,['airport','origin','code','iata']) +"-" + get_dict_value(flight,['airport','destination','code','iata']),
                'airports_long': get_dict_value(flight,['airport','origin','position','region','city']) +"-" + get_dict_value(flight,['airport','destination','position','region','city']),
                'aircraft_code': get_dict_value(flight,['aircraft','model','code']),
                'aircraft_model': get_dict_value(flight,['aircraft','model','text']),
                'eta': get_dict_value(flight,['time','estimated','arrival'])
            }
    return flight_details

def show_flight(flight_info,matrixportal,planeG):
    if DEBUG_VERBOSE:
        now = time.localtime()
        print(f"{now.tm_year}-{now.tm_mon:02}-{now.tm_mday:02} {now.tm_hour:02}:{now.tm_min:02}:{now.tm_sec:02}",flight_info)
    plane_animation(matrixportal,planeG)
    display_flight(flight_info,matrixportal)

def clear_flight(matrixportal):
    if DEBUG_VERBOSE:
        now = time.localtime()
        print(f"{now.tm_year}-{now.tm_mon:02}-{now.tm_mday:02} {now.tm_hour:02}:{now.tm_min:02}:{now.tm_sec:02}","Clear")
    matrixportal.display.root_group = displayio.Group()

def update_sys_UTC_time():
    ntp = adafruit_ntp.NTP(SOCKET, tz_offset=0)  # UTC
    rtc.RTC().datetime = ntp.datetime

def main():
    update_sys_UTC_time()
    config = get_config()
    mp = get_matrix_portal()
    plane = get_plane_Bmp(mp)
    findex_old=None
    gc.collect()
    while True:
        wait_time = WAIT_TIME
        findex = get_flights(config['geo_loc'],config.get('altitude'),config.get('heading'))
        if findex!=findex_old:
            findex_old = findex
            if findex is None:
                clear_flight(mp)
            else:
                finfo = get_flight_detail(findex)
                if finfo is not None:                    
                    show_flight(finfo,mp,plane)
                    wait_time=get_est_arrival(finfo['eta'])
        time.sleep(wait_time)
        gc.collect()
        if DEBUG_VERBOSE:
            print("  Free:", gc.mem_free(), "bytes","  Allocated:", gc.mem_alloc(), "bytes")

main()
#the Matrix Portal S3 running CircuitPython 9.x