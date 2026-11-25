import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "visual_qa"))

from capture_windev_visual import compare_aligned, region
from extract_windev_visual import asset_path, source_index
from windev_visual_geometry import reflow


class VisualQA(unittest.TestCase):
    def test_resizes_child_using_its_anchored_parent(self):
        layout = {"window": {"size": {"width": 100, "height": 100}}, "controls": [
            {"path": "Tab", "x": 10, "y": 10, "width": 70, "height": 60,
             "anchoring": "width", "pane_top": 20},
            {"path": "Tab.Button", "x": 50, "y": 12, "width": 20, "height": 10,
             "anchoring": "right", "anchorRates": {"right": 50}},
        ]}
        reflow(layout, 140, 100)
        parent, button = layout["controls"]
        self.assertEqual(parent["width"], 110)
        self.assertEqual((button["x"], button["y"]), (70, 32))
        self.assertEqual(button["designer_box"], {"x": 50, "y": 12, "width": 20, "height": 10})

    def test_tab_and_nested_paths_are_kept(self):
        controls, tabs, choices = source_index({"elements": [
            {"owner": "tabs", "parents": ["WIN_Demo", "Tab"], "name": "First",
             "fields": {"caption": "First"}, "pane": 1, "line": 18},
            {"owner": "controls", "parents": ["WIN_Demo", "Tab"], "name": "Choice"},
            {"owner": "options", "parents": ["WIN_Demo", "Tab", "Choice"], "name": "Opt",
             "fields": {"caption": "Option"}},
        ]})
        self.assertEqual(len(controls["Tab.Choice"]), 1)
        self.assertEqual(tabs["Tab"][0], {"index": 1, "caption": "First", "line": 18})
        self.assertEqual(choices["Tab.Choice"], ["Option"])

    def test_referenced_art_stays_within_the_project(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            icon = root / "demo.png"
            icon.touch()
            self.assertEqual(asset_path(root, r".\demo.png"), icon)
            self.assertIsNone(asset_path(root, r"..\demo.png"))
            self.assertIsNone(asset_path(root, r"C:\demo.png"))

    def test_aligned_comparison_preserves_exact_size_and_detects_changed_pixel(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            native = root / "native.png"
            capture = root / "capture.png"
            diff = root / "diff.png"
            image = Image.new("RGB", (20, 20), "white")
            ImageDraw.Draw(image).rectangle((6, 6, 8, 8), fill="black")
            image.save(native)
            crop = region("5,5,10,10")
            candidate = image.crop(crop)
            candidate.save(capture)
            self.assertEqual(compare_aligned(native, capture, crop, diff)["exact_rgb_equal_percent"], 100)
            candidate.putpixel((1, 1), (255, 255, 255))
            candidate.save(capture)
            self.assertEqual(compare_aligned(native, capture, crop, diff)["exact_rgb_equal_percent"], 99)
            self.assertTrue(diff.is_file())
            with self.assertRaisesRegex(ValueError, "equal regions"):
                compare_aligned(native, capture, None, diff)


if __name__ == "__main__":
    unittest.main()
