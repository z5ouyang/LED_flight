import os, subprocess,requests,time,gc
import utility as ut
import modbus_led as ml
import plane_icon as pi
from datetime import datetime
from zoneinfo import ZoneInfo

DEBUG_VERBOSE=True #0: no print out; 1: important; 2: everything
TZ = ZoneInfo('America/Los_Angeles')
LED_CURR_BRIGHTNESS=500
LED_DAY_BRIGHTNESS=500
LED_NIGHT_BRIGHTNESS=10
PLANE_SPEED=0.001
SHORT_CANVAS=1
LONG_CANVAS=2
PLANE_CANVAS=3
FLIP_EAST_WEST=False

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

def get_wifi_ssid():
    try:
        ssid = subprocess.check_output(['iwgetid', '-r']).decode().strip()
        return ssid if ssid else "Not connected to Wi-Fi"
    except subprocess.CalledProcessError:
        return "Wi-Fi SSID not found"

def ping_google(tryN=3):
    while tryN>0:
        tryN -=1
        try:
            output = subprocess.check_output(['ping', '-c', '1', '8.8.8.8'], stderr=subprocess.STDOUT).decode()
            return True
        except subprocess.CalledProcessError as e:
            if DEBUG_VERBOSE:
                print(f"Ping failed: {e.output.decode()}")
    return False

def check_wifi():
    fwifi = ping_google()
    if fwifi:
        ml.show_text(0,0,192,32,'FFF',"Connected to\n%s"%get_wifi_ssid(),multiline=True)
    else:
        ml.show_text(0,0,192,32,'FFF',"WIFI\nFailed",multiline=True)
    time.sleep(5)
    return fwifi

def set_time_zone(tz):
    global TZ
    try:
        TZ = ZoneInfo(tz)
    except subprocess.CalledProcessError as e:
        if DEBUG_VERBOSE:
            print(f"Ping failed: {e.output.decode()}")
    ml.show_text(0,0,192,32,'FFF',"Local Time Zone\n%s"%datetime.now(TZ).strftime('%Z'),multiline=True)
    time.sleep(5)

def check_brightness(night_time):
    global LED_CURR_BRIGHTNESS
    dt = datetime.now(TZ)
    bNight = (night_time[0]<night_time[1] and night_time[0] <= dt.hour < night_time[1]) or (night_time[0]>night_time[1] and (night_time[0] <= dt.hour or dt.hour< night_time[1]))
    if bNight and LED_CURR_BRIGHTNESS!=LED_NIGHT_BRIGHTNESS:
        if DEBUG_VERBOSE:
            print("Night Brightness")
        LED_CURR_BRIGHTNESS=LED_NIGHT_BRIGHTNESS
        ml.set_brightness(LED_NIGHT_BRIGHTNESS)
    elif not bNight and LED_CURR_BRIGHTNESS!=LED_DAY_BRIGHTNESS:
        if DEBUG_VERBOSE:
            print("Day Brightness")
        LED_CURR_BRIGHTNESS=LED_DAY_BRIGHTNESS
        ml.set_brightness(LED_DAY_BRIGHTNESS)

def display_date_time():
    dt = datetime.now(TZ)
    ml.show_text(0,0,64,16,'FF0',"%s %s"%(dt.strftime('%b'),dt.day),font=4)
    ml.show_text(128,0,64,16,'FF0',dt.strftime('%a'),font=4)
    ml.show_text(64,16,64,16,'FF0',dt.strftime('%H:%M'),font=4)
    #ml.show_text(0,0,192,32,"FF0","%s %d\t%s\n\t\t%s"%(dt.strftime('%b'),dt.day,dt.strftime('%a'),dt.strftime('%H:%M')),multiline=True)

def plane_animation_old():
    img = pi.get_plane_horizontal()
    w = h = len(img)
    H = 32
    W = 192
    h1 = int((H-h)/2)
    h2 = H-h-h1
    for i in range(h1):
        img.insert(0,"0"*w)
    for i in range(h2):
        img.append("0"*w)
    ml.show_image(W-w,0,img)
    for i in range(W):
        ml.move_frame_left(max(0,W-w-i),0,w,H)

def plane_animation(heading=None):
    heading = heading if heading is None else 270
    if heading<180:
        ml.create_img_program(PLANE_CANVAS,2,0,0,2,0,2)
    else:
        ml.create_img_program(PLANE_CANVAS,1,0,0,3,0,1)
    time.sleep(2)

def display_alt_sp(fInfo):
    x=64
    heading = (360 - int(fInfo['heading']))%360 if FLIP_EAST_WEST else int(fInfo['heading'])
    img = getattr(pi,'get_plane_'+str(ut.closest_heading(heading)))()
    w = len(img)
    ml.show_image(x,2,img)
    ml.show_text(x+w+2,0,190-x-w,16,'FF0',"%sft %skts"%(str(fInfo['altitude']),str(fInfo['speed'])),h_align='00',font=3)

def show_flight(flight_info):
    if DEBUG_VERBOSE:
        print(datetime.now(TZ),flight_info)
    ml.delete_programe(SHORT_CANVAS)
    ml.delete_programe(LONG_CANVAS)
    ml.clear_screen()
    plane_animation(flight_info['heading'])
    labels_s = [flight_info['flight_number'],flight_info['airports_short'],flight_info['aircraft_code']]
    labels_l = [flight_info['airline_name'],flight_info['airports_long'],flight_info['aircraft_model']]
    ml.create_txt_programe(SHORT_CANVAS,'F0F',4,5,200,4,50,'\n'.join(labels_s),multiline=True,font=4)
    ml.create_txt_programe(LONG_CANVAS,'F0F',2,5,0,2,20,' '.join(labels_l),h_align='00',font=3)
    display_alt_sp(flight_info)
    time.sleep(5)

def clear_flight(flight_index):
    if DEBUG_VERBOSE:
        print(datetime.now(TZ),"Clear")
    ml.delete_programe(SHORT_CANVAS)
    ml.delete_programe(LONG_CANVAS)
    flight = ut.get_flight_short(requests,flight_index,DEBUG_VERBOSE=DEBUG_VERBOSE)
    ml.show_text(0,0,192,16,"F0F","%s %s-%s %s"%(flight['flight_number'],flight['ori'],flight['dest'],flight['aircraft_type']),font=4)
    if flight is not None and flight['altitude']<ut.LANDING_ALTITUDE:
        ml.show_text(0,16,192,16,"0FF","Landed\t"+str(flight["speed"])+' kts',font=3)
    else:
        ml.show_text(0,16,192,16,"0FF",'Out of Monitor Boundary',font=3)
    time.sleep(5)
    ml.clear_screen()

def init(config):
    global FLIP_EAST_WEST
    try:
        ml.get_GID()
        ml.set_text_color('FF0')
        ml.delete_programe(SHORT_CANVAS)
        ml.delete_programe(LONG_CANVAS)
        ml.create_canvas(SHORT_CANVAS,0,0,64,16)
        ml.create_canvas(LONG_CANVAS,0,16,192,16)
        ml.create_canvas(PLANE_CANVAS,0,0,192,32)
        FLIP_EAST_WEST = False if config.get('flip_east_west') is None else config.get('flip_east_west')
        ml.DEBUG_VERBOSE=DEBUG_VERBOSE
        if not check_wifi():
            return False
        set_time_zone(config.get('time_zone'))
        ml.clear_screen()
    except subprocess.CalledProcessError as e:
        if DEBUG_VERBOSE:
            print(f"LED controller failed: {e.output.decode()}")
        return False
    return True

def main():
    config = ut.get_config()
    if not init(config):
        return
    findex_old=None
    finfo=None
    flight_followed=ut.MAX_FOLLOW_PLAN
    gc.collect()
    while True:
        wait_time = ut.WAIT_TIME
        check_brightness(config.get("display_time_night"))
        findex,fshort,req_success = ut.get_flights(requests,config['geo_loc'],config.get('altitude'),config.get('heading'),
            config.get('center_loc'),config.get('dest'),config.get('speed'),DEBUG_VERBOSE=DEBUG_VERBOSE)
        ## follow the previous plane when it moved outside the boundary but no new plane entered
        if findex is None and findex_old is not None and flight_followed>0:
            if DEBUG_VERBOSE:
                print("=== Follow the previous plane which is out of boundary ===")
                print(findex,":",findex_old,":",flight_followed)
            fshort = ut.get_flight_short(requests,findex_old,DEBUG_VERBOSE=DEBUG_VERBOSE)
            findex = findex_old
            if fshort['altitude']<ut.LANDING_ALTITUDE:
                flight_followed=0
            flight_followed -=1
        ##
        if findex!=findex_old:
            if findex is None:
                clear_flight(findex_old)
                display_date_time()                
            else:
                finfo = ut.get_flight_detail(requests,findex,DEBUG_VERBOSE=DEBUG_VERBOSE)
                if finfo is not None:                    
                    show_flight(finfo)
                    wait_time=ut.UPDATE_TIME
            findex_old = findex
            flight_followed=ut.MAX_FOLLOW_PLAN
        elif findex is not None:
            if DEBUG_VERBOSE:
                print(findex,":",findex_old)
            display_alt_sp(fshort)
            wait_time=ut.UPDATE_TIME
        else:
            display_date_time()
        time.sleep(wait_time)
        gc.collect()
        #if DEBUG_VERBOSE:
        #    print("  Free:", gc.mem_free(), "bytes","  Allocated:", gc.mem_alloc(), "bytes")

if __name__ == "__main__":
    main()