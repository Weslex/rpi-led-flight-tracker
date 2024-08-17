from PIL import Image, ImageDraw

"""
    AircraftIcon class - parent of all aircraft icons
    SmallFixedWingIcon(AircraftIcon) - Small airplanes
    LargeFixedWingIcon(AircraftIcon) - Large airplanes
    RotorcraftIcon(AircraftIcon) - Helicoptors
"""


class AircraftIcon:
    def __init__(self):
        self.icons: list[Image.Image] = []
        self.headings: list[int] = [0, 45, 90, 135, 180, 225, 270, 315]

    def load_icons(self, icons_dir: str):
        icon_filenames = (
            "0.png",
            "45.png",
            "90.png",
            "135.png",
            "180.png",
            "225.png",
            "270.png",
            "315.png",
        )

        for filename in icon_filenames:
            with Image.open(icons_dir + filename) as icon:
                icon.load()
                icon.convert("1")

                self.icons.append(icon)

    def plot_icon(
        self,
        pos: tuple[int, int],
        color: tuple[int, int, int],
        heading: int,
        frame_draw: ImageDraw.ImageDraw,
    ):
        # Ensure the heading is valid
        if heading > 360 or heading < 0: 
            print("Invalid Heading, Aircraft not added")
            return

        icon = self._heading_to_icons(heading)

        icon_pos = (pos[0] - (icon.size[0]//2), pos[1] - (icon.size[1]//2))

        frame_draw.bitmap(icon_pos, icon, color)


        
    def _heading_to_icons(self, heading: int):
        min_diff = 360
        min_ind = 0

        for i in range(len(self.headings)):
            diff = abs(self.headings[i] - heading)

            if diff < min_diff: 
                min_diff = diff
                min_ind = i

        return self.icons[min_ind]

class SmallFixedWingIcon(AircraftIcon):
    def __init__(self, icons_dir: str):
        super().__init__()

        self.load_icons(icons_dir)


class LargeFixedWingIcon(AircraftIcon):
    def __init__(self, icons_dir: str):
        super().__init__()

        self.load_icons(icons_dir)


class RotorcraftIcon(AircraftIcon):
    def __init__(self, icons_dir: str):
        super().__init__()

        self.load_icons(icons_dir)
