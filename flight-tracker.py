from rpi_led_matrix.bindings.python.rgbmatrix import RGBMatrix, RGBMatrixOptions
import numpy as np  
import data_processing
from collections import deque
import socket
import geopy.distance
import time
"""
    - The first problem to tackle is going to be getting the aircraft currently
    being detected and ploting where they should be located on the 128x128 
    canvas that is the display. 
        - Something to consider will be making the program work with other sizes of 
        displays 

    35.852598, -86.389409
    
"""
class FlightTrackerConfig():
    def __init__(self):
        # Display configuration 
        self.rows : int = 128
        self.cols : int = 128
        self.gpio_slowdown : int = 4
        self.pwm_dither_bits : int = 2
        self.pwm_bits : int = 11
        self.chain_length : int = 4
        self.parallel : int = 1
        self.pixel_mapper_config : str = "U-mapper;Rotate:180"

        # Flight tracking configuration
        self.dump1090_host: str = 'localhost'
        self.dump1090_port : int = 30003
        self.base_latitude = 35.852598
        self.base_longitude = -86.389409
        self.mapping_box_width_mi: float = 20.0
        self.mapping_box_height_mi: float = 20.0
        self.icons = (((-1, 1), (1, -1)), ((-1, 0), (0, 1)), ((-1, -1), (-1, 1)), ((0, -1), (-1, 0)), ((1, -1), (-1, -1)), ((-1, 0), (0, -1)), ((1, 1), (1, -1)), ((1, 0), (0, 1)))

class FlightTracker():
    def __init__(self, config):
        self.config = config
        self.rows = config.rows
        self.cols = config.cols
        
        self.display_config = RGBMatrixOptions()
        self.display_config.rows = config.rows
        self.display_config.cols = config.cols
        self.display_config.gpio_slowdown = config.gpio_slowdown
        self.display_config.pwm_dither_bits = config.pwm_dither_bits
        self.display_config.pwm_bits = config.pwm_bits
        self.display_config.chain_length = config.chain_length
        self.display_config.parallel = config.parallel
        self.display_config.pixel_mapper_config = config.pixel_mapper_config

        self.matrix: RGBMatrix = RGBMatrix(options = self.display_config)
       
        self.aircraft_table = data_processing.Aircraft_Table()
        self.data_queue = deque()

        
        self.rdl_soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.shutdown_data_processing = data_processing.End_Tasks_Flag(False)
        self.receive_data_thread = data_processing.Receive_Data_Thread(self.rdl_soc, self.data_queue, self.shutdown_data_processing)
        self.process_data_thread = data_processing.Process_Data_Thread(self.aircraft_table, self.data_queue, self.shutdown_data_processing)
        self.center_lat = config.base_latitude
        self.center_lon = config.base_longitude
        self.mapping_box_width = config.mapping_box_width_mi
        self.mapping_box_height = config.mapping_box_height_mi

        dist_to_corner = (((self.mapping_box_width/2) ** 2) + ((self.mapping_box_height/2) ** 2)) ** 0.5
        self.reference_point = geopy.distance.distance(miles=dist_to_corner).destination((self.center_lat, self.center_lon), bearing=225)
        self.icons = config.icons
        
        
    def start_data_processing(self):
        self.rdl_soc.connect((self.config.dump1090_host, self.config.dump1090_port))
        self.receive_data_thread.start()
        self.process_data_thread.start()

    def calc_aircraft_pos(self, lat: float, lon: float):
        
        # check if the aircraft is outside of the mapping box 
        if lat < self.reference_point.latitude or lon < self.reference_point.longitude:
            return (-1, -1) 

        dist_x = geopy.distance.distance(self.reference_point, geopy.Point(self.reference_point.latitude, lon)).miles
        dist_y = geopy.distance.distance(self.reference_point, geopy.Point(lat, self.reference_point.longitude)).miles

        x_pos = round((dist_x / self.mapping_box_width) * self.cols)
        y_pos = round((dist_y / self.mapping_box_height) * self.rows)
        y_pos = self.rows - y_pos
        
        if x_pos >= self.cols or y_pos >= self.rows:
            return (-1, -1)
        return (y_pos, x_pos) 
    
    def plot_aircraft(self):
        canvas = self.matrix.CreateFrameCanvas()
        count = 1
        for icao_code in self.aircraft_table.aircraft_table.keys():
            aircraft = self.aircraft_table.aircraft_table[icao_code]
            pos = self.calc_aircraft_pos(aircraft.latitude, aircraft.longitude)

            if pos[0] >= 0 and pos[1] >= 0:
                canvas.SetPixel(pos[0], pos[1], 255, 255, 255) 
                print(count, icao_code)
                count += 1

        return canvas
    def run_display(self):
        while True:
            data_processing.wrt.acquire()
            data_processing.reader_count += 1
            if data_processing.reader_count == 1:
                data_processing.mutex.acquire()

            data_processing.mutex.release()
            self.matrix.SwapOnVSync(self.plot_aircraft())
            data_processing.mutex.acquire()
            if data_processing.reader_count == 1:
                data_processing.wrt.release()

            data_processing.mutex.release()
            time.sleep(10)

    def plot_aircraft_icons(self, x_pos, y_pos, canvas, aircraft):
        tracks = [0, 45, 90, 135, 180, 225, 270, 315]
        tracks = np.array(tracks)
        nearest_track_ind = np.argmin(np.absolute(tracks - aircraft.track))

        


    def shutdown(self):
        self.shutdown_data_processing.flag = True
        self.receive_data_thread.join()
        self.process_data_thread.join()


if __name__ == "__main__":
    config = FlightTrackerConfig()
    tracker = FlightTracker(config)
    tracker.start_data_processing()
    
    try:
        tracker.run_display() 
    except Exception as e:
        tracker.shutdown()
        print(e)
        

