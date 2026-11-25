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
TITLE_MARK = b'\x96\x2c\x00\x00'
# frame types seen with a fill colour: 1 plain; 0x11 a vertical gradient from 15 % of the colour in white at the top
# to the colour at the bottom (designer images: #d9ecd9 -> #008000, #ffd9d9 -> #ff0000; 4,714 buttons)
FRAME_KINDS = {1: 'plain', 0x11: 'gradient'}
FRAME, ALIGN, FONT = b'\x64\x02\x00\x00', b'\x5b\x02\x00\x00', b'\x5e\x00\x00\x00\x01\x00\x00\x00'


# Windows system colours a stored colour can name (the whole u32; decompiled from the WINDEV 28 runtime, wd280obj.dll
# 0x100d9ac6, which ends in GetSysColor): their Windows 10 default values. 0xFF000000 / 0xFF000001 / 0xFBADC0DE = none.
SYSTEM_COLOURS = {
    0xF1000000: '#ffffff', 0xF1800000: '#ffffff',  # BTNHIGHLIGHT
    0xF2000000: '#f0f0f0',  # BTNFACE
    0xF3000000: '#a0a0a0', 0xF3800000: '#696969',  # BTNSHADOW, 3DDKSHADOW
    0xF4000000: '#000000', 0xF4800000: '#ffffff',  # BTNTEXT, WINDOW
    0xF5000000: '#0078d7', 0xF5800000: '#ffffff',  # HIGHLIGHT, HIGHLIGHTTEXT
    0xF6000000: '#000000', 0xF6800000: '#c8c8c8',  # WINDOWTEXT, SCROLLBAR
    0xF7000000: '#646464', 0xF7000001: '#f0f0f0', 0xF7800000: '#ababab',  # WINDOWFRAME, MENU, APPWORKSPACE
    0xF7900001: '#ffffe1', 0xF7900002: '#000000',  # INFOBK, INFOTEXT
}
NO_COLOUR = {0xFF000000, 0xFF000001, 0xFBADC0DE}


def colour(raw):
    """(css colour or None, system colour or not) of a stored 4-byte colour (RGB + flag byte)."""
    value = struct.unpack('<I', raw)[0]
    if value in SYSTEM_COLOURS:
        return SYSTEM_COLOURS[value], True
    if value in NO_COLOUR or raw[3] != 0:
        return None, False
    return _rgb(raw), False


def _rgb(raw):
    return '#%02x%02x%02x' % (raw[0], raw[1], raw[2])


def look(data):
    found = {}
    at = data.find(FRAME)
    if 0 <= at <= len(data) - 16:
        fill, system = colour(data[at + 8:at + 12])
        if fill:
            found['background'] = fill
            if system:
                found['background_system'] = True
            kind = struct.unpack_from('<I', data, at + 4)[0]
            if kind in FRAME_KINDS:
                found['fill'] = FRAME_KINDS[kind]
        border, _ = colour(data[at + 12:at + 16])
        if border:
            found['border'] = border
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
            text_colour = data[at + 12 + length - 4:at + 12 + length]
            if face.isprintable() and -400 < height < 400 and weight % 100 == 0 and 100 <= weight <= 900:
                font = {'face': face, 'height': int(round(height)), 'weight': weight}
                text, _ = colour(text_colour) if len(text_colour) == 4 else (None, False)
                if text:
                    font['colour'] = text
                found['font'] = font
            record_end = at + 12 + length
            if record_end + 28 <= len(data):
                position, width = struct.unpack_from('<II', data, record_end + 20)
                if position in CAPTION and width < 2000:
                    found['caption'] = {'position': CAPTION[position], 'width': width}
    return found
