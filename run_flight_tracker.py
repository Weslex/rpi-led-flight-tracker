from flight_tracker import FlightTrackerConfig, FlightTracker
import traceback

config = FlightTrackerConfig()

# display config
config.total_rows = 128
config.total_cols = 128
config.rows_per_display = 64
config.cols_per_display = 64
config.chain_length = 4
config.parallel = 1
config.pwm_bits = 11
config.pwm_dither_bits = 2
config.pixel_mapper_config = "U-mapper;Rotate:-90"


# height and width of the area represented by the display
config.mapping_box_height_mi = 20
config.mapping_box_width_mi = 20

# latitude and longitude of the center of the display
config.base_latitude = 30.00     # Enter the latitude of the device
config.base_longitude = -86.00    # Enter the longitude of the device

# flags for setting visibility of aircraft traces and callsign
config.traces = True
config.callsign_labels = True
config.use_intl_runways = False

# create the flight tracker object
tracker = FlightTracker(config)

# start up data processing threads for reading from dump1090
tracker.start_data_processing()

try:
    tracker.run_display()

except:
    tracker.shutdown()
    traceback.print_exc()




