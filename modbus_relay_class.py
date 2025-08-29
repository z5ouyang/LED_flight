import serial

class modbus_relay:
    def __init__(self,port):
        self.init = False
        self.port = port
        self.baudrate = 9600
        self.style = self.__get_device_style()
        if self.style is None:
            return
        self.addr = self.get_address()
        if self.addr is None or self.addr<1 or self.addr>255:
            print("Error: No address!")
            return
        self.init=True
    def get_address(self):
        print("*** Make sure only ONE modbus device is on! ***\n")
        if self.style in [2]:
            return 255
        try:
            return(self.__get_address_style1())
        except Exception as e:
            print(f"Failed with protocal style 1: Error - {e}")
    def set_address(self,addr):
        if not self.check_init():
            return False        
        if not self.style in [1]:
            print("Cannot set address")
            return False
        print("*** Make sure only ONE modbus device is on! ***\n")
        if addr<1 or addr>254:
            print("Allowed ModBus address is between 1 and 254, not %d"%addr)
            return False
        try:
            addr = self.__set_address_style1(addr)
            if addr >0:
                self.addr=addr
                return True
        except Exception as e:
            print(f"Failed with protocal style 1: Error - {e}")
        return False
    def set_all_open(self):
        if not self.check_init():
            return False
        try:
            if self.style==1:
                return self.__set_all_open_style1()
            elif self.style==2:
                return self.__set_all_open_style2()
        except Exception as e:
            print(f"Failed with protocal style {self.style}: Error - {e}")
        return False
    def set_all_close(self):
        if not self.check_init():
            return False
        try:
            if self.style==1:
                return self.__set_all_close_style1()
            elif self.style==2:
                return self.__set_all_close_style2()
        except Exception as e:
            print(f"Failed with protocal style {self.style}: Error - {e}")
        return False
    def set_one_open(self,ix):
        if not self.check_init():
            return False
        try:
            if self.style==1:
                return self.__set_one_open_style1(ix)
            elif self.style==2:
                return self.__set_one_open_style2(ix)
        except Exception as e:
            print(f"Failed with protocal style {self.style}: Error - {e}")
        return False
    def set_one_close(self,ix):
        if not self.check_init():
            return False
        try:
            if self.style==1:
                return self.__set_one_close_style1(ix)
            elif self.style==2:
                return self.__set_one_close_style2(ix)
        except Exception as e:
            print(f"Failed with protocal style {self.style}: Error - {e}")
        return False
    def get_status(self):
        if not self.check_init():
            return False
        try:
            if self.style==1:
                return self.__get_status_style1()
            elif self.style==2:
                return self.__get_status_style2()
        except Exception as e:
            print(f"Failed with protocal style {self.style}: Error - {e}")
        return False
    def check_init(self):
        if not self.init or self.addr is None:
            print("Error: Object is not initialized correctly!")
            return False
        return True

    ## internal function -----
    def __get_device_style(self):
        if self.__get_address_style1()>0:
            return 1
        if self.__get_status_style2() is not None:
            return 2
        print("Error: unknown modbus style!")
        return
    ## calculate CRC
    @staticmethod
    def __calculate_modbus_crc(data):
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc.to_bytes(2, 'little')
    ## send data to modbus with return data
    def __send_modbus(self,tx_data,return_size,CRC=True):
        if CRC:
            tx_data = tx_data + modbus_relay.__calculate_modbus_crc(tx_data)
        ser = serial.Serial(port=self.port,baudrate=self.baudrate,parity=serial.PARITY_NONE,stopbits=serial.STOPBITS_ONE,bytesize=serial.EIGHTBITS,timeout=1)
        a = ser.write(tx_data)
        rx_data = ser.read(size=return_size)
        ser.close()
        return rx_data
    #get_address_style1("/dev/cu.usbserial-B001K6BE",[9600])
    def __get_baudrate_style1(self):
        tx_data = bytes.fromhex(f"{self.addr:02x} 03 03 E8 00 01")
        rx_data = self.__send_modbus(tx_data,7)
        baudrate=[0,0,4800,9600,19200]
        return baudrate[rx_data[4]]
    def __set_baudrate_style1(self,baudrate):
        tx_data = bytes.fromhex(f"{self.addr:02x} 03 E9 00 01 02 00 {baudrate}")
        rx_data = self.__send_modbus(tx_data,8)
        return tx_data[:6]==rx_data[:6]
    def __set_baudrate_style2(self,baudrate):        
        tx_data = bytes.fromhex(f"FF 00 {baudrate} FF")
        rx_data = self.__send_modbus(tx_data,4,False)
        return tx_data==rx_data
    def __get_address_style1(self):
        tx_data = bytes.fromhex("00 03 00 00 00 01")
        #print("Will test following baudrate:",self.baudrate)
        addr = 0
        rx_data = self.__send_modbus(tx_data,7)
        if len(rx_data)>4 and int(rx_data[4])>0:
            addr = int(rx_data[4])
            #print("baudrate: %d with address: %d"%(self.baudrate,addr))        
        return addr
    def __set_address_style1(self,addr):
        tx_data = bytes.fromhex(f"00 10 00 00 00 01 02 00 {addr:02x}")#
        rx_data = self.__send_modbus(tx_data,11)
        print("The address changed to: %d"%int(rx_data[8]))
        return int(rx_data[8])
    #set_all_open_style1("/dev/cu.usbserial-B001K6BE",1,9600)
    def __set_all_open_style1(self):
        tx_data = bytes.fromhex(f"{self.addr:02x} 0F 00 00 00 08 01 FF")
        rx_data = self.__send_modbus(tx_data,8)
        return tx_data[:6] == rx_data[:6]
    def __set_all_open_style2(self):
        tx_data = bytes.fromhex("A0 FF 01 A2")
        rx_data = self.__send_modbus(tx_data,4,False)
        return rx_data == tx_data
    #set_all_close_style1("/dev/cu.usbserial-B001K6BE",1,9600)
    def __set_all_close_style1(self):
        tx_data = bytes.fromhex(f"{self.addr:02x} 0F 00 00 00 08 01 00")
        rx_data = self.__send_modbus(tx_data,8)
        return tx_data[:6] == rx_data[:6]
    def __set_all_close_style2(self):
        tx_data = bytes.fromhex("A0 FF 00 A1")
        rx_data = self.__send_modbus(tx_data,4,False)
        return rx_data == tx_data
    #set_one_open_style1("/dev/cu.usbserial-B001K6BE",1,2)
    def __set_one_open_style1(self,ix):
        tx_data = bytes.fromhex(f"{self.addr:02x} 05 00 {ix:02x} FF 00")
        rx_data = self.__send_modbus(tx_data,8)
        return tx_data[:6] == rx_data[:6]
    def __set_one_open_style2(self,ix):
        tx_data = bytes.fromhex(f"A0 {ix+1:02x} 01 A2")
        rx_data = self.__send_modbus(tx_data,4,False)
        return rx_data == tx_data
    #set_one_close_style1("/dev/cu.usbserial-B001K6BE",1,2)
    def __set_one_close_style1(self,ix):
        tx_data = bytes.fromhex(f"{self.addr:02x} 05 00 {ix:02x} 00 00")
        rx_data = self.__send_modbus(tx_data,8)
        return tx_data[:6] == rx_data[:6]
    def __set_one_close_style2(self,ix):
        tx_data = bytes.fromhex(f"A0 {ix+1:02x} 00 A1")
        rx_data = self.__send_modbus(tx_data,4,False)
        return rx_data == tx_data
    #get_status_style1("/dev/cu.usbserial-B001K6BE",1)
    def __get_status_style1(self):
        tx_data = bytes.fromhex(f"{self.addr:02x} 01 00 00 00 08")
        rx_data = self.__send_modbus(tx_data,6)
        num_status = rx_data[3]
        if rx_data[:2]!=tx_data[:2]:
            return
        return [_=='1' for _ in f"{num_status:08b}"][::-1]
    def __get_status_style2(self):
        tx_data = bytes.fromhex(f"A1 00 FF A1")
        rx_data = self.__send_modbus(tx_data,19,False)
        if rx_data[:2]!=bytes.fromhex(f"A1 FF"):
            return
        return [_==1 for _ in list(rx_data)[2:-1]]

