import socket
from prettytable import PrettyTable
import threading
from collections import deque
from typing import Dict
import time

AIRCRAFT_DICT_LOCK = threading.Lock()


class Aircraft_Table:
    def __init__(self, aircraft_timeout=60):
        # self.aircraft_table : Dict[str, Aircraft] = {}
        self.aircraft_table = {}
        self.total_messages = 0
        self.aircraft_timeout = aircraft_timeout

    def process_msg(self, msg: str):
        """
        MSG Fields:
        0 - Message Type - Not used, all messages are type "MSG" from dump1090
        1 - Transmission Type - Can be used for knowing which fields will be used
        2 - Session ID - Not used by dump1090
        3 - Aircraft ID - Not used by dump1090
        4 - Hex ID - ICAO hex ID of the aircraft
        5 - Flight ID - Not used by dump1090
        6 - Date message generated - Not used by dump1090
        7 - Time message generated - Not used by dump1090
        8 - Date message logged - Not used by dump1090
        9 - Time message logged - Not used by dump1090
        10 - Callsign
        11 - Altitude
        12 - Ground Speed
        13 - Track
        14 - Latitude
        15 - Longitude
        16 - Vertical Rate
        17 - Squawk
        18 - Alert - Flag to indicate if squawk has changed
        19 - Emergency - Flag to indicate if emergency code has been sent
        20 - SPI - Flag to indicate if transponder ident has been activated
        21 - IsOnGround - Flag to indicate if the squat switch is active
        """
        msg_l = msg.split(",")

        # Check if message has correct number of fields
        if len(msg_l) != 22:
            print(f"Invalid Message Received - ({msg})")
            return

        hex_id = msg_l[4]
        callsign = msg_l[10]
        altitude = msg_l[11]
        ground_speed = msg_l[12]
        track = msg_l[13]
        latitude = msg_l[14]
        longitude = msg_l[15]
        vertical_rate = msg_l[16]
        squawk = msg_l[17]
        alert = msg_l[18]
        emergency = msg_l[19]
        spi = msg_l[20]
        is_on_ground = msg_l[21]

        # All messages should have a hex id
        if not hex_id:
            print(f"Invalid Message Received - ({msg})")
            return

        aircraft = self.aircraft_table.get(hex_id)

        # Create a new aircraft if it doesn't exist in the aircraft table
        if not aircraft:
            aircraft = Aircraft(hex_id)

            # Add aircraft to table
            self.aircraft_table[hex_id] = aircraft

        if callsign:
            aircraft.call_sign = callsign

        if altitude:
            aircraft.altitude = int(altitude)

        if ground_speed:
            aircraft.ground_speed = int(ground_speed)

        if track:
            aircraft.track = int(track)

        if latitude:
            aircraft.latitude = float(latitude)

        if longitude:
            aircraft.longitude = float(longitude)

        if vertical_rate:
            aircraft.vertical_rate = int(vertical_rate)

        if squawk:
            aircraft.squawk = squawk

        if emergency:
            aircraft.emergency = bool(emergency)

        if is_on_ground:
            aircraft.on_ground = bool(int(is_on_ground))

        aircraft.updated = time.time()
        self.total_messages += 1

    def purge_old_aircraft(self):
        cur_time = time.time()
        deletable = []
        for key in self.aircraft_table.keys():
            if (cur_time - self.aircraft_table[key].updated) > self.aircraft_timeout:
                deletable.append(key)


            # Delete if on ground
            if self.aircraft_table[key].on_ground:
                deletable.append(key)

        for key in deletable:
            del self.aircraft_table[key]


class Aircraft:
    def __init__(self, hex_ident: str):
        self.hex_ident = hex_ident
        self.call_sign: str = ""
        self.altitude: int = 0
        self.ground_speed: int = 0
        self.track: int = 0
        self.latitude: float = 0.0
        self.longitude: float = 0.0
        self.vertical_rate: int = 0
        self.squawk: str = ""
        self.emergency: bool = False
        self.on_ground: bool = False
        self.updated = time.time()
        self.pos_history: list[tuple[tuple[int, int], tuple[int, int, int]]] = []

    def serialize(self) -> list:
        return [
            self.hex_ident,
            self.call_sign,
            self.altitude,
            self.ground_speed,
            self.track,
            self.latitude,
            self.longitude,
            self.squawk,
            self.on_ground,
        ]

    def __str__(self) -> str:
        return f"{self.call_sign}\t{self.altitude}\t{self.ground_speed}\t{self.latitude}\t{self.longitude}"


class Receive_Data_Thread(threading.Thread):
    def __init__(self, rdl_soc: socket.socket, data_queue: deque):
        super().__init__()
        self.rdl_soc = rdl_soc
        self.data_queue = data_queue
        self.exit_flag = threading.Event()

    def run(self):
        while not self.is_stopped():
            rdl_msg_b = self.rdl_soc.recv(2048)
            rdl_msg = rdl_msg_b.decode()
            rdl_msg = rdl_msg[:-1]

            sbs_msgs = rdl_msg.split("\n")

            for msg in sbs_msgs:
                self.data_queue.append(msg)

    def stop(self):
        self.exit_flag.set()

    def is_stopped(self):
        return self.exit_flag.is_set()


class Process_Data_Thread(threading.Thread):
    def __init__(self, aircraft: Aircraft_Table, data_queue: deque):
        threading.Thread.__init__(self)
        self.aircraft = aircraft
        self.data_queue = data_queue
        self.exit_flag = threading.Event()

    def run(self):
        while not self.is_stopped():
            if len(self.data_queue) == 0:
                continue

            msg = self.data_queue.pop()

            with AIRCRAFT_DICT_LOCK:
                self.aircraft.process_msg(msg)

    def stop(self):
        self.exit_flag.set()

    def is_stopped(self):
        return self.exit_flag.is_set()


def main():

    rdl_soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    rdl_soc.connect(("10.0.0.64", 30003))

    data_queue = deque()
    aircraft = Aircraft_Table()

    exit_flag = False

    listen_thread = Process_Data_Thread(aircraft, data_queue)
    process_thread = Receive_Data_Thread(rdl_soc, data_queue)

    listen_thread.start()
    process_thread.start()

    while not exit_flag:
        usr_in = input(">")

        if usr_in == "ls":
            tab = PrettyTable(
                [
                    "Hex Ident",
                    "Call Sign",
                    "Altitude",
                    "Ground Speed",
                    "Track",
                    "Latitude",
                    "Longitude",
                    "Squawk",
                    "On Ground",
                ]
            )

            for craft in aircraft.aircraft_table:
                aircraft_obj = aircraft.aircraft_table[craft]
                tab.add_row(aircraft_obj.serialize())
            print(tab)
        elif usr_in == "exit":
            listen_thread.stop()
            process_thread.stop()
            listen_thread.join()
            process_thread.join()
            exit_flag = True


if __name__ == "__main__":
    main()
