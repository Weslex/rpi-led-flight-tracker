from rpi_led_matrix.bindings.python.rgbmatrix import RGBMatrix, RGBMatrixOptions
from static.static_map_generation import StaticMap
import numpy as np
import data_processing
from collections import deque
import socket
import geopy.distance
import time
import traceback
from PIL import ImageDraw, ImageFont
import sys


sys.path.append("/usr/share/fonts/truetype/freefont/")

"""
    
"""


class FlightTrackerConfig:
    def __init__(self):
        # Display configuration
        self.total_rows: int = 128
        self.total_cols: int = 128
        self.gpio_slowdown: int = 3
        self.pwm_dither_bits: int = 2
        self.pwm_bits: int = 11
        self.chain_length: int = 4
        self.parallel: int = 1
        self.pixel_mapper_config: str = "U-mapper;Rotate:-90"
        self.rows_per_display: int = 64
        self.cols_per_display: int = 64

        # Flight tracking configuration
        self.path_to_static_map: str = ""
        self.path_to_font: str = "Small_Font.ttf"
        self.path_to_runways: str = "runways.csv"
        self.dump1090_host: str = "localhost"
        self.dump1090_port: int = 30003
        # Defualt to centering around BNA
        self.base_latitude = 36.1244750
        self.base_longitude = -86.6781806
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
            ((1, 0), (0, 1)),
        )

        self.traces: bool = True


class FlightTracker:
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

        # Aircraft table to record data on each aircraft
        self.aircraft_table = data_processing.Aircraft_Table()
        self.data_queue = deque()

        # Socket for connecting to dump1090
        self.rdl_soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.receive_data_thread = data_processing.Receive_Data_Thread(
            self.rdl_soc, self.data_queue
        )
        self.process_data_thread = data_processing.Process_Data_Thread(
            self.aircraft_table, self.data_queue
        )
        self.center_lat = config.base_latitude
        self.center_lon = config.base_longitude
        self.mapping_box_width = config.mapping_box_width_mi
        self.mapping_box_height = config.mapping_box_height_mi

        # Calculate reference point to measure the position of aircraft in reference to
        dist_to_corner = (
            ((self.mapping_box_width / 2) ** 2) + ((self.mapping_box_height / 2) ** 2)
        ) ** 0.5

        self.reference_point = geopy.distance.distance(
            miles=dist_to_corner
        ).destination((self.center_lat, self.center_lon), bearing=225)

        self.opposite_reference_point = geopy.distance.distance(
            miles=dist_to_corner
        ).destination((self.center_lat, self.center_lon), bearing=45)

        self.max_lat = self.opposite_reference_point.latitude
        self.min_lat = self.reference_point.latitude
        self.max_lon = self.opposite_reference_point.longitude
        self.min_lon = self.reference_point.longitude

        self.icons = config.icons
        self.traces = config.traces

        self.font = ImageFont.truetype(config.path_to_font, 5)

        # Create the static map
        self.static_map = StaticMap(
            (self.mapping_box_height, self.mapping_box_width),
            (self.rows, self.cols),
            geopy.Point(self.center_lat, self.center_lon),
            runways_data_path=config.path_to_runways,
        ).image

        self.static_map.convert("RGB")

        # Create matrix object
        self.matrix: RGBMatrix = RGBMatrix(options=self.display_config)

        # Create two frame canvases for double buffering
        self.canvas_0 = self.matrix.CreateFrameCanvas()
        self.canvas_1 = self.matrix.CreateFrameCanvas()
        self.use_second_canvas = False

    def start_data_processing(self):
        self.rdl_soc.connect((self.config.dump1090_host, self.config.dump1090_port))
        self.receive_data_thread.start()
        self.process_data_thread.start()

    """
    def latlon_to_xy(self, lat: float, lon: float):

        # check if the aircraft is outside of the mapping box
        if lat < self.reference_point.latitude or lon < self.reference_point.longitude:
            return (-1, -1)

        # Calculate the horizontal and vertical distance from the reference point
        dist_x = geopy.distance.distance(
            self.reference_point, geopy.Point(self.reference_point.latitude, lon)
        ).miles
        dist_y = geopy.distance.distance(
            self.reference_point, geopy.Point(lat, self.reference_point.longitude)
        ).miles

        # Round to the nearest pixel
        x_pos = round((dist_x / self.mapping_box_width) * self.cols)
        y_pos = round((dist_y / self.mapping_box_height) * self.rows)
        y_pos = self.rows - y_pos

        # Ensure that rounding did not put the aircraft outside of bounds
        if x_pos >= self.cols or y_pos >= self.rows:
            return (-1, -1)

        return (x_pos, y_pos)
    """

    """
        This is an extremely naive projection.
        
    """

    def latlon_to_xy(self, lat: float, lon: float):
        lat_dif = self.max_lat - self.min_lat
        lon_dif = self.max_lon - self.min_lon
        x_prop = (lon - self.min_lon) / lon_dif
        y_prop = (lat - self.min_lat) / lat_dif

        x_deci = x_prop * self.cols
        y_deci = y_prop * self.rows

        x = round(x_deci)
        y = round(y_deci)
        y = self.rows - y

        if x < 0 or x >= self.cols:
            return -1, -1

        if y < 0 or y >= self.rows:
            return -1, -1

        return x, y

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
        # colors = ((255, 0, 0), (255, 255, 0), (0, 255, 0), (0, 255, 255), (0, 255, 0), (255, 255, 0))

        key_alts = np.array([0, 2000, 5000, 10000, 20000, 50000])
        key_diff = key_alts[1:] - key_alts[:-1]

        # Color Order:
        #   (255, 0 to 255, 0)
        #   (255 to 0, 255, 0)
        #   (0, 255, 0 to 255)
        #   (0, 255 to 0, 255)
        #   (0 to 255, 0, 255)

        scale_8bit = lambda val, max_val: int(255 * (val / max_val))

        # Special case for if the alitude is 0,
        # this genenrally means no altitude has been read or the aircraft is on the ground
        if alt == 0:
            return (64, 64, 64)

        if alt < key_alts[1]:
            var_channel = scale_8bit(alt, key_diff[0])
            return (255, var_channel, 0)

        if alt < key_alts[2]:
            alt = alt - key_diff[0]
            var_channel = scale_8bit(alt, key_diff[1])
            var_channel = 255 - var_channel
            return (var_channel, 255, 0)

        if alt < key_alts[3]:
            alt = alt - key_diff[1]
            var_channel = scale_8bit(alt, key_diff[2])
            return (0, 255, var_channel)

        if alt < key_alts[4]:
            alt = alt - key_diff[2]
            var_channel = scale_8bit(alt, key_diff[3])
            var_channel = 255 - var_channel
            return (0, var_channel, 255)

        else:
            alt = alt - key_diff[3]
            var_channel = scale_8bit(alt, key_diff[4])

            if var_channel > 255:
                var_channel = 255

            return (var_channel, 0, 255)

    def generate_frame(self):
        frame = self.static_map.copy()

        frame_draw = ImageDraw.Draw(frame)

        # variables to store the aircraft closest to device
        closest_dist = self.rows + self.cols
        closest: data_processing.Aircraft | None = None

        for icao_code in self.aircraft_table.aircraft_table.keys():
            aircraft = self.aircraft_table.aircraft_table[icao_code]
            pos = self.latlon_to_xy(aircraft.latitude, aircraft.longitude)

            if pos[0] >= 0 and pos[1] >= 0:
                self.draw_aircraft(pos[0], pos[1], frame_draw, aircraft)

                dist_to_center = (
                    ((self.cols / 2) - pos[0]) ** 2 + ((self.rows / 2) - pos[1]) ** 2
                ) ** 0.5

                if dist_to_center < closest_dist:
                    closest = self.aircraft_table.aircraft_table[icao_code]
                    closest_dist = dist_to_center

                self.draw_info_on_aircraft(aircraft, frame_draw)

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

        for point in aircraft.pos_history:
            point_pos = point[0]
            point_color = point[1]

            frame_draw.point(point_pos, point_color)

        if x1 >= 0 and x1 < self.cols and y1 >= 0 and y1 < self.rows:
            frame_draw.point((x1, y1), (color[0], color[1], color[2]))

        if x2 >= 0 and x2 < self.cols and y2 >= 0 and y2 < self.rows:
            frame_draw.point((x2, y2), (color[0], color[1], color[2]))

        if (
            len(aircraft.pos_history) == 0
            or x_pos != aircraft.pos_history[-1][0][0]
            or y_pos != aircraft.pos_history[-1][0][1]
        ):
            aircraft.pos_history.append(((x_pos, y_pos), color))
        return frame_draw

    def draw_info_on_aircraft(
        self, aircraft: data_processing.Aircraft, frame_draw: ImageDraw.ImageDraw
    ):
        anchor_pos = self.latlon_to_xy(aircraft.latitude, aircraft.longitude)
        txt = f"{aircraft.call_sign}"
        frame_draw.text(anchor_pos, txt, (255, 255, 255), self.font, anchor="rs")

        return frame_draw

    def run_display(self):
        count = 0
        while True:
            with data_processing.AIRCRAFT_DICT_LOCK:
                self.matrix.SwapOnVSync(self.create_canvas())

                self.aircraft_table.purge_old_aircraft()
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
