import csv
from geopy import distance, Point
from PIL import Image, ImageDraw, ImageFont
import geopy
from geopy.units import miles

"""
    StaticMap class:
        - Represents the static map that is displayed on the flight tracker
        - Propertties: 
            - static_map : PIL.Image - image object of size (height_px, width_px)
            - center_cord : geopy.Point - the cordinates of the center of the flight tracker display (cordinates of device location)
            - map_dimensions_mi : tuple(int, int) - the dimensions of the area represented on the display

        - Methods:
            - 
"""


class StaticMap:
    image: Image.Image

    def __init__(
        self,
        map_dimensions_mi: tuple[int, int],
        map_dimensions_px: tuple[int, int],
        center_cord: Point,
        img_path: str | None = None,
        runways_data_path: str = "runways.csv",
        runway_color: tuple[int, int, int] = (128, 128, 128),
        intl_runways: bool = False,
    ):
        self.img_dims = map_dimensions_px

        self.runways_data_path = runways_data_path

        # pythagorean thoream
        corner_dist = (
            ((map_dimensions_mi[0] / 2) ** 2) + ((map_dimensions_mi[1] / 2) ** 2)
        ) ** 0.5

        ne_corner = distance.distance(miles=corner_dist).destination(
            center_cord, bearing=45
        )
        se_corner = distance.distance(miles=corner_dist).destination(
            center_cord, bearing=225
        )

        self.max_lat = max(ne_corner.latitude, se_corner.latitude)
        self.min_lat = min(ne_corner.latitude, se_corner.latitude)

        self.max_lon = max(ne_corner.longitude, se_corner.longitude)
        self.min_lon = min(ne_corner.longitude, se_corner.longitude)

        self.runway_color = runway_color

        if not intl_runways:
            self.csv_keys = [
                "LAT1_DECIMAL",
                "LONG1_DECIMAL",
                "LAT2_DECIMAL",
                "LONG2_DECIMAL",
            ]

        else:
            self.csv_keys = [
                "le_latitude_deg",
                "le_longitude_deg",
                "he_latitude_deg",
                "he_longitude_deg",
            ]

        if img_path:
            self.image = Image.open(img_path)

        else:
            self.image = self.generate_static_map()

    def generate_static_map(self):
        # Create a new image and image context2
        frame = Image.new("RGB", self.img_dims)
        frame_draw = ImageDraw.ImageDraw(frame)

        # Get list of runways in view
        runways = self.get_runways(self.runways_data_path)

        for runway in runways:
            end1_xy = self.latlon_to_xy(runway[0][0], runway[0][1])
            end2_xy = self.latlon_to_xy(runway[1][0], runway[1][1])

            self.draw_runway(end1_xy, end2_xy, frame_draw)

        return frame

    def get_runways(
        self, file_path: str
    ) -> list[tuple[tuple[float, float], tuple[float, float]]]:
        in_view = []
        # Open the runways data file
        with open(file_path) as runways_file:
            runway_reader = csv.DictReader(runways_file)

            for row in runway_reader:
                if (
                    row[self.csv_keys[0]]
                    and row[self.csv_keys[1]]
                    and row[self.csv_keys[2]]
                    and row[self.csv_keys[3]]
                ):

                    end1_lat = float(row[self.csv_keys[0]])
                    end1_lon = float(row[self.csv_keys[1]])
                    end2_lat = float(row[self.csv_keys[2]])
                    end2_lon = float(row[self.csv_keys[3]])

                    if self.is_visible(end1_lat, end1_lon) and self.is_visible(
                        end2_lat, end2_lon
                    ):
                        in_view.append(((end1_lat, end1_lon), (end2_lat, end2_lon)))

        return in_view

    def draw_runway(
        self,
        end1: tuple[int, int],
        end2: tuple[int, int],
        frame_draw: ImageDraw.ImageDraw,
    ):
        if end1[0] >= 0 and end1[1] >= 0 and end2[0] >= 0 and end2[1] >= 0:
            frame_draw.line([end1, end2], fill=self.runway_color)

    def is_visible(self, lat: float, lon: float):
        lat_in_range = lat > self.min_lat and lat < self.max_lat
        lon_in_range = lon > self.min_lon and lon < self.max_lon

        return lat_in_range and lon_in_range

    """
        This is an extremely naive projection.
        
    """

    def latlon_to_xy(self, lat: float, lon: float):
        lat_dif = abs(self.max_lat - self.min_lat)
        lon_dif = abs(self.max_lon - self.min_lon)
        x_prop = abs(lon - self.min_lon) / lon_dif
        y_prop = abs(lat - self.min_lat) / lat_dif

        x_deci = x_prop * self.img_dims[0]
        y_deci = y_prop * self.img_dims[0]

        x = round(x_deci)
        y = round(y_deci)
        y = self.img_dims[1] - y

        if x < 0 or x >= self.img_dims[0]:
            return -1, -1

        if y < 0 or y >= self.img_dims[1]:
            return -1, -1

        return x, y
