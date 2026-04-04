from __future__ import annotations

import logging

import serial

logger = logging.getLogger(__name__)


class modbus_relay:
    def __init__(self, port: str) -> None:
        self.init: bool = False
        self.port: str = port
        self.baudrate: int = 9600
        self.style: int | None = self.__get_device_style()
        if self.style is None:
            return
        self.addr: int | None = self.get_address()
        if self.addr is None or self.addr < 1 or self.addr > 255:
            logger.error("No address!")
            return
        self.init = True

    def get_address(self) -> int | None:
        logger.warning("*** Make sure only ONE modbus device is on! ***")
        if self.style in [2]:
            return 255
        try:
            return self.__get_address_style1()
        except (serial.SerialException, OSError) as e:
            logger.error("Failed with protocol style 1: Error - %s", e)
        return None

    def set_address(self, addr: int) -> bool:
        if not self.check_init():
            return False
        if self.style not in [1]:
            logger.error("Cannot set address")
            return False
        logger.warning("*** Make sure only ONE modbus device is on! ***")
        if addr < 1 or addr > 254:
            logger.error(
                "Allowed ModBus address is between 1 and 254, not %d",
                addr,
            )
            return False
        try:
            addr = self.__set_address_style1(addr)
            if addr > 0:
                self.addr = addr
                return True
        except (serial.SerialException, OSError) as e:
            logger.error("Failed with protocol style 1: Error - %s", e)
        return False

    def set_all_open(self) -> bool:
        if not self.check_init():
            return False
        try:
            if self.style == 1:
                return self.__set_all_open_style1()
            elif self.style == 2:
                return self.__set_all_open_style2()
        except (serial.SerialException, OSError) as e:
            logger.error(
                "Failed with protocol style %s: Error - %s",
                self.style,
                e,
            )
        return False

    def set_all_close(self) -> bool:
        if not self.check_init():
            return False
        try:
            if self.style == 1:
                return self.__set_all_close_style1()
            elif self.style == 2:
                return self.__set_all_close_style2()
        except (serial.SerialException, OSError) as e:
            logger.error(
                "Failed with protocol style %s: Error - %s",
                self.style,
                e,
            )
        return False

    def set_one_open(self, ix: int) -> bool:
        if not self.check_init():
            return False
        try:
            if self.style == 1:
                return self.__set_one_open_style1(ix)
            elif self.style == 2:
                return self.__set_one_open_style2(ix)
        except (serial.SerialException, OSError) as e:
            logger.error(
                "Failed with protocol style %s: Error - %s",
                self.style,
                e,
            )
        return False

    def set_one_close(self, ix: int) -> bool:
        if not self.check_init():
            return False
        try:
            if self.style == 1:
                return self.__set_one_close_style1(ix)
            elif self.style == 2:
                return self.__set_one_close_style2(ix)
        except (serial.SerialException, OSError) as e:
            logger.error(
                "Failed with protocol style %s: Error - %s",
                self.style,
                e,
            )
        return False

    def get_status(self) -> list[bool] | None:
        if not self.check_init():
            return None
        try:
            if self.style == 1:
                return self.__get_status_style1()
            elif self.style == 2:
                return self.__get_status_style2()
        except (serial.SerialException, OSError) as e:
            logger.error(
                "Failed with protocol style %s: Error - %s",
                self.style,
                e,
            )
        return None

    def check_init(self) -> bool:
        if not self.init or self.addr is None:
            logger.error("Object is not initialized correctly!")
            return False
        return True

    def __get_device_style(self) -> int | None:
        if self.__get_address_style1() > 0:
            return 1
        if self.__get_status_style2() is not None:
            return 2
        logger.error("Unknown modbus style!")
        return None

    @staticmethod
    def __calculate_modbus_crc(data: bytes) -> bytes:
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc.to_bytes(2, "little")

    def __send_modbus(self, tx_data: bytes, return_size: int, CRC: bool = True) -> bytes:
        if CRC:
            tx_data = tx_data + modbus_relay.__calculate_modbus_crc(tx_data)
        ser = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS,
            timeout=1,
        )
        ser.write(tx_data)
        rx_data = ser.read(size=return_size)
        ser.close()
        return rx_data

    def __get_baudrate_style1(self) -> int:
        tx_data = bytes.fromhex(f"{self.addr:02x} 03 03 E8 00 01")
        rx_data = self.__send_modbus(tx_data, 7)
        baudrate = [0, 0, 4800, 9600, 19200]
        return baudrate[rx_data[4]]

    def __set_baudrate_style1(self, baudrate: int) -> bool:
        tx_data = bytes.fromhex(f"{self.addr:02x} 03 E9 00 01 02 00 {baudrate}")
        rx_data = self.__send_modbus(tx_data, 8)
        return tx_data[:6] == rx_data[:6]

    def __set_baudrate_style2(self, baudrate: int) -> bool:
        tx_data = bytes.fromhex(f"FF 00 {baudrate} FF")
        rx_data = self.__send_modbus(tx_data, 4, False)
        return tx_data == rx_data

    def __get_address_style1(self) -> int:
        tx_data = bytes.fromhex("00 03 00 00 00 01")
        addr = 0
        rx_data = self.__send_modbus(tx_data, 7)
        if len(rx_data) > 4 and int(rx_data[4]) > 0:
            addr = int(rx_data[4])
        return addr

    def __set_address_style1(self, addr: int) -> int:
        tx_data = bytes.fromhex(f"00 10 00 00 00 01 02 00 {addr:02x}")
        rx_data = self.__send_modbus(tx_data, 11)
        logger.info("The address changed to: %d", int(rx_data[8]))
        return int(rx_data[8])

    def __set_all_open_style1(self) -> bool:
        tx_data = bytes.fromhex(f"{self.addr:02x} 0F 00 00 00 08 01 FF")
        rx_data = self.__send_modbus(tx_data, 8)
        return tx_data[:6] == rx_data[:6]

    def __set_all_open_style2(self) -> bool:
        tx_data = bytes.fromhex("A0 FF 01 A2")
        rx_data = self.__send_modbus(tx_data, 4, False)
        return rx_data == tx_data

    def __set_all_close_style1(self) -> bool:
        tx_data = bytes.fromhex(f"{self.addr:02x} 0F 00 00 00 08 01 00")
        rx_data = self.__send_modbus(tx_data, 8)
        return tx_data[:6] == rx_data[:6]

    def __set_all_close_style2(self) -> bool:
        tx_data = bytes.fromhex("A0 FF 00 A1")
        rx_data = self.__send_modbus(tx_data, 4, False)
        return rx_data == tx_data

    def __set_one_open_style1(self, ix: int) -> bool:
        tx_data = bytes.fromhex(f"{self.addr:02x} 05 00 {ix:02x} FF 00")
        rx_data = self.__send_modbus(tx_data, 8)
        return tx_data[:6] == rx_data[:6]

    def __set_one_open_style2(self, ix: int) -> bool:
        tx_data = bytes.fromhex(f"A0 {ix + 1:02x} 01 A2")
        rx_data = self.__send_modbus(tx_data, 4, False)
        return rx_data == tx_data

    def __set_one_close_style1(self, ix: int) -> bool:
        tx_data = bytes.fromhex(f"{self.addr:02x} 05 00 {ix:02x} 00 00")
        rx_data = self.__send_modbus(tx_data, 8)
        return tx_data[:6] == rx_data[:6]

    def __set_one_close_style2(self, ix: int) -> bool:
        tx_data = bytes.fromhex(f"A0 {ix + 1:02x} 00 A1")
        rx_data = self.__send_modbus(tx_data, 4, False)
        return rx_data == tx_data

    def __get_status_style1(self) -> list[bool] | None:
        tx_data = bytes.fromhex(f"{self.addr:02x} 01 00 00 00 08")
        rx_data = self.__send_modbus(tx_data, 6)
        num_status = rx_data[3]
        if rx_data[:2] != tx_data[:2]:
            return None
        return [_ == "1" for _ in f"{num_status:08b}"][::-1]

    def __get_status_style2(self) -> list[bool] | None:
        tx_data = bytes.fromhex("A1 00 FF A1")
        rx_data = self.__send_modbus(tx_data, 19, False)
        if rx_data[:2] != bytes.fromhex("A1 FF"):
            return None
        return [_ == 1 for _ in list(rx_data)[2:-1]]
