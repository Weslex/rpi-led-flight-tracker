from rpi_led_matrix.bindings.python.rgbmatrix import RGBMatrix, RGBMatrixOptions

def main():
    options = RGBMatrixOptions()
    options.rows = 64
    options.col = 64
    options.chain_length = 4
    options.parallel = 1
    options.gpio_slowdown = 3
    options.pwm_dither_bits = 0
    options.pwm_bits = 11
    options.pixel_mapper_config = 'U-mapper;Rotate:270'

    matrix = RGBMatrix(options=options)
    while True:
        matrix.SetPixel(32, 32, 200, 200, 200)
main()
