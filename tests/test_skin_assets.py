from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from skin_assets import animation_frames  # noqa: E402

try:
    from PIL import Image, ImageDraw
except ImportError:  # pragma: no cover
    Image = None


@unittest.skipIf(Image is None, 'Pillow not installed')
class AnimationFrameTests(unittest.TestCase):
    def test_stacked_button_frames_are_detected(self):
        # A button state column: six near-identical 80x24 frames stacked vertically (AquaBlue_Btn_*.png).
        column = Image.new('RGBA', (80, 144), (0, 0, 0, 0))
        draw = ImageDraw.Draw(column)
        for frame in range(6):
            shade = 40 + frame * 2
            draw.rounded_rectangle((1, frame * 24 + 1, 78, frame * 24 + 22), radius=4, fill=(shade, 100, 30, 255))
        self.assertEqual(animation_frames(column), 6)

    def test_icon_slices_that_differ_are_not_split(self):
        # A 16x48 icon whose slices are different parts of one picture.
        column = Image.new('RGBA', (16, 48), (0, 0, 0, 0))
        draw = ImageDraw.Draw(column)
        draw.ellipse((0, 0, 15, 47), fill=(200, 30, 30, 255))
        self.assertEqual(animation_frames(column), 1)

    def test_heights_that_do_not_divide_stay_whole(self):
        self.assertEqual(animation_frames(Image.new('RGBA', (80, 25), (1, 2, 3, 255))), 1)


if __name__ == '__main__':
    unittest.main()
