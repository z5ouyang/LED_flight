import time, board, terminalio, json, displayio, framebufferio, rgbmatrix, gc, busio, neopixel, re, ssl, wifi, socketpool, rtc, adafruit_ntp
import utility as ut
from random import randrange
from adafruit_matrixportal.matrixportal import MatrixPortal
from adafruit_portalbase.network import HttpError
import adafruit_requests
import adafruit_display_text.label
from digitalio import DigitalInOut
from microcontroller import watchdog as w
from watchdog import WatchDogMode

DEBUG_VERBOSE=False
if not DEBUG_VERBOSE:
    w.timeout=300 # timeout in seconds
    w.mode = WatchDogMode.RESET
FONT=terminalio.FONT
# limited sockets so global:
SOCKET = socketpool.SocketPool(wifi.radio)
REQUESTS = adafruit_requests.Session(SOCKET, ssl.create_default_context())
# Colours and timings
TEXT_COLOR=[0x440844,0x0040B0,0xB08000]#;g = get_text(labels_s);matrixportal.display.root_group = g
PLANE_COLOUR=0x4B0082
# Time in seconds to wait between scrolling one label and the next
PAUSE_BETWEEN_LABEL_SCROLLING=2
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

def get_plane_0():
     return [
        "000001100000",
        "000001100000",
        "000001100000",
        "000011110000",
        "000111111000",
        "001111111100",
        "011111111110",
        "111001100111",
        "000001100000",
        "000001100000",
        "000011110000",
        "000010010000",
    ]

def get_plane_45():
    return ['000000000000',
            '000000000110',
            '000000001110',
            '011111111100',
            '001111111000',
            '000011111000',
            '000011111000',
            '000111111000',
            '111110011000',
            '001100011000',
            '000100001000',
            '000100000000']

def get_plane_90():
    return ["000100000000",
            "000110000000",
            "000111000000",
            "000011100000",
            "110011110000",
            "011111111111",
            "011111111111",
            "110011110000",
            "000011100000",
            "000111000000",
            "000110000000",
            "000100000000"]

def get_plane_135():
    return ["000100001000",
            "000100011000",
            "001100011000",
            "111110111000",
            "000111111000",
            "000011111000",
            "000111111000",
            "011111111000",
            "111111111100",
            "000000001110",
            "000000000110",
            "000000000000"]

def get_plane_180():
    return ["000010010000",
            "000011110000",
            "000001100000",
            "111001100111",
            "011111111110",
            "001111111100",
            "000111111000",
            "000011110000",
            "000001100000",
            "000001100000",
            "000001100000",
            "000001100000"]

def get_plane_225():
    return ["000100001000",
            "000110001000",
            "000110001100",
            "000111011111",
            "000111111000",
            "000111110000",
            "000111111000",
            "000111111110",
            "001111111111",
            "011100000000",
            "011000000000",
            "000000000000"]

def get_plane_270():
    return ["000000001000",
            "000000011000",
            "000000111000",
            "000001110000",
            "000011110011",
            "111111111110",
            "111111111110",
            "000011110011",
            "000001110000",
            "000000111000",
            "000000011000",
            "000000001000"]

def get_plane_315():
    return ["000000000000",
            "011000000000",
            "011100000000",
            "001111111111",
            "000111111110",
            "000111111000",
            "000111110000",
            "000111111000",
            "000111011111",
            "000110001100",
            "000110001000",
            "000100001000"] 

def get_plane_rotate(heading):
    north = [
        "000001100000",
        "000001100000",
        "000001100000",
        "000001100000",
        "000011110000",
        "000111111000",
        "001111111100",
        "011111111110",
        "111001100111",
        "000001100000",
        "000011110000",
        "000010010000",
    ]
    new_image=['000000000000']*12
    angle_rad = math.radians(heading)
    cx=5.5
    cy=5.5
    for x in range(12):
        for y in range(12):
            dx = x - cx
            dy = y - cy
            x_new = min(11,max(0,round(cx + dx * math.cos(angle_rad) - dy * math.sin(angle_rad))))
            y_new = min(11,max(0,round(cy + dx * math.sin(angle_rad) + dy * math.cos(angle_rad))))
            new_image[y_new]= new_image[y_new][:x_new]+north[y][x]+new_image[y_new][(x_new+1):]
    print('",\n"'.join(new_image))
    return new_image

def closest_heading(angle):
    compass_points = [0, 45, 90, 135, 180, 225, 270, 315]
    return min(compass_points, key=lambda x: abs((angle - x + 180) % 360 - 180))

def get_plane_heading(heading):
    palette = displayio.Palette(2)
    palette[0] = 0x000000  # black (off)
    palette[1] = PLANE_COLOUR  # white (on)
    airplane_bmp = displayio.Bitmap(12, 12, 2)
    icon_data = globals()['get_plane_'+str(closest_heading(heading))]()
    for y, row in enumerate(icon_data):
        for x, pixel in enumerate(row):
            if pixel == "1":
                airplane_bmp[x, y] = 1
    tile_grid = displayio.TileGrid(airplane_bmp, pixel_shader=palette,x=51,y=19)
    #g = displayio.Group()
    #g.append(tile_grid)
    return tile_grid

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

def update_flight(flight_short,flight_info,matrixportal):
    #flight = ut.get_flight_short(REQUESTS,geo_loc,flight_info['flight_index'],DEBUG_VERBOSE=DEBUG_VERBOSE)
    #if flight is not None:
    labels_s = [flight_info['flight_number'],flight_info['airports_short'],str(flight_short['altitude'])+' ft']
    g = get_text(labels_s)
    g.append(get_plane_heading(int(flight_short['heading'])))
    matrixportal.display.root_group = g

def show_flight(flight_info,matrixportal,planeG):
    if DEBUG_VERBOSE:
        now = time.localtime()
        print(f"{now.tm_year}-{now.tm_mon:02}-{now.tm_mday:02} {now.tm_hour:02}:{now.tm_min:02}:{now.tm_sec:02}",flight_info)
    plane_animation(matrixportal,planeG)
    display_flight(flight_info,matrixportal)

def clear_flight(geo_loc,flight_index,matrixportal):
    if DEBUG_VERBOSE:
        now = time.localtime()
        print(f"{now.tm_year}-{now.tm_mon:02}-{now.tm_mday:02} {now.tm_hour:02}:{now.tm_min:02}:{now.tm_sec:02}","Clear")
    flight = ut.get_flight_short(REQUESTS,geo_loc,flight_index,DEBUG_VERBOSE=DEBUG_VERBOSE)
    if flight is not None and flight['altitude']<100:
        labels = ["Landed","",str(flight["speed"])+' kts']
    else:
        labels=['Out of','Monitor','Boundary']
    matrixportal.display.root_group = get_text(labels)
    time.sleep(5)
    matrixportal.display.root_group = displayio.Group()

def update_sys_UTC_time():
    ntp = adafruit_ntp.NTP(SOCKET, tz_offset=0)  # UTC
    rtc.RTC().datetime = ntp.datetime

def main():
    update_sys_UTC_time()
    config = ut.get_config()
    mp = get_matrix_portal()
    plane = get_plane_Bmp(mp)
    findex_old=None
    gc.collect()
    while True:
        wait_time = ut.WAIT_TIME
        findex,fshort,req_success = ut.get_flights(REQUESTS,config['geo_loc'],config.get('altitude'),config.get('heading'),
            config.get('center_loc'),config.get('dest'),config.get('speed'),DEBUG_VERBOSE=DEBUG_VERBOSE)
        if req_success:
            w.feed()
        if findex!=findex_old:
            if findex is None:
                clear_flight(config['geo_loc'],findex_old,mp)
            else:
                finfo = ut.get_flight_detail(REQUESTS,findex,DEBUG_VERBOSE=DEBUG_VERBOSE)
                if finfo is not None:                    
                    show_flight(finfo,mp,plane)
                    wait_time=ut.UPDATE_TIME
            findex_old = findex
        elif findex is not None:
            update_flight(fshort,finfo,mp)
            wait_time=ut.UPDATE_TIME
        time.sleep(wait_time)
        gc.collect()
        if DEBUG_VERBOSE:
            print("  Free:", gc.mem_free(), "bytes","  Allocated:", gc.mem_alloc(), "bytes")

main()
#the Matrix Portal S3 running CircuitPython 9.x

