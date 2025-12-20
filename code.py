import os, time, board, terminalio, json, displayio, framebufferio, rgbmatrix, gc, busio, neopixel, re, ssl, wifi, socketpool, rtc, adafruit_ntp,wifi,ipaddress,traceback
import utility as ut
import plane_icon as pi
from random import randrange
from adafruit_matrixportal.matrixportal import MatrixPortal
from adafruit_portalbase.network import HttpError
import adafruit_requests
import adafruit_display_text.label
from digitalio import DigitalInOut
from microcontroller import watchdog as w
import microcontroller as mc
from watchdog import WatchDogMode

DEBUG_VERBOSE=False
if not DEBUG_VERBOSE:
    w.timeout=60 # timeout in seconds
    w.mode = WatchDogMode.RESET

FONT=terminalio.FONT
# limited sockets so global:
SOCKET = socketpool.SocketPool(wifi.radio)
REQUESTS = adafruit_requests.Session(SOCKET, ssl.create_default_context())
# Colours and timings
TEXT_COLOR=[0x440844,0x0040B0,0xFFBF00]#;g = get_text(labels_s);matrixportal.display.root_group = g
PLANE_COLOUR=0x4B0082
# Time in seconds to wait between scrolling one label and the next
PAUSE_BETWEEN_LABEL_SCROLLING=2
# speed plane animation will move - pause time per pixel shift in seconds
PLANE_SPEED=0.04
# speed text labels will move - pause time per pixel shift in seconds
TEXT_SPEED=0.04
# Git sync not called due to write-only system
GIT_COMMIT={'code.py':'','utility.py':'','plane_icon.py':''}
GIT_DATE=''
# Restarted Date
RESTART_DATE=0

def git_sync():
    global GIT_COMMIT
    global GIT_DATE
    now = time.localtime()
    str_date = f"{now.tm_year}-{now.tm_mon:02}-{now.tm_mday:02}"
    if GIT_DATE==str_date:
        return
    GIT_DATE=str_date
    for f in GIT_COMMIT.keys():
        try:
            url = "https://api.github.com/repos/z5ouyang/LED_flight/commits?path="+f
            res = REQUESTS.get(url=url).json()
            if GIT_COMMIT[f] != res[0]['sha']:
                sha = res[0]['sha']
                url = "https://raw.githubusercontent.com/z5ouyang/LED_flight/main/"+f
                res = REQUESTS.get(url=url)
                if res is not None and res.text is not None and len(res.txt)>10:
                    with open(f,'w') as file:
                        file.write(res.txt)
                    GIT_COMMIT[f] = sha
        except Exception as e:
            if DEBUG_VERBOSE:
                print("GITHUB error for",f)
                print(''.join(traceback.format_exception(None, e, e.__traceback__)))

def get_matrix_portal():
    status_light = neopixel.NeoPixel(
        board.NEOPIXEL, 1, brightness=0.1
    )
    # Top level matrixportal object
    matrixportal = MatrixPortal(
        rotation=0,
        debug=False,
        bit_depth=6
    )
    return matrixportal

def check_wifi(matrixportal):
    ping_ip = ipaddress.IPv4Address("8.8.8.8")  # Google's DNS
    tryN = 3
    fwifi = False
    labels = ["WIFI",os.getenv("CIRCUITPY_WIFI_SSID"),'FAILED']
    while tryN>0:
        ping = wifi.radio.ping(ip=ping_ip)
        if ping:
            fwifi=True
            labels = ["Connected","to",os.getenv("CIRCUITPY_WIFI_SSID")]
            break
        tryN -=1
    matrixportal.display.root_group = get_text(labels)
    time.sleep(5)
    return fwifi

def update_sys_time(tz,matrixportal):#tz='America/Los_Angeles'
    #not reliable: https://worldtimeapi.org/api/timezone/
    global RESTART_DATE
    labels = ["TIME ZONE","ERROR",'Use UTC']
    offset = None
    if tz is not None:
        offset,tz_name = ut.get_time_zone_offset(REQUESTS,tz,DEBUG_VERBOSE)
    if offset is None:
        offset=0
        tz_name='UTC'
    else:
        labels = ["TIME ZONE","",tz_name]
    rtc.RTC().datetime = adafruit_ntp.NTP(SOCKET, tz_offset=offset).datetime
    now = time.localtime()
    RESTART_DATE = now.tm_mday
    matrixportal.display.root_group = get_text(labels)
    time.sleep(5)

def display_date_time(time_within,matrixportal):
    if time_within is None:
        return
    global RESTART_DATE
    led_color = [0x996600]
    now = time.localtime()
    ## restart every 3 days at 2~3am 
    if now.tm_hour<3 and now.tm_hour>2 & (now.tm_yday-RESTART_DATE)%365>3:
        RESTART_DATE = now.tm_yday
        mc.reset()
    ####
    if time_within[0]<time_within[1]:
        if time_within[0] <= now.tm_hour < time_within[1]:
            led_color = [0x100800]
    else:
        if time_within[0] <= now.tm_hour or now.tm_hour < time_within[1]:
            led_color = [0x100800]
    month_names = ["","Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    weekday_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    labels = [month_names[now.tm_mon]+" "+str(now.tm_mday),"      "+weekday_names[now.tm_wday],f"{now.tm_hour:02}:{now.tm_min:02}"]
    matrixportal.display.root_group = get_text(labels,led_color*3)

def get_BMP(icon_data,BMP):
    for y, row in enumerate(icon_data):
        for x, pixel in enumerate(row):
            if pixel == "1":
                BMP[x, y] = 1

def get_plane_Bmp(matrixportal):
    # Little plane to scroll across when we find a flight overhead
    planeBmp = displayio.Bitmap(12, 12, 2)
    planePalette = displayio.Palette(2)
    planePalette[1] = PLANE_COLOUR
    planePalette[0] = 0x000000
    icon_data = pi.get_plane_horizontal()
    get_BMP(pi.get_plane_horizontal(),planeBmp)
    planeTg= displayio.TileGrid(planeBmp, pixel_shader=planePalette)
    planeG=displayio.Group(x=matrixportal.display.width+12,y=10)
    planeG.append(planeTg)
    return planeG

def get_plane_heading(heading):
    palette = displayio.Palette(2)
    palette[0] = 0x000000  # black (off)
    palette[1] = PLANE_COLOUR  # white (on)
    airplane_bmp = displayio.Bitmap(12, 12, 2)
    get_BMP(getattr(pi,'get_plane_'+str(ut.closest_heading(heading)))(),airplane_bmp)
    tile_grid = displayio.TileGrid(airplane_bmp, pixel_shader=palette,x=51,y=19)
    return tile_grid

def plane_animation(matrixportal,planeG):
    matrixportal.display.root_group = planeG
    for i in range(matrixportal.display.width+24,-12,-1):
            planeG.x=i
            time.sleep(PLANE_SPEED)

def get_text(label_s,text_col=None):
    # We can fit three rows of text on a panel, so one label for each. We'll change their text as needed
    if text_col is None:
        text_col = TEXT_COLOR
    g = displayio.Group()
    for i in range(len(label_s)):
        g.append(adafruit_display_text.label.Label(
            FONT,color=text_col[i],x=1,y=i*10+5,
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

def update_flight(flight_short,matrixportal,flip_east_west=None):
    if flight_short is None or flight_short['heading'] is None or flight_short['heading']=='':
        return
    labels_s = [flight_short['flight_number'],flight_short['ori']+'-'+flight_short['dest'],str(flight_short['altitude'])+' ft']
    g = get_text(labels_s)
    heading = (360 - int(flight_short['heading']))%360 if flip_east_west else int(flight_short['heading'])
    g.append(get_plane_heading(heading))
    matrixportal.display.root_group = g

def show_flight(flight_info,matrixportal,planeG):
    if DEBUG_VERBOSE:
        now = time.localtime()
        print(f"{now.tm_year}-{now.tm_mon:02}-{now.tm_mday:02} {now.tm_hour:02}:{now.tm_min:02}:{now.tm_sec:02}",flight_info)
    plane_animation(matrixportal,planeG)
    display_flight(flight_info,matrixportal)

def clear_flight(flight_index,matrixportal):
    if DEBUG_VERBOSE:
        now = time.localtime()
        print(f"{now.tm_year}-{now.tm_mon:02}-{now.tm_mday:02} {now.tm_hour:02}:{now.tm_min:02}:{now.tm_sec:02}","Clear")
    flight = ut.get_flight_short(REQUESTS,flight_index,DEBUG_VERBOSE=DEBUG_VERBOSE)
    if flight is not None and flight['altitude']<ut.LANDING_ALTITUDE:
        labels = ["Landed","",str(flight["speed"])+' kts']
    else:
        labels=['Out of','Monitor','Boundary']
    matrixportal.display.root_group = get_text(labels)
    time.sleep(5)
    matrixportal.display.root_group = displayio.Group()
    #displayio.release_displays()

def main():
    mp = get_matrix_portal()
    if not check_wifi(mp):
        return
    config = ut.get_config()
    update_sys_time(config.get('time_zone'),mp)
    plane = get_plane_Bmp(mp)
    findex_old=None
    finfo=None
    flight_followed=ut.MAX_FOLLOW_PLAN
    gc.collect()
    while True:
        wait_time = ut.WAIT_TIME
        findex,fshort,req_success = ut.get_flights(REQUESTS,config['geo_loc'],config.get('altitude'),config.get('heading'),
            config.get('center_loc'),config.get('dest'),config.get('speed'),DEBUG_VERBOSE=DEBUG_VERBOSE)
        if req_success:
            w.feed()
        ## follow the previous plane when it moved outside the boundary but no new plane entered
        if findex is None and findex_old is not None and flight_followed>0:
            if DEBUG_VERBOSE:
                print("=== Follow the previous plane which is out of boundary ===")
                print(findex,":",findex_old,":",flight_followed)
            fshort = ut.get_flight_short(REQUESTS,findex_old,DEBUG_VERBOSE=DEBUG_VERBOSE)
            findex = findex_old
            if fshort is not None and fshort['altitude']<ut.LANDING_ALTITUDE:
                flight_followed=0
            flight_followed -=1
        ##
        if findex!=findex_old:
            if findex is None:
                clear_flight(findex_old,mp)
                display_date_time(config.get("display_time_night"),mp)                
            else:
                finfo = ut.get_flight_detail(REQUESTS,findex,DEBUG_VERBOSE=DEBUG_VERBOSE)
                if finfo is not None:                    
                    show_flight(finfo,mp,plane)
                    wait_time=ut.UPDATE_TIME
            findex_old = findex
            flight_followed=ut.MAX_FOLLOW_PLAN
        elif findex is not None:
            if DEBUG_VERBOSE:
                print(findex,":",findex_old)
            update_flight(fshort,mp,config.get('flip_east_west'))
            wait_time=ut.UPDATE_TIME
        else:
            display_date_time(config.get("display_time_night"),mp)
        time.sleep(wait_time)
        gc.collect()
        if DEBUG_VERBOSE:
            print("  Free:", gc.mem_free(), "bytes","  Allocated:", gc.mem_alloc(), "bytes")

try:
    main()
except Exception as e:
    error_text = ''.join(traceback.format_exception(None, e, e.__traceback__))
    now = time.localtime()
    print("========",f"{now.tm_year}-{now.tm_mon:02}-{now.tm_mday:02} {now.tm_hour:02}:{now.tm_min:02}:{now.tm_sec:02}","========\n")
    print(error_text)

#time.sleep(300)
#the Matrix Portal S3 running CircuitPython 9.x
