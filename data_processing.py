import socket
from prettytable import PrettyTable
import threading
from collections import deque


class Aircraft_Table():
    def __init__(self):
        self.aircraft_table = {}
        self.total_messages = 0
        

    def process_msg(self, msg: str):
        msg_l = msg.split(",")
        cur_hex = msg_l[4] 
        if self.aircraft_table.get(cur_hex) is None:
            #print("New Aircraft " + cur_hex)
            self.aircraft_table[cur_hex] = Aircraft(cur_hex)

        if msg_l[1] == '1': 
            self.aircraft_table[cur_hex].call_sign = msg_l[10]

        elif msg_l[1] == '2': 
            self.aircraft_table[cur_hex].altitude = msg_l[11]
            self.aircraft_table[cur_hex].ground_speed = msg_l[12]
            self.aircraft_table[cur_hex].track = msg_l[13]
            self.aircraft_table[cur_hex].latitude = msg_l[14]
            self.aircraft_table[cur_hex].longitude = msg_l[15]
            self.aircraft_table[cur_hex].on_ground = msg_l[21]

        elif msg_l[1] == '3': 
            self.aircraft_table[cur_hex].altitude = msg_l[11] 
            self.aircraft_table[cur_hex].latitude = msg_l[14]
            self.aircraft_table[cur_hex].longitude = msg_l[15]
            self.aircraft_table[cur_hex].emergency = msg_l[19]
            self.aircraft_table[cur_hex].on_ground = msg_l[21]

        elif msg_l[1] == '4':
            self.aircraft_table[cur_hex].ground_speed = msg_l[12]
            self.aircraft_table[cur_hex].track = msg_l[13]
            self.aircraft_table[cur_hex].vertical_rate = msg_l[16]

        elif msg_l[1] == '5':
            self.aircraft_table[cur_hex].altitude = msg_l[11]
            self.aircraft_table[cur_hex].on_ground = msg_l[21]

        elif msg_l[1] == '6':
            self.aircraft_table[cur_hex].altitude = msg_l[11]
            self.aircraft_table[cur_hex].squawk = msg_l[17]
            self.aircraft_table[cur_hex].emergency = msg_l[19]
            self.aircraft_table[cur_hex].on_ground = msg_l[21]
        
        elif msg_l[1] == '7':
            self.aircraft_table[cur_hex].altitude = msg_l[11]
            self.aircraft_table[cur_hex].on_ground = msg_l[21]

        elif msg_l[1] == '8':
            self.aircraft_table[cur_hex].on_ground = msg_l[21]


        self.total_messages += 1 
        
class Aircraft():
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

    def serialize(self) -> list:
        return [self.hex_ident, self.call_sign, self.altitude, self.ground_speed, self.track, self.latitude, self.longitude]


    def __str__(self) -> str:
        return f"{self.call_sign}\t{self.altitude}\t{self.ground_speed}\t{self.latitude}\t{self.longitude}"

class End_Tasks_Flag():
    def __init__(self, state: bool):
        self.flag = state
def receive_data(rdl_soc, data_queue, exit_flag):
    while not exit_flag.flag: 
        rdl_msg_b = rdl_soc.recv(2048)
        rdl_msg = rdl_msg_b.decode()
        rdl_msg = rdl_msg[:-1]

        sbs_msgs = rdl_msg.split('\n')

        for msg in sbs_msgs:
            data_queue.append(msg)


def process_data(aircraft: Aircraft_Table, data_queue: deque, exit_flag: End_Tasks_Flag):
    while not exit_flag.flag:
        if len(data_queue) == 0:
            continue

        msg = data_queue.pop()
        aircraft.process_msg(msg)
        
def main():

    exit_flag = End_Tasks_Flag(False)

    rdl_soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    rdl_soc.connect(("10.0.0.64", 30003))
    
    data_queue = deque()
    aircraft = Aircraft_Table()

    
    
    listen_thread = threading.Thread(target=receive_data, args=(rdl_soc, data_queue, exit_flag))
    process_thread = threading.Thread(target=process_data, args=(aircraft, data_queue, exit_flag))

    listen_thread.start()
    process_thread.start()

    while not exit_flag.flag:
        usr_in = input(">")

        if usr_in == 'ls':
            tab = PrettyTable(["Hex Ident", "Call Sign", "Altitude", "Ground Speed", "Track", "Latitude", "Longitude"])

            for craft in aircraft.aircraft_table:
                aircraft_obj = aircraft.aircraft_table[craft]
                tab.add_row(aircraft_obj.serialize())
            print(tab)
        elif usr_in == 'exit':
            exit_flag.flag = True
            listen_thread.join()
            process_thread.join()
            
if __name__ == "__main__":
    main()
            



