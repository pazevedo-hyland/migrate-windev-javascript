#!/usr/bin/env python3
"""What the WLanguage code touches: tables read and written, queries, procedures, windows, reports and globals, per unit.

Read from the inspector's code blocks (plain text, so nothing here is decoded or guessed), the schema's table names,
the decoder's query SQL and control bindings:

  python3 scripts/code_map.py <inspect dir> [--decoded <decoded dir>] --out docs/code-map.md

  docs/code-map.json   per unit: tables (read / write / delete / assign, each with `path:line` sites), named queries,
                       procedures called, windows opened, reports printed, classes used, project globals used;
                       per table: its readers and writers; per procedure: where defined and who calls it
  docs/code-map.md     the same for people: a table x unit matrix, units by what they depend on, what nothing calls

It is a text search, not a compiler: a table name built at run time (`{sTable}`, indirection, a string assembled from
variables) is not seen. Those sites are listed under `dynamic` with their line, so they are read by a person, not
missed. A name in SQL that is no table of the analysis (another database, an alias) is listed under `unknown_tables`.
"""
import argparse
import collections
import json
from pathlib import Path
import re

READ = ('hread', 'hseek', 'hfound', 'hfilter', 'hnbrec', 'hout', 'hfirst', 'hlast', 'hnext', 'hprevious', 'hsavepos',
        'hexecutequery', 'hrecnum', 'hdeactivatefilter', 'hactivatefilter', 'hposition', 'hbuildkeyvalue',
        'hcopyrecord', 'filetoscreen', 'filetopage', 'hlistitem', 'hstatrec')
WRITE = ('hadd', 'hmodify', 'hwrite', 'hsave', 'hcross', 'screentofile', 'pagetofile', 'himportxml', 'himporttext',
         'hcopyfile', 'hsubstdir', 'hcreation')
DELETE = ('hdelete', 'hdeleteall')
OPENERS = re.compile(r'\b(Open\w*|OpenChild|OpenSister|OpenPopup\w*|ChangeSourceWindow|Use)\s*\(\s*"?([A-Za-z_]\w*)', re.I)
PRINTERS = re.compile(r'\b(iPrintReport|iInitReportQuery|iInitSubReport|iAddReport\w*|iSequencingAdd)\s*\(\s*"?([A-Za-z_]\w*)', re.I)
H_CALL = re.compile(r'\b(H[A-Za-z]\w+|FileToScreen|ScreenToFile|FileToPage|PageToFile)\s*\(\s*([^,)\n]*)')
FOR_EACH = re.compile(r'\bFOR\s+(?:EACH|ALL)\s+(?:\w+\s+OF\s+)?([A-Za-z_]\w*)', re.I)
SQL_READ = re.compile(r'\b(?:FROM|JOIN)\s+([A-Za-z_][\w$]*(?:\s*,\s*[A-Za-z_][\w$]*)*)', re.I)
SQL_WRITE = re.compile(r'\b(?:INSERT\s+INTO|UPDATE)\s+([A-Za-z_][\w$]*)', re.I)
SQL_DELETE = re.compile(r'\bDELETE\s+FROM\s+([A-Za-z_][\w$]*)', re.I)
DECLARATION = re.compile(r'^\s*(?:GLOBAL\s+)?([A-Za-z_]\w*(?:\s*,\s*[A-Za-z_]\w*)*)\s+(?:is|est|are|sont)\s+(?:an?\s+|une?\s+)?([\w ]+)', re.I)
CONSTANT = re.compile(r'^\s*([A-Za-z_]\w*)\s*=\s*[^=]')
CLASS_USE = re.compile(r'\b(?:is|est)\s+(?:an?\s+|une?\s+)?(?:dynamic\s+)?([A-Za-z_]\w*)\b', re.I)
DYNAMIC = re.compile(r'\{\s*\w+\s*(?:,\s*\w+\s*)?\}|\bExecuteProcess\s*\(|\bHDescribe\w+\s*\(|\bHDeclareExternal\s*\(', re.I)
SQL_RUN = re.compile(r'\bHExecuteSQLQuery\s*\(', re.I)


def strip_comment(line):
    """A code line without its `//` comment (a `//` inside a string stays)."""
    inside = False
    for index, char in enumerate(line):
        if char == '"':
            inside = not inside
        elif not inside and line.startswith('//', index):
            return line[:index]
    return line


def load_units(inspect_dir):
    """Every inspected source: {'name', 'path', 'kind', 'blocks': [{'code', 'start_line', 'control', 'event', 'procedures'}]}."""
    inventory = json.loads(Path(inspect_dir, 'inventory.json').read_text(encoding='utf-8'))
    kinds = {entry['path']: entry['kind'] for entry in inventory['files']}
    units = []
    for path in sorted(Path(inspect_dir, 'code').rglob('*.json')):
        source = json.loads(path.read_text(encoding='utf-8'))
        units.append({'name': source.get('name') or Path(source['path']).stem, 'path': source['path'],
                      'kind': kinds.get(source['path'], Path(source['path']).suffix.lstrip('.')),
                      'blocks': [{'code': block['code'], 'start_line': block['start_line'],
                                  'control': '/'.join(block['context']['names']),
                                  'event': block['context']['siblings'].get('type'),
                                  'procedures': block.get('procedures', [])} for block in source['blocks']]})
    return units


def schema_tables(inspect_dir):
    """Table names of the analysis, as written (lower-cased key)."""
    tables = {}
    for path in Path(inspect_dir, 'schema').rglob('*.json'):
        for table in json.loads(path.read_text(encoding='utf-8'))['tables']:
            name = table['attributes'].get('Nom') or table['attributes'].get('Name')
            if name:
                tables[name.lower()] = name
    return tables


def sql_tables(sql, tables):
    """({table: operation}, names that are no table of the analysis) for one SQL text."""
    found, unknown = {}, set()

    def note(names, operation):
        for name in re.split(r'\s*,\s*', names):
            if name.lower() in tables:
                found.setdefault(tables[name.lower()], set()).add(operation)
            elif name.upper() not in ('SELECT', 'WHERE', 'SET', 'VALUES', 'DUAL'):
                unknown.add(name)
    for match in SQL_READ.finditer(sql):
        note(match[1], 'read')
    for match in SQL_WRITE.finditer(sql):
        note(match[1], 'write')
    for match in SQL_DELETE.finditer(sql):
        note(match[1], 'delete')
        found.get(tables.get(match[1].lower(), ''), set()).discard('read')    # DELETE FROM x is not a read of x
    return found, unknown


def operation_of(function):
    low = function.lower()
    if low.startswith(DELETE):
        return 'delete'
    if low.startswith(WRITE):
        return 'write'
    if low.startswith(READ):
        return 'read'
    return None


def project_globals(decoded_dir, units):
    """Names declared at project level: in the project's code (a binary .wdp, read by the decoder) and in the global
    declarations of procedure sets. {lower name: {'name', 'declared_in', 'kind': variable|constant}}."""
    found = {}

    def scan(lines, where):
        constant = False
        for line in lines:
            text = strip_comment(line).strip()
            if re.fullmatch(r'CONSTANTE?S?', text, re.I):
                constant = True
                continue
            if re.fullmatch(r'END|FIN', text, re.I):
                constant = False
                continue
            match = CONSTANT.match(text) if constant else DECLARATION.match(text)
            if not constant and re.match(r'(?:LOCAL|PRIVATE|PUBLIC|PROTECTED)\b', text, re.I):
                continue
            if match and not re.match(r'(?:PROCEDURE|FUNCTION|IF|FOR|WHILE|SWITCH|CASE|RETURN|RESULT)\b', text, re.I):
                for name in re.split(r'\s*,\s*', match[1]):
                    found.setdefault(name.lower(), {'name': name, 'declared_in': where,
                                                    'kind': 'constant' if constant else 'variable'})
    for unit in units:
        if unit['kind'] in ('procedures', 'project'):
            for block in unit['blocks']:
                if not block['procedures'] and not block['event']:
                    scan(block['code'].splitlines(), unit['name'])
    return found


def build(inspect_dir, decoded_dir=None):
    units, tables = load_units(inspect_dir), schema_tables(inspect_dir)
    queries = {}
    if decoded_dir and Path(decoded_dir, 'queries.json').exists():
        queries = json.loads(Path(decoded_dir, 'queries.json').read_text(encoding='utf-8'))
    query_names = {name.lower(): name for name in queries}
    query_names.update({unit['name'].lower(): unit['name'] for unit in units if unit['kind'] == 'query'})
    names = {unit['name'].lower(): unit for unit in units}
    procedures = {}      # lower name -> {'name', 'defined_in'}
    for unit in units:
        for block in unit['blocks']:
            for procedure in block['procedures']:
                procedures.setdefault(procedure.lower(), {'name': procedure, 'defined_in': [], 'callers': {}})
                procedures[procedure.lower()]['defined_in'].append(unit['name'])
    classes = {unit['name'].lower(): unit['name'] for unit in units if unit['kind'] == 'class'}
    # The project's own code (initialisation, global declarations) lives in the .wdp: when that file is binary the
    # inspector cannot read it, the decoder can.
    if decoded_dir and not any(unit['kind'] == 'project' and unit['blocks'] for unit in units):
        for path in sorted(Path(decoded_dir, 'project').glob('*.code.wl')):
            units.append({'name': path.name[:-len('.code.wl')] + ' (project code)', 'path': f'decoded:project/{path.name}',
                          'kind': 'project', 'blocks': [{'code': path.read_text(encoding='utf-8'), 'start_line': 1,
                                                         'control': '', 'event': None, 'procedures': []}]})
    declared = project_globals(decoded_dir, units)
    word = re.compile(r'[A-Za-z_][\w$]*')
    result = {}
    for unit in units:
        entry = {'kind': unit['kind'], 'path': unit['path'], 'tables': {}, 'queries': {}, 'calls': {}, 'opens': {},
                 'prints': {}, 'classes': set(), 'globals': collections.Counter(), 'unknown_tables': {}, 'dynamic': []}

        def touch(table, operation, site):
            sites = entry['tables'].setdefault(table, {}).setdefault(operation, [])
            if site not in sites:
                sites.append(site)
        own = {p.lower() for block in unit['blocks'] for p in block['procedures']}
        for block in unit['blocks']:
            lines = [strip_comment(line) for line in block['code'].splitlines()]
            # SQL run from this block whose text names no table of the analysis: built elsewhere or at run time.
            if any(SQL_RUN.search(line) for line in lines) and not any(sql_tables(line, tables)[0] for line in lines):
                entry['dynamic'].append(f"{unit['path']}:{block['start_line']}")
            for offset, line in enumerate(lines):
                if not line.strip():
                    continue
                site = f"{unit['path']}:{block['start_line'] + offset}"
                bare = re.sub(r'"(?:[^"]|"")*"', '""', line)        # the line without its string contents
                for match in H_CALL.finditer(bare):
                    target, operation = match[2].strip().strip('"'), operation_of(match[1])
                    target = re.split(r'[.\s]', target)[0]
                    if operation and target.lower() in tables:
                        touch(tables[target.lower()], operation, site)
                    elif target.lower() in query_names:
                        entry['queries'].setdefault(query_names[target.lower()], []).append(site)
                for match in FOR_EACH.finditer(bare):
                    if match[1].lower() in tables:
                        touch(tables[match[1].lower()], 'read', site)
                    elif match[1].lower() in query_names:
                        entry['queries'].setdefault(query_names[match[1].lower()], []).append(site)
                for match in re.finditer(r'\b([A-Za-z_]\w*)\.([A-Za-z_]\w*)\b(\s*(?:\+|-)?=(?!=))?', bare):
                    if match[1].lower() in tables:
                        touch(tables[match[1].lower()], 'assign' if match[3] else 'read', site)
                found, unknown = sql_tables(line, tables)
                for table, operations in found.items():
                    for operation in operations:
                        touch(table, operation, site)
                for name in unknown:
                    entry['unknown_tables'].setdefault(name, []).append(site)
                for pattern, key in ((OPENERS, 'opens'), (PRINTERS, 'prints')):
                    for match in pattern.finditer(line):
                        if match[2].lower() in names and names[match[2].lower()]['kind'] in ('window', 'report'):
                            entry[key].setdefault(names[match[2].lower()]['name'], []).append(site)
                if DYNAMIC.search(bare):
                    entry['dynamic'].append(site)
                for match in word.finditer(bare):
                    low = match[0].lower()
                    following = bare[match.end():match.end() + 2].lstrip()[:1]
                    if low in procedures and following == '(' and not re.search(r'\b(PROCEDURE|PROC[EÉ]DURE|FUNCTION)\s+$', bare[:match.start()], re.I):
                        if low not in own or unit['name'] not in procedures[low]['defined_in']:
                            entry['calls'].setdefault(procedures[low]['name'], []).append(site)
                            procedures[low]['callers'].setdefault(unit['name'], []).append(site)
                    elif low in query_names and following != '(' and low not in tables:
                        sites = entry['queries'].setdefault(query_names[low], [])
                        if site not in sites:
                            sites.append(site)
                    elif low in declared and following != '(' and declared[low]['declared_in'] != unit['name']:
                        entry['globals'][declared[low]['name']] += 1
                for match in CLASS_USE.finditer(bare):
                    if match[1].lower() in classes and classes[match[1].lower()] != unit['name']:
                        entry['classes'].add(classes[match[1].lower()])
        # A named query brings its own tables.
        for query in entry['queries']:
            found, unknown = sql_tables(queries.get(query, ''), tables)
            for table, operations in found.items():
                for operation in operations:
                    touch(table, f'{operation} (via {query})', entry['queries'][query][0])
        entry['classes'] = sorted(entry['classes'])
        entry['globals'] = dict(sorted(entry['globals'].items()))
        result[unit['name']] = entry
    # What the designer binds without code: a control's linked item, a table's browsed file (from the decoder).
    if decoded_dir:
        for path in Path(decoded_dir, 'properties').rglob('*.json'):
            unit = Path(path.name[:-5]).stem
            target = next((result[name] for name in result if name.lower() == unit.lower()), None)
            if not target:
                continue
            for element in json.loads(path.read_text(encoding='utf-8'))['elements']:
                bound = [(element.get('fields') or {}).get('linked_item')]
                bound += [(element.get('properties') or {}).get(key) for key in ('browsed_item', 'stored_item')]
                for item in filter(None, bound):
                    table = str(item).split('.')[0].lower()
                    if table in tables:
                        sites = target['tables'].setdefault(tables[table], {}).setdefault('bound control', [])
                        if element['name'] not in sites:
                            sites.append(element['name'])
    by_table = {}
    for name, entry in result.items():
        for table, operations in entry['tables'].items():
            for operation in operations:
                key = 'writers' if operation.startswith(('write', 'assign')) else 'deleters' if operation.startswith('delete') \
                    else 'bound' if operation == 'bound control' else 'readers'
                by_table.setdefault(table, {'readers': [], 'writers': [], 'deleters': [], 'bound': []})
                if name not in by_table[table][key]:
                    by_table[table][key].append(name)
    untouched = sorted(set(tables.values()) - set(by_table))
    return {'units': result, 'tables': dict(sorted(by_table.items())), 'tables_never_referenced': untouched,
            'procedures': {p['name']: {'defined_in': p['defined_in'], 'callers': p['callers']}
                           for p in sorted(procedures.values(), key=lambda p: p['name'].lower())},
            'globals': {g['name']: {'declared_in': g['declared_in'], 'kind': g['kind'],
                                    'used_by': sorted(n for n, e in result.items() if g['name'] in e['globals'])}
                        for g in sorted(declared.values(), key=lambda g: g['name'].lower())}}


def markdown(data):
    units, lines = data['units'], ['# Code map', '',
                                   'Generated by `scripts/code_map.py` from the code blocks: a text search, not a compiler. '
                                   'Sites marked dynamic build names at run time and must be read by a person.', '']
    lines += ['## Tables: who reads, writes and deletes', '', '| Table | Written by | Deleted by | Read by | Bound to controls of |',
              '|---|---|---|---|---|']
    short = lambda names: ', '.join(names[:12]) + (f' … (+{len(names) - 12})' if len(names) > 12 else '')
    for table, users in data['tables'].items():
        lines.append(f"| {table} | {short(users['writers'])} | {short(users['deleters'])} | {short(users['readers'])} | {short(users['bound'])} |")
    if data['tables_never_referenced']:
        lines += ['', 'Tables of the analysis no code or binding names: ' + ', '.join(data['tables_never_referenced']) + '.']
    lines += ['', '## Units', '', '| Unit | Kind | Writes | Deletes | Reads | Queries | Calls | Opens / prints | Globals | Dynamic sites |',
              '|---|---|---|---|---|---|---|---|---|---|']
    for name, entry in sorted(units.items(), key=lambda item: item[0].lower()):
        of = lambda prefixes: sorted(t for t, ops in entry['tables'].items() if any(op.startswith(prefixes) for op in ops))
        lines.append(f"| {name} | {entry['kind']} | {short(of(('write', 'assign')))} | {short(of(('delete',)))} | "
                     f"{short(of(('read',)))} | {short(sorted(entry['queries']))} | {len(entry['calls'])} | "
                     f"{short(sorted({**entry['opens'], **entry['prints']}))} | {len(entry['globals'])} | {len(entry['dynamic'])} |")
    unused = [name for name, p in data['procedures'].items() if not p['callers']]
    lines += ['', '## Procedures no other unit calls', '',
              'Called only inside their own unit, by an event, by name at run time, or not at all: check before leaving one out.', '',
              ', '.join(f"`{name}` ({', '.join(data['procedures'][name]['defined_in'])})" for name in unused) or '—']
    unknown = collections.Counter(name for entry in units.values() for name in entry['unknown_tables'])
    lines += ['', '## Names in SQL that are no table of the analysis', '',
              ', '.join(f'`{name}` ({count} units)' for name, count in unknown.most_common()) or '—']
    lines += ['', '## Project globals', '', '| Name | Kind | Declared in | Used by (units) |', '|---|---|---|---|']
    for name, info in data['globals'].items():
        lines.append(f"| {name} | {info['kind']} | {info['declared_in']} | {len(info['used_by'])} |")
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('inspect_dir', type=Path)
    parser.add_argument('--decoded', type=Path, help='windev_decode.py output: query SQL, control bindings, project code')
    parser.add_argument('--out', type=Path, required=True, help='the Markdown file; the JSON is written beside it')
    args = parser.parse_args()
    data = build(args.inspect_dir, args.decoded)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(markdown(data), encoding='utf-8')
    args.out.with_suffix('.json').write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding='utf-8')
    units = data['units']
    print(json.dumps({'units': len(units), 'tables_referenced': len(data['tables']),
                      'tables_never_referenced': len(data['tables_never_referenced']),
                      'units_writing_data': sum(1 for e in units.values() if any(op.startswith(('write', 'assign', 'delete'))
                                                                                 for ops in e['tables'].values() for op in ops)),
                      'procedures': len(data['procedures']), 'globals': len(data['globals']),
                      'dynamic_sites': sum(len(e['dynamic']) for e in units.values())}))


if __name__ == '__main__':
    main()
