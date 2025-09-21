import os, subprocess,yaml,requests,time
import utility as ut
from datetime import datetime
from zoneinfo import ZoneInfo

VERBOSE_LEVEL=1 #0: no print out; 1: important; 2: everything
WAIT_TIME=15
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

def show_flight(flight_info):
    if VERBOSE_LEVEL>0:
        print(datetime.now(TZ),flight_info)

def clear_flight():
    if VERBOSE_LEVEL>0:
        print(datetime.now(TZ),"Clear")

def main():
    print("Unique serial:",get_serial())
    config = ut.get_config()
    findex_old=None
    while True:
        wait_time = WAIT_TIME
        findex,req_success = ut.get_flights(requests,config['geo_loc'],config.get('altitude'),config.get('heading'),config.get('center_loc'),DEBUG_VERBOSE=VERBOSE_LEVEL>0)
        if findex!=findex_old:
            findex_old = findex
            if findex is None:
                clear_flight()
            else:
                finfo = ut.get_flight_detail(requests,findex,DEBUG_VERBOSE=VERBOSE_LEVEL>0)
                if finfo is not None:                    
                    show_flight(finfo)
                    wait_time=ut.get_est_arrival(finfo['eta'])
        if VERBOSE_LEVEL>1:
            print("\tWaiting",wait_time,"seconds")
        time.sleep(wait_time)

if __name__ == "__main__":
    main()