#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import re, shlex, os
from collections import defaultdict

from calibre import walk, guess_type, prints, force_unicode
from calibre.constants import filesystem_encoding, cache_dir
from calibre.utils.icu import numeric_sort_key as sort_key
from calibre.utils.localization import canonicalize_lang, get_lang
from calibre.utils.serialize import msgpack_dumps, msgpack_loads
from polyglot.builtins import iteritems, itervalues, string_or_bytes


def parse_localized_key(key):
    name, rest = key.partition('[')[0::2]
    if not rest:
        return name, None
    return name, rest[:-1]


def unquote_exec(val):
    val = val.replace(r'\\', '\\')
    return shlex.split(val)


def known_localized_items():
    return {'Name': {}, 'GenericName': {}, 'Comment': {}, 'Icon': {}}


def parse_desktop_file(path):
    gpat = re.compile(r'^\[(.+?)\]\s*$')
    kpat = re.compile(r'^([-a-zA-Z0-9\[\]@_.]+)\s*=\s*(.+)$')
    try:
        with open(path, 'rb') as f:
            raw = f.read().decode('utf-8')
    except (OSError, UnicodeDecodeError):
        return
    group = None
    ans = {}
    ans['desktop_file_path'] = path
    localized_items = known_localized_items()
    for line in raw.splitlines():
        m = gpat.match(line)
        if m is not None:
            if group == 'Desktop Entry':
                break
            group = m.group(1)
            continue
        if group == 'Desktop Entry':
            m = kpat.match(line)
            if m is not None:
                k, v = m.group(1), m.group(2)
                if k == 'Hidden' and v == 'true':
                    return
                if k == 'Type' and v != 'Application':
                    return
                if k == 'Exec':
                    cmdline = unquote_exec(v)
                    if cmdline and (not os.path.isabs(cmdline[0]) or os.access(cmdline[0], os.X_OK)):
                        ans[k] = cmdline
                elif k == 'MimeType':
                    ans[k] = frozenset(x.strip() for x in v.split(';'))
                elif k in localized_items or '[' in k:
                    name, lang = parse_localized_key(k)
                    vals = localized_items.setdefault(name, {})
                    vals[lang] = v
                    if name in ans:
                        vals[None] = ans.pop(name)
                else:
                    ans[k] = v
    for k, vals in localized_items.items():
        if vals:
            ans[k] = dict(vals)
    if 'Exec' in ans and 'MimeType' in ans and 'Name' in ans:
        return ans


icon_data = None


def find_icons():
    global icon_data
    if icon_data is not None:
        return icon_data
    base_dirs = [(os.environ.get('XDG_DATA_HOME') or os.path.expanduser('~/.local/share')) + '/icons']
    base_dirs += [os.path.expanduser('~/.icons')]
    base_dirs += [
        os.path.join(b, 'icons') for b in os.environ.get(
            'XDG_DATA_DIRS', '/usr/local/share:/usr/share').split(os.pathsep)] + [
                '/usr/share/pixmaps']
    ans = defaultdict(list)
    sz_pat = re.compile(r'/((?:\d+x\d+)|scalable)/')
    cache_file = os.path.join(cache_dir(), 'icon-theme-cache.calibre_msgpack')
    exts = {'.svg', '.png', '.xpm'}

    def read_icon_theme_dir(dirpath):
        ans = defaultdict(list)
        for path in walk(dirpath):
            bn = os.path.basename(path)
            name, ext = os.path.splitext(bn)
            if ext in exts:
                sz = sz_pat.findall(path)
                if sz:
                    sz = sz[-1]
                    if sz == 'scalable':
                        sz = 100000
                    else:
                        sz = int(sz.partition('x')[0])
                    idx = len(ans[name])
                    ans[name].append((-sz, idx, sz, path))
        for icons in itervalues(ans):
            icons.sort(key=list)
        return {k:(-v[0][2], v[0][3]) for k, v in iteritems(ans)}

    try:
        with open(cache_file, 'rb') as f:
            cache = f.read()
        cache = msgpack_loads(cache)
        mtimes, cache = defaultdict(int, cache['mtimes']), defaultdict(dict, cache['data'])
    except Exception:
        mtimes, cache = defaultdict(int), defaultdict(dict)

    seen_dirs = set()
    changed = False

    for loc in base_dirs:
        try:
            subdirs = os.listdir(loc)
        except OSError:
            continue
        for dname in subdirs:
            d = os.path.join(loc, dname)
            if os.path.isdir(d):
                try:
                    mtime = os.stat(d).st_mtime
                except OSError:
                    continue
                seen_dirs.add(d)
                if mtime != mtimes[d]:
                    changed = True
                    try:
                        cache[d] = read_icon_theme_dir(d)
                    except Exception:
                        prints('Failed to read icon theme dir: %r with error:' % d)
                        import traceback
                        traceback.print_exc()
                    mtimes[d] = mtime
                for name, data in iteritems(cache[d]):
                    ans[name].append(data)
    for removed in set(mtimes) - seen_dirs:
        mtimes.pop(removed), cache.pop(removed)
        changed = True

    if changed:
        data = msgpack_dumps({'data':cache, 'mtimes':mtimes})
        try:
            with open(cache_file, 'wb') as f:
                f.write(data)
        except Exception:
            import traceback
            traceback.print_exc()

    for icons in itervalues(ans):
        icons.sort(key=list)
    icon_data = {k:v[0][1] for k, v in iteritems(ans)}
    return icon_data


def localize_string(data):
    lang = canonicalize_lang(get_lang())

    def key_matches(key):
        if key is None:
            return False
        base = re.split(r'[_.@]', key)[0]
        return canonicalize_lang(base) == lang

    matches = tuple(filter(key_matches, data))
    if matches:
        return data[matches[0]]
    return data.get(None) or ''


def process_desktop_file(data):
    icon = data.get('Icon', {}).get(None)
    if icon and not os.path.isabs(icon):
        icon = find_icons().get(icon)
        if icon:
            data['Icon'] = icon
        else:
            data.pop('Icon')
    if not isinstance(data.get('Icon'), string_or_bytes):
        data.pop('Icon', None)
    for k in ('Name', 'GenericName', 'Comment'):
        val = data.get(k)
        if val:
            data[k] = localize_string(val)
    return data


def find_programs(extensions):
    extensions = {ext.lower() for ext in extensions}
    data_dirs = [os.environ.get('XDG_DATA_HOME') or os.path.expanduser('~/.local/share')]
    data_dirs += (os.environ.get('XDG_DATA_DIRS') or '/usr/local/share/:/usr/share/').split(os.pathsep)
    data_dirs = [force_unicode(x, filesystem_encoding).rstrip(os.sep) for x in data_dirs]
    data_dirs = [x for x in data_dirs if x and os.path.isdir(x)]
    desktop_files = {}
    mime_types = {guess_type('file.' + ext)[0] for ext in extensions}
    ans = []
    for base in data_dirs:
        for f in walk(os.path.join(base, 'applications')):
            if f.endswith('.desktop'):
                bn = os.path.basename(f)
                if f not in desktop_files:
                    desktop_files[bn] = f
    for bn, path in iteritems(desktop_files):
        try:
            data = parse_desktop_file(path)
        except Exception:
            import traceback
            traceback.print_exc()
            continue
        if data is not None and mime_types.intersection(data['MimeType']):
            ans.append(process_desktop_file(data))
    ans.sort(key=lambda d:sort_key(d.get('Name')))
    return ans


def entry_sort_key(entry):
    return sort_key(entry['Name'])


def entry_to_cmdline(entry, path):
    path = os.path.abspath(path)
    rmap = {
        'f':path, 'F':path, 'u':'file://'+path, 'U':'file://'+path, '%':'%',
        'c':entry.get('Name', ''), 'k':entry.get('desktop_file_path', ''),
    }

    def replace(match):
        char = match.group()[-1]
        repl = rmap.get(char)
        return match.group() if repl is None else repl
    sub = re.compile(r'%[fFuUdDnNickvm%]').sub
    cmd = entry['Exec']
    try:
        idx = cmd.index('%i')
    except ValueError:
        pass
    else:
        icon = entry.get('Icon')
        repl = ['--icon', icon] if icon else []
        cmd[idx:idx+1] = repl
    return cmd[:1] + [sub(replace, x) for x in cmd[1:]]
