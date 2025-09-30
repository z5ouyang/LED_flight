import serial,re,time

DEBUG_VERBOSE=True
PORT="/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_B001K6BE-if00-port0"
#PORT="/dev/ttyS1"
BAUDRATE=115200 #9600
SF=b"\xAA\xA5"
GID=b""
SRC=b"\x00\x00"
TID=b"\xB0\xA1"
CRC=b"\x00\x00"
EF=b"\x5A\x55"
# first low byte then high byte
# SF 2 | CTRL 2 | DES 2 | SRC 2 | TID 2 | CMD 2 | ... | CRC 2 | EF 2
# SF fixed: AA A5
# EF fixed: 5A 55
# CTRL 2 bytes = 16bits: 0-10: length; 11: CRC (0 off); 12-15: reserve; thus high byte is 0. and .<8
def send_modbus(tx_data):
    #tx_data = bytes.fromhex("AA A5 08 00 FF FF 00 00 B0 A1 01 00 00 00 5A 55")
    ser = serial.Serial(port=PORT,baudrate=BAUDRATE,parity=serial.PARITY_NONE,stopbits=serial.STOPBITS_ONE,bytesize=serial.EIGHTBITS,timeout=1)
    ser.reset_input_buffer()
    a = ser.write(tx_data)
    time.sleep(0.1)
    rx_data = ser.read_all()
    #rx_data = ser.read(size=18)
    ser.close()
    return rx_data

def get_response(DES,CMD,CNT=b''):
    CTRL = int(8+len(CNT)).to_bytes(2,byteorder='little')
    rx_data = send_modbus(SF+CTRL+DES+SRC+TID+CMD+CNT+CRC+EF)
    rx_len=len(rx_data)
    if not rx_data[:2]==SF:
        if DEBUG_VERBOSE:
            print("SF flag not match!",rx_data[:2])
        return
    if not rx_data[8:10]==TID:
        if DEBUG_VERBOSE:
            print("TID not match!",TID,"vs",rx_data[8:10])
        return
    if not rx_data[12:14]==b"\x00\x00":
        if DEBUG_VERBOSE:
            print("ERROR code:",rx_data[12:14].hex())
        return
    if not rx_data[(rx_len-2):]==EF:
        if DEBUG_VERBOSE:
            print("EF flag not match!",rx_data[16:])
    return rx_data

def get_GID():
    global GID
    GID = get_response(b"\xFF\xFF",b"\x01\x00")[6:8]

def get_W_H():
    rx_data = get_response(GID,b"\x1F\x00")
    if rx_data is None:
        return
    W = int.from_bytes(rx_data[14:16],byteorder='little')
    H = int.from_bytes(rx_data[16:18],byteorder='little')
    return W,H

def get_brightness():
    rx_data = get_response(GID,b"\x37\x00")
    if rx_data is None:
        return
    return int.from_bytes(rx_data[14:16],byteorder='little')

def set_brightness(lum):
    if lum<0 or lum>990:
        if DEBUG_VERBOSE:
            print("Out of brightness rage, set to 500")
        lum=500    
    rx_data = get_response(GID,b"\x38\x00",int(lum).to_bytes(2,byteorder='little'))

def get_text_color():
    rx_data = get_response(GID,b"\x43\x00")
    if rx_data is None:
        return
    color=["","F00","0F0","FF0","00F","F0F","0FF","FFF","000"]
    return color[int(rx_data[14])]

def set_text_color(col):
    if len(col)>3 or not set(col).issubset({'F','0'}):
        if DEBUG_VERBOSE:
            print("Incorrect color code:",col,"\tset it to white")
        col="FFF"
    col = re.sub("F","1",col)[::-1]
    col = "1000".zfill(8) if col=='000' else col.zfill(8)
    col = int(col, 2).to_bytes(1)
    rx_data = get_response(GID,b"\x44\x00",col)

def get_paint_color():
    rx_data = get_response(GID,b"\x4B\x00")
    if rx_data is None:
        return
    color=["","F00","0F0","FF0","00F","F0F","0FF","FFF","000"]
    return color[int(rx_data[14])]

def set_paint_color(col):
    if len(col)>3 or not set(col).issubset({'F','0'}):
        if DEBUG_VERBOSE:
            print("Incorrect color code:",col,"\tset it to white")
        col="FFF"
    col = re.sub("F","1",col)[::-1]
    col = "1000".zfill(8) if col=='000' else col.zfill(8)
    col = int(col, 2).to_bytes(1)
    rx_data = get_response(GID,b"\x4C\x00",col)

def get_font_number():
    rx_data = get_response(GID,b"\x00\x01")
    if rx_data is None:
        return
    return int(rx_data[14])

def clear_screen():
    rx_data = get_response(GID,b"\x00\x02")

def show_text(x,y,w,h,col,txt,multiline=False):
    if len(col)>3 or not set(col).issubset({'F','0'}):
        if DEBUG_VERBOSE:
            print("Incorrect color code:",col,"\tset it to white")
        col="FFF"
    X = int(x).to_bytes(2,byteorder='little')
    Y = int(y).to_bytes(2,byteorder='little')
    W = int(w).to_bytes(2,byteorder='little')
    H = int(h).to_bytes(2,byteorder='little')
    col = re.sub("F","1",col)[::-1]
    col = "1000" if col=='000' else "0"+col
    font_id = '00000000'
    h_align = '00'
    v_align = '00'
    others = '0000' if multiline else '0010'
    FORMAT = int("000000000000"+col+font_id+h_align+v_align+others, 2).to_bytes(4, byteorder='little')
    CNT = int(len(txt)).to_bytes(2,byteorder='little')
    rx_data = get_response(GID,b"\x38\x02",X+Y+W+H+FORMAT+CNT+txt.encode('ascii'))

def show_image(x,y,img):
    #image is a string list with each element is a row, each position in an element is column, 1 means lighting up, 0 means dark
    PG=b''
    PN=0
    for i,r in enumerate(img):
        for j,p in enumerate(r):
            if p=="1":
                PN +=1
                PG += int(x+j).to_bytes(2,byteorder='little')
                PG += int(y+i).to_bytes(2,byteorder='little')
    rx_data = get_response(GID,b"\x04\x02",int(PN).to_bytes(2,byteorder='little')+PG)

def move_frame_left(x,y,w,h):
    X = int(x).to_bytes(2,byteorder='little')
    Y = int(y).to_bytes(2,byteorder='little')
    W = int(w).to_bytes(2,byteorder='little')
    H = int(h).to_bytes(2,byteorder='little')
    rx_data = get_response(GID,b"\x44\x02",X+Y+W+H)

def move_frame_right(x,y,w,h):
    X = int(x).to_bytes(2,byteorder='little')
    Y = int(y).to_bytes(2,byteorder='little')
    W = int(w).to_bytes(2,byteorder='little')
    H = int(h).to_bytes(2,byteorder='little')
    rx_data = get_response(GID,b"\x45\x02",X+Y+W+H)

def move_frame_up(x,y,w,h):
    X = int(x).to_bytes(2,byteorder='little')
    Y = int(y).to_bytes(2,byteorder='little')
    W = int(w).to_bytes(2,byteorder='little')
    H = int(h).to_bytes(2,byteorder='little')
    rx_data = get_response(GID,b"\x46\x02",X+Y+W+H)

def move_frame_down(x,y,w,h):
    X = int(x).to_bytes(2,byteorder='little')
    Y = int(y).to_bytes(2,byteorder='little')
    W = int(w).to_bytes(2,byteorder='little')
    H = int(h).to_bytes(2,byteorder='little')
    rx_data = get_response(GID,b"\x47\x02",X+Y+W+H)

#create_canvas(1,0,0,64,16)
#create_canvas(2,0,16,192,16)
def create_canvas(wid,x,y,w,h):
    WID = int(wid).to_bytes(2,byteorder='little')
    OP = b'\x00\x00'
    X = int(x).to_bytes(2,byteorder='little')
    Y = int(y).to_bytes(2,byteorder='little')
    W = int(w).to_bytes(2,byteorder='little')
    H = int(h).to_bytes(2,byteorder='little')
    STYLE= b'\x00\x00\x00\x00'
    USR=b'\x00\x00\x00\x00'
    rx_data = get_response(GID,b"\x03\x03",WID+OP+X+Y+W+H+STYLE+USR)

def delete_canvas(wid):
    WID = int(wid).to_bytes(2,byteorder='little')
    rx_data = get_response(GID,b"\x05\x03",WID)

#create_txt_programe(2,'0FF',2,5,0,2,200,"Southwest Phoenix-San Diego Boeing 737-7H4")
#create_txt_programe(1,'F0F',4,5,200,4,5,"HA16\nHNL-SAN\nA330",True)
def create_txt_programe(wid,col,en,sp,du,ex,repeat,txt,multiline=False):
    WID = int(wid).to_bytes(2,byteorder='little')
    REV = b'\x00\x00'
    STYLE= b'\x00\x00\x00\x00'
    if len(col)>3 or not set(col).issubset({'F','0'}):
        if DEBUG_VERBOSE:
            print("Incorrect color code:",col,"\tset it to white")
        col="FFF"
    col = re.sub("F","1",col)[::-1]
    col = "1000" if col=='000' else "0"+col
    font_id = '00000000'
    h_align = '00'
    v_align = '00'
    others = '0000' if multiline else '0010'
    FORMAT = int("000000000000"+col+font_id+h_align+v_align+others, 2).to_bytes(4, byteorder='little')
    ENTRY = int(en).to_bytes(2,byteorder='little')
    SPENTRY = int(sp).to_bytes(2,byteorder='little')
    DUENTRY = int(du).to_bytes(2,byteorder='little')
    HIGHLIGHT = b'\x00\x00'
    SPHL = b'\x00\x00'
    DUHL = b'\x00\x00' 
    EXIT = int(ex).to_bytes(2,byteorder='little')
    SPEXIT = SPENTRY
    TIMES = int(repeat).to_bytes(2,byteorder='little')
    CNT = int(len(txt)).to_bytes(2,byteorder='little')
    try:
        rx_data = get_response(GID,b"\x10\x03",WID+REV+STYLE+FORMAT+ENTRY+SPENTRY+DUENTRY+HIGHLIGHT+SPHL+DUHL+EXIT+SPEXIT+TIMES+CNT+txt.encode('ascii'))
    except Exception as e:
        print("Error in create_txt_programe:",txt)
        print(f"\tmessage: {e}")

def delete_programe(wid):
    WID = int(wid).to_bytes(2,byteorder='little')
    OP = b'\x00\xFF'
    rx_data = get_response(GID,b"\x0F\x03",WID+OP)

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
