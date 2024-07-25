from rpi_led_matrix.bindings.python.rgbmatrix import RGBMatrix, RGBMatrixOptions
import numpy as np  
import data_processing
from collections import deque
import socket
import geopy.distance
import time
import traceback
from PIL import Image, ImageDraw, ImageFont
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
        self.total_rows : int = 128
        self.total_cols : int = 128
        self.gpio_slowdown : int = 4
        self.pwm_dither_bits : int = 2
        self.pwm_bits : int = 11
        self.chain_length : int = 4
        self.parallel : int = 1
        self.pixel_mapper_config : str = "U-mapper;Rotate:-90"
        self.rows_per_display : int = 64
        self.cols_per_display : int = 64

        # Flight tracking configuration
        self.path_to_static_map : str = "static/static_map.png"
        self.path_to_font : str = "static/font.ttf"
        self.dump1090_host: str = 'localhost'
        self.dump1090_port : int = 30003
        self.base_latitude = 35.852598
        self.base_longitude = -86.389409
        self.mapping_box_width_mi: float = 50.0
        self.mapping_box_height_mi: float = 50.0
        self.icons = (
                ((1, 1), (-1, 1)),
                ((-1, 0), (0, 1)), 
                ((-1, -1), (-1, 1)),
                ((0, -1), (-1, 0)),
                ((1, -1), (-1, -1)),
                ((1, 0), (0, -1)),
                ((1, 1), (1, -1)),
                ((1, 0), (0, 1))
                )

        self.airports = ((35.8786583,-86.3774708, 'MBT'), (36.0089703,-86.5200897), 'MQY')

class FlightTracker():
    def __init__(self, config):
        self.config = config
        self.rows = config.total_rows
        self.cols = config.total_cols
        
        # Set up RGBMatrixOptions attributes
        self.display_config = RGBMatrixOptions()
        self.display_config.rows = config.rows_per_display
        self.display_config.cols = config.cols_per_display
        self.display_config.gpio_slowdown = config.gpio_slowdown
        self.display_config.pwm_dither_bits = config.pwm_dither_bits
        self.display_config.pwm_bits = config.pwm_bits
        self.display_config.chain_length = config.chain_length
        self.display_config.parallel = config.parallel
        self.display_config.pixel_mapper_config = config.pixel_mapper_config


        # Create matrix object
        self.matrix: RGBMatrix = RGBMatrix(options = self.display_config)

        # Create two frame canvases for double buffering 
        self.canvas_0 = self.matrix.CreateFrameCanvas()
        self.canvas_1 = self.matrix.CreateFrameCanvas()
        self.use_second_canvas = False 
       
        # Aircraft table to record data on each aircraft
        self.aircraft_table = data_processing.Aircraft_Table()
        self.data_queue = deque()

        
        # Socket for connecting to dump1090 
        self.rdl_soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.receive_data_thread = data_processing.Receive_Data_Thread(self.rdl_soc, self.data_queue)
        self.process_data_thread = data_processing.Process_Data_Thread(self.aircraft_table, self.data_queue)
        self.center_lat = config.base_latitude
        self.center_lon = config.base_longitude
        self.mapping_box_width = config.mapping_box_width_mi
        self.mapping_box_height = config.mapping_box_height_mi

        # Calculate reference point to measure the position of aircraft in reference to 
        dist_to_corner = (((self.mapping_box_width/2) ** 2) + ((self.mapping_box_height/2) ** 2)) ** 0.5
        self.reference_point = geopy.distance.distance(miles=dist_to_corner).destination((self.center_lat, self.center_lon), bearing=225)
        self.icons = config.icons
        self.airports = config.airports

        self.font = ImageFont.truetype(config.path_to_font, 5)
        self.path_to_static_map = self.path_to_static_map
        
        
    def start_data_processing(self):
        self.rdl_soc.connect((self.config.dump1090_host, self.config.dump1090_port))
        self.receive_data_thread.start()
        self.process_data_thread.start()

    def latlon_to_xy(self, lat: float, lon: float):
        
        # check if the aircraft is outside of the mapping box 
        if lat < self.reference_point.latitude or lon < self.reference_point.longitude:
            return (-1, -1) 

        # Calculate the horizontal and vertical distance from the reference point
        dist_x = geopy.distance.distance(self.reference_point, geopy.Point(self.reference_point.latitude, lon)).miles
        dist_y = geopy.distance.distance(self.reference_point, geopy.Point(lat, self.reference_point.longitude)).miles

        # Round to the nearest pixel
        x_pos = round((dist_x / self.mapping_box_width) * self.cols)
        y_pos = round((dist_y / self.mapping_box_height) * self.rows)
        y_pos = self.rows - y_pos
       
        # Ensure that rounding did not put the aircraft outside of bounds
        if x_pos >= self.cols or y_pos >= self.rows:
            return (-1, -1)

        return (x_pos, y_pos) 
    
    def create_canvas(self):
        # Alternate between two different frame canvases
        if not self.use_second_canvas:
            canvas = self.canvas_0
        else:
            canvas = self.canvas_1

        canvas.Clear()

        frame = self.generate_frame()

        canvas.SetImage(frame)

        self.use_second_canvas = not self.use_second_canvas

        return canvas


    def get_color_from_altitude(self, alt):
        #colors = ((255, 0, 0), (255, 255, 0), (0, 255, 0), (0, 255, 255), (0, 255, 0), (255, 255, 0))

        if alt < 1000:
            return (255, int((alt/1000) * 255), 0)
        
        if alt < 5000:
            alt_prop = (alt - 1000) / 5000
            return (int(255 - (alt_prop * 255)), 255, 0)

        if alt < 10000:
            alt_prop = (alt - 5000) / 5000
            return (0, 255, int(alt_prop * 255))

        if alt < 30000:
            alt_prop = (alt - 10000) / 20000
            return (0, int(255 - (alt_prop * 255)), 255)

        else: 
            alt_prop = (alt - 30000) / 60000
            if alt_prop > 1:
                alt_prop = 1.0

            return (int(255 * alt_prop), 0, 255)

    def generate_frame(self):
        frame = Image.open(self.path_to_static_map)

        frame_draw = ImageDraw.Draw(frame)

        for icao_code in self.aircraft_table.aircraft_table.keys():
            aircraft = self.aircraft_table.aircraft_table[icao_code]
            pos = self.latlon_to_xy(aircraft.latitude, aircraft.longitude)

            if pos[0] >= 0 and pos[1] >= 0:
                self.draw_aircraft(pos[0], pos[1], frame_draw, aircraft)

        self.draw_airports(frame_draw)


        return frame


    def draw_aircraft(self, x_pos, y_pos, frame_draw: ImageDraw.ImageDraw, aircraft):
        # The tracks in degrees correspoinding to the different icons
        tracks = np.array([0, 45, 90, 135, 180, 225, 270, 315, 360])

        # Calculate the nearest value in tracks to the actual track of the aircraft 
        nearest_track_ind = np.argmin(np.absolute(tracks - aircraft.track))
        # If the nearest index is 360 set the track to 0, since they are the same
        if nearest_track_ind == 8:
            nearest_track_ind = 0

        icon_format = self.icons[nearest_track_ind]
    
        # Call method to get the color of the aircraft icon based on the altitude of the aircraft
        color = self.get_color_from_altitude(aircraft.altitude)

        leg1 = icon_format[0]
        leg2 = icon_format[1]

        x1 = leg1[0] + x_pos
        x2 = leg2[0] + x_pos
        y1 = leg1[1] + y_pos
        y2 = leg2[1] + y_pos

        frame_draw.point((x_pos, y_pos), (color[0], color[1], color[2]))
        
        if x1 >= 0 and x1 < self.cols and y1 >= 0 and y1 < self.rows:
            frame_draw.point((x1, y1), (color[0], color[1], color[2]))

        if x2 >= 0 and x2 < self.cols and y2 >= 0 and y2 < self.rows:
            frame_draw.point((x2, y2), (color[0], color[1], color[2]))

        return frame_draw

    def draw_airports(self, frame_draw: ImageDraw.ImageDraw):
        
        for airport in self.airports:
            pos = self.latlon_to_xy(airport[0], airport[1])

            if pos[0] >= 0 and pos[1] >= 0:
                frame_draw.point(pos, (255, 255, 255))

                frame_draw.text((pos[0], pos[1]-1), airport[2], (255, 255, 255))

        return frame_draw



    def run_display(self):
        count = 0
        while True:
            data_processing.wrt.acquire()
            self.matrix.SwapOnVSync(self.create_canvas())
            data_processing.wrt.release()

            count += 1

            if count == 60:
                self.aircraft_table.purge_old_aircraft()
                count = 0 
            time.sleep(1)

    def shutdown(self):
        self.receive_data_thread.stop()
        self.process_data_thread.stop()
        self.receive_data_thread.join()
        self.process_data_thread.join()


if __name__ == "__main__":
    config = FlightTrackerConfig()
    tracker = FlightTracker(config)
    tracker.start_data_processing()
    
    try:
        tracker.run_display() 
    except:
        tracker.shutdown()
        traceback.print_exc()
        

