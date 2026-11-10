#!/usr/bin/env python3
"""Decode what WINDEV sources hide: `internal_properties` of the text format and the blocks of binary (PCS) files.

  internal_properties : <base64>   = 8-byte header + cipher(16-byte key) + LZW-packed property chunks
  *.wdr *.wdp *.wdw *.wde *.wda … = "PCS" containers holding LZW-packed blocks (no cipher): query SQL,
                                     project code, analysis, compiled windows, thumbnails

Captions, geometry, tab order, anchors, initial state, linked items, images, styles and masks are all in there, so
the project documentation PDF is no longer the only source. The source is only read; nothing is executed.

  python3 scripts/windev_decode.py legacy/<project> --out analysis-local/decoded-1 [--dossier <dossier dir>]

Field offsets were calibrated on a format-25 project (WINDEV 25–28) against its dossier. `index.json` says how many
elements were recognised: on another version, read `coverage` first and compare with a dossier or the running app.
"""
import argparse
import base64
import collections
import hashlib
import json
import os
from pathlib import Path
import re
import struct

# The key WINDEV's editor sets for `internal_properties` (format 5 header). Not a secret of the project.
KEY = bytes.fromhex('51433ae724db4868aa4107db74b74c44')
STRING_START, STRING_END = b'\xff\xce\x88\xf1', b'\xfe\xed\x98\xe1'
FRAMED = re.compile(rb'(?s)\xff\xce\x88\xf1(.{4})(.*?)\x00\xfe\xed\x98\xe1')
UTF16 = re.compile(rb'(?:[\x20-\x7e\xa0-\xff]\x00){4,}')
# Common control block: version tag, x, y, width, height, 8 zero bytes, maximum width and height.
COMMON = re.compile(rb'(?s)(.{4})(.{16})\x00{8}\xff\xff\xff[\x07\x7f\xff]\xff\xff\xff[\x07\x7f\xff]')
IMAGE_FILE = re.compile(rb'\.(png|gif|jpe?g|bmp|ico|svg|tiff?|emf|wmf)$', re.I)
LINKED_ITEM = re.compile(r'[\w$]+\.[A-Za-z_]\w*')
FILE_PATH = re.compile(rb'^\.{0,2}\\|\.(png|gif|jpe?g|bmp|ico|svg|wdw|wde)$', re.I)
SKIP = {'.git', 'node_modules', 'backup', 'history', 'target', 'dist'}
TEXT_EXTENSIONS = {'.wdw', '.wde', '.wdg', '.wdc', '.wdp', '.wdr', '.wdi', '.wdt', '.wdm'}
DATA_EXTENSIONS = {'.fic', '.ndx', '.mmo', '.ftx', '.exe', '.dll', '.wdl', '.wdk', '.zip', '.pdf'}
STATES = {0: 'active', 1: 'read-only', 4: 'grayed'}
BUTTON_TYPES = {0: 'normal', 1: 'validate', 2: 'interrupt', 3: 'abort', 4: 'help'}   # 2 and 4: WINDEV's list, not observed
ANCHOR_BITS = {1: 'bottom', 2: 'height', 4: 'right', 8: 'width'}
# Control type codes of the text format -> the kind names WINDEV's documentation prints (each seen on the measured project).
KINDS = {'2': 'Edit control', '3': 'Static', '4': 'Button', '5': 'Check Box', '6': 'Radio Button', '7': 'List Box',
         '8': 'Image', '9': 'Table', '11': 'Spin', '14': 'Combo Box', '16': 'Tab', '20': 'Shape',
         '32': 'Internal Window', '40': 'Supercontrol', '47': 'Calendar', '80': 'Scheduler', '111': 'Dashboard'}
TAB_PANE_TOP = {0: 26, 2: 2}
STRETCH = {0: 'custom 9-slice scaling', 2: 'width and height'}     # of a button's background image
ALIGN_H = {0: 'left', 1: 'center', 2: 'right', 3: 'justified'}
ALIGN_V = {0: 'top', 1: 'center', 2: 'bottom'}                # bottom: WINDEV's list, not observed
INPUT_TYPES = {0: 'text', 1: 'numeric', 2: 'date', 3: 'time', 5: 'duration'}
STYLE_NAME = re.compile(r'\d{2,3} [^.\\]+\.\S+')         # `170 AquaBlue.BTN_Ok`: skin template, then its style
# A report element's type (chunk 15, 40 bytes after its name): bands, then controls.
REPORT_BANDS = {1: 'start of document', 2: 'page header', 4: 'body', 6: 'break header', 7: 'break footer',
                11: 'page footer', 12: 'end of document'}
REPORT_KINDS = {16: 'Calculation', 17: 'Shape', 18: 'Image', 20: 'Preset', 39: 'Static'}
REPORT_TYPES = {2: 'table', 4: 'label', 5: 'free'}
REPORT_SOURCES = {0: 'no data source', 1: 'embedded query', 6: 'text file'}   # the dossier's wording


# ---------------------------------------------------------------- cipher

def _single(key):
    total = sum(struct.unpack('<4I', key)) & 0xffffffff
    return ((total >> 16) + total) & 255


def decrypt(data, key=KEY):
    """The in-place stream transform of `internal_properties` (after the 8-byte header)."""
    d, n = bytearray(data), len(data)
    if n == 0:
        return b''
    if n == 1:
        return bytes([((_single(key) ^ d[0]) + 0x35) & 255])
    half = n >> 1 if n & 1 else None
    for i in range(n - 1, 0, -1):
        k = (i - 1) & 15
        if i == half:
            d[i] = ((((key[k] ^ d[i]) - 0x11) & 255 ^ key[15 - k]) - d[i - 1]) & 255
            continue
        j = n - 1 - i
        d[j] = ((key[k] ^ d[j]) - d[i]) & 255
        d[i] = ((key[15 - k] ^ d[i]) - d[i - 1] - d[j]) & 255
    d[0] = ((key[15] ^ d[0]) - d[n - 1]) & 255
    return bytes(d)


def encrypt(data, key=KEY):
    """Inverse of decrypt (tests and round trips; the tool never writes sources)."""
    d, n = bytearray(data), len(data)
    if n == 0:
        return b''
    if n == 1:
        return bytes([((d[0] - 0x35) & 255) ^ _single(key)])
    half = n >> 1 if n & 1 else None
    d[0] = key[15] ^ ((d[0] + d[n - 1]) & 255)
    for i in range(1, n):
        k = (i - 1) & 15
        if i == half:
            d[i] = key[k] ^ (((((d[i] + d[i - 1]) & 255) ^ key[15 - k]) + 0x11) & 255)
            continue
        j = n - 1 - i
        a = d[j]
        d[i] = key[15 - k] ^ ((d[i] + d[i - 1] + a) & 255)
        d[j] = key[k] ^ ((a + d[i]) & 255)
    return bytes(d)


# ---------------------------------------------------------------- LZW blocks

def unpack(src):
    """One packed block: type 0 = stored (u32 size, data); type 2/4 = LZW (u32 packed size, u32 size, u16 0, codes).

    Codes are read low bit first, 9 to 16 bits wide; code 0 resets the table, 0x101 ends, 1..0x100 are bytes."""
    kind = src[0]
    if kind == 0:
        size = struct.unpack_from('<I', src, 1)[0]
        if size > len(src) - 5:
            raise ValueError('stored block longer than its data')
        return bytes(src[5:5 + size])
    if kind not in (2, 4):
        raise ValueError(f'unknown block type {kind}')
    size = struct.unpack_from('<I', src, 5)[0]
    out, pos, buffer, held = bytearray(), 11, 0, 0
    prefix, char, following, bits, previous = {}, {}, 0x102, 9, None
    while len(out) < size:
        while held < bits and pos < len(src):
            buffer |= src[pos] << held
            held += 8
            pos += 1
        if held < bits and not buffer:
            raise ValueError('packed block ends early')
        code = buffer & ((1 << bits) - 1)
        buffer >>= bits
        held -= bits
        if previous is None:
            if not 1 <= code <= 0x100:
                raise ValueError('packed block starts with a control code')
            out.append(code - 1)
            previous = code
            continue
        if code == 0:
            prefix, char, following, bits, previous = {}, {}, 0x102, 9, None
            continue
        if code == 0x101:
            break
        known = code < following
        if code > following:
            raise ValueError('packed block uses an undefined code')
        text, current = bytearray(), code if known else previous
        while current > 0x100:
            text.append(char[current])
            current = prefix[current]
        text.append(current - 1)
        text.reverse()
        out += text
        if following < 0x10000:
            prefix[following], char[following] = previous, text[0]
            following += 1
            if bits < 16 and following >= 1 << bits:
                bits += 1
        if known:
            previous = code
        else:
            out.append(text[0])
            previous = following - 1
    if len(out) < size:
        raise ValueError('packed block shorter than declared')
    return bytes(out[:size])


def pack(data, stored=False):
    """Pack as WINDEV does (tests and round trips)."""
    if stored:
        return b'\0' + struct.pack('<I', len(data)) + bytes(data)
    codes, table, following, bits, widths = [], {}, 0x102, 9, []
    current = None
    for byte in data:
        if current is None:
            current = byte + 1
            continue
        if (current, byte) in table:
            current = table[current, byte]
            continue
        codes.append(current)
        widths.append(bits)
        if following < 0x10000:
            table[current, byte] = following
            following += 1
            # The reader adds its entry one code later, so it widens one code after the table would need it.
            if bits < 16 and following - 1 >= 1 << bits:
                bits += 1
        current = byte + 1
    if current is not None:
        codes.append(current)
        widths.append(bits)
    codes.append(0x101)
    widths.append(bits)
    buffer = held = 0
    body = bytearray()
    for code, width in zip(codes, widths):
        buffer |= code << held
        held += width
        while held >= 8:
            body.append(buffer & 255)
            buffer >>= 8
            held -= 8
    if held:
        body.append(buffer & 255)
    return b'\4' + struct.pack('<IIH', len(body), len(data), 0) + bytes(body)


# ---------------------------------------------------------------- property chunks

def decode_properties(value):
    """`internal_properties` value -> list of chunks {id, version, data}."""
    raw = base64.b64decode(value)
    plain = unpack(raw) if raw[:1] in (b'\0', b'\4') else unpack(decrypt(raw[8:]))
    count = plain[0]
    headers = [struct.unpack_from('<HHI', plain, 1 + 8 * i) for i in range(count)]
    offset, chunks = 1 + 8 * count, []
    for identifier, version, size in headers:
        chunks.append({'id': identifier, 'version': version, 'data': plain[offset:offset + size]})
        offset += size
    if offset != len(plain):
        raise ValueError('property chunks do not fill the block')
    return chunks


def encode_properties(chunks, header=b'\5\0\0\0\5\0\0\0'):
    plain = bytes([len(chunks)]) + b''.join(struct.pack('<HHI', c['id'], c['version'], len(c['data'])) for c in chunks)
    plain += b''.join(c['data'] for c in chunks)
    return base64.b64encode(header + encrypt(pack(plain))).decode('ascii')


def text(data, encoding='cp1252'):
    """A string of the project. Controls edited by a recent WINDEV keep their texts in UTF-8 beside older ones in
    the code page (both in one window here): bytes that are valid UTF-8 with an accented letter are UTF-8, which
    code-page text almost never is."""
    if any(byte >= 0x80 for byte in data):
        try:
            return data.decode('utf-8')
        except UnicodeDecodeError:
            pass
    return data.decode(encoding, 'replace')


def framed_string(data, offset, encoding='cp1252'):
    """A serialized string: one zero byte when empty, else marker, u32 total length, text, NUL, end marker."""
    if data[offset] == 0:
        return '', offset + 1
    if data[offset:offset + 4] != STRING_START:
        raise ValueError(f'no string at {offset}')
    length = struct.unpack_from('<I', data, offset + 4)[0]
    if data[offset + length - 4:offset + length] != STRING_END:
        raise ValueError(f'unterminated string at {offset}')
    return text(data[offset + 8:offset + length - 5], encoding), offset + length


def strings(data, encoding='cp1252'):
    """Every framed string of a chunk in file order, then UTF-16 runs outside them (report captions)."""
    found, covered = [], []
    for match in FRAMED.finditer(data):
        if match[2]:
            found.append({'offset': match.start(), 'text': text(match[2], encoding)})
        covered.append((match.start(), match.end()))
    for match in UTF16.finditer(data):
        if not any(start <= match.start() < end for start, end in covered):
            found.append({'offset': match.start(), 'text': match[0].decode('utf-16le'), 'utf16': True})
    return found


def fonts(data, encoding='cp1252'):
    """Font records of a chunk, in file order: a Windows LOGFONT whose face name is a framed string, then four
    bytes read here as the text colour (not checked against another source). Returns (fonts, byte spans)."""
    found, spans = [], []
    for match in FRAMED.finditer(data):
        start = match.start()
        if start < 28 or not match[2]:
            continue
        height, _, _, _, weight, italic, underline, strike = struct.unpack_from('<iiiiIBBB', data, start - 28)
        if not (5 <= abs(height) < 400 and weight % 100 == 0 and 100 <= weight <= 900
                and max(italic, underline, strike) <= 1) or FILE_PATH.search(match[2]) or b'\\' in match[2]:
            continue
        font = {'face': text(match[2], encoding), 'height': height, 'weight': weight}
        if height < 0:
            font['points'] = round(-height * 72 / 96, 1)       # a negative LOGFONT height is pixels at 96 dpi
        font.update({key: True for key, flag in (('italic', italic), ('underline', underline), ('strikeout', strike)) if flag})
        if start >= 48 and data[start - 48:start - 44] == b'\x5b\x02\0\0':
            # A font record (tag 0x25b) keeps how its text is aligned just before the LOGFONT.
            horizontal, vertical = struct.unpack_from('<II', data, start - 36)
            if horizontal in ALIGN_H and vertical in ALIGN_V:
                font.update({'h_align': ALIGN_H[horizontal], 'v_align': ALIGN_V[vertical]})
                spans.append((start - 36, 8))
        colour = data[match.end():match.end() + 4]
        if len(colour) == 4 and colour[3] == 0:
            font['colour'] = '#%02x%02x%02x' % (colour[0], colour[1], colour[2])
        found.append(font)
        spans += [(start - 28, 28), (match.end(), 4)]
    return found, spans


FRAME = re.compile(rb'(?s)\x62\x02\0\0(.)\0\0\0(.{3})([\0\xff])(.{3})\0')


def frames(data):
    """Frame records of a chunk (tag 0x262), in file order: a border type, a background colour (absent when the
    record says none) and a border colour. Read as colours by their shape; the text colours beside them match what
    the controls are for (a red warning, a yellow message), nothing else was checked against another source."""
    found = []
    for match in FRAME.finditer(data):
        frame = {'type': match[1][0], 'border_colour': '#' + match[4].hex()}
        if match[3] == b'\0':
            frame['background'] = '#' + match[2].hex()
        found.append(frame)
    return found


def anchors(value):
    return [name for bit, name in ANCHOR_BITS.items() if value & bit]


def control_fields(data, encoding='cp1252'):
    """The block every window control shares (chunk 0), found by its signature. Positions are relative to the parent."""
    match = COMMON.search(data)
    if not match:
        return None
    start = match.start() + 4
    x, y, width, height = struct.unpack_from('<4i', data, start)
    fields = {'x': x, 'y': y, 'width': width, 'height': height, 'layout_version': struct.unpack('<I', match[1])[0]}
    read = lambda offset: framed_string(data, offset, encoding)
    spans = fields['_spans'] = [(start - 4, 20), (start + 24, 8)]    # the bytes read as numbers, for the audit
    style = next((text(m[2], encoding) for m in FRAMED.finditer(data, 0, start)
                  if STYLE_NAME.fullmatch(text(m[2], encoding))), None)
    if style:
        fields['style'] = style     # the skin template's style the control was created from (none: a custom style)
    try:
        offset = start + 32
        fields['visible'] = bool(struct.unpack_from('<I', data, offset)[0])
        spans.append((offset, 4))
        fields['double_click_button'], offset = read(offset + 5)
        fields['popup_menu'], offset = read(offset)
        state = struct.unpack_from('<I', data, offset)[0]
        fields['state'] = STATES.get(state, state)
        spans.append((offset, 4))
        fields['tooltip'], offset = read(offset + 4)
        fields['caption'], offset = read(offset + 24)
        fields['plane'] = struct.unpack_from('<I', data, offset)[0]
        spans.append((offset, 4))
        fields['initial_value'], offset = read(offset + 4)
        anchor = struct.unpack_from('<H', data, offset)[0]
        fields['anchor'] = anchors(anchor)
        spans.append((offset, 2))
        fields['linked_item'], offset = read(offset + 2)
        fields['tab_stop'] = bool(struct.unpack_from('<I', data, offset)[0])
        fields['tab_order'] = struct.unpack_from('<i', data, offset + 16)[0] + 1   # kept when the stop is off; 0 = none
        spans += [(offset, 4), (offset + 16, 4)]
        fields['group'], offset = read(offset + 20)
        fields['order'] = struct.unpack_from('<H', data, offset)[0]   # 1..n among the controls of the same parent
        spans.append((offset, 2))
        right, wide, bottom, high = struct.unpack_from('<4I', data, offset + 12)
        fields['anchor_rates'] = {'right': right, 'bottom': bottom, 'width': wide, 'height': high}
        spans.append((offset + 12, 16))
        # The record of the control's own kind starts here. Some windows keep four more bytes per control before
        # it (118 of the 124 controls of one window measured): the marker that follows says which.
        marker = (b'\xff\xff\xff\x7f', b'\xff\xff\xff\xff')
        fields['_end'] = offset + 28 + (4 if data[offset + 58:offset + 62] in marker
                                        and data[offset + 54:offset + 58] not in marker else 0)
    except (ValueError, IndexError, struct.error) as error:
        fields['partial'] = str(error)
    return fields


def window_fields(data):
    """A window's own chunk 0: version tag at 16, then x, y, width, height."""
    if len(data) < 36:
        return None
    x, y, width, height = struct.unpack_from('<4i', data, 20)
    if not (0 < width < 20000 and 0 < height < 20000):
        return None
    return {'x': x, 'y': y, 'width': width, 'height': height, 'layout_version': struct.unpack_from('<I', data, 16)[0]}


OPENING = {2: 'Centered in the screen', 3: 'Centered in the parent window'}      # the dossier's wording


def window_record(data, encoding='cp1252'):
    """A window's title and options, 316 bytes after the face of its font: opening mode (one byte, 4 before),
    title, background image, then 5 bytes later four yes/no values (title bar, system menu, minimize icon,
    maximize icon) and, 46 bytes after the image, whether it has its own HFSQL context. Kept only when the two
    strings are there and every yes/no is 0 or 1."""
    faces = [offset for offset, width in fonts(data, encoding)[1] if width == 4]
    if not faces:
        return None
    try:
        title, offset = framed_string(data, faces[0] + 316, encoding)
        image, offset = framed_string(data, offset, encoding)
        bar, menu, minimize, maximize = struct.unpack_from('<4I', data, offset + 5)
        context = struct.unpack_from('<I', data, offset + 46)[0]
    except (ValueError, IndexError, struct.error):
        return None
    if max(bar, menu, minimize, maximize, context) > 1 or (image and not IMAGE_FILE.search(image.encode(encoding, 'replace'))):
        return None
    opening = data[faces[0] + 312]
    return {'title': title, 'background_image': image, 'opening_mode': OPENING.get(opening, opening),
            'title_bar': bool(bar), 'system_menu': bool(menu), 'minimize_icon': bool(minimize),
            'maximize_icon': bool(maximize), 'independent_hfsql_context': bool(context)}


def column_fields(data, encoding='cp1252'):
    """A table column's chunk 0: version tag, width, caption, alignment and options, the item it shows, more
    options. The options are kept only when every one of them is 0 or 1 (another layout is refused, not misread)."""
    try:
        caption, offset = framed_string(data, 8, encoding)
    except (ValueError, IndexError, struct.error):
        return None
    width = struct.unpack_from('<I', data, 4)[0]
    if width >= 20000:
        return None
    fields = {'width': width, 'caption': caption}
    try:
        align, _, _, sortable, moveable = struct.unpack_from('<5I', data, offset)
        linked, after = framed_string(data, offset + 32, encoding)
        adjustable, visible, _, multiline, search = struct.unpack_from('<5I', data, after + 4)
    except (ValueError, IndexError, struct.error):
        return fields
    if align in ALIGN_H and max(sortable, moveable, adjustable, visible, multiline, search) <= 1:
        fields.update({'h_align': ALIGN_H[align], 'sortable': bool(sortable), 'moveable': bool(moveable),
                       'linked_item': linked, 'adjustable_width': bool(adjustable), 'visible': bool(visible),
                       'multiline': bool(multiline), 'with_search': bool(search)})
        # The bytes read, for the audit (removed by `describe` unless asked for).
        fields['_spans'] = [(4, 4), (offset, 4), (offset + 12, 8), (after + 4, 4), (after + 16, 8)]
    return fields


def edit_record(data, end, encoding='cp1252'):
    """What follows the common block of an edit control, or of a table column's cell: a version tag, the input
    size, the input type, the type of the value, the alignment, then the input mask and the format of the value
    returned. Returns (fields, byte spans) or None when the tag is not where it is expected."""
    if len(data) < end + 123 or data[end + 51:end + 55] != b'\1\0\0\0' or data[end + 56] not in (2, 3) \
            or data[end + 57:end + 59] != b'\0\0':
        return None
    size, kind = struct.unpack_from('<I', data, end + 59)[0], struct.unpack_from('<I', data, end + 71)[0]
    fields = {'input_size': size, 'input_type': INPUT_TYPES.get(kind, kind),
              'value_type': struct.unpack_from('<H', data, end + 75)[0],     # WINDEV's code: 13 is a high-precision number
              'h_align': ALIGN_H.get(data[end + 77], data[end + 77])}
    try:
        fields['input_mask'], offset = framed_string(data, end + 121, encoding)
        fields['return_format'], _ = framed_string(data, offset, encoding)
    except (ValueError, IndexError, struct.error):
        pass
    return fields, [(end + 55, 8), (end + 71, 4), (end + 75, 3)]


def list_record(data, end, encoding='cp1252'):
    """What follows the common block of a list box, or of a combo box's `dropdown`: a version tag, whether the
    content is in memory, then the content typed in the designer (one value per line), the file or query browsed,
    the item browsed, the item displayed and the item stored. Returns the fields or None when the tag is not
    where it is expected."""
    if len(data) < end + 76 or data[end + 51:end + 55] != b'\1\0\0\0' or data[end + 56] not in (2, 3) \
            or data[end + 57:end + 59] != b'\0\0':
        return None
    try:
        content, offset = framed_string(data, end + 71, encoding)
        browsed_file, offset = framed_string(data, offset, encoding)
        browsed_item, offset = framed_string(data, offset, encoding)
        displayed, offset = framed_string(data, offset + 4, encoding)
        stored, offset = framed_string(data, offset, encoding)
    except (ValueError, IndexError, struct.error):
        return None
    memory = struct.unpack_from('<I', data, end + 63)[0]
    if memory > 1:
        return None
    # A file's content is loaded in memory or read with direct access: where that choice is kept is not known yet.
    fields = {'source': 'memory' if memory else 'file'}
    if content:
        fields['initial_content'] = content.replace('\r\n', '\n').split('\n')
    fields.update({key: value for key, value in (('browsed_file', browsed_file), ('browsed_item', browsed_item),
                                                 ('displayed_item', displayed), ('stored_item', stored)) if value})
    return fields


def action_fields(data, encoding='cp1252'):
    """A predefined action attached to an event slot (chunk 9 of a `p_codes` entry). Every slot has the same five
    short strings; an action that needs an element of the project adds a record after them: a kind (u32, 16 bytes
    before the name) and the element's name. Seen here: kind 1100 with a report's name on the Print buttons the
    RAD generated. Returns None for a slot with no such record."""
    found = [m for m in FRAMED.finditer(data)]
    if len(found) < 6 or not found[5][2] or found[5].start() < 16:
        return None
    return {'action_code': struct.unpack_from('<I', data, found[5].start() - 16)[0],
            'action_target': text(found[5][2], encoding)}


def report_page(data, encoding='cp1252'):
    """A report's own chunk 15: its name, type and data source, then the page as doubles in millimetres (height,
    width, margins top, bottom, left, right). The doubles are found by their shape: eight plausible lengths in a
    row, the first two a page size."""
    try:
        name, offset = framed_string(data, 2, encoding)
        kind, source, _, page_format = struct.unpack_from('<4I', data, offset + 9)
    except (ValueError, IndexError, struct.error):
        return None
    fields = {'report_type': REPORT_TYPES.get(kind, kind), 'data_source': REPORT_SOURCES.get(source, source),
              'page_format_code': page_format}        # 0 custom size, 1 A4 in the reports measured
    query = next((text(m[2], encoding) for m in FRAMED.finditer(data, offset) if m[2].endswith(b'$Query')), None)
    if query:
        fields['embedded_query'] = query
    for position in range(offset + 32, len(data) - 64):
        values = struct.unpack_from('<8d', data, position)
        if all(0 <= v <= 5000 and abs(v * 100 - round(v * 100)) < 1e-6 for v in values) and min(values[:2]) >= 10:
            fields.update({'page_height_mm': round(values[0], 2), 'page_width_mm': round(values[1], 2),
                           'margins_mm': dict(zip(('top', 'bottom', 'left', 'right'), (round(v, 2) for v in values[2:6])))})
            break
    return fields


def report_fields(data, encoding='cp1252'):
    """A report band or control (chunk 15): its name, 8 bytes, then top, bottom, left, right in millimetres.
    A control's values are relative to its band; a band's are its place in the report."""
    try:
        name, offset = framed_string(data, 0, encoding)
        top, bottom, left, right = struct.unpack_from('<4d', data, offset + 8)
    except (ValueError, IndexError, struct.error):
        return None
    if not name or not all(-1e4 < value < 1e5 for value in (top, bottom, left, right)):
        return None
    fields = {'x_mm': round(left, 3), 'y_mm': round(top, 3), 'width_mm': round(right - left, 3),
              'height_mm': round(bottom - top, 3)}
    if len(data) > offset + 40:
        fields['type_code'] = data[offset + 40]       # REPORT_BANDS for a band, REPORT_KINDS for a control
    return fields


def button_tail(data, end, encoding='cp1252'):
    """What follows a button's common block: caption, background image, its number of states, image, the image's
    number of states. The record starts 107 bytes after the block (111 is tried for a layout seen before the block's
    end was settled); a reading is kept only when its strings are exactly the first strings found there, so a
    shifted layout is refused instead of misread."""
    found = [m.start() for m in FRAMED.finditer(data, end) if m[2]]
    for start in (end + 107, end + 111):
        try:
            caption, after_caption = framed_string(data, start, encoding)
            background, after_background = framed_string(data, after_caption, encoding)
            states = struct.unpack_from('<I', data, after_background)[0]
            image, after_image = framed_string(data, after_background + 4, encoding)
            image_states = struct.unpack_from('<I', data, after_image)[0]
        except (ValueError, IndexError, struct.error):
            continue
        used = [offset for offset, value in ((start, caption), (after_caption, background), (after_background + 4, image))
                if value]
        if used and used == found[:len(used)]:
            return {'caption': caption, 'background_image': background, 'background_states': states, 'image': image,
                    **({'image_states': image_states} if image_states <= 64 else {})}
    return None


def describe(owner, kind, chunks, encoding='cp1252', keep_end=False):
    """Named fields for the element kinds whose layout is known; every chunk's strings for all of them."""
    by_id = {c['id']: c['data'] for c in chunks}
    fields = None
    if owner in ('controls', 'content', 'dropdown', 'calendar') and 0 in by_id:
        # `content` is the cell of a table column: a control of its own (an edit control for a text column).
        fields = control_fields(by_id[0], encoding)
        end = fields.pop('_end', None) if fields else None
        spans = fields.pop('_spans', []) if fields else []
        used, font_spans = fonts(by_id[0], encoding) if fields is not None else ([], [])
        face_end = next((offset for offset, width in font_spans if width == 4), 0)     # where the first font's face ends
        if fields is not None and kind == '2' and end:
            record = edit_record(by_id[0], end, encoding)
            if record:
                fields.update(record[0])
                spans = spans + record[1]
        if fields is not None and (kind == '7' or owner == 'dropdown') and end:
            fields.update(list_record(by_id[0], end, encoding) or {})
        if fields is not None and kind in ('5', '6'):
            # A check box or radio button names two pictures: the one behind the selected choice, then its tick.
            pictures = [text(m[2], encoding) for m in FRAMED.finditer(by_id[0]) if m[2] and IMAGE_FILE.search(m[2])]
            if len(pictures) >= 2:
                fields['tick_image'] = pictures[1]
        if fields is not None and kind == '3' and used and 'h_align' in used[0]:
            fields.update({'h_align': used[0]['h_align'], 'v_align': used[0]['v_align']})   # a static's only font
        if fields is not None and owner == 'controls' and kind in ('2', '14') and used \
                and len(by_id[0]) >= face_end + 32 and struct.unpack_from('<I', by_id[0], face_end + 24)[0] == 4:
            # After the caption's font: where the input area starts, from the control's left edge.
            fields['caption_width'] = struct.unpack_from('<I', by_id[0], face_end + 28)[0]
            spans = spans + [(face_end + 28, 4)]
        if keep_end and fields is not None:
            # Where the shared block ends (an anchor) and which bytes were read, for windev_fieldmap.py.
            fields['_spans'] = spans + ([(len(by_id[0]) - 50, 1)] if kind == '4' else []) \
                + ([(len(by_id[0]) - 58, 4)] if kind == '16' else [])
            if end:
                fields['_end'] = end
        if fields is not None and kind == '4' and len(by_id[0]) >= 50:
            fields['button_type'] = BUTTON_TYPES.get(by_id[0][-50], by_id[0][-50])
            tail = button_tail(by_id[0], end, encoding) if end else None
            if tail:
                fields.update({key: value for key, value in tail.items() if key != 'caption' or not fields['caption']})
            elif end and not fields['caption']:
                # A button's caption follows the common block; a picture-only button has its image there instead.
                after = [m for m in FRAMED.finditer(by_id[0], end) if m[2]]
                if after and not IMAGE_FILE.search(after[0][2]):
                    fields['caption'] = text(after[0][2], encoding)
        faces = [offset for offset, width in font_spans if width == 4]
        if fields is not None and kind == '4' and len(faces) >= 4 and fields.get('background_image') \
                and len(by_id[0]) >= faces[3] + 56:
            # 52 bytes after a button's fourth font: how the background image is stretched.
            stretch = struct.unpack_from('<I', by_id[0], faces[3] + 52)[0]
            if stretch in STRETCH:
                fields['background_stretch'] = STRETCH[stretch]
        if fields is not None and kind == '16' and len(by_id[0]) >= 58:
            # Where a tab's panes start below its top edge, by tab style (two styles measured; others stay unknown).
            style = struct.unpack_from('<I', by_id[0], len(by_id[0]) - 58)[0]
            if style in TAB_PANE_TOP:
                fields['pane_top'] = TAB_PANE_TOP[style]
    elif owner == 'tabs' and 0 in by_id:
        try:
            fields = {'caption': framed_string(by_id[0], 4, encoding)[0]}
        except (ValueError, IndexError, struct.error):
            fields = None
    elif owner == 'options' and 0 in by_id:
        # A menu option or one choice of a radio button or check box: its caption is its first string.
        first = next((m[2] for m in FRAMED.finditer(by_id[0]) if m[2]), None)
        fields = {'caption': text(first, encoding)} if first is not None and FRAMED.search(by_id[0]).start() <= 8 else None
    elif owner == 'report' and 15 in by_id:
        fields = report_page(by_id[15], encoding)
    elif owner in ('controls', 'blocks') and 15 in by_id:
        fields = report_fields(by_id[15], encoding)
        if fields is not None and owner == 'blocks' and fields.get('type_code') in REPORT_BANDS:
            fields['band'] = REPORT_BANDS[fields['type_code']]
        if fields is not None and owner == 'controls':
            if fields.get('type_code') in REPORT_KINDS:
                fields['kind'] = REPORT_KINDS[fields['type_code']]
            # What a report control prints: the item it is linked to (`Query.item`, chunk 1), else its own text,
            # mask or preset (`[PAGENUM]/[NBPAGES]`) - the last string that is neither its name nor a font face.
            faces = {font['face'] for font in fonts(by_id[15], encoding)[0]}
            texts = [text(m[2], encoding) for m in FRAMED.finditer(by_id[15]) if m[2]][1:]
            linked = next((t for t in (text(m[2], encoding) for m in FRAMED.finditer(by_id.get(1, b'')) if m[2])
                           if LINKED_ITEM.fullmatch(t)), None)
            if linked:
                fields['linked_item'] = linked
            content = [t for t in texts if t not in faces and (not linked or t != linked.rsplit('.', 1)[-1])]
            if content:
                fields['content'] = content[-1]
    elif owner == 'window' and 0 in by_id:
        fields = window_fields(by_id[0])
        if fields is not None:
            # The title follows the window's font; an empty title leaves a file path there instead.
            texts = [m[2] for m in FRAMED.finditer(by_id[0]) if m[2] and not m[2].startswith(b'<')]
            title = texts[1] if len(texts) > 1 else b''
            fields['title'] = '' if FILE_PATH.search(title) else text(title, encoding)
            fields.update(window_record(by_id[0], encoding) or {})     # by position, when the record is where expected
    elif owner == 'p_codes' and 9 in by_id:
        fields = action_fields(by_id[9], encoding)
    elif owner == 'columns' and 0 in by_id:
        fields = column_fields(by_id[0], encoding)
        if fields and not keep_end:
            fields.pop('_spans', None)
    return fields


# ---------------------------------------------------------------- text sources

LINE = re.compile(r'^( *)(- +)?([^\s:#][^:]*?)\s*:(?:\s+(.*))?$')


def property_slots(source):
    """Every `internal_properties` of a text source: line, owner (the key holding it: controls, columns, window…),
    the element's name and type, and the enclosing named elements."""
    lines = source.splitlines()
    indents = [len(line) - len(line.lstrip(' ')) for line in lines]
    parsed = [LINE.match(line) for line in lines]
    slots = []
    for index, match in enumerate(parsed):
        if not match or match[3] != 'internal_properties' or not match[4]:
            continue
        indent = indents[index]
        name = kind = owner = ''
        parents, level, in_item = [], indent, True
        for back in range(index - 1, -1, -1):
            stripped = lines[back].strip()
            if not stripped or indents[back] > level:
                continue
            if indents[back] < level:
                if stripped == '-':
                    in_item = False     # the element's own list item starts here
                    continue
                if not parsed[back]:
                    continue
                if not owner:
                    owner = parsed[back][3]
                level, in_item = indents[back], True   # now among the siblings of the holder: the parent's keys
            elif in_item and parsed[back] and parsed[back][3] == 'name' and parsed[back][4]:
                if level == indent:
                    name = name or parsed[back][4]
                else:
                    parents.append(parsed[back][4])
                in_item = False
        for forward in range(index + 1, len(lines)):
            stripped = lines[forward].strip()
            if not stripped or indents[forward] > indent:
                continue
            if indents[forward] < indent:
                break
            if parsed[forward] and parsed[forward][3] == 'type':
                kind = parsed[forward][4] or ''
                break
        slots.append({'line': index + 1, 'owner': owner, 'name': name, 'type': kind,
                      'parents': list(reversed(parents)), 'value': match[4]})
    return slots


def decode_source(source, encoding='cp1252', raw=False, mapper=None, fieldmap=None, unit='', suffix='.wdw',
                  samples=None):
    elements, panes, columns = [], {}, {}
    for slot in property_slots(source):
        entry = {key: slot[key] for key in ('line', 'owner', 'name', 'type', 'parents')}
        try:
            chunks = decode_properties(slot['value'])
        except (ValueError, IndexError, struct.error, KeyError) as error:
            entry['error'] = str(error)
            elements.append(entry)
            continue
        entry['chunks'] = [{'id': c['id'], 'version': c['version'], 'size': len(c['data']),
                            'strings': strings(c['data'], encoding), **({'hex': c['data'].hex()} if raw else {})}
                           for c in chunks]
        fields = describe(slot['owner'], slot['type'], chunks, encoding, keep_end=mapper is not None)
        if mapper is not None:
            # Properties a field map names (windev_fieldmap.py), and the chunk kept for the audit.
            properties = {}
            for chunk in chunks:
                sample = mapper.sample_of(unit, suffix, slot, chunk, fields or {}, encoding)
                properties.update(mapper.apply(fieldmap or {}, sample))
                if samples is not None:
                    samples.append(sample)
            if properties:
                entry['properties'] = properties
            (fields or {}).pop('_end', None)
            (fields or {}).pop('_spans', None)
        if fields:
            entry['fields'] = fields
        used = [f for c in chunks if c['id'] in (0, 15) for f in fonts(c['data'], encoding)[0]]
        if used:
            entry['fonts'] = used
        if slot['owner'] == 'controls' and suffix == '.wdw':
            boxes = [frame for c in chunks if c['id'] == 0 for frame in frames(c['data'])]
            if boxes:
                entry['frames'] = boxes
        for chunk in chunks:
            if chunk['data'][:4] == b'PCS\0':   # an embedded query is a whole container inside the element
                sql = next((s['sql'] for s, _ in decode_container(chunk['data'], encoding)['blocks'] if s.get('sql')), None)
                if sql:
                    entry['sql'] = sql
        if slot['owner'] in ('controls', 'content') and slot['type'] in KINDS:
            entry['kind'] = KINDS[slot['type']]
        elif slot['owner'] == 'controls' and (fields or {}).get('kind'):
            entry['kind'] = fields['kind']          # a report control: its type is in the properties only
        # A tab's panes come before their controls: a control directly under a tab is in the last pane seen.
        if slot['owner'] == 'columns':
            columns[tuple(slot['parents'])] = entry['index'] = columns.get(tuple(slot['parents']), 0) + 1   # 1..n in its table
        if slot['owner'] == 'tabs':
            panes[tuple(slot['parents'])] = panes.get(tuple(slot['parents']), 0) + 1
            entry['pane'] = panes[tuple(slot['parents'])]
        elif slot['owner'] == 'controls' and tuple(slot['parents']) in panes:
            entry['pane'] = panes[tuple(slot['parents'])]
        elements.append(entry)
    return place(elements)


def place(elements):
    """Window coordinates: the parents' positions added, plus each tab's pane origin where its style is known.
    A table (9) places controls in cells: those children keep parent-relative positions only."""
    controls = {e['name']: e for e in elements if e['owner'] == 'controls' and 'x' in e.get('fields', ())}
    for entry in controls.values():
        chain = [controls[name] for name in entry['parents'] if name in controls]
        if any(parent['type'] == '9' or (parent['type'] == '16' and 'pane_top' not in parent['fields']) for parent in chain):
            continue
        entry['fields']['window_x'] = entry['fields']['x'] + sum(parent['fields']['x'] for parent in chain)
        entry['fields']['window_y'] = entry['fields']['y'] + sum(parent['fields']['y'] + parent['fields'].get('pane_top', 0)
                                                               for parent in chain)
    return elements


# A named element of a binary window: version tag, its name, an 8-byte identifier, then the rectangle and the
# signature of the common block. A control's own part starts at the tag 0x270 before it.
BINARY_ELEMENT = re.compile(rb'(?s)(.\x02\x00\x00)\xff\xce\x88\xf1.{4}([^\x00]{1,200})\x00\xfe\xed\x98\xe1.{8}'
                            rb'(.{16})\x00{8}\xff\xff\xff[\x07\x7f\xff]\xff\xff\xff[\x07\x7f\xff]')
# A control's own part: a version tag (0x270 in format 25, 0x273 and 0x274 seen in 28), a length, then one of the
# words that open a kind's style.
BINARY_HEAD = re.compile(rb'(?s)[\x68-\x7f]\x02\x00\x00.{4}'
                         rb'(?:\x60\x1b\x00\x00|\xbd\x02\x00\x00|[\x10-\x1f]\x01\x00\x00|\x6f\x02\x00\x00)')


# A record without a name of its own (a column's cell, a combo's list, an edit's calendar): the same shape, with
# one zero byte where the name would be. A column: its name, a version tag, its name again. A tab's pane: tag 0x25a.
BINARY_UNNAMED = re.compile(rb'(?s)(.\x02\x00\x00)\x00.{8}(.{16})\x00{8}\xff\xff\xff[\x07\x7f\xff]\xff\xff\xff[\x07\x7f\xff]')
BINARY_COLUMN = re.compile(rb'(?s)(\xff\xce\x88\xf1.{4}([^\x00]{1,200})\x00\xfe\xed\x98\xe1)(.\x02\x00\x00)\1.{8}')
BINARY_PANE = re.compile(rb'\x5a\x02\x00\x00(?=\xff\xce\x88\xf1|\x00)')
COLUMN_END = b'\xba\xab\xba\xab'
# A menu option: its name, an identifier, one or two tags, then its caption.
BINARY_OPTION = re.compile(rb'(?s)\xff\xce\x88\xf1.{4}([A-Za-z_\x80-\xff][\w$\x80-\xff]{0,200})\x00\xfe\xed\x98\xe1.{8}'
                           rb'(\xc2\x02\x00\x00)?\xc4\x02\x00\x00(?:\xff\xce\x88\xf1.{4}([^\x00]*)\x00\xfe\xed\x98\xe1|\x00)')
UNNAMED_OWNERS = {7: 'dropdown', 47: 'calendar'}


def binary_window(block, encoding='cp1252'):
    """The elements of a window saved in WINDEV's binary format (the first packed block of its `.wdw`), in the
    shape `decode_source` gives. Each control is the record a text source keeps in chunk 0, with its name and
    identifier inside it and, just before it, its length and its type; a control inside another lies within the
    other's length. Taking the name out gives the text format's bytes (file paths apart: absolute here), so the
    same readers apply. A table's columns, each with its cell, a combo's list, a tab's panes and the options of
    check boxes and radio buttons sit inside their control's record and are listed after it. The window itself
    comes first, with its size, then its menu's options in file order (which sub-menu an option is in is not
    read)."""
    named = list(BINARY_ELEMENT.finditer(block))
    heads = [m.start() for m in BINARY_HEAD.finditer(block)]
    elements = []
    # The window itself opens the block (after four zero bytes in format 28): tag, name, identifier, then x, y,
    # width, height.
    for start in (0, 4):
        try:
            title, offset = framed_string(block, start + 4, encoding)
            x, y, width, height = struct.unpack_from('<4i', block, offset + 8)
        except (ValueError, IndexError, struct.error):
            continue
        if title and block[start + 1:start + 4] == b'\x02\0\0' and 0 < width < 20000 and 0 < height < 20000:
            elements.append({'line': None, 'owner': 'window', 'name': title, 'type': '', 'parents': [],
                             'fields': {'x': x, 'y': y, 'width': width, 'height': height}})
            break
    window = [e['name'] for e in elements]
    for number, match in enumerate(BINARY_OPTION.finditer(block)):
        if number == 0:     # the menu itself comes first, under its own name
            elements.append({'line': None, 'owner': 'menu', 'name': text(match[1], encoding), 'type': '', 'parents': window})
            continue
        elements.append({'line': None, 'owner': 'options', 'name': text(match[1], encoding), 'type': '',
                         'parents': window + ['MENU'], 'fields': {'caption': text(match[3] or b'', encoding)}})
    # Every item with where it starts and ends: (start, order, kind of item, details).
    items = []
    for index, match in enumerate(named):
        # A control's own part starts at the first version tag after the previous element's name whose length
        # (the four bytes 8 before it) reaches past this name and stays inside the block, with a type before it.
        for candidate in heads:
            if candidate < 8 or candidate <= (named[index - 1].start() if index else 0) or candidate >= match.start():
                continue
            size, kind = struct.unpack_from('<II', block, candidate - 8)
            if match.end() < candidate - 8 + size <= len(block) and 0 < kind < 0x200:
                items.append((candidate - 8, 'control', {'head': candidate, 'end': candidate - 8 + size, 'kind': kind,
                                                         'match': match}))
                break
    cells, head_set = set(), set(heads)
    for match in BINARY_COLUMN.finditer(block):
        try:
            caption, offset = framed_string(block, match.end() + 4, encoding)
            linked, after = framed_string(block, offset + 32, encoding)
        except (ValueError, IndexError, struct.error):
            continue
        kind = struct.unpack_from('<I', block, match.start() - 4)[0] if match.start() >= 4 else 0
        # The cell follows the linked item: a word, its type, then its record.
        cell = BINARY_UNNAMED.search(block, after + 8, after + 8 + 20000) if after + 8 in head_set else None
        end = block.find(COLUMN_END, cell.end() if cell else after)
        if end < 0 or not 0 < kind < 0x200:
            continue
        details = {'name': text(match[2], encoding), 'kind': kind, 'end': end + 4, 'tag': match[3], 'body': match.end(),
                   'after': after, 'cell': cell}
        if cell:
            cells.add(cell.start())
            details['cell_kind'] = struct.unpack_from('<I', block, after + 4)[0]
        items.append((match.start() - 4, 'column', details))
    for match in BINARY_UNNAMED.finditer(block):
        if match.start() in cells:
            continue
        head = max((h for h in heads if h < match.start()), default=None)
        if head is not None and head >= 4:
            items.append((head - 4, 'unnamed', {'head': head, 'kind': struct.unpack_from('<I', block, head - 4)[0],
                                                'match': match}))
    controls = [item[2] for item in items if item[1] == 'control']
    for tab in controls:
        if tab['kind'] != 16:
            continue
        inside = [(c['head'] - 8, c['end']) for c in controls if tab['head'] < c['head'] and c['end'] <= tab['end']]
        for pane in BINARY_PANE.finditer(block, tab['match'].end(), tab['end']):
            if not any(start <= pane.start() < end for start, end in inside):
                items.append((pane.start(), 'pane', {'at': pane.end()}))
    items.sort(key=lambda item: item[0])
    starts = [item[0] for item in items]
    open_controls, panes, column = [], {}, None

    def after_block(rectangle, limit):
        # Where a record's common block ends in the block, so that its own strings (group, linked item) are not
        # taken for what follows it.
        common = control_fields(b'\x5f\x02\0\0' + block[rectangle:limit], encoding) or {}
        return rectangle + common['_end'] - 4 if '_end' in common else limit

    def options(first, last, parents):
        # Each choice of a check box or radio button: its caption, then the word 0x0e.
        for option in FRAMED.finditer(block, first, last):
            if option[2] and block[option.end():option.end() + 4] == b'\x0e\0\0\0':
                elements.append({'line': None, 'owner': 'options', 'name': '', 'type': '', 'parents': parents,
                                 'fields': {'caption': text(option[2], encoding)}})

    def record(entry, kind, chunk):
        fields = describe(entry['owner'], str(kind), [{'id': 0, 'version': 14, 'data': chunk}], encoding)
        if fields:
            entry['fields'] = fields
        used = fonts(chunk, encoding)[0]
        if used:
            entry['fonts'] = used
        if str(kind) in KINDS and entry['owner'] != 'columns':
            entry['kind'] = KINDS[str(kind)]

    for index, (start, what, item) in enumerate(items):
        following = starts[index + 1] if index + 1 < len(items) else len(block)
        open_controls = [c for c in open_controls if start < c['end']]
        parents = window + [c['name'] for c in open_controls]
        if column and start < column['end'] and what != 'column':
            parents = parents + [column['name']]        # inside a column: a control in its cells, its combo's list
        if what == 'pane':
            tab = open_controls[-1] if open_controls and open_controls[-1]['kind'] == 16 else None
            try:
                caption, _ = framed_string(block, item['at'], encoding)
            except (ValueError, IndexError, struct.error):
                continue
            if tab is not None:
                panes[tab['name']] = panes.get(tab['name'], 0) + 1
                elements.append({'line': None, 'owner': 'tabs', 'name': '', 'type': '', 'parents': parents,
                                 'fields': {'caption': caption}, 'pane': panes[tab['name']]})
        elif what == 'control':
            match, kind = item['match'], item['kind']
            name = text(match[2], encoding)
            # Its children follow its own record, inside its length: the record stops where the first one starts.
            own = min(item['end'], following)
            chunk = block[item['head']:match.start() + 4] + block[match.start(3):own]
            if kind == 16 and own < item['end']:
                chunk += block[item['end'] - 58:item['end']]      # a tab's style follows its panes and their controls
            entry = {'line': None, 'owner': 'controls', 'name': name, 'type': str(kind), 'parents': parents}
            record(entry, kind, chunk)
            boxes = frames(chunk)
            if boxes:
                entry['frames'] = boxes
            # A control directly inside a tab belongs to the last pane that started before it.
            if open_controls and open_controls[-1]['kind'] == 16 and panes.get(open_controls[-1]['name']):
                entry['pane'] = panes[open_controls[-1]['name']]
            elements.append(entry)
            if kind in (5, 6):
                options(after_block(match.start(3), own), own, parents + [name])
            open_controls.append({'name': name, 'end': item['end'], 'kind': kind, 'columns': 0})
        elif what == 'column':
            table = open_controls[-1] if open_controls else None
            cell = item['cell']
            # The text format's column record: tag, then what follows the identifier, without the cell in the middle.
            chunk = item['tag'] + block[item['body']:item['after'] + 4] + block[item['end'] - 74:item['end']]
            entry = {'line': None, 'owner': 'columns', 'name': item['name'], 'type': str(item['kind']), 'parents': parents}
            fields = column_fields(chunk, encoding)
            if fields:
                fields.pop('_spans', None)
                entry['fields'] = fields
            if table is not None:
                table['columns'] += 1
                entry['index'] = table['columns']
            elements.append(entry)
            if cell:
                head = item['after'] + 8
                content = {'line': None, 'owner': 'content', 'name': '', 'type': str(item['cell_kind']),
                           'parents': parents + [item['name']]}
                record(content, item['cell_kind'], block[head:cell.start() + 4] + block[cell.start(2):item['end'] - 74])
                elements.append(content)
                if item['cell_kind'] in (5, 6):
                    options(after_block(cell.start(2), item['end']), min(following, item['end']), parents + [item['name']])
            column = {'name': item['name'], 'end': item['end']}
        else:
            match, kind = item['match'], item['kind']
            if not 0 < kind < 0x200:
                continue
            entry = {'line': None, 'owner': UNNAMED_OWNERS.get(kind, 'content'), 'name': '', 'type': str(kind), 'parents': parents}
            limit = min([following] + [c['end'] for c in open_controls[-1:]])
            record(entry, kind, block[item['head']:match.start() + 4] + block[match.start(2):limit])
            elements.append(entry)
    return place(elements)


REPORT_NAME = re.compile(rb'\xff\xce\x88\xf1.{4}([A-Za-z_\x80-\xff][\w$\x80-\xff]{0,200})\x00\xfe\xed\x98\xe1', re.S)


def binary_report(block, encoding='cp1252', others=()):
    """The bands and controls of a report saved in binary format (the first packed block of its `.wde`), in the
    shape `decode_source` gives. Each is the record a text source keeps in chunk 15 — its name, eight bytes, its
    geometry as four doubles, its type — with its length just before (zero for a band, whose record holds its
    controls). A record is taken where the geometry is plausible and the type is a known band or control kind, or
    where its length is given and fits. The report's own record (type, data source, page) opens the block. The
    item a control prints is in another packed block (`others`), after the control's name."""
    elements = []
    start = block.find(b'\x59\x00\xff\xce\x88\xf1')
    page = report_page(block[start:], encoding) if start >= 0 else None
    if page:
        elements.append({'line': None, 'owner': 'report', 'name': '', 'type': '', 'parents': [], 'fields': page})
    band = None
    for match in REPORT_NAME.finditer(block):
        if match.start() < 4:
            continue
        size = struct.unpack_from('<I', block, match.start() - 4)[0]
        sized = 64 < size <= len(block) - match.start() + 4
        fields = report_fields(block[match.start():match.start() + (size if sized else 200)], encoding)
        code = (fields or {}).get('type_code')
        if not fields or (code not in REPORT_BANDS and code not in REPORT_KINDS and not sized) or fields['width_mm'] < 0 \
                or fields['height_mm'] < 0 or not 0 < code < 200:
            continue
        entry = {'line': None, 'name': text(match[1], encoding), 'type': '', 'fields': fields}
        if code in REPORT_BANDS:
            fields['band'] = REPORT_BANDS[code]
            entry.update(owner='blocks', parents=[])
            band = entry['name']
        else:
            record = block[match.start():match.start() + size - 4] if sized else block[match.start():match.start() + 200]
            if code in REPORT_KINDS:
                fields['kind'] = entry['kind'] = REPORT_KINDS[code]
            used = fonts(record, encoding)[0]
            if used:
                entry['fonts'] = used
            entry['_record'] = record
            entry.update(owner='controls', parents=[band] if band else [])
        elements.append(entry)
    # The item each control prints: the first `<query>.<item>` after the control's name in another block.
    names = {e['name'] for e in elements if e['owner'] in ('controls', 'blocks')}
    linked = {}
    for other in others:
        current = None
        for match in FRAMED.finditer(other):
            value = text(match[2], encoding)
            if value in names:
                current = value
            elif current and '$' in value and LINKED_ITEM.fullmatch(value):
                linked.setdefault(current, value)
                current = None
    for entry in elements:
        record = entry.pop('_record', None)
        if record is None:
            continue
        fields = entry['fields']
        if entry['name'] in linked:
            fields['linked_item'] = linked[entry['name']]
        faces = {font['face'] for font in entry.get('fonts') or []}
        item = fields.get('linked_item', '').rsplit('.', 1)[-1]
        content = [t for t in (text(m[2], encoding) for m in list(FRAMED.finditer(record))[1:] if m[2])
                   if t not in faces and (not item or t != item)]
        if content:
            fields['content'] = content[-1]
    return elements


# In a binary element's code block: the header of one event's code (0x14, a length, the number of lines, the event,
# then the lines), and the name of the control the following headers belong to (after its code type).
CODE_HEADER = re.compile(rb'(?s)[\x14-\x1f].{4}(.{4})(.{4})\x00{4,5}\x01\x00\x00\x00(?=\x03)')      # 0x14 in 25, 0x15 in 28
CODE_OWNER = re.compile(rb'(?s)(.{4})\xff\xce\x88\xf1.{4}([A-Za-z_\x80-\xff][\w$\x80-\xff]{0,200})\x00\xfe\xed\x98\xe1')


def binary_code(block, encoding='cp1252'):
    """The code of an element saved in binary format, from one packed block: [{control, event, lines}] in file
    order. Each event's code is a header (0x14, a length, the number of lines, the event's number as the text format
    writes it in `type :`) followed by its lines, each `03, text, who wrote it, 12 bytes`; an empty line has no
    text, and the writer is often empty too. The name of a control, after the number of its code type, opens the
    headers that belong to it; before any name the code is the element's own. A procedure is a block whose first
    line declares it (event 458752 in a window)."""
    marks = []
    for match in CODE_OWNER.finditer(block):
        if 0 < struct.unpack('<I', match[1])[0] < 0x200 and block[match.start() + 3:match.start() + 4] != b'\x03':
            marks.append((match.start(), text(match[2], encoding)))
    for match in CODE_HEADER.finditer(block):
        lines, offset = [], match.end()
        try:
            while block[offset:offset + 1] == b'\x03':
                line, after = framed_string(block, offset + 1, encoding)
                _, after = framed_string(block, after, encoding)
                lines.append(line)
                offset = after + 12
        except (ValueError, IndexError, struct.error):
            pass
        marks.append((match.start(), {'event': struct.unpack('<I', match[2])[0], 'lines': lines}))
    control, blocks = None, []
    for _, mark in sorted(marks, key=lambda item: item[0]):
        if isinstance(mark, str):
            control = mark
        else:
            blocks.append({'control': control, **mark})
    return blocks


# A predefined action that names an element, in a binary element's code block: the same record a text source keeps
# in an event slot (a word 4, the action's kind, a word, a word 1, a word, the element's name).
BINARY_ACTION = re.compile(rb'(?s)\x04\x00\x00\x00(.{4}).{4}\x01\x00\x00\x00.{4}'
                           rb'\xff\xce\x88\xf1.{4}([A-Za-z_\x80-\xff][\w$\x80-\xff]{0,200})\x00\xfe\xed\x98\xe1')


def binary_actions(block, encoding='cp1252'):
    """Predefined actions that name an element, from a binary element's code block: [{control, action_code,
    action_target}], the control being the last one named before the record."""
    owners = [(m.start(), text(m[2], encoding)) for m in CODE_OWNER.finditer(block)
              if 0 < struct.unpack('<I', m[1])[0] < 0x200]
    found = []
    for match in BINARY_ACTION.finditer(block):
        code = struct.unpack('<I', match[1])[0]
        control = next((name for start, name in reversed(owners) if start < match.start()), None)
        if 0 < code < 0x10000 and control and control != text(match[2], encoding):
            found.append({'control': control, 'action_code': code, 'action_target': text(match[2], encoding)})
    return found


def source_language(source):
    """The first language a text source declares (`languages : - pt-PT`)."""
    match = re.search(r'^ *languages :\s*\n *- *(\S+)', source, re.M)
    return match[1] if match else None


def layout_geometry(source, encoding='cp1252'):
    """Geometry for the inspector's layout items, in file order: (owner, name) -> list of boxes. Window controls in
    window pixels (only where the whole position is known), columns with their width, report bands and controls in
    millimetres (controls relative to their band)."""
    boxes = {}
    for element in decode_source(source, encoding):
        fields = element.get('fields') or {}
        box = None
        if 'x_mm' in fields:
            box = {'x': fields['x_mm'], 'y': fields['y_mm'], 'width': fields['width_mm'], 'height': fields['height_mm']}
            if element['owner'] == 'blocks':
                box['x'] = 0
        elif element['owner'] == 'controls' and 'window_x' in fields:
            box = {'x': fields['window_x'], 'y': fields['window_y'], 'width': fields['width'], 'height': fields['height']}
        elif element['owner'] == 'columns' and fields.get('width') is not None:
            box = {'width': fields['width']}
        if element['owner'] in ('controls', 'columns', 'blocks') and element['name']:
            boxes.setdefault((element['owner'], element['name']), []).append(box)
    return boxes


# ---------------------------------------------------------------- binary containers

def packed_blocks(data):
    """LZW blocks inside a PCS file, found by their header and kept only when they unpack to the declared size."""
    blocks, offset = [], 0
    while True:
        offset = data.find(b'\4', offset)
        if offset < 0 or offset + 11 > len(data):
            return blocks
        packed, size = struct.unpack_from('<II', data, offset + 1)
        if data[offset + 9:offset + 11] == b'\0\0' and 0 < packed <= len(data) - offset - 11 and 0 < size <= packed * 300:
            try:
                blocks.append((offset, packed, unpack(data[offset:offset + 11 + packed])))
                offset += 11 + packed
                continue
            except (ValueError, IndexError, KeyError):
                pass
        offset += 1


CODE_MARK = re.compile('\x08v[0-9a-fA-F]{16}|\x08')
# In a query block each SQL line is a record: 0x03, the line, the author, a date.
SQL_LINE = re.compile(rb'(?s)\x03\xff\xce\x88\xf1.{4}(.*?)\x00\xfe\xed\x98\xe1\xff\xce\x88\xf1')


def block_summary(block, encoding='cp1252'):
    found = strings(block, encoding)
    summary = {'size': len(block), 'sha256': hashlib.sha256(block).hexdigest(), 'strings': len(found)}
    if block[:2] == b'BM':
        summary['kind'] = 'image'
    elif re.search(rb'\xff\xce\x88\xf1.{4}\s*(SELECT|INSERT|UPDATE|DELETE)\b', block, re.S | re.I):
        summary['kind'] = 'sql'
        summary['sql'] = '\n'.join(text(m[1], encoding).replace('\t', ' ').rstrip() for m in SQL_LINE.finditer(block)).strip()
    return summary, found


def code_lines(texts):
    """Code kept in a binary container is one record per line: the line, then who wrote it. Returns the lines when
    a block looks like that (one short name makes up a quarter of its strings or more), else None. An empty line is
    stored without its text: a writer's name where a line is expected is one."""
    if len(texts) < 8:
        return None
    names = collections.Counter(value for value in texts
                                if len(value) <= 40 and re.fullmatch(r'[^\s()=";.,]+(?: [^\s()=";.,]+)?', value))
    if not names or names.most_common(1)[0][1] < len(texts) / 4:
        return None
    writers, lines, index = {names.most_common(1)[0][0]}, [], 0
    while index < len(texts):
        if texts[index] in writers:
            lines.append('')            # the record of an empty line
            index += 1
            continue
        lines.append(texts[index])
        if index + 1 < len(texts):
            writers.add(texts[index + 1])
        index += 2
    return lines if sum(bool(line.strip()) for line in lines) >= 3 else None


def project_folders(texts, elements):
    """The project explorer's own folders (a block starting with "Project"): {folder: [elements]} in file order.
    A string that is no element of the project is a folder; nesting of folders is not kept."""
    if not texts or texts[0] != 'Project':
        return None
    folders, current = {}, None
    for item in texts[1:]:
        if item.lower() in elements:
            if current is not None:
                folders[current].append(elements[item.lower()])
        elif item.strip():
            current = item
            folders.setdefault(current, [])
    return {folder: members for folder, members in folders.items() if members}


def used_files(text, elements):
    """A `.wdu` file lists every element followed by the files it uses: {element: [files]}."""
    used, current = {}, None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if Path(line).suffix.lower() in TEXT_EXTENSIONS | {'.wdd', '.wdg', '.wdc'} and '\\' not in line and '/' not in line:
            current = Path(line).stem
            used.setdefault(current, [])
        elif current is not None:
            used[current].append(line)
    return {element: files for element, files in used.items() if files}


def decode_container(data, encoding='cp1252'):
    if data[:4] != b'PCS\0':
        return None
    result = {'blocks': []}
    for offset, packed, block in packed_blocks(data):
        summary, found = block_summary(block, encoding)
        summary.update(offset=offset, packed=packed)
        summary['text'] = [CODE_MARK.sub('', item['text']) for item in found]
        result['blocks'].append((summary, block))
    return result


# ---------------------------------------------------------------- command

SKIN_VERSION = re.compile(rb'\d+\.\d+\.\d+\.\d+')
SKIN_STYLE = re.compile(r'[A-Za-z]+_\S.*')


def skin_styles(data, encoding='cp1252'):
    """The styles of a skin template's `.sty` file: {style name: fonts, frames, images}. The file is a PCS container
    that is not packed; each style is a record in the layout a control uses, opened by the WINDEV version that
    wrote it (`25.0.225.3`) and closed by the style's name (`BTN_Ok`)."""
    found = [m for m in FRAMED.finditer(data) if m[2]]
    starts = [index for index, match in enumerate(found) if SKIN_VERSION.fullmatch(match[2])]
    styles = {}
    for first, following in zip(starts, starts[1:] + [len(found)]):
        strings = found[first + 1:following]
        name = text(strings[-1][2], encoding) if strings else ''
        if not SKIN_STYLE.fullmatch(name) or IMAGE_FILE.search(strings[-1][2]):
            continue
        record = data[found[first].end():strings[-1].start()]
        faces = {text(m[2], encoding) for m in strings[:-1]}
        style = {'fonts': fonts(record, encoding)[0], 'frames': frames(record),
                 'images': [text(m[2], encoding).rsplit('\\', 1)[-1] for m in strings[:-1] if IMAGE_FILE.search(m[2])]}
        if style['fonts'] or style['frames'] or style['images'] or faces:
            styles.setdefault(name, style)
    return styles


def style_differences(element, style, limit=12):
    """What a control changed from the skin style it names, one line per value: `fonts[0].colour: #fe0000 (style
    #2d2d2d)`. Records are compared by their place; a different number of records is said as such."""
    lines = []
    for key in ('fonts', 'frames'):
        ours, theirs = element.get(key) or [], style.get(key) or []
        if len(ours) != len(theirs):
            lines.append(f'{key}: {len(ours)} records (style {len(theirs)})')
            continue
        for index, (mine, base) in enumerate(zip(ours, theirs)):
            for name in sorted(set(mine) | set(base)):
                if mine.get(name) != base.get(name):
                    lines.append(f'{key}[{index}].{name}: {mine.get(name)} (style {base.get(name)})')
    return lines[:limit]


ANALYSIS_ITEM = re.compile(rb'(?s)([A-Za-z_\x80-\xff][\w$\x80-\xff]*)\x00\d{8}\x00.{6}[^\x00]*\x00[^\x00]*\x00.{22}'
                           rb'([^\x00]*)\x00')


def analysis_records(block, encoding='cp1252'):
    """The items and keys of an analysis (`.wda`) in file order: [name, caption]. Each record is the name, the day
    it was created, six bytes, who created and who last changed it, 22 bytes, then its caption. Records follow the
    analysis file by file; items deleted since are still there. `schema_draft.py` gives them to the tables."""
    return [[text(m[1], encoding), text(m[2], encoding)] for m in ANALYSIS_ITEM.finditer(block)]


def read_text(data):
    if data.startswith((b'\xff\xfe', b'\xfe\xff')):
        return data.decode('utf-16')
    if b'\0' in data[:4096]:
        return None
    try:
        return data.decode('utf-8-sig')
    except UnicodeDecodeError:
        return data.decode('cp1252')


RATES = re.compile(r'Anchor rate to right (\d+) Anchor rate bottom (\d+) Anc. rate width (\d+) Anchor rate height (\d+)')


def anchor_rates(control):
    for line in control.get('raw') or []:
        match = RATES.match(line)
        if match:
            return dict(zip(('right', 'bottom', 'width', 'height'), map(int, match.groups())))
    return None


def squeeze(value):
    """The PDF wraps and re-spaces captions and can lose accented letters: compare the ASCII letters only."""
    return re.sub(r'[\s\x80-\U0010ffff]+', '', value or '')


def file_name(value):
    """An image's file name whatever the folder; the PDF wraps long names, so white space is dropped."""
    value = next(iter(value.values()), '') if isinstance(value, dict) else value or ''
    return re.sub(r'\s+', '', re.split(r'[\\/]', value)[-1]).lower()


WINDOW_FLAGS = (('Title bar', 'title_bar'), ('System menu', 'system_menu'), ('Minimize icon', 'minimize_icon'),
                ('Maximize icon', 'maximize_icon'), ('Indep. HFSQL ctx.', 'independent_hfsql_context'))


def raw_line(control, key):
    """The value of one "Key value" detail line of a dossier control."""
    return next((line[len(key) + 1:] for line in control.get('raw') or [] if line.startswith(key + ' ')), None)


def first_text(value):
    return next(iter(value.values()), '') if isinstance(value, dict) else value


def column_cells(elements):
    """{column name lower: (column fields with its index, its cell's fields)} for the names used once in the window."""
    found, seen = {}, collections.Counter(e['name'].lower() for e in elements if e['owner'] == 'columns')
    for element in elements:
        if element['owner'] == 'columns' and seen[element['name'].lower()] == 1:
            found[element['name'].lower()] = [{**(element.get('fields') or {}), 'index': element.get('index')}, {}]
        elif element['owner'] == 'content' and element['parents'] and element['parents'][-1].lower() in found:
            found[element['parents'][-1].lower()][1] = element.get('fields') or {}
    return found


def calibrate(decoded, dossier):
    """Compare decoded control fields with the dossier extract (`dossier_extract.py`), field by field."""
    report = {}

    def count(field, same):
        if same is not None:
            report.setdefault(field, {'same': 0, 'different': 0})['same' if same else 'different'] += 1
    for path in sorted(Path(dossier, 'windev-window').glob('*.json')):
        controls = json.loads(path.read_text(encoding='utf-8')).get('controls') or {}
        ours = {e['name'].lower(): e for e in decoded.get(path.stem.lower(), []) if e.get('fields') and e['owner'] == 'controls'}
        for name, theirs in controls.items():
            fields = (ours.get(name.lower()) or {}).get('fields')
            if not fields:
                continue
            caption = next(iter((theirs.get('caption') or {}).values()), None)
            checks = {'size': (theirs.get('width'), theirs.get('height')) == (fields['width'], fields['height'])
                      if theirs.get('width') is not None else None,
                      'window_position': (theirs.get('x'), theirs.get('y')) == (fields['window_x'], fields['window_y'])
                      if theirs.get('x') is not None and 'window_x' in fields else None,
                      # The dossier prints -1 for a control without a tab stop.
                      'tab_order': (not fields.get('tab_stop') or fields.get('tab_order') == 0)
                      if str(theirs.get('tab_order')) == '-1' else str(theirs['tab_order']) == str(fields.get('tab_order'))
                      if theirs.get('tab_order') is not None else None,
                      'anchor_rates': anchor_rates(theirs) == fields.get('anchor_rates') if anchor_rates(theirs) else None,
                      'state': theirs['state'].lower() == fields.get('state') if theirs.get('state') else None,
                      'caption': squeeze(caption) == squeeze(fields.get('caption', '')) if caption
                      else None,
                      'button_type': theirs['button_type'].lower() == fields.get('button_type')
                      if theirs.get('button_type') else None,
                      'plane': str(theirs['plane']) == str(fields['plane'])
                      if theirs.get('plane') is not None and 'plane' in fields else None,
                      'visible': theirs['flags']['Visible'] == fields.get('visible')
                      if 'Visible' in (theirs.get('flags') or {}) and 'visible' in fields else None,
                      'button_background_image': file_name(theirs.get('background_image')) == file_name(fields['background_image'])
                      if 'background_image' in fields else None,
                      'button_image': file_name(theirs.get('image')) == file_name(fields['image'])
                      if 'image' in fields else None,
                      'button_image_states': raw_line(theirs, 'Nb. image states') == str(fields['image_states'])
                      if 'image_states' in fields and raw_line(theirs, 'Nb. image states') else None,
                      'button_background_stretch': raw_line(theirs, 'Stretch background image').lower() == fields['background_stretch']
                      if 'background_stretch' in fields and raw_line(theirs, 'Stretch background image') else None}
            if 'input_type' in fields:          # an edit control's own record
                kind = (theirs.get('input_type') or '').lower()
                mask, align = first_text(theirs.get('input_mask')), raw_line(theirs, 'Horz. alignment')
                checks.update({
                    # The dossier's column cuts "High-precision numeric": a number whose value type is 13.
                    'input_type': (fields['input_type'] == 'numeric' and fields['value_type'] == 13) if kind.startswith('high')
                    else kind == fields['input_type'] if kind else None,
                    'input_size': theirs['input_size'] == fields['input_size'] if theirs.get('input_size') is not None else None,
                    'input_mask': squeeze(str(mask)) == squeeze(fields['input_mask'] or '0')
                    if mask is not None and 'input_mask' in fields else None,
                    'return_format': (raw_line(theirs, 'Return format') or '') == fields['return_format']
                    if 'return_format' in fields and raw_line(theirs, 'Input size') is not None else None,
                    'edit_alignment': align.lower() == fields['h_align'] if align else None})
            if 'caption_width' in fields and theirs.get('x') is not None and (raw_line(theirs, 'Inside X position') or '').isdigit():
                checks['input_area'] = (int(raw_line(theirs, 'Inside X position')) - theirs['x'] == fields['caption_width']
                                        and raw_line(theirs, 'Inside width') == str(fields['width'] - fields['caption_width']))
            lists = next((e['fields'] for e in decoded.get(path.stem.lower(), [])
                          if e.get('fields') and 'source' in e['fields']
                          and (e['name'] or (e['parents'] or [''])[-1]).lower() == name.lower()), None)
            if lists and theirs.get('kind') in ('Combo Box', 'List Box'):
                mode = re.search(r'(Memory|File wit|File loa)', theirs.get('row') or '')
                checks['list_source'] = lists['source'] == ('memory' if mode[1] == 'Memory' else 'file') if mode else None
                for key, label in (('browsed_file', 'Browsed file'), ('browsed_item', 'Browsed item'),
                                   ('displayed_item', 'Displayed item'), ('stored_item', 'Stored item')):
                    if raw_line(theirs, label) is not None or key in lists:
                        count('list_binding', squeeze(raw_line(theirs, label) or '') == squeeze(lists.get(key, '')))
                first = raw_line(theirs, 'Initial content ' + next(iter(theirs.get('caption') or {'PT': ''}), 'PT') + ':')
                if first is not None or 'initial_content' in lists:
                    checks['list_initial_content'] = squeeze(first or '') == squeeze((lists.get('initial_content') or [''])[0])
            if fields.get('tick_image') and theirs.get('image'):
                checks['tick_image'] = file_name(theirs['image']) == file_name(fields['tick_image'])
            row = re.search(r'(Left|Center|Right|Justifie)\w* (Top|Center|Bottom)$', theirs.get('row') or '')
            if row and 'v_align' in fields:
                # The dossier's column cuts "Justified".
                checks['static_alignment'] = (fields['h_align'].startswith(row[1].lower())
                                              and fields['v_align'] == row[2].lower())
            for field, same in checks.items():
                count(field, same)
        for name, (column, cell) in column_cells(decoded.get(path.stem.lower(), [])).items():
            theirs = next((c for n, c in controls.items() if n.lower() == name), None)
            if not theirs or 'h_align' not in column:
                continue
            flags = theirs.get('flags') or {}
            options = {'Sortable column': 'sortable', 'Moveable': 'moveable', 'Adjustable width': 'adjustable_width',
                       'Multiline': 'multiline', 'With search': 'with_search', 'Visible': 'visible'}
            count('column_alignment', theirs['h_align'].lower() == column['h_align'] if theirs.get('h_align') else None)
            for label, key in options.items():
                count('column_options', flags[label] == column[key] if label in flags else None)
            count('column_index', theirs['column_index'] == column['index'] if theirs.get('column_index') else None)
            if 'input_type' in cell and theirs.get('input_type'):
                kind = theirs['input_type'].lower()
                count('column_input_type', cell['value_type'] == 13 if kind.startswith('high') else kind == cell['input_type'])
            mask = first_text(theirs.get('input_mask'))
            if 'input_mask' in cell and mask is not None:
                # The dossier's table cuts a long mask: the start is compared.
                ours = squeeze(cell['input_mask'] or '0')
                count('column_input_mask', ours.startswith(squeeze(str(mask))) if squeeze(str(mask)) else None)
    for path in sorted(Path(dossier, 'report').glob('*.json')):
        element = json.loads(path.read_text(encoding='utf-8'))
        controls = element.get('controls') or {}
        ours = {e['name'].lower(): e for e in decoded.get(path.stem.lower(), []) if e.get('fields') and e['owner'] == 'controls'}
        for name, theirs in controls.items():
            fields = (ours.get(name.lower()) or {}).get('fields')
            if fields and 'x_mm' in fields and theirs.get('width_mm') is not None:
                count('report_geometry_mm',
                      all(abs(theirs.get(key, 0) - fields[key]) < 0.02 for key in ('x_mm', 'y_mm', 'width_mm', 'height_mm')))
            if fields and theirs.get('kind') and 'type_code' in fields:
                count('report_control_kind', theirs['kind'] == fields.get('kind'))
        page = next((e['fields'] for e in decoded.get(path.stem.lower(), []) if e['owner'] == 'report' and e.get('fields')), None)
        if page:
            count('report_type', element['report_type'].lower() == page['report_type']
                  if element.get('report_type') in ('Table', 'Label', 'Free') else None)
            count('report_data_source', element['data_source'].lower() == page['data_source'] if element.get('data_source') else None)
            count('report_margins_mm', element['margins_mm'] == page.get('margins_mm') if element.get('margins_mm') else None)
    for path in sorted(Path(dossier, 'windev-window').glob('*.json')):
        title = json.loads(path.read_text(encoding='utf-8')).get('title')
        title = next(iter(title.values()), '') if isinstance(title, dict) else title or ''
        window = next((e for e in decoded.get(path.stem.lower(), []) if e['owner'] == 'window' and e.get('fields')), None)
        if window:
            same = squeeze(re.sub(r'^[A-Z]{2}:$', '', title.strip())) == squeeze(window['fields'].get('title'))
            counts = report.setdefault('window_title', {'same': 0, 'different': 0})
            counts['same' if same else 'different'] += 1
            theirs, fields = json.loads(path.read_text(encoding='utf-8')), window['fields']
            if 'title_bar' in fields:
                flags = theirs.get('flags') or {}
                count('window_opening_mode', theirs['opening_mode'] == fields['opening_mode'] if theirs.get('opening_mode') else None)
                for label, key in WINDOW_FLAGS:
                    count('window_options', flags[label] == fields[key] if label in flags else None)
    return report


# The dossier's wording for each anchor combination seen; other combinations keep their rates only.
ANCHOR_NAMES = {0: '<None>', 1: 'Bottom', 2: 'Height', 4: 'Right', 5: 'Right and bottom', 6: 'Height and right',
                8: 'Width', 9: 'Width and bottom', 10: 'Width and height', 11: 'Bottom, height and width',
                12: 'Right and width', 14: 'Right, height and width', 15: 'Right and bottom, height and width'}


def existing(folder, stem):
    """A dossier file for this element whatever its case (WINDEV names are case-insensitive)."""
    return next((p for p in folder.glob('*.json') if p.stem.lower() == stem.lower()), folder / f'{stem}.json')


def merge_control(entry, element, language):
    """Put one decoded element into a dossier-shaped control entry. Decoded values replace the PDF's for the fields
    the decoder reads exactly; everything else the dossier had stays. `decoded` lists what was written."""
    fields, written = element['fields'], []

    def put(key, value):
        if value is not None and entry.get(key) != value:
            entry[key] = value
            written.append(key)

    if element.get('fonts') and not entry.get('fonts'):
        put('fonts', element['fonts'])
    if element.get('frames') and not entry.get('frames'):
        put('frames', element['frames'])
    if element.get('differs_from_style'):
        put('differs_from_style', element['differs_from_style'])    # what the control changed from its skin style
    def fill(key, value):
        if entry.get(key) in (None, '') and value not in (None, ''):
            put(key, value)

    def cell(source):
        # An edit control's own record, or a column's cell. The dossier writes 0 for no mask, and wraps a long one.
        if 'input_type' not in source:
            return
        fill('input_type', source['input_type'].capitalize() if isinstance(source['input_type'], str) else None)
        fill('input_size', source['input_size'])
        if source.get('input_mask'):
            old = entry.get('input_mask') if isinstance(entry.get('input_mask'), dict) else {}
            put('input_mask', {**old, next(iter(old), language): source['input_mask']})
        elif 'input_mask' in source:
            fill('input_mask', {language: '0'})
        if source.get('return_format') and raw_line(entry, 'Return format') is None:
            entry.setdefault('raw', []).append(f"Return format {source['return_format']}")
            written.append('return_format')

    for key in ('source', 'initial_content', 'browsed_file', 'browsed_item', 'displayed_item', 'stored_item'):
        if key in fields and 'source' in fields:
            fill('list_source' if key == 'source' else key, fields[key])
    if element['owner'] == 'dropdown':
        return written
    if element['owner'] == 'content':
        cell(fields)
        return written
    if element['owner'] == 'columns':
        entry.setdefault('kind', 'Table column')
        put('width', fields.get('width'))
        fill('column_index', element.get('index'))
        if 'h_align' in fields:
            fill('h_align', fields['h_align'].capitalize())
            fill('linked_item', fields['linked_item'])
            flags = entry.setdefault('flags', {})
            for label, key in (('Sortable column', 'sortable'), ('Moveable', 'moveable'), ('Adjustable width', 'adjustable_width'),
                               ('Multiline', 'multiline'), ('With search', 'with_search'), ('Visible', 'visible')):
                if label not in flags:
                    flags[label] = fields[key]
                    written.append(f'flags.{label}')
    elif 'x_mm' in fields:
        if element.get('kind'):
            entry.setdefault('kind', element['kind'])
        for key in ('x_mm', 'y_mm', 'width_mm', 'height_mm', 'linked_item', 'content'):
            if entry.get(key) is None and fields.get(key) is not None:
                put(key, fields[key])
        return written
    else:
        if element.get('kind'):
            entry.setdefault('kind', element['kind'])
        put('width', fields['width'])
        put('height', fields['height'])
        put('style', fields.get('style'))
        cell(fields)
        if isinstance(fields.get('h_align'), str):
            fill('h_align', fields['h_align'].capitalize())
            if raw_line(entry, 'Horz. alignment') is None and 'input_type' in fields:
                entry.setdefault('raw', []).append(f"Horz. alignment {fields['h_align'].capitalize()}")
        if fields.get('v_align'):
            fill('v_align', fields['v_align'].capitalize())
        if 'caption_width' in fields and raw_line(entry, 'Inside width') is None:
            # The dossier's two lines for where the input area is (its X in the window, its width).
            if 'window_x' in fields:
                entry.setdefault('raw', []).append(f"Inside X position {fields['window_x'] + fields['caption_width']}")
            entry.setdefault('raw', []).append(f"Inside width {fields['width'] - fields['caption_width']}")
            written.append('input_area')
        if 'window_x' in fields:
            put('x', fields['window_x'])
            put('y', fields['window_y'])
        if 'partial' not in fields:
            put('tab_order', fields['tab_order'] if fields['tab_stop'] and fields['tab_order'] else -1)
            put('state', {'active': 'Active', 'read-only': 'Read-only', 'grayed': 'Grayed'}.get(fields['state']))
            if isinstance(fields.get('button_type'), str):
                put('button_type', fields['button_type'].capitalize())
            if 'Visible' not in (entry.get('flags') or {}):
                entry.setdefault('flags', {})['Visible'] = fields['visible']
                written.append('flags.Visible')
            for key in ('background_image', 'image'):       # exact paths: the PDF wraps long file names
                if fields.get(key):
                    old = entry.get(key) if isinstance(entry.get(key), dict) else {}
                    put(key, {**old, next(iter(old), language): fields[key]})
            if fields.get('background_image') and not any(line.startswith('Nb. background states') for line in entry.get('raw', [])):
                entry.setdefault('raw', []).append(f"Nb. background states {fields['background_states']}")
            if fields.get('tick_image') and not entry.get('image'):
                put('image', {language: fields['tick_image']})
            if 'image_states' in fields and raw_line(entry, 'Nb. image states') is None:
                entry.setdefault('raw', []).append(f"Nb. image states {fields['image_states']}")
            if 'background_stretch' in fields and raw_line(entry, 'Stretch background image') is None:
                entry.setdefault('raw', []).append(f"Stretch background image {fields['background_stretch'].capitalize()}")
            for key in ('tooltip', 'linked_item', 'group', 'popup_menu', 'double_click_button'):
                if fields.get(key):
                    put(key, fields[key])
            if fields.get('initial_value') and not entry.get('initial_value'):
                put('initial_value', fields['initial_value'])
            put('plane', fields['plane'])
            put('order', fields['order'])
            if element.get('pane'):
                put('pane', element['pane'])
            if 'TAB Key' not in (entry.get('flags') or {}):
                entry.setdefault('flags', {})['TAB Key'] = fields['tab_stop']
            raw = entry.setdefault('raw', [])
            other = ('Anchor rate', 'Anchor to content', 'Anchor resources')
            mask = sum(bit for bit, name in ANCHOR_BITS.items() if name in fields['anchor'])
            if mask in ANCHOR_NAMES and not any(line.startswith('Anchor ') and not line.startswith(other) for line in raw):
                raw.append(f'Anchor {ANCHOR_NAMES[mask]}')
                written.append('anchor')
            if not any(RATES.match(line) for line in raw):
                rates = fields['anchor_rates']
                raw.append(f"Anchor rate to right {rates['right']} Anchor rate bottom {rates['bottom']} "
                           f"Anc. rate width {rates['width']} Anchor rate height {rates['height']}")
                written.append('anchor_rates')
    for name, value in (element.get('properties') or {}).items():
        # Properties a field map names, in the dossier's own form; what the dossier already says is kept.
        if isinstance(value, str) and value.startswith('unknown:'):
            continue
        if name.startswith('flag:'):
            if name[5:] not in (entry.get('flags') or {}):
                entry.setdefault('flags', {})[name[5:]] = value == 'True' if isinstance(value, str) else bool(value)
                written.append(name)
        elif name.startswith('line:'):
            if not any(line.startswith(name[5:] + ' ') for line in entry.setdefault('raw', [])):
                entry['raw'].append(f'{name[5:]} {value}')
                written.append(name)
        elif entry.get(name) in (None, '') and value != '':
            put(name, value)
    if fields.get('caption'):
        key = next(iter(entry['caption']), language) if isinstance(entry.get('caption'), dict) and entry['caption'] else language
        put('caption', {**(entry.get('caption') if isinstance(entry.get('caption'), dict) else {}), key: fields['caption']})
    return written


def write_evidence(sources, queries, target, dossier=None):
    """A folder in the shape `dossier_extract.py` writes, so every tool that reads a dossier reads the decoded values:
    a copy of the dossier extract when there is one (the fallback for what the decoder does not name), with decoded
    captions, geometry, tab order, state, button type, anchors and SQL written over it, and entries for the windows,
    controls, reports and queries the dossier lacks."""
    import shutil
    target = Path(target)
    if dossier:
        shutil.copytree(dossier, target)
    counts = {'elements': 0, 'controls': 0, 'new_elements': 0, 'new_controls': 0, 'queries': 0}
    for stem, item in sorted(sources.items()):
        folder = target / ('windev-window' if item['suffix'] == '.wdw' else 'report')
        if item['suffix'] not in ('.wdw', '.wde'):
            continue
        folder.mkdir(parents=True, exist_ok=True)
        path = existing(folder, stem)
        element = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'lines': []}
        counts['elements'] += 1
        counts['new_elements'] += not path.exists()
        language = item['language'] or 'default'
        known = {name.lower(): name for name in element.setdefault('controls', {})}
        # The menu as a tree in file order: each option with its caption and the options above it.
        menu = [{'name': decoded['name'], 'caption': decoded['fields']['caption'],
                 'under': [parent for parent in decoded['parents'][2:]]}
                for decoded in item['elements']
                if decoded['owner'] == 'options' and decoded['name'] and decoded.get('fields')
                and len(decoded['parents']) >= 2 and decoded['parents'][1].upper().startswith('MENU')]
        if menu:
            element['menu'] = menu
        bands, actions = [], []
        for decoded in item['elements']:
            fields = decoded.get('fields')
            if fields and decoded['owner'] == 'p_codes' and decoded['parents']:
                # A predefined action that names an element: who opens or prints it without a line of code.
                actions.append({'control': decoded['parents'][-1], 'target': fields['action_target'],
                                'code': fields['action_code']})
                continue
            if fields and decoded['owner'] in ('content', 'dropdown') and decoded['parents'] \
                    and known.get(decoded['parents'][-1].lower()):
                # A column's cell: its input type, size and mask belong to the column's entry.
                entry = element['controls'][known[decoded['parents'][-1].lower()]]
                entry['decoded'] = entry.get('decoded', []) + merge_control(entry, decoded, language)
                continue
            if fields and decoded['owner'] == 'report':
                for key, value in fields.items():      # what the dossier's "General information" says, when it lacks it
                    if element.get(key) in (None, ''):
                        element[key] = value.capitalize() if key in ('report_type', 'data_source') and isinstance(value, str) else value
                continue
            if not fields or not decoded['name']:
                continue
            if decoded['owner'] == 'blocks':
                bands.append({'name': decoded['name'], 'band': fields.get('band'),
                              **{key: fields[key] for key in ('y_mm', 'height_mm', 'width_mm')}})
                continue
            if decoded['owner'] == 'window':
                if not element.get('size'):
                    element['size'] = {key: fields[key] for key in ('x', 'y', 'width', 'height')}
                if fields.get('title'):
                    old = element.get('title') if isinstance(element.get('title'), dict) else {}
                    element['title'] = {**old, next(iter(old), language): fields['title']}
                if 'title_bar' in fields:
                    # The PDF prints these as tick marks in a grid and its extract mixes neighbours: the source wins.
                    flags = element.setdefault('flags', {})
                    flags.update({label: fields[key] for label, key in WINDOW_FLAGS})
                    if isinstance(fields['opening_mode'], str) and not element.get('opening_mode'):
                        element['opening_mode'] = fields['opening_mode']
                    if fields['background_image'] and not element.get('background_image'):
                        element['background_image'] = {language: fields['background_image']}
                continue
            if decoded['owner'] not in ('controls', 'columns'):
                continue
            name = known.get(decoded['name'].lower())
            if name is None:
                name = known[decoded['name'].lower()] = decoded['name']
                element['controls'][name] = {'raw': []}
                counts['new_controls'] += 1
            written = merge_control(element['controls'][name], decoded, language)
            if written:
                element['controls'][name]['decoded'] = written
            counts['controls'] += 1
        if bands:
            element['bands'] = bands
        if actions:
            element['predefined_actions'] = actions
        path.write_text(json.dumps(element, indent=1, ensure_ascii=False), encoding='utf-8')
    for name, sql in sorted(queries.items()):
        folder = target / 'query'
        folder.mkdir(parents=True, exist_ok=True)
        path = existing(folder, name)
        query = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'lines': []}
        if query.get('sql') and query['sql'] != sql:
            query['sql_pdf'] = query['sql']    # the PDF's text: wrapped and re-spaced
        query['sql'] = sql
        query['decoded'] = ['sql']
        # WINDEV writes a query's parameters in its SQL as {name}: their names in order of first use.
        names = list(dict.fromkeys(re.findall(r'\{(\w+)\}', sql)))
        if names:
            query['parameter_names'] = names
        path.write_text(json.dumps(query, indent=1, ensure_ascii=False), encoding='utf-8')
        counts['queries'] += 1
    index_path = target / 'index.json'
    index = json.loads(index_path.read_text(encoding='utf-8')) if index_path.exists() else {'images': False}
    index['decoded'] = {**counts, 'dossier': bool(dossier)}
    index_path.write_text(json.dumps(index, indent=1, ensure_ascii=False), encoding='utf-8')
    return counts


def decode_project(source, output, dossier=None, encoding='cp1252', raw=False, save_blocks=False, evidence=False,
                   fieldmap=None):
    source, output = Path(source).resolve(), Path(output).resolve()
    if not source.is_dir():
        raise ValueError('Source must be a directory')
    if output == source or source in output.parents:
        raise ValueError('Output must be outside the source directory')
    output.mkdir(parents=True, exist_ok=False)
    coverage = {'text_sources': 0, 'properties': 0, 'properties_failed': 0, 'controls': 0, 'controls_with_fields': 0,
                'controls_with_caption': 0, 'report_controls': 0, 'report_controls_with_geometry': 0, 'containers': 0, 'blocks': 0, 'queries_with_sql': 0,
                'embedded_queries_with_sql': 0, 'elements_with_learned_properties': 0, 'images': 0, 'binary_windows': 0, 'binary_window_controls': 0, 'binary_reports': 0, 'binary_report_controls': 0, 'binary_elements_with_code': 0,
                'binary_code_blocks': 0, 'binary_code_lines': 0, 'skin_styles': 0,
                'controls_with_skin_style': 0, 'controls_changed_from_skin_style': 0}
    files, by_name, queries, sources, samples, project, skins = [], {}, {}, {}, [], {}, {}
    text_stems, coded = set(), set()
    source_root = next((p.parent for p in sorted(source.rglob('*.wdp')) if '.cpl' not in p.as_posix().lower()), source)
    import sys
    if str(Path(__file__).resolve().parent) not in sys.path:
        sys.path.insert(0, str(Path(__file__).resolve().parent))    # when loaded from elsewhere (tests, another tool)
    import windev_fieldmap as mapper   # imports this module: loaded here, not at the top
    learned = mapper.load_map(fieldmap)
    for current, folders, names in os.walk(source):
        folders[:] = sorted(f for f in folders if f.lower() not in SKIP and not f.lower().startswith('bkp_'))
        for name in sorted(names):
            path = Path(current) / name
            relative = path.relative_to(source).as_posix()
            # Data files (some also start with PCS) and programs are not project elements: never load them.
            if path.suffix.lower() in DATA_EXTENSIONS or path.is_symlink():
                continue
            with path.open('rb') as handle:
                magic = handle.read(4)
            if magic != b'PCS\0' and path.suffix.lower() not in TEXT_EXTENSIONS:
                continue
            data = path.read_bytes()
            if data[:4] == b'PCS\0' and path.suffix.lower() == '.sty':
                # A skin template's styles: what a control's `style` (`<template>.<style>`) refers to.
                styles = skin_styles(data, encoding)
                if styles:
                    skins.setdefault(path.parent.name, styles)
                    target = output / 'skin' / f'{path.parent.name}.json'
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(json.dumps({'path': relative, 'template': path.parent.name, 'styles': styles},
                                                 indent=1, ensure_ascii=False), encoding='utf-8')
                    coverage['skin_styles'] += len(styles)
                    files.append({'path': relative, 'kind': 'skin', 'styles': len(styles)})
                continue
            if data[:4] == b'PCS\0' and path.suffix.lower() in ('.wdw', '.wde') and path.stem.lower() not in by_name:
                # A window or report in binary format with no text source of the same name: read it from the file.
                packed = packed_blocks(data)
                elements = (binary_window(packed[0][-1], encoding) if path.suffix.lower() == '.wdw'
                            else binary_report(packed[0][-1], encoding, [b[-1] for b in packed[1:]])) if packed else []
                if path.suffix.lower() == '.wdw' and elements:
                    # Its predefined actions, as the event slots of a text source carry them.
                    top = [e['name'] for e in elements if e['owner'] == 'window']
                    for other in packed[1:]:
                        elements += [{'line': None, 'owner': 'p_codes', 'name': '', 'type': '', 'parents': top + [a['control']],
                                      'fields': {'action_code': a['action_code'], 'action_target': a['action_target']}}
                                     for a in binary_actions(other[-1], encoding)]
                if len(elements) > 1:
                    by_name[path.stem.lower()] = elements
                    sources[path.stem] = {'elements': elements, 'suffix': path.suffix.lower(), 'path': relative,
                                          'relative': relative + '.json', 'language': None}
                    target = output / 'properties' / (relative + '.json')
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(json.dumps({'path': relative, 'format': 'binary', 'elements': elements}, indent=1,
                                                 ensure_ascii=False), encoding='utf-8')
                    files.append({'path': relative, 'kind': 'properties', 'elements': len(elements), 'format': 'binary'})
                    coverage['binary_windows' if path.suffix.lower() == '.wdw' else 'binary_reports'] += 1
                    coverage['binary_window_controls' if path.suffix.lower() == '.wdw' else 'binary_report_controls'] += \
                        sum(e['owner'] == 'controls' for e in elements)
            if data[:4] == b'PCS\0':
                container = decode_container(data, encoding)
                if not container['blocks']:
                    continue
                coverage['containers'] += 1
                entry = {'path': relative, 'blocks': []}
                for number, (summary, block) in enumerate(container['blocks']):
                    coverage['blocks'] += 1
                    if summary.get('kind') == 'image':
                        target = output / 'images' / f'{relative}.{number}.bmp'
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(block)
                        summary['file'] = target.relative_to(output).as_posix()
                        coverage['images'] += 1
                    elif save_blocks:
                        target = output / 'blocks' / f'{relative}.{number}.bin'
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(block)
                        summary['file'] = target.relative_to(output).as_posix()
                    if summary.get('sql') and path.suffix.lower() == '.wdr':
                        queries.setdefault(path.stem, summary['sql'])
                    if path.suffix.lower() == '.wda' and 'analysis' not in project:
                        records = analysis_records(block, encoding)
                        if records:
                            (output / 'analysis.json').write_text(
                                json.dumps({'path': relative, 'records': records}, indent=1, ensure_ascii=False), encoding='utf-8')
                            project['analysis'] = 'analysis.json'
                            coverage['analysis_item_records'] = len(records)
                    if path.suffix.lower() == '.wdp' and path.parent == source_root:
                        lines = code_lines(summary['text'])
                        if lines and 'code' not in project:
                            target = output / 'project' / f'{path.stem}.code.wl'
                            target.parent.mkdir(parents=True, exist_ok=True)
                            target.write_text('\n'.join(lines) + '\n', encoding='utf-8')
                            project['code'] = target.relative_to(output).as_posix()
                            project['code_lines'] = len(lines)
                        if summary['text'][:1] == ['Project']:
                            project['explorer_texts'] = summary['text']
                    elif path.suffix.lower() in ('.wdw', '.wde', '.wdg', '.wdc') and path.stem.lower() not in text_stems \
                            and path.stem.lower() not in coded:
                        # An element in binary format with no text source: its code blocks, each with the control it
                        # belongs to and its event, as one readable file and as data.
                        found = [b for b in binary_code(block, encoding) if any(line.strip() for line in b['lines'])]
                        if found:
                            listing = []
                            for part in found:
                                listing.append(f"// ---- {part['control'] or path.stem} : event {part['event']}")
                                part['line'] = len(listing) + 1       # of its first line in the .wl file
                                listing += part['lines'] + ['']
                            target = output / 'code' / f'{relative}.wl'
                            target.parent.mkdir(parents=True, exist_ok=True)
                            target.write_text('\n'.join(listing) + '\n', encoding='utf-8')
                            target.with_suffix('.json').write_text(
                                json.dumps({'path': relative, 'blocks': found}, indent=1, ensure_ascii=False), encoding='utf-8')
                            coded.add(path.stem.lower())
                            coverage['binary_elements_with_code'] += 1
                            coverage['binary_code_blocks'] += len(found)
                            coverage['binary_code_lines'] += sum(len(part['lines']) for part in found)
                    entry['blocks'].append(summary)
                target = output / 'containers' / (relative + '.json')
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps(entry, indent=1, ensure_ascii=False), encoding='utf-8')
                files.append({'path': relative, 'kind': 'container', 'blocks': len(entry['blocks'])})
            elif path.suffix.lower() in TEXT_EXTENSIONS:
                source_text = read_text(data)
                if not source_text or 'internal_properties' not in source_text:
                    continue
                elements = decode_source(source_text, encoding, raw, mapper, learned, path.stem, path.suffix.lower(),
                                         samples if path.stem.lower() not in by_name else None)
                coverage['text_sources'] += 1
                text_stems.add(path.stem.lower())
                for element in elements:
                    if element.get('sql') and element['name']:
                        queries.setdefault(element['name'], element['sql'])
                        coverage['embedded_queries_with_sql'] += 1
                    coverage['elements_with_learned_properties'] += 'properties' in element
                    coverage['properties'] += 1
                    coverage['properties_failed'] += 'error' in element
                    if element['owner'] == 'controls' and path.suffix.lower() == '.wde':
                        coverage['report_controls'] += 1
                        coverage['report_controls_with_geometry'] += 'fields' in element
                    if element['owner'] == 'controls' and path.suffix.lower() == '.wdw':
                        coverage['controls'] += 1
                        coverage['controls_with_fields'] += 'fields' in element and 'partial' not in element['fields']
                        coverage['controls_with_caption'] += bool((element.get('fields') or {}).get('caption'))
                # A project element wins over a same-named file deeper in the tree (templates, copies).
                if path.stem.lower() not in by_name:
                    by_name[path.stem.lower()] = elements
                    sources[path.stem] = {'elements': elements, 'suffix': path.suffix.lower(), 'path': relative,
                                          'relative': relative + '.json', 'language': source_language(source_text)}
                target = output / 'properties' / (relative + '.json')
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps({'path': relative, 'elements': elements}, indent=1, ensure_ascii=False),
                                  encoding='utf-8')
                files.append({'path': relative, 'kind': 'properties', 'elements': len(elements)})
    coverage['queries_with_sql'] = len(queries)
    # What each control changed from the style it was created from: its own fonts or frames differ from the skin's.
    # (Skin files can come after the windows in the tree: compared here, written back into the properties files.)
    for stem, item in sources.items():
        changed = False
        for element in item['elements']:
            template, _, style = ((element.get('fields') or {}).get('style') or '').partition('.')
            known = skins.get(template, {}).get(style)
            if element['owner'] != 'controls' or not known:
                continue
            coverage['controls_with_skin_style'] += 1
            differs = style_differences(element, known)
            if differs:
                element['differs_from_style'] = differs
                coverage['controls_changed_from_skin_style'] += 1
                changed = True
        if changed:
            (output / 'properties' / item['relative']).write_text(
                json.dumps({'path': item['path'], 'elements': item['elements']}, indent=1, ensure_ascii=False), encoding='utf-8')
    # Project level: its own code (written above), the explorer's folders, the files each element uses.
    elements = {Path(f['path']).stem.lower(): Path(f['path']).stem for f in files}
    folders = project_folders(project.pop('explorer_texts', None), elements)
    if folders:
        project['folders'] = folders
    for path in sorted(source_root.glob('*.wdu')):
        project['used_files'] = used_files(path.read_bytes().decode(encoding, 'replace'), elements)
    if project:
        (output / 'project').mkdir(exist_ok=True)
        (output / 'project' / 'project.json').write_text(json.dumps(project, indent=1, ensure_ascii=False), encoding='utf-8')
    coverage['project_code_lines'] = project.get('code_lines', 0)
    if queries:
        (output / 'queries.json').write_text(json.dumps(queries, indent=1, ensure_ascii=False), encoding='utf-8')
    index = {'format_version': 1, 'coverage': coverage, 'files': files,
             'project': {key: (len(value) if isinstance(value, dict) else value) for key, value in project.items()},
             'limitations': ['Named fields exist for window controls, windows, table columns and report geometry; other elements list '
                             'their strings in file order.',
                             'x/y are relative to the parent control; window_x/window_y exist except inside a table or a '
                             'tab whose style is not known.',
                             'Field offsets come from a format-25 project: check coverage and calibration elsewhere.',
                             'Outputs contain business logic and possibly secrets: keep them local.']}
    # What no named property explains: per element, the bytes that differ from the usual value of its kind.
    summary, findings = mapper.audit(samples, learned)
    (output / 'audit.json').write_text(json.dumps({'summary': summary, 'elements': findings}, indent=1), encoding='utf-8')
    index['audit'] = {'chunks': sum(v['elements'] for v in summary.values()),
                      'without_unexplained_difference': sum(v['without_unexplained_difference'] for v in summary.values()),
                      'unexplained_runs': sum(v['unexplained_runs'] for v in summary.values()),
                      'field_map_variants': len(learned)}
    if dossier:
        index['calibration'] = calibrate(by_name, dossier)
    if evidence:
        index['evidence'] = write_evidence(sources, queries, output / 'evidence', dossier)
    (output / 'index.json').write_text(json.dumps(index, indent=1, ensure_ascii=False), encoding='utf-8')
    return index


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('source', type=Path, help='the WINDEV project folder')
    parser.add_argument('--out', required=True, type=Path, help='new output directory; holds business logic')
    parser.add_argument('--dossier', type=Path, help='a dossier_extract.py folder to compare the decoded fields with')
    parser.add_argument('--encoding', default='cp1252', help='code page of non-Unicode strings (default cp1252)')
    parser.add_argument('--raw', action='store_true', help='keep each chunk as hex (to map more fields)')
    parser.add_argument('--blocks', action='store_true', help='save every unpacked container block')
    parser.add_argument('--evidence', action='store_true',
                        help='also write <out>/evidence: the decoded values in the dossier extract\'s shape (over a copy '
                             'of --dossier when given), for the tools that read a dossier')
    parser.add_argument('--fieldmap', type=Path,
                        help='properties learned by windev_fieldmap.py (default: windev_fieldmap.json beside this script)')
    args = parser.parse_args()
    try:
        index = decode_project(args.source, args.out, args.dossier, args.encoding, args.raw, args.blocks, args.evidence,
                               args.fieldmap)
    except (OSError, ValueError, LookupError) as error:
        parser.exit(1, f'Decoding failed: {error}\n')
    print(json.dumps({key: index[key] for key in ('coverage', 'audit', 'calibration', 'evidence') if key in index}, indent=2))


if __name__ == '__main__':
    main()
