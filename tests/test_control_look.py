import struct
import unittest

from helpers import load

look = load('scripts/control_look.py').look


def record(background=None, centred=False, face='Trebuchet MS', height=-12.0, weight=400, colour=b'\x2d\x2d\x2d', tail=bytes(16)):
    """A format-28 control record (chunk 0) reduced to the three records the parser reads, in their order."""
    frame = b'\x64\x02\x00\x00' + b'\x01\x00\x00\x00' + ((background + b'\x00') if background else b'\x00\x00\x00\xff') + b'\xb4\xb4\xb4\x00'
    align = b'\x5b\x02\x00\x00' + ((background + b'\x00') if background else b'\x00\x00\x00\xff') + b'\x00' * 4 + struct.pack('<I', 1 if centred else 0) + b'\x01\x00\x00\x00'
    body = b'\x02\x00\x00\x00' + face.encode() + b'\x00' + struct.pack('<d', height) + struct.pack('<H', weight)
    body += b'\x00' * (78 - len(body)) + colour + b'\x00'
    font = b'\x5e\x00\x00\x00\x01\x00\x00\x00' + struct.pack('<I', len(body)) + body
    return b'\x74\x02\x00\x00' + b'\x00' * 40 + frame + b'\x00' * 8 + align + b'\xff\xff\xff\x7f' + font + tail


class ControlLookTests(unittest.TestCase):
    def test_a_caption_of_its_own_colour_size_and_alignment(self):
        found = look(record(background=b'\xff\xff\x00', centred=True, height=-13.0))
        self.assertEqual(found['background'], '#ffff00')
        self.assertEqual(found['h_align'], 'Center')
        self.assertEqual(found['font'], {'face': 'Trebuchet MS', 'height': -13, 'weight': 400, 'colour': '#2d2d2d'})

    def test_no_background_flag_and_left_alignment(self):
        found = look(record())
        self.assertNotIn('background', found)
        self.assertEqual((found['border'], found['h_align'], found['font']['height']), ('#b4b4b4', 'Left', -12))

    def test_a_system_colour_is_its_windows_default(self):
        found = look(record().replace(b'\x00\x00\x00\xff\xb4\xb4\xb4\x00', b'\x00\x00\x00\xf5\x00\x00\x00\xf1', 1))
        self.assertEqual((found['background'], found['background_system'], found['border']), ('#0078d7', True, '#ffffff'))

    def test_an_edit_caption_left_of_its_input_and_one_not_drawn(self):
        left = record(tail=bytes(20) + struct.pack('<III', 4, 24, 2))
        self.assertEqual(look(left)['caption'], {'position': 'left', 'width': 24})
        self.assertEqual(look(record(tail=bytes(20) + struct.pack('<III', 4, 0, 2)))['caption']['width'], 0)
        self.assertEqual(look(record(tail=bytes(32)))['caption']['position'], 'top')


if __name__ == '__main__':
    unittest.main()
