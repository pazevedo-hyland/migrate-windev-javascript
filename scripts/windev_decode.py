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
        colour = data[match.end():match.end() + 4]
        if len(colour) == 4 and colour[3] == 0:
            font['colour'] = '#%02x%02x%02x' % (colour[0], colour[1], colour[2])
        found.append(font)
        spans += [(start - 28, 28), (match.end(), 4)]
    return found, spans


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
        fields['_end'] = offset + 28
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


def column_fields(data, encoding='cp1252'):
    """A table column's chunk 0: version tag, width, caption."""
    try:
        caption, _ = framed_string(data, 8, encoding)
    except (ValueError, IndexError, struct.error):
        return None
    width = struct.unpack_from('<I', data, 4)[0]
    return {'width': width, 'caption': caption} if width < 20000 else None


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
    return {'x_mm': round(left, 3), 'y_mm': round(top, 3), 'width_mm': round(right - left, 3),
            'height_mm': round(bottom - top, 3)}


def button_tail(data, end, encoding='cp1252'):
    """What follows a button's common block: caption, background image, its number of states, image. The record
    starts 107 or 111 bytes after the block; a reading is kept only when its strings are exactly the first strings
    found there, so a shifted layout is refused instead of misread."""
    found = [m.start() for m in FRAMED.finditer(data, end) if m[2]]
    for start in (end + 107, end + 111):
        try:
            caption, after_caption = framed_string(data, start, encoding)
            background, after_background = framed_string(data, after_caption, encoding)
            states = struct.unpack_from('<I', data, after_background)[0]
            image, _ = framed_string(data, after_background + 4, encoding)
        except (ValueError, IndexError, struct.error):
            continue
        used = [offset for offset, value in ((start, caption), (after_caption, background), (after_background + 4, image))
                if value]
        if used and used == found[:len(used)]:
            return {'caption': caption, 'background_image': background, 'background_states': states, 'image': image}
    return None


def describe(owner, kind, chunks, encoding='cp1252', keep_end=False):
    """Named fields for the element kinds whose layout is known; every chunk's strings for all of them."""
    by_id = {c['id']: c['data'] for c in chunks}
    fields = None
    if owner == 'controls' and 0 in by_id:
        fields = control_fields(by_id[0], encoding)
        end = fields.pop('_end', None) if fields else None
        spans = fields.pop('_spans', []) if fields else []
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
    elif owner in ('controls', 'blocks') and 15 in by_id:
        fields = report_fields(by_id[15], encoding)
        if fields is not None and owner == 'controls':
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
    elif owner == 'columns' and 0 in by_id:
        fields = column_fields(by_id[0], encoding)
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
    elements, panes = [], {}
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
        for chunk in chunks:
            if chunk['data'][:4] == b'PCS\0':   # an embedded query is a whole container inside the element
                sql = next((s['sql'] for s, _ in decode_container(chunk['data'], encoding)['blocks'] if s.get('sql')), None)
                if sql:
                    entry['sql'] = sql
        if slot['owner'] == 'controls' and slot['type'] in KINDS:
            entry['kind'] = KINDS[slot['type']]
        # A tab's panes come before their controls: a control directly under a tab is in the last pane seen.
        if slot['owner'] == 'tabs':
            panes[tuple(slot['parents'])] = panes.get(tuple(slot['parents']), 0) + 1
            entry['pane'] = panes[tuple(slot['parents'])]
        elif slot['owner'] == 'controls' and tuple(slot['parents']) in panes:
            entry['pane'] = panes[tuple(slot['parents'])]
        elements.append(entry)
    # Window coordinates: the parents' positions added, plus each tab's pane origin where its style is known.
    # A table (9) places controls in cells: those children keep parent-relative positions only.
    controls = {e['name']: e for e in elements if e['owner'] == 'controls' and 'x' in e.get('fields', ())}
    for entry in controls.values():
        chain = [controls[name] for name in entry['parents'] if name in controls]
        if any(parent['type'] == '9' or (parent['type'] == '16' and 'pane_top' not in parent['fields']) for parent in chain):
            continue
        entry['fields']['window_x'] = entry['fields']['x'] + sum(parent['fields']['x'] for parent in chain)
        entry['fields']['window_y'] = entry['fields']['y'] + sum(parent['fields']['y'] + parent['fields'].get('pane_top', 0)
                                                               for parent in chain)
    return elements


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


def calibrate(decoded, dossier):
    """Compare decoded control fields with the dossier extract (`dossier_extract.py`), field by field."""
    report = {}
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
                      if 'image' in fields else None}
            for field, same in checks.items():
                if same is not None:
                    counts = report.setdefault(field, {'same': 0, 'different': 0})
                    counts['same' if same else 'different'] += 1
    for path in sorted(Path(dossier, 'report').glob('*.json')):
        controls = json.loads(path.read_text(encoding='utf-8')).get('controls') or {}
        ours = {e['name'].lower(): e for e in decoded.get(path.stem.lower(), []) if e.get('fields') and e['owner'] == 'controls'}
        for name, theirs in controls.items():
            fields = (ours.get(name.lower()) or {}).get('fields')
            if fields and 'x_mm' in fields and theirs.get('width_mm') is not None:
                same = all(abs(theirs.get(key, 0) - fields[key]) < 0.02 for key in ('x_mm', 'y_mm', 'width_mm', 'height_mm'))
                counts = report.setdefault('report_geometry_mm', {'same': 0, 'different': 0})
                counts['same' if same else 'different'] += 1
    for path in sorted(Path(dossier, 'windev-window').glob('*.json')):
        title = json.loads(path.read_text(encoding='utf-8')).get('title')
        title = next(iter(title.values()), '') if isinstance(title, dict) else title or ''
        window = next((e for e in decoded.get(path.stem.lower(), []) if e['owner'] == 'window' and e.get('fields')), None)
        if window:
            same = squeeze(re.sub(r'^[A-Z]{2}:$', '', title.strip())) == squeeze(window['fields'].get('title'))
            counts = report.setdefault('window_title', {'same': 0, 'different': 0})
            counts['same' if same else 'different'] += 1
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
    if element['owner'] == 'columns':
        entry.setdefault('kind', 'Table column')
        put('width', fields.get('width'))
    elif 'x_mm' in fields:
        for key in ('x_mm', 'y_mm', 'width_mm', 'height_mm', 'linked_item', 'content'):
            if entry.get(key) is None and fields.get(key) is not None:
                put(key, fields[key])
        return written
    else:
        if element.get('kind'):
            entry.setdefault('kind', element['kind'])
        put('width', fields['width'])
        put('height', fields['height'])
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
        for decoded in item['elements']:
            fields = decoded.get('fields')
            if not fields or not decoded['name']:
                continue
            if decoded['owner'] == 'window':
                if not element.get('size'):
                    element['size'] = {key: fields[key] for key in ('x', 'y', 'width', 'height')}
                if fields.get('title'):
                    old = element.get('title') if isinstance(element.get('title'), dict) else {}
                    element['title'] = {**old, next(iter(old), language): fields['title']}
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
                'embedded_queries_with_sql': 0, 'elements_with_learned_properties': 0, 'images': 0}
    files, by_name, queries, sources, samples, project = [], {}, {}, {}, [], {}
    source_root = next((p.parent for p in sorted(source.rglob('*.wdp')) if '.cpl' not in p.as_posix().lower()), source)
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
                    sources[path.stem] = {'elements': elements, 'suffix': path.suffix.lower(),
                                          'language': source_language(source_text)}
                target = output / 'properties' / (relative + '.json')
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps({'path': relative, 'elements': elements}, indent=1, ensure_ascii=False),
                                  encoding='utf-8')
                files.append({'path': relative, 'kind': 'properties', 'elements': len(elements)})
    coverage['queries_with_sql'] = len(queries)
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
