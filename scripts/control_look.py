#!/usr/bin/env python3
"""A control's own look in a WINDEV 28 window source: font, text colour, alignment, background and border colours.

windev_decode.py reads a control's fonts from framed face strings; in the format-28 control record (chunk 0) the font
is a fixed record whose face is a plain zero-terminated string, so every control decoded with "fonts: 0 records" and
its colours were lost. Measured on WIN_Form_RecPag_teclado (STC_Nao_pago, a yellow, centred caption of style
LIB_Simple, against STC_Data_Doc of the same style; the designer thumbnail shows the yellow box):

  tag 0x264  frame:      u32 type (1 plain, 0x11 vertical gradient), RGB background + flag byte (0 = set, 0xff = none), RGB border + 0
  tag 0x25b  alignment:  RGB text background + flag, u32 ?, u32 horizontal (0 left, 1 centre, 2 right)
  tag 0x5e   font:       u32 1, u32 record length at +8, u32 2, face at +16 (zero-terminated), f64 height (negative = px)
                         after the face, u16 weight; the text colour is the record's last 4 bytes (RGB + 0)
  edits, combos, lists:  after the first (caption) font record, at +20 u32 caption position (4 = left of the input,
                         0 = above it) and at +24 u32 the caption width in px: where the input starts from the control's
                         left edge, 0 when the caption is not drawn. Measured on designer images: "De" 24, "Até" 28,
                         "Estado" 42 px (IW_DASH_trabalhos, IW_dash_OBRAS_movimentos).

`look(chunk0)` returns {font: {face, height, weight, colour}, h_align, background, border, caption} with what it
finds. The values match WINDEV's style sheet values for controls that keep their style (Trebuchet MS -11 400
#2d2d2d for LIB_Simple), so a project can keep only what differs from the control's style.
"""
import struct

ALIGN_H = {0: 'Left', 1: 'Center', 2: 'Right', 3: 'Justified'}
ALIGN_V = {0: 'Top', 1: 'Center', 2: 'Bottom'}
CAPTION = {4: 'left', 0: 'top'}
# frame types seen with a fill colour: 1 plain; 0x11 a vertical gradient from 15 % of the colour in white at the top
# to the colour at the bottom (designer images: #d9ecd9 -> #008000, #ffd9d9 -> #ff0000; 4,714 buttons)
FRAME_KINDS = {1: 'plain', 0x11: 'gradient'}
FRAME, ALIGN, FONT = b'\x64\x02\x00\x00', b'\x5b\x02\x00\x00', b'\x5e\x00\x00\x00\x01\x00\x00\x00'


def _rgb(raw):
    return '#%02x%02x%02x' % (raw[0], raw[1], raw[2])


def look(data):
    found = {}
    at = data.find(FRAME)
    if 0 <= at <= len(data) - 16:
        background, border = data[at + 8:at + 12], data[at + 12:at + 16]
        if background[3] == 0:
            found['background'] = _rgb(background)
            kind = struct.unpack_from('<I', data, at + 4)[0]
            if kind in FRAME_KINDS:
                found['fill'] = FRAME_KINDS[kind]
        found['border'] = _rgb(border)
    at = data.find(ALIGN)
    if 0 <= at <= len(data) - 16:
        text_background = data[at + 4:at + 8]
        horizontal = struct.unpack_from('<I', data, at + 12)[0]
        if text_background[3] == 0:
            found['text_background'] = _rgb(text_background)
        if horizontal in ALIGN_H:
            found['h_align'] = ALIGN_H[horizontal]
    at = data.find(FONT)
    if 0 <= at <= len(data) - 24:
        length = struct.unpack_from('<I', data, at + 8)[0]
        end = data.find(b'\x00', at + 16)
        if 0 < length < 400 and at + 16 < end < at + 16 + 64 and end + 11 <= len(data):
            face = data[at + 16:end].decode('cp1252', errors='replace')
            height = struct.unpack_from('<d', data, end + 1)[0]
            weight = struct.unpack_from('<H', data, end + 9)[0]
            colour = data[at + 12 + length - 4:at + 12 + length]
            if face.isprintable() and -400 < height < 400 and weight % 100 == 0 and 100 <= weight <= 900:
                font = {'face': face, 'height': int(round(height)), 'weight': weight}
                if len(colour) == 4 and colour[3] == 0:
                    font['colour'] = _rgb(colour)
                found['font'] = font
            record_end = at + 12 + length
            if record_end + 28 <= len(data):
                position, width = struct.unpack_from('<II', data, record_end + 20)
                if position in CAPTION and width < 2000:
                    found['caption'] = {'position': CAPTION[position], 'width': width}
    return found
