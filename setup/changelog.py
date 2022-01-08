#!/usr/bin/env python
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>

from datetime import date


def parse(raw, parse_dates=True):
    entries = []
    current_entry = None
    current_section = 'new features'

    def normal(linenum, line, stripped_line):
        nonlocal current_entry, current_section
        if not stripped_line:
            return normal
        if stripped_line.startswith('{' '{' '{'):
            parts = line.split()[1:]
            if len(parts) != 2:
                raise ValueError(f'The entry start line is malformed: {line}')
            if current_entry is not None:
                raise ValueError(f'Start of entry while previous entry is still active at line: {linenum}')
            version, draw = parts
            if parse_dates:
                d = date(*map(int, draw.split('-')))
            else:
                d = draw
            current_entry = {'version': version, 'date': d, 'new features': [], 'bug fixes': [], 'improved recipes': [], 'new recipes': []}
            current_section = 'new features'
            return in_entry
        raise ValueError(f'Invalid content at line {linenum}: {line}')

    def in_entry(linenum, line, stripped_line):
        nonlocal current_section, current_entry
        if stripped_line == '}' '}' '}':
            if current_entry is None:
                raise ValueError(f'Entry terminator without active entry at line: {linenum}')
            entries.append(current_entry)
            current_entry = None
            return normal
        if line.startswith(':: '):
            current_section = line[3:].strip()
            if current_section not in ('new features', 'bug fixes', 'new recipes', 'improved recipes'):
                raise ValueError(f'Unknown section: {current_section}')
            return in_entry
        if line.startswith('-'):
            return start_item(linenum, line, stripped_line)
        if not stripped_line:
            return in_entry
        raise ValueError(f'Invalid content at line {linenum}: {line}')

    def start_item(linenum, line, stripped_line):
        line = line[1:].lstrip()
        items = current_entry[current_section]
        if current_section == 'improved recipes':
            items.append(line.rstrip())
            return in_entry
        if current_section == 'new recipes':
            idx = line.rfind('by ')
            if idx == -1:
                items.append({'title': line.strip()})
            else:
                items.append({'title': line[:idx].strip(), 'author': line[idx + 3:].strip()})
            return in_entry
        item = {}
        if line.startswith('['):
            idx = line.find(']')
            if idx == -1:
                raise ValueError(f'No closing ] found in line: {linenum}')
            for x in line[1:idx].split():
                if x == 'major':
                    item['type'] = x
                    continue
                num = int(x)
                item.setdefault('tickets', []).append(num)
            item['title'] = line[idx+1:].strip()
        else:
            item['title'] = line.strip()
        items.append(item)
        return in_item

    def finalize_item(item):
        if 'description' in item and not item['description']:
            del item['description']
        if 'description' in item:
            item['description'] = item['description'].strip()
        return item

    def in_item(linenum, line, stripped_line):
        item = current_entry[current_section][-1]
        if line.startswith('::'):
            finalize_item(item)
            return in_entry(linenum, line, stripped_line)
        if line.startswith('-'):
            finalize_item(item)
            return start_item(linenum, line, stripped_line)
        if line.startswith('}' '}' '}'):
            return in_entry(linenum, line, stripped_line)
        if not stripped_line:
            if 'description' not in item:
                item['description'] = ''
            return in_item
        if 'description' in item:
            item['description'] += stripped_line + ' '
        else:
            item['title'] += ' ' + stripped_line
        return in_item

    state = normal
    for i, line in enumerate(raw.splitlines()):
        if line.startswith('#'):
            continue
        stripped_line = line.strip()
        state = state(i + 1, line, stripped_line)
    return entries


def migrate():
    from yaml import safe_load

    def output_item(item, lines):
        meta = []
        if item.get('type') == 'major':
            meta.append(item['type'])
        for x in item.get('tickets', ()):
            meta.append(str(x))
        title = item['title']
        if meta:
            meta = ' '.join(meta)
            title = f'[{meta}] {title}'
        lines.append(f'- {title}')
        d = item.get('description')
        if d:
            lines.append(''), lines.append(d)
        lines.append('')

    for name in ('Changelog.yaml', 'Changelog.old.yaml'):
        entries = safe_load(open(name).read())
        lines = []
        for entry in entries:
            lines.append('')
            lines.append('{' '{' '{' f' {entry["version"]} {entry["date"]}')
            for w in ('new features', 'bug fixes'):
                nf = entry.get(w)
                if nf:
                    lines.append(f':: {w}'), lines.append('')
                    for x in nf:
                        output_item(x, lines)
                    lines.append('')
            nr = entry.get('new recipes')
            if nr:
                lines.append(':: new recipes'), lines.append('')
                for r in nr:
                    aut = r.get('author') or r.get('authors')
                    title = r['title']
                    if title:
                        if aut:
                            lines.append(f'- {title} by {aut}')
                        else:
                            lines.append(f'- {title}')
                lines.append('')
            ir = entry.get('improved recipes')
            if ir:
                lines.append(':: improved recipes'), lines.append('')
                for r in ir:
                    lines.append(f'- {r}')
                lines.append('')
            with open(name.replace('yaml', 'txt'), 'w') as f:
                f.write('\n'.join(lines))
            lines.append(''), lines.append('}' '}' '}'), lines.append('')


if __name__ == '__main__':
    migrate()
