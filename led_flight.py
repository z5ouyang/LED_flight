import os, subprocess,yaml,requests,time
import utility as ut
from datetime import datetime
from zoneinfo import ZoneInfo

VERBOSE_LEVEL=1 #0: no print out; 1: important; 2: everything
WAIT_TIME=15
TZ = ZoneInfo("America/Los_Angeles")

@staticmethod
def calculate_modbus_crc(data):
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc.to_bytes(2, 'little')
## send data to modbus with return data #/dev/ttyUSB0
def send_modbus(port,tx_data,return_size,baudrate=9600,CRC=False):
    if CRC:
        tx_data = tx_data + calculate_modbus_crc(tx_data)
    ser = serial.Serial(port=port,baudrate=baudrate,parity=serial.PARITY_NONE,stopbits=serial.STOPBITS_ONE,bytesize=serial.EIGHTBITS,timeout=1)
    a = ser.write(tx_data)
    rx_data = ser.read(size=return_size)
    ser.close()
    return rx_data

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

def 


def check_wifi():
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